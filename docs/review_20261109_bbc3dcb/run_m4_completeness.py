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

import hashlib
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



def cloud_fingerprints(path):
    """{scan_ns: (message width, sha256 of the payload)} straight from the bag.

    `V.load_scans` keeps only 0.5-30 m points and caps the count, so its lengths are not the
    observation size; comparing them to `n_kept` invents a mismatch. The digest matters as much
    as the count: two runs can keep the same number of points from different rows.
    """
    out = {}
    with V.Reader(path) as r:
        conns = [c for c in r.connections if c.topic == V.SCAN_TOPIC]
        for conn, _t, raw in r.messages(connections=conns):
            m = V.TYPESTORE.deserialize_ros1(raw, conn.msgtype)
            payload = np.asarray(m.data, dtype=np.uint8).tobytes()
            ns = int(m.header.stamp.sec) * 10 ** 9 + int(m.header.stamp.nanosec)
            out[ns] = (int(m.width), hashlib.sha256(payload).hexdigest())
    return out


def classify_key(has_pose, scan_len, dt_near, gap, near_dt, max_gap):
    """One keyframe's status, as a pure function so it can be tested without a bag.

    `scan_len` is None when no scan message exists at the stamp, and 0 when the message is
    present but empty. Success is `pose AND nonempty observation` -- a frame with a pose but no
    usable scan is MISSING, not written.
    """
    has_scan = scan_len is not None and scan_len > 0
    if has_pose and has_scan:
        return {"ok": True, "reason": None, "reasons": [], "cause": None}

    reasons = []
    if not has_pose:
        reasons.append("NO_POSE")
    if scan_len is None:
        reasons.append("MISSING_SCAN")
    elif scan_len == 0:
        reasons.append("EMPTY_SCAN")

    if scan_len is None:
        cause = "FILTERED_SCAN_MISSING"
        reason = "NO_POSE" if not has_pose else "MISSING_SCAN"
    elif scan_len == 0:
        cause = "FILTERED_SCAN_EMPTY"
        reason = "NO_POSE" if not has_pose else "EMPTY_SCAN"
    elif not has_pose:
        if dt_near is None:
            cause, reason = "POSE_STREAM_HAS_NO_NEIGHBOUR", "UNKNOWN"
        elif dt_near <= near_dt:
            cause, reason = "UNEXPECTED (pose exists within the nearest rule)", "UNKNOWN"
        elif gap is not None and gap <= max_gap:
            cause, reason = "UNEXPECTED (interpolatable gap)", "UNKNOWN"
        else:
            cause = "PAIRING_RULE_MISSING (bracketing gap over the 75 ms limit)"
            reason = "PAIRING_RULE_MISSING"
    else:
        cause, reason = "UNKNOWN", "UNKNOWN"
    return {"ok": False, "reason": reason, "reasons": reasons, "cause": cause}


def describe_recoverability(scan_len, dt_near, gap):
    """(recoverable_frozen, recoverable_if_relaxed, explanation).

    `gap` is None whenever the pose stream has no bracketing pair, and the old inline f-string
    formatted it unconditionally -- a None there raised TypeError instead of reporting UNKNOWN.
    """
    if scan_len is None:
        return False, False, "no filtered scan at this stamp"
    if scan_len == 0:
        return False, False, "the filtered scan at this stamp is empty"
    if dt_near is None or dt_near > 1.0:
        return False, False, ("the odometry stream has no message within 1.0 s; would need a "
                              "re-run")
    rec_relax = gap is not None and gap <= 0.150
    gap_txt = "n/a (no bracketing pair)" if gap is None else f"{gap * 1e3:.1f} ms"
    why = (f"scan present; nearest pose {dt_near*1e3:.1f} ms, bracketing gap {gap_txt} -- "
           "refused by the 75 ms interpolation limit. Not recoverable under the frozen protocol"
           + ("; would be recoverable only by relaxing the gap limit, which the protocol does "
              "not allow" if rec_relax else ""))
    return False, rec_relax, why


