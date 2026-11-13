"""The host's declared command surface, and the two commands that must not outrun it.

A host that cannot replay must not be sent `reprocess` after an accepted repair: the repair
clouds would be published and the record would look like a recovery whose last step was the
host's fault. A host that cannot restore must not be sent `restore` after a refusal, and the
refusal must say the map was left as written. Neither case is a new failure mode -- both are the
FAST-LIO2 shape (ikdtree + `re_slam`, no replay buffer, no replay command).

An *undeclared* host keeps the previous behaviour, because the FAST-LIVO2 runs have no
capabilities file; the summary says UNDECLARED so the difference is on the record.
"""

import json
import os
import tempfile
import unittest

import numpy as np

from slam_recovery.ros.recovery_node import (CheckpointClient, Episode, HostCapabilities,
                                             NativeClosedLoop, host_capabilities_record,
                                             message_disposition)
from slam_recovery.tests.test_cloud_repair import _Cloud, _plane
from slam_recovery.tests.test_recovery_node import _FakeLoopNode, _Report
from slam_recovery.tests.test_repair_sync import _FakeCP


class _CapCP(_FakeCP):
    def __init__(self, caps, **kw):
        super().__init__(True, **kw)
        self.caps = caps

    def capabilities(self):
        return self.caps


def _caps(**kw):
    base = {k: "YES" for k in HostCapabilities.KEYS}
    base.update(kw)
    return HostCapabilities({"commands": base})


class HostCapabilitiesParseTest(unittest.TestCase):
    def test_only_yes_is_supported(self):
        caps = _caps(reprocess="NO", restore="PARTIAL", hold="YES")
        self.assertTrue(caps.supports("hold"))
        self.assertFalse(caps.supports("reprocess"))
        self.assertFalse(caps.supports("restore"))

    def test_a_flat_document_is_accepted(self):
        caps = HostCapabilities({"restore": "yes", "snapshot": "NO"})
        self.assertTrue(caps.supports("restore"))
        self.assertFalse(caps.supports("snapshot"))
        # a key that was not declared is unsupported, never assumed
        self.assertFalse(caps.supports("reprocess"))

    def test_checkpoint_contents_are_carried_verbatim(self):
        caps = HostCapabilities({"commands": {"snapshot": "YES"},
                                 "checkpoint": {"eskf_state": True, "ikdtree": True,
                                                "imu_cache": False},
                                 "source": "fastlio2"})
        d = caps.as_dict()
        self.assertEqual(d["checkpoint"]["imu_cache"], False)
        self.assertEqual(d["source"], "fastlio2")


class CapabilitiesFileTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_missing_file_is_undeclared_not_supported(self):
        client = CheckpointClient(self.dir)
        self.assertIsNone(client.capabilities())

    def test_malformed_file_is_undeclared_not_a_permission(self):
        with open(os.path.join(self.dir, "capabilities.json"), "w", encoding="utf-8") as fh:
            fh.write("{not json")
        client = CheckpointClient(self.dir)
        self.assertIsNone(client.capabilities())

    def test_file_is_re_read_after_it_changes(self):
        path = os.path.join(self.dir, "capabilities.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"commands": {"reprocess": "NO"}}, fh)
        client = CheckpointClient(self.dir)
        self.assertFalse(client.capabilities().supports("reprocess"))
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"commands": {"reprocess": "YES"}, "source": "grown"}, fh)
        caps = client.capabilities()
        self.assertTrue(caps.supports("reprocess"))
        self.assertEqual(caps.source, "grown")


