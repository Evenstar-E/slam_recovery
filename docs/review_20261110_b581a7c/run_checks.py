"""Check gated wait diagnostics without changing manager semantics; no native run."""
from contextlib import redirect_stdout
from decimal import Decimal
import io
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
TARGET = "b581a7c155d8d4ca18b3590eb4332d86e68afb66"
path = "slam_recovery/quarantine/manager.py"
expected = subprocess.check_output(["git", "-C", str(ROOT), "show", f"{TARGET}:{path}"])
assert (ROOT / path).read_bytes().replace(b"\r\n", b"\n") == expected
sys.path.insert(0, str(ROOT))
from slam_recovery.sim.transaction_manager_node import OnlineRecoveryTransactionNode
from slam_recovery.tests.test_lifecycle_rearm import _open_waiting_segment

observations = []
for enabled in [False, True]:
    capture = io.StringIO()
    with patch.dict(os.environ):
        os.environ.pop("SLAM_RECOVERY_WAITDIAG", None)
        if enabled:
            os.environ["SLAM_RECOVERY_WAITDIAG"] = "1"
        with redirect_stdout(capture):
            node = OnlineRecoveryTransactionNode(wait_limit_sec=2.)
            _open_waiting_segment(node.tx_mgr)
            node.tx_mgr.register_quarantined_frame(1, 1_000_000_000)
            assert node.tx_mgr.maybe_close_waiting_segment(1_000_000_000) is None
            assert node.tx_mgr.maybe_close_waiting_segment(2_005_000_000) is not None
    text = capture.getvalue()
    assert bool(text) == enabled
    if enabled:
        assert "validate_enter" in text and "wait_started_set(mode3)" in text
        assert "close_check#2" in text
    observations.append({"enabled": enabled, "state": node.tx_mgr.state.value,
                         "wait_started_after_close": node.tx_mgr.wait_started_ns,
                         "closed_ns": node.tx_mgr.lifecycle_events[-1]["closed_ns"],
                         "diagnostic_lines": len(text.splitlines())})
assert observations[0]["state"] == observations[1]["state"]
print(json.dumps({
    "target": TARGET,
    "scope": "Source-bound local diagnostics on/off controls and reported time arithmetic; no native/ROS/bag/tuning",
    "diagnostic_gate": {"status": "PASS_LOCAL", "observations": observations},
    "report_arithmetic": {
        "ack_to_validate_wall_s": str(Decimal("1794310114.969131") - Decimal("1794310079.327")),
        "reported_tail_minus_deadline_bag_s": str(Decimal("35.63") - Decimal("17.08")),
        "limit": "A gap does not establish an overlapping decision block; raw command/ack/deadline-reached/service records missing",
    },
    "driver_change": "NONE_IN_THIS_REVISION",
    "snapshot_causality": "DEVELOPER_REPORTED_NOT_INDEPENDENTLY_ESTABLISHED",
    "native_full_two_event": "NOT_COMPLETED",
    "publication": "LOCAL_ONLY_PRIOR_PUSH_DENIAL_NOT_RETRIED",
}, ensure_ascii=False, indent=2))
