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
BIST = os.path.join(_HERE, "room02_bistability_results.json")
BEFORE = os.environ.get("TWOBY2_BEFORE", "/tmp/2x2_before.json")

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


def audit_receipts(manifest, receipts=None, hasher=None, exists=None, arms=None,
                   expect_per_arm=2):
    """Each receipt must bind its bag and the runner identity; the identity must be shared.

    `receipts`, `hasher` and `exists` are injectable so the fixtures can exercise a mismatch
    without fabricating a 1.3 GB bag.
    """
    hasher = hasher or _sha256
    exists = exists or os.path.exists
    if receipts is None:
        paths = sorted(glob.glob(os.path.join(_HERE, "room02_2x2_receipt_fl_run_*.json")))
        receipts = [json.load(open(p, encoding="utf-8")) for p in paths]
        names = [os.path.basename(p) for p in paths]
    else:
        names = [r.get("_name", f"receipt{i}") for i, r in enumerate(receipts)]

    arms = tuple(arms) if arms else CELLS
    declared = {a: manifest["arms"][a].get("sha256") for a in manifest["arms"]}
    rows, bad = [], []
    for name, rec in zip(names, receipts):
        pre = rec.get("pre_run", {})
        bag = pre.get("paths", {}).get("input_bag")
        sha = pre.get("sha256", {}).get("input_bag")
        arm = ARM_OF_BAG.get(bag)
        if arm is None:
            bad.append(f"{name}: input bag {bag} is not a 2x2 cell")
            continue
        if sha != declared.get(arm):
            bad.append(f"{name}: {arm} sha {str(sha)[:12]} != manifest "
                       f"{str(declared.get(arm))[:12]}")
        if rec.get("status") != "OK":
            bad.append(f"{name}: status {rec.get('status')}")
        if pre.get("paths", {}).get("host_binary") != \
                "/home/R26534/fast_livo2_ws/devel/lib/fast_livo/fastlivo_mapping":
            bad.append(f"{name}: host binary not the expected one")
        if not pre.get("host_revision"):
            bad.append(f"{name}: no host revision")
        rows.append({"receipt": name, "arm": arm, "input_sha256": sha,
                     "host_revision": pre.get("host_revision"),
                     "status": rec.get("status")})

    per_arm = {a: sum(1 for r in rows if r["arm"] == a) for a in arms}
    for a, n in per_arm.items():
        if n != expect_per_arm:
            bad.append(f"{a} has {n} receipts, expected {expect_per_arm}")

    disk = {}
    for a in arms:
        path = f"/tmp/fastlivo/room02_2x2_{a}.bag"
        if not exists(path):
            disk[a] = None
            bad.append(f"{a}: bag missing on disk, hash unverifiable")
            continue
        disk[a] = hasher(path) == declared.get(a)
        if not disk[a]:
            bad.append(f"{a}: bag sha on disk != manifest")

    for field, label in (("script", "runner script"), ("config_m2dgr", "m2dgr config"),
                         ("config_camera", "camera config")):
        vals = {rec.get("pre_run", {}).get("sha256", {}).get(field) for rec in receipts}
        if len(vals) != 1:
            bad.append(f"{label} differs across receipts: {sorted(map(str, vals))}")
    revs = {rec.get("pre_run", {}).get("host_revision") for rec in receipts}
    if len(revs) != 1:
        bad.append(f"host revision differs across receipts: {sorted(map(str, revs))}")

    outputs = []
    for name, rec in zip(names, receipts):
        out = rec.get("output", {})
        bag, sha = out.get("bag"), out.get("sha256")
        present = bool(bag) and exists(bag)
        match = (hasher(bag) == sha) if present and sha else None
        if not sha:
            bad.append(f"{name}: no output hash")
        elif not present:
            bad.append(f"{name}: output bag missing on disk, hash unverifiable")
        elif not match:
            bad.append(f"{name}: output bag sha does not match disk")
        outputs.append({"bag": bag, "sha256": sha, "on_disk": present, "match": match})

    return {"verdict": "PASS" if not bad else "FAIL", "problems": bad,
            "receipts": rows, "per_arm": per_arm,
            "bag_hashes_on_disk_match_manifest": disk,
            "identity_shared": not any("differs across receipts" in b for b in bad),
            "outputs": outputs}


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
    expected = {(a, r) for a in CELLS for r in (1, 2)}
    missing_host = sorted(expected - set(host))
    missing_ind = sorted(expected - set(ind))
    if missing_host or missing_ind:
        problems = []
        if missing_host:
            problems.append(f"host missing {missing_host}")
        if missing_ind:
            problems.append(f"independent missing {missing_ind}")
        return {"verdict": "UNVERIFIABLE", "problems": problems, "per_run": rows}
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


