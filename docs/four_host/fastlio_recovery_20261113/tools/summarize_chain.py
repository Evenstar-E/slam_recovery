#!/usr/bin/env python3
"""Print one run's recovery chain in one view: segment -> decision -> host action -> replay.

Reads only the run's own artifacts (run_summary.json, candidates.jsonl). No inference: every
line below is a field the driver or the host wrote, and a missing field prints as MISSING rather
than being filled in.
"""
import json
import os
import sys


def _get(d, *keys, default="MISSING"):
    for k in keys:
        if not isinstance(d, dict) or k not in d:
            return default
        d = d[k]
    return d


def main(run_dir: str) -> int:
    path = os.path.join(run_dir, "run_summary.json")
    if not os.path.exists(path):
        print(f"no run_summary.json in {run_dir}")
        return 2
    s = json.load(open(path))

    print(f"run_id      {s.get('run_id')}")
    print(f"run_mode    {s.get('run_mode')}   terminal={s.get('terminal_reason')}   "
          f"final={s.get('final_state')}")
    print(f"arming      {s.get('arming_mode')}")
    print(f"candidate   {s.get('candidate_source')}   detection={s.get('detection_enabled')}")
    caps = _get(s, "host_capabilities", "semantics", default={})
    print(f"semantics   {json.dumps(caps, ensure_ascii=False)}")
    print(f"gate        {json.dumps(s.get('gate'), ensure_ascii=False)}")

    st = s.get("scripted_triggers", {})
    for f in st.get("fired", []):
        print(f"trigger     declared={f['declared_ns']} actual={f['actual_s']}s kf={f['kf_id']}")
    for a in st.get("armed_boundaries", []):
        print(f"armed       boundary={a['boundary_ns']} at_ts={a['armed_at_ts_ns']} lead={a['lead_s']}s")

    for ep in _get(s, "quarantine", "episode_detail", default=[]):
        print(f"\n-- episode {ep.get('index')} trigger={ep.get('trigger_ts_ns')} "
              f"frames={ep.get('frames_registered')}")
        for k in ("decision_skipped", "hold_skipped_host_state", "hold_armed_at_boundary",
                  "host_reset_during_quarantine", "host_signal_while_held",
                  "candidate_frames", "repaired_fed", "repair_enqueued",
                  "repaired_in_update", "repair_entered_estimator",
                  "repair_entered_estimator_reason", "replay_suffix",
                  "native_writeback", "native_writeback_skipped", "native_resume",
                  "checkpoint_check", "replay_disposition", "restore_disposition"):
            if k in ep:
                print(f"   {k}: {json.dumps(ep[k], ensure_ascii=False)[:300]}")
        if "paired_evidence" in ep:
            ev = ep["paired_evidence"]
            print(f"   evidence: improved={ev.get('num_improved_frames')}/{ev.get('num_paired_frames')} "
                  f"wilson={ev.get('wilson_lower_bound')} approved={ev.get('approved')} "
                  f"reason={ev.get('reason')}")
        if "repair_publish" in ep:
            rp = ep["repair_publish"]
            print(f"   repair: published={rp.get('published')} bias_z={rp.get('bias_z_m')} "
                  f"synced={rp.get('synced')} mad={rp.get('mad_m')}")

    print("\n-- host actions")
    for a in s.get("native_checkpoint_actions", []):
        print(f"   {a.get('command'):9s} ok={a.get('ok')} wall={a.get('wall')} "
              f"{(a.get('ack') or '')[:110]}")

    print(f"\nhost_native state={_get(s, 'host_native', 'state')} "
          f"events={len(_get(s, 'host_native', 'events', default=[]))}")
    for e in _get(s, "host_native", "events", default=[])[:20]:
        print(f"   {e['event']:14s} ts={e['ts_ns']} state={e['state']}")

    lc = s.get("lifecycle", {})
    print(f"\nlifecycle state={lc.get('state')} unresolved={lc.get('unresolved_segments')} "
          f"run_end_close={json.dumps(lc.get('run_end_close'))}")
    for ev in lc.get("events", []):
        print(f"   {ev.get('event')} {json.dumps({k: v for k, v in ev.items() if k != 'frames_unresolved'}, ensure_ascii=False)[:220]}")

    print(f"\ninput_health {json.dumps(s.get('input_health'), ensure_ascii=False)}")
    rt = s.get("runtime", {})
    print(f"runtime wall={rt.get('wall_sec')}s poses={rt.get('pose_messages')} "
          f"scans={rt.get('scan_messages')}")

    cand = os.path.join(run_dir, "candidates.jsonl")
    if os.path.exists(cand):
        print("\n-- candidates")
        for line in open(cand):
            r = json.loads(line)
            print(f"   {r.get('candidate_id')} accepted={r.get('accepted')} mode={r.get('mode')} "
                  f"committed={len(r.get('committed_pose_keys') or [])} "
                  f"refusal={(r.get('refusal_reason') or '')[:90]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "."))
