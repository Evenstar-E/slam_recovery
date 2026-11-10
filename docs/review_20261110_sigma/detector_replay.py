#!/usr/bin/env python3
"""Replay the detector over archived per-frame NIS, at a given sigma.

This is arithmetic on the archived frames, not a new detector: it constructs the same
`HealthWindow` the node constructs and calls the same `JointHealthDetector`. No threshold, config
or estimator is touched.

The question it answers: with sigma set to the large-map value, does the detector still fire
before the injection onset?

Validation built in: run it on the stage-one run at sigma = 0.12 and it must reproduce that run's
recorded trigger timestamp. That is what makes the replay trustworthy before it is pointed at the
diagnosis run.

    python -I docs/review_20261110_sigma/detector_replay.py RUN_DIR SIGMA [--expect-trigger-ns N]
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np

ROOT = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
OUT_DIR = os.path.join(ROOT, "docs/review_20261110_sigma")
sys.path.insert(0, ROOT)

from slam_recovery.core import HealthWindow, RecoveryState  # noqa: E402
from slam_recovery.health import DetectorConfig, JointHealthDetector  # noqa: E402

ONSET_SOURCE = os.path.join(ROOT, "docs/review_20261109_bbc3dcb/room02_2x2_audit.json")


def _window():
    with open(ONSET_SOURCE, encoding="utf-8") as fh:
        window = json.load(fh)["window"]
    return int(window["onset_ns"]), int(window["end_ns"])


def onset_ns():
    return _window()[0]


def replay(run_dir, sigma, onset):
    with open(os.path.join(run_dir, "run_summary.json"), encoding="utf-8") as fh:
        summary = json.load(fh)
    sigma0 = float(summary["parameters"]["sigma_meas_m"])
    scale = (sigma0 / sigma) ** 2
    frames = [f for f in summary["frame_diagnostics"]
              if f.get("nis_reference") == "node_map"
              and f.get("nis") is not None and np.isfinite(f["nis"])]
    frames.sort(key=lambda f: f["ts_ns"])

    detector = JointHealthDetector(DetectorConfig())
    first_soft = None
    first_quarantined = None
    for f in frames:
        nis = float(f["nis"]) * scale
        window = HealthWindow(
            t_start_ns=int(f["ts_ns"]), t_end_ns=int(f["ts_ns"]),
            # The archived diagnostics carry no FIM, so the geometric branch cannot be replayed.
            # These values keep it below its alarm thresholds, which makes the result a statement
            # about the NIS branch only -- not about every alarm source in the node.
            min_eig_rot=1e9, min_eig_trans=1e9, max_eig_rot_cov=0.0, max_eig_trans_cov=0.0,
            weak_dir_6d=np.zeros(6), nis_mean=nis, nis_q90=nis * 1.35, nis_cusum=0.0,
            loso_primary_conflict=0.5, loso_aux_conflict=0.5, Cross_corr_lag_sec=0.0,
            loop_residual_spike=0.3,
        )
        decision = detector.step(window)
        if decision.state != RecoveryState.HEALTHY and first_soft is None:
            first_soft = {"ts_ns": int(f["ts_ns"]), "kf_id": f.get("kf_id"),
                          "state": decision.state.value, "nis_scaled": round(nis, 6)}
        if decision.state == RecoveryState.QUARANTINED and first_quarantined is None:
            first_quarantined = {"ts_ns": int(f["ts_ns"]), "kf_id": f.get("kf_id"),
                                 "nis_scaled": round(nis, 6),
                                 "cusum": round(detector.cusum_g, 6)}
    return {
        "run": os.path.basename(run_dir),
        "sigma0_used_by_run": sigma0,
        "sigma_replayed": sigma,
        "frames_judged": len(frames),
        "first_alarm_any_state": first_soft,
        "first_quarantined": first_quarantined,
        "first_alarm_rel_onset_s": (round((first_soft["ts_ns"] - onset) / 1e9, 3)
                                    if first_soft else None),
        "first_quarantined_rel_onset_s": (round((first_quarantined["ts_ns"] - onset) / 1e9, 3)
                                          if first_quarantined else None),
    }


def coverage(run_dir, sigma):
    """Per-frame detector state at this sigma, bucketed by second inside the injection window.

    Two denominators are reported because they answer different questions: over *all* frames in the
    window (what an operator would experience) and over *judged* frames only (what the estimator
    could actually see). The gap between them is the frames the warm-up policy never judges.
    """
    onset, end = _window()
    with open(os.path.join(run_dir, "run_summary.json"), encoding="utf-8") as fh:
        summary = json.load(fh)
    sigma0 = float(summary["parameters"]["sigma_meas_m"])
    scale = (sigma0 / sigma) ** 2
    frames = sorted(summary["frame_diagnostics"], key=lambda f: f["ts_ns"])
    in_window = [f for f in frames if onset <= f["ts_ns"] <= end]
    judged = [f for f in in_window if f.get("nis_reference") == "node_map"
              and f.get("nis") is not None and np.isfinite(f["nis"])]

    detector = JointHealthDetector(DetectorConfig())
    state_by_ts = {}
    for f in frames:                                  # state evolves over the whole run
        if f.get("nis_reference") != "node_map" or f.get("nis") is None or not np.isfinite(f["nis"]):
            state_by_ts[f["ts_ns"]] = None            # not judged: no state change
            continue
        nis = float(f["nis"]) * scale
        decision = detector.step(HealthWindow(
            t_start_ns=int(f["ts_ns"]), t_end_ns=int(f["ts_ns"]),
            min_eig_rot=1e9, min_eig_trans=1e9, max_eig_rot_cov=0.0, max_eig_trans_cov=0.0,
            weak_dir_6d=np.zeros(6), nis_mean=nis, nis_q90=nis * 1.35, nis_cusum=0.0,
            loso_primary_conflict=0.5, loso_aux_conflict=0.5, Cross_corr_lag_sec=0.0,
            loop_residual_spike=0.3,
        ))
        state_by_ts[f["ts_ns"]] = decision.state.value

    def flagged(state):
        return state in (RecoveryState.SUSPECT.value, RecoveryState.QUARANTINED.value)

    buckets = []
    for t0 in range(0, int((end - onset) / 1e9) + 1):
        seg = [f for f in in_window if t0 <= (f["ts_ns"] - onset) / 1e9 < t0 + 1]
        if not seg:
            continue
        seg_judged = [f for f in seg if f["ts_ns"] in state_by_ts
                      and state_by_ts[f["ts_ns"]] is not None]
        n_flag_all = sum(1 for f in seg if flagged(state_by_ts.get(f["ts_ns"])))
        n_flag_judged = sum(1 for f in seg_judged if flagged(state_by_ts[f["ts_ns"]]))
        buckets.append({
            "t_rel_onset_s": t0,
            "frames_all": len(seg), "flagged_all": n_flag_all,
            "coverage_all": round(n_flag_all / len(seg), 4),
            "frames_judged": len(seg_judged), "flagged_judged": n_flag_judged,
            "coverage_judged": (round(n_flag_judged / len(seg_judged), 4) if seg_judged else None),
        })
    tot_all = len(in_window)
    tot_flag_all = sum(1 for f in in_window if flagged(state_by_ts.get(f["ts_ns"])))
    tot_judged = len(judged)
    tot_flag_judged = sum(1 for f in judged if flagged(state_by_ts.get(f["ts_ns"])))
    return {
        "run": os.path.basename(run_dir),
        "sigma_replayed": sigma,
        "window": {"onset_ns": onset, "end_ns": end,
                   "duration_s": round((end - onset) / 1e9, 3)},
        "frames_in_window": tot_all,
        "frames_judged_in_window": tot_judged,
        "coverage_all": round(tot_flag_all / tot_all, 4) if tot_all else None,
        "coverage_judged": round(tot_flag_judged / tot_judged, 4) if tot_judged else None,
        "flagged_all": tot_flag_all,
        "flagged_judged": tot_flag_judged,
        "buckets": buckets,
    }


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    expect = None
    if "--expect-trigger-ns" in argv:
        expect = int(argv[argv.index("--expect-trigger-ns") + 1])
        args.remove(str(expect))
    if "--coverage" in argv:
        run_dir = args[0]
        sigma = float(args[1])
        out = coverage(run_dir, sigma)
        os.makedirs(OUT_DIR, exist_ok=True)
        path = os.path.join(OUT_DIR, "nis_detector_coverage_results.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"refusals": ["NIS branch only", "prev_scan frames not judged",
                                    "no threshold changed"], **out}, fh, indent=1)
        print(json.dumps({k: out[k] for k in
                          ("sigma_replayed", "frames_in_window", "frames_judged_in_window",
                           "coverage_all", "coverage_judged")}, indent=1))
        return 0
    if "--sweep" in argv:
        run_dir = args[0]
        sigmas = [float(x) for x in args[1:]]
        onset = onset_ns()
        rows = [replay(run_dir, sigma, onset) for sigma in sigmas]
        out = {
            "_meta": {
                "what": "detector replay over archived per-frame NIS at several sigma",
                "written": "2026-11-10",
                "onset_ns": onset,
                "rule": ("first_alarm_any_state is the first SUSPECT; first_quarantined is the "
                         "frame the dwell rule turns it into a quarantine. Both are relative to "
                         "the injection onset and may straddle it at the crossover sigma."),
                "assumptions": [
                    "only nis_reference == 'node_map' frames are judged, matching the node's "
                    "warm-up policy (no reference -> not judged)",
                    "nis_q90 = nis * 1.35, as the node sets it",
                    "the archived diagnostics carry no FIM, so the geometric branch is held below "
                    "its thresholds: this replays the NIS branch only",
                ],
                "not_done": ["no sigma, threshold or config changed"],
            },
            "runs": rows,
        }
        os.makedirs(OUT_DIR, exist_ok=True)
        path = os.path.join(OUT_DIR, "nis_detector_replay_results.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=1)
        print(json.dumps({"rows": [(r["sigma_replayed"], r["first_alarm_rel_onset_s"],
                                    r["first_quarantined_rel_onset_s"]) for r in rows],
                          "out": os.path.relpath(path, ROOT)}, indent=1))
        return 0
    run_dir, sigma = args[0], float(args[1])
    out = replay(run_dir, sigma, onset_ns())
    out["expected_trigger_ns"] = expect
    out["reproduces_recorded_trigger"] = (
        None if expect is None else
        out["first_quarantined"] is not None and out["first_quarantined"]["ts_ns"] == expect)
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
