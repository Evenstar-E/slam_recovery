#!/usr/bin/env python3
"""Same-input four-arm map-recovery experiment (reviewer item 5).

One input, one keyframe set, one candidate pose set; only the *admission policy* differs.

  A0  host-native mapping      admit every keyframe (no quarantine, no gate)
  A1  quarantine only          admit only keyframes before the onset
  A2  unconditional admission  quarantine, then admit the candidate in full
  A3  verified admission       quarantine, then admit only the verified contiguous prefix

Data are archived, not re-run:
  scans  /tmp/fastlivo/hall01_inj43.bag       (/velodyne_points, 88% occlusion at 4.30 m)
  poses  /tmp/fastlivo/res_hall01_inj_05x.bag (/aft_mapped_to_init, FAST-LIVO2 on that bag)
Provenance: ARCHIVED_REAL_HOST_POSES + INJECTION_SCANS. This is a replay of a recorded run,
not an independent reproduction, and every number below carries that caveat.

Scoring surface is the clean run's map (/tmp/fastlivo/hall01_100_160.bag +
res_hall01_clean_05x.bag), provenance REAL_HOST_CLEAN_PROXY. hall_01 has no ground-truth
surface mesh, so gt_surface_contam_3d is UNAVAILABLE; the proxy metrics are named so that
they cannot be mistaken for it, and the proxy is self-calibrated before use.
"""

from __future__ import annotations

import json
import os
import sys
import time

import numpy as np
import rosbag

sys.path.insert(0, "/tmp/wt-fourarm")

from slam_recovery.quarantine import TrustedMapTransactionManager
from slam_recovery.sim.transaction_manager_node import OnlineRecoveryTransactionNode
from slam_recovery.experiments.evaluation import (
    associate_trajectories,
    load_tum_trajectory_se3,
    umeyama_se3_align,
)

INJ_SCANS = "/tmp/fastlivo/hall01_inj43.bag"
INJ_POSES = "/tmp/fastlivo/res_hall01_inj_05x.bag"
CLN_SCANS = "/tmp/fastlivo/hall01_100_160.bag"
CLN_POSES = "/tmp/fastlivo/res_hall01_clean_05x.bag"
GT_PATH = "/home/R26534/M2DGR/GT/hall_01.txt"

WINDOW_START_SEQ = 100.0     # bag window is sequence time [100, 160] s
ONSET_SEQ = 120.0            # injection [120, 140] s
ONSET_REL = ONSET_SEQ - WINDOW_START_SEQ
INJ_END_REL = 140.0 - WINDOW_START_SEQ

VOXEL = 0.10
SURF_TOL = 0.15
MAX_KF_POINTS = 15000
MAX_DT = 0.020

DT = np.dtype({
    "names": ["x", "y", "z", "intensity", "time", "ring"],
    "formats": ["<f4", "<f4", "<f4", "<f4", "<f4", "<u2"],
    "offsets": [0, 4, 8, 12, 16, 20],
    "itemsize": 24,
})


def load_poses(path, topic="/aft_mapped_to_init"):
    ts, xyz = [], []
    with rosbag.Bag(path, "r") as b:
        for _, m, _ in b.read_messages(topics=[topic]):
            ts.append(m.header.stamp.to_sec())
            p = m.pose.pose.position
            xyz.append([p.x, p.y, p.z])
    t = np.asarray(ts)
    x = np.asarray(xyz)
    o = np.argsort(t)
    return t[o], x[o]


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


def build_keyframes(scan_path, pose_path):
    pts = load_scans(scan_path)
    pt, px = load_poses(pose_path)
    kfs, dts, dropped = [], [], 0
    for ts, p in pts:
        i = int(np.argmin(np.abs(pt - ts)))
        dt = abs(pt[i] - ts)
        if dt > MAX_DT:
            dropped += 1
            continue
        kfs.append({"ts": ts, "rel": ts - pts[0][0], "pts": p, "pose": px[i].copy()})
        dts.append(dt)
    d = np.asarray(dts) if dts else np.zeros(1)
    stats = {
        "scans": len(pts),
        "paired": len(kfs),
        "dropped_dt": dropped,
        "dt_ms_p50": round(float(np.percentile(d, 50)) * 1e3, 3),
        "dt_ms_p95": round(float(np.percentile(d, 95)) * 1e3, 3),
        "dt_ms_max": round(float(d.max()) * 1e3, 3),
    }
    return kfs, stats