def check_audit_binding(audit, src_sha, inj_path, fingerprints):
    """Tie a stored filter audit to THIS run's inputs, or call it stale.

    A per-frame audit is only evidence for the run whose bag it read. The bind is the source bag
    hash plus per-frame agreement between the audit's kept counts and the filtered clouds the
    script just loaded; anything else is STALE_AUDIT and must not be attached to this identity.
    """
    bad = []
    if audit.get("input") != inj_path:
        bad.append(f"audit input path {audit.get('input')} != {inj_path}")
    if audit.get("input_sha256") != src_sha:
        bad.append(f"audit input sha256 {str(audit.get('input_sha256'))[:16]} != {src_sha[:16]}")
    per = audit.get("per_frame", [])
    if not per:
        # An audit with no frames binds to nothing; an empty list is not agreement.
        return {"status": "UNVERIFIABLE", "problems": ["audit carries no per-frame records"],
                "audit_frames": 0, "audit_input_sha256": audit.get("input_sha256"),
                "current_input_sha256": src_sha}
    count_bad = hash_bad = 0
    for f in per:
        got = fingerprints.get(int(f["ns"]))
        if got is None or int(got[0]) != int(f["n_kept"]):
            count_bad += 1
            continue
        want = f.get("output_sha256") or f.get("kept_rows_sha256")
        if want is not None and got[1] != want:
            hash_bad += 1
    if count_bad:
        bad.append(f"{count_bad}/{len(per)} audit frames keep a different count than the bag")
    if hash_bad:
        bad.append(f"{hash_bad}/{len(per)} audit frames keep different rows than the bag")
    status = "BOUND" if not bad else "STALE_AUDIT"
    return {"status": status, "problems": bad, "audit_frames": len(per),
            "audit_input_sha256": audit.get("input_sha256"),
            "current_input_sha256": src_sha}



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
    fingerprints = cloud_fingerprints(R.FILTERED_BAG)
    c3_poses, _ = R.pose_lookup(V.load_poses(R.RERUN_BAG), prefix + keys, _ts_of)
    r_ts, _rx, _rq = V.load_poses(R.RERUN_BAG)

    # ---- 1. every missing frame, classified ------------------------------------------------
    # Success is pose AND nonempty observation. A key with a pose but no usable scan is MISSING
    # too: the old loop only walked keys without a pose, so that case was silently dropped.
    missing = []
    written = []
    for i in keys:
        ts = inj_kfs[i]["ts"]
        has_pose = i in c3_poses
        _fp = fingerprints.get(int(kf_ns[i]))
        scan_len = None if _fp is None else int(_fp[0])
        j = int(np.searchsorted(r_ts, ts))
        near = [k for k in (j - 1, j) if 0 <= k < len(r_ts)]
        best = min(near, key=lambda k: abs(r_ts[k] - ts)) if near else None
        dt_near = float(abs(r_ts[best] - ts)) if best is not None else None
        gap = float(r_ts[j] - r_ts[j - 1]) if 0 < j < len(r_ts) else None
        verdict = classify_key(has_pose, scan_len, dt_near, gap,
                               R.POSE_NEAR_DT, R.POSE_MAX_GAP)
        if verdict["ok"]:
            written.append(i)
            continue
        cause = verdict["cause"]
        # recoverability is two questions, not one
        rec_frozen, rec_relax, why = describe_recoverability(scan_len, dt_near, gap)
        missing.append({"id": int(i), "ns": int(kf_ns[i]), "ts": float(ts),
                        "has_pose": bool(has_pose),
                        "has_filtered_scan": bool(scan_len is not None and scan_len > 0),
                        "scan_points": None if scan_len is None else int(scan_len),
                        "nearest_pose_dt_ms": None if dt_near is None else round(dt_near * 1e3, 3),
                        "bracketing_gap_ms": None if gap is None else round(gap * 1e3, 3),
                        "cause": cause,
                        "reason": verdict["reason"],
                        "reasons": verdict["reasons"],
                        "recoverable_under_frozen_protocol": bool(rec_frozen),
                        "recoverable_if_rule_relaxed": bool(rec_relax),
                        "recoverability": why})

    causes = {}
    by_reason = {}
    for m in missing:
        causes[m["cause"]] = causes.get(m["cause"], 0) + 1
        by_reason[m["reason"]] = by_reason.get(m["reason"], 0) + 1
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
    print(f"[] missing frames: {len(missing)} of {len(keys)}; causes {causes}; "
          f"reasons {by_reason}")

    # ---- 2. healthy-region cost ------------------------------------------------------------
    audit = json.load(open(os.path.join(_HERE, "fixed_input_repair_filter_audit.json"),
                           encoding="utf-8"))
    # Tie the stored audit to THIS run before using a single number from it.
    binding = check_audit_binding(audit, sha["injected_scans"], R.INJ_SCANS, fingerprints)
    if binding["status"] != "BOUND":
        print(f"[] WARNING audit binding {binding['status']}: {binding['problems']}")
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
        "audit_binding": binding,
        "usable": binding["status"] == "BOUND",
    }
    if binding["status"] != "BOUND":
        healthy["warning"] = ("the stored filter audit does not describe this run's inputs; the "
                              "numbers above must not be attributed to this identity")
    print(f"[] healthy region: {len(outside)} frames, {healthy['points_outside']} points, "
          f"removed {healthy['points_removed_outside']} "
          f"({healthy['removal_fraction_outside']}); frames with any removal "
          f"{healthy['frames_with_any_removal']}")

    # ---- 3. service completeness: 446 declared, 400 written --------------------------------
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
        "rerun_bag_sha256": V._sha_file(R.RERUN_BAG),
        "consumed_inputs": {
            "injected_scans": {"path": R.INJ_SCANS, "sha256": sha["injected_scans"]},
            "injected_poses": {"path": R.INJ_POSES, "sha256": sha["injected_poses"]},
            "clean_scans_proxy_only": {"path": R.CLN_SCANS,
                                       "sha256": sha["clean_scans_proxy_only"]},
            "clean_poses_proxy_only": {"path": R.CLN_POSES,
                                       "sha256": sha["clean_poses_proxy_only"]},
            "filtered_bag": {"path": R.FILTERED_BAG, "sha256": f_sha},
            "rerun_bag": {"path": R.RERUN_BAG, "sha256": V._sha_file(R.RERUN_BAG)},
        },
        "audit_binding": binding,
        "missing_by_reason": by_reason,
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
