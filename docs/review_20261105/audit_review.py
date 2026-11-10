"""Bounded, bag-free reproductions of review findings; production code is unchanged."""
from pathlib import Path
import copy
import hashlib
import io
import json
import platform
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import numpy as np
from slam_recovery.core import CandidateMap, TangentFrame
from slam_recovery.quarantine import TrustedMapTransactionManager
from slam_recovery.health.detector import analyze_decoupled_information
from slam_recovery.tests.test_atomic_commit import _make_delta
from slam_recovery.validation import compute_disjoint_holdout_point_to_plane_nis


def quarantine(m):
    return m.trigger_quarantine(int(10e9), int(14e9), np.array([0,0,0,1,0,0]),
                                np.eye(6), 1.0,
        weak_direction_frame=TangentFrame("body", "rot_trans", "probe"),
        info_before_frame=TangentFrame("body", "rot_trans", "probe"),
                                )


def main():
    stream = io.StringIO()
    suite = unittest.defaultTestLoader.discover(str(ROOT / 'slam_recovery/tests'))
    test = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    out = Path(__file__).parent
    (out / 'upstream_tests.txt').write_text(stream.getvalue(), encoding='utf-8')
    observations = []

    m = TrustedMapTransactionManager()
    m.trusted_poses[1] = np.eye(4)
    ck = m.create_checkpoint(100)
    changed = copy.deepcopy(ck)
    changed.keyframe_poses[99] = changed.keyframe_poses.pop(1)
    observations.append(dict(id='R1', issue='checkpoint_key_identity_not_hashed',
        reproduced=ck.compute_hash() == changed.compute_hash(),
        original_keys=list(ck.keyframe_poses), mutated_keys=list(changed.keyframe_poses)))

    m = TrustedMapTransactionManager()
    for t in range(8, 15):
        m.step_healthy(_make_delta(t, t, t if t < 10 else 100 + t))
    quarantine(m)
    late = [k for k in m.trusted_poses if k >= 10]
    observations.append(dict(id='R2', issue='late_onset_does_not_remove_already_promoted_poses',
        reproduced=bool(late), fault_onset_sec=10, alarm_sec=14, delay_sec=2,
        remaining_fault_keyframes=late, checkpoint_timestamp_sec=8,
        checkpoint_contains_future_keyframes=sorted(m.active_quarantine.checkpoint.keyframe_poses)))

    m = TrustedMapTransactionManager()
    quarantine(m)
    pose = np.eye(4); pose[0,3] = np.nan
    c = CandidateMap('nonfinite_pose', m.trusted_version, {42:pose}, np.eye(6)*100,
                     np.eye(6)*0.01, 0.1,
        info_after_frame=TangentFrame("body", "rot_trans", "probe"),
                     )
    rep = m.validate_and_resolve(c)
    observations.append(dict(id='R3', issue='nonfinite_pose_can_be_committed',
        reproduced=rep.accepted and not np.isfinite(m.trusted_poses.get(42, np.eye(4))).all(),
        gate_accepted=rep.accepted, committed_pose_finite=bool(np.isfinite(m.trusted_poses.get(42, np.eye(4))).all())))

    fim = np.block([[np.eye(3)*50, np.eye(3)*49.999],
                    [np.eye(3)*49.999, np.eye(3)*50]])
    mr, mt, _, _, v = analyze_decoupled_information(fim, np.linalg.inv(fim))
    observations.append(dict(id='R4', issue='block_spectrum_misses_coupled_weak_direction',
        reproduced=min(mr,mt) > 25 and np.linalg.eigvalsh(fim)[0] < 0.01,
        rotation_block_min=mr, translation_block_min=mt,
        full_6d_min=float(np.linalg.eigvalsh(fim)[0]), chosen_projection=float(v@fim@v)))

    rng = np.random.default_rng(17)
    train = np.column_stack([rng.uniform(-1,1,(120,2)), np.zeros(120)])
    hold = np.column_stack([rng.uniform(-.5,.5,(160,2)), np.r_[np.full(40,.001),np.full(120,3.)]])
    nis = compute_disjoint_holdout_point_to_plane_nis(train,hold)
    observations.append(dict(id='R5', issue='holdout_large_residuals_disappear_without_coverage_gate',
        reproduced=nis < 2.5, returned_nis=nis, rejected_geometry_fraction=0.75,
        all_point_normalized_squared_residual=float(np.mean((hold[:,2]/.08)**2))))

    m = TrustedMapTransactionManager()
    m.trusted_poses[1] = np.eye(4); m.trusted_factors=[10]
    quarantine(m)
    c = CandidateMap('pose_only', m.trusted_version, {2:np.eye(4)}, np.eye(6)*100,
                     np.eye(6)*.01, .1,
        info_after_frame=TangentFrame("body", "rot_trans", "probe"),
                     )
    rep = m.validate_and_resolve(c)
    observations.append(dict(id='R6', issue='commit_updates_poses_without_candidate_factor_or_bias_transaction',
        reproduced=rep.accepted and m.trusted_factors == [10],
        pose_keys=sorted(m.trusted_poses), factor_ids=m.trusted_factors,
        note='API limitation: CandidateMap has no replacement factor/bias/covariance payload.'))

    sources=['slam_recovery/core.py','slam_recovery/quarantine/manager.py',
             'slam_recovery/health/detector.py','slam_recovery/validation/fim_and_holdout.py']
    result=dict(reviewed_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        python=platform.python_version(), numpy=np.__version__,
        original_tests=dict(run=test.testsRun, failures=len(test.failures),errors=len(test.errors),passed=test.wasSuccessful()),
        observations=observations,
        source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},
        scope='Synthetic counterexamples only. No dataset replay, no original metrics recomputation, no production fix.')
    encoded = json.dumps(result,ensure_ascii=False,indent=2,default=lambda x: x.item())
    (out/'audit_results.json').write_text(encoded,encoding='utf-8')
    print(encoded)


if __name__ == '__main__':
    main()
