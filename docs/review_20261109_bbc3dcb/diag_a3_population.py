#!/usr/bin/env python3
"""Read-only: why does the A3 candidate population differ between two onsets?

Builds the same A3 candidate the four-arm script builds and reports, for the archived onset
(14.528393030166626) and the current one (detected at run time), the counts the review asked for:

  onset/end, candidate span and count, ref_pts length and stride before/after the 4000 cap,
  support_reference size, and the support-fraction distribution that decides pairability.

No host run, no code changes, no new experiment.

    ~/mm/micromamba run -p ~/mm/ros python -I -B docs/review_20261109_bbc3dcb/diag_a3_population.py
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np

REPO = "/tmp/wt-fourarm"
sys.path.insert(0, REPO)
import importlib.util

spec = importlib.util.spec_from_file_location(
    "fa", os.path.join(REPO, "slam_recovery/experiments/run_four_arm_same_input.py"))
fa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fa)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "diag_a3_population.json")
ARCHIVED_ONSET = 14.528393030166626


def gather():
    inj, _ = fa.pair_keyframes(fa.DEFAULT_INJ_SCANS, fa.DEFAULT_INJ_POSES, False)
    cln, _ = fa.pair_keyframes(fa.DEFAULT_CLN_SCANS, fa.DEFAULT_CLN_POSES, False)
    st, _en, _ev = fa.detect_onset(fa.DEFAULT_CLN_SCANS, fa.DEFAULT_INJ_SCANS)
    return inj, cln, float(st)


def probe(inj, onset_rel, label):
    ts = np.asarray([k["ts"] for k in inj])
    t0 = ts[0]
    pre = [k for k in inj if (k["ts"] - t0) < onset_rel]
    quar = [k for k in inj if (k["ts"] - t0) >= onset_rel]

    ref_full = np.vstack([fa.world_points(k) for k in pre]) if pre else np.zeros((0, 3))
    n_full = len(ref_full)
    step = max(1, n_full // 4000)
    ref_pts = ref_full[::step][:4000] if n_full > 4000 else ref_full

    node = fa.OnlineRecoveryTransactionNode(confirmation_margin_sec=2.0, voxel_size_m=fa.VOXEL,
                                            holdout_stride=5)
    node.committed_map_points = [ref_pts] if len(ref_pts) else []
    support_ref = node.support_reference()

    quar_ts = np.asarray([k["ts"] for k in quar])
    # support fraction per candidate frame, using the node's own rule
    poses = {i: k["pose"].copy() for i, k in enumerate(quar)}
    node.scan_buffer_body = {i: k["pts"] for i, k in enumerate(quar)}
    fracs = []
    grid = fa.NearestGrid(support_ref)
    for i, k in enumerate(quar):
        w = k["pts"] @ k["pose"][:3, :3].T + k["pose"][:3, 3]
        sub = w[:: max(1, len(w) // 400)]
        d = grid.query(sub, max_r=2.0)
        fracs.append(float(np.mean(d <= 1.0)))
    fracs = np.asarray(fracs)
    return {
        "label": label,
        "onset_rel_s": round(float(onset_rel), 9),
        "pre_frames": len(pre),
        "quar_frames": len(quar),
        "candidate_span_s": round(float(quar_ts[-1] - quar_ts[0]), 3) if len(quar) else None,
        "ref_pts_full": int(n_full),
        "ref_pts_stride": int(step),
        "ref_pts_used": int(len(ref_pts)),
        "support_reference_points": int(len(support_ref)),
        "support_fraction_median": round(float(np.median(fracs)), 4) if len(fracs) else None,
        "support_fraction_p10": round(float(np.percentile(fracs, 10)), 4) if len(fracs) else None,
        "frames_support_ge_0.60": int(np.sum(fracs >= 0.60)),
        "frames_support_ge_0.60_frac": round(float(np.mean(fracs >= 0.60)), 4) if len(fracs) else None,
    }


def main():
    inj, _cln, detected = gather()
    out = {"detected_onset_rel_s": round(detected, 9),
           "archived_onset_rel_s": ARCHIVED_ONSET,
           "runs": [probe(inj, ARCHIVED_ONSET, "archived_onset"),
                    probe(inj, detected, "detected_onset")]}
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
