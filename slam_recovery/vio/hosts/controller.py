"""Shared live stereo recovery transaction for the VINS-Fusion and OKVIS2 adapters."""

import argparse
from bisect import bisect_right
from concurrent.futures import ThreadPoolExecutor
import csv
import os
from pathlib import Path
import time

import cv2
import numpy as np

from ..blind_history import recover_history
from ..live import LiveInput, PosePublisher
from ..standby import StandbyQueue, StandbyTimeout
from ..stream import EventLog, read_pair
from ..vision import HeldOutStereo, angle, gauge_from, in_public_world, relative
from ..visual_faults import StereoEvidence, region_mask
from .bridge import NativeLane
from .prepared_input import PreparedInput


def qualified_boundary(primary, spare, *, apply_gauge=True):
    """Fit one transform and verify held-out pre-fault poses, speed and biases."""
    if len(primary.recent) < 12 or len(primary.recent) != len(spare.recent):
        return False, None
    before, after = list(primary.recent), list(spare.recent)
    if any(a["timestamp"] != b["timestamp"] for a, b in zip(before, after)):
        return False, None
    gauge = gauge_from(before[0], after[0])
    maxima = np.zeros(5)
    for a, b in zip(before[1:], after[1:]):
        b = in_public_world(b, gauge)
        rot, shift = relative(a, b)
        vel, ba, bg = np.split(np.asarray(a["inertial"]) - b["inertial"], 3)
        maxima = np.maximum(maxima, (np.linalg.norm(shift), angle(rot),
                                    np.linalg.norm(vel), np.linalg.norm(ba), np.linalg.norm(bg)))
    if not np.all(maxima <= [0.05, 0.05, 0.15, 0.15, 0.025]):
        return False, maxima.tolist()
    if apply_gauge:
        spare.gauge = gauge if spare.gauge is None else (
            spare.gauge[0] @ gauge[0], spare.gauge[1] + spare.gauge[0] @ gauge[1])
        spare.recent.clear()
        spare.recent.extend(in_public_world(row, gauge) for row in after)
    return True, maxima.tolist()


