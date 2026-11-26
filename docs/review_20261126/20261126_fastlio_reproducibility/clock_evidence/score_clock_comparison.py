"""Score identical physical scan slots; count preview separately from released host output."""
import json
from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "fastlio_full_cycle_matrix_20261126"))
from score_matrix import base, gt_for


def load(folder, name, expected):
    base.ROOT = folder
    check_prefix = base.check_prefix
    base.check_prefix = lambda rows, seeds: check_prefix(
        [{key: row[key] for key in seeds[0]} for row in rows], seeds,
    )
    bind = base.frame_bind

    def frame_bind(telemetry, relay):
        receipt = base.read(folder / name / "receipt.json")
        corrections = {
            e["scan_ns"]: e["corrected_ns"]
            for e in receipt["events"] if e["action"] == "preview_retime"
        }
        return bind(telemetry, [
            dict(row, fed_ns=corrections.get(row["fed_ns"], row["fed_ns"])) for row in relay
        ])

    base.frame_bind = frame_bind
    try:
        return base.load_arm(name, expected)
    finally:
        base.check_prefix = check_prefix
        base.frame_bind = bind


def main():
    spec = base.read(ROOT / "FIXTURES.json")["sync"]["input"]
    expected = spec["inputs"]
    window, = spec["windows"]
    start, end = window["onset_ns"], window["end_ns"]
    faulty_keys = {row["fed_ns"] for row in expected if row["event"] is not None}
    arms = {
        "native": load(ROOT, "native", expected),
        "frozen": load(ROOT.parent / "fastlio_closed_loop_acceptance_20261126", "sync", expected),
        "preview": load(ROOT, "preview", expected),
    }
    assert any(e["action"] == "preview_started" for e in arms["preview"]["receipt"]["events"])
    shared = set.intersection(*(set(data["poses"]) for data in arms.values()))
    triplet_public = set.intersection(*(set(data["public"]) for data in arms.values()))
    gt = gt_for(spec["site"])
    native = arms["native"]
    reference = {
        key: point for key in shared
        if (point := base.interp(*gt, native["poses"][key][1])) is not None
    }
    anchor = max((key for key in triplet_public & reference.keys() if key < start), default=None)
    score_end = end + 3 * base.NS
    metric_keys = sorted(key for key in reference if start <= key < score_end)
    after = min((key for key in triplet_public & reference.keys() if end <= key < score_end), default=None)
    results = {}
    for arm, data in arms.items():
        eligible = sorted(key for key in data["public"] if start <= key < score_end)
        prior = max((key for key in data["public"] if key < start), default=start)
        gaps = np.diff([prior, *eligible, score_end]) / base.NS
        first_after = next((key for key in eligible if key >= end), None)
        emitted = [data["public"][key]["wall_ns"] for key in [prior, *eligible]
                   if key in data["public"]]
        events = data["receipt"]["events"]
        corrected = [e["scan_ns"] for e in events if e["action"] == "preview_retime"]
        results[arm] = {
            "exit": data["receipt"]["code"],
            "fault_window_public": sum(start <= key < end for key in eligible),
            "complete_input": data["complete_input"],
            "window_public": len(eligible),
            "maximum_public_gap_s": float(max(gaps)),
            "maximum_observed_wall_output_gap_s": (
                float(max(np.diff(emitted))) / base.NS if len(emitted) >= 2 else None),
            "first_post_fault_public_delay_s": (
                (first_after - end) / base.NS if first_after is not None else None),
            "own_first_post_fault_displacement_error_m": base.first_public_displacement(
                data, first_after, anchor, gt, reference),
            "common_window_displacement_rmse": base.displacement_error(
                data, metric_keys, anchor, reference),
            "common_first_post_fault_displacement_error": base.displacement_error(
                data, [after] if after is not None else [], anchor, reference),
            "unbound_public": len(data["unbound"]),
            "retimed": len(corrected),
            "preview_retime_exact_fault_window": (
                set(corrected) == faulty_keys and len(corrected) == len(faulty_keys)
                if arm == "preview" else None),
            "native_refusal_retimed": sum(
                row.get("retimed", False) for row in data["receipt"]["refusal_receipts"]),
            "preview_stops": [e for e in events if e["action"] == "preview_stopped"],
            "native_resets": [r for r in data["health"]
                              if r["kind"] in ("native_re_slam", "native_imu_reset")],
            "authoritative_map": "disposable native map" if arm == "preview" else "run's native map",
            "host_final_status": (data["receipt"]["final"] or {}).get("tail"),
            "native_maps": data["receipt"]["maps"],
        }
    print(json.dumps({
        "fault_scans": sum(row["event"] is not None for row in expected),
        "window_scans": sum(start <= row["stamp_ns"] < score_end for row in expected),
        "common_scored_estimates": len(metric_keys),
        "first_common_after_end_s": (after - end) / base.NS if after is not None else None,
        "arms": results,
    }, allow_nan=False, indent=2))


if __name__ == "__main__":
    main()
