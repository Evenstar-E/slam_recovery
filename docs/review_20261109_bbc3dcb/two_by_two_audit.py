#!/usr/bin/env python3
"""Read-only audit of the room_02 2x2 host results (main acfc820 / b64e22c).

Three questions the review asked: is the criterion still the pre-registered one, are
the eight runs bound to the bags they claim, and does the independent recomputation
disagree with the host only in convention rather than in conclusion.

    python3 -B docs/review_20261109_bbc3dcb/two_by_two_audit.py
"""

from __future__ import annotations

import glob
import hashlib
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_HERE))
for _p in (_HERE, _REPO):
    if _p not in sys.path:
        sys.path.insert(0, _p)

RESULTS = os.path.join(_HERE, "room02_2x2_results.json")
PREREG = os.path.join(_REPO, "docs/review_20261109_6b61c9d/single_factor_preregistration.json")
BAGS = os.path.join(_REPO, "docs/review_20261109_6b61c9d/single_factor_bags.json")
EVAL = os.path.join(_REPO, "docs/review_20261109_6b61c9d/evaluate_2x2_runs.json")
OUT = os.path.join(_HERE, "two_by_two_audit.json")

CELLS = ("O", "O_plus_F", "O_minus_B", "O_plus_F_minus_B")
ARM_OF_BAG = {f"/tmp/fastlivo/room02_2x2_{c}.bag": c for c in CELLS}


def _sha256(path, chunk=1 << 22):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def audit_protocol(results, prereg):
    """Is the post-hoc protocol the same rule that was declared before the runs?"""
    proto = results.get("protocol") or {}
    bad = []
    thr = prereg.get("failure_threshold_ate_m")
    if thr is None:
        bad.append("preregistration has no failure_threshold_ate_m")
    elif f"{float(thr):g}" not in str(proto.get("fail_rule", "")):
        bad.append(f"results fail_rule does not state the pre-registered threshold {thr}")
    if prereg.get("repetitions_per_cell") != 2:
        bad.append("preregistration does not declare two repeats")
    if "both repeats" not in str(proto.get("fail_rule", "")):
        bad.append("results fail_rule does not require both repeats to agree")
    if "O+F-B" not in str(proto.get("interaction_rule", "")):
        bad.append("results interaction_rule does not name O+F-B")
    if "O+F and O-B" not in str(proto.get("interaction_rule", "")):
        bad.append("results interaction_rule does not name the two single factors")
    if prereg.get("declared_before_results") is not True:
        bad.append("preregistration is not marked as declared before results")
    return {"verdict": "PASS" if not bad else "FAIL", "problems": bad,
            "prereg": {"threshold": thr, "repeats": prereg.get("repetitions_per_cell"),
                       "declared_before_results": prereg.get("declared_before_results")},
            "results_protocol": proto}


def audit_receipts(manifest):
    """Each receipt must bind the bag it ran and the runner identity; bag hashes must match."""
    declared = {a: manifest["arms"][a]["sha256"] if "sha256" in manifest["arms"][a]
                else manifest["arms"][a].get("bag_sha256") for a in manifest["arms"]}
    receipts = sorted(glob.glob(os.path.join(_HERE, "room02_2x2_receipt_fl_run_*.json")))
    rows, bad = [], []
    for path in receipts:
        rec = json.load(open(path, encoding="utf-8"))
        pre = rec.get("pre_run", {})
        bag = pre.get("paths", {}).get("input_bag")
        sha = pre.get("sha256", {}).get("input_bag")
        arm = ARM_OF_BAG.get(bag)
        if arm is None:
            bad.append(f"{os.path.basename(path)}: input bag {bag} is not a 2x2 cell")
            continue
        if sha != declared.get(arm):
            bad.append(f"{os.path.basename(path)}: {arm} sha {str(sha)[:12]} != manifest "
                       f"{str(declared.get(arm))[:12]}")
        if rec.get("status") != "OK":
            bad.append(f"{os.path.basename(path)}: status {rec.get('status')}")
        if pre.get("paths", {}).get("host_binary") != \
                "/home/R26534/fast_livo2_ws/devel/lib/fast_livo/fastlivo_mapping":
            bad.append(f"{os.path.basename(path)}: host binary not the expected one")
        if not pre.get("host_revision"):
            bad.append(f"{os.path.basename(path)}: no host revision")
        rows.append({"receipt": os.path.basename(path), "arm": arm,
                     "input_sha256": sha, "host_revision": pre.get("host_revision"),
                     "status": rec.get("status")})
    per_arm = {a: sum(1 for r in rows if r["arm"] == a) for a in CELLS}
    for a, n in per_arm.items():
        if n != 2:
            bad.append(f"{a} has {n} receipts, expected 2")
    return {"verdict": "PASS" if not bad else "FAIL", "problems": bad,
            "receipts": rows, "per_arm": per_arm,
            "bag_hashes_on_disk_match_manifest": {
                a: (_sha256(f"/tmp/fastlivo/room02_2x2_{a}.bag") == declared.get(a)
                    if os.path.exists(f"/tmp/fastlivo/room02_2x2_{a}.bag") else None)
                for a in CELLS}}