class CapabilityGateTest(unittest.TestCase):
    def _loop(self, caps, accepted=True):
        node = _FakeLoopNode(trigger_at=10 ** 9)
        node.evaluate_and_commit_candidate = lambda *a, **k: _Report(
            accepted=accepted,
            committed_pose_keys=[0, 1] if accepted else [],
            deferred_pose_keys=[] if accepted else [0, 1])
        plane = _plane()
        node.support_reference = lambda: plane
        corrupted = _plane(z=0.5)[::4]
        node.scan_buffer_body = {0: corrupted, 1: corrupted}
        loop = NativeClosedLoop(node, run_id="run")
        loop.repair_publish_enabled = True
        loop.published = []
        loop.publish_repair = loop.published.append
        loop.cp = _CapCP(caps) if caps is not None else _FakeCP(True)
        cloud = _Cloud()
        cloud.set_points([(float(x), float(y), float(z), 0.0, 0.0, 0)
                          for x, y, z in corrupted])
        for k in (0, 1):
            loop._scan_index[k] = (1000 + k, cloud)
        loop._last_incumbent = {0: np.eye(4), 1: np.eye(4)}
        ep = Episode(0, 1_000, np.eye(4), 2_000)
        ep.frames = [(k, 1_000, np.eye(4)) for k in (0, 1)]
        loop._open = ep
        loop.episodes = [ep]
        return loop, ep

    def test_an_accepted_candidate_is_not_replayed_on_a_host_without_reprocess(self):
        loop, ep = self._loop(_caps(reprocess="NO"))
        row = loop.decide(1_500, "test")
        self.assertIsNotNone(row)
        self.assertEqual(loop.cp.reprocess_calls, 0)
        self.assertEqual(loop.cp.set_state_calls, 0)
        # repairs are not published either: a cloud the host will never replay is not evidence
        self.assertEqual(len(loop.published), 0)
        self.assertEqual(ep.meta["native_checkpoint_skipped"], "reprocess_unsupported")
        d = ep.meta["recovery_disposition"]
        self.assertEqual(d["replay"], "NOT_SUPPORTED")
        self.assertEqual(d["subsequent_input"], "CONTINUES_FROM_UNCORRECTED_STATE")

    def test_a_refusal_is_not_rolled_back_on_a_host_without_restore(self):
        loop, ep = self._loop(_caps(restore="NO"), accepted=False)
        loop.decide(1_500, "test")
        self.assertEqual(loop.cp.restore_calls, 0)
        self.assertEqual(ep.meta["native_checkpoint_skipped"], "restore_unsupported")
        d = ep.meta["restore_disposition"]
        self.assertEqual(d["scope"], "NONE")
        self.assertEqual(d["rollback"], "NOT_SUPPORTED")
        self.assertEqual(d["subsequent_input"], "CONTINUES_FROM_UNROLLED_STATE")

    def test_a_declared_yes_keeps_the_existing_path(self):
        loop, ep = self._loop(_caps())
        loop.decide(1_500, "test")
        self.assertEqual(loop.cp.reprocess_calls, 1)
        self.assertNotIn("native_checkpoint_skipped", ep.meta)
        self.assertEqual(ep.meta["host_capabilities"]["commands"]["reprocess"], "YES")

    def test_an_undeclared_host_keeps_the_previous_behaviour(self):
        loop, ep = self._loop(None)
        loop.decide(1_500, "test")
        self.assertEqual(loop.cp.reprocess_calls, 1)
        rec = host_capabilities_record(loop)
        self.assertEqual(rec["status"], "UNDECLARED")


