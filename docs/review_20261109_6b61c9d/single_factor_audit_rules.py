#!/usr/bin/env python3
"""Acceptance rules for the single-factor 2x2 bag construction (review dc714e9).

The verifier reports four booleans, but three of them are "no failure of type X", which is true
when the loop never reaches a frame of type X. These rules close that: a check over an empty
population is a violation, not a pass, and a missing field is UNVERIFIABLE rather than OK.

Each rule returns a list of violations; empty means satisfied.
"""

from __future__ import annotations

REQUIRED_CHECKS = ("outside_all_equal_filtered", "combined_equals_actual_in_window",
                   "arms_match_original_indices", "row_counts_match")


def _verdict(bad):
    return "PASS" if not bad else bad[0]


def _kind_count(receipt, kind):
    """Typed counts are authoritative when present; the `why` text is only a fallback.

    The verifier now emits `failure_counts`, so a rule that still keys off message prefixes would
    repeat the weakness it was written to catch.
    """
    fc = receipt.get("failure_counts")
    if isinstance(fc, dict) and kind in fc:
        return int(fc[kind])
    return None


def check_outside_equals_filtered(receipt):
    """Every arm must reproduce the filtered bag outside the window -- and there must be frames.

    `n_out == 0` makes the verifier's boolean vacuously true, so it is rejected here.
    """
    bad = []
    frames = receipt.get("frames") or {}
    checks = receipt.get("checks") or {}
    fails = receipt.get("failures")
    if fails is None or not checks:
        return ["receipt lacks `checks` or `failures`: nothing to verify"]
    n_out = int(frames.get("outside", 0))
    if n_out <= 0:
        bad.append("no outside-window frame: the equality check is vacuously true")
    if "outside_all_equal_filtered" not in checks:
        bad.append("check `outside_all_equal_filtered` absent")
    n_kind = _kind_count(receipt, "outside_mismatch")
    if n_kind is not None:
        if n_kind:
            bad.append(f"{n_kind} outside_mismatch failures recorded")
    elif any(str(f.get("why", "")).startswith("outside") for f in fails):
        bad.append("at least one arm differs from the filtered bag outside the window")
    if checks.get("outside_all_equal_filtered") is False:
        bad.append("verifier reported outside_all_equal_filtered = False")
    return bad


def check_combined_equals_filtered(receipt):
    """O+F-B inside the window must BE the actual filtered scan, not merely resemble it."""
    bad = []
    frames = receipt.get("frames") or {}
    checks = receipt.get("checks") or {}
    fails = receipt.get("failures")
    if fails is None or not checks:
        return ["receipt lacks `checks` or `failures`: nothing to verify"]
    n_in = int(frames.get("in_window", 0))
    if n_in <= 0:
        bad.append("no in-window frame: the combined-cell check is vacuously true")
    if "combined_equals_actual_in_window" not in checks:
        bad.append("check `combined_equals_actual_in_window` absent")
    n_kind = _kind_count(receipt, "combined_mismatch")
    if n_kind is not None:
        if n_kind:
            bad.append(f"{n_kind} combined_mismatch failures recorded")
    elif any("combined cell" in str(f.get("why", "")) for f in fails):
        bad.append("O+F-B differs from the filtered scan inside the window")
    if checks.get("combined_equals_actual_in_window") is False:
        bad.append("verifier reported combined_equals_actual_in_window = False")
    return bad


def check_all_checks_present(receipt):
    checks = receipt.get("checks") or {}
    missing = [c for c in REQUIRED_CHECKS if c not in checks]
    return [f"missing check {c}" for c in missing]


def check_preregistration(design):
    """Two repetitions per cell and a 1.0 m ATE failure threshold, declared before the run.

    `design` is the pre-registered record. A field that appears only in the results is not a
    pre-registration: this rule reads the design, and the test forbids taking it from results.
    """
    bad = []
    if design.get("declared_before_results") is not True:
        bad.append("criteria not marked as declared before results")
    reps = design.get("repetitions_per_cell")
    if reps is None:
        bad.append("repetitions_per_cell not declared")
    elif int(reps) < 2:
        bad.append(f"repetitions_per_cell {reps} < 2")
    thr = design.get("failure_threshold_ate_m")
    if thr is None:
        bad.append("failure_threshold_ate_m not declared")
    elif abs(float(thr) - 1.0) > 1e-9:
        bad.append(f"failure_threshold_ate_m {thr} != 1.0")
    cells = design.get("cells")
    if cells is not None and sorted(cells) != sorted(["O", "O_plus_F", "O_minus_B",
                                                      "O_plus_F_minus_B"]):
        bad.append(f"cells {cells} are not the four 2x2 cells")
    return bad


def run_all(receipt, design=None):
    out = {
        "outside_equals_filtered": check_outside_equals_filtered(receipt),
        "combined_equals_filtered": check_combined_equals_filtered(receipt),
        "checks_present": check_all_checks_present(receipt),
    }
    if design is not None:
        out["preregistration"] = check_preregistration(design)
    return {k: {"violations": v, "verdict": _verdict(v)} for k, v in out.items()}
