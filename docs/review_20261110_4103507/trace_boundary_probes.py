"""Verify trace comparison boundaries at a fixed Git revision, using synthetic CSV only."""

import csv
import io
import json
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
REVISION = "41035074f63fe1d9e77b9b8f0643f757bb191eab"
PREFIX = "docs/review_20261109_bbc3dcb/"
HEADER = "kind,wall_ns,lid_stamp_ns,n_items,first_stamp_ns,last_stamp_ns,stamps_sha256,extra"


def source(name):
    return subprocess.check_output(
        ["git", "-C", str(ROOT), "show", REVISION + ":" + PREFIX + name],
        encoding="utf-8")


def load_module(name, filename):
    module = types.ModuleType(name)
    module.__file__ = str(ROOT / PREFIX / filename)
    sys.modules[name] = module
    exec(compile(source(filename), module.__file__, "exec"), module.__dict__)
    return module


def main():
    compare = load_module("trace_compare", "trace_compare.py")
    tests = load_module("fixed_trace_tests", "test_trace_compare.py")
    # The historical fixture helper leaves some files behind. Confine all to one cleanable folder.
    with tempfile.TemporaryDirectory(prefix="trace-review-") as temp:
        with patch.object(tempfile, "tempdir", temp):
            result = unittest.TextTestRunner(verbosity=1).run(
                unittest.defaultTestLoader.loadTestsFromModule(tests))
    if not result.wasSuccessful():
        raise AssertionError("Existing trace fixtures failed")

    def state(stamp, pos):
        return ["STATE", 1000, stamp, 0, stamp, stamp, "", "pos=" + pos]

    def group(stamp=100, image=90):
        return ["GROUP", 1000, stamp, 3, 10, 30, "a" * 64,
                f"mesures=1|img=1|img_stamp_ns={image}|need_init=0"]

    def parse_rows(rows):
        text = io.StringIO()
        writer = csv.writer(text)
        writer.writerow(HEADER.split(","))
        writer.writerows(rows)
        with patch("builtins.open", return_value=io.StringIO(text.getvalue())):
            return compare.parse("synthetic.csv")

    outputs = {"source_revision": REVISION, "fixture_tests": result.testsRun,
               "scope": "Synthetic inputs only; no native traces or ROS runs"}
    outputs["different_frame_ids"] = compare.judge(
        parse_rows([state(100, "0|0|0")]), parse_rows([state(900, "0|0|0")]))
    assert outputs["different_frame_ids"]["verdict"] == "NO_DIVERGENCE"

    outputs["empty_inputs"] = compare.judge(parse_rows([]), parse_rows([]))
    assert outputs["empty_inputs"]["verdict"] == "NO_DIVERGENCE"

    outputs["nonfinite_state"] = compare.judge(
        parse_rows([state(100, "nan|0|0")]), parse_rows([state(100, "20|0|0")]))
    assert outputs["nonfinite_state"]["verdict"] == "NO_DIVERGENCE"

    def bare_csv(pos):
        text = HEADER + "\nSTATE,1000,100,0,100,100,,pos=" + pos + "\n"
        with patch("builtins.open", return_value=io.StringIO(text)):
            return compare.parse("malformed.csv")

    outputs["extra_csv_columns"] = compare.judge(bare_csv("0,4,9"), bare_csv("0,8,12"))
    assert outputs["extra_csv_columns"]["verdict"] == "NO_DIVERGENCE"

    outputs["group_identity_changed"] = compare.judge(
        parse_rows([group(100, 90), state(100, "0|0|0")]),
        parse_rows([group(999, 95), state(100, "5|0|0")]))
    assert outputs["group_identity_changed"]["groups"]["identical"]
    assert "cannot be the mechanism" in outputs["group_identity_changed"]["why"]

    control = (parse_rows([state(100, "0|0|0"), state(200, "0|0|0")]),
               parse_rows([state(100, "0|0|0")]))
    outputs["missing_control_sample"] = compare.judge(
        parse_rows([state(100, "0|0|0")]), parse_rows([state(100, "5|0|0")]),
        control=control)
    assert "not caused by tracing" in outputs["missing_control_sample"]["why"]

    outputs["valid_first_difference"] = compare.first_state_divergence(
        parse_rows([state(100, "0|0|0"), state(200, "0|0|0")]),
        parse_rows([state(100, "0|0|0"), state(200, "5|0|0")]))
    assert outputs["valid_first_difference"] == {
        "index": 1, "stamp_ns": 200, "max_axis_delta_m": 5.0}
    print(json.dumps(outputs, indent=2, ensure_ascii=False))
    print("Six invalid-evidence counterexamples and one valid control confirmed at the fixed revision.")


if __name__ == "__main__":
    main()