UNCHANGED_FIELDS = ("ate_full_alignment_diagnostic_m", "coverage", "unsupported_fraction",
                    "in_window_unsupported_fraction", "healthy_unsupported_fraction",
                    "frames_scored", "poses_matched_gt")


def audit_frozen_transform(results):
    """One clean->GT transform, fitted on pre-onset clean keyframes, reused by every run."""
    bad = []
    cg = results.get("clean_to_gt") or {}
    if not cg.get("transform"):
        bad.append("no clean->GT transform recorded")
    if int(cg.get("matched", 0)) < 10:
        bad.append(f"clean->GT fitted on {cg.get('matched')} poses: too few")
    per_cell = [k for k, v in (results.get("cells") or {}).items() if v.get("clean_to_gt")]
    if per_cell:
        bad.append(f"{len(per_cell)} cells carry their own clean->GT, so it is not frozen")
    return {"verdict": "PASS" if not bad else "FAIL", "problems": bad,
            "matched": cg.get("matched"), "residual_rmse_m": cg.get("residual_rmse_m"),
            "fitted_on": cg.get("fitted_on")}


def audit_hash_chain(results, manifest):
    """Recorded bag hashes must match the manifest and the files actually on disk."""
    bad = []
    m = results.get("inputs", {}).get("map_bags", {})
    # the results name cells by display form ("O+F"); the manifest uses canonical names
    by_display = {v: k for k, v in DISPLAY.items()}
    for cell in CELLS:
        rec = m.get(by_display.get(cell, cell)) or m.get(cell) or {}
        want = manifest["arms"][cell].get("sha256")
        if rec.get("sha256") != want:
            bad.append(f"{cell}: recorded map sha != manifest")
        path = rec.get("path")
        if not path or not os.path.exists(path):
            bad.append(f"{cell}: map bag missing on disk")
        elif _sha256(path) != want:
            bad.append(f"{cell}: map bag on disk != manifest")
    runs = results.get("inputs", {}).get("run_bags", {})
    if len(runs) != 8:
        bad.append(f"{len(runs)} run bags recorded, expected 8")
    for key, rec in runs.items():
        path = rec.get("path") if isinstance(rec, dict) else None
        sha = rec.get("sha256") if isinstance(rec, dict) else rec
        if not path or not os.path.exists(path):
            bad.append(f"{key}: run bag missing on disk")
            continue
        if _sha256(path) != sha:
            bad.append(f"{key}: run bag sha differs from disk")
    return {"verdict": "PASS" if not bad else "FAIL", "problems": bad,
            "map_bags_on_disk": {c: os.path.exists(
                ((m.get(by_display.get(c, c)) or m.get(c)) or {}).get("path", ""))
                for c in CELLS},
            "run_bags": len(runs)}


