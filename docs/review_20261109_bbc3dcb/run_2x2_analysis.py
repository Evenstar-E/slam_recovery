#!/usr/bin/env python3
"""2x2 single-factor read-out for room_02: O, O+F, O-B, O+F-B, two host repeats each.

The four bags are the preregistered ones (outside-window rows identical across arms, in-window rows
from the original-index audit).  This script does not build anything; it scores the replays.

Pre-declared failure rule: a cell fails if its full-alignment ATE exceeds 1.0 m. A cell is STABLE
only if both repeats land on the same side.  An interaction is supported only if O+F-B fails both
times while O+F and O-B both do not; anything weaker is reported as run variance, non-equivalent
construction, or a different actual/arm condition -- never as interaction by default.

ATE is reported twice and never merged: FULL_ALIGNMENT_DIAGNOSTIC (one SE(3) over the whole run)
and the frozen-prefix protocol (alignment fitted on pre-onset keyframes only).

    python3 -B docs/review_20261109_bbc3dcb/run_2x2_analysis.py
"""

from __future__ import annotations

import hashlib
import json
import os
import sys

import numpy as np
from scipy.spatial import cKDTree

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_HERE))
for _p in (_HERE, _REPO):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import verify_four_arm_independent as V          # noqa: E402
import run_fixed_input_repair_c0c3 as R          # noqa: E402
from run_room02_confirmation import CLN_SCANS, CLN_POSES, INJ_POSES  # noqa: E402

INJ_SCANS = "/tmp/fastlivo/room02_inj43.bag"
GT = "/home/R26534/M2DGR/GT/room_02.txt"
ARMS = {"O": "/tmp/fastlivo/room02_2x2_O.bag",
        "O+F": "/tmp/fastlivo/room02_2x2_O_plus_F.bag",
        "O-B": "/tmp/fastlivo/room02_2x2_O_minus_B.bag",
        "O+F-B": "/tmp/fastlivo/room02_2x2_O_plus_F_minus_B.bag"}
RUN = lambda arm, rep: f"/tmp/fastlivo/res_2x2_{arm.replace('+','_plus_').replace('-','_minus_')}_r{rep}.bag"
RESULTS = os.path.join(_HERE, "room02_2x2_results.json")
FAIL_ATE_M = 1.0


