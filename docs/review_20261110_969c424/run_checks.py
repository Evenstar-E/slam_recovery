"""Version-bound report arithmetic and a synthetic matching-rule example, not native tests."""
import hashlib
import json
import math
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
TARGET = "969c424aefdf8732e0f379bc6097357fac5ccbde"
PATCH = "docs/review_20261110_native_checkpoint/fastlivo2_worktree.diff"
DRIVER = "slam_recovery/ros/recovery_node.py"


def blob(revision, path):
    return subprocess.check_output(["git", "-C", str(ROOT), "show", f"{revision}:{path}"])


patch = blob(TARGET, PATCH)
assert patch == blob("d5f7d8f", PATCH)
assert b"replay_buffer_.push_back(LidarMeasures);" in patch
assert b"LidarMeasures = replay_buffer_[i];" in patch
assert blob(TARGET, DRIVER) == blob("d5f7d8f", DRIVER)
report = blob(TARGET, "docs/review_20261110_native_checkpoint/README.md").decode("utf-8")
assert "6.604361, 9.140322, 0.114888" in report
assert "6.594110, 9.154173, 0.185198" in report
assert "6.608602, 9.176204, 0.173547" in report
live = [6.604361, 9.140322, 0.114888]
control = [6.594110, 9.154173, 0.185198]
treatment = [6.608602, 9.176204, 0.173547]

# Implement only the prose rule, using integer nanoseconds. This is NOT deployed host code.
group_raw_stamp = 100_000_000_000
group_end_stamp = 100_090_000_000
queued_repairs = [99_900_000_000]  # Previous scan; current scan's repair is absent.
eligible = [s for s in queued_repairs if 0 <= group_end_stamp - s <= 200_000_000]
selected = max(eligible) if eligible else None
assert selected == 99_900_000_000 and selected != group_raw_stamp
result = {
    "target": TARGET,
    "scope": "Source binding, developer-report arithmetic, synthetic prose-rule control; no native/ROS/bag execution",
    "published_host_patch": {
        "sha256": hashlib.sha256(patch).hexdigest(),
        "unchanged": True,
        "capture": "replay_buffer_.push_back(LidarMeasures)",
        "replay_assignment": "LidarMeasures = replay_buffer_[i]",
        "deep_copy_fix": "BLOCKED_NOT_PUBLISHED",
    },
    "driver_unchanged": True,
    "reported_distances": {
        "control_live_m": math.dist(control, live),
        "treatment_control_m": math.dist(treatment, control),
        "origin": "Developer-reported rounded positions; not independently measured and not a quality metric",
        "acceptance_tolerance": "UNDECLARED_FOR_REPLAY_FIDELITY",
    },
    "matching_control": {
        "status": "SYNTHETIC_PROSE_RULE_COUNTEREXAMPLE",
        "group_raw_stamp_ns": group_raw_stamp,
        "group_end_stamp_ns": group_end_stamp,
        "queued_repair_stamps_ns": queued_repairs,
        "selected_stamp_ns": selected,
        "same_scan": selected == group_raw_stamp,
        "limit": "Shows that count and temporal proximity alone do not prove scan identity; not an observed mismatch in the reported 20 replacements",
    },
    "host_poses_run": "NOT_ALGORITHMIC_REPAIR_EVIDENCE",
    "old_eight_frame_pass": "DEVELOPER_REQUESTED_RECHECK_NOT_YET_DELIVERED",
    "native_full_two_event": "BLOCKED",
    "publication": "LOCAL_ONLY_PRIOR_PUSH_DENIAL_NOT_RETRIED",
}
print(json.dumps(result, ensure_ascii=False, indent=2))
