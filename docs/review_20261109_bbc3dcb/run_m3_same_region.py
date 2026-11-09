#!/usr/bin/env python3
"""M3 (recomputed): same-region net correct geometry, quarantine-only versus the real repair.

Protocol: docs/MILESTONE_fixed_input_repair.md.  Recomputed after review found two substantive
defects in the first version:

  1. the C3 arm did not include the trusted pre-onset base, so Q (base only) and C3 (repair only)
     were not the two maps the system actually holds.  C3 is now base + repaired post-onset
     frames, with the base being exactly the same points Q is made of;
  2. the region was defined by "within 10 m of both arms' poses", i.e. by the evaluated poses.
     The primary region is now the whole clean reference cloud, which depends on nothing but the
     reference.  The base-supported subset is reported as a sensitivity, not as the answer.

Everything is recomputed from existing outputs: base, filtered bag and re-run poses are all on
disk, no host run.

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


def _list_hash(values):
    return hashlib.sha256(",".join(str(int(v)) for v in sorted(values)).encode()).hexdigest()


def _summary(pts, region, region_tree=None):
    """Coverage of `region` by `pts`, plus the bounded patch support of `pts` itself."""
    tree = cKDTree(pts)
    d, _ = tree.query(region, k=1, distance_upper_bound=R.R_NN)
    covered = np.isfinite(d)
    bm = R.bounded_metrics(pts, _summary.proxy_tree, _summary.proxy)
    uns = int(round(bm["patch"]["unsupported_fraction"] * len(pts)))
    return {
        "map_points": int(len(pts)),
        "proxy_covered": int(covered.sum()),
        "proxy_coverage_fraction": float(covered.mean()),
        "patch_unsupported_points": uns,
        "patch_unsupported_fraction": float(uns / len(pts)) if len(pts) else None,
        "patch_median_m": bm["patch"]["median_m"],
    }, covered


def main():
    sha = {r: V._sha_file(p) for r, p in
           (("injected_scans", R.INJ_SCANS), ("injected_poses", R.INJ_POSES),
            ("clean_scans_proxy_only", R.CLN_SCANS), ("clean_poses_proxy_only", R.CLN_POSES))}
    inj_scans, _ = V.load_scans(R.INJ_SCANS, sha["injected_scans"])
    cln_scans, _ = V.load_scans(R.CLN_SCANS, sha["clean_scans_proxy_only"])
    inj_kfs, _ = V.pair_keyframes(inj_scans, V.load_poses(R.INJ_POSES))
    cln_kfs, _ = V.pair_keyframes(cln_scans, V.load_poses(R.CLN_POSES))
    onset_abs, _end, _fc, _nd, _nc = V.detect_onset(cln_scans, inj_scans)

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

    def _align(poses, ids):
        use = [i for i in ids if i in poses]
        _mt, mi, mc = V.associate(np.asarray([inj_kfs[i]["ts"] for i in use]),
                                  np.asarray([poses[i][:3, 3] for i in use]), cln_ts, cln_xyz)
        return V.umeyama(mi, mc)

    R_q, t_q = _align(host_poses, prefix)

    f_sha = V._sha_file(R.FILTERED_BAG)
    f_scans, _ = V.load_scans(R.FILTERED_BAG, f_sha)
    c3_by_stamp = {round(t, 6): p for t, p in f_scans}
    c3_poses, _ = R.pose_lookup(V.load_poses(R.RERUN_BAG), prefix + keys, _ts_of)
    R_c, t_c = _align(c3_poses, prefix)

    def _map_points(ids, poses, filtered=False):
        out, missing = [], []
        for i in ids:
            if i not in poses:
                missing.append(int(i))
                continue
            body = c3_by_stamp.get(round(inj_kfs[i]["ts"], 6)) if filtered else inj_kfs[i]["pts"]
            if body is None or len(body) == 0:
                missing.append(int(i))
                continue
            w = body @ poses[i][:3, :3].T + poses[i][:3, 3]
            if len(w) > V.KF_CAP:
                w = w[:: max(1, len(w) // V.KF_CAP)][:V.KF_CAP]
            out.append(w)
        return (np.vstack(out) if out else np.zeros((0, 3))), missing

    # ---- arms ------------------------------------------------------------------------------
    base_body, base_missing = _map_points(prefix, host_poses)
    base_pts = base_body @ R_q.T + t_q                 # Q is exactly this
    repair_body, repair_missing = _map_points(keys, c3_poses, filtered=True)
    repair_pts = repair_body @ R_c.T + t_c

    q_pts = base_pts
    c3_pts = np.vstack([base_pts, repair_pts])         # the map the system actually holds
    print(f"[] arms: Q {len(q_pts)} = base; C3 {len(c3_pts)} = base {len(base_pts)} + repair "
          f"{len(repair_pts)}")

    proxy = np.vstack([V.world_pts(k) for k in cln_kfs])
    proxy_tree = cKDTree(proxy)
    _summary.proxy, _summary.proxy_tree = proxy, proxy_tree

    # ---- regions: fixed, independent of the evaluated poses ---------------------------------
    roi_all = np.arange(len(proxy))                     # whole reference cloud
    d_base, _ = cKDTree(base_pts).query(proxy, k=1, distance_upper_bound=R.R_NN)
    roi_base = np.flatnonzero(np.isfinite(d_base))      # the shared base's support

    export = {
        "protocol": "docs/MILESTONE_fixed_input_repair.md (M3, recomputed)",
        "arms": {
            "Q": "trusted pre-onset base only (host poses, pre-onset keyframes)",
            "C3": "the same base points + repaired post-onset frames (repository filter + "
                  "FAST-LIVO2 re-run), i.e. the map the system actually holds",
        },
        "primary_roi": {
            "definition": "the whole clean reference cloud; depends on the reference only, not on "
                          "any evaluated pose",
            "n_points": int(len(roi_all)),
            "index_sha256": hashlib.sha256(np.arange(len(proxy), dtype="<i8").tobytes()).hexdigest(),
            "reference_sha256": hashlib.sha256(proxy.astype("<f8").tobytes()).hexdigest(),
        },
        "sensitivity_roi": {
            "definition": "reference points within 0.5 m of the shared base map (identical in both "
                          "arms, so it is a common region rather than a pose-dependent one)",
            "n_points": int(len(roi_base)),
            "index_sha256": hashlib.sha256(roi_base.astype("<i8").tobytes()).hexdigest(),
        },
        "key_lists": {"q_ns_sha256": _list_hash([int(kf_ns[i]) for i in prefix]),
                      "c3_ns_sha256": _list_hash([int(kf_ns[i]) for i in keys])},
        "inputs_sha256": sha,
        "filtered_bag_sha256": f_sha,
    }
    with open(REGION_JSON, "w", encoding="utf-8") as fh:
        json.dump(export, fh, indent=1)
    print(f"[] ROI: primary {len(roi_all)} (whole proxy), sensitivity {len(roi_base)} (base support)")

    def _run(region_idx):
        region = proxy[region_idx]
        s_q, cov_q = _summary(q_pts, region)
        s_c3, cov_c3 = _summary(c3_pts, region)
        new_proxy = int((cov_c3 & ~cov_q).sum())
        q_tree = cKDTree(q_pts)
        d_new, _ = q_tree.query(c3_pts, k=1, distance_upper_bound=R.R_NN)
        novel = ~np.isfinite(d_new)
        novel_pts = c3_pts[novel]
        if len(novel_pts):
            bm = R.bounded_metrics(novel_pts, proxy_tree, proxy)
            uns_novel = int(round(bm["patch"]["unsupported_fraction"] * len(novel_pts)))
            med_novel = bm["patch"]["median_m"]
        else:
            uns_novel, med_novel = 0, None
        return {
            "n_region_points": int(len(region_idx)),
            "Q": s_q,
            "C3": s_c3,
            "added_by_C3": {
                "proxy_points_newly_covered": new_proxy,
                "proxy_points_newly_covered_pct_of_region": 100.0 * new_proxy / len(region_idx),
                "map_points_not_in_Q": int(len(novel_pts)),
                "map_points_not_in_Q_supported": int(len(novel_pts) - uns_novel),
                "map_points_not_in_Q_unsupported": int(uns_novel),
                "map_points_not_in_Q_supported_fraction": (float((len(novel_pts) - uns_novel)
                                                                 / len(novel_pts))
                                                           if len(novel_pts) else None),
                "novel_patch_median_m": med_novel,
            },
        }

    res = {
        "protocol": export["protocol"],
        "arms": export["arms"],
        "primary_roi": export["primary_roi"],
        "sensitivity_roi": export["sensitivity_roi"],
        "key_lists": export["key_lists"],
        "primary": _run(roi_all),
        "sensitivity": _run(roi_base),
        "frames": {
            "Q": {"declared": len(prefix), "written": len(prefix) - len(base_missing),
                  "missing_ids": base_missing},
            "C3": {"declared_base": len(prefix), "declared_repair": len(keys),
                   "written": len(prefix) - len(base_missing) + len(keys) - len(repair_missing),
                   "missing_repair_ids": repair_missing},
        },
        "notes": [
            "The proxy is the clean run's map, not a GT surface.",
            "C3 contains the base by construction, so its coverage can only be >= Q's; the "
            "interesting quantities are the added coverage and the support of the added points.",
            "Absolute unsupported counts are not comparable between arms of different size; the "
            "comparable figures are the supported fraction of the added points and the added "
            "coverage in percentage points.",
            "Same-region conditional comparison, not a deployment claim or an independent-GT "
            "benefit.",
        ],
    }
    with open(RESULT_JSON, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=float)

    for tag in ("primary", "sensitivity"):
        b = res[tag]
        print(f"[] {tag} ROI ({b['n_region_points']} pts): "
              f"Q cov {b['Q']['proxy_covered']} ({b['Q']['proxy_coverage_fraction']:.4f}) "
              f"unsup {b['Q']['patch_unsupported_points']} ({b['Q']['patch_unsupported_fraction']:.4f}); "
              f"C3 cov {b['C3']['proxy_covered']} ({b['C3']['proxy_coverage_fraction']:.4f}) "
              f"unsup {b['C3']['patch_unsupported_points']} ({b['C3']['patch_unsupported_fraction']:.4f})")
        a = b["added_by_C3"]
        print(f"     C3 adds {a['proxy_points_newly_covered']} proxy pts "
              f"({a['proxy_points_newly_covered_pct_of_region']:.3f} pp), "
              f"{a['map_points_not_in_Q']} novel pts "
              f"({a['map_points_not_in_Q_supported']} sup / {a['map_points_not_in_Q_unsupported']} unsup)")
    print(f"saved {RESULT_JSON}")


if __name__ == "__main__":
    main()
