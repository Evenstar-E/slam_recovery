#!/usr/bin/env python3
"""F2 reader for a FAST-LIO same-update export (contract: F2_FASTLIO_CHANNEL_ELIGIBILITY.md §4).

Read-only. It does not run the host and does not change thresholds. It validates the export,
computes e_I from same-update pre/post poses with the validated T2 SE(3) Log (mixed convention,
V^-1), keeps every row in the denominator, and reports per-row/per-block eligibility. With no
calibration segment every block is UNKNOWN; that is the intended honest output, not a failure.

Canonical input: JSONL, one object per update. Required keys:
  run_id, update_id, lidar_beg_ns, has_out
  pre, post  = {"x","y","z","qx","qy","qz","qw"}   (required when has_out == 1)
Optional keys: lidar_end_ns, rel_s, phase, grp_idx, eff, feats_down_size, feats_in,
  nis, dof_M, R, Ppre, Ppost, support, re_slam, issleeping, isbuilding, ispublish.

The implementation is a self-contained gate around the exported numbers: a malformed row is
reported, never repaired by interpolation or nearest lookup.

    python -I f2_fastlio_read.py --export trace.jsonl [--out-prefix f2]
    python -I f2_fastlio_read.py selftest
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import sys
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
BLOCK_NS = 500_000_000
BLOCK_S = 0.5
SUPPORT_MIN_M = 1.0
SUPPORT_MIN_FRAC = 0.60
SUPPORT_SAMPLES = 200
POSE_KEYS = ("x", "y", "z", "qx", "qy", "qz", "qw")


def _load_t2():
    """Load the validated T2 math without copying it (isolated mode-safe explicit load)."""
    path = os.path.join(HERE, "t2_run.py")
    spec = importlib.util.spec_from_file_location("t2_run_ref", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


T2 = _load_t2()


def _p7(obj: Any, name: str) -> Optional[np.ndarray]:
    if not isinstance(obj, dict):
        return None
    try:
        v = np.array([float(obj[k]) for k in POSE_KEYS], dtype=np.float64)
    except (KeyError, TypeError, ValueError):
        return None
    if not np.all(np.isfinite(v)):
        return None
    return v


def _int(obj: Dict[str, Any], key: str, default: Optional[int] = None) -> Optional[int]:
    v = obj.get(key, default)
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _float(obj: Dict[str, Any], key: str) -> Optional[float]:
    v = obj.get(key)
    if v is None:
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _quat_norm(p: np.ndarray) -> float:
    return float(np.linalg.norm(p[3:7]))


def _support_class(sup: Any) -> str:
    """Map a support record to the ALI-H context. Never guess: absent -> UNKNOWN_CONTEXT."""
    if not isinstance(sup, dict):
        return "UNKNOWN_CONTEXT"
    n = _int(sup, "n")
    k = _int(sup, "pass")
    frac = _float(sup, "pass_fraction")
    if frac is None and n and k is not None:
        frac = k / float(n)
    if frac is None:
        # A bare boolean is a single sample, not a 200-sample support estimate.
        return "UNKNOWN_CONTEXT"
    if n is not None and n < SUPPORT_SAMPLES:
        return "UNKNOWN_CONTEXT"
    return "SUPPORTED" if frac >= SUPPORT_MIN_FRAC else "LOW"


def read_export(path: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    rows, bad = [], []
    with open(path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                bad.append({"line": lineno, "reason": f"json:{exc.msg}"})
                continue
            if not isinstance(obj, dict):
                bad.append({"line": lineno, "reason": "not_an_object"})
                continue
            rows.append({"__line__": lineno, **obj})
    return rows, bad


def qualify(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    seen: Dict[int, int] = {}
    dup: List[Dict[str, Any]] = []
    out_rows: List[Dict[str, Any]] = []
    counts = Counter()

    run_ids = {r.get("run_id") for r in rows if r.get("run_id")}
    for r in rows:
        uid = _int(r, "update_id")
        lidar_ns = _int(r, "lidar_beg_ns")
        has_out = _int(r, "has_out")
        rec: Dict[str, Any] = {
            "line": r.get("__line__"), "update_id": uid, "lidar_beg_ns": lidar_ns,
            "lidar_end_ns": _int(r, "lidar_end_ns"), "rel_s": _float(r, "rel_s"),
            "phase": _int(r, "phase"), "has_out": has_out,
            "eff": _int(r, "eff"), "feats_down_size": _int(r, "feats_down_size"),
            "feats_in": _int(r, "feats_in"), "nis": _float(r, "nis"),
            "dof_M": _int(r, "dof_M"), "support": _support_class(r.get("support")),
            "status": "OK", "reasons": [],
        }
        if uid is None:
            rec["status"] = "INVALID_ROW"
            rec["reasons"].append("missing_update_id")
        elif uid in seen:
            rec["status"] = "INVALID_ROW"
            rec["reasons"].append(f"duplicate_update_id:{seen[uid]}")
            dup.append({"update_id": uid, "lines": [seen[uid], r.get("__line__")]})
        else:
            seen[uid] = r.get("__line__")
        if lidar_ns is None:
            rec["status"] = "INVALID_ROW"
            rec["reasons"].append("missing_lidar_beg_ns")
        if has_out not in (0, 1):
            rec["status"] = "INVALID_ROW"
            rec["reasons"].append("missing_or_invalid_has_out")

        pre = _p7(r.get("pre"), "pre") if has_out == 1 else None
        post = _p7(r.get("post"), "post") if has_out == 1 else None
        if has_out == 1:
            if pre is None or post is None:
                rec["status"] = "NO_PAIR"
                rec["reasons"].append("missing_pre_or_post")
            else:
                qn = (_quat_norm(pre), _quat_norm(post))
                if abs(qn[0] - 1.0) > 1e-6 or abs(qn[1] - 1.0) > 1e-6:
                    rec["status"] = "INVALID_ROW"
                    rec["reasons"].append(f"quat_norm:{qn[0]:.9f}/{qn[1]:.9f}")
                else:
                    rec["pre"] = [float(x) for x in pre]
                    rec["post"] = [float(x) for x in post]
                    rec["e_I"] = [float(x) for x in T2.e_i_from_poses(pre, post)]
                    rec["e_norm2"] = float(np.dot(rec["e_I"], rec["e_I"]))
        if rec["eff"] is not None and rec["eff"] == 0:
            rec["eff_zero"] = True
            if rec.get("e_norm2") is not None and rec["e_norm2"] <= 1e-12:
                rec["zero_eff_zero_log"] = True
        counts[rec["status"]] += 1
        out_rows.append(rec)

    # Per-row verdicts. UNKNOWN is the default; there is no calibration segment in this export.
    for rec in out_rows:
        if rec["status"] != "OK":
            rec["verdict"] = "UNKNOWN"
            rec["verdict_reason"] = rec["status"]
            continue
        if rec["has_out"] == 0:
            rec["verdict"] = "UNKNOWN"
            rec["verdict_reason"] = "NO_UPDATE_OUTPUT"
            continue
        if rec.get("eff_zero"):
            rec["verdict"] = "UNKNOWN"
            rec["verdict_reason"] = "ZERO_EFFECTIVE_CONSTRAINTS"
            continue
        rec["verdict"] = "UNKNOWN"
        rec["verdict_reason"] = "NO_CALIBRATION_REFERENCE"

    return {"rows": out_rows, "bad_lines": [], "duplicates": dup,
            "run_ids": sorted(x for x in run_ids if x), "counts": dict(counts)}


def blocks(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """0.5 s non-overlapping blocks by sensor time; NO_DATA blocks are kept."""
    valid = [r for r in rows if r.get("lidar_beg_ns") is not None]
    if not valid:
        return {"n_blocks": 0, "blocks": [], "unknown": {}}
    first = min(r["lidar_beg_ns"] for r in valid)
    last = max(r["lidar_beg_ns"] for r in valid)
    first_b, last_b = first // BLOCK_NS, last // BLOCK_NS
    by_block: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for r in valid:
        by_block[r["lidar_beg_ns"] // BLOCK_NS].append(r)

    out = []
    for b in range(first_b, last_b + 1):
        rs = by_block.get(b, [])
        e_vals = [r["e_norm2"] for r in rs if r.get("e_norm2") is not None]
        ctx = Counter(r["support"] for r in rs if r.get("support") != "UNKNOWN_CONTEXT")
        block = {
            "block": b, "t0_ns": b * BLOCK_NS, "n_rows": len(rs),
            "n_e": len(e_vals),
            "n_eff_zero": sum(1 for r in rs if r.get("eff_zero")),
            "has_M": any(r.get("nis") is not None for r in rs),
            "n_has_out_0": sum(1 for r in rs if r.get("has_out") == 0),
            "context": (ctx.most_common(1)[0][0] if len(ctx) == 1 else
                        ("MIXED" if len(ctx) > 1 else "UNKNOWN_CONTEXT")),
            "score_e2_median": float(np.median(e_vals)) if e_vals else None,
            "verdict": "UNKNOWN",
        }
        if not rs:
            block["verdict_reason"] = "NO_DATA"
        elif block["context"] == "MIXED":
            block["verdict_reason"] = "MIXED_CONTEXT"
        elif block["context"] == "UNKNOWN_CONTEXT":
            block["verdict_reason"] = "UNKNOWN_CONTEXT"
        elif not e_vals:
            block["verdict_reason"] = "NO_FRESH_I"
        else:
            block["verdict_reason"] = "NO_CALIBRATION_REFERENCE"
        out.append(block)

    # Contiguous UNKNOWN runs (every block is UNKNOWN here, but keep the accounting general).
    intervals, start = [], None
    for i, b in enumerate(out):
        if b["verdict"] == "UNKNOWN" and start is None:
            start = i
        elif b["verdict"] != "UNKNOWN" and start is not None:
            intervals.append((start, i - 1))
            start = None
    if start is not None:
        intervals.append((start, len(out) - 1))
    unknown = {
        "n_blocks": sum(1 for b in out if b["verdict"] == "UNKNOWN"),
        "total_s": sum(1 for b in out if b["verdict"] == "UNKNOWN") * BLOCK_S,
        "n_intervals": len(intervals),
        "longest_interval_s": max((b - a + 1 for a, b in intervals), default=0) * BLOCK_S,
        "intervals_block_index": intervals[:50],
    }
    return {"n_blocks": len(out), "blocks": out, "unknown": unknown}


def _quantiles(vals: List[float]) -> Dict[str, Any]:
    if not vals:
        return {"n": 0}
    a = np.array(vals, dtype=np.float64)
    return {"n": int(a.size), "p10": float(np.quantile(a, 0.10)),
            "p50": float(np.quantile(a, 0.50)), "p90": float(np.quantile(a, 0.90)),
            "max": float(a.max())}


def summarize(q: Dict[str, Any], bl: Dict[str, Any]) -> Dict[str, Any]:
    rows = q["rows"]
    e = [r["e_norm2"] for r in rows if r.get("e_norm2") is not None]
    return {
        "run_ids": q["run_ids"],
        "mixed_run_ids": len(q["run_ids"]) > 1,
        "rows": len(rows),
        "bad_lines": q["bad_lines"],
        "duplicates": q["duplicates"],
        "row_status": q["counts"],
        "has_out": dict(Counter(r.get("has_out") for r in rows)),
        "I_rows": len(e),
        "I_zero_eff_zero_log": sum(1 for r in rows if r.get("zero_eff_zero_log")),
        "eff_zero_rows": sum(1 for r in rows if r.get("eff_zero")),
        "M_rows_nis": sum(1 for r in rows if r.get("nis") is not None),
        "T": "NOT_APPLICABLE_FASTLIO_HAS_NO_PREV_SCAN_UPDATE",
        "support_classes": dict(Counter(r["support"] for r in rows)),
        "unit_weight_e2": _quantiles(e),
        "blocks": {"n_blocks": bl["n_blocks"], "unknown": bl.get("unknown", {})},
        "qualification": {
            # The file can prove unique update ids and complete pairs; only the C++ producer can
            # prove the two states came from the same update call. Keep the two claims separate.
            "SAME_UPDATE_ID_PAIRING": ("INVALID_MIXED_RUN_IDS" if len(q["run_ids"]) > 1 else
                                       ("PASS" if q["counts"].get("OK", 0) and not q["duplicates"]
                                        and all(r.get("update_id") is not None for r in rows)
                                        else "NOT_AVAILABLE")),
            "SAME_UPDATE_CALL_BINDING": "ASSERTED_BY_PRODUCER_NOT_VERIFIED_FROM_FILE",
            "PRE_POST_POSE_SANITY": ("PASS" if e else "NOT_AVAILABLE"),
            "PRE_POST_POSE_IDENTITY": "ASSERTED_NOT_VERIFIED",
            "COMPLETE_POINT_MEMBERSHIP": "ASSERTED_NOT_VERIFIED",
            "COVARIANCE_6D": "NOT_AVAILABLE_FOR_E_I",
            "CALIBRATION": "BLOCKED:no_independently_confirmed_normal_prefix",
            "LABELS": "BLOCKED:no_fault_event_labels_for_fastlio",
        },
        "verdicts": {
            "NORMAL_SUSPECT": "NOT_EVALUABLE",
            "false_alarm_per_hour": "NOT_EVALUABLE",
            "recall_latency": "NOT_EVALUABLE",
            "note": "all blocks UNKNOWN is not zero risk; do not fill missing labels with 0",
        },
    }


def run(export: str, out_prefix: str) -> int:
    rows, bad = read_export(export)
    q = qualify(rows)
    q["bad_lines"].extend(bad)
    bl = blocks(q["rows"])
    summary = summarize(q, bl)
    summary["export"] = os.path.abspath(export)
    with open(out_prefix + "_summary.json", "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=1, ensure_ascii=False)
    with open(out_prefix + "_rows.jsonl", "w", encoding="utf-8") as fh:
        for r in q["rows"]:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(json.dumps(summary, indent=1, ensure_ascii=False))
    return 0


def selftest() -> int:
    out: Dict[str, Any] = {}

    def mk(uid, t_ns, pre, post, eff=100, **kw):
        return {"run_id": "SYNTH", "update_id": uid, "lidar_beg_ns": t_ns, "has_out": 1,
                "pre": dict(zip(POSE_KEYS, pre)), "post": dict(zip(POSE_KEYS, post)),
                "eff": eff, **kw}

    ident = [0, 0, 0, 0, 0, 0, 1]
    # Pure world translation (identity rotation): e_I must be [0,0,0, dx,0,0].
    tr = [0.1, 0.0, 0.0]
    q1 = qualify([mk(1, 0, ident, tr + ident[3:])])
    e1 = np.array(q1["rows"][0]["e_I"])
    out["pure_translation"] = {"e_I": e1.tolist(),
                               "pass": bool(np.allclose(e1, [0, 0, 0, 0.1, 0, 0], atol=1e-12))}
    # Pure body rotation: e_I rotation = [0,0,0.1], translation = 0.
    rot = [0, 0, 0.1]
    R = T2.so3_exp(np.array(rot))
    quat = np.zeros(4)
    # quaternion from R via the same convention as t2_run.quat_to_rot (x,y,z,w)
    trq = np.array([math.sqrt(max(0.0, 1.0 + R[0, 0] - R[1, 1] - R[2, 2])) / 2.0,
                    math.sqrt(max(0.0, 1.0 - R[0, 0] + R[1, 1] - R[2, 2])) / 2.0,
                    math.sqrt(max(0.0, 1.0 - R[0, 0] - R[1, 1] + R[2, 2])) / 2.0,
                    math.sqrt(max(0.0, 1.0 + R[0, 0] + R[1, 1] + R[2, 2])) / 2.0])
    q2 = qualify([mk(2, 0, ident, [0, 0, 0] + trq.tolist())])
    e2 = np.array(q2["rows"][0]["e_I"])
    out["pure_rotation"] = {"e_I": e2.tolist(),
                            "pass": bool(np.allclose(e2[:3], rot, atol=1e-9)
                                         and np.allclose(e2[3:], 0, atol=1e-9))}
    # Missing post with has_out=1 must stay in the denominator as NO_PAIR.
    q3 = qualify([mk(3, 0, ident, tr + ident[3:]), {"update_id": 4, "lidar_beg_ns": 1,
                                                    "has_out": 1, "pre": dict(zip(POSE_KEYS, ident))}])
    out["missing_post"] = {"statuses": q3["counts"], "rows": len(q3["rows"]),
                           "pass": q3["counts"].get("NO_PAIR") == 1 and len(q3["rows"]) == 2}
    # eff=0 with zero Log is flagged, not dropped.
    q4 = qualify([mk(5, 0, ident, ident, eff=0)])
    r4 = q4["rows"][0]
    out["eff_zero"] = {"eff_zero": bool(r4.get("eff_zero")),
                       "zero_eff_zero_log": bool(r4.get("zero_eff_zero_log")),
                       "verdict": r4["verdict"],
                       "pass": bool(r4.get("eff_zero") and r4.get("zero_eff_zero_log")
                                    and r4["verdict_reason"] == "ZERO_EFFECTIVE_CONSTRAINTS")}
    # Duplicate update_id is rejected, both rows kept.
    q5 = qualify([mk(6, 0, ident, tr + ident[3:]), mk(6, 1, ident, tr + ident[3:])])
    out["duplicate_id"] = {"duplicates": q5["duplicates"], "rows": len(q5["rows"]),
                           "pass": len(q5["duplicates"]) == 1 and len(q5["rows"]) == 2}
    # Blocks: 1.0 s span at 0.5 s blocks -> blocks 0 and 1, block 1 has no data? No: t=1.0 s is block 2.
    q6 = qualify([mk(7, 0, ident, tr + ident[3:]), mk(8, 500_000_000, ident, tr + ident[3:])])
    b6 = blocks(q6["rows"])
    out["blocks"] = {"n_blocks": b6["n_blocks"], "pass": b6["n_blocks"] == 2}
    # Support must not be guessed from a boolean/single sample.
    q7 = qualify([mk(9, 0, ident, tr + ident[3:], support={"pass": True})])
    out["support_guard"] = {"class": q7["rows"][0]["support"],
                            "pass": q7["rows"][0]["support"] == "UNKNOWN_CONTEXT"}
    # Two run ids in one export must not be glued.
    q8 = qualify([mk(10, 0, ident, tr + ident[3:]),
                  {**mk(11, 1, ident, tr + ident[3:]), "run_id": "OTHER"}])
    s8 = summarize(q8, blocks(q8["rows"]))
    out["mixed_run_ids"] = {"flag": s8["mixed_run_ids"],
                            "pairing": s8["qualification"]["SAME_UPDATE_ID_PAIRING"],
                            "pass": bool(s8["mixed_run_ids"]
                                         and s8["qualification"]["SAME_UPDATE_ID_PAIRING"]
                                         == "INVALID_MIXED_RUN_IDS")}
    ok = all(v["pass"] for v in out.values())
    print(json.dumps({"pass": ok, "cases": out}, indent=1, ensure_ascii=False))
    return 0 if ok else 1


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "selftest":
        return selftest()
    ap = argparse.ArgumentParser()
    ap.add_argument("--export", required=True)
    ap.add_argument("--out-prefix", default=os.path.join(HERE, "f2_fastlio"))
    args = ap.parse_args(argv)
    return run(args.export, args.out_prefix)


if __name__ == "__main__":
    raise SystemExit(main())
