#!/usr/bin/env python3
"""Stage (d) offline: re-register quarantined frames against the pre-quarantine map.

No ROS, no host run. The inputs are two archived bags that already exist:

    hall01_inj43_filtered.bag   the filtered scans (the quarantined frames' geometry)
    res_h1_inj43_filtered.bag   the host poses from that run

The reference is the world cloud of the frames before the injection window, built from the host's
own poses as they stood before the quarantine opened -- the same reference the gate uses.

Two populations are reported:

  QUARANTINE  frames at or after the injection onset, re-registered from their host pose. This is
              the candidate stage (d) would submit.
  CONTROL     the last pre-onset frames, re-registered against a reference built only from
              *earlier* pre-onset frames. Their host poses were already consistent with that
              reference, so a correct solver must barely move them. This is the check that the
              ICP is not simply drifting every scan to a local minimum.

Nothing here calls the gate. A candidate's worth is the gate's decision, not this script's.

    python3 -B docs/review_20261110_b10/run_icp_candidate_offline.py
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_HERE))
for _p in (_HERE, _REPO, os.path.join(_REPO, "docs", "review_20261109_bbc3dcb")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import verify_four_arm_independent as V          # noqa: E402
from slam_recovery.repair.pose_reregistration import (  # noqa: E402
    ICP_CONFIG, IcpConfig, build_icp_candidate, reregister_frame)

SCANS = "/tmp/fastlivo/hall01_inj43_filtered.bag"
POSES = "/tmp/fastlivo/res_h1_inj43_filtered.bag"
M0 = os.path.join(_REPO, "docs", "milestone_m0_keys.json")
OUT = os.path.join(_HERE, "icp_candidate_offline_results.json")
CONTROL_FRAMES = 10


def main() -> int:
    sha_scans = V._sha_file(SCANS)
    scans, _layout = V.load_scans(SCANS, sha_scans)
    kfs, pairing = V.pair_keyframes(scans, V.load_poses(POSES))
    m0 = json.load(open(M0, encoding="utf-8"))
    onset_ns = int(m0["injection_window"]["start_ns"])
    onset_s = onset_ns * 1e-9

    kf_ts = np.asarray([k["ts"] for k in kfs])
    pre = [k for k in kfs if k["ts"] < onset_s]
    quar = [k for k in kfs if k["ts"] >= onset_s]
    if not pre or not quar:
        raise SystemExit(json.dumps({"status": "BLOCKED",
                                     "reason": "empty pre-onset or post-onset population",
                                     "pre": len(pre), "quar": len(quar)}))

    reference = np.vstack([V.world_pts(k) for k in pre])
    print(f"[] frames {len(kfs)} (pre {len(pre)}, quarantine {len(quar)}), "
          f"reference {len(reference)} pts")
    print(f"[] onset {onset_s:.3f} s, cfg {ICP_CONFIG}")

    # ---- quarantine population ---------------------------------------------------------------
    t0 = time.perf_counter()
    init_poses = {i: k["T"] for i, k in enumerate(quar)}
    poses, results = build_icp_candidate(
        {i: k["pts"] for i, k in enumerate(quar)}, reference, init_poses)
    elapsed = time.perf_counter() - t0
    print(f"[] quarantine: {len(poses)}/{len(quar)} frames produced a candidate in {elapsed:.1f} s "
          f"({elapsed / max(len(quar), 1):.2f} s/frame)")

    # ---- control population ------------------------------------------------------------------
    # The reference excludes the control frames themselves: a frame scored against its own
    # geometry would agree by construction.
    ctrl_ref_src = pre[:-CONTROL_FRAMES] if len(pre) > CONTROL_FRAMES else pre[:1]
    ctrl_frames = pre[-CONTROL_FRAMES:]
    ctrl_ref = np.vstack([V.world_pts(k) for k in ctrl_ref_src])
    ctrl_results = []
    for i, k in enumerate(ctrl_frames):
        t1 = time.perf_counter()
        res = reregister_frame(k["pts"], ctrl_ref, k["T"])
        ctrl_results.append({"frame": i, "seconds": time.perf_counter() - t1,
                             **res.as_dict()})
    print(f"[] control: reference {len(ctrl_ref)} pts from {len(ctrl_ref_src)} frames, "
          f"{len(ctrl_results)} frames")

    def _agg(rows):
        ok = [r for r in rows if r["status"] in ("CONVERGED", "ITERATION_LIMIT")]
        if not ok:
            return {"n": 0}
        conv = [r for r in ok if r["status"] == "CONVERGED"]
        disp = np.asarray([r["displacement_from_init_m"] for r in ok])
        res = np.asarray([r["icp_residual"] for r in ok])
        it = np.asarray([r["icp_iterations"] for r in ok])
        inl = np.asarray([r["icp_inliers"] for r in ok])
        return {"n": len(ok), "converged": len(conv),
                "converged_fraction": len(conv) / len(ok),
                "iterations_median": float(np.median(it)), "iterations_max": int(it.max()),
                "residual_median_m": float(np.median(res)),
                "residual_p90_m": float(np.percentile(res, 90)),
                "inliers_median": float(np.median(inl)),
                "displacement_median_m": float(np.median(disp)),
                "displacement_p90_m": float(np.percentile(disp, 90)),
                "displacement_max_m": float(disp.max()),
                "statuses": {s: sum(1 for r in rows if r["status"] == s)
                             for s in sorted({r["status"] for r in rows})}}

    quarantine_rows = []
    for i, k in enumerate(quar):
        row = {"frame": i, "ts": float(k["ts"]), "host_pose_src": k["src"]}
        row.update(next(r for j, r in results if j == i).as_dict())
        quarantine_rows.append(row)

    payload = {
        "protocol": "stage (d) pose-level re-registration, offline, frozen §9 parameters",
        "inputs": {"scans": {"path": SCANS, "sha256": sha_scans},
                   "poses": {"path": POSES, "sha256": V._sha_file(POSES)},
                   "onset_ns": onset_ns,
                   "onset_source": os.path.relpath(M0, _REPO)},
        "config": {k: getattr(ICP_CONFIG, k) for k in ICP_CONFIG.__dataclass_fields__},
        "pairing": pairing,
        "populations": {
            "quarantine": {"frames": len(quar), "reference_points": int(len(reference)),
                           "reference_frames": len(pre),
                           "reference_definition": "world cloud of every frame before the "
                                                   "injection onset, built from the host poses"},
            "control": {"frames": len(ctrl_frames),
                        "reference_frames": len(ctrl_ref_src),
                        "reference_points": int(len(ctrl_ref)),
                        "reference_definition": "pre-onset frames excluding the last "
                                                f"{CONTROL_FRAMES}",
                        "expectation": "the host pose is already consistent with this reference, "
                                       "so a correct solver moves each frame by millimetres"},
        },
        "summary": {"quarantine": _agg(quarantine_rows),
                    "control": _agg(ctrl_results),
                    "quarantine_seconds_total": elapsed},
        "candidates": quarantine_rows,
        "control": ctrl_results,
        "cannot_answer": [
            "this does not run in the live loop: the closed loop still quarantines 2 s into a run "
            "because of the NIS scale, so a candidate produced there would not be about the "
            "injection window",
            "it does not say whether a candidate should be committed; that is the gate's decision",
            "it does not establish that ICP helps: the control shows the solver does not drift, "
            "and the quarantine arm shows what it produces, but neither is an accuracy label",
        ],
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, default=float)

    for name in ("quarantine", "control"):
        s = payload["summary"][name]
        if not s.get("n"):
            print(f"[] {name}: NO RESULT")
            continue
        print(f"[] {name}: n={s['n']} conv={s['converged']} ({s['converged_fraction']:.0%}) "
              f"iters med {s['iterations_median']:.0f}/max {s['iterations_max']} "
              f"residual med {s['residual_median_m']*100:.2f} cm p90 {s['residual_p90_m']*100:.2f} "
              f"cm | moved med {s['displacement_median_m']*100:.2f} cm "
              f"p90 {s['displacement_p90_m']*100:.2f} cm max {s['displacement_max_m']*100:.2f} cm "
              f"| statuses {s['statuses']}")
    print(f"saved {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
