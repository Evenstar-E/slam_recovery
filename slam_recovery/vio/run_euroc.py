"""Run the native baseline or the stereo-inertial recovery transaction."""
import argparse
from collections import deque
import itertools
import os
import time
from pathlib import Path

import cv2

from .stream import EventLog, InputFault, Worker, euroc, read_pair
from .vision import (HeldOutStereo, healthy, in_public_world, input_support,
                     qualify_replay, replay_delta)


class Lane:
    def __init__(self, worker, delay):
        self.worker = worker
        self.delay = delay
        self.journal = []
        self.pending_imu = []
        self.snapshot = None
        self.recent = deque(maxlen=16)
        self.gauge = None

    def consume(self, pair, view, images=None):
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
    frames = itertools.islice(euroc(args.dataset), args.limit)
    native = args.mode == "native"
    vision = HeldOutStereo(args.settings)
    workers = []
    command = args.worker, args.vocabulary, args.settings

    def new_lane(name):
        worker = Worker(command, output / f"{name}.log")
        workers.append(worker)
        return Lane(worker, args.delay)

    def publish(result, channel, verified):
        if result and result["tracking"] == 2:
            events.emit("pose", channel=channel, coordinate_verified=verified, **result)

    def replay(source, name):
        lane = new_lane(name)
        for pair, view in source.journal:
            lane.consume(pair, view)
        return lane

    def close(lane, name):
        if lane.worker in workers:
            events.emit("worker_exit", name=name, exit=lane.worker.close())
            workers.remove(lane.worker)

    active = new_lane("native")
    primary = None
    probation = []
    pending = []
    anchor_pair = None
    anchor = None
    private = None
    event_id = 0
    origin = None
    aligned = True
    previous = None
    checkpoint_probe = None
    probe_remaining = 0
    imu_delta = None
    total = 0

    def reject(reason):
        nonlocal private, aligned, previous, imu_delta, anchor_pair
        events.emit("reject", event=event_id, reason=reason, preserved_anchor=anchor["timestamp"])
        if private is not None:
            close(private, f"candidate-{event_id}")
            private = None
        aligned = False
        for pair, view, weak in pending:
            result = active.consume(pair, "skip" if weak else view)
            publish(result, "local_unverified", False)
            if result is not None:
                anchor_pair = pair
        previous = active.snapshot
        imu_delta = None
        pending.clear()
        probation.clear()
        events.emit("rearmed", event=event_id, coordinate_verified=False)

    try:
        for pair in frames:
            if origin is None:
                origin = pair.timestamp
            total += 1
            seconds = (pair.timestamp - origin) / 1e9
            obscured = any(start <= seconds < end for start, end in args.occlude)
            view = "occluded" if obscured else "raw"
            images = read_pair(pair, view)
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
                    try:
                        fitted = private.consume(pair, "fit")
                    except (RuntimeError, TimeoutError, BrokenPipeError) as error:
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
                        aligned = True
                        events.emit("promote", event=event_id, checkpoint=anchor["timestamp"],
                                    through=pair.timestamp,
                                    accepted_history=[row["timestamp"] for row in probation])
                        for row in probation:
                            publish(row, "repaired_history", True)
                        close(retired, f"retired-{event_id}")
                        previous = active.snapshot
                        imu_delta = None
                        anchor_pair = pair
                        probation.clear()
                        pending.clear()
                        events.emit("rearmed", event=event_id, coordinate_verified=True)
                if private is not None and pair.timestamp - pending[0][0].timestamp >= 1_500_000_000:
                    reject("bounded_candidate_window")
                continue

            armed = (active.snapshot is not None and healthy(active.snapshot)
                     and (imu_delta is None or imu_delta <= 0.20))
            if weak and (pending or armed):
                pending.append((pair, view, weak))
                if len(pending) == 2:
                    event_id += 1
                    anchor = active.snapshot
                    events.emit("isolate", event=event_id, fault="image_observation",
                                first_untrusted=pending[0][0].timestamp, detected=pair.timestamp,
                                checkpoint=anchor)
                    if args.mode == "qualify":
                        reject("clean_replay_mode")
                        continue
                    private = new_lane(f"candidate-{event_id}")
                    try:
                        for saved_pair, saved_view in active.journal:
                            private.consume(saved_pair, saved_view)
                    except (RuntimeError, TimeoutError, BrokenPipeError) as error:
                        reject(f"checkpoint_worker: {error}")
                        continue
                    if not qualify_replay(active, private, events, "checkpoint_replay", event=event_id):
                        reject("checkpoint_replay_difference")
                        continue
                    for deferred, _, _ in pending:
                        private.consume(deferred, "skip")
                continue

            if pending:  # A single weak frame did not confirm an occlusion.
                deferred, deferred_view, _ = pending.pop()
                previous = active.consume(deferred, deferred_view)
                publish(previous, "native" if aligned else "local_unverified", aligned)

            result = active.consume(pair, view, images)
            imu_delta = vision.imu_residual(previous, result)
            if previous is not None and (previous["map_id"] != result["map_id"]
                                         or previous["maps"] != result["maps"]):
                aligned = False
            publish(result, "native" if aligned else "local_unverified", aligned)
            previous = result
            anchor_pair = pair

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
            publish(active.consume(deferred, view), "native", aligned)
        if not total:
            raise ValueError("no stereo frames")
        events.emit("complete", input_pairs=total, events=event_id,
                    clean_replay_attempted=primary is not None)
    except InputFault as error:
        events.emit("input_fault", kind=error.kind, detail=str(error))
        raise
    finally:
        for worker in workers:
            events.emit("worker_exit", exit=worker.close())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("dataset", "worker", "vocabulary", "settings", "output"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--mode", choices=("native", "recover", "qualify"), required=True)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--delay", type=float, default=0.012, help="extra frame pacing in seconds")
    parser.add_argument("--qualify-at", type=float, default=25.0)
    parser.add_argument("--occlude", nargs=2, type=float, action="append", default=[],
                        metavar=("START_S", "END_S"))
    args = parser.parse_args()
    if (any(not 0 <= start < end for start, end in args.occlude)
            or args.delay < 0 or args.limit is not None and args.limit <= 0):
        parser.error("invalid frame limit, cadence or fault interval")
    cv2.setNumThreads(1)
    cv2.setRNGSeed(73)
    args.output.mkdir()
    with (args.output / "events.jsonl").open("x") as stream:
        events = EventLog(stream)
        events.emit("run", mode=args.mode, dataset=str(args.dataset.resolve()),
                    fault_intervals_s=args.occlude, delay_s=args.delay,
                    drain_local_mapping="ORB_VIO_DRAIN_LOCAL_MAPPING" in os.environ)
        run(args, events, args.output)


if __name__ == "__main__":
    main()
