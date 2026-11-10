#!/usr/bin/env python3
"""Derive the admissible kappa range and check the absolute floor, from the 16 recorded rows.

Input is the table in `tau_info_scale_evidence.md` (main @ the B10 preregistration). Nothing here
comes from r11070-c3's geometry recomputation: the point of a separate derivation is that the two
can be compared afterwards instead of one being fitted to the other.

    python -I docs/review_20261110_b10/kappa_derivation.py

Prints JSON: the admissible interval, the margins at both ends, the maximin point, and the
absolute-floor arithmetic under the two readings of `sigma_tol`.
"""

from __future__ import annotations

import json

# (run, sigma, source, info_before, info_after) -- transcribed from the evidence table.
ROWS = [
    ("025831Z", 0.12, "host_poses", 39.05, 0.00),
    ("030300Z", 0.12, "host_poses", 39.05, 0.00),
    ("030656Z", 0.12, "host_poses", 40.23, 34.47),
    ("030931Z", 0.12, "host_poses", 40.23, 34.47),
    ("031851Z", 0.12, "host_poses", 40.23, 34.47),
    ("032515Z", 0.12, "host_poses", 40.23, 34.47),
    ("035239Z", 0.884, "host_poses", 1.1019, 4.6458),
    ("035544Z", 0.884, "host_poses", 1.1019, 4.6199),
    ("035825Z", 0.884, "host_poses", 1.1019, 4.6281),
    ("042426Z", 0.884, "host_poses", 1.1019, 4.6342),
    ("043148Z", 0.884, "host_poses", 1.1019, 4.6472),
    ("044250Z", 0.884, "host_poses", 1.1019, 4.6990),
    ("044830Z", 0.884, "host_poses", 1.1019, 4.6612),
    ("050737Z", 0.884, "icp_reregistration", 1.1019, 0.9746),
    ("051542Z", 0.884, "icp_reregistration", 1.1019, 4.0293),
    ("051744Z", 0.884, "icp_reregistration", 1.1019, 4.4701),
]

# Which side of the decision each row is declared to be on. This is a declaration, not a fitted
# label: the onset-window candidates are the ones the repair was built for.
BENEFICIAL = {"035239Z", "035544Z", "035825Z", "042426Z", "043148Z", "044250Z", "044830Z",
              "051542Z", "051744Z"}
HARMFUL = {"025831Z", "030300Z", "030656Z", "030931Z", "031851Z", "032515Z", "050737Z"}

SIGMA_TOL = 0.5          # GateThresholds.sigma_tol, compared against ||P_after||_2 in core.py


def ratios():
    out = []
    for run, sigma, source, before, after in ROWS:
        out.append({"run": run, "sigma": sigma, "source": source,
                    "before": before, "after": after,
                    "ratio": round(after / before, 6) if before else None,
                    "gain": round(after - before, 6)})
    return out


