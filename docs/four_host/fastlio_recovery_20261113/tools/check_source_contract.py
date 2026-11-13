#!/usr/bin/env python3
"""Source-level contract checks for the FAST-LIO native recovery host (no build, no run).

Each assertion pins a property the review asked for, so a later edit that silently moves a call
site fails here instead of during a scarce chain run.
"""
import re
import sys

SRC = sys.argv[1] if len(sys.argv) > 1 else "/home/R26534/fastlio2_ws/src/FAST-LIO/src/laserMapping.cpp"
s = open(SRC).read()
line = lambda pat: s[: s.index(pat)].count("\n") + 1 if pat in s else -1
checks = []

def check(name, ok, detail=""):
    checks.append((name, bool(ok), detail))

# 1. deferred application happens after sync_packages and before capture/estimation
i_sync = line("if (sync_packages(Measures))")
i_defer = line("nr_apply_deferred(lidar_end_time);")
i_capture = line("nr_capture_group();")
check("deferred called after sync_packages", i_defer > i_sync, f"sync={i_sync} defer={i_defer}")
check("deferred called before group capture", 0 < i_defer < i_capture, f"defer={i_defer} capture={i_capture}")
# the old top-of-loop call must be gone
check("no pre-sync deferred call", s.count("nr_apply_deferred();") == 0)

# 2. two-level ack
check("enqueue ack says deferred", '" deferred stamp="' in s)
check("executed hold ack says applied", '"OK hold applied valid=1' in s)
check("executed snapshot ack says applied", '"OK snapshot applied valid=1' in s)

# 3. reprocess releases hold and carries repaired_fed
check("reprocess releases hold", "g_nr_hold.store(false);" in s)
check("reprocess ack has repaired_fed", 'repaired_fed=' in s)

# 4. per-group replay identity + update-linked receipt
check("replay marks written on push", "g_nr_replay_marks[gkey] = true;" in s)
check("identity taken on capture", "g_nr_cur_is_replay = g_nr_replay_marks.erase(key) > 0;" in s)
check("fate uses per-group identity", 'g_nr_cur_is_replay ? "replayed"' in s)
check("repaired_in_update exposed", "repaired_in_update=" in s and "g_nr_repaired_in_update" in s)
check("replay flag reset when drained", "g_nr_replay.store(false);" in s and "g_nr_replay_remaining" in s)

# 5. snapshot uses the previous completed frame's time base
check("snapshot stamp from last completed frame", "g_nr_cp.stamp = g_nr_lidar_end;" in s)

bad = [c for c in checks if not c[1]]
for name, ok, detail in checks:
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""))
print("RESULT", "PASS" if not bad else f"FAIL ({len(bad)})")
sys.exit(0 if not bad else 1)