def audit_diagnostic_unchanged(new, before):
    """The fix may touch the protocol ATE only; the diagnostic and map fields must not move."""
    bad, rows = [], []
    n_cells = new.get("cells") or {}
    b_cells = before.get("cells") or {}
    for key in sorted(set(b_cells)):
        if key not in n_cells:
            bad.append(f"{key} disappeared")
            continue
        changed = [f for f in UNCHANGED_FIELDS
                   if n_cells[key].get(f) != b_cells[key].get(f)]
        rows.append({"cell": key, "changed_fields": changed})
        if changed:
            bad.append(f"{key}: {changed} changed")
    return {"verdict": "PASS" if not bad else "FAIL", "problems": bad, "per_cell": rows,
            "protocol_field": "ate_frozen_prefix_protocol_m",
            "protocol_values": {k: v.get("ate_frozen_prefix_protocol_m")
                                for k, v in sorted(n_cells.items())}}


def audit_bistability(results, manifest, receipts):
    """Modes must follow the stated rule, and counts are magnitudes, not probabilities."""
    bad = []
    proto = results.get("protocol") or {}
    rule = proto.get("mode_rule", "")
    good_t, bad_t = 0.10, 0.50
    if "< 0.1" not in rule or "> 0.5" not in rule:
        bad.append(f"mode_rule does not state the thresholds: {rule!r}")
    per_run = results.get("new_runs") or {}
    seq = {c: [] for c in proto.get("cells", [])}
    for key, rec in per_run.items():
        arm = key.split("#")[0]
        u = rec.get("unsupported_fraction")
        want = "GOOD" if u < good_t else ("BAD" if u > bad_t else "UNCLEAR")
        if rec.get("mode") != want:
            bad.append(f"{key}: mode {rec.get('mode')} but unsupported {u:.4f} implies {want}")
        if arm in seq:
            seq[arm].append(want)
    for cell, rec in (results.get("cells") or {}).items():
        if list(rec.get("sequence", [])) != seq.get(cell):
            bad.append(f"{cell}: recorded sequence {rec.get('sequence')} != recomputed "
                       f"{seq.get(cell)}")
        tot = rec.get("good", 0) + rec.get("bad", 0) + rec.get("unclear", 0)
        comb = rec.get("combined_with_earlier_2", {})
        n_comb = len(comb.get("modes", []))
        if tot != len(seq.get(cell)):
            bad.append(f"{cell}: counts sum to {tot}, sequence has {len(seq.get(cell))}")
        if n_comb and (comb.get("good", 0) + comb.get("bad", 0)) > n_comb:
            bad.append(f"{cell}: combined counts exceed {n_comb} runs")
    # a count out of six is a magnitude; wording that turns it into a rate is a finding
    text = json.dumps(results.get("cells"), ensure_ascii=False)
    for token in ("probability", "p =", "rate of", "chance"):
        if token in text:
            bad.append(f"count is described as a {token!r}: a 2/6 count is a magnitude, not a "
                       "probability")
    return {"verdict": "PASS" if not bad else "FAIL", "problems": bad,
            "mode_rule": rule, "recomputed_sequences": seq}


def check_common_mode_consistency(bist):
    """Per-run mode and common-set mode must agree, and the crossing flags must follow the data."""
    bad = []
    for grp in ("new_runs", "earlier_2x2_runs"):
        for key, rec in (bist.get(grp) or {}).items():
            if rec.get("mode") != rec.get("mode_common"):
                bad.append(f"{key}: mode {rec.get('mode')} != mode_common {rec.get('mode_common')}")
    for cell, rec in (bist.get("cells") or {}).items():
        seq, common = rec.get("sequence", []), rec.get("sequence_common_set", [])
        if seq != common:
            bad.append(f"{cell}: per-run sequence {seq} != common-set sequence {common}")
        crosses_ga = ("GOOD" in seq) and ("BAD" in seq)
        if bool(rec.get("crosses_good_and_bad")) != crosses_ga:
            bad.append(f"{cell}: crosses_good_and_bad {rec.get('crosses_good_and_bad')} "
                       f"but sequence {seq} implies {crosses_ga}")
        crosses_any = len(set(seq)) > 1
        if bool(rec.get("crosses_modes")) != crosses_any:
            bad.append(f"{cell}: crosses_modes {rec.get('crosses_modes')} but {seq} implies "
                       f"{crosses_any}")
    return {"verdict": "PASS" if not bad else "FAIL", "problems": bad}


