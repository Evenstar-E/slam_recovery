"""Regression tests for the scan-cache identity in verify_four_arm_independent.py.

The review broke the old cache with a concrete case: the cache was keyed on the bag's basename,
so a renamed or modified bag -- or a nonexistent path -- could be served from an entry that no
longer described it. These tests pin the two properties that stop that:

  * the key covers the source sha256, the filter parameters and the script version;
  * a hit is re-validated field by field, and a missing source raises before any lookup.

Run:  python3 -m unittest docs/review_20261109_bbc3dcb/test_verify_four_arm_cache.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verify_four_arm_independent as V  # noqa: E402

SHA_A = "a" * 64
SHA_B = "b" * 64


def _write_cache(path, sha, layout="point_step=24 x@0"):
    """A cache payload that would pass validation for (sha, current params)."""
    meta = V._cache_meta(sha, layout)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    np.savez(path,
             starts=np.array([0, 2]),
             pts=np.zeros((2, 3)),
             stamps=np.array([1.0, 2.0]),
             meta=np.array(meta))


class CacheIdentityTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old_cache = V.CACHE
        V.CACHE = self._tmp.name

    def tearDown(self):
        V.CACHE = self._old_cache
        self._tmp.cleanup()

    def test_source_change_moves_the_key(self):
        self.assertNotEqual(V._cache_path(SHA_A), V._cache_path(SHA_B))

    def test_param_change_moves_the_key(self):
        base = V._cache_path(SHA_A)
        old = V.RMIN
        try:
            V.RMIN = old + 0.1
            self.assertNotEqual(base, V._cache_path(SHA_A))
        finally:
            V.RMIN = old

    def test_script_version_moves_the_key(self):
        base = V._cache_path(SHA_A)
        old = V.SCRIPT_VERSION
        try:
            V.SCRIPT_VERSION = old + "-dirty"
            self.assertNotEqual(base, V._cache_path(SHA_A))
        finally:
            V.SCRIPT_VERSION = old

    def test_valid_entry_is_accepted(self):
        p = V._cache_path(SHA_A)
        _write_cache(p, SHA_A)
        self.assertTrue(V._cache_is_valid(p, SHA_A))

    def test_entry_for_another_source_is_rejected(self):
        p = V._cache_path(SHA_A)
        _write_cache(p, SHA_B)          # right place, wrong content identity
        self.assertFalse(V._cache_is_valid(p, SHA_A))

    def test_entry_with_stale_params_is_rejected(self):
        p = V._cache_path(SHA_A)
        _write_cache(p, SHA_A)
        old = V.MAX_KF_POINTS
        try:
            V.MAX_KF_POINTS = old * 2   # same file, different filter
            self.assertFalse(V._cache_is_valid(p, SHA_A))
        finally:
            V.MAX_KF_POINTS = old

    def test_corrupt_entry_is_rejected(self):
        p = V._cache_path(SHA_A)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as fh:
            fh.write(b"not an npz")
        self.assertFalse(V._cache_is_valid(p, SHA_A))

    def test_missing_source_raises_even_with_a_cache_present(self):
        """The reviewer's case: a populated cache must not answer for a path that does not exist."""
        _write_cache(V._cache_path(SHA_A), SHA_A)
        with self.assertRaises(FileNotFoundError):
            V.load_scans(os.path.join(self._tmp.name, "no_such_bag.bag"), SHA_A)

    def test_meta_is_json_and_records_layout_and_params(self):
        meta = json.loads(V._cache_meta(SHA_A, "point_step=24"))
        for k in ("sha", "layout", "topic", "rmin", "rmax", "max_points_per_scan",
                  "script_version"):
            self.assertIn(k, meta)
        self.assertEqual(meta["sha"], SHA_A)


if __name__ == "__main__":
    unittest.main()
