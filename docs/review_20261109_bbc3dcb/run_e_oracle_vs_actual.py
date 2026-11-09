#!/usr/bin/env python3
"""E_actual versus E_oracle: both re-estimated by the native host, same everything else.

The decomposition could not separate the filter from the reference, because its fixed-pose arm used
the clean reference poses and therefore never asked the host to estimate state from the
actual-filter observation.  This does: two bags, both replayed through the same host with the same
config, differing only in what was removed.

  E_actual  actual-filter bag  -> FAST-LIVO2 rerun (already on disk)
  E_oracle  exact-oracle bag   -> FAST-LIVO2 rerun (this run; diagnostic ceiling, not deployable)

Criterion, declared before the numbers:
  * E_oracle good and E_actual bad -> the actual filter's removal/distribution/policy is the cause;
  * E_oracle also bad              -> stop tuning the filter; the ancillary / window state repair
                                      is the place to work.
No ROI or pairing-rule change; a negative result still ships.

Mechanism quantities, measured rather than inferred: retained returns per frame, weak-direction
information of the retained scan, effective point counts, trajectory error against GT where GT
covers the run, and the spatial distribution of retained returns for both arms.

    python3 -B docs/review_20261109_bbc3dcb/run_e_oracle_vs_actual.py
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
FILTERED = "/tmp/fastlivo/room02_inj43_filtered.bag"
ORACLE = "/tmp/fastlivo/room02_inj43_oracle.bag"
E_ACTUAL = "/tmp/fastlivo/res_room02_filtered.bag"
E_ORACLE = "/tmp/fastlivo/res_room02_oracle.bag"
E_HYBRID = "/tmp/fastlivo/res_room02_hybrid.bag"
HYBRID_BAG = "/tmp/fastlivo/room02_inj43_hybrid.bag"
GT = "/home/R26534/M2DGR/GT/room_02.txt"
RESULTS = os.path.join(_HERE, "room02_e_oracle_results.json")
ORACLE_REPORT = os.path.join(_HERE, "room02_oracle_bag_report.json")


def main():
    sha = {k: V._sha_file(p) for k, p in
           (("injected", INJ_SCANS), ("filtered", FILTERED), ("oracle_bag", ORACLE),
            ("clean_scans", CLN_SCANS), ("clean_poses", CLN_POSES),
            ("e_actual_poses", E_ACTUAL), ("e_oracle_poses", E_ORACLE),
            ("e_hybrid_poses", E_HYBRID), ("hybrid_bag", HYBRID_BAG),
            ("oracle_report", ORACLE_REPORT))}

    rep = json.load(open(ORACLE_REPORT))
    if rep.get("status") != "OK":
        raise SystemExit("oracle bag report is not OK; refusing to score")
    onset_ns, end_ns = rep["window"]["onset_ns"], rep["window"]["end_ns"]

    inj_scans, _ = V.load_scans(INJ_SCANS, sha["injected"])
    cln_scans, _ = V.load_scans(CLN_SCANS, sha["clean_scans"])
    inj_kfs, _ = V.pair_keyframes(inj_scans, V.load_poses(INJ_POSES))
    cln_kfs, _ = V.pair_keyframes(cln_scans, V.load_poses(CLN_POSES))
    ns_all = R.load_scan_ns(INJ_SCANS, sha["injected"])
    j = np.searchsorted(ns_all, np.asarray([round(k["ts"] * 1e9) for k in inj_kfs],
                                           dtype=np.int64))
    kf_ns = np.asarray([int(ns_all[min([c for c in (q - 1, q) if 0 <= c < len(ns_all)],
                                       key=lambda c: abs(ns_all[c] / 1e9 - t))])
                        for t, q in zip([k["ts"] for k in inj_kfs], j)], dtype=np.int64)
    prefix = [i for i in range(len(inj_kfs)) if kf_ns[i] < onset_ns]
    keys = [i for i in range(len(inj_kfs)) if kf_ns[i] >= onset_ns]

    pos_actual, pair_a = R.pose_lookup(V.load_poses(E_ACTUAL), range(len(inj_kfs)),
                                       lambda i: inj_kfs[i]["ts"])
    pos_oracle, pair_o = R.pose_lookup(V.load_poses(E_ORACLE), range(len(inj_kfs)),
                                       lambda i: inj_kfs[i]["ts"])
    pos_hybrid, _ph = R.pose_lookup(V.load_poses(E_HYBRID), range(len(inj_kfs)),
                                    lambda i: inj_kfs[i]["ts"])
    frames = [i for i in keys if i in pos_actual and i in pos_oracle and i in pos_hybrid]
    print(f"[] frame set {len(frames)} of {len(keys)} "
          f"(actual missing {len([i for i in keys if i not in pos_actual])}, "
          f"oracle missing {len([i for i in keys if i not in pos_oracle])})")

    cln_ts = np.asarray([k["ts"] for k in cln_kfs])
    cln_xyz = np.asarray([k["T"][:3, 3] for k in cln_kfs])

    def _align(poses):
        use = [i for i in prefix if i in poses]
        _mt, mi, mc = V.associate(np.asarray([inj_kfs[i]["ts"] for i in use]),
                                  np.asarray([poses[i][:3, 3] for i in use]), cln_ts, cln_xyz)
        return V.umeyama(mi, mc)

    by_stamp_f = {round(t, 6): p for t, p in V.load_scans(FILTERED, sha["filtered"])[0]}
    by_stamp_o = {round(t, 6): p for t, p in V.load_scans(ORACLE, sha["oracle_bag"])[0]}
    by_stamp_h = {round(t, 6): p for t, p in V.load_scans(HYBRID_BAG, sha["hybrid_bag"])[0]}

    def _map(ids, poses, by_stamp):
        out = []
        for i in ids:
            body = by_stamp[round(inj_kfs[i]["ts"], 6)]
            w = body @ poses[i][:3, :3].T + poses[i][:3, 3]
            if len(w) > V.KF_CAP:
                w = w[:: max(1, len(w) // V.KF_CAP)][:V.KF_CAP]
            out.append(w)
        return np.vstack(out)

    proxy = np.vstack([V.world_pts(k) for k in cln_kfs])
    proxy_tree = cKDTree(proxy)
    arms = {}
    for tag, poses, bags in (("E_actual", pos_actual, by_stamp_f),
                             ("E_oracle", pos_oracle, by_stamp_o),
                             ("E_hybrid", pos_hybrid, by_stamp_h)):
        R_a, t_a = _align(poses)
        pts = _map(frames, poses, bags) @ R_a.T + t_a
        tree = cKDTree(pts)
        d, _ = tree.query(proxy, k=1, distance_upper_bound=R.R_NN)
        covered = np.isfinite(d)
        bm = R.bounded_metrics(pts, proxy_tree, proxy)
        uns = int(round(bm["patch"]["unsupported_fraction"] * len(pts)))
        arms[tag] = {"poses": poses, "align": (R_a, t_a), "map": pts,
                     "coverage": float(covered.mean()), "covered": int(covered.sum()),
                     "unsupported": uns, "unsupported_fraction": float(uns / len(pts))}

    # ---- mechanism: retained returns and weak-direction information ---------------------
    def _retained(by_stamp, ids):
        n = [len(by_stamp[round(inj_kfs[i]["ts"], 6)]) for i in ids]
        return {"frames": len(ids), "mean_points_per_frame": float(np.mean(n)),
                "median_points_per_frame": float(np.median(n)),
                "min_points_per_frame": int(np.min(n))}

    mech = {"retained_returns": {
        "E_actual": _retained(by_stamp_f, frames),
        "E_oracle": _retained(by_stamp_o, frames),
        "hall_01_reference": {"in_window_kept_fraction_filtered": 0.1124,
                              "note": "the hall_01 filter retained 11.24 % of in-window points; "
                                      "room_02 retains 11.34 %, so the removal agreement is not "
                                      "what separates the sequences"}}}

    # weak-direction information on the in-window scans (6-DoF point-to-plane FIM)
    try:
        from slam_recovery.validation.fim_and_holdout import compute_6dof_point_to_plane_fim
        win_ids = [i for i in frames if onset_ns <= kf_ns[i] <= end_ns]
        def _fim(by_stamp):
            vals = []
            for i in win_ids:
                pts = by_stamp[round(inj_kfs[i]["ts"], 6)]
                if len(pts) < 50:
                    continue
                _r, _t, min_r, min_t, _ = compute_6dof_point_to_plane_fim(pts[:, :3])
                vals.append(min(min_r, min_t))
            return {"frames": len(vals),
                    "median_min_eigenvalue": float(np.median(vals)) if vals else None,
                    "p10": float(np.percentile(vals, 10)) if vals else None}
        mech["weak_direction_information"] = {
            "definition": "min of rotational/translational FIM eigenvalues on the in-window scans",
            "E_actual": _fim(by_stamp_f), "E_oracle": _fim(by_stamp_o)}
    except Exception as e:
        mech["weak_direction_information"] = {"status": "UNAVAILABLE", "why": str(e)}

    # spatial distribution of retained returns (voxel overlap is label-free; a corridor/room
    # split would need semantics this input does not carry)
    def _vox(by_stamp, ids):
        pts = np.vstack([by_stamp[round(inj_kfs[i]["ts"], 6)] for i in ids])
        return set(map(tuple, np.floor(pts / 0.5).astype(np.int64).tolist()))
    vf, vo = _vox(by_stamp_f, frames), _vox(by_stamp_o, frames)
    mech["spatial_distribution"] = {
        "voxel_m": 0.5,
        "E_actual_voxels": len(vf), "E_oracle_voxels": len(vo),
        "shared": len(vf & vo), "only_E_actual": len(vf - vo), "only_E_oracle": len(vo - vf),
        "note": "label-free overlap in the sensor frame; a corridor-versus-room split would need "
                "semantics this bag does not carry"}

    # trajectory error against GT, on the frames GT covers
    try:
        from slam_recovery.experiments.evaluation import load_tum_trajectory_se3, \
            associate_trajectories
        ts_gt, xyz_gt, _ = load_tum_trajectory_se3(GT)
        traj = {}
        for tag in ("E_actual", "E_oracle"):
            poses = arms[tag]["poses"]
            ids = [i for i in frames if i in poses]
            ts = np.asarray([inj_kfs[i]["ts"] for i in ids])
            xyz = np.asarray([poses[i][:3, 3] for i in ids])
            mt, me, mg = associate_trajectories(ts, xyz, ts_gt, xyz_gt, 0.05)
            if len(mt) >= 10:
                Ru, tu = V.umeyama(me, mg)
                err = np.linalg.norm(me @ Ru.T + tu - mg, axis=1)
                traj[tag] = {"matched": int(len(mt)), "ate_rmse_m": float(np.sqrt(np.mean(err**2))),
                             "ate_max_m": float(err.max())}
            else:
                traj[tag] = {"matched": int(len(mt)), "status": "TOO_FEW"}
        mech["trajectory_vs_gt"] = traj
    except Exception as e:
        mech["trajectory_vs_gt"] = {"status": "UNAVAILABLE", "why": str(e)}

    # ---- criterion ----------------------------------------------------------------------
    def _good(tag, base):
        return (arms[tag]["coverage"] >= base["coverage"] - 0.02
                and arms[tag]["unsupported_fraction"] <= base["unsupported_fraction"] + 0.02)
    base = arms["E_actual"]
    oracle_good = arms["E_oracle"]["unsupported_fraction"] < base["unsupported_fraction"] * 0.5
    actual_bad = base["unsupported_fraction"] > 0.1
    hybrid = arms["E_hybrid"]
    if oracle_good and actual_bad:
        verdict = ("FILTER_IS_THE_CAUSE (healthy-region removals)"
                   if hybrid["unsupported_fraction"] > 0.1
                   else "FILTER_IS_THE_CAUSE (in-window removal)")
    elif not oracle_good:
        verdict = "ORACLE_ALSO_DEGRADES -> FIX ANCILLARY/WINDOW STATE, NOT THE FILTER"
    else:
        verdict = "INDISTINGUISHABLE"

    res = {
        "protocol": {"source": "docs/MILESTONE_fixed_input_repair.md (E_actual vs E_oracle)",
                     "criterion": "E_oracle good and E_actual bad -> filter; E_oracle also bad -> "
                                  "ancillary/window state",
                     "note": "oracle is a diagnostic ceiling, not a deployable repair"},
        "provenance": "REAL_HOST for both reruns; proxy is the clean run map, not GT; single "
                      "sequence",
        "inputs_sha256": sha,
        "injection_window": {"onset_ns": onset_ns, "end_ns": end_ns},
        "frame_set": {"n_frames": len(frames), "n_keys": len(keys),
                      "missing_actual": [int(i) for i in keys if i not in pos_actual],
                      "missing_oracle": [int(i) for i in keys if i not in pos_oracle],
                      "ns_sha256": hashlib.sha256(",".join(str(int(kf_ns[i])) for i in
                                                          sorted(frames)).encode()).hexdigest()},
        "arms": {t: {"coverage": arms[t]["coverage"], "covered": arms[t]["covered"],
                     "unsupported": arms[t]["unsupported"],
                     "unsupported_fraction": arms[t]["unsupported_fraction"],
                     "map_points": int(len(arms[t]["map"]))} for t in arms},
        "mechanism": mech,
        "verdict": {"value": verdict,
                    "oracle_threshold_used": "E_oracle unsupported < 0.5x E_actual",
                    "E_oracle_unsupported": arms["E_oracle"]["unsupported_fraction"],
                    "E_hybrid_unsupported": arms["E_hybrid"]["unsupported_fraction"],
                    "hybrid_definition": "oracle removal inside the window, the actual filter's "
                                         "removal outside it",
                    "E_actual_unsupported": base["unsupported_fraction"]},
    }
    with open(RESULTS, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=float)
    for t in ("E_actual", "E_oracle", "E_hybrid"):
        print(f"[] {t}: cover {arms[t]['coverage']:.4f}, unsup "
              f"{arms[t]['unsupported_fraction']:.4f}")
    print(f"[] verdict: {verdict}")
    print(f"saved {RESULTS}")


if __name__ == "__main__":
    main()
