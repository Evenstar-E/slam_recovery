#!/usr/bin/env python3
"""B-1: a health-prefix conditional scale, replayed causally, against the frozen baseline.

The rule below is frozen BEFORE the replay and is not adjusted afterwards. It uses only what the
node can see online at time t: its own NIS, its trusted keyframe count and its map size. No bag
quantile, no future frame, no fault label.

FROZEN RULE (B-v1)
  qualifying frame : judged (node_map reference, finite NIS) and trusted_keyframes >= 20 and
                     map_points >= 3000
  prefix           : the first 30 qualifying frames, in time order
  scale            : s = median(NIS over the prefix)  -- the same "median maps to 1" convention the
                     sigma calibration used, so s plays the role of a per-run sigma^2
  before the prefix completes : frames are NOT judged (blind), the same policy the node already
                     applies to its warm-up, just with a support criterion attached
  after the prefix : s is frozen; a frame alarms when NIS/s exceeds the detector's own spike limit
                     (2.8/1.35) and the dwell rule (2 consecutive) turns it into a quarantine

Justification of the constants from existing development evidence, not from this run's outcome:
  - the sigma* curve bottoms out at 21-50 keyframes, so 20 is the first bucket that is no longer
    "young map";
  - 3000 points is the first map_points bucket whose NIS is stable (the 501-2000 buckets carry the
    startup values);
  - 30 frames is ~3 s at 10 Hz, long enough to hold a median and short enough to start judging
    inside the pre-onset window;
  - the spike limit and dwell are the detector's existing ones, unchanged.

    python -I docs/gate_method_research_20261110/b1_health_prefix.py [RUN_DIR ...]
"""

from __future__ import annotations

import glob
import json
import os
import sys

import numpy as np

ROOT = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
OUT_DIR = os.path.join(ROOT, "docs/gate_method_research_20261110")
ONSET_SOURCE = os.path.join(ROOT, "docs/review_20261109_bbc3dcb/room02_2x2_audit.json")

K_MIN = 20
M_MIN = 3000
PREFIX_N = 30
SPIKE = 2.8 / 1.35
BASELINE_SIGMA = 0.12


def window():
    with open(ONSET_SOURCE, encoding="utf-8") as fh:
        w = json.load(fh)["window"]
    return int(w["onset_ns"]), int(w["end_ns"])


def judged_frames(run_dir):
    with open(os.path.join(run_dir, "run_summary.json"), encoding="utf-8") as fh:
        d = json.load(fh)
    fr = [f for f in d["frame_diagnostics"]
          if f.get("nis_reference") == "node_map" and f.get("nis") is not None
          and np.isfinite(f["nis"])]
    fr.sort(key=lambda f: f["ts_ns"])
    return d, fr


class Detector:
    """The detector's NIS branch, on a scale-normalised NIS: spike + dwell + CUSUM."""

    def __init__(self, scale_provider):
        self.scale_provider = scale_provider
        self.cusum = 0.0
        self.dwell = 0
        self.state = "HEALTHY"

    def step(self, t_ns, nis):
        scale = self.scale_provider(t_ns)
        if scale is None:
            return "UNJUDGED"
        x = nis / scale
        self.last_x = x
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
        return self.state


def run_rule(frames, onset, end, scale_fn, judge_from=None):
    det = Detector(scale_fn)
    states = []
    for f in frames:
        if judge_from is not None and f["ts_ns"] < judge_from:
            states.append((f["ts_ns"], "UNJUDGED", f["kf_id"], None, None))
            continue
        st = det.step(f["ts_ns"], float(f["nis"]))
        states.append((f["ts_ns"], st, f["kf_id"], round(getattr(det, "last_x", float("nan")), 4),
                       round(det.cusum, 4)))

    def first(state):
        for ts, st, kf, x, cusum in states:
            if st == state:
                return {"ts_ns": ts, "rel_onset_s": round((ts - onset) / 1e9, 3), "kf_id": kf,
                        "normalised_nis": x, "cusum": cusum,
                        "spike_triggered": bool(x * 1.35 > 2.8)}
        return None

    in_win = [s for s in states if onset <= s[0] <= end]
    flagged = [s for s in in_win if s[1] in ("SUSPECT", "QUARANTINED")]
    pre = [s for s in states if s[0] < onset]
    return {
        "frames": len(states),
        "first_suspect": first("SUSPECT"),
        "first_quarantine": first("QUARANTINED"),
        "pre_onset_judged": sum(1 for s in pre if s[1] != "UNJUDGED"),
        "pre_onset_frames": len(pre),
        "pre_onset_flagged": sum(1 for s in pre if s[1] in ("SUSPECT", "QUARANTINED")),
        "window_frames": len(in_win),
        "window_flagged": len(flagged),
        "window_coverage": round(len(flagged) / len(in_win), 4) if in_win else None,
        "unjudged_span_s": _unjudged_span(states, onset),
    }


