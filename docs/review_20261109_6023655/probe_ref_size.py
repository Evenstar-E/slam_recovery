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



def cap(pts, n):
    if len(pts) <= n:
        return pts
    return pts[:: max(1, len(pts) // n)][:n]


inj, _ = fa.pair_keyframes(fa.DEFAULT_INJ_SCANS, fa.DEFAULT_INJ_POSES, False)
cln, _ = fa.pair_keyframes(fa.DEFAULT_CLN_SCANS, fa.DEFAULT_CLN_POSES, False)
st, _en, _ev = fa.detect_onset(fa.DEFAULT_CLN_SCANS, fa.DEFAULT_INJ_SCANS)
pre = [k for k in inj if k["rel"] < st]
quar = [k for k in inj if st <= k["rel"] <= _en]

cln_ts_all = np.asarray([k["ts"] for k in cln])
cln_xyz_all = np.asarray([k["pose"][:3, 3] for k in cln])
_mt, m_i, m_c = fa.associate_trajectories(
    np.asarray([k["ts"] for k in pre]), np.asarray([k["pose"][:3, 3] for k in pre]),
    cln_ts_all, cln_xyz_all, 0.05)
R_ic, t_ic, _ = fa.umeyama_se3_align(m_i, m_c, with_scale=False)
T_inv = np.eye(4)
T_inv[:3, :3] = R_ic.T
T_inv[:3, 3] = -R_ic.T @ t_ic

ref_pts = np.vstack([fa.world_points(k) for k in pre])
idx_cln = [int(np.argmin(np.abs(cln_ts_all - k["ts"]))) for k in quar]

frames = list(range(0, len(quar), max(1, len(quar) // 12)))[:12]
print(f"ref_pts={len(ref_pts)} testing {len(frames)} frames", flush=True)

for n_cap in (1500, 5000, 20000, 100000, len(ref_pts)):
    train = cap(ref_pts, n_cap)
    row = {}
    for name in ("raw_injected", "oracle_clean"):
        vals = []
        for fi in frames:
            k, j = quar[fi], idx_cln[fi]
            T = T_inv @ cln[j]["pose"]
            pts = k["pts"] if name == "raw_injected" else cln[j]["pts"]
            w = pts @ T[:3, :3].T + T[:3, 3]
            if len(w) == 0:
                continue
            vals.append(nis_param(train, w)[0])
        row[name] = round(float(np.mean(vals)), 2) if vals else None
    print(f"train_cap={n_cap:>8d}  raw={row['raw_injected']:>10}  clean={row['oracle_clean']:>10}",
          flush=True)
