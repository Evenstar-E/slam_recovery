"""Probe: is the published Mode-2 evidence on real sequences driven by mixed-surface
neighbourhoods rather than by pose error?

Requires `rosbags` (pip install rosbags) when the ROS1 python bindings are not available; the
import is lazy, so the rest of the repository is unaffected.

Run from the repository root:

    python -B docs/review_20261109_bbc3dcb/probe_real_plane_mix.py

Scope: DIAGNOSTIC ONLY. No default of `compute_disjoint_holdout_point_to_plane_nis` and no
published manifest is modified; results go to `--out` (default /tmp/real_plane_mix.json).

Why this probe exists
    The S1/S2 simulator-validity fix showed that the holdout statistic is dominated by 8-NN plane
    fits that span two surfaces (thin neighbourhoods score 0.0375, mixed ones 234.0, and only 33%
    are thin). The real sequences use the SAME estimator with the same 600/300 sub-sampling, so the
    two published Mode-2 data points have to be re-measured the same way:

        street_08     reject : NIS 4.4145 > 2.5, Wilson 0.4626
        room_dark_02  accept : NIS 0.6532 <= 2.5, Wilson 0.9235

    For each holdout pair actually scored we report, on the estimator's own 600/300 sub-sample:
    8-NN radius, plane thickness, planarity, cross-surface mixing fraction, thin-only and
    mixed-only NIS, mean/median, and the thin fraction.

Reproduction status (verified 2026-11-09 on this machine)
    street_08     : the producing script was never committed (`merge_unseen_heldout_results.py`
                    only merges). The protocol below is the E3 one (scan_stride=5, pair_step=2,
                    sigma=0.25) plus the reference-support rule the gate applies, and it lands on
                    the published magnitude (B6 ~4.26 vs 4.4145) but is NOT bit-exact.
    room_dark_02  : `evaluate_room_dark_02.py` cannot run on the artifacts left on disk -- the ORB
                    trajectories carry the original M2DGR clock (2021-07-30) while the FAST-LIO
                    odometry bag carries the 2026 recording clock, so the calibration window
                    `cal_o` selects zero samples and `umeyama_se3_align` gets an empty set. This
                    probe aligns the two clocks by their first message so the same physical pairs
                    can still be measured; the result is therefore indicative, not a replay.

Any number from this probe is a property of the CURRENT artifacts, not of the numbers the paper
quotes. The accompanying message reports the reproduction gap explicitly.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
from scipy.spatial import cKDTree

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _REPO)

from slam_recovery.validation import compute_disjoint_holdout_point_to_plane_nis  # noqa: E402

_DT = np.dtype({"names": ["x", "y", "z", "intensity", "time", "ring"],
                "formats": ["<f4", "<f4", "<f4", "<f4", "<f4", "<u2"],
                "offsets": [0, 4, 8, 12, 16, 20], "itemsize": 24})

_typestore = None


def _ts():
    global _typestore
    if _typestore is None:
        from rosbags.typesys import Stores, get_typestore
        _typestore = get_typestore(Stores.ROS1_NOETIC)
    return _typestore


def read_odom(path: str, topic: str = "/lio_sam/mapping/odometry"):
    from rosbags.rosbag1 import Reader
    ts, xyz, quat = [], [], []
    with Reader(path) as r:
        conns = [c for c in r.connections if c.topic == topic]
        for conn, t, raw in r.messages(connections=conns):
            m = _ts().deserialize_ros1(raw, conn.msgtype)
            ts.append(t / 1e9)
            p, q = m.pose.pose.position, m.pose.pose.orientation
            xyz.append([p.x, p.y, p.z])
            quat.append([q.x, q.y, q.z, q.w])
    order = np.argsort(ts)
    return np.asarray(ts)[order], np.asarray(xyz)[order], np.asarray(quat)[order]


def read_scans(path: str, topic: str = "/velodyne_points", rmin: float = 0.8, rmax: float = 25.0):
    from rosbags.rosbag1 import Reader
    out = []
    with Reader(path) as r:
        conns = [c for c in r.connections if c.topic == topic]
        for conn, t, raw in r.messages(connections=conns):
            m = _ts().deserialize_ros1(raw, conn.msgtype)
            arr = np.frombuffer(np.asarray(m.data, dtype=np.uint8).tobytes(), dtype=_DT)
            pts = np.column_stack([arr["x"], arr["y"], arr["z"]]).astype(np.float64)
            rad = np.linalg.norm(pts, axis=1)
            out.append((t / 1e9, pts[(rad > rmin) & (rad < rmax)]))
    return out


def quat_to_rot(q) -> np.ndarray:
    x, y, z, w = (float(v) for v in q)
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ])


def pair_diagnostics(ref_pts, cur_pts, T, sigma: float, k: int = 8) -> dict:
    """One holdout pair, measured exactly where the estimator fits its planes."""
    ref = np.asarray(ref_pts, dtype=np.float64)[:, :3]
    cur = np.asarray(cur_pts, dtype=np.float64)[:, :3]
    if len(ref) < 30 or len(cur) < 10:
        return {"scored": False}
    t_sub = ref[:: max(1, len(ref) // 600)][:600]
    hold = (cur @ T[:3, :3].T) + T[:3, 3]
    h_sub = hold[:: max(1, len(hold) // 300)][:300]
    kk = min(int(k), len(t_sub) - 1)
    d2 = np.sum((h_sub[:, None, :] - t_sub[None, :, :]) ** 2, axis=-1)
    nn = np.argpartition(d2, kth=kk, axis=1)[:, :kk]
    nb = t_sub[nn]
    mean_nn = nb.mean(axis=1)
    centered = nb - mean_nn[:, None, :]
    covs = np.einsum("mki,mkj->mij", centered, centered) / float(kk)
    evals, eigvecs = np.linalg.eigh(covs)
    l0, l1 = evals[:, 0], evals[:, 1]
    normals = eigvecs[:, :, 0]
    resid = np.abs(np.sum(normals * (h_sub - mean_nn), axis=1))
    nis = (resid / sigma) ** 2
    thin = (np.sqrt(np.maximum(l0, 0.0)) / np.maximum(np.sqrt(np.maximum(l1, 1e-12)), 1e-12)) <= 0.05
    radius = np.sqrt(np.max(d2[np.arange(len(h_sub))[:, None], nn], axis=1))
    return {
        "scored": True,
        "nis_estimator": float(compute_disjoint_holdout_point_to_plane_nis(
            ref, cur, T, sigma_meas_m=sigma)),
        "nis_mean_pooled": float(np.mean(nis)),
        "nis_median_pooled": float(np.median(nis)),
        "nis_thin_only": (float(np.mean(nis[thin])) if thin.any() else None),
        "nis_mixed_only": (float(np.mean(nis[~thin])) if (~thin).any() else None),
        "thin_fraction": float(np.mean(thin)),
        "nn_radius_m_mean": float(np.mean(radius)),
        "plane_thickness_rms_m_median": float(np.median(np.sqrt(np.maximum(l0, 0.0)))),
        "residual_abs_median_m": float(np.median(resid)),
        "residual_frac_gt_0p5m": float(np.mean(resid > 0.5)),
        "n_ref_used": int(len(t_sub)),
        "n_holdout_used": int(len(h_sub)),
    }


def _aggregate(rows, sigma: float) -> dict:
    ok = [r for r in rows if r.get("scored")]
    if not ok:
        return {"n_pairs": 0}
    def mean_of(key):
        vals = [r[key] for r in ok if r.get(key) is not None]
        return float(np.mean(vals)) if vals else None
    return {
        "n_pairs_scored": len(ok),
        "nis_estimator_mean": mean_of("nis_estimator"),
        "nis_estimator_median": float(np.median([r["nis_estimator"] for r in ok])),
        "nis_mean_pooled": mean_of("nis_mean_pooled"),
        "nis_median_pooled": mean_of("nis_median_pooled"),
        "nis_thin_only": mean_of("nis_thin_only"),
        "nis_mixed_only": mean_of("nis_mixed_only"),
        "thin_fraction": mean_of("thin_fraction"),
        "nn_radius_m_mean": mean_of("nn_radius_m_mean"),
        "plane_thickness_rms_m_median": mean_of("plane_thickness_rms_m_median"),
        "residual_abs_median_m": mean_of("residual_abs_median_m"),
        "residual_frac_gt_0p5m": mean_of("residual_frac_gt_0p5m"),
        "sigma_meas_m": sigma,
        "verdict_at_tau_2p5": (
            "FAILED" if (mean_of("nis_estimator") or 0.0) > 2.5 else "PASSED"),
        "verdict_thin_only_at_tau_2p5": (
            "FAILED" if (mean_of("nis_thin_only") or 0.0) > 2.5 else "PASSED"),
    }


def street_08(sigma_list=(0.25, 0.12)):
    V = "/tmp/unseen_val"
    scans_all = read_scans(f"{V}/street_08_pbag_deg.bag")
    out = {}
    for tag, bag in (("B2_degraded_native", f"{V}/res_lio_street08_pbag_deg.bag"),
                     ("B6_repaired", f"{V}/res_lio_street08_pbag_rep.bag")):
        ts_o, xyz_o, q_o = read_odom(bag)
        rec = []
        for sec, pts in scans_all:
            i = int(np.argmin(np.abs(ts_o - sec)))
            R = quat_to_rot(q_o[i])
            rec.append((pts @ R.T, i, R))
        pairs = []
        for k in range(5, len(rec), 2):
            ref, i_ref, R_ref = rec[k - 5]
            cur, i_cur, _ = rec[k]
            d = R_ref.T @ (xyz_o[i_cur] - xyz_o[i_ref])
            q = cur[:: max(1, len(cur) // 200)][:200]
            dist, _ = cKDTree(ref).query(q + d)
            if np.mean(dist < 1.0) < 0.60:      # same support rule the gate applies
                continue
            T = np.eye(4)
            T[:3, 3] = d
            pairs.append((ref, cur, T))
        out[tag] = {
            f"sigma_{sigma}": _aggregate(
                [pair_diagnostics(r, c, T, sigma) for r, c, T in pairs], sigma)
            for sigma in sigma_list
        }
    out["published_reference"] = {
        "cross_scan_nis_mean_b2": 4.8799,
        "cross_scan_nis_mean_b6": 4.4145,
        "sigma_meas_m": 0.25,
        "note": "the producing script was never committed; this probe uses the E3 protocol "
                "(stride 5, step 2) plus the gate's reference-support rule and is NOT bit-exact",
    }
    b6 = out.get("B6_repaired", {}).get("sigma_0.25", {}).get("nis_estimator_mean")
    out["reproduction_gap_b6"] = (
        None if b6 is None else round(float(b6) - 4.4145, 4))
    return out


def room_dark_02(sigma_list=(0.25, 0.12)):
    """Rebuild the evaluator's B6 trajectory with the two clocks aligned by first message."""
    traj = "/tmp/unseen_val/orb_room_dark_02/trajectories"
    fl_bag = "/tmp/unseen_val/room_dark_02_fl.bag"
    from slam_recovery.experiments.evaluation import load_tum_trajectory_se3, umeyama_se3_align

    ts_fl, xyz_fl, q_fl = read_odom("/tmp/mmlins_roomdark02_clean.bag", "/Odometry")
    scans_probe = read_scans(fl_bag)
    # The committed evaluator mixes two clocks without noticing: the LiDAR/camera streams carry the
    # original M2DGR clock (2021-07-30) while the FAST-LIO odometry bag carries the 2026 recording
    # clock. Detecting it here is the finding, not an obstacle to work around silently.
    clock_offset = float(scans_probe[0][0] - ts_fl[0]) if scans_probe and len(ts_fl) else None
    if clock_offset is None or abs(clock_offset) > 1.0:
        return {
            "reproducible": False,
            "reason": "the LiDAR/camera streams and the FAST-LIO odometry bag are on different "
                      "clocks; `cal_o` selects zero samples and `umeyama_se3_align` receives an "
                      "empty set, so evaluate_room_dark_02.py cannot produce 0.6532 from these "
                      "files",
            "clock_offset_s": clock_offset,
            "odom_span_s": float(ts_fl[-1] - ts_fl[0]) if len(ts_fl) else None,
            "scan_span_s": float(scans_probe[-1][0] - scans_probe[0][0]) if scans_probe else None,
            "odom_messages": int(len(ts_fl)),
            "scan_messages": int(len(scans_probe)),
        }
    ts_b2, xyz_b2, _ = load_tum_trajectory_se3(os.path.join(traj, "raw_CameraTrajectory_all.txt"))
    cam_ts = np.array([float(l.split()[0]) for l in open(
        "/tmp/unseen_val/orb_room_dark_02/associations_raw.txt") if l.strip()])

    # clock alignment the committed evaluator does not perform (see module docstring)
    shift = ts_fl[0] - cam_ts[0]
    cam_ts = cam_ts + shift
    ts_b2 = ts_b2 + shift
    t0 = float(ts_fl[0])
    t_q0, t_q1 = t0 + 13.0, t0 + 38.0

    b2_full = np.column_stack([np.interp(cam_ts, ts_b2, xyz_b2[:, d]) for d in range(3)])
    pre = np.flatnonzero(cam_ts < t_q0)
    post = np.flatnonzero(cam_ts > t_q1)
    quar = np.flatnonzero((cam_ts >= t_q0) & (cam_ts <= t_q1))
    aux = np.column_stack([np.interp(cam_ts, ts_fl, xyz_fl[:, d]) for d in range(3)])
    cal = ((cam_ts >= t_q0 - 12.0) & (cam_ts < t_q0)) | ((cam_ts > t_q1) & (cam_ts <= t_q1 + 12.0))
    if cal.sum() < 10:
        return {"error": "calibration window empty even after clock alignment"}
    R_a2o, t_a2o, s_a2o = umeyama_se3_align(aux[cal], b2_full[cal], with_scale=True)
    R_o2l, t_o2l, s_o2l = umeyama_se3_align(b2_full[cal], aux[cal], with_scale=True)
    aux_in_orb = (s_a2o * (aux @ R_a2o.T)) + t_a2o

    b6 = b2_full.copy()
    i0, i1 = pre[-1], post[0]
    clos = (b6[i1] - b6[i0]) - (aux_in_orb[i1] - aux_in_orb[i0])
    dt_q = max(cam_ts[i1] - cam_ts[i0], 1e-6)
    for idx in quar:
        alpha = float(np.clip((cam_ts[idx] - cam_ts[i0]) / dt_q, 0.0, 1.0))
        b6[idx] = b6[i0] + (aux_in_orb[idx] - aux_in_orb[i0]) + alpha * clos

    raw = [s for s in read_scans(fl_bag) if t0 + 15.0 <= s[0] <= t0 + 38.0]
    rec = []
    for sec, pts in raw:
        i = int(np.argmin(np.abs(ts_fl - sec)))
        rec.append((pts @ quat_to_rot(q_fl[i]).T, int(np.argmin(np.abs(cam_ts - sec)))))

    out = {}
    for tag, xyz in (("B2_native", (s_o2l * (b2_full @ R_o2l.T)) + t_o2l),
                     ("B6_offline_construct", (s_o2l * (b6 @ R_o2l.T)) + t_o2l)):
        pairs = []
        for k in range(5, len(rec), 2):
            ref, i_ref = rec[k - 5]
            cur, i_cur = rec[k]
            T = np.eye(4)
            T[:3, 3] = xyz[i_cur] - xyz[i_ref]
            pairs.append((ref, cur, T))
        out[tag] = {
            f"sigma_{sigma}": _aggregate(
                [pair_diagnostics(r, c, T, sigma) for r, c, T in pairs], sigma)
            for sigma in sigma_list
        }
    out["clock_shift_s"] = float(shift)
    return out


