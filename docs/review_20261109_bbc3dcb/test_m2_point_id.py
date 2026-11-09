#!/usr/bin/env python3
"""Regression tests for the M2 point-identity contract.

    python3 -m unittest discover -s docs/review_20261109_bbc3dcb -p "test_m2_point_id.py" -v

Two families:

  TestPointIdentity   reads the real bags; every join is by scan_ns, never by message order.
  TestFixtures        no bag access at all -- synthetic inputs that the validator must reject
                      (missing sidecar, wrong stride, wrong msgtype, wrong bag hash, duplicate
                      stamp, out-of-range index). A validator that accepts everything passes
                      the positive tests and fails these.
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
ID_MSGTYPE = "std_msgs/msg/UInt32MultiArray"
FIELDS = [("x", 0, 7), ("y", 4, 7), ("z", 8, 7),
          ("intensity", 12, 7), ("time", 16, 7), ("ring", 20, 4)]


def _sha256_file(path, chunk=1 << 22):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def _clouds(path):
    """{scan_ns: (rows, point_step, fields, width, row_step)} keyed by integer ns."""
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


def _mask_pairs(path, topic=ID_TOPIC, msgtype=ID_MSGTYPE):
    """[(scan_ns, idx, stride, size)] in stream order, so repeats survive."""
    pairs = []
    with V.Reader(path) as r:
        conns = [c for c in r.connections if c.topic == topic]
        for conn, _t, raw in r.messages(connections=conns):
            m = V.TYPESTORE.deserialize_ros1(raw, conn.msgtype)
            ns = int(m.layout.dim[0].label.split("=", 1)[1])
            pairs.append((ns, np.asarray(m.data, dtype=np.uint32),
                          int(m.layout.dim[0].stride), int(m.layout.dim[0].size)))
    return pairs


def validate(src, clouds, mask_pairs, side, filter_frames=None, bag_hashes=None,
             msgtype=None, schema_version=None):
    """Return a list of problems. Empty means the identity contract holds."""
    errs = []
    if msgtype is not None and msgtype != ID_MSGTYPE:
        errs.append(f"msgtype {msgtype} != {ID_MSGTYPE}")
    if schema_version is not None and int(schema_version) < 2:
        errs.append(f"id_schema_version {schema_version} < 2")
    if bag_hashes is not None:
        src_sha, out_sha = bag_hashes
        if src_sha != (side or {}).get("source_bag_sha256"):
            errs.append("source bag sha256 does not match the sidecar")
        if out_sha != (side or {}).get("output_bag_sha256"):
            errs.append("output bag sha256 does not match the sidecar")

    masks, dups = {}, []
    for ns, idx, stride, size in mask_pairs:
        if ns in masks:
            dups.append(ns)
        masks[ns] = (idx, stride, size)
    if dups:
        errs.append(f"duplicate mask stamps: {sorted(set(dups))[:5]}")
    if len(masks) != len(clouds):
        errs.append(f"{len(masks)} masks for {len(clouds)} clouds")

    per = {int(f["scan_ns"]): f for f in (side or {}).get("per_frame", [])}
    for ns, (rows, step, fields, width, row_step) in clouds.items():
        if ns not in masks:
            errs.append(f"{ns}: no mask")
            continue
        idx, stride, size = masks[ns]
        if fields != FIELDS:
            errs.append(f"{ns}: field layout changed")
        if step != 24 or row_step != 24 * width:
            errs.append(f"{ns}: point_step/row_step not 24/{24 * width}")
        if len(idx) != len(rows):
            errs.append(f"{ns}: len(mask)={len(idx)} != width {len(rows)}")
        if stride != len(idx) or size != len(idx):
            errs.append(f"{ns}: dim size/stride {size}/{stride} != len {len(idx)}")
        if len(idx) > 1 and not np.all(np.diff(idx.astype(np.int64)) > 0):
            errs.append(f"{ns}: mask not strictly increasing")
        n_src = len(src[ns][0]) if ns in src else None
        if n_src is None:
            errs.append(f"{ns}: not in source")
            continue
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
        cls.pairs = _mask_pairs(IDBAG)
        cls.clouds = _clouds(IDBAG)
        cls.src = _clouds(SRC)
        cls.per = {int(f["scan_ns"]): f for f in cls.side["per_frame"]}
        cls.hashes = (_sha256_file(SRC), _sha256_file(IDBAG))

    def test_bags_bound_by_hash(self):
        """The sidecar's hashes must equal the recomputed hashes of the bags on disk."""
        self.assertEqual(self.hashes[0], self.side["source_bag_sha256"])
        self.assertEqual(self.hashes[1], self.side["output_bag_sha256"])
        # and the validator itself rejects a mismatch
        errs = validate(self.src, self.clouds, self.pairs, self.side,
                        bag_hashes=("0" * 64, self.hashes[1]))
        self.assertTrue(any("source bag sha256" in e for e in errs), errs[:3])

    def test_every_cloud_has_a_mask_and_matches(self):
        errs = validate(self.src, self.clouds, self.pairs, self.side,
                        bag_hashes=self.hashes, msgtype=ID_MSGTYPE,
                        schema_version=self.side.get("id_schema_version"))
        self.assertEqual(errs, [], msg="; ".join(errs[:5]))

    def test_stripped_frames_are_covered(self):
        stripped = sorted(ns for ns, f in self.per.items() if f["strip_fraction"] > 0)
        self.assertGreater(len(stripped), 0)
        picks = [stripped[0], stripped[-1],
                 max(stripped, key=lambda n: self.per[n]["strip_fraction"])]
        self.assertEqual(len(set(picks)), 3)
        sub = [(ns, *self._pair(ns)) for ns in picks]
        errs = validate({n: self.src[n] for n in picks},
                        {n: self.clouds[n] for n in picks}, sub, self.side)
        self.assertEqual(errs, [], msg="; ".join(errs[:5]))
        for n in picks:
            self.assertGreater(float(self.per[n]["strip_fraction"]), 0.8)

    def test_zero_deletion_frame_is_identity(self):
        zero = [n for n, f in self.per.items() if f["n_kept"] == f["n_original"]]
        self.assertTrue(zero)
        ns = zero[0]
        idx = self._pair(ns)[0].astype(np.int64)
        self.assertTrue(np.array_equal(idx, np.arange(len(idx))))
        self.assertEqual(self.clouds[ns][0].tobytes(), self.src[ns][0].tobytes())

    def _pair(self, ns):
        for n, idx, stride, size in self.pairs:
            if n == ns:
                return idx, stride, size
        raise KeyError(ns)

    # -- negative, on the real data --------------------------------------------
    def test_rejects_wrong_scan_ns(self):
        errs = validate(self.src, self.clouds,
                        [(ns + 1, idx, s, z) for ns, idx, s, z in self.pairs], self.side)
        self.assertTrue(any("no mask" in e for e in errs), errs[:3])

    def test_rejects_out_of_range_index(self):
        ns = next(iter(self.clouds))
        idx, stride, size = self._pair(ns)
        bad = idx.copy()
        bad[0] = len(self.src[ns][0])
        pairs = [(n, (bad if n == ns else i), s, z) for n, i, s, z in self.pairs]
        errs = validate(self.src, self.clouds, pairs, self.side)
        self.assertTrue(any(">= n_original" in e for e in errs), errs[:3])

    def test_rejects_same_stamp_duplicate(self):
        """A second mask message under the *same* stamp is the real duplicate-stream case."""
        ns = next(iter(self.clouds))
        idx, stride, size = self._pair(ns)
        errs = validate(self.src, self.clouds, self.pairs + [(ns, idx, stride, size)], self.side)
        self.assertTrue(any("duplicate mask stamps" in e for e in errs), errs[:3])

    def test_rejects_filter_report_disagreement(self):
        ns = next(iter(self.clouds))
        frames = {n: {"kept": f["kept"]} for n, f in self.per.items()}
        frames[ns] = {"kept": frames[ns]["kept"] + 1}
        errs = validate(self.src, self.clouds, self.pairs, self.side, filter_frames=frames)
        self.assertTrue(any("filter report" in e for e in errs), errs[:3])


