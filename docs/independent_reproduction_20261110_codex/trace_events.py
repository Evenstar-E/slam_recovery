"""Recompute package identities and trace/receipt SHA from canonical Git blobs.

Pair GROUP -> next STATE within one writer stream, rejecting missing/interleaved
packages. Cross-run keys are image timestamp + observed measures stage, not STATE
timestamp or row index. This is package correspondence, not physical-time/GT pairing.
"""
from collections import Counter, defaultdict
import csv
import hashlib
import io
import json
from pathlib import Path
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[2]
REV = "39eac2f337eaf2b9df28aa0e9b015b36d0ecf34d"
PREFIX = "docs/review_20261109_bbc3dcb/"
SOURCES = (("default", "trace_default_emit_fixed.csv", "trace_20261110T023139Z_2912547_receipt.json"),
           ("on1", "on1.csv", "trace_20261110T015818Z_2883571_receipt.json"),
           ("on2", "on2.csv", "trace_20261110T020104Z_2887395_receipt.json"))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def blob(name):
    return subprocess.check_output(["git", "-C", str(ROOT), "show", REV+":"+PREFIX+name])


def extra(text):
    result, key = {}, None
    for token in text.split("|"):
        if "=" in token:
            key, value = token.split("=", 1)
            result[key] = value
        elif key:
            result[key] += "|"+token
    return result


def pair_events(rows):
    pending, pairs, keys = None, [], set()
    for line, row in enumerate(rows, 2):
        if row["kind"] == "GROUP":
            assert pending is None, "Second GROUP before STATE"
            pending = (line, row)
        elif row["kind"] == "STATE":
            assert pending is not None, "STATE without GROUP"
            gline, group = pending
            fields = extra(group["extra"])
            image_ns = int(fields["img_stamp_ns"])
            key = (image_ns, int(fields["mesures"]))
            assert key not in keys, "Ambiguous duplicate image/stage identity"
            keys.add(key)
            pairs.append({"key": key, "group": group, "state": row,
                          "group_csv_line": gline, "state_csv_line": line})
            pending = None
    assert pending is None, "Final GROUP lacks STATE"
    return pairs


def signature(row):
    return tuple(row[k] for k in ("lid_stamp_ns", "n_items", "first_stamp_ns",
                                  "last_stamp_ns", "stamps_sha256", "extra"))


def position(pair):
    values = list(map(float, extra(pair["state"]["extra"])["pos"].split("|")))
    import math
    assert len(values) == 3 and all(math.isfinite(v) for v in values)
    return values


def compare(left, right):
    index = {tuple(p["key"]): p for p in right}
    assert {tuple(p["key"]) for p in left} == set(index), "Missing package identity"
    deltas, timestamp_mismatch, first = [], 0, None
    for order, a in enumerate(left):
        b = index[tuple(a["key"])]
        assert signature(a["group"]) == signature(b["group"]), "Different GROUP support"
        delta = max(abs(x-y) for x, y in zip(position(a), position(b)))
        deltas.append(delta)
        different = a["state"]["lid_stamp_ns"] != b["state"]["lid_stamp_ns"]
        timestamp_mismatch += different
        if first is None and delta > .001:
            first = {"package_index_zero_based": order, "image_stage_key": a["key"],
                     "max_axis_delta_m": delta, "left_state_ns": a["state"]["lid_stamp_ns"],
                     "right_state_ns": b["state"]["lid_stamp_ns"],
                     "left_csv_lines": [a["group_csv_line"], a["state_csv_line"]],
                     "right_csv_lines": [b["group_csv_line"], b["state_csv_line"]]}
    return {"common_packages": len(left), "missing_packages": 0, "group_signatures_equal": True,
            "state_timestamp_mismatches": timestamp_mismatch, "first_over_1mm": first,
            "maximum_max_axis_delta_m": max(deltas),
            "meaning": "Difference at matched package stage; not ATE/RPE or GT error. "
                       "STATE timestamp equality is reported separately, not assumed."}


