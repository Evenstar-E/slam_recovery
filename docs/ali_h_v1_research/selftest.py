#!/usr/bin/env python3
"""T1: the six minimal synthetic controls from ALI-H v1 §7 T1.

All records here are SYNTHETIC/UNIT. Nothing in this file is a real recovery result, a real
normal reference or a real anomaly label. The controls only exercise the frozen decision rules.

    python -I docs/ali_h_v1_research/selftest.py
"""

from __future__ import annotations

import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import ali_h_v1 as ali  # noqa: E402


def calib_pair(channel, context="LOW"):
    """A deterministic 20-block reference whose scores are 1..20."""
    return {(channel, context): [float(i) for i in range(1, 21)]}


def calib_all(context="LOW"):
    table = {}
    for ch in ("M", "T", "I"):
        table.update(calib_pair(ch, context))
    return ali.Calibration(table, reference_status="SYNTHETIC_UNIT")


def block(bid, m=None, t=None, i=None):
    def v(x):
        return {"verdict": x, "u": None}
    return {"block_id": bid, "verdicts": {"M": v(m), "T": v(t), "I": v(i)}}


def test_1_low_support_cross_modal_consistency():
    """Low support + I normal + T normal -> NORMAL (relative scope); only T -> UNKNOWN."""
    calib = calib_all()
    blocks = [block(0, m=None, t="NORMAL", i="NORMAL"),
              block(1, m=None, t="NORMAL", i="NORMAL")]
    out = ali.classify_blocks(blocks, calib)
    ok_scope = out[-1]["state"] == "NORMAL_CONSISTENT" and out[-1]["scope"] == "RELATIVE_MOTION_ONLY"
    blocks2 = [block(0, m=None, t="NORMAL", i="MISSING"),
               block(1, m=None, t="NORMAL", i="MISSING")]
    out2 = ali.classify_blocks(blocks2, calib)
    ok_t_only = out2[-1]["state"] == "UNKNOWN"
    return ok_scope and ok_t_only, {
        "i_plus_t": out[-1], "t_only": out2[-1]}


def test_2_low_support_qualified_conflict():
    """Low support + two adjacent I alarms -> SUSPECT, not masked by support."""
    calib = calib_all()
    blocks = [block(0, m=None, t=None, i="ALARM"),
              block(1, m=None, t=None, i="ALARM")]
    out = ali.classify_blocks(blocks, calib)
    ok = out[-1]["state"] == "SUSPECT" and out[-1]["scope"] == "RELATIVE_MOTION_ONLY"
    blocks_m = [block(0, m="ALARM", t=None, i=None),
                block(1, m="ALARM", t=None, i=None)]
    out_m = ali.classify_blocks(blocks_m, calib)
    ok_m = out_m[-1]["state"] == "SUSPECT" and out_m[-1]["scope"] == "MAP_AND_MOTION"
    return ok and ok_m, {"i_conflict": out[-1], "m_conflict": out_m[-1]}


def test_3_missing_and_carried():
    """No reference / no I / carried -> UNKNOWN; missing is not a zero; last suspect kept."""
    calib = calib_all()
    # a SUSPECT first so last_suspect is set, then a block with no evidence
    blocks = [block(0, i="ALARM"), block(1, i="ALARM"), block(2, i="MISSING")]
    out = ali.classify_blocks(blocks, calib)
    ok_unknown = out[-1]["state"] == "UNKNOWN"
    ok_keep = out[-1]["last_suspect_block"] == 1
    ch = {"name": "I", "present": False, "source": None, "fresh": False, "score": None,
          "qualification": "NOT_AVAILABLE", "reason": "no_imu"}
    v = ali.channel_verdict(ch, "LOW", calib)
    ok_not_zero = v["score"] is None and v["verdict"] == "MISSING"
    # carried is stale, not fresh evidence
    ch2 = {"name": "T", "present": True, "source": "prev_scan", "fresh": False, "score": 1.0,
           "qualification": "EVIDENCE_PRESENT", "reason": None}
    v2 = ali.channel_verdict(ch2, "LOW", calib)
    ok_stale = v2["verdict"] == "STALE"
    return ok_unknown and ok_keep and ok_not_zero and ok_stale, {
        "after_missing": out[-1], "missing_channel": v, "carried_channel": v2}


