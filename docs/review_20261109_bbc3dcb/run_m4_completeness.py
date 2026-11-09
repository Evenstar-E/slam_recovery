#!/usr/bin/env python3
"""Frozen-446 service completeness and the healthy-region cost of the real filter.

Preregistered at docs/MILESTONE_fixed_input_repair.md (main 027804e).  Existing outputs only; no
new fault severity, no threshold change, no ROI or frame-set change.

  1. every one of the 46 keyframes without a pose, classified by the step that failed:
     filtered scan missing / pose stream gap / pairing rule says MISSING, plus whether it is
     recoverable from this run at all;
  2. the filter's removal on frames OUTSIDE the absolute injection window -- the healthy region
     cost.  The audit already reported zero; this recomputes it from the per-frame records and
     reports the distribution rather than the total;
  3. service completeness on the frozen 446 with the 46 missing frames recorded as missing and NOT
     dropped from the denominator, next to the older "denominator = 400 written frames" view.

Provenance: OFFLINE_NATIVE_REESTIMATION.  The reference surface is the clean run's map, a proxy,
not GT.

    python3 -B docs/review_20261109_bbc3dcb/run_m4_completeness.py
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_HERE))
for _p in (_HERE, _REPO):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import verify_four_arm_independent as V          # noqa: E402
import run_fixed_input_repair_c0c3 as R          # noqa: E402

RESULT_JSON = os.path.join(_HERE, "completeness_healthy_region_results.json")


def main():
    sha = {r: V._sha_file(p) for r, p in
           (("injected_scans", R.INJ_SCANS), ("injected_poses", R.INJ_POSES),
            ("clean_scans_proxy_only", R.CLN_SCANS), ("clean_poses_proxy_only", R.CLN_POSES))}
    inj_scans, _ = V.load_scans(R.INJ_SCANS, sha["injected_scans"])
    cln_scans, _ = V.load_scans(R.CLN_SCANS, sha["clean_scans_proxy_only"])
    inj_kfs, _ = V.pair_keyframes(inj_scans, V.load_poses(R.INJ_POSES))
    cln_kfs, _ = V.pair_keyframes(cln_scans, V.load_poses(R.CLN_POSES))
    _on, _end, _fc, _nd, _nc = V.detect_onset(cln_scans, inj_scans)

    m0 = json.load(open(os.path.join(_REPO, "docs", "milestone_m0_keys.json"), encoding="utf-8"))
    start_ns = int(m0["injection_window"]["start_ns"])
    end_ns = int(m0["injection_window"]["end_ns"])
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
    f_sha = V._sha_file(R.FILTERED_BAG)
    f_scans, _ = V.load_scans(R.FILTERED_BAG, f_sha)
    by_stamp = {round(t, 6): p for t, p in f_scans}
    c3_poses, _ = R.pose_lookup(V.load_poses(R.RERUN_BAG), prefix + keys, _ts_of)
    r_ts, _rx, _rq = V.load_poses(R.RERUN_BAG)

    # ---- 1. every missing frame, classified ------------------------------------------------
    missing = []
    for i in keys:
        if i in c3_poses:
            continue
        ts = inj_kfs[i]["ts"]
        has_scan = round(ts, 6) in by_stamp and len(by_stamp[round(ts, 6)]) > 0
        j = int(np.searchsorted(r_ts, ts))
        near = [k for k in (j - 1, j) if 0 <= k < len(r_ts)]
        best = min(near, key=lambda k: abs(r_ts[k] - ts)) if near else None
        dt_near = float(abs(r_ts[best] - ts)) if best is not None else None
        gap = float(r_ts[j] - r_ts[j - 1]) if 0 < j < len(r_ts) else None
        if not has_scan:
            cause = "FILTERED_SCAN_MISSING"
        elif best is None:
            cause = "POSE_STREAM_HAS_NO_NEIGHBOUR"
        elif dt_near is not None and dt_near <= R.POSE_NEAR_DT:
            cause = "UNEXPECTED (pose exists within the nearest rule)"
        elif gap is not None and gap <= R.POSE_MAX_GAP:
            cause = "UNEXPECTED (interpolatable gap)"
        else:
            cause = "PAIRING_RULE_MISSING (bracketing gap over the 75 ms limit)"
        # recoverability is two questions, not one
        if not has_scan:
            rec_frozen, rec_relax = False, False
            why = "no filtered scan at this stamp"
        elif dt_near is None or dt_near > 1.0:
            rec_frozen, rec_relax = False, False
            why = "the odometry stream has no message within 1.0 s; would need a re-run"
        else:
            rec_frozen = False
            rec_relax = gap is not None and gap <= 0.150
            why = (f"scan present; nearest pose {dt_near*1e3:.1f} ms, bracketing gap "
                   f"{gap*1e3:.1f} ms -- refused by the 75 ms interpolation limit. Not "
                   f"recoverable under the frozen protocol"
                   + ("; would be recoverable only by relaxing the gap limit, which the "
                      "protocol does not allow" if rec_relax else ""))
        missing.append({"id": int(i), "ns": int(kf_ns[i]), "ts": float(ts),
                        "has_filtered_scan": bool(has_scan),
                        "nearest_pose_dt_ms": None if dt_near is None else round(dt_near * 1e3, 3),
                        "bracketing_gap_ms": None if gap is None else round(gap * 1e3, 3),
                        "cause": cause,
                        "recoverable_under_frozen_protocol": bool(rec_frozen),
                        "recoverable_if_rule_relaxed": bool(rec_relax),
                        "recoverability": why})

    causes = {}
    for m in missing:
        causes[m["cause"]] = causes.get(m["cause"], 0) + 1
    if missing:
        _ts = sorted(m["ts"] for m in missing)
        gaps = np.diff(_ts)
        print(f"[] missing stamps span {_ts[0]:.3f}..{_ts[-1]:.3f}; "
              f"max inter-missing interval {gaps.max():.3f} s" if len(_ts) > 1 else "")

    segments = []
    if missing:
        _ts = sorted(m["ts"] for m in missing)
        lo = prev = _ts[0]
        for t in _ts[1:]:
            if t - prev > 1.0:
                segments.append([round(lo, 3), round(prev, 3)])
                lo = t
            prev = t
        segments.append([round(lo, 3), round(prev, 3)])
    print(f"[] missing frames: {len(missing)} of {len(keys)}; causes {causes}")

    # ---- 2. healthy-region cost ------------------------------------------------------------
    audit = json.load(open(os.path.join(_HERE, "fixed_input_repair_filter_audit.json"),
                           encoding="utf-8"))
    pf = audit["per_frame"]
    outside = [f for f in pf if not (start_ns <= f["ns"] <= end_ns)]
    inside = [f for f in pf if start_ns <= f["ns"] <= end_ns]
    o_removed = [f["n"] - f["n_kept"] for f in outside]
    o_frac = [(f["n"] - f["n_kept"]) / f["n"] if f["n"] else 0.0 for f in outside]
    nonzero = [f for f in outside if f["n"] - f["n_kept"] > 0]
    healthy = {
        "window_ns": [start_ns, end_ns],
        "frames_outside": len(outside),
        "points_outside": int(sum(f["n"] for f in outside)),
        "points_removed_outside": int(sum(o_removed)),
        "removal_fraction_outside": (float(sum(o_removed) / sum(f["n"] for f in outside))
                                     if outside else None),
        "frames_with_any_removal": len(nonzero),
        "frames_with_removal_gt_0.1pct": int(sum(1 for x in o_frac if x > 0.001)),
        "max_frame_removal_fraction": float(max(o_frac)) if o_frac else None,
        "max_frame_removed_points": int(max(o_removed)) if o_removed else None,
        "distribution_removed_points": {
            "min": int(min(o_removed)) if o_removed else None,
            "p50": float(np.percentile(o_removed, 50)) if o_removed else None,
            "p95": float(np.percentile(o_removed, 95)) if o_removed else None,
            "max": int(max(o_removed)) if o_removed else None},
        "nonzero_frames": [{"ns": f["ns"], "n": f["n"],
                            "removed": f["n"] - f["n_kept"]} for f in nonzero][:50],
        "in_window_for_contrast": {
            "frames": len(inside),
            "points": int(sum(f["n"] for f in inside)),
            "removed": int(sum(f["n"] - f["n_kept"] for f in inside)),
            "fraction": (float(sum(f["n"] - f["n_kept"] for f in inside)
                               / sum(f["n"] for f in inside)) if inside else None)},
        "independently_confirms_previous_claim": bool(len(nonzero) == 0),
    }
    print(f"[] healthy region: {len(outside)} frames, {healthy['points_outside']} points, "
          f"removed {healthy['points_removed_outside']} "
          f"({healthy['removal_fraction_outside']}); frames with any removal "
          f"{healthy['frames_with_any_removal']}")

    # ---- 3. service completeness: 446 declared, 400 written --------------------------------
    written = [i for i in keys if i in c3_poses and round(inj_kfs[i]["ts"], 6) in by_stamp]
    map_points = 250 * len(written)          # 250-point sidecar per written frame
    completeness = {
        "denominator_policy": ("frozen 446 is the denominator; a frame without output is MISSING "
                               "and is never removed from the count"),
        "declared_frames": len(keys),
        "frames_with_output": len(written),
        "frames_missing": len(missing),
        "completeness_446": len(written) / len(keys),
        "by_cause": causes,
        "old_400_denominator_view": {
            "what": "the previous reporting convention, denominator = surviving frames",
            "frames": len(written),
            "completeness": 1.0,
            "map_points_per_frame": 250.0},
        "frozen_446_denominator_view": {
            "what": "frozen denominator = all 446 declared frames",
            "frames": len(keys),
            "map_points_per_frame": map_points / len(keys),
            "missing_fraction": len(missing) / len(keys)},
        "map_points_written": map_points,
        "note": ("coverage and patch-unsupported are properties of the map and do not change with "
                 "the denominator; what changes is any per-frame rate, and those are reported "
                 "under both denominators"),
    }
    print(f"[] completeness: {len(written)}/{len(keys)} = "
          f"{100*len(written)/len(keys):.1f}%")

    res = {
        "provenance": "OFFLINE_NATIVE_REESTIMATION",
        "reference": "clean-run map (proxy), not GT",
        "inputs_sha256": sha,
        "filtered_bag_sha256": f_sha,
        "missing_frames": missing,
        "missing_by_cause": causes,
        "missing_segments_abs_sec": segments,
        "missing_recoverable_under_frozen": sum(1 for m in missing
                                                if m["recoverable_under_frozen_protocol"]),
        "missing_recoverable_if_relaxed": sum(1 for m in missing
                                              if m["recoverable_if_rule_relaxed"]),
        "healthy_region": healthy,
        "service_completeness": completeness,
    }
    with open(RESULT_JSON, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=float)
    print(f"saved {RESULT_JSON}")


if __name__ == "__main__":
    main()
