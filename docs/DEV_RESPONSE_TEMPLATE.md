# Developer response template (per milestone handoff)

Every handoff uses these sections in this order. If a section has nothing in it, say "none" and
why; do not omit it.

## 1. Milestone and commits

- milestone (M0/M1/M2/M3), commit range, branch, and the exact command that reproduces the numbers.
- what is frozen (key sets, reference, thresholds) and where its hash lives.

## 2. Mainline progress

What advanced the paper's main claim, stated as a claim plus the evidence that supports it. If a
claim was narrowed or withdrawn, say so here, before the supporting work.

## 3. Blockers

What prevents the next mainline step. Separate "missing data/measurement" from "missing
implementation" from "decision needed from the owner". A blocker that is only a wording issue is
not a blocker.

## 4. Parallel support work

Work that advanced and is useful but does not by itself move the main claim. Label it explicitly as
supporting; do not let it read as mainline progress.

## 5. Deferred cleanup

Accepted debt with the reason it is deferred and the condition that would bring it back. Examples:
retrospective receipts, archived runs under an older boundary, auxiliary metrics that are not
single criteria.

## 6. Evidence-based reprioritization

What changed in the evidence since the last handoff, and what that changes about the next step. If
nothing changed, say so and keep the plan.

## 7. Statement of what did not advance

One line: whether this handoff contains mainline progress, supporting work only, or both. A
handoff that is supporting-only must say so in the first sentence.