def world_points(kf):
    p, x = kf["pts"], kf["pose"]
    return p + x[None, :]


def voxels(points):
    if len(points) == 0:
        return set()
    q = np.floor(points / VOXEL).astype(np.int64)
    return set(map(tuple, q.tolist()))


# Voxel centres are 0.10 m apart and the surface tolerance is 0.15 m, so "within tolerance"
# is exactly the set of integer offsets with dx^2+dy^2+dz^2 <= 2.25 -> |offset|^2 <= 2.
# That makes the test O(1) per voxel instead of an O(N*M) distance matrix.
_NEIGHBOURS = [
    (dx, dy, dz)
    for dx in (-2, -1, 0, 1, 2)
    for dy in (-2, -1, 0, 1, 2)
    for dz in (-2, -1, 0, 1, 2)
    if dx * dx + dy * dy + dz * dz <= 2
]


def supported_mask(vox_keys, surf_keys):
    """True where a surface voxel lies within SURF_TOL of this voxel's centre."""
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
    m = supported_mask(vox_keys, surf_keys)
    return float(np.mean(~m))


def coverage_recall(surf_keys, map_keys):
    if not surf_keys:
        return float("nan")
    hit = sum(1 for k in surf_keys if k in map_keys)
    return hit / float(len(surf_keys))


def ate(pred_ts, pred_xyz, gt_ts, gt_xyz, R, t):
    m_ts, m_e, m_g = associate_trajectories(pred_ts, pred_xyz, gt_ts, gt_xyz, 0.05)
    if len(m_e) < 3:
        return float("nan"), 0
    al = m_e @ R.T + t
    err = np.linalg.norm(al - m_g, axis=1)
    return float(np.sqrt(np.mean(err ** 2))), int(len(err))


