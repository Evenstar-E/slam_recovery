"""Run the native baseline or the stereo-inertial recovery transaction."""
import argparse
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import itertools
import os
import time
from pathlib import Path

import cv2

from .blind_history import recover_history
from .live import LiveInput, PosePublisher
from .standby import StandbyQueue
from .stream import EventLog, InputFault, Worker, euroc, read_pair
from .vision import (HeldOutStereo, healthy, in_public_world, input_support,
                     qualify_replay, replay_delta)


WORKER_FAILURE = (RuntimeError, TimeoutError, BrokenPipeError)


class Lane:
    def __init__(self, worker, delay, keep_journal=False):
        self.worker = worker
        self.delay = delay
        self.journal = [] if keep_journal else None
        self.pending_imu = []
        self.snapshot = None
        self.recent = deque(maxlen=16)
        self.gauge = None

    def consume(self, pair, view, images=None, **options):
        if self.journal is not None:
            self.journal.append((pair, view))
        self.pending_imu.extend(pair.imu)
        if view == "skip":
            return None
        snapshot = self.worker.track(
            pair, read_pair(pair, view) if images is None else images, self.pending_imu, **options)
        if self.snapshot is not None and snapshot['map_id'] != self.snapshot['map_id']:
            self.gauge = None
        self.snapshot = in_public_world(snapshot, self.gauge)
        self.recent.append(self.snapshot)
        self.pending_imu.clear()
        if self.delay:
            time.sleep(self.delay)
        return self.snapshot


