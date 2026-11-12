#!/usr/bin/env python3
"""Summarize an availability_frames.jsonl and recompute two frames offline.

Usage: python analyze_availability.py <availability_frames.jsonl> <out.json>
"""
import json
import statistics
import sys
from collections import Counter


def main():
    src, out_path = sys.argv[1], sys.argv[2]
    rows = [json.loads(line) for line in open(src, encoding="utf-8")]
    n = len(rows)

    def support_class(r):
        s = r["support"]
        if s.get("reason") == "empty_reference":
            return "empty_reference"
        if s.get("pass") is False:
            frac = s.get("supported_fraction")
            return "insufficient_support" if frac is not None else "support_input_missing"
        if s.get("pass") is True:
            return "ok"
        return "not_evaluated"

    def nis_class(r):
        nis = r["nis"]
        kind = nis.get("raw_kind")
        if kind == "finite" and nis.get("source") == "computed":
            return "computed_finite"
        if kind == "not_computed":
            return "not_computed:%s" % nis.get("raw_reason")
        if kind in ("inf", "nan"):
            return "non_finite:%s" % kind
        if nis.get("source") == "carried_forward":
            return "carried_forward"
        return "other"

    runs = []
    start = 0
    for i in range(1, n + 1):
        if i == n or rows[i]["status"] != rows[start]["status"]:
            runs.append({"status": rows[start]["status"], "first_row": start, "last_row": i - 1,
                         "frames": i - start,
                         "start_pose_stamp_ns": rows[start]["pose_stamp_ns"],
                         "end_pose_stamp_ns": rows[i - 1]["pose_stamp_ns"]})
            start = i

    def recompute(i):
        r = rows[i]
        s, nis = r["support"], r["nis"]
        pts = s.get("points", [])
        within = [p["within_1m"] for p in pts if p.get("within_1m") is not None]
        h = nis.get("holdout") or {}
        hp = h.get("points", [])
        chi = [p["chi2"] for p in hp if p.get("chi2") is not None]
        res = [p["residual_m"] for p in hp if p.get("residual_m") is not None]
        within2 = [p["within_2m"] for p in hp if p.get("within_2m") is not None]
        return {
            "row": i, "kf_id": r["kf_id"], "status": r["status"],
            "support_pass": r["support_pass"], "nis_present": r["nis_present"],
            "status_from_conditions": r["status_from_conditions"],
            "support": {
                "reported_reason": s.get("reason"),
                "reported_supported_fraction": s.get("supported_fraction"),
                "reported_within": s.get("within_radius_count"),
                "reported_sampled": s.get("sampled_query_count"),
                "saved_points": len(pts),
                "saved_within": int(sum(within)) if within else None,
                "saved_fraction": round(sum(within) / len(within), 6) if within else None,
            },
            "nis": {
                "reported_nis": h.get("nis"),
                "reported_mean_residual": h.get("mean_residual"),
                "reported_branch": h.get("branch"),
                "reported_valid_total": (h.get("residual_valid"), h.get("residual_total")),
                "saved_residuals": len(chi),
                "saved_chi2_mean": round(sum(chi) / len(chi), 6) if chi else None,
                "saved_residual_mean": round(sum(res) / len(res), 6) if res else None,
                "saved_within_2m": (int(sum(within2)), len(within2)) if within2 else None,
            },
        }

    # status must be recomputable from the two booleans
    status_mismatch = [r["kf_id"] for r in rows
                       if r["status"] != ("AVAILABLE" if (r["support_pass"] and r["nis_present"])
                                          else "UNAVAILABLE")]
    summary = {
        "rows": n,
        "support_classes": dict(Counter(support_class(r) for r in rows)),
        "support_pass": dict(Counter(r["support_pass"] for r in rows)),
        "nis_classes": dict(Counter(nis_class(r) for r in rows)),
        "status": dict(Counter(r["status"] for r in rows)),
        "status_from_conditions_mismatches": status_mismatch,
        "runs": runs,
        "recompute": [recompute(i) for i in (22, 53, 157)],
    }
    combos = Counter((r["support_pass"], r["nis_present"]) for r in rows)
    summary["status_condition_combos"] = {"%s/%s" % k: v for k, v in combos.items()}
    json.dump(summary, open(out_path, "w", encoding="utf-8"), indent=1)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
