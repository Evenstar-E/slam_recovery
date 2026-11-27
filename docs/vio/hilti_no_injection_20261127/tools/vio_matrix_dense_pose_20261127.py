"""Paired 1 s relative pose errors and timely, accurate delivery on dense Hilti references."""
from decimal import Decimal
import json
import math
from pathlib import Path

import numpy as np


root = Path.home() / "vio_matrix_evidence_20261127"
T_b_c = np.asarray(json.loads((root / "config/calibration.json").read_text())["body_from_camera"][0])


def rotation(q):
    x, y, z, w = q / np.linalg.norm(q)
    return np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                     [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                     [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])


def slerp(q0, q1, t):
    dot = float(q0 @ q1)
    if dot < 0:
        q1 = -q1
        dot = -dot
    if dot > .9995:
        return q0 + (q1-q0)*t
    theta = math.acos(np.clip(dot, -1, 1))
    return (math.sin((1-t)*theta)*q0 + math.sin(t*theta)*q1) / math.sin(theta)


def reference_at(times, poses, key):
    i = int(times.searchsorted(key))
    if i < len(times) and times[i] == key:
        v = poses[i]
        return rotation(v[3:]), v[:3]
    if i == 0 or i == len(times) or times[i]-times[i-1] > 150_000_000:
        return None
    d = (key-times[i-1]) / (times[i]-times[i-1])
    a, b = poses[i-1], poses[i]
    return rotation(slerp(a[3:], b[3:], d)), (1-d)*a[:3] + d*b[:3]


def positions(rows):
    poses = {}
    for row in rows:
        v = np.asarray(row["pose_cw"])
        wc = rotation(v[3:]).T
        wb = wc @ T_b_c[:3,:3].T
        poses[row["timestamp"]] = (wb, -wc @ v[:3] - wb @ T_b_c[:3,3])
    return poses


def read(path):
    return [json.loads(line) for line in path.open()] if path.is_file() else []


def relative(a, b):
    r0, t0 = a
    r1, t1 = b
    return r0.T @ r1, r0.T @ (t1-t0)


def rpe(gt, runs, times):
    errors = {key: [[], []] for key in runs}
    delta_times = []
    times = np.asarray(times, dtype=np.int64)
    for i, t0 in enumerate(times):
        expected = t0+1_000_000_000
        index = int(times.searchsorted(expected))
        indices = [j for j in (index-1, index) if i < j < len(times)]
        if not indices:
            continue
        j = min(indices, key=lambda k: abs(times[k]-expected))
        t1 = times[j]
        if abs(t1-expected) > 50_000_000:
            continue
        delta_times.append((t1-t0)/1e9)
        rr, rp = relative(gt[t0], gt[t1])
        for mode, track in runs.items():
            er, ep = relative(track[t0], track[t1])
            errors[mode][0].append(float(np.linalg.norm(ep-rp)))
            angle = math.degrees(math.acos(np.clip((np.trace(rr.T @ er)-1)/2., -1., 1.)))
            errors[mode][1].append(angle)
    return {mode: {"count": len(delta_times),
                   "translation_rmse_m": float(np.sqrt(np.mean(np.square(e[0])))) if delta_times else None,
                   "rotation_rmse_deg": float(np.sqrt(np.mean(np.square(e[1])))) if delta_times else None}
            for mode, e in errors.items()}


def measure(sequence, host, gt_times, gt_poses):
    export = root / sequence
    test_name = sequence
    if sequence == "exp18" and host == "orb" and (root / "exp18-nodrain/cleanup.json").is_file():
        test_name = "exp18-nodrain"
        export = root / test_name
    suffix = "-startup-fixed" if test_name == "exp18" and host in ("orb", "vins") else ""
    runs, clock = {}, {}
    for mode in ("native", "recover"):
        run = export / "results" / f"{test_name}-{host}-{mode}{suffix}"
        if not (run / "result.json").is_file():
            return None
        runs[mode] = positions([x for x in read(run/"external.jsonl")
                                if x["coordinate_verified"] and x.get("imu_initialized", True)])
        clock[mode] = {x["timestamp"] for x in read(run / "log/input_clock.jsonl")}
    gt = {}
    for stamp in clock["native"] | clock["recover"]:
        sample = reference_at(gt_times, gt_poses, stamp)
        if sample is not None:
            gt[stamp] = sample
    common = sorted(gt.keys() & runs["native"].keys() & runs["recover"].keys())
    return {"test": test_name, "common_original_and_inertial_frames": len(common),
            "truth_times_observed": len(gt), "rpe_1sec": rpe(gt, runs, common)}


output = {}
for sequence in ("exp16", "exp18"):
    data = [row.split() for row in (root / "config" / f"{sequence}-reference.txt").read_text().splitlines()
            if row.strip() and not row.startswith("#")]
    times = np.asarray([int(Decimal(x[0])*10**9) for x in data])
    poses = np.asarray([[float(cell) for cell in x[1:]] for x in data])
    poses[:,3:] /= np.linalg.norm(poses[:,3:], axis=1, keepdims=True)
    output[sequence] = {host: measure(sequence, host, times, poses) for host in ("orb", "vins", "okvis")}
(root / "DENSE_RPE.json").write_text(json.dumps(output, indent=2))
