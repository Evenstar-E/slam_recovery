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
HALL01 = json.load(open(os.path.join(_HERE, "hall01_stability_results.json"), encoding="utf-8"))
HALL01_PATHS = sorted(glob.glob(os.path.join(_HERE, "hall01_stab_receipt_fl_run_*.json")))
HALL01_RECEIPTS = [json.load(open(p, encoding="utf-8")) for p in HALL01_PATHS]
HALL01_NAMES = [os.path.basename(p) for p in HALL01_PATHS]
LIB_GAP = (json.load(open(os.path.join(_HERE, "library_hash_gap.json"), encoding="utf-8"))
           if os.path.exists(os.path.join(_HERE, "library_hash_gap.json")) else {})
T3A_RESULTS = json.load(open(os.path.join(_HERE, "room02_T3a_results.json"), encoding="utf-8"))
T3A_ENRICHED = json.load(open(os.path.join(_HERE, "room02_T3a_enriched_results.json"),
                              encoding="utf-8"))
T3A_PATHS = sorted(glob.glob(os.path.join(_HERE, "room02_T3a*_receipt_r*.json")))
T3A_RECEIPTS = [json.load(open(p, encoding="utf-8")) for p in T3A_PATHS]
T3A_NAMES = [os.path.basename(p) for p in T3A_PATHS]
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


def expected_run_labels(bist):
    """The labels the protocol implies: R new repeats per cell plus the two pooled earlier ones."""
    proto = bist.get("protocol") or {}
    cells = proto.get("cells") or []
    reps = int(proto.get("repeats_per_cell") or 0)
    labels = {f"new:{c}#{i}" for c in cells for i in range(1, reps + 1)}
    labels |= {f"earlier:{c}#{i}" for c in cells for i in (1, 2)}
    return labels


def check_run_identity(bist):
    """Every analysed run must be present, uniquely labelled, and none may be silently missing.

    An empty or unlabelled input is UNVERIFIABLE: the previous version compared two internal
    lists and returned PASS for `{}`, which is a check that cannot fail.
    """
    if not bist or not (bist.get("new_runs") or bist.get("earlier_2x2_runs")):
        return {"verdict": "UNVERIFIABLE", "problems": ["no run records to audit"],
                "runs": [], "common_frames": None}
    bad = []
    runs = {}
    for batch, grp in (("new", "new_runs"), ("earlier", "earlier_2x2_runs")):
        for key in (bist.get(grp) or {}):
            # "O#earlier1" is the earlier batch's first repeat of cell O -> "earlier:O#1"
            label = f"{batch}:{key.replace('#earlier', '#')}"
            if label in runs:
                bad.append(f"collision on {label}")
            runs[label] = grp
    expected = expected_run_labels(bist)
    if not expected:
        return {"verdict": "UNVERIFIABLE",
                "problems": ["protocol declares no cells/repeats, so no expected set exists"],
                "runs": sorted(runs), "common_frames": None}
    missing = sorted(expected - set(runs))
    extra = sorted(set(runs) - expected)
    if missing:
        bad.append(f"missing runs: {missing}")
    if extra:
        bad.append(f"unexpected runs: {extra}")
    pav = (bist.get("common_set") or {}).get("per_run_available")
    if not isinstance(pav, dict):
        bad.append("common_set.per_run_available absent: coverage of the run list is unknown")
    else:
        if len(pav) != len(runs):
            bad.append(f"per_run_available lists {len(pav)} runs but {len(runs)} were analysed")
        for label in runs:
            if label not in pav:
                bad.append(f"{label} missing from per_run_available")
        for label in pav:
            if label.split(":")[0] not in ("new", "earlier"):
                bad.append(f"per_run_available entry {label} carries no batch prefix")
    n_runs = (bist.get("common_set") or {}).get("n_runs")
    if n_runs is None:
        bad.append("common_set.n_runs absent")
    elif int(n_runs) != len(runs):
        bad.append(f"common_set.n_runs {n_runs} != {len(runs)} analysed runs")
    return {"verdict": "PASS" if not bad else "FAIL", "problems": bad,
            "runs": sorted(runs), "expected": sorted(expected),
            "common_frames": (bist.get("common_set") or {}).get("n")}


def check_verdict_scope(results, label=""):
    """A verdict must name the runs it covers; a partial verdict cannot be quoted on its own.

    `S3_ACCEPTED_AS_SEED` came from two runs of one build and was later contradicted by four
    runs of the next. Without the run set in the record, the verdict travels alone.
    """
    bad = []
    scope = (results.get("runs_analysed") or results.get("run_set")
             or results.get("runs") or results.get("run_labels"))
    if not scope:
        bad.append(f"{label or 'verdict'} carries no run set")
    build = results.get("build") or results.get("binary") or results.get("host")
    if not build:
        bad.append(f"{label or 'verdict'} carries no build identifier")
    if (results.get("criterion") or {}).get("verdict") and not scope:
        bad.append("criterion.verdict present without the runs it covers")
    return {"verdict": "PASS" if not bad else "FAIL", "problems": bad,
            "scope": scope, "build": str(build)[:80] if build else None}


