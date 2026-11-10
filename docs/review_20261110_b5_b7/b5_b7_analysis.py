#!/usr/bin/env python3
"""B5/B7: separate the gate from an independent evaluation, using only archived data.

The two questions are different:

  B5  does the gate add value over accepting every candidate?
      -> needs, per candidate: an independent label, the gate's accept/reject, and the reason.
  B7  what does running the gate cost on normal data, and what does a bad repair risk?
      -> needs the same decision records, partitioned by normal / degraded / recovery-tail.

This script does not estimate either from run-level outcomes. It first proves, by scanning every
archived JSON, whether decision records exist at all; if they do not, the affected quantities are
reported as UNAVAILABLE rather than back-inferred. What is genuinely measurable from the archive
(geometry cost per region, run completion) is measured.

    python -I docs/review_20261110_b5_b7/b5_b7_analysis.py [REPO_ROOT]
"""

from __future__ import annotations

import glob
import json
import math
import os
import sys

ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else
                       os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
OUT_DIR = os.path.join(ROOT, "docs/review_20261110_b5_b7")
ARCHIVE = os.path.join(ROOT, "docs/review_20261109_bbc3dcb")

# What a per-candidate record must carry for B5/B7 to be computable at all.
REQUIRED_FIELDS = ("candidate_id", "gate_accept", "gate_reject_reason", "independent_label")
ID_FIELDS = {"candidate_id", "candidate", "cand_id", "id"}
DECISION_FIELDS = {"accepted", "accept", "rejected", "reject", "gate_accepted", "decision"}
REASON_FIELDS = {"reason", "rejection_reason", "refusal_reason", "gate_reason"}
LABEL_FIELDS = {"independent_label", "label", "gt_label", "quality_label", "harmful", "beneficial"}


def wilson(k: int, n: int, z: float = 1.645):
    """Wilson score interval; the project uses z=1.645 (one-sided 95%)."""
    if n == 0:
        return None
    p = k / n
    denom = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return {"k": k, "n": n, "rate": round(p, 6),
            "lo": round(max(0.0, centre - half), 6), "hi": round(min(1.0, centre + half), 6)}


def scan_for_decision_records():
    """Walk every archived JSON and look for a *list of records* that could be a candidate stream.

    A record qualifies only if one object carries identity + decision + (reason or label).
    Records that carry a decision but no independent label are counted separately: the point is
    not "nothing was found", it is "decisions exist and are never paired with a label".
    """
    complete = []
    decision_only = []
    label_only = []
    inventory = []
    for path in sorted(glob.glob(os.path.join(ROOT, "docs/**/*.json"), recursive=True)):
        if os.path.abspath(path).startswith(OUT_DIR + os.sep):
            continue  # never scan this analysis's own output: a rerun must be reproducible
        try:
            doc = json.load(open(path, encoding="utf-8"))
        except Exception:
            continue
        lists = 0
        max_len = 0
        keysets = set()

        def walk(node, depth=0):
            nonlocal lists, max_len
            if depth > 8:
                return
            if isinstance(node, dict):
                for v in node.values():
                    walk(v, depth + 1)
            elif isinstance(node, list):
                if node and all(isinstance(x, dict) for x in node):
                    lists += 1
                    max_len = max(max_len, len(node))
                    keysets.add(tuple(sorted(node[0].keys())))
                    for rec in node:
                        k = set(rec.keys())
                        has_id, has_dec = bool(k & ID_FIELDS), bool(k & DECISION_FIELDS)
                        has_lab = bool(k & LABEL_FIELDS)
                        if has_id and has_dec and has_lab:
                            complete.append({"file": os.path.relpath(path, ROOT),
                                             "keys": sorted(k)})
                        elif has_id and has_dec:
                            decision_only.append({"file": os.path.relpath(path, ROOT),
                                                  "missing": sorted(LABEL_FIELDS - k),
                                                  "keys": sorted(k)})
                        elif has_id and has_lab:
                            label_only.append({"file": os.path.relpath(path, ROOT),
                                               "keys": sorted(k)})
                for v in node[:50]:
                    walk(v, depth + 1)

        walk(doc)
        if lists:
            inventory.append({"file": os.path.relpath(path, ROOT), "record_lists": lists,
                              "longest_list": max_len,
                              "record_shapes": [list(s) for s in sorted(keysets)][:6]})
    return complete, decision_only, label_only, inventory


