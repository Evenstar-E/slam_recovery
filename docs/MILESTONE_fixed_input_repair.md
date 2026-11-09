# Milestone: fixed-input measurement repair and native map reconstruction

Status: M1 diagnostic measured (C0-C3 on the ns boundary, `OFFLINE_NATIVE_REESTIMATION` for C3), but the
surface-accuracy claim is withdrawn pending a bounded-geometry evaluation: an unbounded 8-NN plane
residual scores a point 99.9 m from a finite patch as zero. M2 (full-record filtered exporter with
original point ids, native host runner and runtime receipt) and M3 (online checkpoint / deployable
repair) remain open.
This document fixed the protocol before results existed, so the controls and labels were not chosen
after seeing the numbers.

## Scope (frozen)

- Host: FAST-LIVO2.
- Sequence: `hall_01`, window `[100, 160] s`, 4.30 m plastic-bag injection.
- Injection window: absolute `[1627785275.607, 1627785295.546]`, measured by per-frame buffer
  equality against the clean bag (200 differing frames). This is an **INJECTION_ORACLE**; it needs
  the clean recording and is not an online detector.
- Key set (frozen; `docs/milestone_m0_keys.json`, integer nanoseconds):
  - **primary**: all 446 paired quarantine scans, independent of candidate support
    (sha256 `89a8bfa1...d3235a3f`);
  - **diagnostic subset**: the 252 gate-committable scans, reported only as a subset
    (sha256 `2bb7fe3d...00101f5`);
  - **healthy prefix**: the 132 paired pre-onset keyframes, `ts_ns < start_ns`
    (sha256 `74995bb9...62268788`);
  - **outside the cohort**: 20 raw scans with no pose under the pairing rule, listed by ns.
  The encoding is integer `header.stamp.to_nsec()`; a list hash is sha256 of the comma-joined sorted
  ns. An earlier float-rounded boundary (445 / 259 / 133) put the first injected scan into the
  healthy prefix; it is superseded, and the four-arm archive generated with it is marked as such.
  A candidate-dependent set is never the common population for the four controls. Missing poses or
  observations are listed separately, not dropped from the denominator.
- Reference surface: the clean run's map, built only from the clean recording
  (`REAL_HOST_CLEAN_PROXY`). `hall_01` has no ground-truth mesh, so no GT contamination value is
  reported.

## Conditions

| ID | Scan stream | Pose stream | Label |
|---|---|---|---|
| C0 | contaminated (as recorded) | host (FAST-LIVO2 on the injected bag) | REAL_HOST |
| C1 | contaminated | reference (clean-run pose mapped into the injected frame by the pre-onset SE(3)) | OFFLINE_CONSTRUCT |
| C2 | oracle-decontaminated (injector azimuth sector removed **inside the injection window only**) | reference | ORACLE_CEILING |
| C3 | actual filter output (repository near-field filter / mixture repairer) | actual re-estimation | OFFLINE_NATIVE_REESTIMATION at M0/M1; DEPLOYABLE_REPAIR only after a true online host checkpoint run |

C2 is a ceiling, never a deployable result. It removes contaminated points but cannot restore the
occluded background, so it is not a universal optimal-map bound. C3 is the only condition that can
support a claim about what the system can do. If the C3 chain cannot run on the archived data, it is
recorded as `UNAVAILABLE` with the missing input named; it is not replaced by C2 or by a hand-written
rule.

C1 and C2 use clean-run poses and are scored against the clean-run map, so their numbers are an
oracle/proxy consistency control, not independent GT accuracy. C3 must be evaluated against an
independent or held-out reference; if none exists, the proxy limitation is stated and the
connectivity work still proceeds.

### C3 host-input consumption record (M0/M2 deliverable)

The native rerun must record: sha256 of the original, converted and filtered bags; the host binary
and its revision; the configuration actually loaded; the exact command; and the output hash. File
hashes alone identify files, not that the host consumed them. The first rerun from the same healthy
prefix is labelled `OFFLINE_NATIVE_REESTIMATION`; `DEPLOYABLE_REPAIR` requires an online checkpoint
and host map commit run, which is a separate milestone.

### Runtime receipt and runner (M2)

The wrapper that sets the playback rate, drain, recorded topic and `rosrun` invocation is now
committed as `docs/review_20261109_bbc3dcb/fl_run_isolated.sh` (sha256
`aba9b27e...629b588c94`, 1,558 bytes). The C3 record references this file and its hash; the runner
launches with an isolated ROS master (private port, `ROS_HOME` under `/tmp`) and kills only its own
processes. The remaining gap in the receipt is evidence that the host actually consumed the named
filtered bag at run time; file hashes identify files, not consumption.

### State and full point-record contract (M2)

- The filter must preserve ring, time, header stamp and the original point id; a filtered message
  without those cannot be replayed or attributed.
- The host deskew/estimation must produce new full SE3 poses and a map; report translation and RPE
  on the common time support, the output missing rate, false interventions on recovery tail and
  clean windows, and runtime.
- Oracle contamination identity is scored only on points inside the absolute injection window.
  Points from the same azimuth sector outside the window are healthy background and must not count
  as true positives.

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
