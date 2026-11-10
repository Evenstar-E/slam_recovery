#!/usr/bin/env python3
"""Normal node covariance/gauge probe for fixed source 21fa650; no native host run.

python -B -W ignore docs/review_20261110_21fa650/a7_node_cov_probe.py

The detector is not evaluated: trigger_quarantine controls the event entry so only
candidate production and admission are compared. Support, holdout, paired benefit,
FIM production, gate, and transaction commit use the actual node implementations.
A zero exit means the reported mode-flip counterexample was reproduced, not A7 PASS.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import numpy as np

from slam_recovery.core import GateThresholds, TangentFrame
from slam_recovery.sim.transaction_manager_node import OnlineRecoveryTransactionNode

SOURCE = "21fa6506f8b1c63f95b135f7052b2fb84ea7c9c3"
SOURCE_FILES = (
    "slam_recovery/core.py",
    "slam_recovery/sim/transaction_manager_node.py",
    "slam_recovery/validation/fim_and_holdout.py",
)


def git(*args):
    return subprocess.check_output(
        ["git", "-C", str(ROOT), *args], text=True, encoding="utf-8"
    ).strip()


def run_case(cloud, world_y):
    node = OnlineRecoveryTransactionNode()
    T = np.eye(4)
    T[1, 3] = world_y
    node.scan_buffer_body[0] = cloud.copy()
    node.tx_mgr.trusted_poses[0] = T.copy()
    node._sync_spatial_map_with_trusted_poses()
    body = TangentFrame("body", "rot_trans", "scan:7")
    node.tx_mgr.trigger_quarantine(
        0, 4_000_000_000,
        np.array([0, 0, 0, 1, 0, 0.]),
        np.diag([60, 60, 60, 20, 40, 40.]), .1,
        weak_direction_frame=body, info_before_frame=body,
        anchor_pose_world=T,
    )
    candidate, incumbent = {}, {}
    for k in (1, 2, 3, 4):
        node.scan_buffer_body[k] = cloud.copy()
        node._kf_timestamps[k] = k * 100_000_000
        node.tx_mgr.register_quarantined_frame(k, k * 100_000_000)
        candidate[k] = T.copy()
        incumbent[k] = T.copy()
        incumbent[k][0, 3] += .12
    report = node.evaluate_and_commit_candidate(
        "realnode", candidate, incumbent_poses=incumbent,
        reentry_anchor_pose=T,
    )
    return {
        "world_y_m": world_y,
        "weak_dir_info_before": report.weak_dir_info_before,
        "weak_dir_info_after": report.weak_dir_info_after,
        "posterior_cov_norm": report.posterior_cov_norm,
        "holdout_nis": report.holdout_nis,
        "mode": report.mode.value,
        "accepted": report.accepted,
        "paired_evidence": node.last_paired_evidence,
    }


def main():
    identity = {}
    for name in SOURCE_FILES:
        expected = git("rev-parse", f"{SOURCE}:{name}")
        loaded = git("hash-object", name)
        if loaded != expected:
            raise RuntimeError(f"Source differs from {SOURCE}: {name}")
        identity[name] = loaded
    cloud = np.random.default_rng(0).normal(size=(400, 3)) * .16
    cases = [run_case(cloud, y) for y in (0., 20.)]
    out = {
        "source_revision": SOURCE,
        "loaded_source_blobs": identity,
        "scope": "synthetic normal node path, no ROS/bag/native run",
        "detector_entry": "direct trigger_quarantine; not detector accuracy evidence",
        "gate_thresholds": vars(GateThresholds()),
        "thresholds_modified": False,
        "cases": cases,
        "mode_flip_reproduced": cases[0]["mode"] != cases[1]["mode"],
        "accepted_flip_reproduced": cases[0]["accepted"] != cases[1]["accepted"],
    }
    print(json.dumps(out, indent=2))
    return 0 if out["mode_flip_reproduced"] and out["accepted_flip_reproduced"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