def check_receipt_library(receipts, results=None, registry=None, batch=None, names=None):
    """An executable hash that is identical across builds cannot identify a build.

    If the behaviour lives in a shared library, the receipt must hash that library too.

    A batch recorded before the requirement existed cannot be back-filled: its receipts only
    carry the shared executable sha, and inventing a library hash per run would fabricate
    provenance. Such a batch is reported as RETROSPECTIVE_PARTIAL -- the gap is known and
    written down -- while a receipt that had no declared gap still fails outright, so the rule
    stays able to catch a new one.
    """
    if not receipts:
        return {"verdict": "UNVERIFIABLE", "problems": ["no receipts"]}
    missing = [r.get("host", {}).get("binary", "")[-40:] for r in receipts
               if not (r.get("host", {}).get("library_sha256")
                       or r.get("host", {}).get("libraries"))]
    if not missing:
        return {"verdict": "PASS", "problems": [], "receipts": len(receipts)}
    gap = (results or {}).get("provenance_gap") or {}
    reg = registry or {}
    entry = (reg.get("batches") or {}).get(batch) if batch else None
    if entry is not None and names:
        # the registry names individual historical records; a new receipt in the same batch
        # must not inherit the excuse just because the batch is listed
        allowed = set(entry.get("records") or [])
        unlisted = [n for n in names if n not in allowed]
        if unlisted:
            return {"verdict": "FAIL",
                    "problems": [f"{len(unlisted)} receipt(s) are not named in the registry "
                                 f"(e.g. {unlisted[0]}) and record no loaded-library hash"],
                    "receipts": len(receipts)}
        listed = True
    else:
        listed = entry is not None
    if gap.get("receipt_library_sha256") == "ABSENT" or listed:
        return {"verdict": "RETROSPECTIVE_PARTIAL",
                "problems": [f"{len(missing)}/{len(receipts)} receipts predate the requirement; "
                             "the gap is declared, not silently missing"],
                "declared_gap": gap if gap else (reg.get("batches", {}).get(batch) if listed
                                                 else None),
                "declared_by": "results" if gap else ("registry" if listed else None),
                "receipts": len(receipts)}
    return {"verdict": "FAIL",
            "problems": [f"{len(missing)}/{len(receipts)} receipts record no loaded-library hash "
                         "and no declared gap explains it"],
            "receipts": len(receipts)}


def check_batch_identity(receipts, expected_input_sha=None):
    """Any batch: one binary, one config, one revision, one input, outputs matching disk."""
    bad = []
    if not receipts:
        return {"verdict": "UNVERIFIABLE", "problems": ["no receipts"]}
    for field, label in (("script", "runner script"), ("config_m2dgr", "m2dgr config"),
                         ("config_camera", "camera config")):
        vals = {r.get("pre_run", {}).get("sha256", {}).get(field) for r in receipts}
        if len(vals) != 1:
            bad.append(f"{label} differs across receipts: {sorted(map(str, vals))}")
    for field, label in (("sha256", "binary sha"), ("source_revision", "revision")):
        vals = {r.get("host", {}).get(field) for r in receipts}
        if len(vals) != 1:
            bad.append(f"{label} differs across receipts: {sorted(map(str, vals))}")
    bags = {(r.get("pre_run", {}).get("paths", {}).get("input_bag"),
             r.get("pre_run", {}).get("sha256", {}).get("input_bag")) for r in receipts}
    if len(bags) != 1:
        bad.append(f"input bag differs across receipts: {sorted(map(str, bags))}")
    elif expected_input_sha and bags.pop()[1] != expected_input_sha:
        bad.append("input bag sha != the one this batch claims")
    for r in receipts:
        if r.get("status") != "OK":
            bad.append(f"status {r.get('status')}")
            break
        out = r.get("output", {})
        if not out.get("sha256") or not out.get("bag"):
            bad.append("a receipt has no output hash")
            break
        if os.path.exists(out["bag"]) and _sha256(out["bag"]) != out["sha256"]:
            bad.append("an output bag does not match its recorded hash")
            break
    return {"verdict": "PASS" if not bad else "FAIL", "problems": bad,
            "receipts": len(receipts)}


def check_hall01_stability(results):
    """The hall_01 applicability numbers, and whether the conclusion rests on labels or on values."""
    bad = []
    runs = results.get("runs") or {}
    n_common = results.get("common_frames")
    if len(runs) != 4:
        bad.append(f"{len(runs)} runs, expected 4")
    for key, r in runs.items():
        if r.get("n_common") != n_common:
            bad.append(f"{key}: n_common {r.get('n_common')} != common {n_common}")
        if r.get("nn_supported_fraction") != 1.0:
            bad.append(f"{key}: nn_supported {r.get('nn_supported_fraction')}")
    u = [r.get("patch_unsupported_fraction") for r in runs.values()]
    spread = (max(u) - min(u)) if u else None
    declared = (results.get("source_spread") or {}).get("range")
    if spread is not None and declared is not None and abs(spread - float(declared)) > 1e-9:
        bad.append(f"spread {spread:.6f} != recorded {declared}")
    modes = [r.get("mode") for r in runs.values()]
    if len(set(modes)) != 1:
        bad.append(f"modes are not uniform: {modes}")
    # a uniform UNCLEAR is not stability evidence by itself
    summary = results.get("summary") or {}
    if set(modes) == {"UNCLEAR"} and not summary.get("note"):
        bad.append("all runs UNCLEAR and no note explaining that the label is not the evidence")
    return {"verdict": "PASS" if not bad else "FAIL", "problems": bad,
            "common_frames": n_common, "spread": round(spread, 6) if spread else None,
            "modes": modes}


