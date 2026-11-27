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
from .checkpoint import CheckpointStore
from .live import LiveInput, PosePublisher
from .standby import StandbyQueue, StandbyRebuild
from .stream import EventLog, InputFault, SharedFeatures, Worker, euroc, read_pair
from .vision import (HeldOutStereo, healthy, in_public_world, input_support,
                     qualify_replay, replay_delta)


from .visual_faults import CELLS, RegionPlan, StereoEvidence, region_mask, textured_cover


WORKER_FAILURE = (RuntimeError, TimeoutError, BrokenPipeError)


class Lane:
    def __init__(self, worker, delay, keep_journal=False, reader=read_pair):
        self.worker = worker
        self.delay = delay
        self.read = reader
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
            pair, self.read(pair, view) if images is None else images, self.pending_imu, **options)
        if self.snapshot is not None and snapshot['map_id'] != self.snapshot['map_id']:
            self.gauge = None
        self.snapshot = in_public_world(snapshot, self.gauge)
        self.recent.append(self.snapshot)
        self.pending_imu.clear()
        if self.delay:
            time.sleep(self.delay)
        return self.snapshot

    def synchronize(self):
        prior = self.snapshot
        if prior is None:
            return None
        fresh = self.worker.synchronize(prior["timestamp"])
        if (fresh is None or fresh["map_id"] != prior["map_id"]
                or fresh["maps"] != prior["maps"]):
            return None
        self.snapshot = in_public_world(fresh, self.gauge)
        self.recent[-1] = self.snapshot
        return self.snapshot


