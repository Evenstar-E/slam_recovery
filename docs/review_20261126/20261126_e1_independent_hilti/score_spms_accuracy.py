"""Relative prism displacement on the same public scan slots of the holdout."""
import json
from pathlib import Path
import sys

from score_stream import ROOT, NS, base


TRUTH = Path("/home/tong/e1_hilti_stream_20261126/spms_02/ground_truth.csv")


def main():
    pins = base.read_gt(TRUTH)
    native = base.read(ROOT / "spms_fault_native" / "trajectory.json")
    plugin = base.read(ROOT / "spms_fault_plugin" / "trajectory.json")
    receipt = base.read(ROOT / "spms_fault_native" / "receipt.json")
    tracks = [{r[0]: r for r in arm["selected"] if r[-1] == 1} for arm in (native, plugin)]
    shared = sorted(set(tracks[0]) & set(tracks[1]))
    references = {key: p for key in shared
                  if (p := base.interp(*pins, tracks[0][key][1])) is not None}
    results = []
    for window in (receipt["final"] or {}).get("windows", []):
        begin, end = window["onset_ns"], window["end_ns"]
        anchor = max((key for key in references if key < begin), default=None)
        window_keys = [key for key in references if begin <= key < end + 3 * NS]
        results.append(dict(
            event=window["id"], kind=window["kind"],
            count_shared=len(window_keys),
            native=base.displacement_error(dict(poses=tracks[0]), window_keys, anchor, references),
            plugin=base.displacement_error(dict(poses=tracks[1]), window_keys, anchor, references)))
    print(json.dumps(results, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
