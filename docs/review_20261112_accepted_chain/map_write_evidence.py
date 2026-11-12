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
import os
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

# Prefer the driver's recorded receipt time for the resume: after the outbox fix the driver
# accounts for every state command, and its ledger is not overwritten by later snapshots. Fall
# back to the command directory's receipt for runs from before that fix.
resume_ev = next((e for e in events if e.get("command") == "resume"), None)
if resume_ev is not None and resume_ev.get("received_wall") is not None:
    resume_wall = float(resume_ev["received_wall"])
    resume_source = "native_checkpoint_events.resume.received_wall"
else:
    recv = open(f"{RUN}/host_control/ack_received", encoding="utf-8").read().split()
    resume_wall = float(next(p.split("=", 1)[1] for p in recv if p.startswith("wall=")))
    resume_source = "host_control/ack_received"

a, b = index_at(hold_done), index_at(resume_wall)
out = {
    "method": "count of '[ LIO ] Update Voxel Map' lines between timestamped INFO anchors",
    "boundaries": {"hold_applied_wall": hold_done, "resume_received_wall": resume_wall,
                   "resume_time_source": resume_source},
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
    # The command directory keeps only the last ack, and the last command may have timed out;
    # after the outbox fix the driver's ledger always has the resume ack.
    "host_ack_at_resume": (
        open(f"{RUN}/host_control/ack", encoding="utf-8").read().strip()
        if os.path.exists(f"{RUN}/host_control/ack")
        else (resume_ev or {}).get("ack")),
    "reprocess_log_lines": count(0, len(lines), "[NATIVE_CHECKPOINT] reprocess #"),
}
json.dump(out, open(f"{RUN}/map_write_evidence.json", "w"), indent=1)
print(json.dumps(out, indent=1))
