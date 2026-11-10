import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, REPO)

import importlib.util  # noqa: E402

spec = importlib.util.spec_from_file_location(
    "fa", os.path.join(REPO, "slam_recovery/experiments/run_four_arm_same_input.py"))
fa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fa)
from probe_three_obs import nis_param  # noqa: E402


REF_CAP = 1500


def cap_stride(pts, n):
    return pts if len(pts) <= n else pts[:: max(1, len(pts) // n)][:n]


inj, _ = fa.pair_keyframes(fa.DEFAULT_INJ_SCANS, fa.DEFAULT_INJ_POSES, False)
cln, _ = fa.pair_keyframes(fa.DEFAULT_CLN_SCANS, fa.DEFAULT_CLN_POSES, False)
st, _en, _ev = fa.detect_onset(fa.DEFAULT_CLN_SCANS, fa.DEFAULT_INJ_SCANS)
pre = [k for k in inj if k["rel"] < st]
quar = [k for k in inj if k["rel"] >= st]          # everything from onset on: 578 - 133 = 445
print(f"pre={len(pre)} quar={len(quar)} (peer protocol: all post-onset frames)", flush=True)

cln_ts_all = np.asarray([k["ts"] for k in cln])
cln_xyz_all = np.asarray([k["pose"][:3, 3] for k in cln])
_mt, m_i, m_c = fa.associate_trajectories(
    np.asarray([k["ts"] for k in pre]), np.asarray([k["pose"][:3, 3] for k in pre]),
    cln_ts_all, cln_xyz_all, 0.05)
R_ic, t_ic, _ = fa.umeyama_se3_align(m_i, m_c, with_scale=False)
T_inv = np.eye(4)
T_inv[:3, :3] = R_ic.T
T_inv[:3, 3] = -R_ic.T @ t_ic

ref_full = np.vstack([fa.world_points(k) for k in pre])
ref = cap_stride(ref_full, REF_CAP)
print(f"reference: {len(ref_full)} -> {len(ref)}", flush=True)

idx_cln = [int(np.argmin(np.abs(cln_ts_all - k["ts"]))) for k in quar]

def world(pts, T):
    return pts @ T[:3, :3].T + T[:3, 3]

rows = {"clean_pose_raw_injected": [], "clean_pose_filtered_injected": [],
        "clean_pose_oracle_clean": [], "host_pose_raw_injected": []}
for fi, (k, j) in enumerate(zip(quar, idx_cln)):
    T = T_inv @ cln[j]["pose"]
    raw = k["pts"]
    rng = np.linalg.norm(raw, axis=1)
    keep = ~((rng >= 4.0) & (rng <= 4.6))
    rows["clean_pose_raw_injected"].append(nis_param(ref, world(raw, T))[0])
    rows["clean_pose_filtered_injected"].append(nis_param(ref, world(raw[keep], T))[0])
    rows["clean_pose_oracle_clean"].append(nis_param(ref, world(cln[j]["pts"], T))[0])
    rows["host_pose_raw_injected"].append(nis_param(ref, world(raw, k["pose"]))[0])
    if fi % 100 == 0:
        print(f"  frame {fi}/{len(quar)}", flush=True)

print(f"\n{'observation':32s} {'NIS median':>10s} {'NIS mean':>10s} {'eq. residual m':>15s}")
for name, vals in rows.items():
    v = np.asarray([x for x in vals if np.isfinite(x)])
    med = float(np.median(v))
    print(f"{name:32s} {med:10.1f} {float(np.mean(v)):10.1f} {0.12*np.sqrt(med):15.2f}")
