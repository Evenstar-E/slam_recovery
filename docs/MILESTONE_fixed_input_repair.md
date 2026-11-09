# Milestone: fixed-input measurement repair and native map reconstruction

Status: in progress. This document fixes the protocol before results arrive; it exists so the
controls, labels and provenance do not get chosen after seeing the numbers.

## Scope (frozen)

- Host: FAST-LIVO2.
- Sequence: `hall_01`, window `[100, 160] s`, 4.30 m plastic-bag injection.
- Injection window: absolute `[1627785275.607, 1627785295.546]`, measured by per-frame buffer
  equality against the clean bag (200 differing frames). This is an **INJECTION_ORACLE**; it needs
  the clean recording and is not an online detector.
- Key set: frozen before evaluation. Two acceptable sets, both reported explicitly:
  the gate's committable set (259 keys at the time of writing) or all quarantine keyframes (445).
  The key list and the reference hash are exported with the results.
- Reference surface: the clean run's map, built only from the clean recording
  (`REAL_HOST_CLEAN_PROXY`). `hall_01` has no ground-truth mesh, so no GT contamination value is
  reported.

## Conditions

| ID | Scan stream | Pose stream | Label |
|---|---|---|---|
| C0 | contaminated (as recorded) | host (FAST-LIVO2 on the injected bag) | REAL_HOST |
| C1 | contaminated | reference (clean-run pose mapped into the injected frame by the pre-onset SE(3)) | OFFLINE_CONSTRUCT |
| C2 | oracle-decontaminated (injector azimuth sector removed **inside the injection window only**) | reference | ORACLE_CEILING |
| C3 | actual filter output (repository near-field filter / mixture repairer) | actual re-estimation | DEPLOYABLE_REPAIR |

C2 is a ceiling, never a deployable result. C3 is the only condition that can support a claim about
what the system can do. If the C3 chain cannot run on the archived data, it is recorded as
`UNAVAILABLE` with the missing input named; it is not replaced by C2 or by a hand-written rule.

## Measurements (same keys and region for every condition)

1. Point-to-clean-proxy distance distribution: tail >0.25 / 0.5 / 1.0 m and coverage @0.5 m, with
   the surface definition stated (5 cm voxel surface is the primary; the 120k stride surface is
   legacy and not comparable).
2. Map connectivity: number of connected components of the committed voxel set, largest-component
   fraction, and trajectory gaps on the common support.
3. Admitted keyframe count and explicit missing-frame ids; no silent denominator shrinkage.
4. Filter accounting for C3: points removed, how many lie in the injector's azimuth sector (oracle
   only for scoring), and false removals on clean intervals.

## Reporting rules

- Accuracy and coverage are reported together; neither is a quality score alone.
- Oracle ceilings and deployable repairs are never pooled in one number.
- The reference and key list are frozen and exported before the candidate is evaluated. If a
  candidate is admitted, the reference snapshot must be taken before the commit mutates it.
- Provenance: input bag sha256, source commit, and the branch that produced each number. The
  four-arm replay's 5 cm voxel rerun lives on `exp/four-arm` at `762b533`; main keeps its 120k
  fields and a `voxel_surface_check` block.
- No iterative single-NIS attribution. The NIS on this reference construction is not comparable
  with `tau = 2.5`; the milestone is about map accuracy, completeness and connectivity under the
  four conditions.

## Open, not claimed complete

- A human/independent baseline for the clean proxy (it is a clean-run map, not a GT surface).
- Host-input consumption chain: file hashes identify the bags, not that the host run consumed them;
  a host run record with converted-input hash and config is still missing.
- Boundary continuity remains `BOUND_ONLY` (elapsed-time envelope, not an independent
  relative-motion measurement).
- `LOOP_OUTLIER` real-host test: no unused sequence available.