def _unjudged_span(states, onset):
    ts = [s[0] for s in states if s[1] == "UNJUDGED"]
    if not ts:
        return 0.0
    return round((max(ts) - min(ts)) / 1e9, 3)


def build_scale(frames, contaminated=False):
    """Prefix scale, plus the timestamp from which judgement can start.

    `contaminated=True` is the negative control: the prefix is taken from frames inside the
    degradation window instead of the qualifying start, i.e. the estimator is fed exactly the
    samples the rule is supposed to keep out. If the control does not change the outcome, the
    control has no trigger path and the claim would be empty.
    """
    if contaminated:
        onset, end = window()
        pool = [f for f in frames if onset + 6.0e9 <= f["ts_ns"] <= onset + 12.0e9]
        if len(pool) < PREFIX_N:
            return None, None, None
        prefix = pool[:PREFIX_N]
    else:
        pool = [f for f in frames if f["trusted_keyframes"] >= K_MIN and f["map_points"] >= M_MIN]
        if len(pool) < PREFIX_N:
            return None, None, None
        prefix = pool[:PREFIX_N]
    scale = float(np.median([f["nis"] for f in prefix]))
    start = prefix[-1]["ts_ns"]
    return scale, start, {"prefix_start_ts_ns": prefix[0]["ts_ns"],
                          "prefix_end_ts_ns": start,
                          "prefix_median_nis": round(scale, 6),
                          "prefix_kf_range": [prefix[0]["trusted_keyframes"],
                                              prefix[-1]["trusted_keyframes"]]}


def main(argv):
    run_dirs = argv[1:] or sorted(glob.glob("/tmp/fl_native_*"))
    onset, end = window()
    results = []
    for rd in run_dirs:
        path = os.path.join(rd, "run_summary.json")
        if not os.path.exists(path):
            continue
        _, frames = judged_frames(rd)
        if len(frames) < PREFIX_N:
            continue
        sigma0 = json.load(open(path, encoding="utf-8"))["parameters"]["sigma_meas_m"]

        # baseline: frozen method, every judged frame, scale = sigma0^2 (NIS is ~1/sigma^2)
        base = run_rule(frames, onset, end, lambda t, s=sigma0: s ** 2)
        # B-v1
        scale, start, meta = build_scale(frames, contaminated=False)
        if scale is None:
            results.append({"run": os.path.basename(rd), "status": "NO_PREFIX"})
            continue
        b = run_rule(frames, onset, end, lambda t, sc=scale: sc, judge_from=start)
        # negative control: the same rule, prefix fed from inside the degradation window
        cscale, cstart, cmeta = build_scale(frames, contaminated=True)
        ctl = (run_rule(frames, onset, end, lambda t, sc=cscale: sc, judge_from=cstart)
               if cscale is not None else None)
        results.append({"run": os.path.basename(rd), "sigma0": sigma0,
                        "baseline": base, "B_v1": {**b, "prefix": meta},
                        "negative_control_contaminated_prefix": (
                            {"scale": round(cscale, 6), **({**ctl, "prefix": cmeta}
                                                           if ctl else {})})})

    out = {
        "_meta": {
            "what": "B-1 health-prefix conditional scale, causal replay",
            "written": "2026-11-10",
            "frozen_rule": {"K_MIN": K_MIN, "M_MIN": M_MIN, "PREFIX_N": PREFIX_N,
                            "spike": round(SPIKE, 6), "dwell": 2, "scale": "prefix median NIS",
                            "frozen_after_prefix": True, "no_future_data": True},
            "not_done": ["no host run", "no threshold changed", "no bag quantile used"],
            "candidate_admission_half": ("BLOCKED: B's second question is admission calibration, "
                                         "which needs a candidate stream with per-candidate scale; "
                                         "the archive has none"),
        },
        "runs": results,
    }
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, "b1_health_prefix.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    print(json.dumps({"runs": [(r["run"], r.get("baseline", {}).get("first_suspect"),
                                r.get("B_v1", {}).get("first_suspect")) for r in results],
                      "out": os.path.relpath(path, ROOT)}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
