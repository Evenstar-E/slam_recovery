#!/usr/bin/env python3
"""Independent recomputation of determinism_alignment.json (main 291a0dd).

Shares no code with evaluate_determinism_pairs.py: poses are read with rosbag, the association
is a nearest-within-tolerance rule written here, the Umeyama is written here, and the GT is read
from the TUM file. If the two implementations agree, the numbers are a property of the bags.

    ~/mm/micromamba run -p ~/mm/ros python -I -B docs/review_20261109_6b61c9d/verify_determinism_alignment.py
"""

from __future__ import annotations

import hashlib
import json
import os
import sys

import numpy as np
import rosbag

HERE = os.path.dirname(os.path.abspath(__file__))
RECORD = os.path.join(HERE, "determinism_alignment.json")
OUT = os.path.join(HERE, "determinism_alignment_verified.json")
GT = "/home/R26534/M2DGR/GT/room_02.txt"
POSE_TOPIC = "/aft_mapped_to_init"
TOL = 0.05


def poses(path):
    ts, xyz = [], []
    with rosbag.Bag(path, "r") as b:
        for _, m, _ in b.read_messages(topics=[POSE_TOPIC]):
            ts.append(m.header.stamp.to_sec())
            p = m.pose.pose.position
            xyz.append([p.x, p.y, p.z])
    o = np.argsort(ts)
    return np.asarray(ts)[o], np.asarray(xyz)[o]


def associate(ta, tb, tol=TOL):
    j = np.clip(np.searchsorted(tb, ta), 1, len(tb) - 1)
    pick = np.where(np.abs(tb[j - 1] - ta) <= np.abs(tb[j] - ta), j - 1, j)
    ok = np.abs(tb[pick] - ta) <= tol
    return np.flatnonzero(ok), pick[ok]


def umeyama(src, dst):
    cs, cd = src.mean(0), dst.mean(0)
    cov = (dst - cd).T @ (src - cs) / len(src)
    U, _D, Vt = np.linalg.svd(cov)
    S = np.eye(3)
    if np.linalg.det(U) * np.linalg.det(Vt) < 0:
        S[2, 2] = -1
    R = U @ S @ Vt
    return R, cd - R @ cs


def ate(path, gt_ts, gt_xyz):
    ts, xyz = poses(path)
    ia, ib = associate(ts, gt_ts)
    if len(ia) < 10:
        return None, int(len(ia))
    R, t = umeyama(xyz[ia], gt_xyz[ib])
    err = np.linalg.norm(xyz[ia] @ R.T + t - gt_xyz[ib], axis=1)
    return float(np.sqrt(np.mean(err ** 2))), int(len(ia))


def main():
    rec = json.load(open(RECORD, encoding="utf-8"))
    onset = rec["onset_s"]
    gt = np.loadtxt(GT)
    gt_ts, gt_xyz = gt[:, 0], gt[:, 1:4]
    out = {"record": RECORD, "pairs": {}}
    for tag, r in rec["pairs"].items():
        ta, xa = poses(r["run1_bag"])
        tb, xb = poses(r["run2_bag"])
        ia, ib = associate(ta, tb)
        ts = ta[ia]
        pre = ts < onset
        R, t = umeyama(xb[ib][pre], xa[ia][pre])
        gauge = np.linalg.norm(xb[ib][pre] @ R.T + t - xa[ia][pre], axis=1)
        dp = np.linalg.norm(xa[ia] - (xb[ib] @ R.T + t), axis=1)
        k = int(np.argmin(np.abs(ts - onset)))
        mine = {
            "first_output_run1_s": float(ta.min()), "first_output_run2_s": float(tb.min()),
            "first_scored_s": float(ts[0]), "common_ids": int(len(ts)),
            "common_ids_sha256": hashlib.sha256(
                ",".join(str(int(round(x * 1e9))) for x in ts).encode()).hexdigest(),
            "gauge_prefix_ids": int(pre.sum()),
            "gauge_residual_rmse_m": float(np.sqrt(np.mean(gauge ** 2))),
            "aligned_first_scored_m": float(dp[0]), "aligned_at_onset_m": float(dp[k]),
            "ate_run1_m": ate(r["run1_bag"], gt_ts, gt_xyz)[0],
            "ate_run2_m": ate(r["run2_bag"], gt_ts, gt_xyz)[0],
        }
        diffs = {f: (mine[f], r.get(f)) for f in mine
                 if r.get(f) is not None and not _close(f, mine[f], r.get(f))}
        out["pairs"][tag] = {"recomputed": mine, "diffs": diffs,
                             "verdict": "PASS" if not diffs else "FAIL"}
        print(tag, out["pairs"][tag]["verdict"], diffs or "")
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    print("wrote", OUT)


ATE_TOL_M = 1e-3          # association tie-breaking differs at the 1e-5 level; see the record
EXACT = {"common_ids_sha256", "common_ids", "gauge_prefix_ids"}


def _close(field, a, b):
    """Hashes and counts must agree exactly; metres may differ within the association noise."""
    if field in EXACT or isinstance(a, str):
        return a == b
    if field.startswith("ate_"):
        return abs(float(a) - float(b)) <= ATE_TOL_M
    return abs(float(a) - float(b)) <= 1e-9


if __name__ == "__main__":
    main()