class TestFixtures(unittest.TestCase):
    """No bag access: synthetic inputs the validator must reject."""

    @staticmethod
    def _fixture():
        rng = np.random.default_rng(0)
        n, k = 12, 5
        src_rows = rng.integers(0, 255, (n, 24), dtype=np.uint8)
        idx = np.array([0, 2, 5, 7, 11], dtype=np.uint32)
        rows = src_rows[idx.astype(np.int64)]
        clouds = {100: (rows, 24, FIELDS, k, 24 * k)}
        src = {100: (src_rows, 24, FIELDS, n, 24 * n)}
        sha = hashlib.sha256(np.asarray(idx, dtype="<u4").tobytes()).hexdigest()
        side = {"source_bag_sha256": "a" * 64, "output_bag_sha256": "b" * 64,
                "id_schema_version": 2,
                "per_frame": [{"scan_ns": 100, "n_original": n, "n_kept": k,
                               "mask_sha256": sha, "strip_fraction": 0.58}]}
        pairs = [(100, idx, k, k)]
        return src, clouds, pairs, side

    def test_fixture_is_valid(self):
        src, clouds, pairs, side = self._fixture()
        self.assertEqual(validate(src, clouds, pairs, side), [])

    def test_rejects_missing_sidecar(self):
        src, clouds, pairs, _side = self._fixture()
        errs = validate(src, clouds, pairs, None)
        self.assertTrue(any("no sidecar entry" in e for e in errs), errs[:3])

    def test_rejects_empty_sidecar(self):
        src, clouds, pairs, _side = self._fixture()
        errs = validate(src, clouds, pairs, {"per_frame": []})
        self.assertTrue(any("no sidecar entry" in e for e in errs), errs[:3])

    def test_rejects_wrong_stride(self):
        src, clouds, pairs, side = self._fixture()
        bad = [(100, pairs[0][1], 4, pairs[0][3])]        # stride in bytes, the v1 bug
        errs = validate(src, clouds, bad, side)
        self.assertTrue(any("dim size/stride" in e for e in errs), errs[:3])

    def test_rejects_wrong_msgtype(self):
        src, clouds, pairs, side = self._fixture()
        errs = validate(src, clouds, pairs, side, msgtype="std_msgs/msg/Int32MultiArray")
        self.assertTrue(any("msgtype" in e for e in errs), errs[:3])

    def test_rejects_old_schema(self):
        src, clouds, pairs, side = self._fixture()
        errs = validate(src, clouds, pairs, side, schema_version=1)
        self.assertTrue(any("id_schema_version" in e for e in errs), errs[:3])

    def test_rejects_wrong_bag_hash(self):
        src, clouds, pairs, side = self._fixture()
        errs = validate(src, clouds, pairs, side, bag_hashes=("c" * 64, "b" * 64))
        self.assertTrue(any("source bag sha256" in e for e in errs), errs[:3])


if __name__ == "__main__":
    unittest.main(verbosity=2)
