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

# 3. reprocess carries repaired_fed, and does not take the driver's hold away
i_rp = s.find('else if (cmd == "reprocess")')
i_rp_end = s.find('else if (cmd == "capabilities")', i_rp)
rp_body = s[i_rp:i_rp_end] if 0 <= i_rp < i_rp_end else ""
check("reprocess ack has repaired_fed", 'repaired_fed=' in s)
check("reprocess does not clear the driver's hold", "g_nr_hold.store(false);" not in rp_body)
check("map writes stay allowed during a replay",
      "if (g_nr_hold.load() && !g_nr_cur_is_replay) return;" in s)

# 4. per-group replay identity + update-linked receipt
check("replay marks written on push", "g_nr_replay_marks[gkey] = true;" in s)
check("identity taken on capture", "g_nr_cur_is_replay = g_nr_replay_marks.erase(key) > 0;" in s)
check("fate uses per-group identity", 'g_nr_cur_is_replay ? "replayed"' in s)
check("repaired_in_update exposed", "repaired_in_update=" in s and "g_nr_repaired_in_update" in s)
check("replay flag reset when drained", "g_nr_replay.store(false);" in s and "g_nr_replay_remaining" in s)

# 5. snapshot uses the previous completed frame's time base
check("snapshot stamp from last completed frame", "g_nr_cp.stamp = g_nr_lidar_end;" in s)

# 6a. re_slam invalidates the checkpoint, and restore says why
i_rs = s.find("void re_slam()")
i_rs_end = s.find("\n}\n", i_rs) if i_rs >= 0 else -1
body = s[i_rs:i_rs_end] if i_rs >= 0 and i_rs_end > i_rs else ""
check("re_slam invalidates the checkpoint", "g_nr_cp.valid = false;" in body)
check("restore names the re_slam invalidation",
      "checkpoint_invalidated_by_re_slam" in s)
check("capabilities declares the invalidation",
      '\\"checkpoint_invalidated_by\\"' in s)

# 6b. re_slam also refuses snapshots until odometry is published again
i_pub = s.find("void publish_odometry")
i_pub_end = s.find("\n}\n", i_pub) if i_pub >= 0 else -1
pub_body = s[i_pub:i_pub_end] if i_pub >= 0 and i_pub_end > i_pub else ""
check("re_slam marks the host as reset", "g_nr_host_reset = true;" in body)
check("snapshot refuses while reset", "host_reset_no_map" in s)
check("publish clears the reset flag", "g_nr_host_reset = false;" in pub_body)
check("capabilities declares the snapshot refusal",
      '\\"snapshot_refused_after_host_reset\\"' in s)

# 6c. capabilities carries the contract block the driver's --require-contract validates
check("capabilities declares semantics.apply_stamp", '\\"apply_stamp\\": \\"YES\\"' in s)
check("capabilities declares both ack levels",
      '\\"ack_levels\\": [\\"deferred\\", \\"applied\\"]' in s)
check("capabilities declares checkpoint validity",
      '\\"checkpoint_validity\\": \\"until_re_slam\\"' in s)
check("capabilities declares publish gating", '\\"publish_gating\\": \\"isPublish+held\\"' in s)
check("capabilities declares the profile", '\\"profile\\": \\"native_recovery\\"' in s)
check("capabilities declares the reset policy under hold",
      '\\"native_reset_under_hold\\": \\"deferred\\"' in s)

# 6d. a held host defers its native reset instead of invalidating the driver's checkpoint
i_deg = s.find("if( degradation_count > 1)")
i_deg_end = s.find("}else{", i_deg) if i_deg >= 0 else -1
deg_body = s[i_deg:i_deg_end] if 0 <= i_deg < i_deg_end else ""
check("degeneracy path checks the external hold", "if (g_nr_hold.load())" in deg_body)
check("held host counts the deferred reset", "++g_nr_deferred_resets;" in deg_body)
check("held host does not call re_slam",
      "re_slam();" in deg_body and deg_body.find("re_slam();") > deg_body.find("g_nr_hold.load()"))
check("status exposes the deferred resets", '" deferred_resets="' in s)

# 6e. a held host keeps publishing so the driver's window can span the degeneracy
check("publication gate widened while held",
      "if(isPublish || g_nr_hold.load()){" in s)
check("capabilities declares publish-while-held",
      '\\"publish_while_held\\": \\"YES\\"' in s
      and '\\"publish_gating\\": \\"isPublish+held\\"' in s)

# 6. the deferred queue is FIFO and executes every due entry (two commands can share one stamp)
check("deferred queue is a deque", "std::deque<NrDeferred> g_nr_deferred;" in s)
check("deferred enqueue is push_back", "g_nr_deferred.push_back(std::move(d));" in s)
check("deferred apply pops the front", "g_nr_deferred.pop_front();" in s)
check("deferred loop drains all due (<= now)",
      "while (!g_nr_deferred.empty() && g_nr_deferred.front().stamp_ns <= now_ns)" in s)
check("deferred executes in queue order",
      "for (auto& d : due) nr_execute(d.cmd, d.payload);" in s)

bad = [c for c in checks if not c[1]]
for name, ok, detail in checks:
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""))
print("RESULT", "PASS" if not bad else f"FAIL ({len(bad)})")
sys.exit(0 if not bad else 1)
