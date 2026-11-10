#!/usr/bin/env python3
"""Calibrate the NIS scale on a pre-declared healthy segment, without touching any threshold.

The node's `sigma_meas_m` multiplies the whole NIS: `compute_disjoint_holdout_point_to_plane_nis`
returns `mean((residual / sigma)^2)` (residuals are truncated at a fixed 2.0 m and the coverage
gate is sigma-independent), so NIS is exactly proportional to 1/sigma^2 and a target median fixes
sigma in closed form. No host run is needed.

  sigma* = sigma_0 * sqrt(median NIS on the healthy segment at sigma_0)

What this script does NOT do: it does not change sigma, does not change `nis_allowance_k` or any
threshold, and does not choose a segment to make the alarm go away. The segment is declared by
provenance -- outside the injection window -- and if the "no alarm" part of the definition cannot
be met, that is reported as NOT_SATISFIABLE rather than worked around.

    python -I docs/review_20261110_sigma/nis_sigma_calibration.py [RUN_DIR ...]
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np

ROOT = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
OUT_DIR = os.path.join(ROOT, "docs/review_20261110_sigma")
ONSET_SOURCE = os.path.join(ROOT, "docs/review_20261109_bbc3dcb/room02_2x2_audit.json")
DEFAULT_RUNS = [
    "/tmp/fl_native_20261110T030931Z_2941380",   # the run the stage-one report quotes (n=363)
    "/tmp/fl_native_20261110T030656Z_2938083",   # earlier attempt, same pairing window and warm-up
]
# The detector flags when nis * 1.35 > 2.8, i.e. nis > 2.074. Read from the detector config, not
# tuned here; it is used only to count how many frames would still alarm after calibration.
DETECTOR_NIS_LIMIT = 2.8 / 1.35


def pct(values, q):
    return round(float(np.percentile(values, q)), 6) if len(values) else None


def distribution(values):
    v = np.asarray([x for x in values if np.isfinite(x)], dtype=np.float64)
    if not len(v):
        return {"n": 0}
    return {"n": int(len(v)), "min": round(float(v.min()), 6),
            "p10": pct(v, 10), "median": pct(v, 50), "p90": pct(v, 90),
            "max": round(float(v.max()), 6)}


def onset_ns():
    with open(ONSET_SOURCE, encoding="utf-8") as fh:
        return int(json.load(fh)["window"]["onset_ns"])


def analyse(run_dir, onset):
    with open(os.path.join(run_dir, "run_summary.json"), encoding="utf-8") as fh:
        summary = json.load(fh)
    sigma0 = float(summary["parameters"]["sigma_meas_m"])
    frames = summary["frame_diagnostics"]

    node_map = [f for f in frames if f.get("nis_reference") == "node_map"]
    healthy = [f for f in node_map if int(f["ts_ns"]) < onset]
    alarm_free = [f for f in healthy if f.get("detector_state") == "HEALTHY"]
    values = [f["nis"] for f in healthy]

    median0 = float(np.median([v for v in values if np.isfinite(v)]))
    sigma_star = sigma0 * median0 ** 0.5
    scale = (sigma0 / sigma_star) ** 2          # NIS_new = NIS_old * scale
    after = [v * scale for v in values]

    return {
        "run": os.path.basename(run_dir),
        "run_id": summary.get("run_id"),
        "sigma_meas_m_used": sigma0,
        "frames_total": len(frames),
        "frames_node_map": len(node_map),
        "frames_prev_scan": sum(1 for f in frames if f.get("nis_reference") == "prev_scan"),
        "healthy_segment": {
            "rule": "nis_reference == 'node_map' and ts_ns < onset_ns",
            "n": len(healthy),
            "first_ts_ns": int(healthy[0]["ts_ns"]) if healthy else None,
            "last_ts_ns": int(healthy[-1]["ts_ns"]) if healthy else None,
            "alarm_free_subset_n": len(alarm_free),
            "alarm_free_status": ("SATISFIED" if len(alarm_free) >= 30 else "NOT_SATISFIABLE"),
        },
        "reference_variant": (
            "point_cap"
            if len({f.get("map_points") for f in healthy}) == 1
            else "spatial_sampling_or_other"),
        "reference_construction": {
            # Recorded because sigma* is coupled to it: a calibration on a different reference is a
            # different measurement, and the two must never be compared or carried across.
            "scan_cap": summary.get("parameters", {}).get("scan_cap"),
            # Both the per-scan input cap (6000) and the NIS reference cap are relevant, and they
            # are different numbers. The reference cap is a source constant today
            # (`get_trusted_map_points(max_pts=1500)`); the observed `map_points` below is the
            # evidence that actually identifies which construction produced this calibration.
            "nis_radius_m": summary.get("parameters", {}).get("nis_radius_m"),
            "pair_window_ns": summary.get("parameters", {}).get("pair_window_ns"),
            "map_points_over_healthy": distribution([f.get("map_points", 0) for f in healthy]),
            "trusted_keyframes_over_healthy": distribution(
                [f.get("trusted_keyframes", 0) for f in healthy]),
        },
        # Bin by trusted-keyframe count: a detection-off run measures NIS while the map is still
        # growing, so its whole-segment median is not the same population as a frozen-reference
        # run. Comparing the two medians directly would mix "the map got bigger" with "the
        # detector started too early". Only within-bin comparisons are meaningful.
        "nis_by_trusted_keyframes": {
            str(k): distribution([f["nis"] for f in healthy if f.get("trusted_keyframes") == k])
            for k in sorted({f.get("trusted_keyframes") for f in healthy})
        },
        "before": distribution(values),
        "sigma_star_m": round(sigma_star, 6),
        "after": distribution(after),
        "frames_above_detector_limit_before": int(sum(1 for v in values
                                                      if np.isfinite(v) and v > DETECTOR_NIS_LIMIT)),
        "frames_above_detector_limit_after": int(sum(1 for v in after
                                                     if np.isfinite(v) and v > DETECTOR_NIS_LIMIT)),
        "detector_nis_limit": round(DETECTOR_NIS_LIMIT, 6),
    }


def diagnosis_analysis(run_dir, onset):
    """A detection-off run: NIS measured while the map grows, so it is read per keyframe bin.

    The bins are the comparison unit because a whole-segment median over a growing map mixes "the
    map got bigger" with "the detector started too early". Within a bin the reference size is
    fixed, so sigma* is well defined there and nowhere else.
    """
    with open(os.path.join(run_dir, "run_summary.json"), encoding="utf-8") as fh:
        summary = json.load(fh)
    sigma0 = float(summary["parameters"]["sigma_meas_m"])
    frames = [f for f in summary["frame_diagnostics"]
              if f.get("nis_reference") == "node_map"
              and f.get("nis") is not None and np.isfinite(f["nis"])]
    edges = [(1, 2), (3, 5), (6, 10), (11, 20), (21, 50), (51, 100), (101, None)]
    bins = []
    for lo, hi in edges:
        members = [f for f in frames if lo <= f["trusted_keyframes"] and
                   (hi is None or f["trusted_keyframes"] <= hi)]
        if not members:
            continue
        values = np.array([f["nis"] for f in members])
        median = float(np.median(values))
        sigma_star = sigma0 * median ** 0.5
        scale = (sigma0 / sigma_star) ** 2
        tail = [f for f in members if f["nis"] * scale > DETECTOR_NIS_LIMIT]
        # Where in time the above-threshold frames sit. A tail that is a bounded interval after
        # the injection onset is degradation; one spread evenly over the run is coverage/pairing.
        profile = []
        for t0 in range(0, 24, 2):
            seg = [f for f in members
                   if t0 <= (f["ts_ns"] - onset) / 1e9 < t0 + 2]
            if seg:
                profile.append({
                    "t_rel_onset_s": [t0, t0 + 2], "n": len(seg),
                    "above_after_rescale": sum(1 for f in seg
                                               if f["nis"] * scale > DETECTOR_NIS_LIMIT),
                    "median_raw": round(float(np.median([f["nis"] for f in seg])), 3),
                })
        pre = [f["nis"] for f in members if f["ts_ns"] < onset]
        bins.append({
            "lo": lo, "hi": hi, "n": len(members), "before": distribution(values),
            # Calibrating only on pre-onset frames is the honest check that the degradation does
            # not drive sigma*: if the two agree, the value is a property of the reference size,
            # not of the fault.
            "sigma_star_pre_onset_only_m": (
                round(sigma0 * float(np.median(pre)) ** 0.5, 6) if len(pre) >= 10 else None),
            "n_pre_onset": len(pre),
            "post_onset_profile": profile,
            "sigma_star_m": round(sigma_star, 6),
            "after": distribution(values * scale),
            "frames_above_detector_limit_after": len(tail),
            "tail": {
                "n": len(tail),
                "first_ts_rel_onset_s": (round((min(f["ts_ns"] for f in tail) - onset) / 1e9, 3)
                                         if tail else None),
                "all_after_onset": (all(f["ts_ns"] >= onset for f in tail) if tail else None),
                "kf_range": ([min(f["kf_id"] for f in tail), max(f["kf_id"] for f in tail)]
                             if tail else None),
                "map_points_range": ([min(f["map_points"] for f in tail),
                                      max(f["map_points"] for f in tail)] if tail else None),
            },
        })
    return {
        "run": os.path.basename(run_dir),
        "detection_enabled": summary.get("detection_enabled"),
        "sigma_meas_m_used": sigma0,
        "reference_variant": (
            "point_cap" if len({f.get("map_points") for f in frames}) == 1
            else "spatial_sampling_or_other"),
        "frames_with_node_map_nis": len(frames),
        "map_points_range": [min(f["map_points"] for f in frames),
                             max(f["map_points"] for f in frames)],
        "bins": bins,
        "not_available": {
            "position_distribution": ("the archived diagnostics carry no pose; the tail is "
                                      "characterised by time, keyframe id and map size only. "
                                      "Recovering position would need the host output bag, which "
                                      "this run did not record (receipt.output is null)."),
        },
    }


def archived_candidate(run_dir, scale):
    path = os.path.join(run_dir, "candidates.jsonl")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        cand = json.loads(fh.readline())
    nis = float(cand.get("holdout_nis"))
    return {
        "candidate_id": cand.get("candidate_id"),
        "candidate_source": cand.get("candidate_source"),
        "mode": cand.get("mode"),
        "accepted": cand.get("accepted"),
        "refusal_reason": cand.get("refusal_reason"),
        "holdout_nis_before": round(nis, 6),
        "holdout_nis_after_rescale": round(nis * scale, 6),
        "tau_val_nis": 2.5,
        "other_refusal_legs": {
            "reentry_pos_jump_m": cand.get("reentry_pos_jump_m"),
            "max_reentry_jump_m": 0.5,
            "wilson_lower_bound": cand.get("wilson_lower_bound"),
            "min_wilson_lower_bound": 0.55,
            "weak_dir_info_gain": round(
                float(cand.get("weak_dir_info_after")) - float(cand.get("weak_dir_info_before")), 6),
        },
        "mode_would_change": False,
        "why": ("the archived candidate is refused before the NIS comparison is ever decisive: "
                "boundary continuity fails (0.666 m > 0.5 m) and the paired evidence FAILED "
                "(wilson 0.121 < 0.55). Rescaling sigma moves only the holdout-NIS leg, which was "
                "not the leg that refused it."),
    }


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    if "--diagnosis" in argv:
        onset = onset_ns()
        diags = [diagnosis_analysis(run_dir, onset) for run_dir in args]
        out = {
            "_meta": {
                "what": "detection-off diagnosis: sigma* per trusted-keyframe bin, and the tail",
                "written": "2026-11-10",
                "onset_ns": onset,
                "onset_source": os.path.relpath(ONSET_SOURCE, ROOT),
                "comparison_rule": ("bins are the unit; a whole-segment median over a growing map "
                                    "is not comparable with a frozen-reference calibration"),
                "not_done": ["no sigma changed", "no threshold changed",
                             "no attempt to suppress the tail with sigma"],
            },
            "runs": diags,
        }
        os.makedirs(OUT_DIR, exist_ok=True)
        path = os.path.join(OUT_DIR, "nis_sigma_diagnosis_results.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=1)
        print(json.dumps({"sigma_star_by_bin": [
            [(b["lo"], b["hi"], b["sigma_star_m"]) for b in r["bins"]] for r in diags],
            "out": os.path.relpath(path, ROOT)}, indent=1))
        return 0
    runs = args or DEFAULT_RUNS
    onset = onset_ns()
    results = []
    for run_dir in runs:
        record = analyse(run_dir, onset)
        record["archived_candidate"] = archived_candidate(
            run_dir, (record["sigma_meas_m_used"] / record["sigma_star_m"]) ** 2)
        results.append(record)

    out = {
        "_meta": {
            "what": "NIS sigma calibration on a pre-declared healthy segment; diagnostic only",
            "written": "2026-11-10",
            "onset_ns": onset,
            "onset_source": os.path.relpath(ONSET_SOURCE, ROOT),
            "proportionality": ("NIS = mean((residual/sigma)^2) with a sigma-independent 2.0 m "
                                "truncation and coverage gate, so NIS scales exactly as 1/sigma^2; "
                                "sigma* = sigma_0 * sqrt(median NIS)"),
            "not_done": ["no sigma changed", "no threshold changed", "no nis_allowance_k touch",
                         "no segment chosen to suppress the alarm"],
            "reference_construction_per_run": [r["reference_construction"] for r in results],
            "reference_variant_per_run": [r["reference_variant"] for r in results],
            "variant_rule": ("a constant map_points over the healthy segment identifies the "
                             "point-capped reference; a varying distribution identifies a "
                             "sampling that tracks the map, so the two calibrations are different "
                             "measurements and sigma* must not be carried between them"),
            "coupling_caveat": ("sigma* absorbs whatever the reference construction produces. "
                                "This calibration was taken on the point-capped reference "
                                "(map_points constant 1500, one trusted keyframe); a later run with "
                                "resolution-based spatial sampling measured a higher median, so "
                                "sigma* must be recomputed on any other construction and must not "
                                "be carried across."),
            "attribution_correction": {
                "date": "2026-11-10",
                "source": "r11070-c3 measurement, relayed by the integration session",
                "what": ("the point cap was replaced by 0.30 m resolution-based spatial sampling: "
                         "1500 -> 931 points and the NIS median moved 21.57 -> 24.05, i.e. it did "
                         "not fall"),
                "withdrawn": ("the 'point cap thins the map and inflates NIS' half of the earlier "
                              "attribution is withdrawn; this file's own numbers are unaffected "
                              "but the explanation attached to them is"),
                "remaining_candidates": [
                    "the reference holds only two keyframes at first decision (confirmation "
                    "margin 2 s), so the map is young irrespective of how it is sampled",
                    "the residual between a scan and this 931-point reference is genuinely ~0.55 m",
                ],
                "open": ("r11070-c3 runs a detection-off pass to see whether NIS converges to "
                         "O(1) as the map grows; convergence would move the fix to start "
                         "conditions, non-convergence would bring it back to sigma / residual "
                         "definition. Neither outcome may reuse 0.5538."),
            },
        },
        "runs": results,
        "summary": {
            "sigma_star_m_per_run": [r["sigma_star_m"] for r in results],
            "median_before_per_run": [r["before"].get("median") for r in results],
            "healthy_rule_satisfies_no_alarm": all(
                r["healthy_segment"]["alarm_free_status"] == "SATISFIED" for r in results),
            "note": ("the 'no alarm' clause of the pre-declared health rule cannot be met here: the "
                     "first judged frame already alarms, so 167 of 168 pre-onset frames carry "
                     "detector_state QUARANTINED. Selecting only unalarmed frames would leave n=1 "
                     "and would select on the outcome. The segment is therefore declared healthy "
                     "by provenance (outside the injection window) and the clause is reported "
                     "NOT_SATISFIABLE, not silently dropped."),
        },
    }
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, "nis_sigma_results.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    print(json.dumps({"sigma_star_m": out["summary"]["sigma_star_m_per_run"],
                      "median_before": out["summary"]["median_before_per_run"],
                      "out": os.path.relpath(path, ROOT)}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