class MessageDispositionTest(unittest.TestCase):
    def _loop(self, ingested):
        node = _FakeLoopNode(trigger_at=10 ** 9)
        loop = NativeClosedLoop(node, run_id="run")
        loop.cp = None
        loop.next_kf_id = ingested
        loop.episodes = []
        loop.records = []
        return loop

    def _episode(self, idx, keys, decided=True, skipped=False, accepted=True):
        ep = Episode(idx, 1_000 + idx, np.eye(4), 2_000 + idx)
        ep.frames = [(k, 1_000, np.eye(4)) for k in keys]
        ep.decided = decided
        ep.meta = {"decision_skipped": "SEGMENT_CLOSED_BEFORE_DECISION"} if skipped else {}
        rec = None
        if decided and not skipped:
            rec = {"candidate_id": ep.candidate_id,
                   "committed_pose_keys": list(keys) if accepted else [],
                   "deferred_pose_keys": [] if accepted else list(keys),
                   "accepted": accepted}
        return ep, rec

    def test_each_key_is_in_exactly_one_class(self):
        loop = self._loop(5)
        ep, rec = self._episode(0, [0, 1])
        loop.episodes = [ep]
        loop.records = [rec]
        loop.pairer.poses_received = 6
        loop.pairer.scans_received = 7
        loop.pairer.paired = 5
        loop.pairer.scans_unpaired = 2
        d = message_disposition(loop)
        k = d["keyframes"]
        self.assertEqual((k["ingested"], k["quarantine_distinct"], k["never_quarantined"]), (5, 2, 3))
        self.assertEqual((k["committed"], k["deferred"], k["pending"], k["skipped"]), (2, 0, 0, 0))
        self.assertTrue(d["fully_accounted"])
        self.assertTrue(d["fully_decided"])
        self.assertEqual(d["unresolved"], [])

    def test_a_skipped_segment_is_counted_but_not_decided(self):
        loop = self._loop(1)
        ep, _ = self._episode(0, [0], decided=True, skipped=True)
        loop.episodes = [ep]
        d = message_disposition(loop)
        self.assertEqual(d["keyframes"]["skipped"], 1)
        self.assertFalse(d["fully_decided"])
        self.assertTrue(d["fully_accounted"])

    def test_a_key_in_two_episodes_is_unresolved(self):
        loop = self._loop(1)
        ep1, rec1 = self._episode(0, [0], accepted=True)
        ep2, _ = self._episode(1, [0], decided=False)
        loop.episodes = [ep1, ep2]
        loop.records = [rec1]
        d = message_disposition(loop)
        kinds = [u["kind"] for u in d["unresolved"]]
        self.assertIn("key_with_more_than_one_outcome", kinds)
        self.assertFalse(d["fully_accounted"])

    def test_a_committed_key_outside_the_episode_is_unresolved(self):
        loop = self._loop(3)
        ep, rec = self._episode(0, [0], accepted=True)
        rec["committed_pose_keys"] = [0, 7]
        loop.episodes = [ep]
        loop.records = [rec]
        d = message_disposition(loop)
        kinds = [u["kind"] for u in d["unresolved"]]
        self.assertIn("committed_key_not_in_episode_frames", kinds)


class PartialCapabilityTest(unittest.TestCase):
    """PARTIAL is usable but must travel with its limitation; NO is not usable."""

    def _loop(self, caps):
        from slam_recovery.tests.test_repair_sync import _FakeCP
        from slam_recovery.tests.test_cloud_repair import _Cloud, _plane
        from slam_recovery.tests.test_recovery_node import _FakeLoopNode, _Report

        node = _FakeLoopNode(trigger_at=10 ** 9)
        node.evaluate_and_commit_candidate = lambda *a, **k: _Report(
            accepted=True, committed_pose_keys=[0, 1], deferred_pose_keys=[])
        node.support_reference = lambda: _plane()
        corrupted = _plane(z=0.5)[::4]
        node.scan_buffer_body = {0: corrupted, 1: corrupted}
        loop = NativeClosedLoop(node, run_id="run")
        loop.repair_publish_enabled = True
        loop.published = []
        loop.publish_repair = loop.published.append
        cp = _FakeCP(True)
        cp.capabilities = lambda: caps
        loop.cp = cp
        cloud = _Cloud()
        cloud.set_points([(float(x), float(y), float(z), 0.0, 0.0, 0)
                          for x, y, z in corrupted])
        for k in (0, 1):
            loop._scan_index[k] = (1000 + k, cloud)
        loop._last_incumbent = {0: np.eye(4), 1: np.eye(4)}
        ep = Episode(0, 1_000, np.eye(4), 2_000)
        ep.frames = [(k, 1_000, np.eye(4)) for k in (0, 1)]
        loop._open = ep
        loop.episodes = [ep]
        return loop, ep

    def test_partial_reprocess_is_used_and_its_limitation_recorded(self):
        caps = HostCapabilities({"commands": dict(
            {k: "YES" for k in HostCapabilities.KEYS}, reprocess="PARTIAL"),
            "partial_notes": {"reprocess": "buffer replay, no IMU cache in checkpoint"}})
        loop, ep = self._loop(caps)
        loop.decide(1_500, "test")
        self.assertEqual(loop.cp.reprocess_calls, 1)
        d = ep.meta["replay_disposition"]
        self.assertEqual(d["status"], "PARTIAL")
        self.assertIn("buffer replay", d["limitation"])

    def test_a_host_without_set_state_gets_no_pose_writeback(self):
        caps = HostCapabilities({"commands": dict(
            {k: "YES" for k in HostCapabilities.KEYS}, set_state="NO")})
        loop, ep = self._loop(caps)
        loop.cp.reprocess_ack = "OK reprocess replay_suffix=0 replay_within_end=2 repaired_fed=2"
        loop.cp.status_ack = "OK status valid=1 repair_received=2 repair_applied=2 repaired_in_update=2"
        loop.decide(1_500, "test")
        self.assertEqual(loop.cp.set_state_calls, 0)
        self.assertEqual(ep.meta["native_writeback_skipped"]["reason"], "set_state_unsupported")
        # enqueue is not the update receipt; the status read supplies the latter
        self.assertEqual(ep.meta["repaired_fed"], 2)
        self.assertEqual(ep.meta["repaired_in_update"], 2)
        self.assertTrue(ep.meta["repair_entered_estimator"])
        self.assertEqual(ep.meta["update_receipt_source"], "status")

    def test_without_an_update_receipt_the_driver_does_not_claim_entry(self):
        caps = HostCapabilities({"commands": dict(
            {k: "YES" for k in HostCapabilities.KEYS}, set_state="NO")})
        loop, ep = self._loop(caps)
        loop.cp.reprocess_ack = "OK reprocess replay_suffix=0 replay_within_end=2 repaired_fed=2"
        loop.cp.status_ack = "OK status valid=1 repair_received=2 repair_applied=2"
        loop.decide(1_500, "test")
        self.assertEqual(ep.meta["repaired_fed"], 2)
        self.assertIsNone(ep.meta["repaired_in_update"])
        self.assertIsNone(ep.meta["repair_entered_estimator"])
        self.assertEqual(ep.meta["repair_entered_estimator_reason"], "NO_UPDATE_RECEIPT")