def b7_measurable():
    """What the archive contains at region granularity -- and why it is not the gate's cost.

    `healthy_unsupported_fraction` / `in_window_unsupported_fraction` describe a *host run* under
    one degradation input. They are not "the price of running the gate", because the archive has
    no with-gate / without-gate pair for the same input, and no post-recovery segment label.
    Keeping them under a descriptive key and not under the B7 quantity names is the whole point.
    """
    p = os.path.join(ARCHIVE, "room02_2x2_results.json")
    d = json.load(open(p, encoding="utf-8"))
    cells = {}
    for name, c in d.get("cells", {}).items():
        cells[name] = {
            "status": c.get("status"),
            "coverage": c.get("coverage"),
            "healthy_region_unsupported_fraction": c.get("healthy_unsupported_fraction"),
            "degraded_window_unsupported_fraction": c.get("in_window_unsupported_fraction"),
            "ate_full_diagnostic_m": c.get("ate_full_alignment_diagnostic_m"),
            "fail": c.get("fail"),
        }
    fails = [c["fail"] for c in cells.values() if c["fail"] is not None]
    return {
        "source": os.path.relpath(p, ROOT),
        "cells": cells,
        "healthy_region_unsupported_fraction": {
            "per_cell": {k: v["healthy_region_unsupported_fraction"] for k, v in cells.items()},
            "range": _range([v["healthy_region_unsupported_fraction"] for v in cells.values()]),
            "caution": ("six of eight cells report 1.0, i.e. a run that lost the map entirely; "
                        "this is a failed host run under its input, not a cost of the gate"),
        },
        "degraded_window_unsupported_fraction": {
            "per_cell": {k: v["degraded_window_unsupported_fraction"] for k, v in cells.items()},
            "range": _range([v["degraded_window_unsupported_fraction"] for v in cells.values()]),
        },
        "run_status": {
            "cells_with_status_OK": sum(1 for c in cells.values() if c["status"] == "OK"),
            "cells": len(cells),
            "fail_rate_across_cells": wilson(sum(1 for f in fails if f), len(fails)),
        },
    }


def _range(values):
    vals = [v for v in values if isinstance(v, (int, float))]
    if not vals:
        return None
    return {"min": round(min(vals), 6), "max": round(max(vals), 6),
            "median": round(sorted(vals)[len(vals) // 2], 6), "n": len(vals)}


def hall01_cost():
    p = os.path.join(ARCHIVE, "hall01_b4_cost_and_gap.json")
    d = json.load(open(p, encoding="utf-8"))
    out = {"source": os.path.relpath(p, ROOT), "arms": {}}
    for arm, c in d.get("cost", {}).items():
        if not isinstance(c, dict):
            continue
        out["arms"][arm] = {
            "wall_s": c.get("wall_s"), "status": c.get("status", "OK" if c.get("wall_s") else "NO_WALL_TIME"),
            "provenance_error": c.get("provenance_error"),
        }
    for block in ("with_all_400", "without_gap_neighbours"):
        out[block] = d.get(block)
    out["population"] = d.get("population")
    return out


def main():
    complete, decision_only, label_only, inventory = scan_for_decision_records()
    b7 = b7_measurable()
    hall = hall01_cost()

    result = {
        "_meta": {
            "what": "B5/B7 status from archived data only; no host run, no threshold changed",
            "written": "2026-11-10",
            "rule": "a quantity that has no per-candidate record is reported UNAVAILABLE, never "
                    "back-inferred from final results",
        },
        "B5": {
            "status": "BLOCKED",
            "reason": ("the archive holds run- and arm-level outcomes only: no list of candidates "
                       "each carrying a gate decision AND an independent label"),
            "records_with_decision_and_label": len(complete),
            "records_with_decision_but_no_label": len(decision_only),
            "records_with_label_but_no_decision": len(label_only),
            "decision_only_examples": decision_only[:8],
            "confusion_matrix": "NOT COMPUTED (would require exactly the records that are absent)",
            "harmful_rejected": "UNAVAILABLE",
            "beneficial_rejected": "UNAVAILABLE",
            "next_native_run_must_record": list(REQUIRED_FIELDS),
            "note_on_scope": ("these four fields are the whole requirement: candidate identity, the "
                              "gate's decision, its reason, and an independent label. No threshold, "
                              "score or extra telemetry is needed."),
        },
        "B7": {
            "status": "BLOCKED",
            "reason": ("every quantity B7 asks for is a count over decisions partitioned by "
                       "segment; the archive has neither decisions nor segment labels. It also "
                       "has no with-gate / without-gate pair, so the healthy-data cost cannot be "
                       "differenced out of a host run either."),
            "required": {
                "false_intervention_count": "decisions on the normal segment",
                "healthy_geometry_cost": "the same input run with and without the gate",
                "harmful_accept_count": "independent labels on accepted candidates",
                "harmful_reject_count": "independent labels on rejected candidates",
                "missed_repair_count": "a repair outcome per quarantined segment",
                "interruption_count": "a run status per decision",
                "continued_operation_after_safe_reject": "a post-decision liveness record",
            },
            "descriptive_only": b7,
            "hall01": hall,
            "note": ("the numbers below are host-run outcomes under different degradation inputs. "
                     "They are not the gate's cost: subtracting them would require the with/without "
                     "pair that does not exist, and calling run O#2's healthy fraction 'a false "
                     "intervention' would attribute a host failure to the gate."),
        },
        "scan": {
            "files_with_record_lists": len(inventory),
            "inventory": inventory[:40],
        },
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, "b5_b7_results.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=1)
    print(json.dumps({"B5": result["B5"]["status"],
                      "decision_and_label_records": len(complete),
                      "decision_only_records": len(decision_only),
                      "B7": result["B7"]["status"],
                      "files_scanned_with_record_lists": len(inventory),
                      "out": os.path.relpath(out, ROOT)}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
