#!/usr/bin/env python3
"""Offline evidence for `tau_info`: trigger-frame geometry and the reference-resolution floor.

Scope is §2-C of `tau_info_preregistration.md`: measure, do not decide. No threshold is touched,
no host is run, and every number carries its source (run id, frame stamp, bag, command).

Two questions:

  1. What geometry did each trigger frame have? Recompute the 6-DoF point-to-plane FIM on the
     *same* cloud the node saw (message points, non-finite dropped, strided to the node's
     SCAN_CAP), and check that it reproduces the `weak_dir_info_before` the run recorded. If it
     does, the chain from "bag scan" to "gate number" is verified rather than assumed; if it does
     not, the mismatch is reported instead of being explained away.

  2. How much information survives when the cloud is sampled no finer than the reference? The
     trusted reference is spatially sampled (0.5 m voxels for the ICP search; `support_reference`
     uses 0.3 m). Resampling the trigger cloud at those pitches gives the information a frame
     still carries at reference resolution -- the quantity `tau_abs_min` would have to respect.

    python3 -B docs/review_20261110_b10/tau_info_evidence/run_tau_info_offline.py
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_B10 = os.path.dirname(_HERE)
_REPO = os.path.dirname(os.path.dirname(_B10))
for _p in (_HERE, _B10, _REPO, os.path.join(_REPO, "docs", "review_20261109_bbc3dcb")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import verify_four_arm_independent as V          # noqa: E402
from slam_recovery.core import transport_information   # noqa: E402
from slam_recovery.validation import compute_6dof_point_to_plane_fim  # noqa: E402

BAG = "/tmp/fastlivo/room02_2x2_O.bag"
OUT = os.path.join(_HERE, "tau_info_offline_results.json")
SCAN_CAP = 6000          # slam_recovery/ros/recovery_node.py: SCAN_CAP
FIM_SIGMA = 0.075        # the node's FIM noise scale, both for before and after
VOXEL_PITCHES = (1.0, 0.5, 0.3)   # 0.5 = ICP search grid; 0.3 = support_reference pitch
# The live loop paired a pose with a scan inside 40 ms; the trigger stamp is the pose stamp, so the
# same window is the honest rule for finding "the scan that frame was built from".
MATCH_WINDOW_NS = 40_000_000

# One run per trigger class. The classes differ in when the detector fired, not in the bag.
RUNS = {
    "early_start": "/tmp/fl_native_20261110T030656Z_2938083",
    "injection_onset": "/tmp/fl_native_20261110T044830Z_3036955",
}


def _subsample(pts: np.ndarray, cap: int) -> np.ndarray:
    if len(pts) <= cap:
        return pts
    step = max(1, len(pts) // cap)
    return pts[::step][:cap]


def load_clouds(path: str) -> dict:
    """{header stamp ns: (N, 3) float64}, identical preprocessing to the live node."""
    out = {}
    with V.Reader(path) as r:
        conns = [c for c in r.connections if c.topic == V.SCAN_TOPIC]
        for conn, _t, raw in r.messages(connections=conns):
            m = V.TYPESTORE.deserialize_ros1(raw, conn.msgtype)
            a = np.frombuffer(np.asarray(m.data, dtype=np.uint8).tobytes(), dtype=V._cloud_dtype(m))
            p = np.column_stack([a["x"], a["y"], a["z"]]).astype(np.float64)
            p = p[np.isfinite(p).all(axis=1)]
            ns = int(m.header.stamp.sec) * 10 ** 9 + int(m.header.stamp.nanosec)
            out[ns] = p
    return out


def voxel_sample(pts: np.ndarray, pitch: float) -> np.ndarray:
    """One point per occupied voxel -- the same rule the reference uses."""
    if len(pts) == 0:
        return pts
    q = np.floor(pts / pitch).astype(np.int64)
    _, first = np.unique(q, axis=0, return_index=True)
    return pts[np.sort(first)]


def fim_summary(pts: np.ndarray) -> dict:
    fim, cov, min_r, min_t, weak = compute_6dof_point_to_plane_fim(
        pts, sigma_meas_m=FIM_SIGMA)
    w = np.asarray(weak, dtype=np.float64)
    info = float(w @ fim @ w)
    return {
        "points": int(len(pts)),
        "fim_diag": [float(fim[i, i]) for i in range(6)],
        "fim_min_eig": float(np.min(np.linalg.eigvalsh(0.5 * (fim + fim.T)))),
        "fim_max_eig": float(np.max(np.linalg.eigvalsh(0.5 * (fim + fim.T)))),
        "min_eig_rot": float(min_r),
        "min_eig_trans": float(min_t),
        "weak_direction_6d": [float(x) for x in w],
        "weak_dir_info_body": info,
        "cov_norm_2": float(np.linalg.norm(cov, ord=2)),
    }


def main() -> int:
    clouds = load_clouds(BAG)
    print(f"[] bag frames {len(clouds)} from {BAG}")
    res = {
        "protocol": "offline recomputation for tau_info §2-C; no host run, no threshold change",
        "bag": {"path": BAG, "sha256": V._sha_file(BAG)},
        "constants": {"scan_cap": SCAN_CAP, "fim_sigma_m": FIM_SIGMA,
                      "voxel_pitches_m": list(VOXEL_PITCHES),
                      "note": "weak_dir_info is the quadratic form v^T Lambda v, invariant under "
                              "the body/world transport, so recomputing it in the body frame must "
                              "reproduce the transported value the gate used"},
        "trigger_classes": {},
    }
    bag_ns = np.asarray(sorted(clouds), dtype=np.int64)

    for label, run_dir in RUNS.items():
        sp = os.path.join(run_dir, "run_summary.json")
        if not os.path.exists(sp):
            res["trigger_classes"][label] = {"status": "UNAVAILABLE", "reason": "run summary missing",
                                             "run": os.path.basename(run_dir)}
            continue
        s = json.load(open(sp))
        ep = s["quarantine"]["episode_detail"][0]
        trig = int(ep["trigger_ts_ns"])
        j = int(np.searchsorted(bag_ns, trig))
        cand = [k for k in (j - 1, j, j + 1) if 0 <= k < len(bag_ns)]
        best = min(cand, key=lambda k: abs(int(bag_ns[k]) - trig))
        delta_ns = int(bag_ns[best]) - trig
        rec_before = None
        cp = os.path.join(run_dir, "candidates.jsonl")
        if os.path.exists(cp):
            first = json.loads(open(cp).readline())
            rec_before = first.get("weak_dir_info_before")
        entry = {
            "run": os.path.basename(run_dir),
            "sigma_meas_m": s["parameters"]["sigma_meas_m"],
            "trigger_ts_ns": trig,
            "matched_bag_stamp_ns": int(bag_ns[best]),
            "match_delta_ns": delta_ns,
            "recorded_weak_dir_info_before": rec_before,
            "sampling_levels": {},
        }
        if abs(delta_ns) > MATCH_WINDOW_NS:
            entry["status"] = "NO_MATCHING_FRAME_IN_BAG"
            res["trigger_classes"][label] = entry
            continue
        full = clouds[int(bag_ns[best])]
        node_cloud = _subsample(full, SCAN_CAP)
        base = fim_summary(node_cloud)
        entry["node_cloud"] = base
        entry["reproduces_recorded"] = (
            None if rec_before is None
            else bool(abs(base["weak_dir_info_body"] - float(rec_before))
                      <= 1e-3 * max(1.0, abs(float(rec_before))))
        )
        entry["reproduces_delta"] = (
            None if rec_before is None
            else float(base["weak_dir_info_body"] - float(rec_before))
        )
        for pitch in VOXEL_PITCHES:
            sampled = voxel_sample(node_cloud, pitch)
            lvl = fim_summary(sampled)
            lvl["pitch_m"] = pitch
            entry["sampling_levels"][f"{pitch:.1f}m"] = lvl
        res["trigger_classes"][label] = entry
        print(f"[] {label}: trigger {trig} (bag delta {delta_ns} ns), node cloud "
              f"{base['points']} pts, info {base['weak_dir_info_body']:.4f} "
              f"(recorded {rec_before}), reproduces={entry['reproduces_recorded']}")
        for k, lvl in entry["sampling_levels"].items():
            print(f"     pitch {k}: {lvl['points']:5d} pts, info {lvl['weak_dir_info_body']:.4f}, "
                  f"min_eig_rot {lvl['min_eig_rot']:.3f}, min_eig_trans {lvl['min_eig_trans']:.3f}")

    # ---- cross-class comparison --------------------------------------------------------------
    ok = {k: v for k, v in res["trigger_classes"].items() if "node_cloud" in v}
    res["summary"] = {
        "classes_measured": sorted(ok),
        "recorded_before_by_class": {k: v["recorded_weak_dir_info_before"] for k, v in ok.items()},
        "recomputed_before_by_class": {k: v["node_cloud"]["weak_dir_info_body"] for k, v in ok.items()},
        "reproduces": {k: v["reproduces_recorded"] for k, v in ok.items()},
        "info_by_pitch": {k: {p: lvl["weak_dir_info_body"]
                              for p, lvl in v["sampling_levels"].items()} for k, v in ok.items()},
        "min_eig_by_class": {k: {"min_eig_rot": v["node_cloud"]["min_eig_rot"],
                                 "min_eig_trans": v["node_cloud"]["min_eig_trans"]} for k, v in ok.items()},
    }
    if len(ok) == 2:
        a, b = (res["trigger_classes"][k]["node_cloud"] for k in sorted(ok))
        res["summary"]["cross_class_ratio"] = {
            "weak_dir_info": (max(a["weak_dir_info_body"], b["weak_dir_info_body"])
                              / max(min(a["weak_dir_info_body"], b["weak_dir_info_body"]), 1e-12)),
            "min_eig_rot": max(a["min_eig_rot"], b["min_eig_rot"]) / max(min(a["min_eig_rot"],
                                                                           b["min_eig_rot"]), 1e-12),
            "min_eig_trans": max(a["min_eig_trans"], b["min_eig_trans"])
            / max(min(a["min_eig_trans"], b["min_eig_trans"]), 1e-12),
        }

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=float)
    print(f"\nsaved {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
