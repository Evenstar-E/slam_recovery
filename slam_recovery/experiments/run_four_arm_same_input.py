#!/usr/bin/env python3
"""Same-input four-arm map-recovery experiment (reviewer item 5).

One input, one keyframe set, one candidate pose set; only the *admission policy* differs.

  A0  host-native mapping      admit every keyframe (no quarantine, no gate)
  A1  quarantine only          admit only keyframes before the onset
  A2  unconditional admission  quarantine, then admit the candidate in full
  A3  verified admission       quarantine, then admit only the verified prefix

Data are archived, not re-run:
  scans  /tmp/fastlivo/hall01_inj43.bag       (/velodyne_points, 88% occlusion at 4.30 m)
  poses  /tmp/fastlivo/res_hall01_inj_05x.bag (/aft_mapped_to_init, FAST-LIVO2 on that bag)
Provenance: ARCHIVED_REAL_HOST_POSES + INJECTION_SCANS.

Poses are full SE(3). The scan lives in the body frame, so the recorded orientation has to be
applied; dropping it smears walls by 2*r*sin(theta/2) as soon as the platform yaws, and the
contamination figures then measure that smear rather than map pollution. `--ignore-rotation`
reproduces the earlier rotation-free numbers for comparison only.

Candidate = the host's own quarantined poses. Incumbent -- what "doing nothing" looks like --
is a constant-velocity extrapolation of the last pre-onset keyframes, so the paired test asks
"is the candidate better than no repair" instead of comparing the candidate with itself.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np
import rosbag

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from slam_recovery.quarantine import TrustedMapTransactionManager
from slam_recovery.sim.transaction_manager_node import OnlineRecoveryTransactionNode
from slam_recovery.experiments.evaluation import (
    associate_trajectories,
    load_tum_trajectory_se3,
    quat_xyzw_to_rot,
    umeyama_se3_align,
)

DEFAULT_INJ_SCANS = "/tmp/fastlivo/hall01_inj43.bag"
DEFAULT_INJ_POSES = "/tmp/fastlivo/res_hall01_inj_05x.bag"
DEFAULT_CLN_SCANS = "/tmp/fastlivo/hall01_100_160.bag"
DEFAULT_CLN_POSES = "/tmp/fastlivo/res_hall01_clean_05x.bag"
DEFAULT_GT = "/home/R26534/M2DGR/GT/hall_01.txt"

ONSET_REL = 20.0          # injection [120, 140] s of sequence time; window starts at 100 s
INJ_END_REL = 40.0
VOXEL = 0.10
SURF_TOL = 0.15
MAX_KF_POINTS = 15000
NEAR_DT = 0.020
MAX_GAP = 0.075
EXTRAP_FRAMES = 5

DT = np.dtype({
    "names": ["x", "y", "z", "intensity", "time", "ring"],
    "formats": ["<f4", "<f4", "<f4", "<f4", "<f4", "<u2"],
    "offsets": [0, 4, 8, 12, 16, 20],
    "itemsize": 24,
})

_NEIGHBOURS = [
    (dx, dy, dz)
    for dx in (-2, -1, 0, 1, 2)
    for dy in (-2, -1, 0, 1, 2)
    for dz in (-2, -1, 0, 1, 2)
    if dx * dx + dy * dy + dz * dz <= 2
]


def slerp(q0, q1, a):
    d = float(np.dot(q0, q1))
    if d < 0.0:
        q1 = -q1
        d = -d
    if d > 0.9995:
        q = q0 + a * (q1 - q0)
    else:
        th = np.arccos(np.clip(d, -1.0, 1.0))
        q = (np.sin((1.0 - a) * th) * q0 + np.sin(a * th) * q1) / np.sin(th)
    return q / np.linalg.norm(q)


def load_poses(path, topic="/aft_mapped_to_init"):
    ts, xyz, quat = [], [], []
    with rosbag.Bag(path, "r") as b:
        for _, m, _ in b.read_messages(topics=[topic]):
            ts.append(m.header.stamp.to_sec())
            p = m.pose.pose.position
            q = m.pose.pose.orientation
            xyz.append([p.x, p.y, p.z])
            quat.append([q.x, q.y, q.z, q.w])
    t = np.asarray(ts)
    o = np.argsort(t)
    return t[o], np.asarray(xyz)[o], np.asarray(quat)[o]


def pose_matrix(xyz, quat):
    T = np.eye(4)
    T[:3, :3] = quat_xyzw_to_rot(quat)
    T[:3, 3] = xyz
    return T


def load_scans(path, topic="/velodyne_points"):
    out = []
    with rosbag.Bag(path, "r") as b:
        for _, m, _ in b.read_messages(topics=[topic]):
            a = np.frombuffer(m.data, dtype=DT)
            p = np.column_stack([a["x"], a["y"], a["z"]]).astype(np.float64)
            r = np.linalg.norm(p, axis=1)
            p = p[(r > 0.5) & (r < 30.0)]
            if len(p) > MAX_KF_POINTS:
                p = p[:: max(1, len(p) // MAX_KF_POINTS)][:MAX_KF_POINTS]
            out.append((m.header.stamp.to_sec(), p))
    out.sort(key=lambda kv: kv[0])
    return out


def _ranges(vals):
    if not vals:
        return []
    vals = sorted(vals)
    out, lo, prev = [], vals[0], vals[0]
    for v in vals[1:]:
        if v - prev > 1.0:
            out.append([lo, prev])
            lo = v
        prev = v
    out.append([lo, prev])
    return out


def pair_keyframes(scan_path, pose_path, ignore_rotation):
    pts = load_scans(scan_path)
    pt, px, pq = load_poses(pose_path)

    iv = np.diff(pt)
    pose_stats = {
        "poses": int(len(pt)),
        "interval_ms_p50": round(float(np.percentile(iv, 50)) * 1e3, 2),
        "interval_ms_p95": round(float(np.percentile(iv, 95)) * 1e3, 2),
        "interval_ms_max": round(float(iv.max()) * 1e3, 2),
        "gaps_over_50ms": int(np.sum(iv > MAX_GAP)),
    }

    kfs, dts, interp, dropped, drop_rel = [], [], 0, 0, []
    t_start = pts[0][0]
    for ts, p in pts:
        j = int(np.searchsorted(pt, ts))
        near = [i for i in (j - 1, j) if 0 <= i < len(pt)]
        best = min(near, key=lambda i: abs(pt[i] - ts)) if near else None
        if best is not None and abs(pt[best] - ts) <= NEAR_DT:
            xyz, q = px[best], pq[best]
            dts.append(abs(pt[best] - ts))
            flag = "NEAREST"
        elif 0 < j < len(pt) and (pt[j] - pt[j - 1]) <= MAX_GAP:
            a = (ts - pt[j - 1]) / (pt[j] - pt[j - 1])
            xyz = (1 - a) * px[j - 1] + a * px[j]
            q = slerp(pq[j - 1], pq[j], float(a))
            interp += 1
            dts.append(0.0)
            flag = "INTERPOLATED_FROM_ARCHIVED_ODOMETRY"
        else:
            dropped += 1
            drop_rel.append(round(float(ts - t_start), 2))
            continue
        if ignore_rotation:
            T = np.eye(4)
            T[:3, 3] = xyz
        else:
            T = pose_matrix(xyz, q)
        kfs.append({"ts": ts, "rel": ts - t_start, "pts": p, "pose": T, "pose_source": flag})

    d = np.asarray(dts) if dts else np.zeros(1)
    stats = {
        "scans": len(pts),
        "paired": len(kfs),
        "interpolated": interp,
        "dropped": dropped,
        "dt_ms_p50": round(float(np.percentile(d, 50)) * 1e3, 3),
        "dt_ms_p95": round(float(np.percentile(d, 95)) * 1e3, 3),
        "dt_ms_max": round(float(d.max()) * 1e3, 3),
        "dropped_time_ranges_rel_sec": _ranges(drop_rel),
        "pose_stream": pose_stats,
    }
    return kfs, stats


def world_points(kf):
    T = kf["pose"]
    return kf["pts"] @ T[:3, :3].T + T[:3, 3]


def to_gt_frame(kfs, R, t):
    out = []
    for k in kfs:
        w = world_points(k)
        out.append(w @ R.T + t)
    return np.vstack(out) if out else np.zeros((0, 3))



class NearestGrid:
    """Uniform-grid nearest-neighbour search (no scipy on this machine).

    Cells are 0.25 m; queries expand ring by ring and stop as soon as the next ring cannot beat
    the best distance found, so the returned distance is exact up to the search radius.
    """

    def __init__(self, points, cell=0.40):
        self.cell = float(cell)
        self.grid = {}
        self.pts = np.asarray(points, dtype=np.float64)
        if len(self.pts) == 0:
            return
        keys = np.floor(self.pts / self.cell).astype(np.int64)
        for i, k in enumerate(map(tuple, keys.tolist())):
            self.grid.setdefault(k, []).append(i)

    def query(self, q, max_r=2.0):
        out = np.full(len(q), np.inf)
        if not self.grid:
            return out
        c = self.cell
        kmax = int(np.ceil(max_r / c))
        qk = np.floor(np.asarray(q, dtype=np.float64) / c).astype(np.int64)
        groups = {}
        for i, key in enumerate(map(tuple, qk.tolist())):
            groups.setdefault(key, []).append(i)
        for key, members in groups.items():
          qq = np.asarray(q, dtype=np.float64)[members]
          for i in members:
            best = np.inf
            for r in range(0, kmax + 1):
                if r > 0 and (r - 1) * c > best:
                    break
                found = False
                for dx in range(-r, r + 1):
                    for dy in range(-r, r + 1):
                        for dz in range(-r, r + 1):
                            if max(abs(dx), abs(dy), abs(dz)) != r:
                                continue
                            idx = self.grid.get((key[0] + dx, key[1] + dy, key[2] + dz))
                            if not idx:
                                continue
                            found = True
                            d = np.linalg.norm(self.pts[idx] - q[i], axis=1)
                            m = float(d.min())
                            if m < best:
                                best = m
                if found and best <= r * c:
                    break
            out[i] = best
        return out


def distance_stats(d, thresholds=(0.25, 0.5, 1.0, 2.0)):
    if len(d) == 0:
        return {}
    return {
        "n_points": int(len(d)),
        "median_m": round(float(np.median(d)), 4),
        "p90_m": round(float(np.percentile(d, 90)), 4),
        "p99_m": round(float(np.percentile(d, 99)), 4),
        **{f"tail_over_{t}m": round(float(np.mean(d > t)), 4) for t in thresholds},
    }


def bootstrap_tail(kf_dists, thresholds=(0.25, 0.5, 1.0, 2.0), n_boot=1000, seed=0):
    """Resample KEYFRAMES, not points: points inside a keyframe are highly correlated."""
    if not kf_dists:
        return {}
    rng = np.random.default_rng(seed)
    n = len(kf_dists)
    out = {}
    for t in thresholds:
        per = np.asarray([float(np.mean(d > t)) for d in kf_dists])
        idx = rng.integers(0, n, size=(n_boot, n))
        boot = per[idx].mean(axis=1)
        out[f"tail_over_{t}m"] = {
            "mean": round(float(per.mean()), 4),
            "ci95": [round(float(np.percentile(boot, 2.5)), 4),
                     round(float(np.percentile(boot, 97.5)), 4)],
        }
    return out


def voxels(points):
    if len(points) == 0:
        return set()
    q = np.floor(points / VOXEL).astype(np.int64)
    return set(map(tuple, q.tolist()))


def supported_mask(vox_keys, surf_keys):
    if not vox_keys:
        return np.zeros(0, dtype=bool)
    keys = sorted(vox_keys)
    out = np.zeros(len(keys), dtype=bool)
    for i, (x, y, z) in enumerate(keys):
        for dx, dy, dz in _NEIGHBOURS:
            if (x + dx, y + dy, z + dz) in surf_keys:
                out[i] = True
                break
    return out


def unsupported_fraction(vox_keys, surf_keys):
    if not vox_keys:
        return None
    return float(np.mean(~supported_mask(vox_keys, surf_keys)))


def coverage_recall(surf_keys, map_keys):
    if not surf_keys:
        return float("nan")
    return sum(1 for k in surf_keys if k in map_keys) / float(len(surf_keys))


def ate(pred_ts, pred_xyz, gt_ts, gt_xyz, R, t):
    m_ts, m_e, m_g = associate_trajectories(pred_ts, pred_xyz, gt_ts, gt_xyz, 0.05)
    if len(m_e) < 3:
        return float("nan"), 0
    err = np.linalg.norm(m_e @ R.T + t - m_g, axis=1)
    return float(np.sqrt(np.mean(err ** 2))), int(len(err))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--ignore-rotation", action="store_true",
                    help="reproduce the earlier rotation-free numbers for comparison only")
    args = ap.parse_args()

    out_manifest = args.out or os.path.join(
        _REPO_ROOT, "slam_recovery", "experiments", "manifests", "four_arm_same_input_benchmark.json")
    os.makedirs(os.path.dirname(out_manifest), exist_ok=True)

    print("loading injected run ...")
    inj_kfs, inj_stats = pair_keyframes(DEFAULT_INJ_SCANS, DEFAULT_INJ_POSES, args.ignore_rotation)
    print(f"  paired={inj_stats['paired']} interp={inj_stats['interpolated']} dropped={inj_stats['dropped']}")
    print(f"  pose stream {inj_stats['pose_stream']}")

    print("loading clean run (scoring surface only) ...")
    cln_kfs, cln_stats = pair_keyframes(DEFAULT_CLN_SCANS, DEFAULT_CLN_POSES, args.ignore_rotation)
    print(f"  paired={cln_stats['paired']} interp={cln_stats['interpolated']} dropped={cln_stats['dropped']}")

    # The two runs each initialise their own world frame, so their maps cannot be compared
    # voxel-for-voxel until one is carried into the other's frame. A single rigid transform is
    # fitted on the PRE-ONSET overlap only, so it is identical for all four arms and cannot
    # favour any admission policy.
    ts_gt_all, xyz_gt_all, _ = load_tum_trajectory_se3(DEFAULT_GT)

    pre_inj = [k for k in inj_kfs if k["rel"] < ONSET_REL]
    pre_inj_ts = np.asarray([k["ts"] for k in pre_inj])
    pre_inj_xyz = np.asarray([k["pose"][:3, 3] for k in pre_inj])
    cln_ts_all = np.asarray([k["ts"] for k in cln_kfs])
    cln_xyz_all = np.asarray([k["pose"][:3, 3] for k in cln_kfs])
    m_ts, m_i, m_c = associate_trajectories(pre_inj_ts, pre_inj_xyz, cln_ts_all, cln_xyz_all, 0.05)
    R_ic, t_ic, _ = umeyama_se3_align(m_i, m_c, with_scale=False)

    def _align_residuals(kfs):
        """Position residual of the aligned injected trajectory against the clean one, by window."""
        ts_a = np.asarray([k["ts"] for k in kfs])
        xyz_a = np.asarray([k["pose"][:3, 3] for k in kfs])
        mt, mi, mc = associate_trajectories(ts_a, xyz_a, cln_ts_all, cln_xyz_all, 0.05)
        if len(mi) < 3:
            return {}
        err = np.linalg.norm(mi @ R_ic.T + t_ic - mc, axis=1)
        rel = mt - inj_kfs[0]["ts"]
        out = {}
        for lo, hi in ((0, ONSET_REL), (ONSET_REL, INJ_END_REL), (INJ_END_REL, 1e9)):
            m = (rel >= lo) & (rel < hi)
            if m.sum():
                out[f"[{lo:g},{hi if hi < 1e8 else 60:g})s"] = {
                    "n": int(m.sum()),
                    "mean_m": round(float(np.mean(err[m])), 4),
                    "p95_m": round(float(np.percentile(err[m], 95)), 4),
                    "max_m": round(float(np.max(err[m])), 4),
                }
        return out

    align_residuals = _align_residuals(inj_kfs)

    proxy_pts_all = to_gt_frame(cln_kfs, np.eye(3), np.zeros(3))
    if len(proxy_pts_all) > 120000:
        proxy_pts_all = proxy_pts_all[:: max(1, len(proxy_pts_all) // 120000)][:120000]
    proxy_grid = NearestGrid(proxy_pts_all)
    proxy_surface = voxels(to_gt_frame(cln_kfs, np.eye(3), np.zeros(3)))

    def _half_cloud(kfs, parity):
        return to_gt_frame(kfs, np.eye(3), np.zeros(3))[parity::2]

    surf_even = voxels(_half_cloud(cln_kfs, 0))
    surf_odd = voxels(_half_cloud(cln_kfs, 1))

    def _selfcal(surf, other_map):
        return {
            "unsupported_voxel_fraction": round(float(unsupported_fraction(other_map, surf)), 4),
            "coverage_recall": round(coverage_recall(surf, other_map), 4),
        }

    selfcal = {"builds_from_even_points_scores_odd": _selfcal(surf_even, surf_odd),
               "builds_from_odd_points_scores_even": _selfcal(surf_odd, surf_even)}
    floor_unsup = float(np.mean([v["unsupported_voxel_fraction"] for v in selfcal.values()]))
    floor_cov = float(np.mean([v["coverage_recall"] for v in selfcal.values()]))
    print(f"  proxy floor: unsupported={floor_unsup:.4f} coverage={floor_cov:.4f}")

    # Second, independent floor: score the injected run's own PRE-ONSET map against the aligned
    # clean proxy. This measures the disagreement between two runs that saw identical input, which
    # is the resolution limit for any cross-run comparison.
    pre_aligned = np.vstack([world_points(k) for k in
                             [k for k in inj_kfs if k["rel"] < ONSET_REL]]) @ R_ic.T + t_ic
    pre_vox = voxels(pre_aligned)
    cross_floor = {
        "unsupported_voxel_fraction": round(float(unsupported_fraction(pre_vox, proxy_surface)), 4),
        "coverage_recall": round(coverage_recall(proxy_surface, pre_vox), 4),
        "what": "injected pre-onset map vs aligned clean proxy (identical input, two runs)",
    }
    print(f"  cross-run floor: unsupported={cross_floor['unsupported_voxel_fraction']:.4f} "
          f"coverage={cross_floor['coverage_recall']:.4f}")

    # Leave-one-out check on the interpolator, using real poses as truth. The neighbour gap here
    # is ~2x the pose interval, i.e. wider than MAX_GAP, so this is a conservative upper bound.
    _pt, _px, _pq = load_poses(DEFAULT_INJ_POSES)
    _te, _re = [], []
    for i in range(1, len(_pt) - 1, 7):
        a = (_pt[i] - _pt[i - 1]) / (_pt[i + 1] - _pt[i - 1])
        xyz = (1 - a) * _px[i - 1] + a * _px[i + 1]
        q = slerp(_pq[i - 1], _pq[i + 1], float(a))
        _te.append(float(np.linalg.norm(xyz - _px[i])))
        c = abs(float(np.dot(q, _pq[i])))
        _re.append(float(2 * np.degrees(np.arccos(np.clip(c, -1, 1)))))
    interp_loo = {
        "samples": len(_te),
        "neighbour_gap_ms": round(float(np.median(np.diff(_pt[1:-1:7]))) * 1e3, 1),
        "translation_err_mean_m": round(float(np.mean(_te)), 5),
        "translation_err_max_m": round(float(np.max(_te)), 5),
        "rotation_err_mean_deg": round(float(np.mean(_re)), 4),
        "rotation_err_max_deg": round(float(np.max(_re)), 4),
        "note": "gap exceeds MAX_GAP, so this bounds the interpolator from above",
    }
    print(f"  interp LOO: {interp_loo['translation_err_mean_m']*1000:.2f} mm / "
          f"{interp_loo['rotation_err_mean_deg']:.3f} deg")

    pre = [k for k in inj_kfs if k["rel"] < ONSET_REL]
    quar = [k for k in inj_kfs if k["rel"] >= ONSET_REL]

    tail = pre[-EXTRAP_FRAMES:]
    dt_span = tail[-1]["ts"] - tail[0]["ts"]
    v = (tail[-1]["pose"][:3, 3] - tail[0]["pose"][:3, 3]) / dt_span if dt_span > 1e-6 else np.zeros(3)
    anchor_T = tail[-1]["pose"].copy()
    anchor_t = tail[-1]["ts"]
    incumbent = {}
    for i, k in enumerate(quar):
        T = anchor_T.copy()
        T[:3, 3] = anchor_T[:3, 3] + v * (k["ts"] - anchor_t)
        incumbent[i] = T
    candidate = {i: k["pose"].copy() for i, k in enumerate(quar)}

    ref_pts = np.vstack([world_points(k) for k in pre]) if pre else np.zeros((0, 3))
    if len(ref_pts) > 4000:
        ref_pts = ref_pts[:: max(1, len(ref_pts) // 4000)][:4000]

    node = OnlineRecoveryTransactionNode(confirmation_margin_sec=2.0, voxel_size_m=VOXEL, holdout_stride=5)
    node.committed_map_points = [ref_pts] if len(ref_pts) else []
    node.scan_buffer_body = {i: k["pts"] for i, k in enumerate(quar)}
    node.tx_mgr = TrustedMapTransactionManager(confirmation_margin_ns=int(2.0e9))
    node.tx_mgr.trigger_quarantine(
        int(ONSET_REL * 1e9), int((ONSET_REL + 2.0) * 1e9),
        np.array([0, 0, 0, 1, 0, 0], dtype=np.float64), np.eye(6) * 2.0, 1.2,
    )

    t0 = time.perf_counter()
    report = node.evaluate_and_commit_candidate(
        "four_arm_A3", candidate, incumbent_poses=incumbent, reentry_anchor_pose=np.eye(4))
    a3_runtime = time.perf_counter() - t0
    verified_prefix = sorted(node.tx_mgr.trusted_poses.keys()) if report.accepted else []

    arms = {
        "A0_Host_Native": list(range(len(inj_kfs))),
        "A1_Quarantine_Only": list(range(len(pre))),
        "A2_Unconditional_Admission": list(range(len(inj_kfs))),
        "A3_Verified_Admission": list(range(len(pre))) + [len(pre) + i for i in verified_prefix],
    }

    ts_gt, xyz_gt = ts_gt_all, xyz_gt_all
    m_ts_g, m_e_g, m_g_g = associate_trajectories(
        np.asarray([k["ts"] for k in pre_inj]), pre_inj_xyz, ts_gt_all, xyz_gt_all, 0.05)
    R, t_align, _ = umeyama_se3_align(m_e_g, m_g_g, with_scale=False)

    common_ids = set(arms["A0_Host_Native"])
    for vv in arms.values():
        common_ids &= set(vv)
    common_ids = sorted(common_ids)

    # ---- distance-based metrics (voxel metrics kept as an appendix) --------------------
    def kf_points(i, cap=250):
        w = world_points(inj_kfs[i]) @ R_ic.T + t_ic
        if len(w) > cap:
            w = w[:: max(1, len(w) // cap)][:cap]
        return w

    def per_kf_distances(ids):
        return [proxy_grid.query(kf_points(i), max_r=2.5) for i in ids]

    floor_ids = [i for i in range(len(inj_kfs)) if inj_kfs[i]["rel"] < ONSET_REL]
    floor_d = per_kf_distances(floor_ids)
    floor_flat = np.concatenate(floor_d) if floor_d else np.zeros(0)
    floor_stats = distance_stats(floor_flat)
    floor_boot = bootstrap_tail(floor_d)
    floor_vox = voxels(np.vstack([world_points(inj_kfs[i]) for i in floor_ids]) @ R_ic.T + t_ic)
    floor_vox_unsup = unsupported_fraction(floor_vox, proxy_surface)
    floor_vox_cov = coverage_recall(proxy_surface, floor_vox)
    print(f"  distance floor: median={floor_stats.get('median_m')} "
          f"tail0.5={floor_stats.get('tail_over_0.5m')}")

    cov_q = proxy_pts_all[:: max(1, len(proxy_pts_all) // 40000)][:40000]
    results = {}
    for name, ids in arms.items():
        kd = per_kf_distances(ids)
        flat = np.concatenate(kd) if kd else np.zeros(0)
        stats = distance_stats(flat)
        boot = bootstrap_tail(kd)

        admitted_ts = np.asarray([inj_kfs[i]["ts"] for i in ids])
        admitted_xyz = np.asarray([inj_kfs[i]["pose"][:3, 3] for i in ids])
        ate_adm, n_adm = ate(admitted_ts, admitted_xyz, ts_gt, xyz_gt, R, t_align)
        c_xyz = np.asarray([inj_kfs[i]["pose"][:3, 3] for i in common_ids])
        ate_common, n_common = ate(np.asarray([inj_kfs[i]["ts"] for i in common_ids]), c_xyz,
                                   ts_gt, xyz_gt, R, t_align)

        committed = np.vstack([kf_points(i) for i in ids]) if ids else np.zeros((0, 3))
        cov = {}
        if len(committed):
            g = NearestGrid(committed)
            dd = g.query(cov_q, max_r=2.5)
            cov = {f"covered_within_{t}m": round(float(np.mean(dd <= t)), 4) for t in (0.25, 0.5, 1.0, 2.0)}
            cov["median_m"] = round(float(np.median(dd)), 4)

        results[name] = {
            "admitted_keyframes": len(ids),
            "admitted_quarantined_frames": len([i for i in ids if i >= len(pre)]),
            "deferred_keyframes": len(inj_kfs) - len(ids),
            "admitted_duration_sec": round(float(admitted_ts[-1] - admitted_ts[0]), 2) if len(ids) else 0.0,
            "distance_stats": stats,
            "distance_tail_bootstrap": boot,
            "coverage_sweep": cov,
            "ate_on_common_support_m": round(ate_common, 4) if n_common else None,
            "ate_on_common_support_frames": n_common,
            "ate_on_admitted_set_m": round(ate_adm, 4) if n_adm else None,
            "ate_on_admitted_set_frames": n_adm,
            "clean_interval_keyframes_not_admitted": len(set(range(len(pre))) - set(ids)),
            "appendix_voxel_unsupported": round(float(unsupported_fraction(voxels(committed), proxy_surface)), 4),
            "appendix_voxel_coverage": round(coverage_recall(proxy_surface, voxels(committed)), 4),
            "runtime_sec": round(a3_runtime, 4) if name.startswith("A3") else None,
        }

    manifest = {
        "run_id": "four_arm_same_input_benchmark",
        "provenance": "ARCHIVED_REAL_HOST_POSES + INJECTION_SCANS",
        "provenance_note": (
            "Replays a recorded FAST-LIVO2 run. The poses are archived, not produced for this "
            "experiment; this is not an independent reproduction of the host."),
        "rotation_applied": not args.ignore_rotation,
        "inputs": {
            "injected_scans": DEFAULT_INJ_SCANS, "injected_poses": DEFAULT_INJ_POSES,
            "clean_scans_proxy_only": DEFAULT_CLN_SCANS, "clean_poses_proxy_only": DEFAULT_CLN_POSES,
            "gt_trajectory": DEFAULT_GT,
        },
        "pairing": {"injected": inj_stats, "clean": cln_stats,
                    "near_dt_sec": NEAR_DT, "max_interp_gap_sec": MAX_GAP},
        "protocol": {
            "voxel_m": VOXEL, "surface_tolerance_m": SURF_TOL,
            "onset_rel_sec": ONSET_REL, "injection_end_rel_sec": INJ_END_REL,
            "incumbent_model": "constant-velocity extrapolation of the last pre-onset keyframes",
            "extrap_frames": EXTRAP_FRAMES,
            "alignment": "single SE(3) fitted on the pre-onset keyframes of the host, applied to all arms",
        },
        "reference_surface": {
            "provenance": "REAL_HOST_CLEAN_PROXY",
            "gt_surface_contam_3d": "UNAVAILABLE (no hall_01 GT mesh; M2DGR provides trajectory only)",
            "self_calibration": selfcal,
            "resolution_floor": {
                "within_run_point_split": {
                    "unsupported_voxel_fraction": round(floor_unsup, 4),
                    "coverage_recall": round(floor_cov, 4),
                    "what": "surface sampling noise within one run",
                },
                "across_run_pre_onset": cross_floor,
                "use": "an arm difference must exceed the across-run floor to count as a finding",
            },
        },
        "validation_reference_source": {
            "A0_Host_Native": "none (no gate)",
            "A1_Quarantine_Only": "none (no gate)",
            "A2_Unconditional_Admission": "none (admission is unconditional)",
            "A3_Verified_Admission": "injected_run_pre_onset_keyframes",
        },
        "alignment": {
            "model": "single rigid SE(3), clean<-injected, fitted on the pre-onset overlap only",
            "matched_pre_onset_poses": int(len(m_i)),
            "residual_by_window": align_residuals,
            "note": "identical for every arm, so it cannot favour an admission policy; the post-injection residual grows, which bounds how far the proxy can be trusted downstream",
        },
        "interpolation": interp_loo,
        "gate_result_A3": {
            "accepted": bool(report.accepted),
            "mode": report.mode.value,
            "holdout_nis": round(float(report.holdout_nis), 4),
            "reason": report.reason,
            "evidence_status": getattr(report, "evidence_status", None),
            "paired_test_informative": True,
            "paired_evidence": node.last_paired_evidence,
        },
        "arms": results,
        "caveats": [
            "Candidate is the host's own quarantined trajectory; the archive holds no repaired "
            "candidate for this window, so A3 can only accept or reject the host poses.",
            "Incumbent is a constant-velocity extrapolation, not a per-frame record, so the paired "
            "test asks whether the candidate beats 'no repair', not whether it is optimal.",
            "A0 and A2 write the identical keyframe set and therefore the same map; A2 differs only "
            "in having passed through quarantine before admitting everything.",
            "ATE on the admitted set is confounded by coverage; ate_on_common_support is the "
            "like-for-like number.",
        ],
    }
    with open(out_manifest, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print("\n=== four-arm same-input (archived replay) ===")
    print(f"proxy floor: unsupported={floor_unsup:.4f}  coverage={floor_cov:.4f}")
    print(f"{'arm':30s} {'kf':>4s} {'vox':>9s} {'unsup':>7s} {'cover':>7s} {'ATEcommon':>10s} {'ATEadm':>8s} {'cleanLost':>9s}")
    for k, vv in results.items():
        print(f"{k:30s} {vv['admitted_keyframes']:4d} {vv['appendix_voxel_unsupported']:9d} "
              f"{vv['distance_stats']['tail_over_0.5m']:7.4f} {vv['coverage_sweep'].get('covered_within_0.5m', float('nan')):7.4f} "
              f"{vv['ate_on_common_support_m']:10.4f} {vv['ate_on_admitted_set_m']:8.4f} "
              f"{vv['clean_interval_keyframes_not_admitted']:9d}")
    print(f"\nA3 gate: {report.mode.value} accepted={report.accepted} nis={report.holdout_nis:.3f}")
    print(f"wrote {out_manifest}")


if __name__ == "__main__":
    main()
