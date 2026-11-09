#!/usr/bin/env python3
"""M3: same-region net correct geometry, quarantine-only (Q) versus real repair (C3).

Protocol: docs/MILESTONE_fixed_input_repair.md @ 8704370, fixed before results existed.

  Q   the pre-onset trusted map only; no post-onset frame is written
  C3  the repository filter + the FAST-LIVO2 re-run on the filtered bag

Both arms are scored on the SAME region and the SAME query sample, using the bounded metric already
used elsewhere (NN cap 0.5 m; patch radius 0.30 m, plane RMS 0.02 m).  The reference is the clean
run's map -- a proxy, not a GT surface -- so the result is a conditional same-region comparison and
nothing here is a deployment or independent-GT claim.

Region.  "Common support of both arms" is realised as: proxy points within REGION_RADIUS_M of at
least one pose of Q and at least one pose of C3, i.e. the part of the scene both trajectories can
observe.  It cannot mean "supported by both maps": that set makes both coverage fractions 100 % by
construction.  The other two candidate definitions are reported alongside so the choice is visible.

Reported as absolute counts on both sides, never as one mixed ratio:
  1. proxy points covered by each arm (NN <= 0.5 m) and the coverage fraction
  2. map points unsupported by the bounded patch test, absolute and as a fraction
  3. what C3 adds over Q: newly covered proxy points, and map points Q does not have, split into
     supported / unsupported
  4. frames written and missing per arm

    python3 -B docs/review_20261109_bbc3dcb/run_m3_same_region.py
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

RESULT_JSON = os.path.join(_HERE, "m3_same_region_results.json")
REGION_JSON = os.path.join(_HERE, "m3_region_export.json")
REGION_RADIUS_M = 10.0
SENSITIVITY_RADII = (5.0, 15.0)


def _list_hash(values):
    return hashlib.sha256(",".join(str(int(v)) for v in sorted(values)).encode()).hexdigest()


def main():
    sha = {r: V._sha_file(p) for r, p in
           (("injected_scans", R.INJ_SCANS), ("injected_poses", R.INJ_POSES),
            ("clean_scans_proxy_only", R.CLN_SCANS), ("clean_poses_proxy_only", R.CLN_POSES))}
    inj_scans, _lay = V.load_scans(R.INJ_SCANS, sha["injected_scans"])
    cln_scans, _ = V.load_scans(R.CLN_SCANS, sha["clean_scans_proxy_only"])
    inj_kfs, _ = V.pair_keyframes(inj_scans, V.load_poses(R.INJ_POSES))
    cln_kfs, _ = V.pair_keyframes(cln_scans, V.load_poses(R.CLN_POSES))
    onset_abs, end_abs, _fc, _nd, _nc = V.detect_onset(cln_scans, inj_scans)

    # ---- frozen M0 keys (integer ns), exactly as in the C0-C3 measurement -----------------
    m0 = json.load(open(os.path.join(_REPO, "docs", "milestone_m0_keys.json"), encoding="utf-8"))
    ns_all = R.load_scan_ns(R.INJ_SCANS, sha["injected_scans"])
    pos = np.searchsorted(ns_all, np.asarray([round(k["ts"] * 1e9) for k in inj_kfs], dtype=np.int64))
    kf_ns = []
    for t, j in zip([k["ts"] for k in inj_kfs], pos):
        cand = [c for c in (j - 1, j) if 0 <= c < len(ns_all)]
        kf_ns.append(int(ns_all[min(cand, key=lambda c: abs(ns_all[c] / 1e9 - t))]))
    kf_ns = np.asarray(kf_ns, dtype=np.int64)
    by_ns = {int(n): i for i, n in enumerate(kf_ns)}
    keys = [by_ns[int(n)] for n in m0["primary_scan_set"]["timestamps_ns"]]
    prefix = [by_ns[int(n)] for n in m0["healthy_prefix"]["timestamps_ns"]]
    start_ns = int(m0["injection_window"]["start_ns"])
    end_ns = int(m0["injection_window"]["end_ns"])

    # ---- frames, poses, alignment ---------------------------------------------------------
    _ts_of = lambda i: inj_kfs[i]["ts"]
    cln_ts = np.asarray([k["ts"] for k in cln_kfs])
    cln_xyz = np.asarray([k["T"][:3, 3] for k in cln_kfs])

    host_poses, _ = R.pose_lookup(V.load_poses(R.INJ_POSES), prefix + keys, _ts_of)

    def _align(poses, ids):
        use = [i for i in ids if i in poses]
        _mt, mi, mc = V.associate(np.asarray([inj_kfs[i]["ts"] for i in use]),
                                  np.asarray([poses[i][:3, 3] for i in use]), cln_ts, cln_xyz)
        return V.umeyama(mi, mc)

    R_q, t_q = _align(host_poses, prefix)

    c3_poses, c3_by_stamp = None, None
    if os.path.exists(R.RERUN_BAG) and os.path.exists(R.FILTERED_BAG):
        f_sha = V._sha_file(R.FILTERED_BAG)
        f_scans, _ = V.load_scans(R.FILTERED_BAG, f_sha)
        c3_by_stamp = {round(t, 6): p for t, p in f_scans}
        c3_poses, _st = R.pose_lookup(V.load_poses(R.RERUN_BAG), prefix + keys, _ts_of)
    if c3_poses is None:
        raise SystemExit("C3 arms unavailable: filtered bag or re-run poses missing")
    R_c, t_c = _align(c3_poses, prefix)

    def _map_points(ids, poses, c3=False, cap=250):
        out, missing = [], []
        for i in ids:
            if i not in poses:
                missing.append(int(i))
                continue
            body = c3_by_stamp.get(round(inj_kfs[i]["ts"], 6)) if c3 else inj_kfs[i]["pts"]
            if body is None or len(body) == 0:
                missing.append(int(i))
                continue
            w = body @ poses[i][:3, :3].T + poses[i][:3, 3]
            if len(w) > V.KF_CAP:
                w = w[:: max(1, len(w) // V.KF_CAP)][:V.KF_CAP]
            out.append(w)
        return (np.vstack(out) if out else np.zeros((0, 3))), missing

    q_pts, q_missing = _map_points(prefix, host_poses)
    q_pts = q_pts @ R_q.T + t_q
    c3_pts, c3_missing = _map_points(keys, c3_poses, c3=True)
    c3_pts = c3_pts @ R_c.T + t_c
    print(f"[] maps: Q {len(q_pts)} pts from {len(prefix) - len(q_missing)} frames; "
          f"C3 {len(c3_pts)} pts from {len(keys) - len(c3_missing)} frames")

    # ---- reference and region --------------------------------------------------------------
    proxy = np.vstack([V.world_pts(k) for k in cln_kfs])
    proxy_tree = cKDTree(proxy)

    q_pose_xyz = np.asarray([host_poses[i][:3, 3] for i in prefix if i in host_poses]) @ R_q.T + t_q
    c3_pose_xyz = np.asarray([c3_poses[i][:3, 3] for i in keys if i in c3_poses]) @ R_c.T + t_c

    def _region(radius):
        dq, _ = cKDTree(q_pose_xyz).query(proxy, k=1, distance_upper_bound=radius)
        dc, _ = cKDTree(c3_pose_xyz).query(proxy, k=1, distance_upper_bound=radius)
        return np.flatnonzero(np.isfinite(dq) & np.isfinite(dc))

    region_idx = _region(REGION_RADIUS_M)
    region = proxy[region_idx]
    print(f"[] region (poses within {REGION_RADIUS_M} m of both arms): {len(region_idx)} proxy points")

    # exported BEFORE any metric is computed
    export = {
        "protocol": "docs/MILESTONE_fixed_input_repair.md @ 8704370",
        "region_definition": (f"proxy points with NN <= {REGION_RADIUS_M} m to at least one pose of "
                              f"each arm (observability, not map support)"),
        "why_not_map_support": ("the intersection of the two maps' support makes both coverage "
                                "fractions 100 % by construction"),
        "n_region_points": int(len(region_idx)),
        "region_index_sha256": hashlib.sha256(region_idx.astype("<i8").tobytes()).hexdigest(),
        "region_aabb_min": region.min(axis=0).tolist() if len(region) else None,
        "region_aabb_max": region.max(axis=0).tolist() if len(region) else None,
        "q_keys_ns_sha256": _list_hash([int(kf_ns[i]) for i in prefix]),
        "c3_keys_ns_sha256": _list_hash([int(kf_ns[i]) for i in keys]),
        "q_frames": len(prefix), "c3_frames": len(keys),
        "sensitivity_region_sizes": {f"{r}m": int(len(_region(r))) for r in SENSITIVITY_RADII},
        "inputs_sha256": sha,
    }
    with open(REGION_JSON, "w", encoding="utf-8") as fh:
        json.dump(export, fh, indent=1)
    print(f"[] region exported: sha {export['region_index_sha256'][:16]}")

    # ---- metric 1: proxy coverage by each arm ----------------------------------------------
    q_tree = cKDTree(q_pts)
    c3_tree = cKDTree(c3_pts)
    d_q, _ = q_tree.query(region, k=1, distance_upper_bound=R.R_NN)
    d_c3, _ = c3_tree.query(region, k=1, distance_upper_bound=R.R_NN)
    cov_q = np.isfinite(d_q)
    cov_c3 = np.isfinite(d_c3)

    # Literal reading check: if "common support" meant points supported by both maps, the region
    # would be exactly this set and both coverage fractions would be 100 % by construction.
    both_supported = int((cov_q & cov_c3).sum())

    # ---- metric 2: bounded patch support of each arm's map --------------------------------
    def _support(pts):
        bm = R.bounded_metrics(pts, proxy_tree, proxy)
        unsupported = int(round(bm["patch"]["unsupported_fraction"] * len(pts)))
        return bm, unsupported, len(pts)

    bm_q, uns_q, n_q = _support(q_pts)
    bm_c3, uns_c3, n_c3 = _support(c3_pts)

    # ---- metric 3: what C3 adds ------------------------------------------------------------
    new_proxy = region_idx[cov_c3 & ~cov_q]
    d_new, _ = q_tree.query(c3_pts, k=1, distance_upper_bound=R.R_NN)
    novel = ~np.isfinite(d_new)          # C3 map points with nothing from Q within the cap
    novel_pts = c3_pts[novel]
    bm_novel, uns_novel, n_novel = (_support(novel_pts) if len(novel_pts)
                                    else ({"patch": {"unsupported_fraction": None}}, 0, 0))

    res = {
        "protocol": export["protocol"],
        "region": {"definition": export["region_definition"],
                   "n_points": int(len(region_idx)),
                   "index_sha256": export["region_index_sha256"]},
        "arms": {
            "Q": {"label": "QUARANTINE_ONLY",
                  "frames_declared": len(prefix), "frames_written": len(prefix) - len(q_missing),
                  "missing_frame_ids": q_missing,
                  "map_points": int(n_q),
                  "proxy_covered": int(cov_q.sum()),
                  "proxy_coverage_fraction": float(cov_q.mean()),
                  "patch_unsupported_points": int(uns_q),
                  "patch_unsupported_fraction": float(uns_q / n_q) if n_q else None,
                  "patch_median_m": bm_q["patch"]["median_m"]},
            "C3": {"label": "OFFLINE_NATIVE_REESTIMATION",
                   "frames_declared": len(keys), "frames_written": len(keys) - len(c3_missing),
                   "missing_frame_ids": c3_missing,
                   "map_points": int(n_c3),
                   "proxy_covered": int(cov_c3.sum()),
                   "proxy_coverage_fraction": float(cov_c3.mean()),
                   "patch_unsupported_points": int(uns_c3),
                   "patch_unsupported_fraction": float(uns_c3 / n_c3) if n_c3 else None,
                   "patch_median_m": bm_c3["patch"]["median_m"]},
        },
        "added_by_C3": {
            "proxy_points_newly_covered": int(len(new_proxy)),
            "proxy_points_newly_covered_fraction_of_region": float(len(new_proxy) / len(region)),
            "map_points_not_in_Q_within_cap": int(n_novel),
            "map_points_not_in_Q_supported": int(n_novel - uns_novel),
            "map_points_not_in_Q_unsupported": int(uns_novel),
            "map_points_not_in_Q_supported_fraction": (float((n_novel - uns_novel) / n_novel)
                                                       if n_novel else None),
            "novel_patch_median_m": bm_novel["patch"].get("median_m"),
            "literal_both_supported_region_points": both_supported,
            "literal_reading_note": ("restricting the region to points BOTH maps support makes "
                                     "coverage 100 % for both arms by construction, which is why "
                                     "observability is used instead"),
        },
        "notes": [
            "The proxy is the clean run's map, not a GT surface.",
            "Conditional same-region comparison; not a deployment claim and not an independent-GT "
            "benefit.",
            "Counts on both sides are reported separately; no mixed ratio is formed.",
        ],
    }
    with open(RESULT_JSON, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=float)

    a = res["arms"]
    print(f"[] Q : frames {a['Q']['frames_written']}/{a['Q']['frames_declared']}  "
          f"map {a['Q']['map_points']}  covered {a['Q']['proxy_covered']} "
          f"({a['Q']['proxy_coverage_fraction']:.4f})  unsupported {a['Q']['patch_unsupported_points']} "
          f"({a['Q']['patch_unsupported_fraction']:.4f})")
    print(f"[] C3: frames {a['C3']['frames_written']}/{a['C3']['frames_declared']}  "
          f"map {a['C3']['map_points']}  covered {a['C3']['proxy_covered']} "
          f"({a['C3']['proxy_coverage_fraction']:.4f})  unsupported {a['C3']['patch_unsupported_points']} "
          f"({a['C3']['patch_unsupported_fraction']:.4f})")
    ad = res["added_by_C3"]
    print(f"[] C3 adds: {ad['proxy_points_newly_covered']} proxy pts "
          f"({ad['proxy_points_newly_covered_fraction_of_region']:.4f} of region), "
          f"{ad['map_points_not_in_Q_within_cap']} novel map pts "
          f"({ad['map_points_not_in_Q_supported']} supported / "
          f"{ad['map_points_not_in_Q_unsupported']} unsupported)")
    print(f"saved {RESULT_JSON}")


if __name__ == "__main__":
    main()
