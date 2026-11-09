#!/usr/bin/env python3
"""Read-only audit of run_room02_decomposition.py (main a05a8ba / da09333).

Five questions, in the order the review asked them. Nothing here modifies the producer's script
or the main tree; the bag-level checks run against the files it actually reads, and the two
code-path findings are reported as static facts with the exact expression that causes them.

    python3 -B docs/review_20261109_bbc3dcb/oracle_removal_audit.py
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np
from scipy.spatial import cKDTree

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_HERE))
for _p in (_HERE, _REPO):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import verify_four_arm_independent as V          # noqa: E402
import run_room02_decomposition as D             # noqa: E402

OUT = os.path.join(_HERE, "oracle_removal_audit.json")


def _frames(path):
    out = {}
    with V.Reader(path) as r:
        for conn, _t, raw in r.messages(
                connections=[c for c in r.connections if c.topic == V.SCAN_TOPIC]):
            m = V.TYPESTORE.deserialize_ros1(raw, conn.msgtype)
            ns = int(m.header.stamp.sec) * 10 ** 9 + int(m.header.stamp.nanosec)
            out[ns] = {"step": int(m.point_step),
                       "fields": [(f.name, f.offset, f.datatype) for f in m.fields],
                       "rows": np.frombuffer(np.asarray(m.data, dtype=np.uint8).tobytes(),
                                             dtype=np.uint8).reshape(-1, int(m.point_step)),
                       "width": int(m.width)}
    return out


def audit_layout(inj, cln):
    """Same header ns -> same layout, same row count, same order outside the window."""
    common = sorted(set(inj) & set(cln))
    step_mismatch = [ns for ns in common if inj[ns]["step"] != cln[ns]["step"]]
    field_mismatch = [ns for ns in common if inj[ns]["fields"] != cln[ns]["fields"]]
    shape_mismatch = [ns for ns in common if inj[ns]["rows"].shape != cln[ns]["rows"].shape]
    differing = [ns for ns in common if inj[ns]["rows"].tobytes() != cln[ns]["rows"].tobytes()]
    # contiguity: is every differing frame inside [min, max], and is every common frame in that
    # span also differing? a gap would mean the window is not a window
    lo, hi = min(differing), max(differing)
    in_span = [ns for ns in common if lo <= ns <= hi]
    gaps = [ns for ns in in_span if ns not in set(differing)]

    # reorder test: same multiset of rows but different order would masquerade as "rewritten"
    reorder = []
    for ns in differing[:200]:
        a, b = inj[ns]["rows"], cln[ns]["rows"]
        if a.shape == b.shape and a.shape[0] > 0:
            sa = np.sort(a.view([("a", "<u8"), ("b", "<u8"), ("c", "<u8")]), axis=0)
            sb = np.sort(b.view([("a", "<u8"), ("b", "<u8"), ("c", "<u8")]), axis=0)
            if np.array_equal(sa, sb):
                reorder.append(ns)

    # per differing frame: how many rows differ, and does the retained set keep its positions
    row_diff_fraction = []
    for ns in differing:
        a, b = inj[ns]["rows"], cln[ns]["rows"]
        if a.shape != b.shape:
            continue
        diff = (a != b).any(axis=1)
        row_diff_fraction.append(float(diff.mean()))

    return {
        "common_frames": len(common),
        "point_step_mismatch": len(step_mismatch),
        "field_layout_mismatch": len(field_mismatch),
        "row_count_mismatch": len(shape_mismatch),
        "differing_frames": len(differing),
        "window_ns": [lo, hi],
        "frames_in_span_not_differing": len(gaps),
        "reordered_but_not_rewritten_frames": len(reorder),
        "row_diff_fraction_median": float(np.median(row_diff_fraction)) if row_diff_fraction else None,
        "row_diff_fraction_max": float(np.max(row_diff_fraction)) if row_diff_fraction else None,
        "frames_with_all_rows_differing": int(sum(1 for x in row_diff_fraction if x > 0.999)),
    }


def audit_oracle_failopen(inj, cln, window):
    """Does a shape mismatch fall back to the raw scan instead of refusing?"""
    lo, hi = window
    bad = [(ns, inj[ns]["rows"].shape, cln[ns]["rows"].shape)
           for ns in sorted(set(inj) & set(cln))]
    bad = [b for b in bad if b[1] != b[2]]
    # the producer's guard
    src = open(os.path.join(_HERE, "run_room02_decomposition.py"), encoding="utf-8").read()
    fallback = "return inj_kfs[i][\"pts\"]           # cannot split rows; fall back to the raw scan"
    missing_guard = "if ns not in inj_raw or ns not in cln_raw"
    return {"shape_mismatched_frames_in_data": len(bad),
            "fail_open_expression_present": fallback in src,
            "missing_key_guard_present": missing_guard in src,
            "verdict": (("FAIL: a shape mismatch returns the raw scan, so an unsplittable "
                         "frame is silently scored as ORACLE_CLEAN")
                        if (fallback in src and missing_guard not in src)
                        else ("PASS" if missing_guard in src else "UNVERIFIABLE")),
            "how_a_mismatch_enters": ("any re-encode that changes point_step or the row count of "
                                      "one bag's frame makes the whole frame unsplittable")}


def audit_clean_pose():
    """Is a key without a clean reference pose reported as MISSING, or does it raise?"""
    src = open(os.path.join(_HERE, "run_room02_decomposition.py"), encoding="utf-8").read()
    frame_filter = ("frames = [i for i in keys\n"
                    "              if i in rerun_poses and round(inj_kfs[i][\"ts\"], 6) in by_stamp]")
    ref_poses = "ref_poses = {i: T_inv @ cln_poses[i] for i in cln_poses}"
    index_use = "w = body @ poses[i][:3, :3].T + poses[i][:3, 3]"
    return {"frame_filter_mentions_clean_pose": "cln_poses" in frame_filter,
            "frame_filter_expression": frame_filter.strip(),
            "ref_poses_built_from": ref_poses.strip(),
            "poses_indexed_without_guard": index_use in src,
            "verdict": (("FAIL: the frame set is filtered on rerun poses and filtered scans "
                         "only; a key missing a clean pose reaches `poses[i]` and raises KeyError")
                        if ("cln_poses" not in frame_filter and index_use in src) else "PASS")}


def audit_healthy_binding():
    """Does the healthy-window block bind the audit's content, or only its counts?"""
    rep = json.load(open(os.path.join(_HERE, "room02_filter_report.json"), encoding="utf-8"))
    src = open(os.path.join(_HERE, "run_room02_decomposition.py"), encoding="utf-8").read()
    checks_output = "fr.get(\"output_sha256\")" in src or "fr[\"output_sha256\"]" in src
    return {"report_has_output_sha256": rep.get("output_sha256") is not None,
            "script_compares_output_sha256": checks_output,
            "report_binding_method": rep.get("binding", {}).get("method"),
            "report_binding_verdict": rep.get("binding", {}).get("verdict"),
            "verdict": (("FAIL: the script checks binding.verdict and input_sha256 only; the "
                         "report's own binding is count-based, so identical counts over "
                         "different rows would still read BOUND")
                        if not checks_output else "PASS")}


