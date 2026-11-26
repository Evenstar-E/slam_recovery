"""Score published ORB-SLAM3 positions against raw EuRoC Vicon observations."""
import argparse
import bisect
from collections import Counter
import csv
import json
from pathlib import Path

import numpy as np
import yaml

from .vision import HeldOutStereo, rotation


def reference(dataset):
    vicon = dataset / "mav0/vicon0"
    parameters = yaml.safe_load((vicon / "sensor.yaml").read_text())
    body_from_sensor = np.array(parameters["T_BS"]["data"]).reshape(4, 4)
    sensor_to_body = -body_from_sensor[:3, :3].T @ body_from_sensor[:3, 3]
    stamps, positions = [], []
    with (vicon / "data.csv").open(newline="") as stream:
        for row in csv.reader(line for line in stream if not line.startswith("#")):
            stamp = int(row[0])
            x, y, z, qw, qx, qy, qz = map(float, row[1:])
            stamps.append(stamp)
            positions.append(np.array([x, y, z]) + rotation([qx, qy, qz, qw]) @ sensor_to_body)
    return stamps, positions


def interpolate(stamps, positions, stamp):
    i = bisect.bisect_left(stamps, stamp)
    if i < len(stamps) and stamps[i] == stamp:
        return positions[i]
    if not 0 < i < len(stamps) or stamps[i] - stamps[i-1] > 35_000_000:
        return None
    ratio = (stamp - stamps[i-1]) / (stamps[i] - stamps[i-1])
    return (1-ratio) * positions[i-1] + ratio * positions[i]


def align(estimated, true):
    estimated, true = np.array(estimated), np.array(true)
    a, b = estimated.mean(axis=0), true.mean(axis=0)
    U, _, Vh = np.linalg.svd((estimated-a).T @ (true-b))
    correction = np.eye(3)
    correction[-1, -1] = np.sign(np.linalg.det(Vh.T @ U.T))
    R = Vh.T @ correction @ U.T
    return R, b - R @ a


def score(dataset, settings, paths):
    stamps, positions = reference(dataset)
    camera_to_body = HeldOutStereo(settings).camera_to_body
    results, errors = {}, {}
    for path in paths:
        counts = Counter()
        timestamps, matched = [], {}
        lifecycle = []
        with path.open() as stream:
            for line in stream:
                row = json.loads(line)
                kind = row["type"]
                counts[kind] += 1
                if kind == "run":
                    windows = row["fault_intervals_s"]
                elif kind == "frame":
                    timestamps.append(row["timestamp"])
                elif kind == "pose":
                    counts["history_delivered"] += row["channel"] == "repaired_history"
                    if not row["coordinate_verified"]:
                        counts["local_unverified"] += 1
                        continue
                    t = row["timestamp"]
                    true = interpolate(stamps, positions, t)
                    if true is not None:
                        pose = np.array(row["pose_cw"])
                        position = rotation(pose[3:]).T @ (camera_to_body - pose[:3])
                        if t in matched:
                            raise ValueError(f"duplicate output for {t}")
                        matched[t] = (position, true)
                elif kind in ("isolate", "checkpoint_replay", "clean_checkpoint_replay",
                              "clean_suffix_replay", "promote", "reject", "rearmed",
                              "worker_exit", "complete"):
                    lifecycle.append(row)
        origin = timestamps[0]
        pre_anchor_end = min((start for start, _ in windows), default=25.0) - 0.25
        anchor = [value for stamp, value in matched.items()
                  if 8 <= (stamp - origin)/1e9 <= pre_anchor_end]
        residuals = {}
        if len(anchor) >= 20:
            R, shift = align(*zip(*anchor))
            residuals = {stamp: float(np.linalg.norm(R @ position + shift - truth))
                         for stamp, (position, truth) in matched.items()}
        errors[str(path)] = residuals
        coverage = [
            {"start_s": start, "end_s": end,
             "input_frames": sum(start <= (t - origin)/1e9 < end for t in timestamps),
             "verified_scored_frames": sum(start <= (t - origin)/1e9 < end for t in residuals)}
            for start, end in windows
        ]
        results[str(path)] = dict(counts=counts, lifecycle=lifecycle, cases=coverage,
                                  anchor_pairs=len(anchor), scored=len(residuals),
                                  rmse_m=rms(residuals.values()))
    common = set.intersection(*(set(values) for values in errors.values()))
    for name, values in errors.items():
        results[name]["common_scored"] = len(common)
        results[name]["common_rmse_m"] = rms(values[t] for t in sorted(common))
    return results


def rms(values):
    values = list(values)
    return float(np.sqrt(np.mean(np.square(values)))) if values else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("settings", type=Path)
    parser.add_argument("events", type=Path, nargs="+")
    args = parser.parse_args()
    print(json.dumps(score(args.dataset, args.settings, args.events), indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