if __name__ == "__main__":
    unittest.main()



class DeferredAckTest(unittest.TestCase):
    """An armed ack is not an applied ack; the client must keep the command in flight."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_deferred_ack_does_not_complete_the_command(self):
        client = CheckpointClient(self.dir)
        event = {"command": "snapshot", "wall": 0.0}
        done, line = client._classify_ack(event, "snapshot", "OK snapshot deferred stamp=123")
        self.assertFalse(done)
        self.assertTrue(event["armed"])
        self.assertEqual(event["armed_ack"], "OK snapshot deferred stamp=123")

    def test_applied_ack_completes_the_command(self):
        client = CheckpointClient(self.dir)
        event = {"command": "snapshot", "wall": 0.0, "armed_ack": "OK snapshot deferred stamp=1"}
        done, line = client._classify_ack(
            event, "snapshot", "OK snapshot applied stamp=100 frame=9 map_points=42")
        self.assertTrue(done)
        self.assertIn("applied", line)

    def test_poll_keeps_a_deferred_command_pending(self):
        client = CheckpointClient(self.dir)
        with open(os.path.join(self.dir, "ack"), "w", encoding="utf-8") as fh:
            fh.write("OK hold deferred stamp=1711547997000000000\n")
        from slam_recovery.ros.recovery_node import CheckpointClient as _CP
        ev = {"command": "hold", "wall": 0.0}
        client._pending.append(ev)
        self.assertIsNone(client.poll())
        self.assertEqual(len(client._pending), 1)
        self.assertTrue(ev["armed"])

    def test_a_command_that_is_never_applied_is_not_counted(self):
        client = CheckpointClient(self.dir, ack_timeout_s=0.2)
        ev = client.hold(1)                     # writing the command removes any stale ack
        with open(os.path.join(self.dir, "ack"), "w", encoding="utf-8") as fh:
            fh.write("OK hold deferred stamp=1\n")
        got = client.collect(timeout_s=0.3)
        self.assertFalse(got["ok"])
        self.assertEqual(got["error"], "deferred_not_applied")
        self.assertEqual(client.holds, 0)


if __name__ == "__main__":
    unittest.main()
