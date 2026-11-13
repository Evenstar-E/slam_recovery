#!/usr/bin/env python3
"""Regression assertion over the ctrl2 originals: the replay/live split must be 83/899.

The v2 host kept `g_nr_replay` set after the replay queue drained, so every later live frame was
labelled `replayed`. The corrected host decides per group (marks written when the replay is
queued) and clears the flag when the last replayed group has been processed. This checker
validates that reading against the archived run without touching the host:

  declared replay = the `replay_within_end` from the reprocess ack (83),
  live afterwards = the remaining frames that carry the same (wrong) label (899).

Usage: check_replay_regression.py <ctrl2 run dir>
"""
import json
import os
import re
import sys

run = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(__file__)) + "/ctrl2"
fates_path = os.path.join(run, "ctl", "input_fates.jsonl")
cmds_path = os.path.join(run, "commands.log")
rows = [json.loads(l) for l in open(fates_path) if l.strip()]
ack = open(cmds_path).read()
m = re.search(r"replay_within_end=(\d+)", ack)
declared = int(m.group(1)) if m else None
replayed = [r for r in rows if r["fate"] == "replayed"]
ok = True
print(f"rows={len(rows)} replayed_label={len(replayed)} declared_replay={declared}")
if declared is None:
    print("FAIL: no replay_within_end in commands.log")
    ok = False
else:
    live_after = len(replayed) - declared
    print(f"corrected_split: replay={declared} live={live_after}")
    ok = (len(rows) == 1255 and len(replayed) == 982 and declared == 83 and live_after == 899)
print("PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
