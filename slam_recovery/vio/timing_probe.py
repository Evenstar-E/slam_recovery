"""Replay timing faults against identical native ORB-SLAM3 checkpoint starts."""
import argparse
import csv
from dataclasses import replace
import json
import os
from pathlib import Path

import cv2 as cv
import numpy as np

from .checkpoint import CheckpointStore
from .run_euroc import Lane
from .stream import InputFault, Worker, euroc, read_pair
from .timing_recovery import (ImagePacket, ImuTimeline, pair_stereo,
                              qualify_offset, rotation_error)
from .visual_faults import StereoEvidence
from .vision import HeldOutStereo, rotation


FRAME_LAG = 50_000_000
CLOCK_JUMP = 50_000_000


def load_imu(root):
    with (root / "mav0/imu0/data.csv").open() as stream:
        for row in csv.reader(line for line in stream if not line.startswith("#")):
            gx, gy, gz, ax, ay, az = map(float, row[1:])
            yield int(row[0]), ax, ay, az, gx, gy, gz


def choose_windows(frames, origin, timeline, vision, window_frames):
    stamps = [frame.timestamp for frame in frames]
    rotation_change = []
    for a, b in zip(stamps, stamps[1:]):
        early = timeline.camera_rotation(a-100_000_000, b-100_000_000, vision.body_from_camera)
        late = timeline.camera_rotation(a+100_000_000, b+100_000_000, vision.body_from_camera)
        rotation_change.append(rotation_error(early, late))
    windows = []
    half = (window_frames - 1)//2
    for i in range(1, len(stamps) - window_frames):
        score = min(np.median(rotation_change[i:i+half]),
                    np.median(rotation_change[i+half:i+2*half]))
        windows.append((float(score), i+origin))
    return max(windows), min(windows)


def verify_stereo(window, timeline, previous):
    packets = []
    for frame in window:
        packets.append((frame.timestamp, ImagePacket(0, frame.timestamp, frame.left)))
        packets.append((frame.timestamp + FRAME_LAG, ImagePacket(1, frame.timestamp, frame.right)))
    packets.sort(key=lambda item: item[0])
    paired = tuple(pair_stereo(packets, 90_000_000))
    if len(paired) != len(window):
        raise RuntimeError("stereo pair count differs from original captures")
    corrected = [replace(frame, timestamp=stamp, left=left, right=right)
                 for frame, (stamp, left, right) in zip(window, paired)]
    corrected = tuple(timeline.reassign(corrected, previous))
    if corrected != tuple(window):
        raise RuntimeError("stereo pairing or its IMU assignment differs from original capture")
    missing = [item for item in packets if not (item[1].side == 1 and
               item[1].stamp == window[0].timestamp)]
    refusal = None
    try:
        list(pair_stereo(missing, 90_000_000))
    except InputFault as error:
        refusal = str(error)
    if refusal is None:
        raise RuntimeError("missing mate was incorrectly accepted")
    return corrected, {
        "lag_ms": FRAME_LAG/1e6, "physical_pairs_verified": len(corrected),
        "missing_mate_refusal": refusal,
    }


def observations(geometry, images, window, shift):
    result = []
    half = len(window)//2
    for start, end in ((0, half), (half, len(window))):
        # Separate the physical image exposures used to choose/verify the offset.
        # Longer visual rotation intervals improve signal relative to pixel error.
        block = []
        for i in range(start, end - 3):
            later = i + 3
            motion = geometry.compare(images[i], images[later], refine=True)
            if motion is not None:
                block.append((window[i].timestamp+shift, window[later].timestamp+shift,
                              motion["rotation"]))
        result.append(block)
    count = min(map(len, result))
    return result[0][:count] + result[1][:count]


def run_arm(label, feed, geometry, store, manifest, command, args, healthy_prefix):
    with store.restore(manifest) as prefix:
        worker = Worker(command, args.out/f"{label}.log", restore=prefix,
                        vocabulary_cache=args.vocabulary_cache)
    lane = Lane(worker, 0)
    poses = []
    try:
        for pair in healthy_prefix:
            lane.consume(pair, "raw")
        for original, delivered in zip(geometry, feed):
            pose = lane.consume(delivered, "raw")
            poses.append(dict(pose, physical_t=original.timestamp, imu_samples=len(delivered.imu),
                              first_imu_t=delivered.imu[0][0], last_imu_t=delivered.imu[-1][0]))
    finally:
        exit_code = worker.close()
    (args.out/f"{label}.json").write_text(json.dumps(poses, indent=2))
    return poses, exit_code


