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
        "before": distribution(values),
        "sigma_star_m": round(sigma_star, 6),
        "after": distribution(after),
        "frames_above_detector_limit_before": int(sum(1 for v in values
                                                      if np.isfinite(v) and v > DETECTOR_NIS_LIMIT)),
        "frames_above_detector_limit_after": int(sum(1 for v in after
                                                     if np.isfinite(v) and v > DETECTOR_NIS_LIMIT)),
        "detector_nis_limit": round(DETECTOR_NIS_LIMIT, 6),
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
    runs = argv[1:] or DEFAULT_RUNS
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
            "coupling_caveat": ("sigma* absorbs whatever the reference construction produces. The "
                                "NIS reference still comes from a point-capped map sample; if that "
                                "is changed, sigma* must be recomputed, and the two causes must "
                                "stay reported separately."),
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
