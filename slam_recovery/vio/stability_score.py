"""Score all physical frames, including missing and unverified outputs."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import numpy as np

from .realtime_score import describe, elapsed, rows
from .score import align, interpolate, reference, rms
from .vision import HeldOutStereo, rotation


def sha(path):
    with path.open("rb") as stream:
        digest = hashlib.sha256()
        for part in iter(lambda: stream.read(1 << 20), b""):
            digest.update(part)
    return digest.hexdigest()


def evaluate(folder, meta, ground_truth, body_offset):
    label = meta.stem
    run = folder / label
    status = json.loads(meta.read_text())
    evidence = {"run_metadata": status}
    if status["controller_exit"] or status["subscriber_exit"]:
        return evidence, {}
    receipts = folder / f"{label}.subscriber.jsonl"
    delivery = rows(receipts)
    try:
        public = describe(run, receipts)
    except (ValueError, KeyError, IndexError) as failure:
        return dict(evidence, evidence_error=str(failure)), {}
    input_rows = rows(run / "input_clock.jsonl")
    trace = rows(run / "events.jsonl")
    keys = [(row["timestamp"], row["image_sha256"], row["imu_count"]) for row in input_rows]
    digest = hashlib.sha256(json.dumps(keys).encode()).hexdigest()
    origin = input_rows[0]["timestamp"]
    first_fault = min((w[0] for w in trace[0]["fault_intervals_s"]), default=25)
    arrivals = {row["timestamp"]: row["arrival_ns"] for row in input_rows}
    truth = {}
    for stamp in arrivals:
        if elapsed(origin, stamp) >= 8:
            position = interpolate(*ground_truth, stamp)
            if position is not None:
                truth[stamp] = position

    measurement = {}
    for row in delivery:
        stamp = row["timestamp"]
        if row["coordinate_verified"] and stamp in truth:
            pose = np.asarray(row["pose_cw"])
            measurement[stamp] = rotation(pose[3:]).T @ (body_offset - pose[:3])
    anchor = [(value, truth[t]) for t, value in measurement.items()
              if elapsed(origin, t) <= first_fault - 0.25]
    errors = {}
    if len(anchor) >= 20:
        R, offset = align(*zip(*anchor))
        errors = {t: float(np.linalg.norm(R @ position + offset - truth[t]))
                  for t, position in measurement.items()}
    delays = {r["timestamp"]: elapsed(arrivals[r["timestamp"]], r["received_ns"])
              for r in delivery if r["timestamp"] in truth}
    useful = {stamp for stamp, error in errors.items() if error <= 0.5 and delays[stamp] <= 1}
    event_populations = []
    for start, end in trace[0]["fault_intervals_s"]:
        window = {stamp for stamp in truth if start <= elapsed(origin, stamp) < end + 3}
        event_populations.append({"fault_span_s": [start, end], "physical_frames": len(window),
                                  "verified": len(window & measurement.keys()),
                                  "timely_usable": len(window & useful)})
    usable = len(useful)
    stat = {
        "ordered_input_sha256": digest,
        "controller_and_subscriber_zero": True, "input_frames": public["input_frames"],
        "input_drop": public["input_drop"], "input_clock_span_s": public["input_span_s"],
        "max_input_gap_s": public["max_input_gap_s"],
        "end_to_end_span_s": public["input_span_s"] + public["last_input_to_last_delivery_s"],
        "delivered": public["subscriber_received"], "channels": public["delivery_channels"],
        "scoreable_frames": len(truth), "anchor_pairs": len(anchor),
        "timely_outputs": sum(value <= 1 for value in delays.values()),
        "verified_outputs": len(measurement), "position_within_limit": sum(e <= 0.5 for e in errors.values()),
        "timely_usable": usable,
        "timely_usable_fraction": usable / len(truth) if truth else None,
        "receipt_latency_p95_s": float(np.percentile(list(delays.values()), 95)) if delays else None,
        "arm_position_rmse_m": rms(errors.values()),
        "longest_wall_gap_s": public["largest_public_gap_s"], "per_event": public["events"],
        "history_delivered": public["history_validation"],
        "lifecycle": public["lifecycle"], "event_populations": event_populations,
        "source_file_sha256": {
            str(path.relative_to(folder)): sha(path) for path in
            (run / "events.jsonl", run / "input_clock.jsonl", receipts, meta)
        },
        "controller_counts": dict(Counter(r["type"] for r in trace)),
    }
    stat["worker_failures"] = sum(r["exit"] != 0 for r in public["lifecycle"] if r["type"] == "worker_exit")
    return dict(evidence, **stat), errors


def compare(first, second, first_error, second_error):
    if ("timely_usable" not in first or "timely_usable" not in second
            or not first["anchor_pairs"] >= 20 or not second["anchor_pairs"] >= 20
            or first["receipt_latency_p95_s"] is None or second["receipt_latency_p95_s"] is None):
        return {"status": "unassessable"}
    if first["ordered_input_sha256"] != second["ordered_input_sha256"]:
        return {"status": "input_mismatch"}
    common = sorted(first_error.keys() & second_error.keys())
    coverage = second["timely_usable_fraction"] - first["timely_usable_fraction"]
    latency = second["receipt_latency_p95_s"] - first["receipt_latency_p95_s"]
    usable = second["timely_usable"] - first["timely_usable"]
    condition = first["run_metadata"]["condition"]
    long_rejected = any(r["type"] == "reject" and r["event"] == 2
                        for r in second["lifecycle"])
    if condition == "clean":
        accepted = (coverage >= -0.01 and latency <= 0.25
                    and second["controller_counts"].get("isolate", 0) == 0)
    else:
        accepted = usable >= 5 and latency <= 0.25 and (condition != "short_long" or long_rejected)
    if (first["input_drop"] or second["input_drop"] or first["worker_failures"]
            or second["worker_failures"] or first["input_frames"] != 950
            or second["input_frames"] != 950):
        accepted = False
    return {
        "status": "pass" if accepted else "fail", "timely_usable_delta": usable,
        "timely_usable_delta_pp": 100 * coverage, "p95_delay_delta_s": latency,
        "common_frames": len(common), "primary_rmse_m": rms(first_error[t] for t in common),
        "candidate_rmse_m": rms(second_error[t] for t in common),
        "long_rejected": long_rejected if condition == "short_long" else None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("evidence", "dataset_root", "settings"):
        parser.add_argument(key, type=Path)
    parser.add_argument("--sequences", nargs="+")
    args = parser.parse_args()
    arms, errors, pairs, ground_truths = {}, {}, {}, {}
    body_offset = HeldOutStereo(args.settings).camera_to_body
    for path in sorted(args.evidence.glob("*-r[0-9]-*.json")):
        meta = json.loads(path.read_text())
        name = meta["sequence"]
        if args.sequences and name not in args.sequences:
            continue
        if name not in ground_truths:
            ground_truths[name] = reference(args.dataset_root / name)
        arms[path.stem], errors[path.stem] = evaluate(
            args.evidence, path, ground_truths[name], body_offset)
    for label, candidate in arms.items():
        group, arm = label.rsplit("-", maxsplit=1)
        if arm == "native":
            continue
        for opponent in ("native", "sync") if arm == "improved" else ("native",):
            baseline = f"{group}-{opponent}"
            if baseline in arms:
                pairs[f"{label}_vs_{opponent}"] = compare(
                    arms[baseline], candidate, errors[baseline], errors[label])
    print(json.dumps({"arms": arms, "paired_results": pairs}, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
