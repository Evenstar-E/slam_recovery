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

### Point identity (M2) — fixed

The filtered bag now carries `/velodyne_points/kept_index` (`std_msgs/UInt32MultiArray`), written
with the same rosbag timestamp as its scan; because that type has no header, the scan ns is stored
in `layout.dim[0].label` so pairing does not depend on message order. The payload is
`flatnonzero(keep)`, the sidecar records `scan_ns / n_original / n_kept / mask_sha256` plus the
source and output bag hashes, and `point_step` stays 24 with fields and offsets unchanged. Cost is
5.99% of bag size (4 B per original point). Two independent exporters produced the same mask for
the first filtered frame, and all 598 frames join source/cloud/sidecar by `scan_ns` with 0 failures;
the audit decodes the topic (exact msgtype, ns from `layout.dim[0].label`) instead of trusting its
name, and ten positive/negative tests share one validator. Reconstruction is `src_rows = source[mask]`; deleted rows are the
complement, so no value matching is needed.

Schema v2 (2026-11-09) fixes `layout.dim[0].stride` to the element count (`len(idx)`), hashes
the mask as `<u4`, and records `id_schema_version`. The audited bag `c90300cb...` is kept as the
record it is; the point-id-bearing bag is `/tmp/fastlivo/hall01_inj43_filtered_id.bag`
(`700ce116...70bdd`). The C3 numbers in the M1 result
were produced from the earlier bag and are not rerun on this one; that rerun is a separate step.

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

## M3: same-region net correct geometry (protocol, before results)

The question is not whether a repair improves a score, but whether it adds *correct* geometry to the
same region without adding wrong geometry. Two arms, same frozen region and query sample:

- **Q (quarantine only)**: the pre-onset trusted map only; no post-onset frame is written.
- **C3 (real repair)**: the repository filter plus the FAST-LIVO2 rerun, `OFFLINE_NATIVE_REESTIMATION`.

Region and queries: the clean-run proxy restricted to the common support of both arms, with the
same query sample and tolerance used by the bounded metric (NN cap 0.5 m; patch radius 0.30 m,
plane RMS 0.02 m). Key and reference are the frozen M0 sets; the reference is exported before any
metric.

Report absolute counts on both sides, not one ratio:

1. proxy surface points covered by each arm (NN <= 0.5 m), and the coverage fraction;
2. map points that are unsupported by the bounded patch test, and the unsupported fraction;
3. the coverage gained by C3 relative to Q, in proxy points, and the map points it adds that Q
   does not have, split into supported and unsupported;
4. frames written and missing per arm.

No single "net score" is formed from points of different populations. The proxy is the clean run's
map, not a GT surface; the result is a conditional same-region comparison, not a deployment claim.

Measured (`1ae5eaa`), shared base and pose-free ROIs: C3 is base + repaired frames (133,000 points,
532 frames); Q is the base alone. Primary ROI, the whole 8,490,000-point clean reference: Q 91.85%
coverage / 5.68% patch-unsupported, C3 99.20% / 8.41%, and C3 adds 623,880 covered points
(+7.35 pp) that all lie outside the base support, so that gain is trajectory extent, not repair
quality. The 7,797,828-point base-support ROI gives 100.00% for both arms, but that is **tautological**:
the ROI is defined by distance to the shared base, so it cannot say anything about repair quality in
either direction. The `24252d0` review is right to reject that inference.

