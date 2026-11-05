"""Bounded review probes. Writes only evidence files beside this script.

These probes reproduce defects, not SLAM recovery success. No bag, ROS or GPU.
P9 is exercised with an explicitly synthetic input fixture and a zero-alarm
inference stub to check metric accounting, not to evaluate a real model.
"""
from __future__ import annotations

import ast
import dataclasses
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import traceback
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

OUT = Path(__file__).resolve().parent
REPO = OUT.parents[1]
sys.path.insert(0, str(REPO))
from slam_recovery.core import CandidateMap, DegeneracyType, HealthWindow, RecoveryState
from slam_recovery.quarantine import TrustedMapTransactionManager
from slam_recovery.tests.test_atomic_commit import _make_delta
from slam_recovery.diagnosis import PhysicsGuidedCausalTransformer
from slam_recovery.sim.transaction_manager_node import OnlineRecoveryTransactionNode
from slam_recovery.sim.run_s1_s2_simulation_experiments import Arena3DMeshGroundTruth
from slam_recovery.experiments.evaluation.trajectory_eval import evaluate_rotation_ate_rpe_deg


def quarantine(m, onset=10., now=14.):
    return m.trigger_quarantine(int(onset*1e9), int(now*1e9),
                               np.array([0.,0,0,1,0,0]), np.eye(6), 1.)


def candidate(m, **kw):
    args = dict(candidate_id="review_probe", parent_map_version=m.trusted_version,
                repaired_poses={42: np.eye(4)}, info_after_6x6=np.eye(6)*100,
                cov_after_6x6=np.eye(6)*.01, holdout_nis=.1)
    args.update(kw)
    return CandidateMap(**args)


def nominal_window(i=0):
    return HealthWindow(int(i*.2e9), int((i+1)*.2e9), 45., 60., 1e-4, 1e-3,
                        np.array([0.,0,0,1,0,0]), 1., 1.4, 0., .8, .8, 0., .5, .01, .04)


def late_same_key():
    m = TrustedMapTransactionManager(confirmation_margin_ns=0)
    m.step_healthy(_make_delta(1., 1, 1.))
    m.step_healthy(_make_delta(3., 1, 30.))
    quarantine(m, 2., 6.)
    return dict(defect_reproduced=1 not in m.trusted_poses,
                expected_healthy_pose_x=1., actual_pose_present=1 in m.trusted_poses)


def all_revoked_bias():
    m = TrustedMapTransactionManager(confirmation_margin_ns=0)
    d = _make_delta(1., 1, 10.)
    d.bias_acc[:] = .7
    m.step_healthy(d)
    quarantine(m, .5, 6.)
    return dict(defect_reproduced=bool(np.any(m.trusted_bias_acc != 0)),
                remaining_pose_count=len(m.trusted_poses), expected_bias=[0,0,0],
                actual_bias=m.trusted_bias_acc.tolist())


def unsafe_candidate_fields():
    m = TrustedMapTransactionManager()
    quarantine(m)
    r = m.validate_and_resolve(candidate(m, repaired_bias_acc=np.array([np.nan,0,0])))
    nan_accepted = bool(r.accepted and np.isnan(m.trusted_bias_acc).any())
    m2 = TrustedMapTransactionManager()
    quarantine(m2)
    r2 = m2.validate_and_resolve(candidate(m2, repaired_poses={42:np.eye(2)}))
    return dict(defect_reproduced=nan_accepted and r2.accepted,
                nonfinite_bias_committed=nan_accepted, invalid_pose_shape_committed=list(m2.trusted_poses[42].shape))


def absent_validation_defaults():
    m = TrustedMapTransactionManager()
    quarantine(m)
    c = candidate(m, wilson_lower_bound=0., reentry_pos_jump_m=99.)
    r = m.validate_and_resolve(c)
    return dict(defect_reproduced=r.accepted, accepted=r.accepted,
                paired_benefit_approved_default=c.paired_benefit_approved,
                wilson_lower_bound=c.wilson_lower_bound, reentry_pos_jump_m=c.reentry_pos_jump_m,
                claimed_reason=r.reason)


def voxel_rollback_divergence():
    n = OnlineRecoveryTransactionNode(confirmation_margin_sec=2.)
    # Explicit controlled health decisions isolate transaction bookkeeping.
    decisions = [SimpleNamespace(state=RecoveryState.HEALTHY)]*3 + [
        SimpleNamespace(state=RecoveryState.QUARANTINED, estimated_onset_ns=int(6e9))]
    fixed_fim = (np.eye(6)*100., np.eye(6)*.01, 100., 100., np.array([0.,0,0,1,0,0]))
    cloud = np.array([[0.,0,0], [.01,0,0], [.02,0,0], [.03,0,0]])
    with patch.object(n.detector, "step", side_effect=decisions), patch(
        "slam_recovery.sim.transaction_manager_node.compute_6dof_point_to_plane_fim", return_value=fixed_fim):
        for k, t in enumerate([1.,4.,7.,10.], start=1):
            pose = np.eye(4)
            pose[0,3] = 100. if k == 2 else float(k)
            n.step_frame(k, int(t*1e9), pose, cloud, nis_value=1.)
    leaked_voxels = [v for v,owner in n.voxel_store.items() if owner == 2]
    return dict(defect_reproduced=2 not in n.tx_mgr.trusted_poses and bool(leaked_voxels),
                revoked_pose_present=2 in n.tx_mgr.trusted_poses,
                revoked_voxels_still_present=len(leaked_voxels),
                revoked_points_in_validation_reference=bool((n.get_trusted_map_points()[:,0] == 100.).any()))