def main():
    rows = ratios()
    ben = [r["ratio"] for r in rows if r["run"] in BENEFICIAL]
    harm = [r["ratio"] for r in rows if r["run"] in HARMFUL]
    lo_harm, hi_ben = max(harm), min(ben)

    kappa_upper = hi_ben                 # above this, a beneficial candidate is refused
    kappa_lower_raw = lo_harm            # without `gain > 0` this is the floor
    kappa_lower_effective = 1.0          # with `gain > 0`, kappa <= 1 is vacuous

    out = {
        "_meta": {
            "what": "kappa range and absolute floor from the 16 recorded decisions",
            "source": "docs/review_20261110_b10/tau_info_scale_evidence.md (16 rows)",
            "independence": ("derived only from the archived rows; not compared against the offline "
                             "geometry recomputation, so the two can be checked against each other"),
            "not_done": ["no threshold changed", "no code changed", "no gate value picked"],
        },
        "rows": rows,
        "beneficial_ratios": sorted(ben),
        "harmful_ratios": sorted(harm),
        "interval": {
            "without_gain_condition": [kappa_lower_raw, kappa_upper],
            "with_gain_condition": [kappa_lower_effective, kappa_upper],
            "open_lower": True, "closed_upper": True,
            "separation_factor": round(hi_ben / lo_harm, 6) if lo_harm else None,
        },
        "margins": {
            "upper_is_zero": True,
            "upper_set_by": [r["run"] for r in rows if r["run"] in BENEFICIAL
                             and r["ratio"] == hi_ben],
            "interpretation": ("the upper bound is the weakest beneficial row itself, so any "
                               "kappa above it refuses a candidate this population calls "
                               "beneficial: there is no margin at that end, the bound is a single "
                               "observation"),
            "lower_effective_bound": ("with `gain > 0` every harmful row fails already (their "
                                      "ratios are below 1), so the lower bound does not bind; "
                                      "kappa <= 1 is the same criterion as kappa = 1"),
            "log_maximin_without_gain": round((lo_harm * kappa_upper) ** 0.5, 6),
            "log_maximin_with_gain": round((kappa_lower_effective * kappa_upper) ** 0.5, 6),
            "maximin_is_a_convention": ("equal relative distance to both bounds; it is a convention "
                                        "for choosing inside the interval, not a measurement"),
        },
        "effective_gain_threshold": {
            "note": ("after >= kappa*before with gain > 0 is the same as after/before > max(1, "
                     "kappa); kappa <= 1 makes the ratio test redundant"),
        },
        "absolute_floor": {
            "why": ("a pure ratio passes when both sides are tiny: before=0.01, after=0.05 is "
                    "ratio 5 but 0.05 of information, which no downstream leg can use"),
            "form": "after >= tau_abs_min",
            "derived_from": "GateThresholds.sigma_tol, through the Mode-2 covariance leg",
            "reading_variance": {
                "formula": "tau_abs_min = 1 / sigma_tol",
                "value": round(1.0 / SIGMA_TOL, 6),
                "reasoning": ("core.py compares ||P_after||_2 (a covariance eigenvalue, i.e. a "
                              "variance) against sigma_tol; a variance 1/lambda along the weak "
                              "direction must not exceed that bound, so lambda >= 1/sigma_tol"),
                "margin_against_this_population": {
                    "min_beneficial_after": round(min(r["after"] for r in rows
                                                      if r["run"] in BENEFICIAL), 6),
                    "factor": round(min(r["after"] for r in rows if r["run"] in BENEFICIAL)
                                    / (1.0 / SIGMA_TOL), 6),
                },
            },
            "reading_std": {
                "formula": "tau_abs_min = 1 / sigma_tol**2",
                "value": round(1.0 / SIGMA_TOL ** 2, 6),
                "reasoning": ("if sigma_tol were meant as a standard deviation rather than a "
                              "variance, the bound on 1/lambda is sigma_tol**2 and the floor "
                              "doubles"),
                "margin_against_this_population": {
                    "min_beneficial_after": round(min(r["after"] for r in rows
                                                      if r["run"] in BENEFICIAL), 6),
                    "factor": round(min(r["after"] for r in rows if r["run"] in BENEFICIAL)
                                    / (1.0 / SIGMA_TOL ** 2), 6),
                },
            },
            "must_be_settled_first": ("which reading the code implements decides whether the floor "
                                      "is 2.0 or 4.0; the weakest beneficial row (4.0293) sits "
                                      "0.7% above the second and 101% above the first"),
        },
        "population_warning": {
            "distinct_ratios": sorted({round(r["ratio"], 6) for r in rows}),
            "n_rows": len(rows),
            "note": ("the 16 rows are repeats of a few configurations: several rows share identical "
                     "values to three decimals. The interval is 'the range consistent with these "
                     "rows', not a confidence interval, and it cannot be validated on the same "
                     "data it was derived from"),
        },
    }
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
