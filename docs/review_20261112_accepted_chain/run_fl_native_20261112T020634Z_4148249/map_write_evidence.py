#!/usr/bin/env python3
"""Count the host's own map-update prints before, during and after the hold.

`[ LIO ] Update Voxel Map` is emitted inside UpdateVoxelMap, which handleLIO skips while
``map_hold_`` is true. So the print is a direct witness of whether frames wrote the map, and the
hold interval should contain none while still containing LIO frames that were processed and not
written.

The stdout lines carry no timestamps, so line positions are anchored on the ROS INFO lines that
do. Boundaries come from the command ledger (hold ack wall, resume receipt wall).
"""
import json
import re
import sys

RUN = sys.argv[1] if len(sys.argv) > 1 else "."
lines = open(f"{RUN}/host.log", errors="ignore").read().splitlines()

anchors = []
for i, line in enumerate(lines):
    m = re.search(r"\[ INFO\] \[([0-9.]+)\]", line)
    if m:
        anchors.append((i, float(m.group(1))))


def index_at(wall):
    """Last line index whose timestamp is at or before `wall`."""
    idx = 0
    for i, t in anchors:
        if t <= wall:
            idx = i
        else:
            break
    return idx


def count(lo, hi, needle):
    return sum(1 for i in range(lo, hi) if needle in lines[i])


events = json.load(open(f"{RUN}/native_checkpoint_events.json"))
hold = next(e for e in events if e.get("command") == "hold")
hold_done = float(hold.get("ack_wall") or hold.get("received_wall"))

# The resume's receipt wall survives in the command directory even though the driver's pending
# queue never reached it; that file is the only wall-clock record of when the host took it.
recv = open(f"{RUN}/host_control/ack_received", encoding="utf-8").read().split()
resume_wall = float(next(p.split("=", 1)[1] for p in recv if p.startswith("wall=")))

a, b = index_at(hold_done), index_at(resume_wall)
out = {
    "method": "count of '[ LIO ] Update Voxel Map' lines between timestamped INFO anchors",
    "boundaries": {"hold_applied_wall": hold_done, "resume_received_wall": resume_wall},
    "line_index": {"hold": a, "resume": b, "end": len(lines)},
    "update_voxel_map": {
        "before_hold": count(0, a, "Update Voxel Map"),
        "during_hold": count(a, b, "Update Voxel Map"),
        "after_resume": count(b, len(lines), "Update Voxel Map"),
    },
    "lio_frames_processed": {
        "before_hold": count(0, a, "Raw feature num"),
        "during_hold": count(a, b, "Raw feature num"),
        "after_resume": count(b, len(lines), "Raw feature num"),
    },
    "host_ack_at_resume": open(f"{RUN}/host_control/ack", encoding="utf-8").read().strip(),
    "reprocess_log_lines": count(0, len(lines), "[NATIVE_CHECKPOINT] reprocess #"),
}
json.dump(out, open(f"{RUN}/map_write_evidence.json", "w"), indent=1)
print(json.dumps(out, indent=1))
