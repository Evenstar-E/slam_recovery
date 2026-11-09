#!/usr/bin/env python3
"""Preregistered bistability estimate: the same cell, four host repeats each.

Question is not which arm is better any more, but how often the host enters its bad mode on this
sequence.  Two cells (O and O+F-B), four repeats each, same prefix/config/runner, order varied by
interleaving so a run is not always preceded by the same one.

Pre-declared rule: if a cell crosses modes at least once across its four repeats, the sequence is
not usable for single-run factor comparisons.

Mode classification, fixed before the numbers: GOOD = patch-unsupported < 0.10 on the common set,
BAD = > 0.50, otherwise UNCLEAR.  Coverage and ATE (FULL_ALIGNMENT_DIAGNOSTIC) are reported
alongside but do not decide the mode.

    python3 -B docs/review_20261109_bbc3dcb/run_bistability_analysis.py
"""

from __future__ import annotations

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

INJ = "/tmp/fastlivo/room02_inj43.bag"
GT = "/home/R26534/M2DGR/GT/room_02.txt"
CELLS = {"O": "/tmp/fastlivo/room02_2x2_O.bag",
         "O+F-B": "/tmp/fastlivo/room02_2x2_O_plus_F_minus_B.bag"}
NEW = {("O", i): f"/tmp/fastlivo/res_bist_O_r{i}.bag" for i in (1, 2, 3, 4)}
NEW.update({("O+F-B", i): f"/tmp/fastlivo/res_bist_O_plus_F_minus_B_r{i}.bag"
            for i in (1, 2, 3, 4)})
EARLIER = {("O", 1): "/tmp/fastlivo/res_2x2_O_r1.bag",
           ("O", 2): "/tmp/fastlivo/res_2x2_O_r2.bag",
           ("O+F-B", 1): "/tmp/fastlivo/res_2x2_O_plus_F_minus_B_r1.bag",
           ("O+F-B", 2): "/tmp/fastlivo/res_2x2_O_plus_F_minus_B_r2.bag"}
RESULTS = os.path.join(_HERE, "room02_bistability_results.json")
GOOD_MAX, BAD_MIN = 0.10, 0.50


