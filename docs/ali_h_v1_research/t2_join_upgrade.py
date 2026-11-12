#!/usr/bin/env python3
"""Upgrade the T2 join on the v8 trace (124217Z_521833) that carries a real scan_first_ns.

This does not rerun T2's classification: it measures the join relationship and the population.
Rule: a scan S belongs to every group whose [scan_first_ns, scan_last_ns] contains S. Because the
timestamps are printed as double seconds (ns integers, <=512 ns quantization), the containment is
tested with a declared 512 ns quantization guard, not a nearest search. Multi-to-one is kept.

    python -I docs/ali_h_v1_research/t2_join_upgrade.py --run /tmp/fl_native_20261112T124217Z_521833
"""

from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import os
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
TOL_NS = 512


def parse_trace(path):
    names = None
    rows, malformed = [], []
    with open(path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            if line.startswith("#"):
                p = line.lstrip("#").strip().split()
                if p and p[0] == "idx":
                    names = p
                continue
            f = line.split()
            if not f:
                continue
            if names is None:
                malformed.append({"line": lineno, "ncols": len(f)})
                continue
            # Read scalars by NAME; v8 inserted n_scans, v10 appends 7 post-pose scalars.
            col = {name: i for i, name in enumerate(names)}
            vec_start = names.index("r_chi2w") + 1
            block_end = vec_start + 78
            tail_names = (names[names.index("Ppost6x6") + 1:]
                          if "Ppost6x6" in names else [])
            if len(f) not in (block_end, block_end + len(tail_names)):
                malformed.append({"line": lineno, "ncols": len(f)})
                continue
            pose = ({name: float(f[block_end + i]) for i, name in enumerate(tail_names)}
                    if len(f) == block_end + len(tail_names) and tail_names else None)
            rows.append({
                "idx": int(f[col["idx"]]), "rel_s": float(f[col["rel_s"]]),
                "abs_ns": int(f[col["abs_ns"]]), "grp_idx": int(f[col["grp_idx"]]),
                "scan_first_ns": int(f[col["scan_first_ns"]]),
                "scan_last_ns": int(f[col["scan_last_ns"]]),
                "n_scans": int(f[col["n_scans"]]) if "n_scans" in col else 1,
                "has_out": int(f[col["has_out"]]), "phase": int(f[col["phase"]]),
                "pose_tail": pose,
            })
    return {"rows": rows, "malformed": malformed, "has_n_scans": "n_scans" in (names or [])}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    args = ap.parse_args(argv)
    base = os.path.abspath(args.run)
    trace = parse_trace(os.path.join(base, "host_logs", "trace_cov.txt"))
    av = [json.loads(l) for l in open(os.path.join(base, "availability_frames.jsonl"), encoding="utf-8")
          if l.strip()]
    receipt = json.load(open(os.path.join(base, "receipt.json"), encoding="utf-8"))
    summary = json.load(open(os.path.join(base, "run_summary.json"), encoding="utf-8"))
    rows = trace["rows"]

    last_sorted = sorted(r["scan_last_ns"] for r in rows)
    by_last = {}
    for r in rows:
        by_last.setdefault(r["scan_last_ns"], []).append(r)

    def mechanical(S):
        i = bisect.bisect_left(last_sorted, S)
        return last_sorted[i] if i < len(last_sorted) else None

    def spans(S, tol=TOL_NS):
        return [r for r in rows if r["scan_first_ns"] - tol <= S <= r["scan_last_ns"] + tol]

    per_row = []
    n_groups = Counter()
    mech_state = Counter()
    matched_nscans = Counter()
    shared_scan_stamps = Counter()
    for r in rows:
        shared_scan_stamps[(r["scan_first_ns"], r["scan_last_ns"])] += 1
    for a in av:
        S = int(a["scan_stamp_ns"])
        g = spans(S)
        n_groups[len(g)] += 1
        L = mechanical(S)
        mg = None
        if L is not None:
            mg = by_last[L][0]
            if any(x["grp_idx"] == mg["grp_idx"] for x in g):
                mech_state["old_group_in_new_set"] += 1
            else:
                mech_state["old_group_not_in_new_set"] += 1
        else:
            mech_state["old_unmapped"] += 1
        if g:
            for x in g:
                matched_nscans[x["n_scans"]] += 1
        per_row.append({
            "kf_id": a.get("kf_id"), "scan_stamp_ns": S,
            "pose_stamp_ns": a.get("pose_stamp_ns"), "old_status": a.get("status"),
            "scan_first_ns": [x["scan_first_ns"] for x in g],
            "scan_last_ns": [x["scan_last_ns"] for x in g],
            "grp_idx": [x["grp_idx"] for x in g],
            "n_scans": [x["n_scans"] for x in g],
            "phase": [x["phase"] for x in g],
            "has_out": [x["has_out"] for x in g],
            "n_groups": len(g),
            "old_mechanical_group": None if mg is None else mg["grp_idx"],
            "old_in_new": bool(mg is not None and any(x["grp_idx"] == mg["grp_idx"] for x in g)),
        })

    trace_rel_max = max(r["rel_s"] for r in rows)
    n_scans_dist = Counter(r["n_scans"] for r in rows)
    shared_dist = Counter(v for v in shared_scan_stamps.values())
    out = {
        "_meta": {
            "run": os.path.basename(base), "run_id": summary.get("run_id"),
            "trace_sha256": sha256(os.path.join(base, "host_logs", "trace_cov.txt")),
            "availability_sha256": sha256(os.path.join(base, "availability_frames.jsonl")),
            "receipt_sha256": sha256(os.path.join(base, "receipt.json")),
            "summary_sha256": sha256(os.path.join(base, "run_summary.json")),
            "join_status": "TRUE_SPAN_CONTAINMENT_WITH_512NS_QUANTIZATION",
            "tolerance_ns": TOL_NS,
            "tolerance_basis": "double-second print quantization (ulp), not a nearest search",
            "rule": "S in every group with first-512 <= S <= last+512; multi-to-one kept",
        },
        "run": {
            "run_mode": summary.get("run_mode"), "detection_enabled": summary.get("detection_enabled"),
            "final_state": summary.get("final_state"), "paired": (summary.get("frames") or {}).get("paired"),
            "injection": (receipt.get("launch") or {}).get("injection"),
            "candidate_source": (receipt.get("launch") or {}).get("candidate_source"),
            "runtime_library": (receipt.get("inputs") or {}).get("runtime_library_sha256"),
            "recovery_node_source": (receipt.get("inputs") or {}).get("recovery_node_source"),
            "availability_rows": len(av),
            "status_counts": dict(Counter(a.get("status") for a in av)),
            "support_non_null": sum(1 for a in av if a.get("support")),
        },
        "trace": {
            "rows": len(rows), "malformed": trace["malformed"],
            "has_n_scans": trace["has_n_scans"],
            "groups": len({r["grp_idx"] for r in rows}),
            "n_scans_distribution": dict(n_scans_dist),
            "first_equals_last": sum(1 for r in rows if r["scan_first_ns"] == r["scan_last_ns"]),
            "phase_distribution": dict(Counter(r["phase"] for r in rows)),
            "has_out_distribution": dict(Counter(r["has_out"] for r in rows)),
            "rel_s_max": trace_rel_max,
            "shared_scan_stamp_groups": dict(shared_dist),
        },
        "join": {
            "denominator": len(av),
            "true_groups_per_availability": {str(k): v for k, v in n_groups.items()},
            "unmatched": sum(v for k, v in n_groups.items() if k == 0),
            "matched_n_scans": {str(k): v for k, v in matched_nscans.items()},
            "old_mechanical_vs_new": dict(mech_state),
            "multi_to_one_rows": sum(v for k, v in n_groups.items() if k > 1),
            "one_to_one_rows": n_groups.get(1, 0),
            "rule": "span containment with 512 ns quantization; multi-to-one kept, no group split",
        },
        "population_limits": {
            "rel_s_max": trace_rel_max,
            "bag_duration_s": 60.0,
            "full_60s_coverage": False,
            "note": "this run stops at rel≈49.1 s; 736 trace rows / 444 paired, not a full 60 s population",
        },
    }
    with open(os.path.join(HERE, "t2_join_upgrade.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, ensure_ascii=False)
    with open(os.path.join(HERE, "t2_join_upgrade_rows.jsonl"), "w", encoding="utf-8") as fh:
        for r in per_row:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(json.dumps(out, indent=1, ensure_ascii=False)[:7000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