def run(args, events, output):
    source = None
    publisher = None
    native = args.mode == "native"
    incremental = args.mode == "recover"
    vision = HeldOutStereo(args.settings)
    workers = []
    feature_workers = []
    command = args.worker, args.vocabulary, args.settings
    parallel = ThreadPoolExecutor(max_workers=1) if incremental else None
    queued = StandbyQueue(parallel) if incremental else None
    retired_workers = []

    def new_lane(name):
        worker = Worker(command, output / f"{name}.log", wait_ready=args.realtime,
                        feature_protocol=args.share_orb_features)
        feature_workers.append(worker)
        workers.append(worker)
        return Lane(worker, args.delay, keep_journal=args.mode == "qualify")

    def publish(result, channel, verified):
        if result is None or (channel not in ("inertial_history", "local_inertial_history")
                              and result["tracking"] != 2):
            return
        row = dict(result, type="pose", channel=channel, coordinate_verified=verified)
        if publisher is not None:
            row["delivery_id"] = publisher.send(row)
        kind = row.pop("type")
        events.emit(kind, **row)

    def replay(source, name):
        lane = new_lane(name)
        for pair, view in source.journal:
            lane.consume(pair, view)
        return lane

    def close(lane, name):
        if lane.worker in workers:
            events.emit("worker_exit", name=name, exit=lane.worker.close())
            workers.remove(lane.worker)

    active = None
    standby = None
    primary = None
    probation = []
    pending = []
    anchor_pair = None
    anchor = None
    history_anchor = None
    private = None
    event_id = 0
    origin = None
    aligned = True
    previous = None
    checkpoint_probe = None
    probe_remaining = 0
    imu_delta = None
    total = 0
    needs_rearm = False
    healthy_count = 0
    candidate_fitted = False
    standby_probe = None

    def retire_worker(lane, name):
        worker = lane.worker
        retired_workers.append((name, queued.retire(worker.close)))
        workers.remove(worker)

    def retire_busy_standby():
        nonlocal standby, standby_probe
        retire_worker(standby, "retired_standby")
        standby = None
        standby_probe = None

    def consume_public(pair, view, images=None):
        if standby is None:
            return active.consume(pair, view, images)
        if images is None and view != "skip":
            images = read_pair(pair, view)
        shared = args.share_orb_features and view == "raw"
        # With exchange enabled the primary creates the only feature packet
        # for this physical input. The standby consumes that exact packet.
        if shared:
            result = active.consume(pair, view, images, capture=True)
            features = active.worker.last_features
            feed = lambda: standby_lane.consume(pair, view, images, features=features)
        else:
            feed = lambda: standby_lane.consume(pair, view, images)
        standby_lane = standby
        try:
            if queued.offer(feed):
                events.emit("standby_queue_pressure", timestamp=pair.timestamp)
        except WORKER_FAILURE as error:
            events.emit("standby_unavailable", reason=str(error), timestamp=pair.timestamp)
            retire_busy_standby()
        return result if shared else active.consume(pair, view, images)

    def catch_up_standby(retired):
        nonlocal standby
        if not incremental:
            return
        started = time.monotonic_ns()
        try:
            for buffered, _, weak in pending:
                retired.consume(buffered, "skip" if weak else "fit")
        except WORKER_FAILURE as error:
            events.emit("standby_unavailable", reason=str(error), event=event_id)
            retire_worker(retired, "standby_catchup_failed")
            return
        standby = retired
        events.emit("standby_catchup", event=event_id, frames=len(pending),
                    through=retired.snapshot["timestamp"], started_ns=started,
                    finished_ns=time.monotonic_ns())

    def probe_standby():
        nonlocal standby_probe
        if standby_probe is None:
            return True
        rejected_event, after = standby_probe
        # The entire comparison window must be fresh raw input after rejection.
        if len(active.recent) < active.recent.maxlen or active.recent[0]["timestamp"] <= after:
            return False
        if not all(healthy(row) for row in active.recent):
            return False
        if not qualify_replay(active, standby, events, "standby_requalification",
                              event=rejected_event, after=after):
            return False
        events.emit("standby_restored", event=rejected_event,
                    before_candidate_event=event_id if event_id != rejected_event else None,
                    through=standby.snapshot["timestamp"],
                    coordinate_verified=aligned)
        standby_probe = None
        return True

    def observe_reentry(result):
        nonlocal needs_rearm, healthy_count
        if not needs_rearm:
            return
        healthy_count = healthy_count + 1 if result is not None and healthy(result) else 0
        if healthy_count >= 3:
            needs_rearm = False
            events.emit("rearmed", event=event_id, coordinate_verified=False,
                        timestamp=result["timestamp"])

    def reject(reason):
        nonlocal private, aligned, previous, imu_delta, anchor_pair, needs_rearm, healthy_count, standby
        nonlocal standby_probe
        events.emit("reject", event=event_id, reason=reason, preserved_anchor=anchor["timestamp"],
                    decided_ns=time.monotonic_ns())
        probationary_lane = None
        if private is not None:
            if not candidate_fitted and reason in ("bounded_candidate_window", "end_of_input"):
                # No native visual update was attempted. Only the unsent IMU queue
                # changed; both replicas can resume from the original boundary.
                private.pending_imu.clear()
                standby = private
            elif candidate_fitted and reason == "bounded_candidate_window":
                probationary_lane = private
            else:
                retire_worker(private, f"candidate-{event_id}")
            private = None
        aligned = False
        needs_rearm, healthy_count = True, 0
        for pair, view, weak in pending:
            result = consume_public(pair, "skip" if weak else view)
            publish(result, "local_unverified", False)
            observe_reentry(result)
            if result is not None:
                anchor_pair = pair
        if probationary_lane is not None:
            if (active.snapshot["timestamp"] == probationary_lane.snapshot["timestamp"]
                    and active.pending_imu == probationary_lane.pending_imu):
                standby = probationary_lane
                after = pending[-1][0].timestamp
                standby_probe = event_id, after
                events.emit("standby_probation", event=event_id, after=after)
            else:
                retire_worker(probationary_lane, f"candidate-{event_id}")
        previous = active.snapshot
        imu_delta = None
        pending.clear()
        probation.clear()

    try:
        if args.subscriber is not None:
            publisher = PosePublisher(args.subscriber)
        active = new_lane("native")
        if incremental:
            standby = new_lane("standby")
        if args.realtime:
            source = LiveInput(args.dataset, args.limit, output / "input_clock.jsonl")
            frames = iter(source)
        else:
            frames = ((pair, None, None) for pair in itertools.islice(euroc(args.dataset), args.limit))
        for pair, arrival, payload in frames:
            if arrival is not None:
                events.emit("consume", timestamp=pair.timestamp, arrival_ns=arrival,
                            consume_ns=time.monotonic_ns())
            if origin is None:
                origin = pair.timestamp
            total += 1
            seconds = (pair.timestamp - origin) / 1e9
            obscured = any(start <= seconds < end for start, end in args.occlude)
            view = "occluded" if obscured else "raw"
            images = read_pair(pair, view, payload)
            if native:
                result = active.consume(pair, view, images)
                publish(result, "native", result["maps"] == 1 and result["map_id"] == 0)
                events.emit("frame", timestamp=pair.timestamp, imu_count=len(pair.imu),
                            tracking=result["tracking"], map_id=result["map_id"])
                continue

            support = input_support(images)
            weak = min(support) < 12
            events.emit("frame", timestamp=pair.timestamp, imu_count=len(pair.imu),
                        left_features=support[0], right_features=support[1],
                        tracking=active.snapshot["tracking"] if active.snapshot else None,
                        prior_imu_rotation_error_rad=imu_delta)
            if private is not None:
                pending.append((pair, view, weak))
                if weak:
                    private.consume(pair, "skip")
                    probation.clear()
                else:
                    candidate_fitted = True
                    try:
                        fitted = private.consume(pair, "fit")
                    except WORKER_FAILURE as error:
                        reject(f"candidate_worker: {error}")
                        continue
                    proof = vision.validate(read_pair(anchor_pair, "raw"), images, anchor, fitted)
                    eligible = (healthy(fitted) and fitted["map_id"] == anchor["map_id"]
                                and fitted["maps"] == anchor["maps"] and proof["passed"])
                    events.emit("candidate", event=event_id, timestamp=pair.timestamp,
                                snapshot=fitted, gate=proof, eligible=eligible)
                    if eligible:
                        probation.append(fitted)
                    else:
                        probation.clear()
                    if len(probation) == 3:
                        retired, active = active, private
                        private = None
                        inertial, closure = recover_history(history_anchor, anchor_pair, pending,
                                                            probation[0], vision)
                        events.emit("blind_history", event=event_id, **closure)
                        events.emit("promote", event=event_id, checkpoint=anchor["timestamp"],
                                    through=pair.timestamp, decided_ns=time.monotonic_ns(),
                                    coordinate_verified=aligned,
                                    accepted_blind_history=[row["timestamp"] for row in inertial],
                                    accepted_history=[row["timestamp"] for row in probation])
                        for row in inertial:
                            publish(row, "inertial_history" if aligned else "local_inertial_history",
                                    aligned)
                        for row in probation:
                            publish(row, "repaired_history" if aligned else "local_repaired_history",
                                    aligned)
                        catch_up_standby(retired)
                        previous = active.snapshot
                        imu_delta = None
                        anchor_pair = pair
                        probation.clear()
                        pending.clear()
                        events.emit("rearmed", event=event_id, coordinate_verified=aligned)
                if private is not None and pair.timestamp - pending[0][0].timestamp >= 1_500_000_000:
                    reject("bounded_candidate_window")
                continue

            if needs_rearm and weak:
                consume_public(pair, "skip")
                observe_reentry(None)
                events.emit("reentry_wait", event=event_id, timestamp=pair.timestamp)
                continue

            armed = (not needs_rearm and active.snapshot is not None and healthy(active.snapshot)
                     and (imu_delta is None or imu_delta <= 0.20))
            if weak and (pending or armed):
                pending.append((pair, view, weak))
                if len(pending) == 2:
                    event_id += 1
                    candidate_fitted = False
                    anchor = active.snapshot
                    events.emit("isolate", event=event_id, fault="image_observation",
                                first_untrusted=pending[0][0].timestamp, detected=pair.timestamp,
                                checkpoint=anchor, detected_ns=time.monotonic_ns())
                    if args.mode == "qualify":
                        reject("clean_replay_mode")
                        continue
                    if standby is None:
                        reject("incremental_checkpoint_unavailable")
                        continue
                    started = time.monotonic_ns()
                    try:
                        mirrored_pending = queued.at_boundary()
                    except WORKER_FAILURE as error:
                        events.emit("standby_unavailable", event=event_id, reason=str(error))
                        retire_busy_standby()
                        reject("incremental_checkpoint_not_ready")
                        continue
                    if not probe_standby():
                        reject("standby_requalification_pending")
                        continue
                    private, standby = standby, None
                    if not qualify_replay(active, private, events, "incremental_checkpoint",
                                          event=event_id, prefix_frames_replayed=0):
                        reject("incremental_checkpoint_difference")
                        continue
                    events.emit("checkpoint_ready", event=event_id, frames_replayed=0,
                                mirrored_pending_at_isolation=mirrored_pending,
                                through=private.snapshot["timestamp"], started_ns=started,
                                finished_ns=time.monotonic_ns())
                    history_anchor = private.snapshot
                    for deferred, _, _ in pending:
                        private.consume(deferred, "skip")
                continue

            if pending:  # A single weak frame did not confirm an occlusion.
                deferred, deferred_view, _ = pending.pop()
                previous = consume_public(deferred, deferred_view)
                publish(previous, "native" if aligned else "local_unverified", aligned)

            result = consume_public(pair, view, images)
            imu_delta = vision.imu_residual(previous, result)
            if previous is not None and (previous["map_id"] != result["map_id"]
                                         or previous["maps"] != result["maps"]):
                aligned = False
            publish(result, "native" if aligned else "local_unverified", aligned)
            previous = result
            anchor_pair = pair
            observe_reentry(result)
            if (standby_probe is not None and standby is not None and healthy(result)
                    and len(active.recent) == active.recent.maxlen
                    and active.recent[0]["timestamp"] > standby_probe[1]):
                try:
                    if queued.idle():
                        probe_standby()
                except WORKER_FAILURE as error:
                    events.emit("standby_unavailable", reason=str(error), timestamp=pair.timestamp)
                    retire_busy_standby()

            if checkpoint_probe is not None:
                copied = checkpoint_probe.consume(pair, view, images)
                events.emit("clean_suffix_replay", **replay_delta(result, copied))
                probe_remaining -= 1
                if not probe_remaining:
                    close(checkpoint_probe, "clean-replay")
                    checkpoint_probe = None
            if args.mode == "qualify" and primary is None and seconds >= args.qualify_at and healthy(result):
                primary = result
                checkpoint_probe = replay(active, "clean-replay")
                qualify_replay(active, checkpoint_probe, events, "clean_checkpoint_replay",
                               timestamp=result["timestamp"])
                probe_remaining = 10

        if private is not None:
            reject("end_of_input")
        elif pending:
            deferred, view, _ = pending.pop()
            publish(consume_public(deferred, view), "native", aligned)
        if not total:
            raise ValueError("no stereo frames")
        events.emit("complete", input_pairs=total, events=event_id,
                    clean_replay_attempted=primary is not None)
    except InputFault as error:
        events.emit("input_fault", kind=error.kind, detail=str(error))
        raise
    finally:
        if source is not None:
            source.close()
        if publisher is not None:
            publisher.close()
        if parallel is not None:
            parallel.shutdown()
        if args.share_orb_features:
            events.emit("orb_feature_exchange", workers=[worker.feature_stats for worker in feature_workers])
        for name, receipt in retired_workers:
            events.emit("worker_exit", name=name, exit=receipt.result())
        for worker in workers:
            events.emit("worker_exit", exit=worker.close())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("dataset", "worker", "vocabulary", "settings", "output"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--mode", choices=("native", "recover", "qualify"), required=True)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--realtime", action="store_true")
    parser.add_argument("--share-orb-features", action="store_true")
    parser.add_argument("--subscriber", type=Path)
    parser.add_argument("--delay", type=float, default=0.012, help="extra frame pacing in seconds")
    parser.add_argument("--qualify-at", type=float, default=25.0)
    parser.add_argument("--occlude", nargs=2, type=float, action="append", default=[],
                        metavar=("START_S", "END_S"))
    args = parser.parse_args()
    if (any(not 0 <= start < end for start, end in args.occlude)
            or args.delay < 0 or args.limit is not None and args.limit <= 0):
        parser.error("invalid frame limit, cadence or fault interval")
    if args.realtime:
        if args.mode == "qualify":
            parser.error("checkpoint qualification uses offline replay")
        args.delay = 0
    cv2.setNumThreads(1)
    cv2.setRNGSeed(73)
    args.output.mkdir()
    with (args.output / "events.jsonl").open("x") as stream:
        events = EventLog(stream)
        events.emit("run", mode=args.mode, dataset=str(args.dataset.resolve()),
                    fault_intervals_s=args.occlude, delay_s=args.delay,
                    drain_local_mapping="ORB_VIO_DRAIN_LOCAL_MAPPING" in os.environ,
                    realtime=args.realtime,
                    external_subscriber=args.subscriber is not None,
                    shared_orb_features=args.share_orb_features)
        run(args, events, args.output)


if __name__ == "__main__":
    main()
