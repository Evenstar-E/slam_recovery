#!/usr/bin/env python3
"""Per-segment checkpoint-candidate table for a run with cp_history_k > 1.

Reads <run>/run_summary.json. Every host ack carries the checkpoint slot at apply time:
  ... stamp_ns=<active> ... hist_k=K hist_bytes=B hist=<stamp_ns:frame:voxels:points;...>
`hist` lists the retained snapshots older than the active one. For each segment
(lifecycle.checkpoint_checks) this prints:

  boundary            the segment's quarantine_start_ns
  actual              the checkpoint the host used (stamp_ns of the matching ack)
  candidates <= boundary   how many of {active + hist} are at or before the boundary
  latest <= boundary  the newest such checkpoint, and how far before the boundary it is
  status              the driver's AT_OR_BEFORE_BOUNDARY / LATE_AFTER_BOUNDARY

Usage: analyze_cp_candidates.py <run_dir>
"""
import json
import sys


def parse_ack(ack):
    out = {"hist": []}
    for tok in ack.split():
        if tok.startswith("stamp_ns="):
            out["stamp_ns"] = int(tok.split("=", 1)[1])
        elif tok.startswith("frame="):
            out["frame"] = int(tok.split("=", 1)[1])
        elif tok.startswith("hist_k="):
            out["hist_k"] = int(tok.split("=", 1)[1])
        elif tok.startswith("hist_bytes="):
            out["hist_bytes"] = int(tok.split("=", 1)[1])
        elif tok.startswith("hist="):
            for e in tok.split("=", 1)[1].split(";"):
                if not e:
                    continue
                s, f, v, p = e.split(":")
                out["hist"].append({"stamp_ns": int(s), "frame": int(f),
                                    "voxels": int(v), "points": int(p)})
    return out


def main(run_dir):
    s = json.load(open(run_dir + "/run_summary.json"))
    checks = (s.get("lifecycle") or {}).get("checkpoint_checks") or []
    acks = [parse_ack(a.get("ack", ""))
            for a in (s.get("lifecycle") or {}).get("native_checkpoint_actions") or []
            if a.get("ack") and "stamp_ns=" in a.get("ack", "")]
    print(f"{'ep':>2} {'boundary_ns':>19} {'actual_ns':>19} {'status':<22} "
          f"{'cand<=b':>7} {'latest<=b':>19} {'delta_s':>8}  candidates")
    for i, c in enumerate(checks):
        b = c.get("boundary_stamp_ns")
        actual = c.get("actual_stamp_ns")
        ack = next((a for a in acks if a.get("stamp_ns") == actual), None)
        cands = []
        if ack:
            cands = ack["hist"] + [{"stamp_ns": ack["stamp_ns"], "frame": ack.get("frame", -1)}]
        legal = [x for x in cands if b is not None and x["stamp_ns"] <= b]
        latest = max(legal, key=lambda x: x["stamp_ns"]) if legal else None
        delta = (None if latest is None else round((b - latest["stamp_ns"]) / 1e9, 3))
        cand_s = ",".join(f"{x['stamp_ns']}:f{x.get('frame', -1)}" for x in cands)
        print(f"{i:>2} {str(b):>19} {str(actual):>19} {c.get('status', ''):<22} "
              f"{len(legal):>7} {str(latest['stamp_ns'] if latest else None):>19} "
              f"{str(delta):>8}  {cand_s}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
