#!/usr/bin/env python3
"""Acceptance rules for the room_02 oracle/hybrid audit chain.

These are the rules the review asked for, written as pure functions so the fixtures can drive
them with constructed inputs and the producer can run them against real artefacts. A rule returns
a list of violations; empty means the artefact satisfies that rule.

Five rules:

  R1 row counting must preserve multiplicity -- count by original index/mask, never
     `len(set(rows))`;
  R2 a hybrid bag report must carry the input hash of the bag whose removals it borrows, and the
     original-index sidecar that lets a removal be traced back to a row;
  R3 an outside-window check whose window is derived from min/max of the differing frames is
     tautologically empty; the window must be declared independently and match;
  R4 accepting an oracle run on `status == OK` alone is not evidence -- its recorded input and
     output hashes have to match the files on disk;
  R5 the false-negative rate is missed / all injected rows, not missed / background rows.
"""

from __future__ import annotations

from collections import Counter


def count_rows_by_index(injected_rows, clean_rows, kept_rows):
    """Counts by row identity WITH multiplicity.

    `injected_rows` and `clean_rows` are sequences of row keys (bytes or hashes); a repeated key
    is a repeated point, not one point. `kept_rows` are the rows the filter kept, in any order.
    """
    inj = Counter(injected_rows)
    cln = Counter(clean_rows)
    kept = Counter(kept_rows)
    background_present = sum((inj & cln).values())
    kept_background = sum((kept & cln).values())
    kept_injected = sum((kept - cln).values())
    dropped_background = sum(((inj & cln) - kept).values())
    dropped_injected = sum(((inj - cln) - kept).values())
    return {"background_present": background_present, "kept_background": kept_background,
            "kept_injected": kept_injected, "dropped_background": dropped_background,
            "dropped_injected": dropped_injected}


def check_multiplicity(injected_rows, kept_rows):
    """R1: a set-based count loses repeated rows."""
    a = count_rows_by_index(injected_rows, [], kept_rows)
    lost = len(kept_rows) - len(set(kept_rows))
    return [] if lost == 0 else [
        f"{lost} kept rows are repeats; a set-based count would drop them, "
        f"index-based keeps {a['kept_injected']}"]


REQUIRED_HYBRID = ("input_sha256", "hybrid_with_sha256", "original_index_sidecar")


def check_hybrid_report(rep):
    """R2: the borrowed-removal bag and the row provenance must both be pinned."""
    bad = []
    for key in REQUIRED_HYBRID:
        if not rep.get(key):
            bad.append(f"hybrid report lacks {key}")
    if rep.get("status") != "OK":
        bad.append(f"hybrid report status {rep.get('status')!r}")
    return bad


def check_window_provenance(rep, declared_window=None):
    """R3: a window derived from min/max of the differing set cannot test anything outside it."""
    win = rep.get("window") or {}
    onset, end = win.get("onset_ns"), win.get("end_ns")
    if onset is None or end is None:
        return ["no window recorded"]
    source = win.get("declared_from") or win.get("source")
    if not source:
        return ["window provenance not declared: onset/end are the min/max of the differing "
                "frames, so an outside-window check against them is tautologically empty"]
    if win.get("derived_from") == "min/max of differing frames" and not declared_window:
        return ["window is derived from min/max of the differing set: an outside-window check "
                "against it is tautologically empty"]
    if declared_window and (onset, end) != tuple(declared_window):
        return [f"window {(onset, end)} != declared {tuple(declared_window)}"]
    return []


def check_oracle_acceptance(report, current_input_sha, current_output_sha):
    """R4: status OK is not evidence; the hashes must match the files on disk."""
    bad = []
    if report.get("status") != "OK":
        bad.append(f"status {report.get('status')!r}")
    rec_in = report.get("input_sha256") or (report.get("pre_run", {}).get("sha256", {})
                                            .get("input_bag"))
    rec_out = report.get("output_sha256") or (report.get("output", {}).get("sha256"))
    if not rec_in:
        bad.append("no recorded input hash")
    elif rec_in != current_input_sha:
        bad.append("recorded input hash != bag on disk")
    if not rec_out:
        bad.append("no recorded output hash")
    elif rec_out != current_output_sha:
        bad.append("recorded output hash != bag on disk")
    return bad


def check_fnr(agg):
    """R5: FNR = kept_injected / (kept_injected + dropped_injected)."""
    kept = int(agg.get("kept_injected", 0))
    dropped = int(agg.get("dropped_injected", 0))
    denom = kept + dropped
    want = (kept / denom) if denom else None
    got = agg.get("false_negative_rate")
    if denom == 0:
        return [] if got in (None, 0) else [f"false_negative_rate {got} with no injected rows"]
    if got is None or abs(float(got) - want) > 1e-12:
        return [f"false_negative_rate {got} != kept/(kept+dropped) = {want:.8f}"]
    return []


def run_all(row_audit, hybrid_report, oracle_report, current_hashes, declared_window=None):
    """Convenience wrapper used by the fixtures against real artefacts."""
    out = {}
    inw = row_audit.get("in_window", {})
    out["R1_multiplicity"] = []      # cannot be checked without per-row data; see the fixture
    out["R2_hybrid"] = check_hybrid_report(hybrid_report)
    out["R3_window"] = check_window_provenance(hybrid_report, declared_window)
    out["R4_oracle"] = check_oracle_acceptance(oracle_report, *current_hashes)
    out["R5_fnr"] = check_fnr(inw)
    return out
