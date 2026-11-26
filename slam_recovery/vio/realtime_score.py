"""Report tracking quality and wall-clock delivery using actual subscriber receipts."""
import argparse
from collections import Counter
import json
from pathlib import Path

import numpy as np

from .score import score


def rows(path):
    with path.open() as stream:
        return list(map(json.loads, stream))


def elapsed(start, stop):
    return (stop - start) / 1e9


def describe(run, receipt_file):
    trace = rows(run / "events.jsonl")
    input_rows = rows(run / "input_clock.jsonl")
    output = rows(receipt_file)
    emitted = [row for row in trace if row["type"] == "pose"]
    received = [{k: v for k, v in row.items() if k != "received_ns"} for row in output]
    if emitted != received:
        raise ValueError("publisher records differ from external receipts")

    consumed = [row for row in trace if row["type"] == "consume"]
    enqueued = [row for row in input_rows if row["enqueued"]]
    if [(row["timestamp"], row["arrival_ns"]) for row in enqueued] != [
            (row["timestamp"], row["arrival_ns"]) for row in consumed]:
        raise ValueError("consumed physical identities differ from the producer stream")
    first = input_rows[0]["timestamp"]
    poses = {row["timestamp"]: row for row in output}
    if len(poses) != len(output):
        raise ValueError("duplicate delivered physical frame")
    arrival = {row["timestamp"]: row["arrival_ns"] for row in input_rows}
    if any(row["received_ns"] < arrival[row["timestamp"]] for row in output):
        raise ValueError("received pose predates its physical input")
    if any(b["received_ns"] < a["received_ns"] for a, b in zip(output, output[1:])):
        raise ValueError("receipt clock regressed")
    counts = Counter(row["channel"] for row in output)
    lifecycle = [row for row in trace if row["type"] in
                 ("isolate", "checkpoint_replay", "blind_history", "promote", "reject", "rearmed",
                  "complete", "worker_exit")]
    validations = []
    for row in lifecycle:
        if row["type"] == "promote":
            t = row["through"]
            blind = row["accepted_blind_history"]
            suffix = row["accepted_history"]
            for stamps, channel in ((blind, "inertial_history"), (suffix, "repaired_history")):
                for stamp in stamps:
                    pose = poses[stamp]
                    if pose["channel"] != channel or not pose["coordinate_verified"]:
                        raise ValueError("promoted history receipt has the wrong channel")
                    if pose["received_ns"] < arrival[t]:
                        raise ValueError("history was released before visual verification")
            validations.append({"event": row["event"], "verified_historical_blind_frames": len(blind),
                                "verified_historical_visual_frames": len(suffix),
                                "receipts": [poses[stamp] for stamp in blind + suffix]})

    event_stats = []
    for start, end in trace[0]["fault_intervals_s"]:
        begin = first + round(start * 1e9)
        stop = first + round(end * 1e9)
        affected = [row["timestamp"] for row in input_rows if begin <= row["timestamp"] < stop]
        pre = next((row for row in reversed(output) if row["timestamp"] < begin), None)
        after = next((row for row in output if row["timestamp"] >= begin), None)
        live = next((row for row in output if row["timestamp"] >= stop
                     and row["channel"] in ("native", "local_unverified")), None)
        event_stats.append({
            "window_s": [start, end], "input_blind_frames": len(affected),
            "received_blind_frames": sum(t in poses for t in affected),
            "received_blind_history": sum(t in poses and poses[t]["channel"] == "inertial_history"
                                          for t in affected),
            "public_interruption_s": elapsed(pre["received_ns"], after["received_ns"])
            if pre and after else None,
            "to_live_output_s": elapsed(pre["received_ns"], live["received_ns"])
            if pre and live else None,
        })
    lag = [elapsed(row["arrival_ns"], row["consume_ns"]) for row in consumed]
    scheduling = [elapsed(row["scheduled_ns"], row["arrival_ns"]) for row in input_rows]
    return {
        "input_frames": len(input_rows), "input_drop": len(input_rows) - len(enqueued),
        "host_consumed": len(consumed), "subscriber_received": len(output),
        "delivery_channels": counts,
        "unverified_received": sum(not row["coordinate_verified"] for row in output),
        "input_span_s": elapsed(input_rows[0]["arrival_ns"], input_rows[-1]["arrival_ns"]),
        "max_input_gap_s": max(elapsed(a["arrival_ns"], b["arrival_ns"])
                               for a, b in zip(input_rows, input_rows[1:])),
        "input_schedule_p99_s": float(np.percentile(scheduling, 99)),
        "max_consumer_queue_s": max(lag),
        "last_input_to_last_delivery_s": elapsed(input_rows[-1]["arrival_ns"], output[-1]["received_ns"]),
        "largest_public_gap_s": max(elapsed(a["received_ns"], b["received_ns"])
                                    for a, b in zip(output, output[1:])),
        "events": event_stats, "history_validation": validations, "lifecycle": lifecycle,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("dataset", "settings", "native", "native_receipts", "plugin", "plugin_receipts"):
        parser.add_argument(key, type=Path)
    args = parser.parse_args()
    native, plugin = (args.native / "events.jsonl", args.plugin / "events.jsonl")
    positional = score(args.dataset, args.settings, [native, plugin])
    summary = {}
    for label, run, receipt, path in (
            ("native", args.native, args.native_receipts, native),
            ("plugin", args.plugin, args.plugin_receipts, plugin)):
        summary[label] = describe(run, receipt)
        positional[str(path)].pop("lifecycle")
        summary[label]["independent_vicon"] = positional[str(path)]
    print(json.dumps(summary, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