Measured next by a fixed-frame comparison (`0f31e3b`): the same 400 frames (those with both
filtered scans and rerun poses), ROI = the whole clean reference (pose-free). R (raw scans + host
poses) covers 60.38% with 62.51% patch-unsupported; C3 covers 98.49% with 9.31%. C3 adds 42,227
points of which 85.25% are supported (novel subset 10,581: 69.16%); of the 50,234 points R has and
C3 does not, 95.14% were already unsupported. The pre-stated rule (novel supported > unsupported
AND added-unsupported fraction <= R's) passes: 7,318 > 3,263 and 0.1475 <= 0.6251, verdict
REPAIR_BENEFIT_SUPPORTED. The proxy is not GT, the frame set is 400/446, and C3 is
OFFLINE_NATIVE_REESTIMATION, not a deployable loop. ### Next mainline (pre-registered choice, revised)

Chosen: a short, receipt-backed rate diagnostic on the same frozen input, because
PAIRING_RULE_MISSING is only the proximate reason for the 46 misses. The run records host
publication intervals, node/queue logs and input timing over the two missing segments (about 9.4 s
and 0.2 s) to separate scheduling, input synchronisation and internal tracking. The 75 ms rule is not
changed, and a fresh run must produce a complete receipt (pre-run hashes, output hash, message
coverage, exit status). No new fault intensity and no threshold tuning.

The 400-frame set is conditional on C3 having both filtered scans and poses, the
rule is an analysis rule recorded in the same commit rather than an independently frozen protocol,
and it does not bind lost good geometry, coverage, missing frames or cost. Counts are sampled
geometric disagreement at 0.5 m, not original point-id edits.

### Next mainline (pre-registered choice)

Chosen: frozen-446 service completeness and healthy-region cost on the same chain, using existing
outputs. Pre-registered before running: (a) identify which of the 46 frames lack pose and why;
(b) the real filter's false-removal rate on clean, non-injection intervals; (c) coverage and
patch-unsupported on the frozen 446 with missing frames counted as missing, never dropped. No new
fault intensity, no ROI/阈值 tuning; the same-frame result above is the baseline.

### Pre-stated decision rule (written before applying it)

Population: the common ROI of the base-support set (7,797,828 points), where both arms are
observable, so the comparison is about repair quality rather than trajectory extent.

- ΔC = coverage fraction (C3) − coverage fraction (Q), in proxy points;
- ΔU = patch-unsupported fraction (C3) − patch-unsupported fraction (Q), in map points;
- A net-benefit claim is allowed only if **ΔC ≥ 0.05 and ΔU ≤ 0.05**. Both values are reported
  whether or not the rule passes; no alternative ROI is tried.

Applied to `1ae5eaa`: ΔC = 0.0000 (both 100.00%), ΔU = +0.0273 (8.41% − 5.68%). The coverage clause
fails, so **no net-benefit claim is made**. The primary-ROI ΔC of +0.0735 is not used: those points
lie outside the common region and measure trajectory extent, not repair quality.

## Independent confirmation (next mainline, pre-registered)

Result (38ef313): **the benefit does not repeat**. On a clean reference rebuilt from the raw bag
(599/599 stamps, 400 frames byte-identical, 199 differing over the 19.84 s injection window), the
fixed 326-frame comparison gives R coverage 0.7672 / unsupported 0.4585 and C3 0.6952 / 0.6590; C3
adds 53,027 novel points of which 60 are supported, and removes 15,028 supported points. Both
criterion clauses fail (novel 60 vs 52,967; added-unsupported 0.8333 > R's 0.4585). Service
completeness is 326/398; the 72 misses are all NO_RERUN_POSE under the 75 ms rule. Healthy-region
deletions are 919,702 points (4.47%) over 52 frames, against zero on hall_01.

Consequences: the hall_01 same-frame improvement is single-sequence and does not generalise; the
filter's specificity is sequence-dependent; no cross-sequence or general repair-benefit claim is
made. The hall_01 result stays as a conditional single-sequence observation.

Sequence: `room_02`, 4.30 m injection (`/tmp/fastlivo/room02_inj43.bag`), the prepared window; the
same filter, host config, runner and reconstruction. The injection window is measured by per-frame
buffer equality against the clean `room_02` recording (oracle), not assumed.

Frame set: frames with both a filtered scan and a rerun pose, frozen and exported before metrics.
The criterion is the same one used on `hall_01`, declared before the run: novel added points must
have supported > unsupported, and the added-unsupported fraction must not exceed R's. Report the
added and lost points in total and in the novel subset, service completeness on the declared
denominator, and healthy-region removals. If it fails, report the failure; no tuning of ROI, frame
set or threshold.

## Open, not claimed complete

- A human/independent baseline for the clean proxy (it is a clean-run map, not a GT surface).
- Host-input consumption chain: file hashes identify the bags, not that the host run consumed them;
  a host run record with converted-input hash and config is still missing.
- Boundary continuity remains `BOUND_ONLY` (elapsed-time envelope, not an independent
  relative-motion measurement).
- `LOOP_OUTLIER` real-host test: no unused sequence available.

### Final mechanism split (pre-registered)

A true single-factor 2×2 on the same room_02 input, window, frame set, config, runner and
outside-window policy. Every cell is built from **original row indices/masks** (never `set(row
hash)`, which loses duplicate-value multiplicity), and the construction is exported as a sidecar
with the consumed-input hash:

- **O**: exact clean-background retained (oracle removal).
- **O+F**: O plus the 1,265 injected rows the filter kept (contamination-only).
- **O−B**: O minus the 23,607 background rows the filter dropped (deletion-only).
- **O+F−B**: both changes together, i.e. the actual in-window filter output.

Outside the window all four cells keep the actual filtered rows byte-for-byte; this is the fixed
policy, not a fifth variable. **O+F−B must equal the actual filtered scan inside the window by
original index and by message bytes**; if it does not, the construction is inequivalent and no
factor conclusion may be drawn.

Pre-declared reading rule: each cell is run twice. A cell *fails* if its full-alignment ATE exceeds
1.0 m (actual 315.16 m, oracle 0.0744 m); a cell is *stable* if both repeats land on the same side.
The interaction reading requires **O+F−B to fail in both repeats while O+F and O−B fail in neither**.
If the two single-factor cells fail as well, or if O+F−B is not stable, the outcome is "not a clean
interaction" and is reported as run variance, inequivalent construction or a different actual
condition — never as interaction by default. All four statuses and errors are reported, including
cells that fail. The oracle remains a mechanism diagnostic, not a deployable repair.

**Current status**: the four bags are built from original indices and the equivalence checks pass
on the real data (`b67a804`, hardened through `4f5ed15`): outside-window arms are byte-identical
to the filtered recording, each arm equals the indexed injected rows, and O+F−B is byte-identical
to the actual filtered scan inside the window (599 frames, 0 failures, 9 checks;
`single_factor_bags_verified.json`). The window is asserted against the audit's independent
declaration and its `source`, not against the sidecar's own key set; every stream must reach EOF
together; sidecar indices are gated on dtype, sign, bounds, ordering and missing frames; the
sidecar hash is bound to the audit. The non-scan streams the bags inherit (IMU 8,313, images 884)
are identical between the injected and filtered recordings, and the window contains no duplicate
LiDAR rows, so the ordered-subsequence index is unique rather than one of several witnesses.
The eight host reruns (two per cell) then ran on those bags. **They do not support a factor or an
interaction**: O split 0.072/14.439 m, O+F−B split 554.6/0.301 m, and the two single-factor cells
failed in both repeats (O+F 593.0/14.9 m, O−B 48.8/19.7 m). Map coverage is bimodal in the same
way (0.9988/0.007 unsupported in the good mode, ~0.69/0.65 in the bad mode), and the good mode
appeared once for O and once for the actual cell, independent of the arm. The pre-registered rule
therefore reads `NOT_A_CLEAN_INTERACTION`: the pre-registered interaction pattern is not supported
and the repeats are unstable **under the metric the pre-registration named** — the full-alignment
diagnostic. With two repeats per cell this does not establish the absence of an interaction, nor
that variance statistically dominates every factor. That was a pre-registration error; the
protocol quantity is the frozen-prefix ATE. The first protocol computation also had a frame error
(run→clean prefix alignment compared directly with GT, with no clean→GT transform); after fitting
one frozen clean→GT transform on pre-onset clean keyframes (177 matched, 0.091 m residual) and
composing run→clean→GT, the protocol cells are O 0.093/26.373, O+F 743.3/26.1, O−B 76.1/33.7,
O+F−B 687.5/0.314 m. The metric is not swapped after seeing results: both readings are reported,
both reject interaction, and after the frame fix they agree that the same two runs (O#1 and
O+F−B#2) are good while the other six fail. The earlier "all eight fail the protocol" reading was
an artifact of the missing transform.

**Where the repeats first disagree**: comparing each cell's two pose streams directly (same input,
same world frame), the first recorded pose already differs by 0.159–1.589 m and 0.017–0.122 rad,
14–17 s before onset, and the first output stamps spread over 3.4 s (O pair 3.4 s, O+F/O-B pairs 0.4 s, O+F-B pair 2.0 s). The split is therefore seeded in
initialisation/early tracking, before the injection window; later >1 m differences are its
amplification, not evidence about the in-window rows. A pre-registered variance control then ran each of O and O+F−B four more times on the same bags,
config and runner, varying only the run order. Both cells crossed modes (O: BAD/GOOD/BAD/BAD;
O+F−B: UNCLEAR/UNCLEAR/BAD/BAD), so the pre-registered rule fires
**`SEQUENCE_UNUSABLE_FOR_SINGLE_RUN`**. Pooled with the first two repeats, O is good in ~2/6 and
O+F−B in ~1/6 runs (magnitude only). Two O+F−B runs are intermediate (unsupported 0.114/0.190,
ATE 0.69/1.93 m), so this is a continuum with two ends, not a binary bistability. No single-run A/B
on this sequence can compare factors; the four-cell answer stays **UNKNOWN** until the variance is
controlled.

**Initialisation proxy is negative**: the first-pose delay (first `/aft_mapped_to_init` minus the
first LiDAR scan, read from the 16 existing output bags) does not separate modes — GOOD delays are
1.864/4.196/5.462 s, BAD 1.397–3.130 s, overlapping at 1.86 s, and the delay drifts with the run
batch (1.4–2.3 s for the first eight, 2.1–5.5 s for the last eight). Load/batch and mode are
confounded in this sample, so the proxy neither confirms nor rules out the initialisation-timing
hypothesis; a controlled environment is required.

This diagnostic is `POST_HOC_DESCRIPTIVE` (instability was seen first); its rule is stated here
for prospective use on the next repeat pair: first divergence is the first matched pose with
|Δp| > 1 cm or Δangle > 1e-3 rad, and a pre-onset first divergence names initialisation/early
tracking as the locus. It locates when the repeats diverge, not how often; with two repeats per
cell it is not a probability estimate. The single-run "filter is the cause" observation is withdrawn as not
reproducible. Two independently written
builders and audits (one per side) produce the same in-window counts. Until the host variance is
brought under control, the existing E_actual vs E_oracle comparison changes both
factors at once
(1,265 retained + 23,607 dropped), and its hybrid arm only holds the outside-window policy fixed;
it therefore does **not** yet establish which in-window factor matters. The 315.16 m ATE is a
`FULL_ALIGNMENT_DIAGNOSTIC` (full-trajectory SE(3) fit), separate from the frozen healthy-prefix
protocol, whose ATE for this sequence is `UNAVAILABLE`. The comparison set is the 323-frame
intersection of E_actual's 326 usable frames and E_oracle's 323, of which 317 have a GT match;
326 is E_actual's usable/five-arm common set and is never quoted as the three-arm common set.

### Record corrections (review 0c2e4206)

Details and non-mixing rules: `docs/review_20261109_bbc3dcb/room02_record_corrections.md`.

- The **E_oracle vs E_actual comparison set is 323 frames / 317 GT matches**, not 326.
- **ATE 315.159 m (E_actual) and 0.0744 m (E_oracle) are `FULL_ALIGNMENT_DIAGNOSTIC`**; they are
  not the frozen healthy-prefix protocol number and must not be tabulated with hall_01's.
- **FNR is 0.01394 % (1,265 / 9,073,943)**, not 0.1066 %. The old figure divided surviving
  injected rows by the background count; it is retained under
  `kept_injected_over_background_present`.
- **The mechanism statement is downgraded**: an in-window measurement-selection difference is a
  major factor; the single factor is not isolated until the 2×2 above runs. "1,265 rows are enough
  to pull registration" is not claimed.
