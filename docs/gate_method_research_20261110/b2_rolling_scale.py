#!/usr/bin/env python3
"""B-v2: the same health-conditioned scale, but rolling instead of frozen. One rule, one run.

FROZEN RULE (B-v2) -- written before the replay, not adjusted afterwards:
  qualifying frame : judged (node_map reference, finite NIS) and trusted_keyframes >= 20 and
                     map_points >= 3000            (identical to B-v1, so the only difference is
                                                    the update rule)
  scale            : s_t = median of the last min(W, available) qualifying judged NIS values,
                     INCLUDING the current frame; W = 50 frames (~5 s at 10 Hz)
  cold start       : frames are not judged until 30 qualifying values exist
  no filter        : a frame is admitted to the window whatever its value. This is deliberate:
                     the question B has to answer is whether a rolling health estimate swallows
                     the fault it is supposed to detect, and a trimmed update would hide exactly
                     that. A filter is a different rule (B-v3), not this one.
  alarm            : the detector's own spike limit on NIS/s (2.8/1.35) and CUSUM 4.0, dwell 2.

The fault-absorption test is the point of this version: if the window admits degradation samples,
the scale climbs and the detector closes itself. That is reported as a scale trajectory, not
inferred from the final coverage.

    python -I docs/gate_method_research_20261110/b2_rolling_scale.py RUN_DIR
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np

ROOT = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
OUT_DIR = os.path.join(ROOT, "docs/gate_method_research_20261110")
ONSET_SOURCE = os.path.join(ROOT, "docs/review_20261109_bbc3dcb/room02_2x2_audit.json")

K_MIN, M_MIN = 20, 3000
W = 50
MIN_SAMPLES = 30
SPIKE = 2.8 / 1.35


def window_bounds():
    with open(ONSET_SOURCE, encoding="utf-8") as fh:
        w = json.load(fh)["window"]
    return int(w["onset_ns"]), int(w["end_ns"])


def load(run_dir):
    with open(os.path.join(run_dir, "run_summary.json"), encoding="utf-8") as fh:
        d = json.load(fh)
    fr = [f for f in d["frame_diagnostics"]
          if f.get("nis_reference") == "node_map" and f.get("nis") is not None
          and np.isfinite(f["nis"])]
    fr.sort(key=lambda f: f["ts_ns"])
    return d, fr


class RollingDetector:
    def __init__(self):
        self.buf = []
        self.cusum = 0.0
        self.dwell = 0
        self.state = "HEALTHY"
        self.scale = None

    def step(self, frame):
        if frame["trusted_keyframes"] < K_MIN or frame["map_points"] < M_MIN:
            return "UNJUDGED", self.scale
        self.buf.append(float(frame["nis"]))
        if len(self.buf) > W:
            self.buf.pop(0)
        if len(self.buf) < MIN_SAMPLES:
            return "UNJUDGED", None
        self.scale = float(np.median(self.buf))
        x = float(frame["nis"]) / self.scale
        if x < 1.35:
            self.cusum = max(0.0, 0.4 * self.cusum + (x - 1.35))
        else:
            self.cusum = max(0.0, self.cusum + (x - 1.35))
        alarm = (self.cusum > 4.0) or (x * 1.35 > 2.8)
        if alarm:
            self.dwell += 1
            self.state = "QUARANTINED" if self.dwell >= 2 else "SUSPECT"
        else:
            self.dwell = 0
            self.state = "HEALTHY"
        return self.state, self.scale




def _nearest(trace, seconds):
    out = []
    for s in seconds:
        cand = min(trace, key=lambda r: abs(r["rel_onset_s"] - s))
        out.append({"target_rel_onset_s": s, "rel_onset_s": cand["rel_onset_s"],
                    "scale": (round(cand["scale"], 4) if cand["scale"] is not None else None),
                    "state": cand["state"]})
    return out


def _by_third(trace, onset, end):
    span = (end - onset) / 3.0
    out = []
    for i in range(3):
        lo, hi = onset + i * span, onset + (i + 1) * span
        seg = [r for r in trace if lo <= r["ts_ns"] < hi or (i == 2 and r["ts_ns"] == hi)]
        if not seg:
            continue
        flagged = sum(1 for r in seg if r["state"] in ("SUSPECT", "QUARANTINED"))
        scales = [r["scale"] for r in seg if r["scale"] is not None]
        out.append({"third": i + 1, "frames": len(seg), "flagged": flagged,
                    "coverage": round(flagged / len(seg), 4),
                    "scale_median": round(float(np.median(scales)), 4) if scales else None})
    return out

def main(argv):
    run_dir = argv[1]
    onset, end = window_bounds()
    summary, frames = load(run_dir)
    det = RollingDetector()
    trace = []
    for f in frames:
        st, sc = det.step(f)
        trace.append({"ts_ns": f["ts_ns"], "rel_onset_s": round((f["ts_ns"] - onset) / 1e9, 3),
                      "state": st, "scale": sc, "nis": float(f["nis"]),
                      "kf": f["trusted_keyframes"]})

    def first(state):
        for r in trace:
            if r["state"] == state:
                return {k: r[k] for k in ("rel_onset_s", "kf", "scale", "nis")}
        return None

    in_win = [r for r in trace if onset <= r["ts_ns"] <= end]
    flagged = [r for r in in_win if r["state"] in ("SUSPECT", "QUARANTINED")]
    scaled = [r for r in in_win if r["scale"] is not None]
    pre = [r for r in trace if r["ts_ns"] < onset and r["scale"] is not None]
    post_scales = [r["scale"] for r in scaled]

    out = {
        "run": os.path.basename(run_dir),
        "sigma_in_run": summary["parameters"]["sigma_meas_m"],
        "rule": {"K_MIN": K_MIN, "M_MIN": M_MIN, "W": W, "MIN_SAMPLES": MIN_SAMPLES,
                 "update": "rolling median, current frame included", "filter": "none"},
        "first_suspect": first("SUSPECT"),
        "first_quarantine": first("QUARANTINED"),
        "unjudged_frames": sum(1 for r in trace if r["state"] == "UNJUDGED"),
        "window_frames": len(in_win),
        "window_flagged": len(flagged),
        "window_coverage": round(len(flagged) / len(in_win), 4) if in_win else None,
        "fault_absorption": {
            "scale_at_onset": next((r["scale"] for r in trace
                                    if r["ts_ns"] >= onset and r["scale"] is not None), None),
            "scale_pre_onset_median": round(float(np.median([r["scale"] for r in pre])), 4)
            if pre else None,
            "scale_max_in_window": round(max(post_scales), 4) if post_scales else None,
            "scale_median_in_window": round(float(np.median(post_scales)), 4)
            if post_scales else None,
            "drift_ratio_max_over_pre": (
                round(max(post_scales) / float(np.median([r["scale"] for r in pre])), 4)
                if pre and post_scales else None),
        },
        "scale_trajectory": _nearest(trace, [-10, -5, -1, 0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20]),
        "coverage_by_third": _by_third(trace, onset, end),
    }
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, "b2_rolling_scale.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    print(json.dumps({k: out[k] for k in ("run", "first_suspect", "first_quarantine",
                                          "window_coverage", "fault_absorption")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
