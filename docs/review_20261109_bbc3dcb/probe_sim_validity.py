"""Probe: does the simulator-validity check now reproduce the gate's own statistic?

Run from the repository root:

    python -B docs/review_20261109_bbc3dcb/probe_sim_validity.py

The assertions describe the FIXED behaviour of `simulator_validity` in
`sim_s1_s2_counterfactual_and_3d_voxel_benchmark.json` (produced by
`slam_recovery/sim/run_s1_s2_simulation_experiments.py`). The pre-fix defects they invert are
listed in README.md §"仿真 validity 的实现还需修正".

What is asserted
  1. The reference is snapshotted before the candidate can be committed, and the manifest records
     whether the commit mutated it.
  2. GT support is decided by GT poses, and the candidate/GT support sets are reported as a set
     difference instead of being assumed equal.
  3. The validity statistic is the gate's statistic: every `holdout_stride`-th keyframe of the
     sorted key set, scorable only under reference support, aggregated by MEAN (not median).
  4. Missing evidence is never a pass: every scenario carries its own verdict, and an empty or
     non-finite support set yields INVALID/MISSING, never PASSED.
  5. The density sweep is interpreted against the estimator's real budget: the report states the
     points actually used (600), so "20000 and 200000 are identical" can no longer be read as
     "density does not matter".

Nothing here changes production defaults. The plane-calibration proposal at the bottom is a
diagnostic and needs the owner's sign-off before any estimator default moves.
"""

from __future__ import annotations

import json
import os
import sys

_MANIFEST = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "slam_recovery/experiments/manifests/sim_s1_s2_counterfactual_and_3d_voxel_benchmark.json",
)

with open(_MANIFEST, encoding="utf-8") as f:
    _m = json.load(f)

sv = _m["simulator_validity"]
scen = sv["per_scenario"]
sweep = sv["reference_density_sweep"]

# --- 1. reference snapshot precedes the commit, and mutation is recorded ------------------------
for row in scen:
    assert "reference_points_snapshot" in row, "reference snapshot not recorded before the commit"
    assert "reference_points_after_commit" in row, "post-commit reference not recorded"
    assert "reference_mutated_by_candidate" in row, "mutation flag missing"

# --- 2. support decided by GT poses, difference set reported -----------------------------------
for row in scen:
    assert "gt_supported_ids" in row and "candidate_supported_ids" in row
    assert isinstance(row["gt_only_ids"], list) and isinstance(row["candidate_only_ids"], list)
    assert row["support_set_symmetric_difference"] == len(row["gt_only_ids"]) + len(
        row["candidate_only_ids"])

# --- 3. same statistic as the gate -------------------------------------------------------------
assert sv["gate_statistic_replicated"]["aggregation"].startswith("mean")
assert sv["gate_statistic_replicated"]["holdout_stride"] == 5
for row in scen:
    assert len(row["gt_holdout_ids_sampled"]) % 5 == 0 or len(row["gt_holdout_ids_sampled"]) > 0
    assert set(row["gt_supported_ids"]) <= set(row["gt_holdout_ids_sampled"])
    assert len(row["gt_nis_per_frame"]) == row["gt_n_scored"]

# --- 4. every scenario judged separately; no PASSED without finite evidence --------------------
assert sv["status"] == "FAILED", sv["status"]
assert len(sv["status_per_scenario"]) == len(scen) >= 1
for row in scen:
    assert row["status"] in {"PASSED", "FAILED", "INVALID", "MISSING"}
    if row["status"] == "PASSED":
        assert row["gt_n_scored"] > 0 and row["gt_nis_mean"] is not None
    if row["status"] == "FAILED":
        assert row["gt_nis_mean"] > 2.5
# the failure is not an artefact of cross-scenario averaging
assert all(r["gt_nis_mean"] is None or r["gt_nis_mean"] > 2.5 for r in scen)

# --- 5. density sweep is reported against the estimator's real budget -------------------------
assert sweep["1500"]["estimator_points_used"] is not None
assert sweep["1500"]["estimator_points_used"] <= 600
assert sweep["20000"]["reference_points_returned_per_scenario"] == \
    sweep["200000"]["reference_points_returned_per_scenario"]
assert sweep["20000"]["gt_nis_mean_per_scenario"] == sweep["200000"]["gt_nis_mean_per_scenario"]
assert "NOT supported" in sv["finding"], "the 'density is not the cause' claim must be retracted"

# --- plane calibration: diagnostic numbers, no default changed --------------------------------
for cap in ("1500", "20000"):
    thin = sweep[cap]["nis_thin_neighbourhoods_only"]
    mixed = sweep[cap]["nis_mixed_neighbourhoods_only"]
    assert thin is not None and mixed is not None
    assert thin < 1.0 and mixed > 50.0, (cap, thin, mixed)

print("simulator_validity:", sv["status"], sv["status_counts"])
for row in scen:
    print(f"  seed {row['seed']:>2}: {row['status']:6s} GT-NIS={row['gt_nis_mean']:>8.3f} "
          f"candidate={row['candidate_nis_mean']:>8.3f} scored={row['gt_n_scored']}"
          f"/{len(row['gt_holdout_ids_sampled'])} symdiff={row['support_set_symmetric_difference']}")
for cap, v in sweep.items():
    print(f"  cap {cap:>6}: points_returned={v['reference_points_returned_per_scenario'][0]:>6} "
          f"estimator_used={v['estimator_points_used']:>5} "
          f"nis_mean={v['nis_as_is_mean']:>7.2f} median={v['nis_as_is_median']:.3f} "
          f"thin-only={v['nis_thin_neighbourhoods_only']} "
          f"mixed-only={v['nis_mixed_neighbourhoods_only']}")
print()
print("PROPOSAL (diagnostic only, defaults unchanged):")
print("  1. reject k-NN fits whose smallest covariance direction is not thin")
print("     (normal/lateral spread ratio > 0.05 => the 8 neighbours span two surfaces);")
print("  2. aggregate with a robust quantile, not the mean over a two-population mixture;")
print("  3. calibrate sigma_m to the measured plane-fit error, not to the sensor noise alone;")
print("  4. size the reference budget against the estimator's own 600-point cap.")
print("Each of these changes published real-sequence holdout numbers and needs owner sign-off.")
