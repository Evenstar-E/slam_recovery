#!/usr/bin/env python3
"""Regression tests for the M2 point-identity contract.

Run with the environment that has `rosbags` (system python3 here):
    python3 -m unittest docs/review_20261109_bbc3dcb/test_m2_point_id.py -v

The subject is a bag produced by `run_fixed_input_repair_c0c3.py build-filtered-bag`
after the point-id fix, plus its sidecar. Paths are overridable by environment variable so the
test can run against a fresh build without editing it.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import verify_four_arm_independent as V  # noqa: E402

SRC = os.environ.get("M2_SRC_BAG", "/tmp/fastlivo/hall01_inj43.bag")
IDBAG = os.environ.get("M2_ID_BAG", "/tmp/fastlivo/hall01_inj43_filtered_id.bag")
SIDECAR = os.environ.get("M2_SIDECAR", "/tmp/fastlivo/hall01_inj43_filtered_id_report.json")
ID_TOPIC = "/velodyne_points/kept_index"
SAMPLE = 20


def _clouds(path):
    """Yield (scan_ns, msg, rows) for every scan in a bag."""
    with V.Reader(path) as r:
        conns = [c for c in r.connections if c.topic == V.SCAN_TOPIC]
        for conn, _t, raw in r.messages(connections=conns):
            m = V.TYPESTORE.deserialize_ros1(raw, conn.msgtype)
            step = int(m.point_step)
            buf = np.asarray(m.data, dtype=np.uint8).tobytes()
            yield (int(m.header.stamp.sec) * 10 ** 9 + int(m.header.stamp.nanosec),
                   m, buf, step)


def _masks(path):
    with V.Reader(path) as r:
        conns = [c for c in r.connections if c.topic == ID_TOPIC]
        for conn, _t, raw in r.messages(connections=conns):
            m = V.TYPESTORE.deserialize_ros1(raw, conn.msgtype)
            yield np.asarray(m.data, dtype=np.uint32), m


class TestPointIdentity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (os.path.exists(IDBAG) and os.path.exists(SIDECAR)):
            raise unittest.SkipTest(f"missing {IDBAG} or {SIDECAR}")
        cls.side = json.load(open(SIDECAR, encoding="utf-8"))
        cls.per = cls.side["per_frame"]

    def test_sidecar_binds_both_bags(self):
        self.assertIn("source_bag_sha256", self.side)
        self.assertIn("output_bag_sha256", self.side)
        self.assertEqual(len(self.side["source_bag_sha256"]), 64)
        self.assertEqual(len(self.side["output_bag_sha256"]), 64)

    def test_mask_pairing_and_sha(self):
        """Every scan has a mask, with the same scan_ns, and the sidecar hash matches."""
        by_ns = {f["scan_ns"]: f for f in self.per}
        count = 0
        for idx, m in _masks(IDBAG):
            # the mask message carries scan_ns in its dimension label
            label = m.layout.dim[0].label
            scan_ns = int(label.split("=", 1)[1])
            rec = by_ns.get(scan_ns)
            self.assertIsNotNone(rec, f"no sidecar entry for scan_ns={scan_ns}")
            self.assertEqual(len(idx), rec["n_kept"])
            h = hashlib.sha256(np.asarray(idx, dtype="<i4").tobytes()).hexdigest()
            self.assertEqual(h, rec["mask_sha256"])
            count += 1
        self.assertEqual(count, len(self.per))

    def test_mask_is_sorted_and_in_range(self):
        for idx, _m in _masks(IDBAG):
            if len(idx) < 2:
                continue
            self.assertTrue(np.all(np.diff(idx.astype(np.int64)) > 0),
                            "mask is not strictly increasing")
            self.assertEqual(int(idx[-1]), int(idx.max()))

    def test_retained_rows_are_exactly_the_mask(self):
        """rows[mask] from the source equals the filtered payload, byte for byte."""
        src = {ns: (buf, step) for ns, _m, buf, step in _clouds(SRC)}
        checked = 0
        for (ns, m, buf, step), (idx, _im) in zip(_clouds(IDBAG), _masks(IDBAG)):
            if checked >= SAMPLE:
                break
            s_buf, s_step = src[ns]
            self.assertEqual(step, s_step)
            self.assertEqual(step, 24)
            s_rows = np.frombuffer(s_buf, dtype=np.uint8).reshape(-1, step)
            f_rows = np.frombuffer(buf, dtype=np.uint8).reshape(-1, step)
            self.assertEqual(len(f_rows), len(idx))
            self.assertTrue(np.array_equal(s_rows[idx.astype(np.int64)], f_rows),
                            f"rows[mask] != payload at scan_ns={ns}")
            self.assertEqual([(f.name, f.offset, f.datatype) for f in m.fields],
                             [("x", 0, 7), ("y", 4, 7), ("z", 8, 7),
                              ("intensity", 12, 7), ("time", 16, 7), ("ring", 20, 4)])
            self.assertEqual(int(m.row_step), step * int(m.width))
            checked += 1
        self.assertEqual(checked, SAMPLE)

    def test_zero_deletion_frame_has_identity_mask(self):
        """A frame the filter leaves alone must yield [0..N-1] and identical bytes."""
        zero = [f for f in self.per if f["n_kept"] == f["n_original"]]
        self.assertTrue(zero, "no untouched frame in this bag to test against")
        want = zero[0]["scan_ns"]
        src = {ns: buf for ns, _m, buf, _s in _clouds(SRC)}
        for (ns, _m, buf, _s), (idx, _im) in zip(_clouds(IDBAG), _masks(IDBAG)):
            if ns != want:
                continue
            self.assertTrue(np.array_equal(idx.astype(np.int64),
                                           np.arange(len(idx), dtype=np.int64)))
            self.assertEqual(buf, src[ns], "untouched frame's payload changed")
            return
        self.fail(f"scan {want} not found in the filtered bag")


if __name__ == "__main__":
    unittest.main(verbosity=2)