def main():
    inj_scans, _ = V.load_scans(INJ_SCANS, V._sha_file(INJ_SCANS))
    cln_scans, _ = V.load_scans(CLN_SCANS, V._sha_file(CLN_SCANS))
    inj_kfs, _ = V.pair_keyframes(inj_scans, V.load_poses(INJ_POSES))
    cln_kfs, _ = V.pair_keyframes(cln_scans, V.load_poses(CLN_POSES))
    ns_all = R.load_scan_ns(INJ_SCANS, V._sha_file(INJ_SCANS))
    j = np.searchsorted(ns_all, np.asarray([round(k["ts"] * 1e9) for k in inj_kfs],
                                           dtype=np.int64))
    kf_ns = np.asarray([int(ns_all[min([c for c in (q - 1, q) if 0 <= c < len(ns_all)],
                                       key=lambda c: abs(ns_all[c] / 1e9 - t))])
                        for t, q in zip([k["ts"] for k in inj_kfs], j)], dtype=np.int64)
    from run_room02_confirmation import _raw_by_ns
    a = _raw_by_ns(INJ_SCANS, "/velodyne_points")
    b = _raw_by_ns(CLN_SCANS, "/velodyne_points")
    differing = [ns for ns in sorted(set(a) & set(b)) if a[ns] != b[ns]]
    onset_ns, end_ns = min(differing), max(differing)
    prefix = [i for i in range(len(inj_kfs)) if kf_ns[i] < onset_ns]
    keys = [i for i in range(len(inj_kfs)) if kf_ns[i] >= onset_ns]

    from slam_recovery.experiments.evaluation import load_tum_trajectory_se3, \
        associate_trajectories
    ts_gt, xyz_gt, _ = load_tum_trajectory_se3(GT)
    cln_ts = np.asarray([k["ts"] for k in cln_kfs])
    cln_xyz = np.asarray([k["T"][:3, 3] for k in cln_kfs])
    proxy = np.vstack([V.world_pts(k) for k in cln_kfs])
    proxy_tree = cKDTree(proxy)



    cells = {}
    avail = {}
    for arm in ARMS:
        for rep in (1, 2):
            rp = RUN(arm, rep)
            if not os.path.exists(rp):
                cells[f"{arm}#{rep}"] = {"status": "MISSING", "bag": rp}
                continue
            poses, stats = R.pose_lookup(V.load_poses(rp), range(len(inj_kfs)),
                                         lambda i: inj_kfs[i]["ts"])
            ids = [i for i in keys if i in poses]
            avail[(arm, rep)] = set(int(i) for i in ids)
            cells[f"{arm}#{rep}"] = {"status": "OK", "ids": ids, "poses": poses,
                                     "pairing": stats, "bag": rp}

    common = set(int(i) for i in keys)
    for k, v in cells.items():
        if v.get("status") == "OK":
            common &= set(int(i) for i in v["ids"])
    common = sorted(common)
    print(f"[] common set across every cell: {len(common)} of {len(keys)} keys")

    out = {}
    for k, v in cells.items():
        if v.get("status") != "OK":
            out[k] = v
            continue
        arm = k.split("#")[0]
        poses = v["poses"]
        scans = {round(t, 6): p for t, p in V.load_scans(ARMS[arm], V._sha_file(ARMS[arm]))[0]}
        # frozen-prefix alignment (the protocol used everywhere else)
        use = [i for i in prefix if i in poses]
        _mt, mi, mc = V.associate(np.asarray([inj_kfs[i]["ts"] for i in use]),
                                  np.asarray([poses[i][:3, 3] for i in use]), cln_ts, cln_xyz)
        R_p, t_p = V.umeyama(mi, mc)
        pts, sizes, inw_parts = [], [], []
        for i in common:
            body = scans[round(inj_kfs[i]["ts"], 6)]
            w = body @ poses[i][:3, :3].T + poses[i][:3, 3]
            if len(w) > V.KF_CAP:
                w = w[:: max(1, len(w) // V.KF_CAP)][:V.KF_CAP]
            pts.append(w)
            sizes.append(len(w))
            inw_parts.append(np.full(len(w), onset_ns <= kf_ns[i] <= end_ns))
        pts = np.vstack(pts) @ R_p.T + t_p
        in_win = np.concatenate(inw_parts)
        d, _ = cKDTree(pts).query(proxy, k=1, distance_upper_bound=R.R_NN)
        covered = np.isfinite(d)
        bm = R.bounded_metrics(pts, proxy_tree, proxy)
        uns = int(round(bm["patch"]["unsupported_fraction"] * len(pts)))

        def _frac(mask):
            if not mask.any():
                return None
            b = R.bounded_metrics(pts[mask], proxy_tree, proxy)
            return float(b["patch"]["unsupported_fraction"])

        ts = np.asarray([inj_kfs[i]["ts"] for i in common])
        xyz = np.asarray([poses[i][:3, 3] for i in common])
        mt, me, mg = associate_trajectories(ts, xyz, ts_gt, xyz_gt, 0.05)
        ate_full = None
        if len(mt) >= 10:
            Ru, tu = V.umeyama(me, mg)
            err = np.linalg.norm(me @ Ru.T + tu - mg, axis=1)
            ate_full = float(np.sqrt(np.mean(err ** 2)))
        ate_prefix = None
        mpre = mt < cln_ts.min() + 1e9  # all of it, aligned by prefix
        if len(mt) >= 10:
            err2 = np.linalg.norm(me @ R_p.T + t_p - mg, axis=1)
            ate_prefix = float(np.sqrt(np.mean(err2 ** 2)))

        out[k] = {"status": "OK", "frames_scored": len(common),
                  "poses_matched_gt": int(len(mt)),
                  "coverage": float(covered.mean()),
                  "unsupported_fraction": float(uns / len(pts)),
                  "in_window_unsupported_fraction": _frac(in_win),
                  "healthy_unsupported_fraction": _frac(~in_win),
                  "ate_full_alignment_diagnostic_m": ate_full,
                  "ate_frozen_prefix_protocol_m": ate_prefix,
                  "fail": (None if ate_full is None else bool(ate_full > FAIL_ATE_M))}
        print(f"   {k:10s} cover {out[k]['coverage']:.4f} unsup "
              f"{out[k]['unsupported_fraction']:.4f} ATE {ate_full} "
              f"{'FAIL' if out[k]['fail'] else 'ok'}")

    summary = {}
    for arm in ARMS:
        f = [out.get(f"{arm}#{r}", {}).get("fail") for r in (1, 2)]
        summary[arm] = {"fail_repeats": f,
                        "stable": (None if any(x is None for x in f) else f[0] == f[1]),
                        "fails_both": bool(f[0] is True and f[1] is True),
                        "ok_both": bool(f[0] is False and f[1] is False)}
    interaction = (summary["O+F-B"]["fails_both"] and summary["O+F"]["ok_both"]
                   and summary["O-B"]["ok_both"])
    res = {
        "protocol": {"source": "docs/MILESTONE_fixed_input_repair.md (2x2 single factor)",
                     "fail_rule": f"full-alignment ATE > {FAIL_ATE_M} m fails; both repeats must "
                                  f"land on the same side to be stable",
                     "interaction_rule": "supported only if O+F-B fails both repeats while O+F "
                                         "and O-B do not"},
        "provenance": "REAL_HOST, two repeats per cell; proxy is the clean run map, not GT; "
                      "single sequence",
        "common_set": {"n": len(common), "n_keys": len(keys),
                       "ns_sha256": hashlib.sha256(",".join(str(int(kf_ns[i])) for i in
                                                           common).encode()).hexdigest()},
        "per_frame_available": {f"{a}#{r}": len(v) for (a, r), v in avail.items()},
        "cells": {k: {kk: vv for kk, vv in v.items() if kk not in ("ids", "poses")}
                  for k, v in out.items()},
        "summary": summary,
        "interaction_supported": bool(interaction),
        "ate_note": "ate_full_alignment_diagnostic_m is a FULL_ALIGNMENT_DIAGNOSTIC and must not "
                    "be merged into the frozen-prefix protocol table; ate_frozen_prefix_protocol_m "
                    "is the protocol number",
    }
    with open(RESULTS, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=float)
    print(json.dumps(summary, indent=1))
    print(f"[] interaction supported: {interaction}")
    print(f"saved {RESULTS}")


if __name__ == "__main__":
    main()
