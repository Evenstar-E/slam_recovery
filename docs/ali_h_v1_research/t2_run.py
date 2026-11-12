#!/usr/bin/env python3
"""T2 on the delivered trace run fl_native_20261112T115734Z_483777.

Read-only. No host run, no threshold change, no production edit. It applies the pre-registered
T2 protocol (T2_PROTOCOL.md) to one run: span-containment join, M/T from the availability log,
I from the trace's vec6/Ppre under the trace header's declarations, 0.5 s blocks, phase split,
and the known post-E2 no-catch-up tail. No normal reference exists, so every state is UNKNOWN
and every label-dependent metric is NOT_EVALUABLE; the deliverable is eligibility and intervals.

    python -I docs/ali_h_v1_research/t2_run.py --run /tmp/fl_native_20261112T115734Z_483777
"""

from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import math
import os
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
BLOCK_NS = 500_000_000
E2_REL_S = 54.0
OLD_RUN_IDS = {"fl_native_20261112T065500Z_187992", "fl_native_20261112T070801Z_197026"}


def sha256(path: str, chunk: int = 1 << 22) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(chunk), b""):
            h.update(b)
    return h.hexdigest()


def parse_trace(path: str) -> Dict[str, Any]:
    names: Optional[List[str]] = None
    rows, malformed = [], []
    with open(path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            if line.startswith("#"):
                parts = line.lstrip("#").strip().split()
                if parts and parts[0] == "idx":
                    names = parts
                continue
            f = line.split()
            if not f:
                continue
            if names is None or len(f) != 92:
                malformed.append({"line": lineno, "ncols": len(f)})
                continue
            # The header names the first 14 scalars, then vec6 / Ppre6x6 / Ppost6x6 as three
            # blocks. Parse by the declared block positions, not by zip(names, fields).
            rows.append({
                "idx": int(f[0]), "rel_s": float(f[1]), "abs_ns": int(f[2]),
                "grp_idx": int(f[3]), "scan_first_ns": int(f[4]),
                "scan_last_ns": int(f[5]), "has_out": int(f[6]),
                "phase": int(f[7]), "eff": int(float(f[8])),
                "vec6": np.array([float(x) for x in f[14:20]]),
                "Ppre": np.array([float(x) for x in f[20:56]]).reshape(6, 6),
                "Ppost": np.array([float(x) for x in f[56:92]]).reshape(6, 6),
            })
    return {"names": names, "rows": rows, "malformed": malformed}


def parse_availability(path: str) -> List[Dict[str, Any]]:
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                out.append(json.loads(line))
    return out


def map_support(sup: Dict[str, Any]) -> str:
    if (sup.get("reference_points") or 0) == 0:
        return "EMPTY"
    if sup.get("pass") is True:
        return "SUPPORTED"
    return "LOW"


def build_join(av: List[Dict[str, Any]], trace: Dict[str, Any]) -> Dict[str, Any]:
    rows = trace["rows"]
    by_last: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_last[r["scan_last_ns"]].append(r)
    lasts = sorted(by_last)
    mapped = []
    for a in av:
        S = int(a["scan_stamp_ns"])
        i = bisect.bisect_left(lasts, S)
        if i >= len(lasts):
            mapped.append({"av": a, "last": None, "rows": []})
            continue
        L = lasts[i]
        mapped.append({"av": a, "last": L, "rows": by_last[L]})
    return {"mapped": mapped, "lasts": lasts, "by_last": by_last}


def i_evidence(group_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not group_rows:
        return {"present": False, "reason": "NO_TRACE_ROW"}
    live = [r for r in group_rows if r["phase"] == 0] or group_rows
    r = live[0]
    out = {"present": False, "grp_idx": r["grp_idx"], "phase": r["phase"],
           "has_out": r["has_out"], "trace_idx": r["idx"]}
    if r["has_out"] != 1:
        out["reason"] = "HAS_OUT_0"
        return out
    vec = np.asarray(r["vec6"], dtype=np.float64)
    P = np.asarray(r["Ppre"], dtype=np.float64)
    if not (np.isfinite(vec).all() and np.isfinite(P).all()):
        out["reason"] = "NONFINITE_I_FIELDS"
        return out
    w, V = np.linalg.eigh(0.5 * (P + P.T))
    keep = w > 1e-9 * max(float(w.max()), 1e-12)
    rank = int(keep.sum())
    s = float(np.sum((V[:, keep].T @ vec) ** 2 / w[keep])) if rank else None
    out.update({"present": True, "reason": None, "rank": rank, "s_i": s,
                "e_norm": float(np.linalg.norm(vec)), "e_rot_norm": float(np.linalg.norm(vec[:3])),
                "e_pos_norm": float(np.linalg.norm(vec[3:]))})
    return out


def _phase_i(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for ph in (0, 1):
        vals = [r for r in rows if r["phase"] == ph and r["has_out"] == 1]
        if not vals:
            out[str(ph)] = {"n": 0}
            continue
        e = np.array([np.linalg.norm(r["vec6"]) for r in vals])
        ss = []
        for r in vals:
            w, V = np.linalg.eigh(0.5 * (r["Ppre"] + r["Ppre"].T))
            keep = w > 1e-9 * max(float(w.max()), 1e-12)
            if keep.any():
                ss.append(float(np.sum((V[:, keep].T @ r["vec6"]) ** 2 / w[keep])))
        out[str(ph)] = {"n": len(vals), "e_norm_median": float(np.median(e)),
                        "e_norm_max": float(e.max()),
                        "s_median": float(np.median(ss)) if ss else None,
                        "s_max": max(ss) if ss else None}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    args = ap.parse_args(argv)
    base = os.path.abspath(args.run)
    trace_path = os.path.join(base, "host_logs", "trace_cov.txt")
    av_path = os.path.join(base, "availability_frames.jsonl")
    receipt_path = os.path.join(base, "receipt.json")
    summary_path = os.path.join(base, "run_summary.json")

    trace = parse_trace(trace_path)
    av = parse_availability(av_path)
    receipt = json.load(open(receipt_path, encoding="utf-8"))
    summary = json.load(open(summary_path, encoding="utf-8"))
    join = build_join(av, trace)

    mapped = join["mapped"]
    unmapped = [m for m in mapped if m["last"] is None]
    map_counts = Counter(len(m["rows"]) for m in mapped)
    phase_sets = Counter(tuple(sorted({r["phase"] for r in m["rows"]})) for m in mapped if m["rows"])
    has_sets = Counter(tuple(sorted({r["has_out"] for r in m["rows"]})) for m in mapped if m["rows"])
    av_per_group = Counter(min(r["grp_idx"] for r in m["rows"]) for m in mapped if m["rows"])
    phase_coverage = Counter("both" if {r["phase"] for r in m["rows"]} == {0, 1} else "live_only"
                             for m in mapped if m["rows"])
    exact = sum(1 for m in mapped if m["last"] is not None
                and int(m["av"]["scan_stamp_ns"]) == int(m["last"]))

    joined_rows = []
    state_counts = Counter()
    block_map: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    i_stats = Counter()
    i_norms, i_s = [], []
    tail_rows = 0
    for m in mapped:
        a = m["av"]
        sup = a.get("support") or {}
        nis = a.get("nis") or {}
        ie = i_evidence(m["rows"])
        rel_s = None
        if m["rows"]:
            rel_s = min(r["rel_s"] for r in m["rows"])
        tail = bool(rel_s is not None and rel_s >= E2_REL_S)
        if tail:
            tail_rows += 1
        m_status = map_support(sup)
        status = "UNKNOWN"
        reasons = ["CALIBRATION_BLOCKED:no_normal_reference"]
        if not ie["present"]:
            reasons.append("I_" + str(ie.get("reason")))
        if tail:
            reasons.append("POST_E2_NO_CATCHUP")
        state = "UNKNOWN"
        state_counts[(state, tail)] += 1
        joined_rows.append({
            "kf_id": a.get("kf_id"), "scan_stamp_ns": a.get("scan_stamp_ns"),
            "pose_stamp_ns": a.get("pose_stamp_ns"), "old_status": a.get("status"),
            "map_support": m_status, "supported_fraction": sup.get("supported_fraction"),
            "support_reason": sup.get("reason"), "support_pass": a.get("support_pass"),
            "nis_source": nis.get("source"), "nis_reference": nis.get("selected_reference_source"),
            "nis_effective": nis.get("effective_nis"),
            "M_present": (nis.get("selected_reference_source") == "node_map"
                          and nis.get("computed") is True and isinstance(nis.get("effective_nis"), (int, float))),
            "T_present": (nis.get("selected_reference_source") == "prev_scan"
                          and nis.get("computed") is True and isinstance(nis.get("effective_nis"), (int, float))),
            "join_last_ns": m["last"],
            "grp_idx": sorted({r["grp_idx"] for r in m["rows"]}) if m["rows"] else None,
            "grp_rows": [r["idx"] for r in m["rows"]],
            "phases": sorted({r["phase"] for r in m["rows"]}) if m["rows"] else None,
            "has_out": sorted({r["has_out"] for r in m["rows"]}) if m["rows"] else None,
            "i": ie, "tail": tail, "shadow_state": state, "reason_codes": reasons,
        })
        if ie["present"]:
            i_stats["present"] += 1
            i_norms.append(ie["e_norm"]); i_s.append(ie["s_i"])
            i_stats[f"phase_{ie['phase']}"] += 1
        else:
            i_stats[f"missing_{ie.get('reason')}"] += 1
        if m["rows"]:
            ts = int(a["pose_stamp_ns"])
            block_map[ts // BLOCK_NS].append({"phase": ie["phase"], "tail": tail,
                                              "map_support": m_status})
        else:
            block_map[int(a["pose_stamp_ns"]) // BLOCK_NS].append(
                {"phase": None, "tail": False, "map_support": m_status})

    # fill missing blocks inside the availability time range; all UNKNOWN
    block_ids = sorted(block_map)
    block_rows = []
    for bid in range(block_ids[0], block_ids[-1] + 1):
        fs = block_map.get(bid, [])
        phases = {f["phase"] for f in fs if f["phase"] is not None}
        phase = next(iter(phases)) if len(phases) == 1 else ("MIXED" if phases else "NO_DATA")
        tails = any(f["tail"] for f in fs)
        block_rows.append({"block_id": bid, "n_frames": len(fs), "phase": phase,
                           "tail": tails, "state": "UNKNOWN",
                           "reason_codes": ["CALIBRATION_BLOCKED:no_normal_reference"]
                           + (["POST_E2_NO_CATCHUP"] if tails else [])})
    unknown_blocks = sum(1 for b in block_rows if b["state"] == "UNKNOWN")

    joined_counter = Counter()
    for r in joined_rows:
        joined_counter[(r["old_status"], r["M_present"], r["T_present"])] += 1
    status_count = Counter(a.get("status") for a in av)
    support_reason = Counter((a.get("support") or {}).get("reason") for a in av)
    support_class = Counter(map_support(a.get("support") or {}) for a in av)

    repair = {}
    ack_path = os.path.join(base, "host_control", "ack")
    if os.path.exists(ack_path):
        txt = open(ack_path, encoding="utf-8", errors="replace").read()
        for key in ("repair_received", "repair_applied", "repair_dropped", "repair_queued"):
            m = None
            for tok in txt.split():
                if tok.startswith(key + "="):
                    m = tok.split("=", 1)[1]
            if m is not None:
                repair[key] = int(m)

    out = {
        "_meta": {
            "run": os.path.basename(base), "run_id": summary.get("run_id"),
            "branch_head_at_run": "see git log",
            "trace_sha256": sha256(trace_path), "availability_sha256": sha256(av_path),
            "receipt_sha256": sha256(receipt_path), "summary_sha256": sha256(summary_path),
            "protocol": "T2_PROTOCOL.md (pre-registered)", "block_ns": BLOCK_NS,
            "e2_rel_s": E2_REL_S,
            "i_sign_note": "s_i and |e| are sign-invariant; e_I = -vec6 under the trace header "
                           "(vec6 = state_propagat - state_ after StateEstimation).",
            "not_done": ["no normal reference", "no independent labels", "no host run"],
        },
        "run": {
            "run_mode": summary.get("run_mode"), "detection_enabled": summary.get("detection_enabled"),
            "final_state": summary.get("final_state"), "paired": (summary.get("frames") or {}).get("paired"),
            "injection": (receipt.get("launch") or {}).get("injection"),
            "candidate_source": (receipt.get("launch") or {}).get("candidate_source"),
            "recovery_node_source": (receipt.get("inputs") or {}).get("recovery_node_source"),
            "runtime_library": (receipt.get("inputs") or {}).get("runtime_library_sha256"),
            "status_counts": dict(status_count), "support_non_null": sum(1 for a in av if a.get("support")),
            "repair_ack": repair,
            "support_reasons": dict(support_reason), "support_classes": dict(support_class),
        },
        "trace": {
            "rows_total_lines": len(trace["rows"]) + len(trace["malformed"]),
            "rows_valid": len(trace["rows"]), "malformed": trace["malformed"],
            "phase1_rows": sum(1 for r in trace["rows"] if r["phase"] == 1),
            "has_out_rows": sum(r["has_out"] for r in trace["rows"]),
            "groups": len({r["grp_idx"] for r in trace["rows"]}),
            "duplicate_groups": sum(1 for g, n in Counter(r["grp_idx"] for r in trace["rows"]).items() if n > 1),
            "scan_first_sentinel_all": all(r["scan_first_ns"] == -1 for r in trace["rows"]),
        },
        "join": {
            "availability_rows": len(av), "mapped": len(mapped) - len(unmapped),
            "unmapped": len(unmapped), "exact_equality": exact,
            "trace_rows_per_group": dict(map_counts),
            "availability_per_group": dict(Counter(av_per_group.values())),
            "multi_grp_idx_rows": sum(1 for r in joined_rows if r["grp_idx"] and len(r["grp_idx"]) > 1),
            "multi_grp_idx_row_examples": [r["kf_id"] for r in joined_rows
                                            if r["grp_idx"] and len(r["grp_idx"]) > 1][:5],
            "groups_used_by_availability": len(av_per_group),
            "phase_coverage_availability": dict(phase_coverage),
            "phase_sets": {str(k): v for k, v in phase_sets.items()},
            "has_out_sets": {str(k): v for k, v in has_sets.items()},
            "rule": "effective span containment: previous distinct scan_last < scan_stamp_ns <= scan_last",
        },
        "channels": {
            "M_present_all": sum(1 for r in joined_rows if r["M_present"]),
            "T_present_all": sum(1 for r in joined_rows if r["T_present"]),
            "I_present": i_stats["present"], "I_missing": {k: v for k, v in i_stats.items()
                                                          if k.startswith("missing_")},
            "I_phase": {k: v for k, v in i_stats.items() if k.startswith("phase_")},
            "I_rank6": sum(1 for r in joined_rows if r["i"].get("rank") == 6),
            "I_e_norm": {"min": min(i_norms) if i_norms else None,
                         "median": float(np.median(i_norms)) if i_norms else None,
                         "max": max(i_norms) if i_norms else None},
            "I_s": {"min": min(i_s) if i_s else None,
                    "median": float(np.median(i_s)) if i_s else None,
                    "max": max(i_s) if i_s else None},
            "I_by_phase": _phase_i(trace["rows"]),
            "old_status_by_M_T": {str(k): v for k, v in joined_counter.items()},
        },
        "states": {
            "by_status_and_tail": {str(k): v for k, v in state_counts.items()},
            "blocks": len(block_rows), "unknown_blocks": unknown_blocks,
            "tail_rows": tail_rows, "tail_blocks": sum(1 for b in block_rows if b["tail"]),
            "span_s": (block_ids[-1] - block_ids[0] + 1) * (BLOCK_NS / 1e9),
            "not_evaluable": ["NORMAL_CONSISTENT", "SUSPECT", "false positive", "missed detection",
                              "detection delay", "wrong NORMAL"],
        },
        "blocks": block_rows,
    }
    os.makedirs(HERE, exist_ok=True)
    with open(os.path.join(HERE, "t2_summary.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, ensure_ascii=False)
    with open(os.path.join(HERE, "t2_join.jsonl"), "w", encoding="utf-8") as fh:
        for r in joined_rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(json.dumps({k: out[k] for k in ("run", "trace", "join", "channels", "states")},
                     indent=1, ensure_ascii=False)[:8000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
