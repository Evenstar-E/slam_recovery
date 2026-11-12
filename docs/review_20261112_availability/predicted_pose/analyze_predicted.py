#!/usr/bin/env python3
"""Pose-map decomposition from an availability log with support_under_predicted_pose.

Usage: python analyze_predicted.py <availability_frames.jsonl> <out.json>

Reading rule (state section 90): predicted fraction clearly higher than the host-pose fraction
means the host pose moved away from the frozen trusted map (pose drift); both low means the trusted
reference does not cover the scan; a null prediction means fewer than one trusted pose existed.
"""
import json
import statistics
import sys
from collections import Counter

# The row ranges from the 402-row run the review refers to; this run's paired population is
# different, so the same *stamp windows* are selected instead of the same row indices.
WINDOWS = {
    "prev_53_117": (1627785267272356749, 1627785273678019524),
    "prev_199_401": (1627785286344705820, 1627785306575157404),
}


def fracs(rows, key):
    out = []
    for r in rows:
        s = r.get("support") if key == "support" else r.get("support_under_predicted_pose")
        if s and s.get("supported_fraction") is not None:
            out.append(float(s["supported_fraction"]))
    return out


def passes(rows, key):
    n = 0
    for r in rows:
        s = r.get("support") if key == "support" else r.get("support_under_predicted_pose")
        if s and s.get("pass") is True:
            n += 1
    return n


def q(vals):
    if not vals:
        return None
    if len(vals) < 10:
        return {"median": round(statistics.median(vals), 4)}
    qs = statistics.quantiles(vals, n=10)
    return {"p10": round(qs[0], 4), "median": round(statistics.median(vals), 4),
            "p90": round(qs[-1], 4)}


def main():
    src, out_path = sys.argv[1], sys.argv[2]
    rows = [json.loads(line) for line in open(src, encoding="utf-8")]
    n = len(rows)

    nulls = [i for i, r in enumerate(rows) if not r.get("support_under_predicted_pose")]
    null_runs = []
    if nulls:
        s = p = nulls[0]
        for x in nulls[1:]:
            if x == p + 1:
                p = x
            else:
                null_runs.append([s, p, p - s + 1])
                s = p = x
        null_runs.append([s, p, p - s + 1])

    joint = Counter()
    for r in rows:
        p = r.get("support_under_predicted_pose")
        if not p:
            joint["no_prediction"] += 1
            continue
        h = r["support_pass"] is False
        pl = p.get("pass") is False
        joint["both_low" if h and pl else "only_host_low" if h else
              "only_pred_low" if pl else "both_pass"] += 1

    runs = []
    start = 0
    for i in range(1, n + 1):
        if i == n or rows[i]["status"] != rows[start]["status"]:
            runs.append((rows[start]["status"], start, i - 1))
            start = i

    per_run = []
    for st, a, b in runs:
        if st != "UNAVAILABLE":
            continue
        sel = rows[a:b + 1]
        hf = fracs(sel, "support")
        pf = fracs(sel, "predicted")
        per_run.append({
            "rows": [a, b], "frames": len(sel),
            "host": {"fraction": q(hf), "pass": passes(sel, "support"), "n": len(hf)},
            "predicted": {"fraction": q(pf), "pass": passes(sel, "predicted"), "n": len(pf)},
            "reading": ("null_prediction" if not pf else
                        "host_low_predicted_recovered"
                        if hf and statistics.median(pf) - statistics.median(hf) >= 0.25 else
                        "predicted_lower"
                        if hf and statistics.median(pf) < statistics.median(hf) - 0.10 else
                        "both_low"),
        })

    windows = {}
    for name, (lo, hi) in WINDOWS.items():
        sel = [r for r in rows if lo <= r["pose_stamp_ns"] <= hi]
        windows[name] = {
            "frames": len(sel),
            "host": {"fraction": q(fracs(sel, "support")), "pass": passes(sel, "support")},
            "predicted": {"fraction": q(fracs(sel, "predicted")),
                          "pass": passes(sel, "predicted")},
        }

    summary = {
        "rows": n,
        "predicted_present": n - len(nulls),
        "predicted_null": len(nulls),
        "predicted_null_runs": null_runs,
        "joint": dict(joint),
        "unavailable_runs": per_run,
        "stamp_windows_from_previous_run": windows,
        "window_note": ("the previous run had 402 paired frames and its segment 53-117 was a "
                        "continuous UNAVAILABLE run; this run has a different paired population "
                        "and different map/pose state, so the same stamps are not the same "
                        "status run"),
    }
    json.dump(summary, open(out_path, "w", encoding="utf-8"), indent=1)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