class Recovery:
    def __init__(self, active, spare, calibration, events, publisher, *, serial=False, backlog=12):
        self.active = active
        self.spare = spare
        self.enabled = spare is not None
        self.executor = ThreadPoolExecutor(max_workers=1) if self.enabled and not serial else None
        self.mirror = StandbyQueue(self.executor, capacity=backlog, wait_s=0) if self.executor else None
        self.spare_lagged = False
        self.spare_settled_at = None
        self.public_requests = {}
        self.last_forwarded = None
        self.vision = calibration
        self.spatial = StereoEvidence(calibration)
        self.events = events
        self.publisher = publisher
        self.verified = True
        self.anchor = None
        self.pending = []
        self.probation = []
        self.plan = None
        self.event = 0
        self.isolated = False
        self.awaiting_boundary = False

    def deliver(self, row, channel):
        if row is None:
            return
        payload = dict(row, type="pose", channel=channel, coordinate_verified=self.verified)
        payload["delivery_id"] = self.publisher.send(payload)
        del payload["type"]
        self.events.emit("pose", **payload)

    def native_timing(self, lane, pair, images, role):
        if lane.timing is not None:
            self.events.emit("native_stage", role=role, pid=lane.process.pid,
                             timestamp=pair.timestamp, visual=images is not None, **lane.timing)

    def native_step(self, lane, pair, images, imu, role):
        pose = lane.step(pair, images, imu)
        self.native_timing(lane, pair, images, role)
        return pose

    def submit_native(self, lane, pair, images, imu, role):
        if getattr(lane, "pipelined", False):
            poses = lane.submit(pair, images, imu)
            self.native_timing(lane, pair, images, role)
            return poses
        pose = self.native_step(lane, pair, images, imu, role)
        return [pose] if pose is not None else []

    def mark_spare_lag(self, stamp, reason):
        if not self.spare_lagged:
            self.events.emit("standby_ineligible", timestamp=stamp, reason=reason,
                             queued_jobs=len(self.mirror.pending))
        self.spare_lagged = True

    def observe_spare(self, stamp):
        if self.spare is None or not self.spare_lagged:
            return
        try:
            idle = self.mirror.idle()
        except (RuntimeError, OSError, TimeoutError) as error:
            self.unavailable(error, stamp)
            return
        if idle:
            qualified, errors = qualified_boundary(self.active, self.spare, apply_gauge=False)
            if qualified:
                self.spare_lagged = False
                self.events.emit("standby_requalified", timestamp=stamp,
                                 through=self.spare.recent[-1]["timestamp"],
                                 maximum_state_differences=errors)

    def unavailable(self, reason, stamp):
        self.events.emit("standby_unavailable", timestamp=stamp, reason=str(reason))
        self.spare = None
        if self.mirror is not None:
            # Running work can finish on its original lane. Discard the pending
            # suffix because this replica can no longer prove continuous input.
            self.mirror.retire(lambda: None)

    def submit_spare(self, stamp, callback, *args):
        try:
            self.mirror.offer(callback, *args)
            if len(self.mirror.pending) > 2:
                self.mark_spare_lag(stamp, "pending_original_inputs")
        except (RuntimeError, OSError, TimeoutError) as error:
            self.unavailable(error, stamp)

    def qualify_spare(self, stamp, wait=.05):
        if self.spare is None:
            return False, None, "standby_unavailable"
        if self.mirror is not None:
            try:
                deadline = time.monotonic() + wait
                self.mirror.at_boundary(wait)
                if (getattr(self.spare, "pipelined", False)
                        and self.spare_settled_at != self.last_forwarded):
                    self.mirror.offer(self.spare.settle)
                    self.spare_settled_at = self.last_forwarded
                    self.mirror.at_boundary(max(0, deadline - time.monotonic()))
            except StandbyTimeout:
                # Preserve the original FIFO so a short lag can be caught up.
                self.mark_spare_lag(stamp, "boundary_late")
                return False, None, "standby_boundary_late"
            except (RuntimeError, OSError, TimeoutError) as error:
                self.unavailable(error, stamp)
                return False, None, "standby_unavailable"
        elif getattr(self.spare, "pipelined", False):
            self.spare.settle()
        if (self.last_forwarded is not None
                and (not self.active.recent or
                     self.active.recent[-1]["timestamp"] != self.last_forwarded)):
            return False, None, "foreground_boundary_missing"
        qualified, errors = qualified_boundary(self.active, self.spare)
        if qualified and self.spare_lagged:
            self.spare_lagged = False
            self.events.emit("standby_requalified", timestamp=stamp,
                             through=self.active.recent[-1]["timestamp"],
                             maximum_state_differences=errors)
        return qualified, errors, "incremental_checkpoint_difference"

    def close(self):
        if self.executor is not None:
            self.executor.shutdown()

    def deliver_callbacks(self, poses, channel):
        for pose in poses:
            stamp = pose["timestamp"]
            self.anchor = self.public_requests.pop(stamp)
            self.deliver(pose, channel)

    def settle_public(self, channel):
        if getattr(self.active, "pipelined", False):
            self.deliver_callbacks(self.active.settle(), channel)
            self.public_requests.clear()
            if self.anchor is not None and self.anchor.timestamp != self.last_forwarded:
                self.anchor = None

    def forward(self, pair, images, imu, channel):
        if self.verified and self.spare is not None and self.mirror is not None:
            self.observe_spare(pair.timestamp)
            if self.spare is not None:
                self.submit_spare(pair.timestamp, self.submit_native, self.spare,
                                  pair, images, imu, "spare")
        self.last_forwarded = pair.timestamp
        poses = self.submit_native(self.active, pair, images, imu, "public")
        if self.verified and self.spare is not None and self.mirror is None:
            self.submit_native(self.spare, pair, images, imu, "spare")
        if getattr(self.active, "pipelined", False):
            self.public_requests[pair.timestamp] = pair
            self.deliver_callbacks(poses, channel)
            if len(self.public_requests) > 3:
                del self.public_requests[next(iter(self.public_requests))]
        else:
            self.anchor = pair if poses else None
            for pose in poses:
                self.deliver(pose, channel)

    def finish_event(self):
        self.pending.clear()
        self.probation.clear()
        self.isolated = False
        self.awaiting_boundary = False
        self.plan = None

    def reject(self, reason):
        self.events.emit("reject", event=self.event, reason=reason, decided_ns=time.monotonic_ns(),
                         preserved_anchor=self.anchor.timestamp)
        self.verified = False
        for pair, images, imu, weak in self.pending:
            view = None if weak else images
            self.native_step(self.active, pair, view, imu, "refusal")
        # The private hypothesis may diverge from the public worker on refusal.
        # Keep the retained worker. Local tracking can still produce outputs.
        self.finish_event()

    def promote(self, pair):
        anchor = self.active.recent[-1]
        buffered = [(p, "raw", weak) for p, _, _, weak in self.pending]
        history, receipt = recover_history(
            anchor, self.anchor, buffered, self.probation[0], self.vision)
        self.events.emit("blind_history", event=self.event, **receipt)
        self.active, self.spare = self.spare, self.active
        self.spare_settled_at = None
        self.events.emit("promote", event=self.event, checkpoint=self.anchor.timestamp,
                         through=pair.timestamp, decided_ns=time.monotonic_ns(),
                         coordinate_verified=self.verified,
                         accepted_blind_history=[r["timestamp"] for r in history],
                         accepted_history=[r["timestamp"] for r in self.probation])
        for row in history:
            self.deliver(row, "inertial_history")
        for row in self.probation:
            self.deliver(row, "repaired_history")
        batch = tuple(self.pending)
        plan, lane, event = self.plan, self.spare, self.event

        def catch_up():
            started = time.monotonic_ns()
            for former, images, imu, weak in batch:
                self.submit_native(lane, former, None if weak else plan.mask(images), imu, "catchup")
            if getattr(lane, "pipelined", False):
                lane.settle()
            self.events.emit("standby_catchup", event=event, frames=len(batch),
                             through=pair.timestamp, started_ns=started, finished_ns=time.monotonic_ns())

        if self.mirror is None:
            catch_up()
        else:
            self.submit_spare(pair.timestamp, catch_up)
            self.mark_spare_lag(pair.timestamp, "replay_after_handoff")
        self.public_requests.clear()
        self.last_forwarded = pair.timestamp
        self.anchor = pair
        self.finish_event()
        self.events.emit("rearmed", event=self.event, coordinate_verified=True)

    def candidate(self, pair, images, imu, weak):
        if weak:
            self.native_step(self.spare, pair, None, imu, "candidate")
            self.probation.clear()
        else:
            anchor_images = read_pair(self.anchor, "raw")
            if self.plan is None:
                self.plan, counts = self.spatial.reserve(anchor_images, images)
                self.events.emit("validation_partition", event=self.event, timestamp=pair.timestamp,
                                 held=self.plan.held, raw_support_by_tile=counts)
            pose = self.native_step(self.spare, pair, self.plan.mask(images), imu, "candidate")
            support = region_mask(images[0].shape, self.plan.held)
            mask = region_mask(images[0].shape, self.plan.held, margin=18)
            proof = (self.vision.validate(anchor_images, images, self.active.recent[-1], pose,
                                          mask, support=support, adaptive=True)
                     if pose is not None else {"passed": False, "reason": "native_pose_unavailable"})
            self.events.emit("candidate", event=self.event, timestamp=pair.timestamp,
                             eligible=proof["passed"], gate=proof)
            if proof["passed"]:
                self.probation.append(pose)
                if len(self.probation) == 3:
                    self.promote(pair)
                    return
            else:
                self.probation.clear()

    def process_candidate_frame(self, pair, images, imu, weak):
        self.pending.append((pair, images, imu, weak))
        self.candidate(pair, images, imu, weak)
        if self.isolated and pair.timestamp - self.pending[0][0].timestamp >= 1_500_000_000:
            self.reject("bounded_candidate_window")

    def try_fault_boundary(self, stamp, *, first):
        if stamp - self.pending[0][0].timestamp >= 1_500_000_000:
            self.reject("standby_boundary_late")
            return
        qualified, errors, reason = self.qualify_spare(stamp, wait=.05 if first else 0)
        if reason == "standby_boundary_late":
            if first:
                self.events.emit("standby_boundary_wait", event=self.event, timestamp=stamp,
                                 checkpoint=self.last_forwarded)
            return
        self.events.emit("incremental_checkpoint", event=self.event, qualified=qualified,
                         maximum_state_differences=errors, prefix_frames_replayed=0,
                         checked_at=stamp)
        if not qualified:
            self.reject(reason)
            return

        self.awaiting_boundary = False
        buffered, self.pending = self.pending, []
        for frame in buffered:
            if self.isolated:
                self.process_candidate_frame(*frame)
            else:
                self.step(*frame)

    def step(self, pair, images, imu, weak):
        if not self.enabled:
            self.forward(pair, images, imu, "native")
            return
        if not self.verified:
            self.forward(pair, None if weak else images, imu, "local_unverified")
            return
        if weak and not self.pending and not self.isolated:
            self.settle_public("native")
        if self.isolated:
            if self.awaiting_boundary:
                self.pending.append((pair, images, imu, weak))
                self.try_fault_boundary(pair.timestamp, first=False)
            else:
                self.process_candidate_frame(pair, images, imu, weak)
        elif weak and (self.pending or self.anchor is not None and len(self.active.recent) >= 12):
            self.pending.append((pair, images, imu, weak))
            if len(self.pending) == 2:
                self.event += 1
                self.events.emit("isolate", event=self.event, fault="image_observation",
                                 first_untrusted=self.pending[0][0].timestamp, detected=pair.timestamp,
                                 checkpoint=self.active.recent[-1], detected_ns=time.monotonic_ns())
                self.isolated = self.awaiting_boundary = True
                self.try_fault_boundary(pair.timestamp, first=True)
        else:
            for deferred, view, samples, _ in self.pending:
                self.forward(deferred, view, samples, "native")
            self.pending.clear()
            self.forward(pair, images, imu, "native")

    def finish(self):
        if self.isolated:
            self.reject("end_of_input")
        else:
            for pair, images, imu, _ in self.pending:
                self.forward(pair, images, imu, "native")
        self.settle_public("native" if self.verified else "local_unverified")