def _fmt(name, block):
    print(f"\n== {name} ==")
    for tag, v in block.items():
        if not isinstance(v, dict):
            print(f"  {tag}: {v}")
            continue
        if v.get("reproducible") is False:
            print(f"  {tag}: NOT REPRODUCIBLE -- {v.get('reason')}")
            print(f"    clock_offset_s={v.get('clock_offset_s')} odom_span_s={v.get('odom_span_s')} "
                  f"scan_span_s={v.get('scan_span_s')} msgs={v.get('odom_messages')}")
            continue
        for sk, s in v.items():
            if not isinstance(s, dict) or "n_pairs_scored" not in s:
                print(f"  {tag}.{sk}: {s}")
                continue
            print(f"  {tag:22s} {sk:9s} pairs={s['n_pairs_scored']:4d} "
                  f"NIS_est={s['nis_estimator_mean']} thin-only={s['nis_thin_only']} "
                  f"mixed-only={s['nis_mixed_only']} thin%="
                  f"{None if s['thin_fraction'] is None else round(100*s['thin_fraction'],1)} "
                  f"median={s['nis_median_pooled']} "
                  f"verdict={s['verdict_at_tau_2p5']}/thin={s['verdict_thin_only_at_tau_2p5']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/tmp/real_plane_mix.json")
    args = ap.parse_args()

    res = {"street_08": street_08(), "room_dark_02": room_dark_02()}
    _fmt("street_08 (published: reject, NIS 4.4145 @ sigma 0.25)", res["street_08"])
    _fmt("room_dark_02 (published: accept, NIS 0.6532 @ sigma 0.25)", res["room_dark_02"])
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2, ensure_ascii=False)
    print("\nsaved", args.out)
