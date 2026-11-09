# Automatic review and mainline progress

> every auto review needs read and plan to work on main line according to this table

Before every automatic review, read [the mainline progress standard](docs/MAINLINE_PROGRESS_STANDARD_20261109.md), including its two score tables, metric definitions, dependency order, and review handoff template. Also read the applicable current instructions and [the review protocol](REVIEW_AND_SIMULATION_PLAN.md), especially sections 10.10–10.13.

- Compare the actual current commit and evidence with the table. The published 16/36 and 11/36 scores are a **frozen assessment of `7fc67cf`**, not scores automatically inherited by later commits.
- Map findings and the next concrete mainline deliverable to A/B row IDs. State what changed, what remains unverified, the minimum real blocker, and the acceptance evidence needed. Keep supporting engineering work proportionate to that deliverable.
- Preserve the frozen baseline. Record subsequent assessments separately with their exact source revision, evidence, score changes, and remaining gaps. Do not promote scores from commit messages, test counts, or documentation alone.
- Follow current user authorization and stop/pause instructions, including `stop.md`. This read-and-plan requirement does not start or resume automation, authorize experiments or retries, or grant new compute, installation, commit, or push permission. Do not relax frozen scientific thresholds or silently replace P0–P5.