def main():
    results, all_pairs, receipts = {}, {}, {}
    source_hashes = {}
    runner = blob("fl_run_isolated.sh")
    source_hashes["fl_run_isolated.sh"] = sha(runner)
    for label, filename, receipt_name in SOURCES:
        raw, receipt_raw = blob(filename), blob(receipt_name)
        source_hashes[filename], source_hashes[receipt_name] = sha(raw), sha(receipt_raw)
        receipt = json.loads(receipt_raw)
        receipts[label] = receipt
        assert sha(raw) == receipt["host"]["trace_file"]["sha256"]
        assert sha(runner) == receipt["pre_run"]["sha256"]["script"]
        rows = list(csv.DictReader(io.StringIO(raw.decode("utf8"))))
        pairs = pair_events(rows)
        all_pairs[label] = pairs
        groups = [p["group"] for p in pairs]
        empty = [g for g in groups if int(g["n_items"]) == 0]
        assert all(g["first_stamp_ns"] == g["last_stamp_ns"] == "-1"
                   and g["stamps_sha256"] == sha(b"") for g in empty)
        arrivals = [r for r in rows if r["kind"] == "ARRIVE"]
        assert all(sha(struct.pack("<q", int(r["lid_stamp_ns"]))) == r["stamps_sha256"]
                   for r in arrivals)
        by_image = defaultdict(list)
        for pair in pairs:
            by_image[pair["key"][0]].append(pair)
        initial = by_image.pop(-1)
        assert len(initial) == 1 and extra(initial[0]["group"]["extra"])["img"] == "0"
        complete, incomplete = 0, []
        for image, events in by_image.items():
            stage_counts = [(p["key"][1], int(p["group"]["n_items"])) for p in events]
            if len(events) == 2 and stage_counts[0] == (1, 0) and stage_counts[1][0] == 2 and stage_counts[1][1] > 0:
                complete += 1
            else:
                incomplete.append({"image_ns": image, "stages_and_imu_counts": stage_counts})
        checkout = (ROOT/PREFIX/filename).read_bytes()
        assert checkout.replace(b"\r\n", b"\n") == raw.replace(b"\r\n", b"\n"), "Non-newline checkout difference"
        results[label] = {
            "csv": filename, "rows": dict(Counter(r["kind"] for r in rows)),
            "csv_receipt_sha_verified": True, "runner_sha_verified": True,
            "blob_sha256": sha(raw), "checkout_sha256": sha(checkout),
            "checkout_identical": checkout == raw, "newline_normalized_identical": True,
            "empty_imu_groups": len(empty), "empty_with_image": sum(extra(g["extra"])["img"] == "1" for g in empty),
            "distinct_image_ids": len(by_image), "complete_empty_nonempty_pairs": complete,
            "initial_nonimage_packages": len(initial), "incomplete_image_packages": incomplete,
            "group_to_state_stamp_mismatches": sum(p["group"]["lid_stamp_ns"] != p["state"]["lid_stamp_ns"] for p in pairs),
            "receipt_status": receipt["status"], "termination": receipt["termination"],
            "process_exit": receipt["process_exit"], "native_rerun": False,
            "odom_messages_receipt_only": receipt["output"]["odometry_messages"],
            "runtime_binary_sha": receipt["host"]["sha256"],
            "runtime_library_sha": receipt["host"]["runtime_library"]["sha256"],
            "cpu_affinity": receipt["run"]["taskset_prefix"],
            "imuinit_signatures": [signature(r) for r in rows if r["kind"] == "IMUINIT"]}
    assert results["default"]["imuinit_signatures"] == results["on1"]["imuinit_signatures"] == results["on2"]["imuinit_signatures"]
    for field in ("script", "input_bag", "config_m2dgr", "config_camera"):
        assert len({r["pre_run"]["sha256"][field] for r in receipts.values()}) == 1
    output = {"source_revision": REV, "status": "PASS_ARCHIVE_RECOMPUTATION",
              "runs": results, "source_blob_sha256": source_hashes,
              "on1_on2": compare(all_pairs["on1"], all_pairs["on2"]),
              "default_on1": compare(all_pairs["default"], all_pairs["on1"]),
              "limits": ["No raw input/output bags or GT independently measured.",
                         "IMU hash covers stamps; raw sensor values are not verified.",
                         "Measures stages are observed trace identities, not an inferred count of LiDAR scans.",
                         "Build and CPU affinity both differ; this is not a single-factor causal test.",
                         "Receipt status OK includes planned native kill code 137, not native exit 0."]}
    print(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
