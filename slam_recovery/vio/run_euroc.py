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

    def consume(self, pair, view, images=None):
        if self.journal is not None:
            self.journal.append((pair, view))
        self.pending_imu.extend(pair.imu)
        if view == "skip":
            return None
        snapshot = self.worker.track(
            pair, read_pair(pair, view) if images is None else images, self.pending_imu)
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
    command = args.worker, args.vocabulary, args.settings
    parallel = ThreadPoolExecutor(max_workers=1) if incremental else None
    queued = StandbyQueue(parallel) if incremental else None
    retired_workers = []

    def new_lane(name):
        worker = Worker(command, output / f"{name}.log", wait_ready=args.realtime)
        workers.append(worker)
        return Lane(worker, args.delay, keep_journal=args.mode == "qualify")

    def publish(result, channel, verified):
        if result is None or (channel != "inertial_history" and result["tracking"] != 2):
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

    def retire_busy_standby():
        nonlocal standby
        worker = standby.worker
        retired_workers.append(queued.retire(worker.close))
        workers.remove(worker)
        standby = None

    def consume_public(pair, view, images=None):
        if standby is not None:
            if images is None and view != "skip":
                images = read_pair(pair, view)
            try:
                if queued.offer(standby.consume, pair, view, images):
                    events.emit("standby_queue_pressure", timestamp=pair.timestamp)
            except WORKER_FAILURE as error:
                events.emit("standby_unavailable", reason=str(error), timestamp=pair.timestamp)
                retire_busy_standby()
        return active.consume(pair, view, images)

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
            close(retired, "standby_catchup_failed")
            return
        standby = retired
        events.emit("standby_catchup", event=event_id, frames=len(pending),
                    through=retired.snapshot["timestamp"], started_ns=started,
                    finished_ns=time.monotonic_ns())

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
        events.emit("reject", event=event_id, reason=reason, preserved_anchor=anchor["timestamp"],
                    decided_ns=time.monotonic_ns())
        if private is not None:
            if not candidate_fitted and reason in ("bounded_candidate_window", "end_of_input"):
                # No native visual update was attempted. Only the unsent IMU queue
                # changed; both replicas can resume from the original boundary.
                private.pending_imu.clear()
                standby = private
            else:
                close(private, f"candidate-{event_id}")
            private = None
        aligned = False
        needs_rearm, healthy_count = True, 0
        for pair, view, weak in pending:
            result = consume_public(pair, "skip" if weak else view)
            publish(result, "local_unverified", False)
            observe_reentry(result)
            if result is not None:
                anchor_pair = pair
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
                    eligible = (aligned and healthy(fitted) and fitted["map_id"] == anchor["map_id"]
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
                        aligned = True
                        inertial, closure = recover_history(history_anchor, anchor_pair, pending,
                                                            probation[0], vision)
                        events.emit("blind_history", event=event_id, **closure)
                        events.emit("promote", event=event_id, checkpoint=anchor["timestamp"],
                                    through=pair.timestamp, decided_ns=time.monotonic_ns(),
                                    accepted_blind_history=[row["timestamp"] for row in inertial],
                                    accepted_history=[row["timestamp"] for row in probation])
                        for row in inertial:
                            publish(row, "inertial_history", True)
                        for row in probation:
                            publish(row, "repaired_history", True)
                        catch_up_standby(retired)
                        previous = active.snapshot
                        imu_delta = None
                        anchor_pair = pair
                        probation.clear()
                        pending.clear()
                        events.emit("rearmed", event=event_id, coordinate_verified=True)
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
        for receipt in retired_workers:
            events.emit("worker_exit", name="retired_standby", exit=receipt.result())
        for worker in workers:
            events.emit("worker_exit", exit=worker.close())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("dataset", "worker", "vocabulary", "settings", "output"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--mode", choices=("native", "recover", "qualify"), required=True)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--realtime", action="store_true")
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
                    external_subscriber=args.subscriber is not None)
        run(args, events, args.output)


if __name__ == "__main__":
    main()