def main() -> None:
    out_manifest = os.path.join(
        "/tmp/wt-fourarm/slam_recovery/experiments/manifests",
        "four_arm_same_input_benchmark.json",
    )
    os.makedirs(os.path.dirname(out_manifest), exist_ok=True)

    print("loading injected run ...")
    inj_kfs, inj_stats = build_keyframes(INJ_SCANS, INJ_POSES)
    print(f"  {inj_stats}")

    print("loading clean run (scoring surface only) ...")
    cln_kfs, cln_stats = build_keyframes(CLN_SCANS, CLN_POSES)
    print(f"  {cln_stats}")

    # ---- proxy surface + proxy self-calibration ------------------------------------
    # The proxy must never enter any arm's map or validation reference; it is built here and
    # used only for scoring. Split the clean run by index parity to measure the proxy's own
    # resolution floor: half builds the surface, the other half is scored as if it were a map.
    proxy_surface = voxels(np.vstack([world_points(k) for k in cln_kfs]))  # scoring only

    # Null model for the proxy: split each clean scan's *points* by index parity, so both halves
    # observe the same surfaces. Splitting by scan index instead would compare two halves that
    # cover different space, and the resulting floor would swamped every real difference.
    def _half_cloud(kfs, parity):
        return np.vstack([world_points(k)[parity::2] for k in kfs])

    surf_pt_even = voxels(_half_cloud(cln_kfs, 0))
    surf_pt_odd = voxels(_half_cloud(cln_kfs, 1))

    def _selfcal(surf, other_map):
        return {
            "unsupported_voxel_fraction": round(float(unsupported_fraction(other_map, surf)), 4),
            "coverage_recall": round(coverage_recall(surf, other_map), 4),
            "_n_map_voxels": len(other_map),
            "_n_surface_voxels": len(surf),
        }

    selfcal = {"builds_from_even_points_scores_odd": _selfcal(surf_pt_even, surf_pt_odd),
               "builds_from_odd_points_scores_even": _selfcal(surf_pt_odd, surf_pt_even)}
    floor_unsup = float(np.mean([v["unsupported_voxel_fraction"] for v in selfcal.values()]))
    floor_cov = float(np.mean([v["coverage_recall"] for v in selfcal.values()]))
    print(f"  proxy self-calibration: unsupported={floor_unsup:.4f} coverage={floor_cov:.4f}")

    # ---- arm construction -----------------------------------------------------------
    pre = [k for k in inj_kfs if k["rel"] < ONSET_REL]
    quar = [k for k in inj_kfs if k["rel"] >= ONSET_REL]

    # Validation reference for A3 comes ONLY from the injected run's own pre-onset keyframes.
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
    repaired = {i: np.eye(4) for i in range(len(quar))}
    for i, k in enumerate(quar):
        repaired[i][:3, 3] = k["pose"]
    incumbent = {i: repaired[i].copy() for i in range(len(quar))}

    t0 = time.perf_counter()
    report = node.evaluate_and_commit_candidate(
        "four_arm_A3", repaired, incumbent_poses=incumbent, reentry_anchor_pose=np.eye(4)
    )
    a3_runtime = time.perf_counter() - t0
    verified_prefix = sorted(node.tx_mgr.trusted_poses.keys()) if report.accepted else []

    arms = {
        "A0_Host_Native": list(range(len(inj_kfs))),
        "A1_Quarantine_Only": list(range(len(pre))),
        "A2_Unconditional_Admission": list(range(len(inj_kfs))),
        "A3_Verified_Admission": list(range(len(pre))) + [len(pre) + i for i in verified_prefix],
    }
    all_kfs = inj_kfs

    # ---- trajectory alignment: ONE transform, fitted on the common pre-onset set ------
    ts_gt, xyz_gt, _ = load_tum_trajectory_se3(GT_PATH)
    pre_ts = np.asarray([k["ts"] for k in pre])
    pre_xyz = np.asarray([k["pose"] for k in pre])
    m_ts, m_e, m_g = associate_trajectories(pre_ts, pre_xyz, ts_gt, xyz_gt, 0.05)
    R, t_align, _ = umeyama_se3_align(m_e, m_g, with_scale=False)

    common_ids = set(arms["A0_Host_Native"])
    for v in arms.values():
        common_ids &= set(v)
    common_ids = sorted(common_ids)

    results = {}
    for name, ids in arms.items():
        pts = np.vstack([world_points(all_kfs[i]) for i in ids]) if ids else np.zeros((0, 3))
        vox = voxels(pts)
        admitted_ts = np.asarray([all_kfs[i]["ts"] for i in ids])
        admitted_xyz = np.asarray([all_kfs[i]["pose"] for i in ids])
        ate_adm, n_adm = ate(admitted_ts, admitted_xyz, ts_gt, xyz_gt, R, t_align)
        c_ts = np.asarray([all_kfs[i]["ts"] for i in common_ids])
        c_xyz = np.asarray([all_kfs[i]["pose"] for i in common_ids])
        ate_common, n_common = ate(c_ts, c_xyz, ts_gt, xyz_gt, R, t_align)
        # unexpected intervention on the clean interval: pre-onset keyframes not admitted, or
        # admitted with a pose that differs from the host's own recorded pose.
        pre_ids = set(range(len(pre)))
        rewritten_pre = len(pre_ids - set(ids))
        results[name] = {
            "admitted_keyframes": len(ids),
            "deferred_keyframes": len(all_kfs) - len(ids),
            "admitted_duration_sec": round(float(admitted_ts[-1] - admitted_ts[0]), 2) if len(ids) else 0.0,
            "committed_voxels": len(vox),
            "unsupported_voxel_fraction_vs_clean_proxy": round(float(unsupported_fraction(vox, proxy_surface)), 4),
            "clean_proxy_coverage_recall": round(coverage_recall(proxy_surface, vox), 4),
            "ate_on_common_support_m": round(ate_common, 4) if n_common else None,
            "ate_on_common_support_frames": n_common,
            "ate_on_admitted_set_m": round(ate_adm, 4) if n_adm else None,
            "ate_on_admitted_set_frames": n_adm,
            "clean_interval_keyframes_not_admitted": rewritten_pre,
            "runtime_sec": round(a3_runtime, 4) if name.startswith("A3") else None,
        }

    manifest = {
        "run_id": "four_arm_same_input_benchmark",
        "provenance": "ARCHIVED_REAL_HOST_POSES + INJECTION_SCANS",
        "provenance_note": (
            "Replays a recorded FAST-LIVO2 run. The poses are archived, not produced for this "
            "experiment; this is not an independent reproduction of the host."
        ),
        "inputs": {
            "injected_scans": INJ_SCANS,
            "injected_poses": INJ_POSES,
            "clean_scans_proxy_only": CLN_SCANS,
            "clean_poses_proxy_only": CLN_POSES,
            "gt_trajectory": GT_PATH,
        },
        "pairing": {"injected": inj_stats, "clean": cln_stats, "max_dt_sec": MAX_DT},
        "protocol": {
            "voxel_m": VOXEL,
            "surface_tolerance_m": SURF_TOL,
            "onset_rel_sec": ONSET_REL,
            "injection_end_rel_sec": INJ_END_REL,
            "alignment": "single SE(3) fitted on the pre-onset keyframes of the host, applied to all arms",
        },
        "reference_surface": {
            "provenance": "REAL_HOST_CLEAN_PROXY",
            "gt_surface_contam_3d": "UNAVAILABLE (no hall_01 GT mesh; M2DGR provides trajectory only)",
            "self_calibration": selfcal,
            "resolution_floor": {
                "unsupported_voxel_fraction": round(floor_unsup, 4),
                "coverage_recall": round(floor_cov, 4),
                "use": "differences between arms smaller than this are not findings",
            },
        },
        "validation_reference_source": {
            "A0_Host_Native": "none (no gate)",
            "A1_Quarantine_Only": "none (no gate)",
            "A2_Unconditional_Admission": "none (admission is unconditional)",
            "A3_Verified_Admission": "injected_run_pre_onset_keyframes",
        },
        "gate_result_A3": {
            "accepted": bool(report.accepted),
            "mode": report.mode.value,
            "holdout_nis": round(float(report.holdout_nis), 4),
            "reason": report.reason,
            "paired_evidence": node.last_paired_evidence,
        },
        "arms": results,
        "caveats": [
            "The candidate is the host's own quarantined trajectory; the archive holds no repaired "
            "candidate for this window, so A3 can only accept or reject the host poses themselves.",
            "A0 and A2 write the identical keyframe set and therefore produce the same map; they "
            "differ only in that A2 passed through quarantine before admitting everything.",
            "ATE on the admitted set is confounded by coverage: arms that admit fewer keyframes "
            "are scored over less of the trajectory. ate_on_common_support is the like-for-like "
            "number; differences there are the only ones attributable to admission policy.",
        ],
    }
    with open(out_manifest, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print("\n=== four-arm same-input (archived replay) ===")
    print(f"proxy floor: unsupported={floor_unsup:.4f}  coverage={floor_cov:.4f}")
    hdr = f"{'arm':30s} {'kf':>4s} {'vox':>8s} {'unsup':>7s} {'cover':>7s} {'ATEcommon':>10s} {'ATEadm':>8s} {'cleanLost':>9s}"
    print(hdr)
    for k, v in results.items():
        print(f"{k:30s} {v['admitted_keyframes']:4d} {v['committed_voxels']:8d} "
              f"{v['unsupported_voxel_fraction_vs_clean_proxy']:7.4f} {v['clean_proxy_coverage_recall']:7.4f} "
              f"{v['ate_on_common_support_m']:10.4f} {v['ate_on_admitted_set_m']:8.4f} "
              f"{v['clean_interval_keyframes_not_admitted']:9d}")
    print(f"\nA3 gate: {report.mode.value} accepted={report.accepted}")
    print(f"wrote {out_manifest}")


if __name__ == "__main__":
    main()
