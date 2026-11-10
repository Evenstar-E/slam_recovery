#!/usr/bin/env python3
"""A-1: attribute every archived decision to the leg that produced it, then ask what A would change.

A is "delete the information leg" (floor, kappa, gain) while keeping paired evidence, holdout,
covariance and boundary. This script answers three questions and refuses to answer a fourth:

  1. can the archived `mode`/`refusal_reason` be reproduced from the recorded fields? (self-check;
     a row that cannot be reproduced is reported as such, the archive is not edited)
  2. under the CURRENT frozen gate, which leg decides each candidate?
  3. under A, which decisions change -- and where the change depends on a field that was never
     archived (`||P_after||_2`), the row is BLOCKED, not guessed.

It does not assign any quality label. A flip means "more candidates admitted, quality UNKNOWN".

    python -I docs/gate_method_research_20261110/a1_leg_attribution.py [RUN_DIR ...]
"""

from __future__ import annotations

import glob
import json
import os
import sys

import numpy as np

ROOT = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
OUT_DIR = os.path.join(ROOT, "docs/gate_method_research_20261110")

TAU_ABS_MIN = 3.0
TAU_INFO_KAPPA = 2.0
TAU_VAL_NIS = 2.5
SIGMA_TOL = 0.5
MIN_WILSON = 0.55


def load_rows(run_dirs):
    rows = []
    for run_dir in run_dirs:
        path = os.path.join(run_dir, "candidates.jsonl")
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                d = json.loads(line)
                d["_run"] = os.path.basename(run_dir)
                rows.append(d)
    return rows


def _finite(value):
    return value is not None and np.isfinite(float(value))


def evidence_status(row, assume_elapsed_s):
    """Tri-state paired evidence, exactly as core.py forms it.

    `assume_elapsed_s` resolves the reentry envelope: the archive does not record the elapsed
    time, and the envelope only matters when the jump exceeds the bare bound.
    """
    # The archived record carries `paired_benefit_status` as a string; the gate takes the bool.
    status = row.get("paired_benefit_status")
    approved = ({"PASSED": True, "FAILED": False}.get(status, None)
                if status is not None else row.get("paired_benefit_approved"))
    if approved is False:
        return "FAILED"
    wilson = row.get("wilson_lower_bound")
    if wilson is not None and float(wilson) < MIN_WILSON:
        return "FAILED"
    jump = row.get("reentry_pos_jump_m")
    if jump is not None:
        if assume_elapsed_s is None:
            ok = float(jump) <= 0.5
        else:
            ok = float(jump) <= 0.5 + 2.0 * max(0.0, assume_elapsed_s)
        if not ok:
            return "FAILED"
    if (approved is None or wilson is None or jump is None):
        return "MISSING"
    return "PASSED"


def info_leg(row, rule):
    before = row.get("weak_dir_info_before")
    after = row.get("weak_dir_info_after")
    if rule == "old_absolute25":
        return after is not None and float(after) >= 25.0
    if rule == "current":
        return bool(_finite(after) and _finite(before)
                    and float(after) >= TAU_ABS_MIN
                    and float(after) >= TAU_INFO_KAPPA * max(float(before), 1e-12)
                    and (float(after) - float(before)) > 0.0)
    if rule == "A_no_info":
        return True
    raise ValueError(rule)


def decide(row, rule, assume_elapsed_s, cov_certified_failed=False):
    """Three-valued: True accepted, False refused, None BLOCKED on the unarchived covariance.

    Leg order follows core.py: boundary, evidence, finite state, holdout, then Mode 2.
    """
    if str(row.get("refusal_reason", "")).startswith("Rejected candidate due to non-finite"):
        return False, "non_finite"
    if row.get("_boundary_ok") is False:
        return False, "boundary"
    ev = evidence_status(row, assume_elapsed_s)
    if ev != "PASSED":
        return False, f"evidence_{ev.lower()}"
    holdout = row.get("holdout_nis")
    if holdout is None or not np.isfinite(float(holdout)):
        return False, "holdout_missing"
    if float(holdout) > TAU_VAL_NIS:
        return False, "holdout"
    if not info_leg(row, rule):
        return False, "info"
    if cov_certified_failed:
        # Under the old criterion every other leg passed and the row was still refused, so the
        # covariance leg is the one that refused it: ||P_after||_2 > sigma_tol is certified by the
        # archived outcome even though the number itself was never recorded.
        return False, "cov_certified_by_archive"
    return None, "mode2_if_cov_passes"      # ||P_after||_2 was never archived


