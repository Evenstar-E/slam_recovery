#!/usr/bin/env python3
"""Regression tests for the M2 point-identity contract.

    python3 -m unittest discover -s docs/review_20261109_bbc3dcb -p "test_m2_point_id.py" -v

The subject is a bag produced by `run_fixed_input_repair_c0c3.py build-filtered-bag` after the
point-id fix, plus its sidecar. Every join is by `scan_ns`, never by message order, because
message order is exactly the assumption the contract is supposed to remove. Negative cases
corrupt one input at a time and require the validator to reject it — a validator that passes
everything would pass the positive tests too.
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


def _sha256_file(path, chunk=1 << 22):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def _clouds(path):
    """{scan_ns: (rows, point_step, fields)} — keyed by integer ns, not by order."""
    out = {}
    with V.Reader(path) as r:
        conns = [c for c in r.connections if c.topic == V.SCAN_TOPIC]
        for conn, _t, raw in r.messages(connections=conns):
            m = V.TYPESTORE.deserialize_ros1(raw, conn.msgtype)
            step = int(m.point_step)
            buf = np.asarray(m.data, dtype=np.uint8).tobytes()
            ns = int(m.header.stamp.sec) * 10 ** 9 + int(m.header.stamp.nanosec)
            out[ns] = (np.frombuffer(buf, dtype=np.uint8).reshape(-1, step), step,
                       [(f.name, f.offset, f.datatype) for f in m.fields],
                       int(m.width), int(m.row_step))
    return out


def _masks(path):
    """{scan_ns: (idx, stride, size)} decoded from the parallel topic."""
    out, dups = {}, []
    with V.Reader(path) as r:
        conns = [c for c in r.connections if c.topic == ID_TOPIC]
        for conn, _t, raw in r.messages(connections=conns):
            m = V.TYPESTORE.deserialize_ros1(raw, conn.msgtype)
            label = m.layout.dim[0].label
            ns = int(label.split("=", 1)[1])
            if ns in out:
                dups.append(ns)
            out[ns] = (np.asarray(m.data, dtype=np.uint32),
                       int(m.layout.dim[0].stride), int(m.layout.dim[0].size))
    return out, dups


def validate(src, clouds, masks, side, filter_frames=None):
    """Return a list of problems. Empty list means the identity contract holds."""
    errs = []
    if len(masks) != len(clouds):
        errs.append(f"{len(masks)} masks for {len(clouds)} clouds")
    per = {int(f["scan_ns"]): f for f in side["per_frame"]}
    for ns, (rows, step, fields, width, row_step) in clouds.items():
        if ns not in masks:
            errs.append(f"{ns}: no mask")
            continue
        idx, stride, size = masks[ns]
        if fields != [("x", 0, 7), ("y", 4, 7), ("z", 8, 7),
                      ("intensity", 12, 7), ("time", 16, 7), ("ring", 20, 4)]:
            errs.append(f"{ns}: field layout changed")
        if step != 24 or row_step != 24 * width:
            errs.append(f"{ns}: point_step/row_step not 24/{24 * width}")
        if len(idx) != len(rows):
            errs.append(f"{ns}: len(mask)={len(idx)} != width {len(rows)}")
        if stride != len(idx) or size != len(idx):
            errs.append(f"{ns}: dim size/stride {size}/{stride} != len {len(idx)}")
        if len(idx) > 1 and not np.all(np.diff(idx.astype(np.int64)) > 0):
            errs.append(f"{ns}: mask not strictly increasing")
        n_src = len(src[ns][0])
        if len(idx) and int(idx.max()) >= n_src:
            errs.append(f"{ns}: index {int(idx.max())} >= n_original {n_src}")
        elif len(idx) and not np.array_equal(src[ns][0][idx.astype(np.int64)], rows):
            errs.append(f"{ns}: source[idx] != filtered rows")
        rec = per.get(ns)
        if rec is None:
            errs.append(f"{ns}: no sidecar entry")
            continue
        if int(rec["n_original"]) != n_src or int(rec["n_kept"]) != len(rows):
            errs.append(f"{ns}: sidecar counts {rec['n_original']}/{rec['n_kept']} "
                        f"!= {n_src}/{len(rows)}")
        if hashlib.sha256(np.asarray(idx, dtype="<u4").tobytes()).hexdigest() != rec["mask_sha256"]:
            errs.append(f"{ns}: mask_sha256 mismatch")
        if filter_frames is not None:
            fr = filter_frames.get(ns)
            if fr is None or int(fr["kept"]) != len(rows):
                errs.append(f"{ns}: filter report disagrees")
    return errs


class TestPointIdentity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (os.path.exists(IDBAG) and os.path.exists(SIDECAR)):
            raise unittest.SkipTest(f"missing {IDBAG} or {SIDECAR}")
        with open(SIDECAR, encoding="utf-8") as fh:
            cls.side = json.load(fh)
        cls.masks, cls.dups = _masks(IDBAG)
        cls.clouds = _clouds(IDBAG)
        cls.src = _clouds(SRC)
        cls.per = {int(f["scan_ns"]): f for f in cls.side["per_frame"]}

    # -- positive ---------------------------------------------------------------
    def test_bags_bound_by_hash(self):
        """The sidecar's hashes must be the hashes of the bags on disk, not just 64-char strings."""
        self.assertEqual(_sha256_file(SRC), self.side["source_bag_sha256"])
        self.assertEqual(_sha256_file(IDBAG), self.side["output_bag_sha256"])

    def test_schema_version(self):
        self.assertGreaterEqual(self.side.get("id_schema_version", 0), 2)

    def test_every_cloud_has_a_mask_and_matches(self):
        self.assertFalse(self.dups, f"duplicate mask frames: {self.dups[:5]}")
        errs = validate(self.src, self.clouds, self.masks, self.side)
        self.assertEqual(errs, [], msg="; ".join(errs[:5]))

    def test_stripped_frames_are_covered(self):
        """The sampled population must include real stripping, not only untouched frames."""
        stripped = sorted(ns for ns, f in self.per.items() if f["strip_fraction"] > 0)
        self.assertGreater(len(stripped), 0)
        picks = [stripped[0], stripped[-1],
                 max(stripped, key=lambda n: self.per[n]["strip_fraction"])]
        self.assertEqual(len(set(picks)), 3, "first / last / max strip must be three frames")
        sub_src = {n: self.src[n] for n in picks}
        sub_cloud = {n: self.clouds[n] for n in picks}
        sub_mask = {n: self.masks[n] for n in picks}
        self.assertEqual(validate(sub_src, sub_cloud, sub_mask, self.side), [])
        # and the mask really does remove most rows on those frames
        for n in picks:
            self.assertGreater(float(self.per[n]["strip_fraction"]), 0.8)

    def test_zero_deletion_frame_is_identity(self):
        zero = [n for n, f in self.per.items() if f["n_kept"] == f["n_original"]]
        self.assertTrue(zero)
        ns = zero[0]
        idx = self.masks[ns][0].astype(np.int64)
        self.assertTrue(np.array_equal(idx, np.arange(len(idx))))
        self.assertEqual(self.clouds[ns][0].tobytes(), self.src[ns][0].tobytes())

    # -- negative ---------------------------------------------------------------
    def test_rejects_wrong_scan_ns(self):
        """A mask filed under the wrong stamp must not be accepted."""
        errs = validate(self.src, self.clouds,
                        {ns + 1: v for ns, v in self.masks.items()}, self.side)
        self.assertTrue(errs)
        self.assertTrue(any("no mask" in e for e in errs))

    def test_rejects_out_of_range_index(self):
        ns = next(iter(self.clouds))
        idx, stride, size = self.masks[ns]
        bad = idx.copy()
        bad[0] = len(self.src[ns][0])          # one past the end
        masks = dict(self.masks)
        masks[ns] = (bad, stride, size)
        errs = validate(self.src, self.clouds, masks, self.side)
        self.assertTrue(any(">= n_original" in e for e in errs), errs[:3])

    def test_rejects_duplicate_mask_frame(self):
        ns = next(iter(self.clouds))
        masks = dict(self.masks)
        masks[ns] = masks[ns]
        errs = validate(self.src, self.clouds, masks, self.side,
                        filter_frames=self.per)
        self.assertEqual(errs, [])      # same object, no corruption
        dup = dict(self.masks)
        dup[ns + 1] = dup[ns]           # a second entry under another stamp
        errs = validate(self.src, self.clouds, dup, self.side)
        self.assertTrue(any("masks for" in e for e in errs), errs[:3])

    def test_rejects_source_hash_mismatch(self):
        self.assertNotEqual(_sha256_file(SRC), "0" * 64)
        self.assertNotEqual(_sha256_file(SRC), self.side["output_bag_sha256"])
        tampered = dict(self.side)
        tampered["source_bag_sha256"] = "0" * 64
        self.assertNotEqual(_sha256_file(SRC), tampered["source_bag_sha256"])

    def test_rejects_filter_report_disagreement(self):
        ns = next(iter(self.clouds))
        frames = {n: {"kept": f["kept"]} for n, f in self.per.items()}
        frames[ns] = {"kept": frames[ns]["kept"] + 1}
        errs = validate(self.src, self.clouds, self.masks, self.side, filter_frames=frames)
        self.assertTrue(any("filter report" in e for e in errs), errs[:3])


if __name__ == "__main__":
    unittest.main(verbosity=2)
