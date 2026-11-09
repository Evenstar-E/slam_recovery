# Developer response — M1/M2/M3 handoff at 18e7994

This handoff contains **both** mainline progress and supporting work: M1 bounded re-evaluation and
M3 same-region measurement are mainline; the runner receipt and point-identity audit are support.

## 1. Milestone and commits

- M1 (bounded re-evaluation) and M3 (same-region net geometry): `52d5b8c`, merged as `18e7994`.
- M2 records: point identity `9732169`; runner `d51dcc79...`.
- Reproduce: `/home/R26534/mm/ros/bin/python -u docs/review_20261109_bbc3dcb/probe_c_good_attribution.py`
  for the attribution, and `python3 docs/review_20261109_bbc3dcb/run_m3_same_region.py` for M3
  (system python with scipy + rosbags).
- Frozen: M0 key sets in `docs/milestone_m0_keys.json` (integer ns; primary 446, diagnostic 252,
  healthy 132, 20 raw outside); region and query indices exported in `m3_region_export.json`.

## 2. Mainline progress

- Bounded patch unsupported falls from 0.6251 (C0, polluted + host pose) to 0.3147 (C1, reference
  pose) to 0.0931 (C3, real filter + native rerun). The oracle ceiling is 0.0593: C3 is 1.57x the
  ceiling, so "reaches the ceiling" is withdrawn; the earlier unbounded plane residual that made it
  look attainable is retired to auxiliary.
- Negative controls: a 0.5 m translation gives 0.743 and a 5 degree yaw 0.755 against a 0.357
  baseline; both JUDGED_BAD.
- M3, same 5,191,379-point region: quarantine-only covers 95.70% with 5.68% patch-unsupported; the
  real repair covers 99.40% with 9.31% unsupported and adds 205,391 covered proxy points (3.96% of
  the region). In previously uncovered area, 71.4% of its added points are supported.
- **Claim narrowed:** the repair buys coverage and a higher contamination rate together. There is
  no clean net benefit; any single score would require a stated weighting.

## 3. Blockers

- No ground-truth surface for `hall_01`; all M1/M3 numbers are against the clean-run proxy.
- No online checkpoint / host map-commit run; C3 is `OFFLINE_NATIVE_REESTIMATION`, not deployable.
- The M3 region leaves only ~4.3 pp of headroom because quarantine already covers 95.7%, so the
  measurement cannot distinguish a large repair benefit even if one exists.

## 4. Parallel support work

- Point identity (M2): `/velodyne_points/kept_index`, scan-ns-keyed join, 598/598 frames, 0
  failures, schema v2; 15/15 tests including negative cases.
- Runner: exit code follows the output, cleanup asserts rc/port/PIDs, pre-run hashes. The archived
  C3 run predates this and stays `RETROSPECTIVE_PARTIAL`.
- Filter accounting by original row-index masks: 0.3981 filter / 0.4197 oracle on the cohort,
  0.8876/0.8855 in-window.

These are support: they make the measurement auditable, but they are not a recovery benefit result.

## 5. Deferred cleanup

- The archived C3 run's runtime receipt is incomplete (no launch-time hashes, no ROS param dump);
  only a fresh run can supply it.
- 46/446 C3 frames lack pose (all listed); the public 400-frame comparison is conditional on them.
- The four-arm archive remains on the float boundary; the M0 ns sets are separate and must not be
  mixed with it.
- The reconstructed maps use a 250-point-per-frame sidecar, not the host-emitted map.

## 6. Evidence-based reprioritization

The M3 trade-off changes the next mainline step: instead of another single-number comparison, the
next step is either (a) an explicit weighting/decision criterion that the paper states in advance,
or (b) an independent reference surface that can separate correct coverage from contamination. More
single-NIS attribution does not advance either.

## 7. Statement

Both mainline and supporting work advanced in this handoff. The mainline claim is narrower than the
previous one: the real chain lands near, but above, the oracle, and its same-region benefit is a
coverage/contamination trade-off rather than a net gain.