def test_4_per_source_calibration_and_scope():
    """Same score uses each source's own reference; no LOW reference is OUT_OF_SUPPORT."""
    table = calib_pair("M", "LOW")
    table.update({("T", "LOW"): [0.0] * 20})       # score 1.0 is the maximum for T
    table.update(calib_pair("M", "SUPPORTED"))     # must not be borrowed by LOW
    calib = ali.Calibration(table, reference_status="SYNTHETIC_UNIT")
    m = ali.channel_verdict({"name": "M", "present": True, "fresh": True, "score": 1.0,
                             "reason": None}, "LOW", calib)
    t = ali.channel_verdict({"name": "T", "present": True, "fresh": True, "score": 1.0,
                             "reason": None}, "LOW", calib)
    ok_diff = m["verdict"] == "NORMAL" and t["verdict"] == "ALARM"
    calib2 = ali.Calibration({("M", "SUPPORTED"): [1.0] * 20}, reference_status="SYNTHETIC_UNIT")
    low = ali.channel_verdict({"name": "M", "present": True, "fresh": True, "score": 1.0,
                               "reason": None}, "LOW", calib2)
    ok_out = low["verdict"] == "UNQUALIFIED" and low["calibration"] == "OUT_OF_SUPPORT"
    return ok_diff and ok_out, {"M": m, "T": t, "M_LOW_without_LOW_ref": low}


def test_5_frame_and_time_contract():
    """The same physical scalar under a rigid re-expression, and block time from sensor stamps."""
    from slam_recovery.core import transport, transport_information
    rng = np.random.default_rng(0)
    A = rng.normal(size=(6, 6))
    L = A @ A.T + np.eye(6)
    v = rng.normal(size=6)
    v = v / np.linalg.norm(v)
    base = float(v @ L @ v)
    G = np.eye(4)
    c, s = np.cos(0.4), np.sin(0.4)
    G[:3, :3] = np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])
    G[:3, 3] = [0.3, -0.2, 0.1]
    v2 = transport(v, G)
    L2 = transport_information(L, G)
    rel = abs(float(v2 @ L2 @ v2) - base) / max(abs(base), 1e-12)
    ok_transport = rel < 1e-10
    row = {"pose_stamp_ns": 1627785262123456789, "scan_stamp_ns": 1627785261982946396,
           "kf_id": 7, "support": {"pass": False, "reference_points": 10},
           "nis": {"source": "computed", "computed": True,
                   "selected_reference_source": "prev_scan", "effective_nis": 2.0}}
    rec = ali.frame_record(row, "unit")
    ok_block = rec["block_id"] == row["pose_stamp_ns"] // ali.BLOCK_NS
    ok_dt = rec["pose_scan_dt_ns"] is None       # not invented when the input omits it
    return ok_transport and ok_block and ok_dt, {"relative_diff": rel,
                                                 "block_id": rec["block_id"],
                                                 "pose_scan_dt_ns": rec["pose_scan_dt_ns"]}


def test_6_shadow_leaves_old_decision_unchanged():
    """Same-trace toggle: shadow on and off must leave every old decision field identical."""
    row = {"pose_stamp_ns": 1627785262123456789, "scan_stamp_ns": 1627785261982946396,
           "kf_id": 3, "status": "UNAVAILABLE", "status_from_conditions": "UNAVAILABLE",
           "nis_present": True,
           "support": {"pass": False, "reference_points": 5, "reason": "ok"},
           "nis": {"source": "computed", "computed": True,
                   "selected_reference_source": "prev_scan", "effective_nis": 2.0}}
    before = (row["status"], row["support"]["pass"], row["nis"]["effective_nis"])
    rec = ali.frame_record(row, "unit")
    after = (row["status"], row["support"]["pass"], row["nis"]["effective_nis"])
    ok_copy = rec["old"]["status"] == before[0] and rec["old"]["nis_reference"] == "prev_scan"
    ok_single = ok_copy and before == after

    # Real trace A (402 rows): attach a shadow state to every row and compare the old fields,
    # the channel scores and the support values against the same rows without the shadow block.
    rows = list(ali.load_rows(ali.RUNS["A"]["frames"]))
    frames = [ali.frame_record(r, "A") for r in rows]
    base = [(f["old"]["status"], f["old"]["nis_source"], f["old"]["nis_reference"],
             f["channels"]["M"]["score"], f["channels"]["T"]["score"],
             f["support"]["supported_fraction"]) for f in frames]
    blocks = ali.block_summary(frames, ali.Calibration())
    state = {b["block_id"]: {"state": b["state"], "scope": b["scope"]} for b in blocks}
    on = [dict(f, shadow=state[f["block_id"]]) for f in frames]
    same = all(on[i]["old"] == frames[i]["old"] and on[i]["channels"] == frames[i]["channels"]
               for i in range(len(frames)))
    raw_ok = all(frames[i]["old"]["status"] == rows[i].get("status")
                 and frames[i]["old"]["nis_source"] == (rows[i].get("nis") or {}).get("source")
                 for i in range(len(rows)))
    block_counts = {s: sum(1 for x in state.values() if x["state"] == s)
                    for s in sorted({x["state"] for x in state.values()})}
    frame_counts = {s: sum(1 for f in frames if state[f["block_id"]]["state"] == s)
                    for s in sorted({x["state"] for x in state.values()})}
    return ok_single and same and raw_ok and len(frames) == 402, {
        "single_row_unchanged": ok_single,
        "real_trace_frames": len(frames), "real_trace_blocks": len(blocks),
        "frame_to_block": f"{len(frames)} rows grouped into {len(blocks)} 0.5 s blocks",
        "toggle_identical": same, "old_fields_match_input": raw_ok,
        "block_counts": block_counts, "state_counts_frames": frame_counts}