DISPLAY = {"O": "O", "O+F": "O_plus_F", "O-B": "O_minus_B", "O+F-B": "O_plus_F_minus_B"}


def _host_runs(results):
    """{"O+F#1": {...}} -> {("O_plus_F", 1): {...}}"""
    out = {}
    for key, v in (results.get("cells") or {}).items():
        arm, _, rep = key.partition("#")
        out[(DISPLAY.get(arm, arm), int(rep))] = v
    return out


def _eval_runs(ev):
    out = {}
    for cell, runs in (ev.get("cells") or {}).items():
        for r in runs:
            out[(DISPLAY.get(cell, cell), int(r["repeat"]))] = r
    return out


def audit_independent(results, ev):
    """Do the two implementations disagree about any cell's side of the threshold?"""
    bad, rows = [], []
    host, ind = _host_runs(results), _eval_runs(ev)
    for key in sorted(host):
        h = host[key]
        e = ind.get(key) or {}
        h_full = h.get("ate_full_alignment_diagnostic_m")
        h_pref = h.get("ate_frozen_prefix_protocol_m")
        e_ate = e.get("ate_rmse_m")
        rows.append({"cell": key[0], "repeat": key[1], "host_full": h_full,
                     "host_prefix": h_pref, "independent": e_ate,
                     "delta_full_vs_independent": (None if h_full is None or e_ate is None
                                                   else round(float(h_full) - float(e_ate), 6))})
        if h_full is not None and e_ate is not None:
            if (float(h_full) > 1.0) != (float(e_ate) > 1.0):
                bad.append(f"{key}: host {h_full:.3f} and independent {e_ate:.3f} "
                           "fall on different sides of 1.0 m")
    return {"verdict": "PASS" if not bad else "FAIL", "problems": bad, "per_run": rows}


def audit_ate_convention(results):
    """Which ATE does the fail rule actually use, and does the other convention agree?

    The results block names "full-alignment ATE > 1.0 m" as the failure test, while the same
    record says the full-alignment number is a diagnostic and the frozen-prefix number is the
    protocol figure. This checks whether the two conventions would classify the cells the same.
    """
    host = _host_runs(results)
    cells = {}
    for arm in CELLS:
        full = [float(host[(arm, r)]["ate_full_alignment_diagnostic_m"] > 1.0)
                if (arm, r) in host else None for r in (1, 2)]
        pref = [float(host[(arm, r)]["ate_frozen_prefix_protocol_m"] > 1.0)
                if (arm, r) in host else None for r in (1, 2)]
        cells[arm] = {"fail_full_alignment": full, "fail_frozen_prefix": pref,
                      "same": full == pref}
    disagree = [a for a, v in cells.items() if not v["same"]]
    return {"cells": cells, "cells_where_conventions_disagree": disagree,
            "verdict": "PASS" if not disagree else "FINDING"}


def main():
    results = json.load(open(RESULTS, encoding="utf-8"))
    prereg = json.load(open(PREREG, encoding="utf-8"))
    manifest = json.load(open(BAGS, encoding="utf-8"))
    ev = json.load(open(EVAL, encoding="utf-8")) if os.path.exists(EVAL) else {}
    out = {"subject": "room_02 2x2 host results", "read_only": True,
           "1_protocol": audit_protocol(results, prereg),
           "2_receipts": audit_receipts(manifest),
           "3_independent": audit_independent(results, ev),
           "4_ate_convention": audit_ate_convention(results)}
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, default=float)
    for k in ("1_protocol", "2_receipts", "3_independent", "4_ate_convention"):
        print(k, out[k]["verdict"], out[k].get("problems", out[k].get(
            "cells_where_conventions_disagree"))[:3])
    print("wrote", OUT)


if __name__ == "__main__":
    main()
