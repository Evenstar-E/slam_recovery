"""Attribute paired native outcomes from the refusal replay actually consumed by the host."""

from collections import Counter
import json
from pathlib import Path


def summarize_refusal_comparison(path: Path, checkpoint_ns: int, target_ns: int,
                                 expected: int) -> dict:
    trace = {"checkpoint_ns": checkpoint_ns, "target_ns": target_ns,
             "expected_groups": expected}
    branches = {"native": {}, "refusal": {}}
    try:
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                row = json.loads(line)
                if row["checkpoint_ns"] != checkpoint_ns or row["target_ns"] != target_ns:
                    continue
                groups = branches[row["branch"]]
                group = (row["scan_ns"], row["end_ns"])
                if group in groups:
                    return {**trace, "status": "DUPLICATE_GROUP", "branch": row["branch"],
                            "scan_ns": group[0], "group_end_ns": group[1]}
                groups[group] = row["result"]
    except (OSError, ValueError, KeyError, TypeError):
        return {**trace, "status": "RECEIPT_UNAVAILABLE"}

    native, refusal = branches["native"], branches["refusal"]
    native_reset = [start for (start, _), state in native.items() if state == "native_reset_due"]
    trace.update(native_groups=len(native), refusal_groups=len(refusal),
                 native_reset_scan_ns=native_reset[0] if native_reset else None,
                 native_outcomes=dict(Counter(native.values())),
                 refusal_outcomes=dict(Counter(refusal.values())))
    if len(refusal) != expected or not set(native).issubset(refusal):
        return {**trace, "status": "UNMATCHED_INPUT"}

    joint = Counter()
    for group, state in refusal.items():
        if group not in native:
            joint["native_unmeasured"] += 1
        elif state == "imu_only":
            joint["protected_imu_only"] += 1
        else:
            raw_tracks = native[group] == "lidar_tracking"
            refusal_tracks = state == "lidar_tracking"
            if raw_tracks and refusal_tracks:
                joint["both_lidar_tracking"] += 1
            elif not raw_tracks and not refusal_tracks:
                joint["both_tracking_unavailable"] += 1
            elif refusal_tracks:
                joint["only_refusal_lidar_tracking"] += 1
            else:
                joint["only_native_lidar_tracking"] += 1
    return {**trace, "status": "NATIVE_STOPPED_EARLY" if native_reset else
            ("COMPARED" if len(native) == expected else "NATIVE_INCOMPLETE"),
            "matched_outcomes": dict(joint)}