def incomplete_model_hash():
    m = PhysicsGuidedCausalTransformer()
    m.is_trained = True
    m.W_act[:] = 0.
    def score(bias):
        m.b_act = bias
        m.reset_stream()
        for i in range(10):
            out = m.step_inference(nominal_window(i))
        return out.active_prob, out.used_analytical_fallback, m.weights_sha256()
    a, fa, ha = score(-20.)
    b, fb, hb = score(20.)
    return dict(defect_reproduced=ha==hb and a<.01 and b>.99 and not fa and not fb,
                hash_unchanged=ha==hb, probability_before=a, probability_after=b, hash=ha)


def missing_orientation_fabricates_zero():
    ts=np.arange(40)*.1
    xyz=np.zeros((40,3)); missing=np.zeros((40,4))
    r=evaluate_rotation_ate_rpe_deg(ts,xyz,missing,ts,xyz,missing)
    return dict(defect_reproduced=all(v == 0. for v in r.values()),
                expected="UNAVAILABLE: neither estimate nor reference orientation exists", actual=r)


def mesh_outside_bounds():
    p=np.array([[1000.,3.,1000.]])
    d=Arena3DMeshGroundTruth().compute_distance_to_gt_mesh(p)
    return dict(defect_reproduced=float(d[0]) == 0.,
                point=p[0].tolist(), reported_distance_m=float(d[0]),
                declared_arena_size_m=[40,25], expected="point outside finite arena cannot lie on its wall")


def p9_no_alarm_still_perfect_recall():
    source=REPO/"slam_recovery/experiments/run_identifiability_and_transformer_real_bags.py"
    tree=ast.parse(source.read_text(encoding="utf-8"))
    fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=="evaluate_cross_sequence_causal_transformer")
    module=ast.Module(body=[fn],type_ignores=[])
    ast.fix_missing_locations(module)
    def fixture(scans, fault_type, onset_idx, end_idx, ramp_steps, seed):
        n=40
        wins=[nominal_window(i) for i in range(n)]
        cells=[np.zeros((48,10)) for _ in range(n)]
        active=np.array([onset_idx<=i<=end_idx for i in range(n)])
        ages=np.array([(i-onset_idx+1)*.2 if active[i] else 0. for i in range(n)])
        return wins,cells,active,ages
    calls=[]
    def no_alarm(self,w,cells):
        calls.append(0)
        return SimpleNamespace(active_prob=0., estimated_age_sec=0.,
                               diagnosis=SimpleNamespace(active_types=[DegeneracyType.UNKNOWN]))
    ns=dict(np=np,time=time,PhysicsGuidedCausalTransformer=PhysicsGuidedCausalTransformer,
            load_real_scans_xyzi=lambda *a,**k:[],build_real_bag_window_stream=fixture)
    exec(compile(module,str(source),"exec"),ns)
    with patch.object(PhysicsGuidedCausalTransformer,"step_inference",no_alarm):
        result=ns[fn.name]()
    reported={k:v["event_detection_recall"] for k,v in result["sequences"].items()}
    return dict(defect_reproduced=all(v==1. for v in reported.values()),
                fixture="synthetic 40 windows; actual evaluation function; inference forced to UNKNOWN/0 probability",
                model_calls=len(calls),actual_model_alarms=sum(calls),reported_recall=reported)


def main():
    upstream=subprocess.run([sys.executable,"-X","utf8","-B","-m","unittest","discover",
                             "-s","slam_recovery/tests","-v"],cwd=REPO,capture_output=True,text=True,encoding="utf-8")
    (OUT/"upstream_tests.txt").write_text(upstream.stdout+upstream.stderr,encoding="utf-8")
    probes={}
    funcs=[late_same_key,all_revoked_bias,unsafe_candidate_fields,absent_validation_defaults,
           voxel_rollback_divergence,incomplete_model_hash,missing_orientation_fabricates_zero,
           mesh_outside_bounds,p9_no_alarm_still_perfect_recall]
    for fn in funcs:
        try:
            probes[fn.__name__]=fn()
        except Exception:
            probes[fn.__name__]={"probe_error":traceback.format_exc(),"defect_reproduced":False}
    result=dict(head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=REPO,text=True).strip(),
                scope="local bounded review probes, not a physical SLAM experiment",
                upstream_returncode=upstream.returncode,probes=probes,
                reproduced_count=sum(bool(r["defect_reproduced"]) for r in probes.values()))
    (OUT/"audit_results.json").write_text(json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False),encoding="utf-8")
    print(json.dumps(result,indent=2,ensure_ascii=False))
    return 0 if upstream.returncode==0 and result["reproduced_count"]==len(funcs) else 1


if __name__=="__main__":
    raise SystemExit(main())