def comparison(clean, candidate):
    position, attitude = [], []
    for first, second in zip(clean, candidate):
        if (first["physical_t"] != second["physical_t"] or first["tracking"] != 2
                or second["tracking"] != 2 or first["map_id"] != second["map_id"]):
            continue
        a, b = (rotation(row["pose_cw"][3:]) for row in (first, second))
        center_a = -a.T @ first["pose_cw"][:3]
        center_b = -b.T @ second["pose_cw"][:3]
        position.append(float(np.linalg.norm(center_a-center_b)))
        attitude.append(rotation_error(a, b))
    return {"shared_native_frame_pairs": len(position),
            "rmse_against_clean_native_m": float(np.sqrt(np.mean(np.square(position)))) if position else None,
            "median_rotation_against_clean_native_rad": float(np.median(attitude)) if attitude else None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("dataset", "settings", "worker", "vocabulary", "vocabulary-cache", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--checkpoint-dir", type=Path, required=True)
    parser.add_argument("--window-frames", type=int, default=33, choices=(33, 65))
    args = parser.parse_args()
    os.environ["ORB_VIO_DRAIN_LOCAL_MAPPING"] = "1"
    args.out.mkdir()
    cv.setNumThreads(1)
    cv.setRNGSeed(7123)
    frames = list(euroc(args.dataset))
    vision = HeldOutStereo(args.settings)
    window_frames = args.window_frames
    timeline = ImuTimeline(load_imu(args.dataset))
    first_search = 280
    high, low = choose_windows(frames[first_search:820], first_search, timeline, vision, window_frames)
    geometry = StereoEvidence(vision)
    report = {}
    for label, (score, start) in (("excited", high), ("low_excitation", low)):
        window = frames[start:start+window_frames]
        prepared = [geometry.prepare(read_pair(frame, "raw")) for frame in window]
        report[label] = {
            "first_zero_based_index": start, "seconds_from_input_start": (window[0].timestamp-frames[0].timestamp)/1e9,
            "physical_frames": len(window), "imu_selected_excitation_rad": score,
            "clean": qualify_offset(observations(geometry, prepared, window, 0), timeline, vision.body_from_camera),
            "common_plus_50_ms": qualify_offset(observations(geometry, prepared, window, CLOCK_JUMP), timeline,
                                                vision.body_from_camera),
        }
    start = high[1]
    window = frames[start:start+window_frames]
    previous = frames[start-1].timestamp
    paired, stereo = verify_stereo(window, timeline, previous)
    report["stereo_arrival"] = stereo
    args.out.joinpath("diagnostics.json").write_text(json.dumps(report, indent=2))
    store = CheckpointStore.open_existing(args.checkpoint_dir)
    available = [json.loads(path.read_text()) for path in store.directory.glob("checkpoint-*.json")]
    manifest = max((item for item in available if item["count"] <= start), key=lambda item: item["count"])
    if frames[manifest["count"]-1].timestamp != manifest["timestamp"]:
        raise RuntimeError("checkpoint is not aligned with the input recording")
    healthy_prefix = frames[manifest["count"]:start]
    report["checkpoint"] = {key: manifest[key] for key in ("count", "timestamp", "state_sha256")}
    command = args.worker, args.vocabulary, args.settings
    observed = [replace(frame, timestamp=frame.timestamp+CLOCK_JUMP) for frame in window]
    mismatched = [replace(frame, right=frames[start+i-1].right) for i, frame in enumerate(window)]
    feeds = {"clean": window, "uncorrected_stereo": mismatched, "repaired_stereo": paired,
             "uncorrected_clock": tuple(timeline.reassign(observed, previous))}
    # No correction is sent to the native worker unless disjoint visual observations qualify it.
    decision = report["excited"]["common_plus_50_ms"]
    if decision["accepted"]:
        correction_ns = round(decision["estimated_correction_ms"]*1e6)
        feeds["corrected_clock"] = tuple(timeline.reassign(observed, previous, correction_ns))
    else:
        # Diagnostic control only. This arm is never an authorized detector output.
        feeds["oracle_clock_control"] = tuple(timeline.reassign(observed, previous, -CLOCK_JUMP))
    baseline = None
    report["native"] = {}
    report["replayed_healthy_prefix_frames"] = len(healthy_prefix)
    for label, feed in feeds.items():
        poses, code = run_arm(label, feed, window, store, manifest, command, args, healthy_prefix)
        if baseline is None:
            baseline = poses
        report["native"][label] = dict(
            comparison(baseline, poses), worker_exit=code, tracked=sum(r["tracking"] == 2 for r in poses),
            changed_imu_sample_intervals=sum(row.imu != clean.imu for row, clean in zip(feed, window)),
            first_interval_imu_samples=len(feed[0].imu),
        )
    args.out.joinpath("results.json").write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
