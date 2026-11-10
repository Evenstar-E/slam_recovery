"""Recompute archived trace observations from fixed Git blobs; no ROS or remote execution."""

import collections
import csv
import hashlib
import io
import json
import math
import struct
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REV = "4255cbe601263e458e772c08f9fce83bc36307e3"
PREFIX = "docs/review_20261109_bbc3dcb/"


def blob(name):
    return subprocess.check_output(["git", "-C", str(ROOT), "show", REV + ":" + PREFIX + name])


def extra(text):
    result, key = {}, None
    for token in text.split("|"):
        if "=" in token:
            key, value = token.split("=", 1)
            result[key] = value
        elif key:
            result[key] += "|" + token
    return result


def main():
    receipt_names = ["trace_20261110T015818Z_2883571_receipt.json",
                     "trace_20261110T020104Z_2887395_receipt.json"]
    traces, receipts, runs = [], [], []
    for index, name in enumerate(("on1.csv", "on2.csv")):
        data = blob(name)
        rows = list(csv.DictReader(io.StringIO(data.decode("utf-8"))))
        receipt = json.loads(blob(receipt_names[index]))
        digest = hashlib.sha256(data).hexdigest()
        assert digest == receipt["host"]["trace_file"]["sha256"]
        traces.append(rows)
        receipts.append(receipt)
        groups = [r for r in rows if r["kind"] == "GROUP"]
        states = [r for r in rows if r["kind"] == "STATE"]
        arrivals = [r for r in rows if r["kind"] == "ARRIVE"]
        empty = [r for r in groups if int(r["n_items"]) == 0]
        assert len(groups) == len(states)
        assert all(g["lid_stamp_ns"] == s["lid_stamp_ns"] for g, s in zip(groups, states))
        assert all(hashlib.sha256(struct.pack("<q", int(r["lid_stamp_ns"]))).hexdigest()
                   == r["stamps_sha256"] for r in arrivals)
        assert all(r["first_stamp_ns"] == r["last_stamp_ns"] == "-1"
                   and r["stamps_sha256"] == hashlib.sha256(b"").hexdigest() for r in empty)
        for state in states:
            position = list(map(float, extra(state["extra"])["pos"].split("|")))
            assert len(position) == 3 and all(math.isfinite(v) for v in position)
        runs.append({"csv": name, "sha256": digest,
                     "rows": dict(collections.Counter(r["kind"] for r in rows)),
                     "empty_groups": len(empty), "status": receipt["status"],
                     "odom_messages": receipt["output"]["odometry_messages"]})

    for field in ("script", "input_bag", "config_m2dgr", "config_camera", "host_binary"):
        assert receipts[0]["pre_run"]["sha256"][field] == receipts[1]["pre_run"]["sha256"][field]
    assert receipts[0]["host"]["runtime_library"]["sha256"] == receipts[1]["host"]["runtime_library"]["sha256"]
    for kind in ("GROUP", "IMUINIT"):
        a = [r for r in traces[0] if r["kind"] == kind]
        b = [r for r in traces[1] if r["kind"] == kind]
        fields = ("lid_stamp_ns", "n_items", "first_stamp_ns", "last_stamp_ns", "stamps_sha256", "extra")
        assert len(a) == len(b) and all(all(x[f] == y[f] for f in fields) for x, y in zip(a, b))

    a = [r for r in traces[0] if r["kind"] == "STATE"]
    b = [r for r in traces[1] if r["kind"] == "STATE"]
    assert len(a) == len(b) and all(x["lid_stamp_ns"] == y["lid_stamp_ns"] for x, y in zip(a, b))
    deltas = [max(abs(x - y) for x, y in zip(
        map(float, extra(left["extra"])["pos"].split("|")),
        map(float, extra(right["extra"])["pos"].split("|")))) for left, right in zip(a, b)]
    start = int(a[0]["lid_stamp_ns"])
    thresholds = []
    for tolerance in (0.001, 0.01, 0.1, 1, 10, 100):
        index = next((i for i, d in enumerate(deltas) if d > tolerance), None)
        thresholds.append({"threshold_m": tolerance, "index": index,
                           "elapsed_s": None if index is None else (int(a[index]["lid_stamp_ns"]) - start) / 1e9,
                           "max_axis_delta_m": None if index is None else deltas[index]})
    result = {"source_revision": REV, "scope": "Archived CSV recomputation, not native rerun",
              "runs": runs, "group_and_imuinit_record_fields_identical": True,
              "state_stamps_identical": True, "thresholds": thresholds,
              "final_max_axis_delta_m": deltas[-1], "maximum_max_axis_delta_m": max(deltas),
              "samples_over_1mm": sum(d > 0.001 for d in deltas),
              "samples_over_0_1m": sum(d > 0.1 for d in deltas),
              "limits": "No raw consumed IMU contents; full-sample hash recipe not regenerated; no OFF control, GT/ATE or full-state comparison."}
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
