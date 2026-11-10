"""Protect the comparison from index-only pairing and ambiguous package IDs."""
import unittest
from trace_events import compare, pair_events


def event(image=100, state_time=100, position="0|0|0"):
    group = {"kind": "GROUP", "lid_stamp_ns": "90", "n_items": "0",
             "first_stamp_ns": "-1", "last_stamp_ns": "-1", "stamps_sha256": "empty",
             "extra": f"mesures=1|img=1|img_stamp_ns={image}|need_init=0"}
    state = {"kind": "STATE", "lid_stamp_ns": str(state_time), "extra": "pos="+position}
    return [group, state]


class PairIdentityTest(unittest.TestCase):
    def test_missing_state_rejected(self):
        with self.assertRaises(AssertionError):
            pair_events(event()[:1])

    def test_interleaved_groups_rejected(self):
        with self.assertRaises(AssertionError):
            pair_events(event()[:1]+event(200))

    def test_duplicate_identity_rejected(self):
        with self.assertRaises(AssertionError):
            pair_events(event()+event())

    def test_reordered_packages_match_by_identity_and_expose_stamp_change(self):
        left = pair_events(event()+event(200, 200, "1|0|0"))
        right = pair_events(event(200, 201, "1|0|0")+event())
        result = compare(left, right)
        self.assertEqual(result["maximum_max_axis_delta_m"], 0)
        self.assertEqual(result["state_timestamp_mismatches"], 1)

    def test_missing_package_rejected(self):
        with self.assertRaises(AssertionError):
            compare(pair_events(event()+event(200)), pair_events(event()))


if __name__ == "__main__":
    unittest.main()