def read_imu(path):
    with path.open() as stream:
        for row in csv.reader(line for line in stream if not line.startswith("#")):
            gx, gy, gz, x, y, z = map(float, row[1:])
            yield int(row[0]), x, y, z, gx, gy, gz


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("dataset", "worker", "config", "resources", "calibration", "output", "subscriber"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--mode", choices=("native", "detect", "recover"), required=True)
    parser.add_argument("--occlude", nargs=2, type=float, action="append", default=[])
    parser.add_argument("--limit", type=int, default=950)
    parser.add_argument("--serial-standby", action="store_true",
                        help="reproduce the previous synchronous schedule for comparison")
    parser.add_argument("--primary-cpus", default="", help="comma-separated CPU IDs")
    parser.add_argument("--standby-cpus", default="", help="disjoint CPU IDs of equal count")
    parser.add_argument("--standby-backlog", type=int, default=12, choices=range(3, 33),
                        metavar="3..32")
    parser.add_argument("--blocking-callback", action="store_true",
                        help="wait for each OKVIS2 optimisation for the paired control")
    args = parser.parse_args()
    try:
        primary = set(map(int, args.primary_cpus.split(","))) if args.primary_cpus else set()
        standby = set(map(int, args.standby_cpus.split(","))) if args.standby_cpus else set()
    except ValueError:
        parser.error("CPU budgets must be comma-separated CPU IDs")
    if not (primary | standby) <= os.sched_getaffinity(0):
        parser.error("CPU budget must be inside the process affinity")
    if args.mode == "recover" and (primary & standby or len(primary) != len(standby)):
        parser.error("recovery CPU budgets must be disjoint and equally sized")
    args.output.mkdir()
    cv2.setNumThreads(1)
    cv2.setRNGSeed(73)
    calibration = HeldOutStereo(args.calibration)
    publisher = PosePublisher(args.subscriber)
    lanes = []
    source = recovery = prepared = None
    imu = list(read_imu(args.dataset / "mav0/imu0/data.csv"))
    stamps = [row[0] for row in imu]
    with (args.output / "events.jsonl").open("x") as stream:
        events = EventLog(stream)
        try:
            events.emit("run", mode=args.mode, dataset=str(args.dataset),
                        fault_intervals_s=args.occlude, realtime=True, imu_overlap_ms=25,
                        serial_standby=args.serial_standby, primary_cpus=sorted(primary),
                        standby_cpus=sorted(standby), standby_backlog=args.standby_backlog,
                        blocking_callback=args.blocking_callback)
            for name in ("primary", "spare") if args.mode == "recover" else ("primary",):
                config = (Path(os.environ["VIO_VINS_SPARE_CONFIG"])
                          if name == "spare" and "VIO_VINS_SPARE_CONFIG" in os.environ else args.config)
                cpus = args.standby_cpus if name == "spare" else args.primary_cpus
                lane = NativeLane(args.worker, config, args.resources, name, args.output, calibration,
                                  cpus=cpus, blocking_callback=args.blocking_callback)
                lanes.append(lane)
                events.emit("worker_started", name=name, pid=lane.process.pid, callback=lane.pipelined,
                            cpus=sorted(os.sched_getaffinity(lane.process.pid)))
            spare = lanes[1] if len(lanes) > 1 else None
            recovery = Recovery(lanes[0], spare, calibration, events, publisher,
                                serial=args.serial_standby, backlog=args.standby_backlog)
            source = LiveInput(args.dataset, args.limit, args.output / "input_clock.jsonl")
            prepared = PreparedInput(source, args.occlude, args.mode != "native")
            cursor = None
            for frame in prepared:
                pair = frame.pair
                if cursor is None:
                    cursor = bisect_right(stamps, pair.timestamp - 100_000_000)
                end = bisect_right(stamps, pair.timestamp + 25_000_000, lo=cursor)
                events.emit("consume", timestamp=pair.timestamp, arrival_ns=frame.arrival_ns,
                            consume_ns=time.monotonic_ns())
                events.emit("input_prepared", timestamp=pair.timestamp, ready_ns=frame.ready_ns,
                            decode_ns=frame.decode_ns, detector_ns=frame.detector_ns, weak=frame.weak)
                recovery.step(pair, frame.images, imu[cursor:end], frame.weak)
                cursor = end
            recovery.finish()
        finally:
            if prepared is not None:
                prepared.close()
            if source is not None:
                source.close()
            if recovery is not None:
                recovery.close()
            for lane in lanes:
                events.emit("worker_exit", name=lane.process.pid, exit=lane.close(),
                            callback_gaps=lane.callback_gaps, late_callbacks=lane.late_callbacks)
            publisher.close()


if __name__ == "__main__":
    main()
