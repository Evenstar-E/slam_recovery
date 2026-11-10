"""Check the proposal's two information examples with the unchanged actual gate."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
REV = "13edd0c4bd948473310bca004398d35f09ac7f9f"
for relative in ("slam_recovery/core.py", "slam_recovery/tests/test_transaction_normal_path.py"):
    expected = subprocess.check_output(["git", "-C", str(ROOT), "show", f"{REV}:{relative}"])
    actual = (ROOT / relative).read_bytes().replace(b"\r\n", b"\n")
    assert hashlib.sha256(expected).digest() == hashlib.sha256(actual).digest(), relative
sys.path.insert(0, str(ROOT))
from slam_recovery.core import evaluate_four_mode_gate
from slam_recovery.quarantine import TrustedMapTransactionManager
from slam_recovery.tests.test_transaction_normal_path import _candidate, _delta, _trigger

rows = []
for before, after in ((40.23, 34.47), (1.1019, 4.4701)):
    manager = TrustedMapTransactionManager(confirmation_margin_ns=0)
    for k in (1, 2, 3):
        manager.step_healthy(_delta(k, k * 100_000_000, .1 * k))
    segment = _trigger(manager, 200_000_000, 300_000_000)
    segment.info_before_6x6 = np.eye(6) * before
    candidate = _candidate(segment.checkpoint.map_version, {2: np.eye(4)})
    candidate.info_after_6x6 = np.eye(6) * after
    report = evaluate_four_mode_gate(segment, candidate)
    assert not report.accepted
    rows.append({
        "before": report.weak_dir_info_before, "after": report.weak_dir_info_after,
        "gain": report.weak_dir_info_gain, "absolute_information_leg": after >= 25,
        "accepted": report.accepted, "mode": report.mode.value,
        "evidence_status": report.evidence_status,
    })
print(json.dumps({"target": REV, "thresholds_modified": False,
                  "scope": "synthetic actual gate, reuse positive candidate fixture; no ROS",
                  "rows": rows}, indent=2))
