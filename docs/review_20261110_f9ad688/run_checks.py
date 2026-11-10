"""Reuse prior boundary integration fixture against f9ad688; no native run or algorithm edits."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

loader = unittest.TestLoader()
suite = unittest.TestSuite([
    loader.loadTestsFromName("slam_recovery.tests.test_transaction_normal_path.ReentryEvidenceLegTest"),
    loader.loadTestsFromName("slam_recovery.tests.test_commit_evidence_coverage"),
    loader.loadTestsFromName("slam_recovery.tests.test_a7_tangent_frames"),
])
result = unittest.TextTestRunner(verbosity=2).run(suite)
if not result.wasSuccessful():
    raise SystemExit(1)

old_probe = ROOT / "docs/review_20261110_bcadd9f/boundary_integration_probe.py"
source = old_probe.read_text(encoding="utf-8")
source = source.replace(
    "bcadd9f6a03846589ef5a3ae73309c977f6d97c4",
    "f9ad688b42cca607a35b766634b0e7a5a3a5f9f9",
)
source = source.replace(
    'assert rows[0]["evidence_status"] == "FAILED" and not rows[0]["accepted"]',
    'assert rows[0]["evidence_status"] == "PASSED" and not rows[0]["accepted"]',
)
source = source.replace(
    "PASS means remaining duplicate raw-distance refusal reproduced, not fixed/full gate PASS",
    "PASS means previous duplicate raw-distance refusal removed; fixture remains Mode3 due to covariance, not full gate PASS",
)
exec(compile(source, str(old_probe), "exec"), {"__file__": str(old_probe), "__name__": "__main__"})