def check_trajectory_population(results):
    """Trajectory metrics must name the population they were computed on, arms included."""
    bad, notes = [], []
    tr = results.get("trajectory") or {}
    pop = tr.get("population") or {}
    fs = results.get("frame_set") or {}
    arms = [a for a in ("R", "C3") if a in tr]
    if len(arms) != 2:
        bad.append(f"trajectory has {arms}, expected R and C3")
    matched = {tr[a].get("gt_matched") for a in arms}
    if len(matched) != 1:
        bad.append(f"arms match different GT counts: {matched}")
    m = matched.pop() if len(matched) == 1 else None
    if m is not None and pop.get("gt_matched") != m:
        bad.append(f"population.gt_matched {pop.get('gt_matched')} != arm match {m}")
    if pop.get("frame_set") != fs.get("n_frames"):
        bad.append(f"population.frame_set {pop.get('frame_set')} != frame_set "
                   f"{fs.get('n_frames')}")
    if m is not None and fs.get("n_frames") and m >= fs["n_frames"]:
        bad.append("gt_matched equals the frame set: the GT subset is not recorded")
    for a in arms:
        if tr[a].get("ate_full_alignment_diagnostic_m") is None:
            bad.append(f"{a}: no diagnostic ATE")
        if tr[a].get("ate_frozen_prefix_protocol_m") is None:
            bad.append(f"{a}: no protocol ATE")
    cg = results.get("clean_to_gt") or {}
    if int(cg.get("matched", 0)) < 10:
        bad.append(f"clean->GT fitted on {cg.get('matched')} poses")
    if not cg.get("fitted_on"):
        notes.append("clean_to_gt records matched/residual but not the fit window or the "
                     "transform, so a reader cannot check that it was pre-onset")
    return {"verdict": "PASS" if not bad else "FAIL", "problems": bad + notes,
            "gt_matched": m, "frame_set": fs.get("n_frames"),
            "ate": {a: {"full": tr[a].get("ate_full_alignment_diagnostic_m"),
                        "prefix": tr[a].get("ate_frozen_prefix_protocol_m")} for a in arms}}


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
           "11_t3a": {
               "receipt_library": check_receipt_library(T3A_RECEIPTS, T3A_RESULTS,
                                                        LIB_GAP, "room02_T3a", T3A_NAMES),
               "verdict_scope": check_verdict_scope(T3A_RESULTS, "room02_T3a_results"),
               "enriched_scope": check_verdict_scope(T3A_ENRICHED, "room02_T3a_enriched_results"),
               "identity": audit_receipts(
                   manifest,
                   receipts=T3A_RECEIPTS, arms=("O",), expect_per_arm=6),
           },
           "13_hall01_trajectory": check_trajectory_population(
               json.load(open(os.path.join(_HERE, "raw_vs_repaired_results.json"),
                              encoding="utf-8"))),
           "12_hall01": {
               "stability": check_hall01_stability(HALL01),
               "identity": check_batch_identity(HALL01_RECEIPTS),
               "receipt_library": check_receipt_library(HALL01_RECEIPTS, HALL01,
                                                        LIB_GAP, "hall01_stab", HALL01_NAMES),
           },
           "10_run_identity": check_run_identity(
               json.load(open(BIST, encoding="utf-8"))),
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
              "8_bistability", "9_bist_runs", "10_run_identity", "11_t3a", "12_hall01", "13_hall01_trajectory"):
        if k == "13_hall01_trajectory":
            print(k, out[k]["verdict"], out[k]["problems"][:3], out[k]["ate"])
            continue
        if k == "12_hall01":
            print(k, {n: v["verdict"] for n, v in out[k].items()})
            for n, v in out[k].items():
                if v["verdict"] != "PASS":
                    print("   ", n, v.get("problems", [])[:2])
            continue
        if k == "11_t3a":
            print(k, {n: v["verdict"] for n, v in out[k].items()})
            for n, v in out[k].items():
                if v["verdict"] != "PASS":
                    print("   ", n, v.get("problems", [])[:2])
            continue
        if k == "9_bist_runs":
            print(k, {name: v["verdict"] for name, v in out[k].items()})
            continue
        print(k, out[k]["verdict"], (out[k].get("problems")
                                     or out[k].get("cells_where_conventions_disagree")
                                     or [])[:3])
    print("wrote", OUT)


if __name__ == "__main__":
    main()
