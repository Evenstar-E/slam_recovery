#!/usr/bin/env python3
"""Same-frame raw/native versus repaired comparison (R vs C3).

Fixed frame set: the keyframes for which the repaired arm has both a filtered scan and a re-run
pose.  Same frames in both arms, so this isolates "the repair" rather than "how much of the scene
was visited".

  R   the injected scan + the host's own pose (the C0 construction, restricted to these frames)
  C3  the filtered scan + the re-run pose (the existing filtered bag and rerun poses)

Same region (the whole clean reference cloud; independent of any evaluated pose) and the same query
sample.  Absolute counts on both sides:

  1. reference points covered and patch-unsupported points, both arms
  2. points C3 adds over R -- total, and the novel subset outside the base support -- each split
     into supported / unsupported
  3. points R has and C3 does not -- total and novel, same split
  4. frames, missing, matched

Criterion, declared before the numbers are read: the repair is supported as a net benefit only if
the novel added subset has clearly more supported than unsupported points AND the total added
unsupported fraction is not higher than R's own.  Otherwise the result is "the same-frame
comparison does not support a net benefit".  No region or frame-set retry.

    python3 -B docs/review_20261109_bbc3dcb/run_raw_vs_repaired.py
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

RESULT_JSON = os.path.join(_HERE, "raw_vs_repaired_results.json")
CRITERION = ("supported_novel > unsupported_novel AND added_unsupported_fraction <= "
             "R_unsupported_fraction")


def main():
    sha = {r: V._sha_file(p) for r, p in
           (("injected_scans", R.INJ_SCANS), ("injected_poses", R.INJ_POSES),
            ("clean_scans_proxy_only", R.CLN_SCANS), ("clean_poses_proxy_only", R.CLN_POSES))}
    inj_scans, _ = V.load_scans(R.INJ_SCANS, sha["injected_scans"])
    cln_scans, _ = V.load_scans(R.CLN_SCANS, sha["clean_scans_proxy_only"])
    inj_kfs, _ = V.pair_keyframes(inj_scans, V.load_poses(R.INJ_POSES))
    cln_kfs, _ = V.pair_keyframes(cln_scans, V.load_poses(R.CLN_POSES))
    _onset, _end, _fc, _nd, _nc = V.detect_onset(cln_scans, inj_scans)

    m0 = json.load(open(os.path.join(_REPO, "docs", "milestone_m0_keys.json"), encoding="utf-8"))
    ns_all = R.load_scan_ns(R.INJ_SCANS, sha["injected_scans"])
    pos = np.searchsorted(ns_all, np.asarray([round(k["ts"] * 1e9) for k in inj_kfs],
                                             dtype=np.int64))
    kf_ns = []
    for t, j in zip([k["ts"] for k in inj_kfs], pos):
        cand = [c for c in (j - 1, j) if 0 <= c < len(ns_all)]
        kf_ns.append(int(ns_all[min(cand, key=lambda c: abs(ns_all[c] / 1e9 - t))]))
    kf_ns = np.asarray(kf_ns, dtype=np.int64)
    by_ns = {int(n): i for i, n in enumerate(kf_ns)}
    keys = [by_ns[int(n)] for n in m0["primary_scan_set"]["timestamps_ns"]]
    prefix = [by_ns[int(n)] for n in m0["healthy_prefix"]["timestamps_ns"]]

    _ts_of = lambda i: inj_kfs[i]["ts"]
    cln_ts = np.asarray([k["ts"] for k in cln_kfs])
    cln_xyz = np.asarray([k["T"][:3, 3] for k in cln_kfs])
    host_poses, _ = R.pose_lookup(V.load_poses(R.INJ_POSES), prefix + keys, _ts_of)
    f_sha = V._sha_file(R.FILTERED_BAG)
    f_scans, _ = V.load_scans(R.FILTERED_BAG, f_sha)
    by_stamp = {round(t, 6): p for t, p in f_scans}
    c3_poses, _ = R.pose_lookup(V.load_poses(R.RERUN_BAG), prefix + keys, _ts_of)

    def _align(poses, ids):
        use = [i for i in ids if i in poses]
        _mt, mi, mc = V.associate(np.asarray([inj_kfs[i]["ts"] for i in use]),
                                  np.asarray([poses[i][:3, 3] for i in use]), cln_ts, cln_xyz)
        return V.umeyama(mi, mc)

    R_h, t_h = _align(host_poses, prefix)
    R_c, t_c = _align(c3_poses, prefix)

    # ---- the fixed frame set: keys with BOTH a filtered scan and a re-run pose -----------
    frames = [i for i in keys
              if i in c3_poses and round(inj_kfs[i]["ts"], 6) in by_stamp
              and len(by_stamp[round(inj_kfs[i]["ts"], 6)]) > 0]
    missing = [int(i) for i in keys if i not in frames]
    print(f"[] fixed frame set: {len(frames)} of {len(keys)} keys (missing {len(missing)})")

    def _map(ids, poses, filtered):
        out = []
        for i in ids:
            body = by_stamp[round(inj_kfs[i]["ts"], 6)] if filtered else inj_kfs[i]["pts"]
            w = body @ poses[i][:3, :3].T + poses[i][:3, 3]
            if len(w) > V.KF_CAP:
                w = w[:: max(1, len(w) // V.KF_CAP)][:V.KF_CAP]
            out.append(w)
        return np.vstack(out)

    r_pts = _map(frames, host_poses, False) @ R_h.T + t_h
    c3_pts = _map(frames, c3_poses, True) @ R_c.T + t_c
    base_pts, _ = (lambda o: (o, None))(_map(prefix, host_poses, False) @ R_h.T + t_h)
    print(f"[] maps: R {len(r_pts)} pts, C3 {len(c3_pts)} pts, base {len(base_pts)} pts")

    proxy = np.vstack([V.world_pts(k) for k in cln_kfs])
    proxy_tree = cKDTree(proxy)
    roi = proxy                                   # whole reference cloud, pose-independent

    def _arm(pts):
        tree = cKDTree(pts)
        d, _ = tree.query(roi, k=1, distance_upper_bound=R.R_NN)
        covered = np.isfinite(d)
        bm = R.bounded_metrics(pts, proxy_tree, proxy)
        uns = int(round(bm["patch"]["unsupported_fraction"] * len(pts)))
        return {"map_points": int(len(pts)),
                "proxy_covered": int(covered.sum()),
                "proxy_coverage_fraction": float(covered.mean()),
                "patch_unsupported_points": uns,
                "patch_unsupported_fraction": float(uns / len(pts)),
                "patch_median_m": bm["patch"]["median_m"]}, tree

    s_r, r_tree = _arm(r_pts)
    s_c3, c3_tree = _arm(c3_pts)

    base_tree = cKDTree(base_pts)

    def _split(subset, tag):
        if not len(subset):
            return {"n": 0, "supported": 0, "unsupported": 0, "supported_fraction": None,
                    "median_m": None}
        bm = R.bounded_metrics(subset, proxy_tree, proxy)
        uns = int(round(bm["patch"]["unsupported_fraction"] * len(subset)))
        out = base_tree.query(subset, k=1, distance_upper_bound=R.R_NN)[0]
        novel = ~np.isfinite(out)
        return {"n": int(len(subset)), "supported": int(len(subset) - uns),
                "unsupported": uns,
                "supported_fraction": float((len(subset) - uns) / len(subset)),
                "median_m": bm["patch"]["median_m"], "novel_outside_base": int(novel.sum())}

    # 2. what C3 adds over R
    d_add, _ = r_tree.query(c3_pts, k=1, distance_upper_bound=R.R_NN)
    added = c3_pts[~np.isfinite(d_add)]
    added_novel = added[~np.isfinite(base_tree.query(added, k=1,
                                                    distance_upper_bound=R.R_NN)[0])]
    # 3. what R has and C3 does not
    d_lost, _ = c3_tree.query(r_pts, k=1, distance_upper_bound=R.R_NN)
    lost = r_pts[~np.isfinite(d_lost)]
    lost_novel = lost[~np.isfinite(base_tree.query(lost, k=1,
                                                  distance_upper_bound=R.R_NN)[0])]

    split_added, split_added_novel = _split(added, "added"), _split(added_novel, "added_novel")
    split_lost, split_lost_novel = _split(lost, "lost"), _split(lost_novel, "lost_novel")

    cond_a = split_added_novel["supported"] > split_added_novel["unsupported"]
    frac_added_unsup = (split_added["unsupported"] / split_added["n"]) if split_added["n"] else None
    cond_b = (frac_added_unsup is not None
              and frac_added_unsup <= s_r["patch_unsupported_fraction"] + 1e-12)
    verdict = ("REPAIR_BENEFIT_SUPPORTED" if (cond_a and cond_b)
               else "SAME_FRAME_COMPARISON_DOES_NOT_SUPPORT_NET_BENEFIT")

    # ---- trajectory on the same fixed population, against GT ------------------------------
    from slam_recovery.experiments.evaluation import load_tum_trajectory_se3, \
        associate_trajectories
    start_ns = int(m0["injection_window"]["start_ns"])
    ts_gt, xyz_gt, _ = load_tum_trajectory_se3("/home/R26534/M2DGR/GT/hall_01.txt")
    # One frozen clean-world -> GT transform, estimated on pre-onset clean keyframes.
    cpre = cln_ts < start_ns * 1e-9
    mtcg, mecg, mgcg = associate_trajectories(cln_ts[cpre], cln_xyz[cpre], ts_gt, xyz_gt, 0.05)
    if len(mtcg) >= 10:
        R_cg, t_cg = V.umeyama(mecg, mgcg)
        clean_to_gt = {"matched": int(len(mtcg)),
                       "residual_rmse_m": float(np.sqrt(np.mean(
                           np.sum((mecg @ R_cg.T + t_cg - mgcg) ** 2, axis=1))))}
    else:
        R_cg = t_cg = None
        clean_to_gt = {"matched": int(len(mtcg)), "status": "TOO_FEW"}

    def _trajectory(poses, R_p, t_p):
        ids = [i for i in frames if i in poses]
        ts = np.asarray([inj_kfs[i]["ts"] for i in ids])
        xyz = np.asarray([poses[i][:3, 3] for i in ids])
        mt, me, mg = associate_trajectories(ts, xyz, ts_gt, xyz_gt, 0.05)
        rec = {"frames_scored": len(ids), "gt_matched": int(len(mt))}
        if len(mt) < 10:
            rec["status"] = "TOO_FEW_GT"
            return rec
        Ru, tu = V.umeyama(me, mg)
        err = np.linalg.norm(me @ Ru.T + tu - mg, axis=1)
        rec["ate_full_alignment_diagnostic_m"] = float(np.sqrt(np.mean(err ** 2)))
        rec["ate_full_alignment_max_m"] = float(err.max())
        if R_cg is not None:
            in_gt = (me @ R_p.T + t_p) @ R_cg.T + t_cg
            e2 = np.linalg.norm(in_gt - mg, axis=1)
            rec["ate_frozen_prefix_protocol_m"] = float(np.sqrt(np.mean(e2 ** 2)))
        else:
            rec["ate_frozen_prefix_protocol_m"] = None
        return rec

    trajectory = {"R": _trajectory(host_poses, R_h, t_h),
                  "C3": _trajectory(c3_poses, R_c, t_c)}

    res = {
        "protocol": "same-frame raw/native vs repaired, fixed frame set",
        "time_sync": {"rule": "nearest pose within 75 ms; bracketing interpolation",
                      "frame_stamps_from": "injected scan header (ns)"},
        "inputs": {"injected_scans": {"path": R.INJ_SCANS, "sha256": sha["injected_scans"]},
                   "injected_poses": {"path": R.INJ_POSES, "sha256": sha["injected_poses"]},
                   "clean_scans": {"path": R.CLN_SCANS, "sha256": sha["clean_scans_proxy_only"]},
                   "clean_poses": {"path": R.CLN_POSES, "sha256": sha["clean_poses_proxy_only"]},
                   "filtered_scans": {"path": R.FILTERED_BAG, "sha256": f_sha},
                   "rerun_poses": {"path": R.RERUN_BAG, "sha256": V._sha_file(R.RERUN_BAG)}},
        "clean_to_gt": clean_to_gt,
        "trajectory": trajectory,
        "frame_set": {"definition": "keys whose repaired arm has both a filtered scan and a "
                                    "re-run pose",
                      "n_frames": len(frames), "n_keys": len(keys),
                      "missing_ids": missing,
                      "ns_sha256": hashlib.sha256(",".join(
                          str(int(kf_ns[i])) for i in sorted(frames)).encode()).hexdigest()},
        "roi": {"definition": "the whole clean reference cloud; independent of evaluated poses",
                "n_points": int(len(roi)),
                "reference_sha256": hashlib.sha256(proxy.astype("<f8").tobytes()).hexdigest()},
        "arms": {"R": {"label": "RAW_NATIVE", **s_r},
                 "C3": {"label": "OFFLINE_NATIVE_REESTIMATION", **s_c3}},
        "added_by_C3": {"total": split_added, "novel_outside_base": split_added_novel},
        "lost_from_R": {"total": split_lost, "novel_outside_base": split_lost_novel},
        "criterion": {"declared": CRITERION,
                      "novel_added_supported_gt_unsupported": bool(cond_a),
                      "added_unsupported_fraction": frac_added_unsup,
                      "R_unsupported_fraction": s_r["patch_unsupported_fraction"],
                      "added_unsup_not_above_R": bool(cond_b),
                      "verdict": verdict},
        "notes": ["The proxy is the clean run's map, not a GT surface.",
                  "Both arms use the same frames, so the trajectory-extent confound is removed.",
                  "Absolute unsupported counts are not comparable across arms of different size; "
                  "the pre-declared criterion is used instead.",
                  "Trajectory is evaluated on the same 400-frame population, but GT covers 252 of "
                  "them; ATE is therefore a 252-frame diagnostic, not a 400-frame number.",
                  "ate_frozen_prefix_protocol_m composes the prefix alignment with one frozen "
                  "clean->GT transform estimated on 77 pre-onset clean keyframes (0.085 m residual).",
                  "C3 is OFFLINE_NATIVE_REESTIMATION, not a deployable loop."],
    }
    with open(RESULT_JSON, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=float)

    print(f"[] R : {s_r['map_points']} pts, cover {s_r['proxy_covered']} "
          f"({s_r['proxy_coverage_fraction']:.4f}), unsup {s_r['patch_unsupported_points']} "
          f"({s_r['patch_unsupported_fraction']:.4f})")
    print(f"[] C3: {s_c3['map_points']} pts, cover {s_c3['proxy_covered']} "
          f"({s_c3['proxy_coverage_fraction']:.4f}), unsup {s_c3['patch_unsupported_points']} "
          f"({s_c3['patch_unsupported_fraction']:.4f})")
    print(f"[] added {split_added['n']} (sup {split_added['supported']} / unsup "
          f"{split_added['unsupported']}); novel {split_added_novel['n']} "
          f"(sup {split_added_novel['supported']} / unsup {split_added_novel['unsupported']})")
    print(f"[] lost  {split_lost['n']} (sup {split_lost['supported']} / unsup "
          f"{split_lost['unsupported']}); novel {split_lost_novel['n']} "
          f"(sup {split_lost_novel['supported']} / unsup {split_lost_novel['unsupported']})")
    print(f"[] criterion: novel sup>unsup={cond_a}, added unsup {frac_added_unsup} vs R "
          f"{s_r['patch_unsupported_fraction']:.4f} -> {verdict}")
    print(f"saved {RESULT_JSON}")


if __name__ == "__main__":
    main()
