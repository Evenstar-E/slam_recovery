"""Small source-pinned classification control; no ROS or native execution."""
import ast
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
TARGET = "d5f7d8f81a0aa8522d943649301aecd4fb636e82"
SCRIPT = "slam_recovery/ros/smoke_repair.sh"
PATCH = "docs/review_20261110_native_checkpoint/fastlivo2_worktree.diff"


def blob(path):
    return subprocess.check_output(["git", "-C", str(ROOT), "show", f"{TARGET}:{path}"])


source = blob(SCRIPT).decode("utf-8")
working = (ROOT / SCRIPT).read_text(encoding="utf-8")
assert working == source.replace("\r\n", "\n"), "Working script differs from reviewed revision"
embedded = source.split("<<'PYEOF'\n", 1)[1].split("\nPYEOF", 1)[0]
tree = ast.parse(embedded)
assignments = [
    node for node in tree.body
    if isinstance(node, ast.Assign)
    and any(isinstance(t, ast.Name) and t.id in {"before", "after", "inside"} for t in node.targets)
]
assert len(assignments) == 3
classification = compile(ast.Module(body=assignments, type_ignores=[]), SCRIPT, "exec")


def classify(cp):
    # These are synthetic seconds, not timestamps from the reported native run.
    scope = {"stamps": [int(s * 1e9) for s in [9, 11, 13, 15]], "cp": cp, "lo": 12, "hi": 14}
    exec(classification, scope)
    return {k: [s / 1e9 for s in scope[k]] for k in ["before", "after", "inside"]}


with_checkpoint = classify(10)
without_checkpoint = classify(None)
assert with_checkpoint == {"before": [9.0], "after": [15.0], "inside": [11.0, 13.0]}
assert without_checkpoint == {"before": [], "after": [15.0], "inside": [9.0, 11.0, 13.0]}
patch_hash = hashlib.sha256(blob(PATCH)).hexdigest()
assert patch_hash == "f5efce7160e45933f84b23c365f08b9a51798aeb9c201c4e48a5ba026e2c2f21"
result = {
    "target": TARGET,
    "scope": "Local arithmetic and extracted classification expressions; synthetic timestamps, no ROS/native/bag/tuning",
    "source_binding": "PASS_LOCAL",
    "developer_report_arithmetic": {
        "x_difference_m": str(Decimal("1.587") - Decimal("-12.644")),
        "voxel_difference": 15965 - 9400,
        "point_difference": 235542 - 189173,
        "origin": "Developer-reported values, not independently measured host results",
    },
    "classification_control": {
        "status": "COUNTEREXAMPLE_REPRODUCED_LOCAL",
        "fixture": {"published_s": [9, 11, 13, 15], "checkpoint_s": 10, "replay_span_s": [12, 14]},
        "with_checkpoint": with_checkpoint,
        "without_checkpoint": without_checkpoint,
        "limit": "Shows diagnostic boundary semantics only; does not locate the actual eight unmatched repairs",
    },
    "host_patch": {"sha256": patch_hash, "status": "UNCHANGED_OLD_PATCH"},
    "native_replay_fidelity": "BLOCKED_NO_SAME_RUN_LIVE_AND_DEPLOYED_SOURCE",
    "native_full_two_event": "BLOCKED",
    "publication": "LOCAL_ONLY: prior push denial not retried or bypassed",
}
print(json.dumps(result, ensure_ascii=False, indent=2))