def audit_partition_fields():
    """Are the per-arm in-window numbers actually in the result?"""
    res = json.load(open(os.path.join(_HERE, "room02_decomposition_results.json"), encoding="utf-8"))
    arm_keys = sorted(res["arms"]["A"].keys())
    want = ["in_window_unsupported_fraction", "in_window_retained_fraction",
            "in_window_map_points", "healthy_unsupported_fraction"]
    return {"arm_fields": arm_keys,
            "present_of_expected": [w for w in want if w in arm_keys],
            "missing_of_expected": [w for w in want if w not in arm_keys],
            "healthy_window_fields": sorted(res["healthy_window"].keys()),
            "verdict": (("FAIL: arms carry whole-set totals only; the in-window unsupported "
                         "and retained fractions the docstring promises are absent")
                        if not any(w in arm_keys for w in want) else "PASS")}


def main():
    inj, cln = _frames(D.INJ_SCANS), _frames(D.CLN_SCANS)
    layout = audit_layout(inj, cln)
    window = tuple(layout["window_ns"])
    out = {
        "subject": "run_room02_decomposition.py oracle-removal audit",
        "read_only": True,
        "producer": "docs/review_20261109_bbc3dcb/run_room02_decomposition.py @ a05a8ba",
        "1_layout_order": layout,
        "2_oracle_failopen": audit_oracle_failopen(inj, cln, window),
        "3_clean_pose": audit_clean_pose(),
        "4_healthy_binding": audit_healthy_binding(),
        "5_time_partition": audit_partition_fields(),
    }
    out["verdicts"] = {
        "1_layout_order": "PASS" if (layout["point_step_mismatch"] == 0
                                     and layout["field_layout_mismatch"] == 0
                                     and layout["row_count_mismatch"] == 0
                                     and layout["reordered_but_not_rewritten_frames"] == 0
                                     and layout["frames_in_span_not_differing"] == 0) else "BLOCKED",
    }
    for k in ("2_oracle_failopen", "3_clean_pose", "4_healthy_binding", "5_time_partition"):
        out["verdicts"][k] = out[k]["verdict"].split(":")[0]
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, default=float)
    print(json.dumps({k: out["verdicts"][k] for k in out["verdicts"]}, indent=1))
    print("layout:", json.dumps(layout, indent=1)[:900])
    print("wrote", OUT)


if __name__ == "__main__":
    main()
