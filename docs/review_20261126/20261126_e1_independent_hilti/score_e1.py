"""Score gauge restoration and historical delivery from independently checked receipts."""
import json
from pathlib import Path
import sys


NS = 1_000_000_000


def score(run):
    fault = run["fault"]
    population = {row["scan_ns"]: row for row in run["input"]}
    if len(population) != len(run["input"]):
        raise ValueError("duplicate physical scan IDs")
    lo, hi = fault["start_ns"], fault["end_ns"]
    fault_slots = {key for key in population if lo <= key < hi}
    order = {key: index for index, key in enumerate(sorted(population))}
    public = sorted((r for r in run["public"] if r["scan_ns"] in population),
                    key=lambda r: r["published_ns"])
    end_receipt = min((r["arrival_ns"] for key, r in population.items() if key >= hi),
                      default=None)
    old_gauge = run["original_gauge"]
    confirmed = None
    consecutive = []
    after = [r for r in public if r["scan_ns"] >= hi]
    for row in after:
        if row["gauge"] != old_gauge or not row["verified_against_frozen_reference"]:
            consecutive.clear()
            continue
        if consecutive and order[row["scan_ns"]] != order[consecutive[-1]["scan_ns"]] + 1:
            consecutive.clear()
        consecutive.append(row)
        if len(consecutive) >= run["sustained_frames"]:
            confirmed = consecutive[0]
            break
    delivered = set()
    for row in run["historical"]:
        slot = row["scan_ns"]
        if (slot in fault_slots and row["reestimated"] and row["verified"] and
                row["gauge"] == old_gauge and row.get("downstream_receipt") and
                row["downstream_received_ns"] >= row["validated_ns"] >= population[slot]["arrival_ns"]):
            delivered.add(slot)
    marks = [r["published_ns"] for r in public if r["scan_ns"] >= lo]
    before = [r["published_ns"] for r in public if r["scan_ns"] < lo]
    if before:
        marks.insert(0, before[-1])
    marks.append(run["observation_cutoff_ns"])
    marks.sort()
    longest = max((right-left for left, right in zip(marks, marks[1:])), default=None)
    merge = run.get("upstream_merge_receipt") or {}
    return dict(
        fault_slots=len(fault_slots), public=len(public),
        original_gauge_return_s=(
            (confirmed["published_ns"] - end_receipt) / NS if confirmed and end_receipt else None),
        original_gauge_return_m=(
            population[confirmed["scan_ns"]].get("distance_from_fault_end_m") if confirmed else None),
        longest_public_gap_s=longest / NS if longest is not None else None,
        verified_historical_delivered=len(delivered),
        first_new_gauge_s=next(((r["published_ns"] - end_receipt) / NS
                                for r in after if end_receipt and r["gauge"] != old_gauge), None),
        merge_verified=bool(merge.get("optimization_accepted")
                            and merge.get("active_submap_gauge") not in (None, old_gauge)
                            and merge.get("published_gauge") == old_gauge
                            and merge.get("backend_receipt_id")))


if __name__ == "__main__":
    print(json.dumps(score(json.loads(Path(sys.argv[1]).read_text())), indent=2, allow_nan=False))