def check_run_output_hashes(bist, receipts):
    """Every recorded run hash must be a receipt's output and match the file on disk."""
    by_sha = {}
    for rec in receipts:
        out = rec.get("output", {})
        if out.get("sha256") and out.get("bag"):
            by_sha[out["sha256"]] = out["bag"]
    bad, checked = [], 0
    for grp in ("new_runs", "earlier_2x2_runs"):
        for key, rec in (bist.get(grp) or {}).items():
            sha = rec.get("output_sha256")
            checked += 1
            if not sha:
                bad.append(f"{key}: no output_sha256")
            elif sha not in by_sha:
                bad.append(f"{key}: hash does not match any receipt output")
            elif _sha256(by_sha[sha]) != sha:
                bad.append(f"{key}: output bag on disk != recorded hash")
    return {"verdict": "PASS" if not bad else "FAIL", "problems": bad, "checked": checked}


def main():
    results = json.load(open(RESULTS, encoding="utf-8"))
    prereg = json.load(open(PREREG, encoding="utf-8"))
    manifest = json.load(open(BAGS, encoding="utf-8"))
    ev = json.load(open(EVAL, encoding="utf-8")) if os.path.exists(EVAL) else {}
    out = {"subject": "room_02 2x2 host results", "read_only": True,
           "1_protocol": audit_protocol(results, prereg),
           "2_receipts": audit_receipts(manifest),
           "3_independent": audit_independent(results, ev),
           "4_ate_convention": audit_ate_convention(results),
           "5_frozen_transform": audit_frozen_transform(results),
           "6_hash_chain": audit_hash_chain(results, manifest),
           "9_bist_runs": {
               "modes": check_common_mode_consistency(json.load(open(BIST, encoding="utf-8"))),
               "hashes": check_run_output_hashes(
                   json.load(open(BIST, encoding="utf-8")),
                   [json.load(open(p, encoding="utf-8")) for p in sorted(
                       glob.glob(os.path.join(_HERE, "room02_bist_receipt_fl_run_*.json"))
                       + glob.glob(os.path.join(_HERE, "room02_2x2_receipt_fl_run_*.json")))]),
           },
           "8_bistability": dict(
               audit_bistability(json.load(open(BIST, encoding="utf-8")), manifest,
               [json.load(open(p, encoding="utf-8")) for p in sorted(glob.glob(
                   os.path.join(_HERE, "room02_bist_receipt_fl_run_*.json")))]
               if glob.glob(os.path.join(_HERE, "room02_bist_receipt_fl_run_*.json"))
               else None),
               receipts=audit_receipts(
                   manifest,
                   receipts=[json.load(open(p, encoding="utf-8")) for p in sorted(glob.glob(
                       os.path.join(_HERE, "room02_bist_receipt_fl_run_*.json")))],
                   arms=("O", "O_plus_F_minus_B"), expect_per_arm=4)),
           "7_diagnostic_unchanged": (
               audit_diagnostic_unchanged(results, json.load(open(BEFORE, encoding="utf-8")))
               if os.path.exists(BEFORE) else
               {"verdict": "UNVERIFIABLE", "problems": [f"no baseline at {BEFORE}"],
                "per_cell": []})}
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, default=float)
    for k in ("1_protocol", "2_receipts", "3_independent", "4_ate_convention",
              "5_frozen_transform", "6_hash_chain", "7_diagnostic_unchanged",
              "8_bistability", "9_bist_runs"):
        if k == "9_bist_runs":
            print(k, {name: v["verdict"] for name, v in out[k].items()})
            continue
        print(k, out[k]["verdict"], (out[k].get("problems")
                                     or out[k].get("cells_where_conventions_disagree")
                                     or [])[:3])
    print("wrote", OUT)


if __name__ == "__main__":
    main()