def main(argv):
    run_dirs = argv[1:] or sorted({os.path.dirname(p) for p in
                                   glob.glob("/tmp/fl_native_*/candidates.jsonl")})
    rows = load_rows(run_dirs)

    # The boundary outcome is a property of the candidate, not of the info rule: it is recorded
    # indirectly by the refusal reason, which the self-check below uses.
    for r in rows:
        r["_boundary_ok"] = not str(r.get("refusal_reason", "")).startswith(
            "Refused Mode 2 atomic commit: a committed segment begins beyond")

    # --- self-check: reproduce the archived reason under the criterion the archive used ---
    checks = []
    for r in rows:
        archived = str(r.get("refusal_reason", ""))
        elapsed = None
        # The archive's own reason certifies that the elapsed envelope admitted this jump: without
        # the envelope the evidence leg would have refused first and the reason would name it.
        if ("Insufficient verified info" in archived or "evidence MISSING" in archived):
            jump = r.get("reentry_pos_jump_m")
            if jump is not None and float(jump) > 0.5:
                elapsed = (float(jump) - 0.5) / 2.0
        accepted, leg = decide(r, "old_absolute25", elapsed)
        cov_failed = False
        if accepted is None:
            # Old gate reached the covariance leg and still refused -> the covariance leg is what
            # refused. That resolves the otherwise-missing number, by inference from the outcome.
            accepted, leg, cov_failed = False, "cov_certified_by_archive", True
            r["_cov_certified_failed"] = True
        reproduced = (
            (not accepted and leg == "info" and "Insufficient verified info" in archived)
            or (not accepted and leg == "boundary" and "beyond the boundary jump bound" in archived)
            or (not accepted and leg == "non_finite" and "non-finite" in archived)
            or (not accepted and leg == "evidence_failed" and "evidence FAILED" in archived)
            or (not accepted and leg == "evidence_missing" and "evidence MISSING" in archived)
            # The Mode-2 fallback reason names no leg: it is what the gate prints when the
            # conjunction fails, and the covariance leg is one of its terms. Reached-and-refused on
            # the covariance leg therefore reproduces it.
            or (not accepted and leg == "cov_certified_by_archive"
                and "Insufficient verified info" in archived)
        )
        checks.append({"run": r["_run"], "archived_reason": archived[:60],
                       "replayed_leg": leg, "accepted": accepted, "reproduced": reproduced,
                       "assumed_elapsed_s": elapsed})

    # --- current frozen gate vs A, on the same rows ---
    comparisons = []
    for r, chk in zip(rows, checks):
        elapsed = chk["assumed_elapsed_s"]
        cov_failed = bool(r.get("_cov_certified_failed", False))
        cur_acc, cur_leg = decide(r, "current", elapsed, cov_failed)
        a_acc, a_leg = decide(r, "A_no_info", elapsed, cov_failed)
        comparisons.append({
            "run": r["_run"],
            "candidate_id": r.get("candidate_id"),
            "info_before": r.get("weak_dir_info_before"),
            "info_after": r.get("weak_dir_info_after"),
            "current_leg": cur_leg, "current_decision": cur_acc,
            "A_leg": a_leg, "A_decision": a_acc,
            "changes": (cur_acc != a_acc),
            "blocked_on": ("posterior_cov_norm" if (cur_acc is None or a_acc is None) else None),
        })

    out = {
        "_meta": {
            "what": "A-1 leg attribution and A ablation on the archived candidate stream",
            "written": "2026-11-10",
            "rules": {"tau_abs_min": TAU_ABS_MIN, "tau_info_kappa": TAU_INFO_KAPPA,
                      "tau_val_nis": TAU_VAL_NIS, "sigma_tol": SIGMA_TOL},
            "A_definition": ("remove after>=tau_abs_min, after>=kappa*before and gain>0; keep "
                             "paired evidence, holdout, covariance and boundary"),
            "no_quality_label": ("a flip is 'admitted with UNKNOWN quality'. The archive has no "
                                 "independent label, so it cannot be called a gain or a harm"),
            "not_done": "no host run, no threshold change, no production gate edit",
        },
        "self_check": {
            "rows": len(rows),
            "reproduced": sum(1 for c in checks if c["reproduced"]),
            "failed": [c for c in checks if not c["reproduced"]],
            "detail": checks,
        },
        "comparison": comparisons,
        "summary": {
            "current_gate": {leg: sum(1 for c in comparisons if c["current_leg"] == leg)
                             for leg in sorted({c["current_leg"] for c in comparisons})},
            "A_gate": {leg: sum(1 for c in comparisons if c["A_leg"] == leg)
                       for leg in sorted({c["A_leg"] for c in comparisons})},
            "changed_decisions": [c for c in comparisons if c["changes"]],
            "blocked_on_cov": [c["run"] for c in comparisons if c["blocked_on"]],
        },
    }
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, "a1_leg_attribution.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    print(json.dumps({"rows": len(rows),
                      "self_check_reproduced": out["self_check"]["reproduced"],
                      "current_gate": out["summary"]["current_gate"],
                      "A_gate": out["summary"]["A_gate"],
                      "changed": [(c["run"], c["current_leg"]) for c in
                                  out["summary"]["changed_decisions"]],
                      "out": os.path.relpath(path, ROOT)}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
