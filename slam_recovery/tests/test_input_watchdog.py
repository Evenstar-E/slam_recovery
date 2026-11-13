"""The pose-stream watchdog: a host that stops publishing must end the run as an error.

FAST-LIO hibernates when its position covariance crosses fixed thresholds and stops publishing
/Odometry while it re-initialises (laserMapping.cpp:890-948). In the authorised run the driver
then waited out the remaining 165 s for an E1 it could never receive. That condition is local to
this host, so the driver stops and reports it instead of silently running to the wall clock.
"""

import unittest

from slam_recovery.ros.recovery_node import pose_stream_health


class PoseStreamHealthTest(unittest.TestCase):
    def test_disabled_by_default(self):
        h = pose_stream_health(0, None, 100.0, 200.0, 0.0)
        self.assertEqual(h["status"], "DISABLED")

    def test_no_pose_inside_the_startup_grace(self):
        h = pose_stream_health(0, None, 100.0, 105.0, 15.0)
        self.assertEqual(h["status"], "WAITING_FOR_FIRST_POSE")
        self.assertEqual(h["silence_s"], 5.0)

    def test_no_pose_beyond_the_grace_is_stale(self):
        h = pose_stream_health(0, None, 100.0, 120.0, 15.0)
        self.assertEqual(h["status"], "STALE")

    def test_the_first_pose_grace_is_separate_from_the_stale_limit(self):
        # FAST-LIO needs ~17-19 s to initialise its IMU; a 15 s startup grace killed the
        # authorised v5 run before the first pose.
        h = pose_stream_health(0, None, 100.0, 120.0, 15.0, first_pose_grace_s=60.0)
        self.assertEqual(h["status"], "WAITING_FOR_FIRST_POSE")
        self.assertEqual(h["first_pose_grace_s"], 60.0)
        h2 = pose_stream_health(0, None, 100.0, 170.0, 15.0, first_pose_grace_s=60.0)
        self.assertEqual(h2["status"], "STALE")

    def test_recent_pose_is_ok(self):
        h = pose_stream_health(10, 190.0, 100.0, 200.0, 15.0)
        self.assertEqual(h["status"], "OK")
        self.assertEqual(h["silence_s"], 10.0)

    def test_silence_beyond_the_limit_is_stale(self):
        h = pose_stream_health(949, 195.0, 100.0, 216.0, 15.0)
        self.assertEqual(h["status"], "STALE")
        self.assertEqual(h["silence_s"], 21.0)

    def test_a_natural_sleep_gap_is_not_a_stale_stream(self):
        # FAST-LIO's own E1 sleep is 23.8 s; a 15 s stale limit during it would abort the
        # recovery the run is waiting for.
        h = pose_stream_health(949, 195.0, 100.0, 216.0, 15.0,
                               host_state="HIBERNATING", hibernation_max_s=90.0)
        self.assertEqual(h["status"], "HOST_HIBERNATING")
        self.assertEqual(h["silence_s"], 21.0)

    def test_a_host_that_never_wakes_times_out(self):
        h = pose_stream_health(949, 100.0, 100.0, 200.0, 15.0,
                               host_state="HIBERNATING", hibernation_max_s=90.0)
        self.assertEqual(h["status"], "HOST_HIBERNATION_TIMEOUT")

    def test_publishing_uses_the_ordinary_limit(self):
        h = pose_stream_health(949, 195.0, 100.0, 216.0, 15.0,
                               host_state="PUBLISHING", hibernation_max_s=90.0)
        self.assertEqual(h["status"], "STALE")



class DurationStatsTest(unittest.TestCase):
    def test_percentiles_and_empty(self):
        from slam_recovery.ros.recovery_node import duration_stats
        self.assertEqual(duration_stats([]), {"n": 0})
        s = duration_stats([0.001, 0.002, 0.003, 0.004])
        self.assertEqual(s["n"], 4)
        self.assertTrue(2.0 <= s["p50_ms"] <= 3.0)
        self.assertAlmostEqual(s["max_ms"], 4.0, delta=1e-9)

if __name__ == "__main__":
    unittest.main()