def main():
    inj_scans, _ = V.load_scans(INJ, V._sha_file(INJ))
    cln_scans, _ = V.load_scans(CLN_SCANS, V._sha_file(CLN_SCANS))
    inj_kfs, _ = V.pair_keyframes(inj_scans, V.load_poses(INJ_POSES))
    cln_kfs, _ = V.pair_keyframes(cln_scans, V.load_poses(CLN_POSES))
    ns_all = R.load_scan_ns(INJ, V._sha_file(INJ))
    j = np.searchsorted(ns_all, np.asarray([round(k["ts"] * 1e9) for k in inj_kfs],
                                           dtype=np.int64))
    kf_ns = np.asarray([int(ns_all[min([c for c in (q - 1, q) if 0 <= c < len(ns_all)],
                                       key=lambda c: abs(ns_all[c] / 1e9 - t))])
                        for t, q in zip([k["ts"] for k in inj_kfs], j)], dtype=np.int64)
    prefix = [i for i in range(len(inj_kfs)) if kf_ns[i] < 1627643759554082870]
    keys = [i for i in range(len(inj_kfs)) if kf_ns[i] >= 1627643759554082870]

    from slam_recovery.experiments.evaluation import load_tum_trajectory_se3, \
        associate_trajectories
    ts_gt, xyz_gt, _ = load_tum_trajectory_se3(GT)
    cln_ts = np.asarray([k["ts"] for k in cln_kfs])
    cln_xyz = np.asarray([k["T"][:3, 3] for k in cln_kfs])
    proxy = np.vstack([V.world_pts(k) for k in cln_kfs])
    proxy_tree = cKDTree(proxy)

    bags = {c: {round(t, 6): p for t, p in V.load_scans(p, V._sha_file(p))[0]}
            for c, p in CELLS.items()}

    def _poses(path):
        poses, _st = R.pose_lookup(V.load_poses(path), range(len(inj_kfs)),
                                   lambda i: inj_kfs[i]["ts"])
        return poses

    def _score(cell, path, common_ids):
        poses = _poses(path)
        ids = [i for i in keys if i in poses]
        use = [i for i in prefix if i in poses]
        _mt, mi, mc = V.associate(np.asarray([inj_kfs[i]["ts"] for i in use]),
                                  np.asarray([poses[i][:3, 3] for i in use]), cln_ts, cln_xyz)
        Ra, ta = V.umeyama(mi, mc)
        w_by = {}
        for i in ids:
            body = bags[cell][round(inj_kfs[i]["ts"], 6)]
            w = body @ poses[i][:3, :3].T + poses[i][:3, 3]
            if len(w) > V.KF_CAP:
                w = w[:: max(1, len(w) // V.KF_CAP)][:V.KF_CAP]
            w_by[i] = w

        def _metrics(id_list):
            pts = np.vstack([w_by[i] for i in id_list]) @ Ra.T + ta
            d, _ = cKDTree(pts).query(proxy, k=1, distance_upper_bound=R.R_NN)
            cov = float(np.isfinite(d).mean())
            bm = R.bounded_metrics(pts, proxy_tree, proxy)
            return cov, float(bm["patch"]["unsupported_fraction"])

        cov, uns = _metrics(ids)
        ids_c = [i for i in common_ids if i in w_by]
        cov_c, uns_c = _metrics(ids_c) if ids_c else (None, None)

        def _mode(u):
            if u is None:
                return None
            return "GOOD" if u < GOOD_MAX else ("BAD" if u > BAD_MIN else "UNCLEAR")

        ts = np.asarray([inj_kfs[i]["ts"] for i in ids])
        xyz = np.asarray([poses[i][:3, 3] for i in ids])
        mt, me, mg = associate_trajectories(ts, xyz, ts_gt, xyz_gt, 0.05)
        ate = None
        if len(mt) >= 10:
            Ru, tu = V.umeyama(me, mg)
            ate = float(np.sqrt(np.mean(np.sum((me @ Ru.T + tu - mg) ** 2, axis=1))))
        return {"frames": len(ids), "common_frames": len(ids_c),
                "coverage": cov, "unsupported_fraction": uns,
                "common_coverage": cov_c, "common_unsupported_fraction": uns_c,
                "ate_full_alignment_diagnostic_m": ate,
                "mode": _mode(uns), "mode_common": _mode(uns_c),
                "output_sha256": V._sha_file(path)}

    res = {"protocol": {"source": "declared in session before the four repeats; not verifiable "
                                  "from the repository (UNVERIFIABLE)",
                        "cells": list(CELLS), "repeats_per_cell": 4,
                        "rule": "if a cell crosses modes at least once across its four repeats, "
                                "the sequence is not usable for single-run factor comparison",
                        "mode_rule": f"GOOD unsupported < {GOOD_MAX}, BAD > {BAD_MIN}, else "
                                     f"UNCLEAR"},
           "provenance": "REAL_HOST; same bags and config as the 2x2; order varied by "
                         "interleaving",
           "new_runs": {}, "earlier_2x2_runs": {}, "cells": {}}

    all_paths = {k: p for k, p in list(NEW.items()) + list(EARLIER.items())
                 if os.path.exists(p)}
    ids_by_run = {k: set(i for i in keys if i in _poses(p)) for k, p in all_paths.items()}
    common_ids = sorted(set.intersection(*ids_by_run.values())) if ids_by_run else []
    res["common_set"] = {"n": len(common_ids), "n_keys": len(keys),
                         "per_run_available": {f"{c}#{i}": len(v)
                                               for (c, i), v in ids_by_run.items()}}
    for key, path in NEW.items():
        cell, i = key
        if not os.path.exists(path):
            res["new_runs"][f"{cell}#{i}"] = {"status": "MISSING", "bag": path}
            continue
        res["new_runs"][f"{cell}#{i}"] = _score(cell, path, common_ids)
    for key, path in EARLIER.items():
        cell, i = key
        if os.path.exists(path):
            res["earlier_2x2_runs"][f"{cell}#earlier{i}"] = _score(cell, path, common_ids)

    for cell in CELLS:
        seq = [res["new_runs"].get(f"{cell}#{i}", {}).get("mode") for i in (1, 2, 3, 4)]
        modes = [m for m in seq if m in ("GOOD", "BAD", "UNCLEAR")]
        cross = len(set(modes)) > 1 if modes else None
        combined = modes + [v["mode"] for k, v in res["earlier_2x2_runs"].items()
                            if k.startswith(f"{cell}#")]
        seq_c = [res["new_runs"].get(f"{cell}#{i}", {}).get("mode_common")
                 for i in (1, 2, 3, 4)]
        modes_c = [m for m in seq_c if m in ("GOOD", "BAD", "UNCLEAR")]
        res["cells"][cell] = {
            "sequence": seq,
            "sequence_common_set": seq_c,
            "crosses_modes": cross,
            # Different categories are not proof of two attractors; report the literal
            # GOOD-vs-BAD crossing separately from UNCLEAR involvement.
            "crosses_good_and_bad": (("GOOD" in modes) and ("BAD" in modes)),
            "good": modes.count("GOOD"), "bad": modes.count("BAD"),
            "unclear": modes.count("UNCLEAR"),
            "combined_with_earlier_2": {"modes": combined,
                                        "good": combined.count("GOOD"),
                                        "bad": combined.count("BAD")},
            "verdict": ("SEQUENCE_UNUSABLE_FOR_SINGLE_RUN" if cross
                        else ("STABLE_" + modes[0] if modes else "NO_DATA")),
        }
    with open(RESULTS, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=float)
    for cell, v in res["cells"].items():
        print(f"{cell}: {v['sequence']}  crosses={v['crosses_modes']}  "
              f"good/bad={v['good']}/{v['bad']}  combined(6)={v['combined_with_earlier_2']}  -> "
              f"{v['verdict']}")
    print(f"saved {RESULTS}")


if __name__ == "__main__":
    main()