def run(args, events, output):
    source = None
    publisher = None
    native = args.mode == "native"
    incremental = args.mode == "recover"
    replay_options = {"async_mapping": True} if args.async_recovery else {}
    vision = HeldOutStereo(args.settings)
    spatial = StereoEvidence(vision) if args.regional_visual or args.adaptive_gate else None
    region_reference = None
    regional_plan = None
    adaptive_plan = None
    accepted_region = None
    recovered_region = 0
    origin = None

    def load_view(pair, view, payload=None):
        if not args.regional_cover and isinstance(view, str):
            return read_pair(pair, view, payload)
        if view == "occluded":
            return read_pair(pair, view, payload)
        images = read_pair(pair, "raw", payload)
        seconds = (pair.timestamp - origin) / 1e9
        for start, end, selected in args.regional_cover:
            if start <= seconds < end:
                images = textured_cover(images, selected)
        if isinstance(view, RegionPlan):
            return view.mask(images)
        if view == "fit":
            for image in images:
                image[:image.shape[0] // 3] = 0
        return images
    workers = []
    feature_workers = []
    command = args.worker, args.vocabulary, args.settings
    parallel = ThreadPoolExecutor(max_workers=1) if incremental else None
    wait_seconds = 0 if args.primary_first else .35
    queued = StandbyQueue(parallel, wait_s=wait_seconds) if incremental else None
    retired_workers = []
    checkpoints = CheckpointStore(output / "checkpoints") if args.native_checkpoints else None
    rebuild = (StandbyRebuild(parallel, lambda: euroc(args.dataset),
                              limit=240 if checkpoints else 2000, rolling=checkpoints is not None,
                              replay_features=args.archive_orb_features, async_mapping=args.async_recovery)
               if args.rebuild_standby else None)
    next_checkpoint = 40
    checkpoint_io = ThreadPoolExecutor(max_workers=1) if checkpoints is not None else None
    pending_checkpoint = None
    rebuild_started = None
    rebuild_count = 0
    rebuild_attempted = False
    rebase_requested = False
    rebase_used = False
    missing_checkpoint = None
    shared_features = None
    suffix_features = checkpoints is not None and args.feature_transport == "shared"
    if args.feature_transport == "shared":
        slots = rebuild.limit + 16 if args.archive_orb_features or suffix_features else 16
        shared_features = SharedFeatures(slots)

    def new_lane(name, restore=None):
        worker = Worker(command, output / f"{name}.log", wait_ready=args.realtime,
                        feature_protocol=args.share_orb_features, shared_features=shared_features,
                        restore=restore, vocabulary_cache=args.checkpoint_vocabulary,
                        boundary_protocol=args.async_recovery)
        feature_workers.append(worker)
        workers.append(worker)
        events.emit("worker_started", name=name, pid=worker.process.pid)
        return Lane(worker, args.delay, keep_journal=args.mode == "qualify", reader=load_view)

    def timing(stage, timestamp, started):
        if args.profile_stages:
            events.emit("stage", stage=stage, timestamp=timestamp,
                        elapsed_ns=time.monotonic_ns() - started)

    def boundary_state(lane, phase):
        started = time.monotonic_ns()
        stamp = lane.snapshot["timestamp"] if lane.snapshot is not None else None
        state = lane.synchronize()
        events.emit("native_recovery_boundary", event=event_id, phase=phase, timestamp=stamp,
                    settled=state is not None, elapsed_ns=time.monotonic_ns() - started)
        return state

    def track_active(pair, view, images=None, **options):
        started = time.monotonic_ns()
        result = active.consume(pair, view, images, **options)
        timing("primary_tracking", pair.timestamp, started)
        return result

    def publish(result, channel, verified):
        if result is None or (channel not in ("inertial_history", "local_inertial_history")
                              and result["tracking"] != 2):
            return
        row = dict(result, type="pose", channel=channel, coordinate_verified=verified)
        if publisher is not None:
            started = time.monotonic_ns()
            row["delivery_id"] = publisher.send(row)
            timing("subscriber_ack", row["timestamp"], started)
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

    def retire_busy_standby(reason="worker_failure", timestamp=None):
        nonlocal standby, standby_probe
        events.emit("standby_qualification_lost", reason=reason, timestamp=timestamp,
                    pid=standby.worker.process.pid)
        retire_worker(standby, "retired_standby")
        standby = None
        standby_probe = None

    def restore_lane(name, checkpoint):
        if checkpoint is None:
            return new_lane(name)
        with checkpoints.restore(checkpoint) as prefix:
            lane = new_lane(name, restore=prefix)
        events.emit("native_checkpoint_loaded", count=checkpoint["count"],
                    timestamp=checkpoint["timestamp"], loaded_ns=time.monotonic_ns())
        return lane

    def commit_checkpoint(prepared, count, timestamp):
        try:
            generation = checkpoints.commit(prepared, count, timestamp)
        except OSError as error:
            events.emit("native_checkpoint_error", count=count, reason=str(error))
            return
        events.emit("native_checkpoint_saved", **{k: v for k, v in generation.items() if k != "blocks"},
                    donor="active")

    def capture_checkpoint(pair, result):
        nonlocal next_checkpoint, pending_checkpoint
        if (checkpoints is None or (standby is None and not args.primary_first) or not aligned or needs_rearm
                or standby_probe is not None or rebuild.count < next_checkpoint
                or not healthy(result) or len(active.recent) != active.recent.maxlen
                or not all(healthy(row) for row in active.recent)
                or (pending_checkpoint is not None and not pending_checkpoint.done())):
            return
        if pending_checkpoint is not None:
            pending_checkpoint.result()
        count = rebuild.count
        staged_ns = time.monotonic_ns()
        try:
            prepared = checkpoints.stage(active.worker)
        except (OSError, RuntimeError) as error:
            next_checkpoint = count + 4
            events.emit("native_checkpoint_error", count=count, reason=str(error))
            return
        finally:
            timing("snapshot_serialization", pair.timestamp, staged_ns)
        if prepared is None:
            next_checkpoint = count + 4
            events.emit("native_checkpoint_busy", count=count)
            return
        next_checkpoint = count + 40
        events.emit("native_checkpoint_staged", count=count, donor="active",
                    elapsed_s=(time.monotonic_ns() - staged_ns) / 1e9)
        pending_checkpoint = checkpoint_io.submit(commit_checkpoint, prepared, count, pair.timestamp)

    def service_rebuild(pair):
        nonlocal rebuild_started, rebuild_count, rebuild_attempted, standby, standby_probe
        nonlocal missing_checkpoint, rebase_requested, rebase_used
        if rebuild is None:
            return
        if standby is not None:
            exit_code = standby.worker.process.poll()
            if exit_code is None:
                return
            events.emit("standby_crashed", timestamp=pair.timestamp, exit=exit_code,
                        pid=standby.worker.process.pid)
            retire_busy_standby()
        if rebuild.pending is not None:
            checkpoint = checkpoints.latest if checkpoints is not None else None
            replay_tip = rebuild.base + rebuild.replayed_frames
            if (args.rebase_standby and not rebase_used and not rebase_requested
                    and checkpoint is not None and private is None and aligned
                    and checkpoint["count"] - replay_tip >= 20
                    and rebuild.count - checkpoint["count"] <= 24):
                rebase_requested = True
                rebase_used = True
                rebuild.cancelled = True
                events.emit("standby_rebase_requested", timestamp=pair.timestamp,
                            replay_tip=replay_tip, checkpoint_count=checkpoint["count"],
                            live_count=rebuild.count)
            if rebase_requested:
                if not rebuild.pending.done():
                    return
                try:
                    obsolete, _, _, _ = rebuild.pending.result()
                    retire_worker(obsolete, "standby_rebased")
                except WORKER_FAILURE + (OSError, ValueError, StopIteration) as error:
                    events.emit("standby_rebuild_failed", reason=str(error), timestamp=pair.timestamp)
                rebuild.pending = None
                rebuild.cancelled = False
                rebase_requested = False
                rebuild_attempted = False
                return
            try:
                completed = rebuild.at_tip(queued)
            except WORKER_FAILURE + (OSError, ValueError, StopIteration) as error:
                events.emit("standby_rebuild_failed", reason=str(error), timestamp=pair.timestamp)
                return
            if completed is None:
                return
            lane, complete, queued_tail = completed
            if not complete or active.snapshot is None:
                retire_worker(lane, "standby_rebuild_boundary_failed")
                events.emit("standby_rebuild_failed", reason="boundary", timestamp=pair.timestamp)
                return
            standby = lane
            standby_probe = event_id, active.snapshot["timestamp"]
            events.emit("standby_rebuilt", event=event_id, pid=lane.worker.process.pid,
                        through=active.snapshot["timestamp"],
                        replayed_frames=rebuild.replayed_frames, queued_tail=queued_tail,
                        checkpoint_count=rebuild.base,
                        finished_ns=time.monotonic_ns(), started_ns=rebuild_started)
        elif not rebuild_attempted and not rebuild.overflow:
            checkpoint = checkpoints.latest if checkpoints is not None else None
            if checkpoints is not None and (checkpoint is None
                    or not rebuild.floor <= checkpoint["count"] <= rebuild.count):
                missing = checkpoint["count"] if checkpoint else 0
                if missing_checkpoint != missing:
                    events.emit("native_checkpoint_unavailable", timestamp=pair.timestamp,
                                journal_floor=rebuild.floor, count=rebuild.count)
                missing_checkpoint = missing
                if not args.primary_first:
                    rebuild_attempted = True
                return
            rebuild_attempted = True
            rebuild_count += 1
            rebuild_started = time.monotonic_ns()
            base = checkpoint["count"] if checkpoint else 0
            events.emit("standby_rebuild_started", event=event_id, timestamp=pair.timestamp,
                        frames=rebuild.count - base, checkpoint_count=base,
                        started_ns=rebuild_started)
            name = f"standby-rebuilt-{rebuild_count}"
            rebuild.start(lambda: restore_lane(name, checkpoint), checkpoint)

    def consume_public(pair, view, images=None):
        service_rebuild(pair)
        if standby is None:
            capture = (args.archive_orb_features or suffix_features) and view == "raw"
            result = track_active(pair, view, images, capture=capture)
            if rebuild is not None:
                rebuild.record(view, pair.timestamp, active.worker.last_features if capture and suffix_features else b"")
            return result
        if images is None and view != "skip":
            images = load_view(pair, view)
        shared = args.share_orb_features and view == "raw"
        if shared:
            result = track_active(pair, view, images, capture=True)
        standby_lane = standby
        features = active.worker.last_features if shared else b""

        def feed():
            standby_lane.consume(pair, view, images, features=features)

        queued_ns = time.monotonic_ns()
        try:
            if queued.offer(feed):
                events.emit("standby_queue_pressure", timestamp=pair.timestamp)
        except WORKER_FAILURE as error:
            events.emit("standby_unavailable", reason=str(error), timestamp=pair.timestamp)
            retire_busy_standby(type(error).__name__, pair.timestamp)
        finally:
            timing("standby_enqueue_wait", pair.timestamp, queued_ns)
        if not shared:
            result = track_active(pair, view, images)
        if rebuild is not None:
            rebuild.record(view, pair.timestamp, features if suffix_features else b"")
        return result

    def catch_up_standby(retired):
        nonlocal standby, standby_probe
        if not incremental:
            return
        frames = list(pending)
        started = time.monotonic_ns()
        def catch_up():
            for buffered, applied, weak in frames:
                fitted_view = applied if isinstance(applied, RegionPlan) else "fit"
                retired.consume(buffered, "skip" if weak else fitted_view, **replay_options)
            events.emit("standby_catchup", event=catchup_event, frames=len(frames),
                        through=retired.snapshot["timestamp"], started_ns=started,
                        finished_ns=time.monotonic_ns())

        catchup_event = event_id
        try:
            if args.primary_first or args.async_recovery:
                standby_probe = event_id, active.snapshot["timestamp"]
                queued.offer(catch_up)
            else:
                catch_up()
        except WORKER_FAILURE as error:
            events.emit("standby_unavailable", reason=str(error), event=event_id)
            retire_worker(retired, "standby_catchup_failed")
            standby_probe = None
            return
        standby = retired

    def probe_standby():
        nonlocal standby_probe, rebuild_attempted, rebase_used
        if standby_probe is None:
            return True
        rejected_event, after = standby_probe
        # The entire comparison window must be fresh raw input after rejection.
        if len(active.recent) < active.recent.maxlen or active.recent[0]["timestamp"] <= after:
            return False
        if not all(healthy(row) for row in active.recent):
            return False
        if (standby.snapshot is None or standby.snapshot["timestamp"] != active.snapshot["timestamp"]
                or standby.pending_imu != active.pending_imu):
            return False
        if not qualify_replay(active, standby, events, "standby_requalification",
                              event=rejected_event, after=after):
            return False
        events.emit("standby_restored", event=rejected_event,
                    before_candidate_event=event_id if event_id != rejected_event else None,
                    through=standby.snapshot["timestamp"],
                    coordinate_verified=aligned)
        standby_probe = None
        rebuild_attempted = False
        rebase_used = False
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
        nonlocal standby_probe, accepted_region, regional_plan, adaptive_plan
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
        if regional_plan is not None:
            accepted_region = regional_plan
            regional_plan = None
        adaptive_plan = None
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
                consumed_ns = time.monotonic_ns()
                events.emit("consume", timestamp=pair.timestamp, arrival_ns=arrival, consume_ns=consumed_ns)
                if args.profile_stages:
                    events.emit("stage", stage="input_queue", timestamp=pair.timestamp,
                                elapsed_ns=consumed_ns - arrival)
            if origin is None:
                origin = pair.timestamp
            total += 1
            seconds = (pair.timestamp - origin) / 1e9
            obscured = any(start <= seconds < end for start, end in args.occlude)
            view = "occluded" if obscured else "raw"
            started = time.monotonic_ns()
            images = load_view(pair, view, payload)
            timing("image_decode", pair.timestamp, started)
            if native:
                result = track_active(pair, view, images)
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
            prepared = None
            if args.regional_visual and not weak and private is None:
                started = time.monotonic_ns()
                prepared = spatial.prepare(images)
                timing("regional_stereo_features", pair.timestamp, started)
            proposal = None
            if prepared is not None and region_reference is not None and private is None:
                started = time.monotonic_ns()
                proposal, report = spatial.diagnose(region_reference, prepared)
                timing("regional_motion", pair.timestamp, started)
                if accepted_region is not None:
                    cells = list(accepted_region.bad)
                    recovered = report is not None and all(
                        report["inliers_by_cell"][cell] >= 3 and report["after_stereo"][cell] >= 4
                        for cell in cells)
                    recovered_region = recovered_region + 1 if recovered else 0
                    if recovered_region >= 2:
                        accepted_region = None
                    proposal = None
                if proposal is not None:
                    events.emit("regional_suspect", timestamp=pair.timestamp, excluded=proposal.bad,
                                heldout=proposal.held, stereo_before=report["before_stereo"].tolist(),
                                stereo_after=report["after_stereo"].tolist(),
                                temporal_inliers=report["inliers_by_cell"].tolist())
            if private is not None:
                pending.append((pair, regional_plan if regional_plan is not None else view, weak))
                if weak:
                    private.consume(pair, "skip")
                    probation.clear()
                else:
                    anchor_images = load_view(anchor_pair, "raw")
                    if args.adaptive_gate and regional_plan is None and adaptive_plan is None:
                        adaptive_plan, support_by_tile = spatial.reserve(anchor_images, images)
                        events.emit("validation_partition", event=event_id, timestamp=pair.timestamp,
                                    held=adaptive_plan.held, raw_support_by_tile=support_by_tile)
                    validation_plan = regional_plan or adaptive_plan
                    candidate_fitted = True
                    try:
                        fitted = private.consume(pair, validation_plan or "fit", **replay_options)
                    except WORKER_FAILURE as error:
                        reject(f"candidate_worker: {error}")
                        continue
                    mask = (region_mask(images[0].shape, validation_plan.held, margin=18)
                            if validation_plan is not None else None)
                    support = (region_mask(images[0].shape, validation_plan.held)
                               if validation_plan is not None else None)
                    proof = vision.validate(anchor_images, images, anchor, fitted, mask,
                                            support=support, adaptive=args.adaptive_gate)
                    eligible = (healthy(fitted) and fitted["map_id"] == anchor["map_id"]
                                and fitted["maps"] == anchor["maps"] and proof["passed"])
                    events.emit("candidate", event=event_id, timestamp=pair.timestamp,
                                snapshot=fitted, gate=proof, eligible=eligible)
                    if eligible:
                        probation.append(fitted)
                    else:
                        probation.clear()
                    if len(probation) == 3:
                        if args.async_recovery:
                            try:
                                settled = boundary_state(private, "promotion")
                            except WORKER_FAILURE as error:
                                reject(f"candidate_boundary_worker: {error}")
                                continue
                            if settled is None:
                                reject("candidate_boundary_not_settled")
                                continue
                            continuity = replay_delta(fitted, settled)
                            final_proof = vision.validate(anchor_images, images, anchor, settled,
                                                          mask, support=support,
                                                          adaptive=args.adaptive_gate)
                            ready = continuity["qualified"] and final_proof["passed"]
                            events.emit("candidate_boundary_gate", event=event_id, timestamp=pair.timestamp,
                                        qualified=ready, state_delta=continuity, gate=final_proof)
                            if not ready:
                                reject("candidate_boundary_difference")
                                continue
                            probation[-1] = settled
                        retired, active = active, private
                        private = None
                        inertial, closure = recover_history(history_anchor, anchor_pair, pending,
                                                            probation[0], vision)
                        events.emit("blind_history", event=event_id, **closure)
                        events.emit("promote", event=event_id, checkpoint=anchor["timestamp"],
                                    through=pair.timestamp, decided_ns=time.monotonic_ns(),
                                    repaired_fault="regional_visual" if regional_plan else "image_observation",
                                    coordinate_verified=aligned,
                                    accepted_blind_history=[row["timestamp"] for row in inertial],
                                    accepted_history=[row["timestamp"] for row in probation])
                        for row in inertial:
                            publish(row, "inertial_history" if aligned else "local_inertial_history",
                                    aligned)
                        for row in probation:
                            publish(row, "repaired_history" if aligned else "local_repaired_history",
                                    aligned)
                        if adaptive_plan is not None:
                            pending[:] = [(buffered, adaptive_plan, was_weak)
                                          for buffered, _, was_weak in pending]
                            adaptive_plan = None
                        if rebuild is not None:
                            for buffered, applied, was_weak in pending:
                                fitted_view = applied if isinstance(applied, RegionPlan) else "fit"
                                rebuild.record("skip" if was_weak else fitted_view, buffered.timestamp)
                        catch_up_standby(retired)
                        if regional_plan is not None:
                            accepted_region = regional_plan
                            recovered_region = 0
                            regional_plan = None
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
            regional_suspect = proposal is not None and (
                regional_plan is None or bool(set(regional_plan.bad) & set(proposal.bad)))
            if (weak or regional_suspect) and (pending or armed):
                if not pending:
                    regional_plan = proposal if regional_suspect else None
                pending.append((pair, regional_plan or view, weak))
                if regional_plan is not None and len(pending) == 2:
                    # Both withheld frames are filled by the same inertial history path.
                    pending[:] = [(look, applied, True) for look, applied, _ in pending]
                if len(pending) == 2:
                    event_id += 1
                    candidate_fitted = False
                    anchor = active.snapshot
                    events.emit("isolate", event=event_id,
                                fault="regional_visual" if regional_plan else "image_observation",
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
                        mirrored_pending = queued.at_boundary(args.isolation_wait_ms / 1000
                                                              if args.isolation_wait_ms else None)
                    except WORKER_FAILURE as error:
                        events.emit("standby_unavailable", event=event_id, reason=str(error))
                        retire_busy_standby(type(error).__name__, pair.timestamp)
                        reject("incremental_checkpoint_not_ready")
                        continue
                    finally:
                        timing("standby_boundary_wait", pair.timestamp, started)
                    if not probe_standby():
                        reject("standby_requalification_pending")
                        continue
                    private, standby = standby, None
                    if args.async_recovery:
                        settled_anchor = boundary_state(active, "isolation_active")
                        try:
                            settled_private = boundary_state(private, "isolation_standby")
                        except WORKER_FAILURE as error:
                            reject(f"standby_boundary_worker: {error}")
                            continue
                        if settled_anchor is None or settled_private is None:
                            reject("isolation_boundary_not_settled")
                            continue
                        anchor = settled_anchor
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
                if isinstance(deferred_view, RegionPlan):
                    events.emit("regional_suspect_cleared", timestamp=deferred.timestamp)
                    deferred_view = "raw"
                previous = consume_public(deferred, deferred_view)
                publish(previous, "native" if aligned else "local_unverified", aligned)
                regional_plan = None

            if accepted_region is not None and not weak:
                view = accepted_region
                images = accepted_region.mask(images)
            result = consume_public(pair, view, images)
            imu_delta = vision.imu_residual(previous, result)
            if previous is not None and (previous["map_id"] != result["map_id"]
                                         or previous["maps"] != result["maps"]):
                aligned = False
            publish(result, "native" if aligned else "local_unverified", aligned)
            previous = result
            anchor_pair = pair
            observe_reentry(result)
            if view == "raw" and prepared is not None:
                region_reference = prepared
            if view == "raw":
                capture_checkpoint(pair, result)
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
            publish(consume_public(deferred, "raw" if isinstance(view, RegionPlan) else view), "native", aligned)
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
        if checkpoint_io is not None:
            checkpoint_io.shutdown()
        if rebuild is not None:
            rebuild.cancelled = True
        if parallel is not None:
            parallel.shutdown()
        if rebuild is not None:
            events.emit("standby_journal", replay_plan_bytes=len(rebuild.entries),
                        overflow=rebuild.overflow, max_frames=rebuild.limit,
                        last_replayed_frames=rebuild.replayed_frames,
                        attempts=rebuild_count, process_recovery_scope="standby")
        if args.share_orb_features:
            events.emit("orb_feature_exchange", workers=[worker.feature_stats for worker in feature_workers])
        for name, receipt in retired_workers:
            events.emit("worker_exit", name=name, exit=receipt.result())
        for worker in workers:
            events.emit("worker_exit", exit=worker.close())
        if shared_features is not None:
            events.emit("orb_feature_storage", slots=shared_features.slots,
                        logical_bytes=os.fstat(shared_features.fd).st_size,
                        allocated_bytes=os.fstat(shared_features.fd).st_blocks * 512)
            shared_features.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("dataset", "worker", "vocabulary", "settings", "output"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--mode", choices=("native", "recover", "qualify"), required=True)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--profile-stages", action="store_true")
    parser.add_argument("--isolation-wait-ms", type=int, default=0, choices=range(51), metavar="0..50",
                        help="standby wait allowed only after two observations confirm isolation")
    parser.add_argument("--rebase-standby", action="store_true",
                        help="one background restart from a newer durable generation when chasing stale input")
    parser.add_argument("--primary-first", action="store_true",
                        help="never wait for standby work on the foreground path")
    parser.add_argument("--async-recovery", action="store_true",
                        help="overlap local mapping with private replay and synchronize recovery boundaries")
    parser.add_argument("--realtime", action="store_true")
    parser.add_argument("--share-orb-features", action="store_true")
    parser.add_argument("--feature-transport", choices=("pipe", "shared"), default="pipe")
    parser.add_argument("--archive-orb-features", action="store_true",
                        help="retain exact ORB packets within the reconstruction horizon")
    parser.add_argument("--checkpoint-vocabulary", type=Path,
                        help="trusted binary cache of the exact configured text vocabulary")
    parser.add_argument("--native-checkpoints", action="store_true",
                        help="store native checkpoints; rebuild with a bounded input suffix")
    parser.add_argument("--rebuild-standby", action="store_true",
                        help="rebuild a lost stereo replica in the background from this recording")
    parser.add_argument("--subscriber", type=Path)
    parser.add_argument("--delay", type=float, default=0.012, help="extra frame pacing in seconds")
    parser.add_argument("--qualify-at", type=float, default=25.0)
    parser.add_argument("--adaptive-gate", action="store_true",
                        help="use a raw-support-based holdout partition and an 8-inlier distributed gate")
    parser.add_argument("--regional-visual", action="store_true",
                        help="detect regional stereo/temporal degradation and use disjoint heldout tiles")
    parser.add_argument("--regional-cover", nargs=3, action="append", default=[],
                        metavar=("START_S", "END_S", "CELLS"))
    parser.add_argument("--occlude", nargs=2, type=float, action="append", default=[],
                        metavar=("START_S", "END_S"))
    args = parser.parse_args()
    if args.async_recovery and args.mode != "recover":
        parser.error("asynchronous recovery requires recover mode")
    if args.isolation_wait_ms and not args.primary_first:
        parser.error("a separate isolation wait requires primary-first")
    if args.rebase_standby and not (args.primary_first and args.native_checkpoints and args.rebuild_standby):
        parser.error("standby rebase requires primary-first with native checkpoint recovery")
    try:
        args.regional_cover = [(float(start), float(end), tuple(map(int, cells.split(","))))
                               for start, end, cells in args.regional_cover]
    except ValueError:
        parser.error("regional cover needs a valid interval and comma-separated cells")
    if any(not (0 <= start < end and cells and all(0 <= i < CELLS for i in cells))
           for start, end, cells in args.regional_cover):
        parser.error("invalid regional cover interval or cell")
    if (any(not 0 <= start < end for start, end in args.occlude)
            or args.delay < 0 or args.limit is not None and args.limit <= 0):
        parser.error("invalid frame limit, cadence or fault interval")
    if args.feature_transport == "shared" and not args.share_orb_features:
        parser.error("shared transport requires --share-orb-features")
    if args.archive_orb_features and not (args.rebuild_standby and args.feature_transport == "shared"):
        parser.error("feature archive requires shared transport and standby reconstruction")
    if args.checkpoint_vocabulary is not None and (
            not args.native_checkpoints or not args.checkpoint_vocabulary.is_file()):
        parser.error("checkpoint vocabulary requires native checkpoint mode and an existing cache")
    if args.native_checkpoints and not args.rebuild_standby:
        parser.error("native checkpoints require standby reconstruction")
    if args.rebuild_standby and args.mode != "recover":
        parser.error("standby reconstruction requires recover mode")
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
                    fault_intervals_s=args.occlude, regional_cover=args.regional_cover,
                    regional_visual=args.regional_visual, adaptive_gate=args.adaptive_gate,
                    delay_s=args.delay,
                    drain_local_mapping="ORB_VIO_DRAIN_LOCAL_MAPPING" in os.environ,
                    realtime=args.realtime,
                    external_subscriber=args.subscriber is not None,
                    shared_orb_features=args.share_orb_features,
                    feature_transport=args.feature_transport, rebuild_standby=args.rebuild_standby,
                    archive_orb_features=args.archive_orb_features, native_checkpoints=args.native_checkpoints,
                    primary_first=args.primary_first, profile_stages=args.profile_stages,
                    rebase_standby=args.rebase_standby, isolation_wait_ms=args.isolation_wait_ms,
                    async_recovery=args.async_recovery)
        run(args, events, args.output)


if __name__ == "__main__":
    main()