def test_7_dwell_does_not_cross_missing_block():
    """A gap (or a NO_DATA block) breaks the two-adjacent-block dwell; last_suspect is kept."""
    calib = calib_all()
    # Two adjacent alarms -> SUSPECT at block 9. A later alarm alone after a gap must stay UNKNOWN.
    out = ali.classify_blocks([block(8, m="ALARM"), block(9, m="ALARM"), block(12, m="ALARM")],
                              calib)
    ok_gap = out[1]["state"] == "SUSPECT" and out[-1]["state"] == "UNKNOWN"
    ok_keep = out[-1]["last_suspect_block"] == 9
    nodata = {"block_id": 10, "verdicts": {k: {"verdict": "NO_DATA", "u": None}
                                           for k in ("M", "T", "I")}}
    out2 = ali.classify_blocks([block(8, m="ALARM"), block(9, m="ALARM"), nodata,
                                block(11, m="ALARM")], calib)
    ok_nodata = out2[2]["state"] == "UNKNOWN" and out2[-1]["state"] == "UNKNOWN"
    ok_keep2 = out2[-1]["last_suspect_block"] == 9

    def fake(bid):
        return {"block_id": bid, "map_support": "LOW", "old": {"status": "UNAVAILABLE"},
                "channels": {ch: {"name": ch, "present": False, "fresh": False, "score": None,
                                  "reason": None} for ch in ("M", "T", "I")}}
    blocks = ali.block_summary([fake(8), fake(12)], ali.Calibration())
    ok_fill = ([b["block_id"] for b in blocks] == [8, 9, 10, 11, 12]
               and all(b["context"] == "NO_DATA" for b in blocks[1:4]))
    return ok_gap and ok_keep and ok_nodata and ok_keep2 and ok_fill, {
        "gap_only_last": out[-1], "no_data_last": out2[-1],
        "filled_block_ids": [b["block_id"] for b in blocks]}


TESTS = [
    ("T1.1 low support cross-modal consistency / T-only", test_1_low_support_cross_modal_consistency),
    ("T1.2 low support qualified conflict -> SUSPECT", test_2_low_support_qualified_conflict),
    ("T1.3 missing / carried semantics", test_3_missing_and_carried),
    ("T1.4 per-source calibration and scope", test_4_per_source_calibration_and_scope),
    ("T1.5 SE(3) and time contract", test_5_frame_and_time_contract),
    ("T1.6 shadow leaves old decision unchanged", test_6_shadow_leaves_old_decision_unchanged),
    ("T1.7 dwell does not cross a missing block", test_7_dwell_does_not_cross_missing_block),
]


def run_all():
    results = []
    for name, fn in TESTS:
        try:
            ok, detail = fn()
        except Exception as exc:                       # noqa: BLE001 - recorded, not hidden
            ok, detail = False, {"error": f"{type(exc).__name__}: {exc}"}
        results.append({"test": name, "status": "PASS" if ok else "FAIL", "detail": detail})
    failed = sum(1 for r in results if r["status"] != "PASS")
    return {"marker": "SYNTHETIC_UNIT", "tests": results, "failed": failed}


if __name__ == "__main__":
    import json
    print(json.dumps(run_all(), indent=1, ensure_ascii=False))
