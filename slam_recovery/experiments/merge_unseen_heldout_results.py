#!/usr/bin/env python3
"""Merge all unseen held-out test manifests into a single summary table."""
import json
import os
import sys

MAN_DIR = "/home/R26534/MM-LINS/slam_recovery/experiments/manifests"


def main():
    summary = {
        "unseen_heldout_test_sequences": {},
        "campus_outdoor_sequences": {},
    }

    # 1. hall_02
    hall02_path = os.path.join(MAN_DIR, "test_hall_02_heldout_benchmark.json")
    if os.path.exists(hall02_path):
        with open(hall02_path) as f:
            d = json.load(f)
        summary["unseen_heldout_test_sequences"]["hall_02"] = d

    # 2. street_08
    street08_path = os.path.join(MAN_DIR, "test_street_08_heldout_benchmark.json")
    if os.path.exists(street08_path):
        with open(street08_path) as f:
            d = json.load(f)
        summary["unseen_heldout_test_sequences"]["street_08"] = d

    # 3. room_dark_02
    rd02_path = os.path.join(MAN_DIR, "test_room_dark_02_heldout_benchmark.json")
    if os.path.exists(rd02_path):
        with open(rd02_path) as f:
            d = json.load(f)
        summary["unseen_heldout_test_sequences"]["room_dark_02"] = d

    # 4. Campus sequences
    campus_path = os.path.join(MAN_DIR, "p7_campus_and_overhead_benchmark.json")
    if os.path.exists(campus_path):
        with open(campus_path) as f:
            d = json.load(f)
        summary["campus_outdoor_sequences"] = d

    out_path = os.path.join(MAN_DIR, "unseen_heldout_all_sequences_summary.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print("Saved unseen held-out summary to:", out_path)

    # Print concise table
    print("\n=== Unseen Held-Out Test Sequences Summary ===")
    for seq, data in summary["unseen_heldout_test_sequences"].items():
        print(f"\n[{seq}]")
        if "results" in data:
            for host, res in data["results"].items():
                if isinstance(res, dict) and "ate_rmse_m" in res:
                    print(f"  {host:30s}: ATE={res['ate_rmse_m']:.4f}m (Max={res.get('ate_max_m', 0):.4f}m)")


if __name__ == "__main__":
    main()
