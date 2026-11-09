"""Probe: is the published Mode-2 evidence on real sequences driven by mixed-surface
neighbourhoods rather than by pose error?

Run with the ROS python (rosbag is required and only available there):

    /home/R26534/mm/ros/bin/python -B docs/review_20261109_bbc3dcb/probe_real_plane_mix.py

All message times are `m.header.stamp`, never the bag record time. The two differ on this machine
(the MM-LINS odometry bag was re-recorded in 2026 while its messages keep the original M2DGR
stamps), and using the record time silently moves every stream into a different epoch.

Scope: DIAGNOSTIC ONLY. No default of `compute_disjoint_holdout_point_to_plane_nis` and no
published manifest is modified; results go to `--out` (default /tmp/real_plane_mix.json).

Why this probe exists
    The S1/S2 simulator-validity fix showed the holdout statistic is dominated by 8-NN plane fits
    that span two surfaces (thin 0.0375 vs mixed 234.0, thin fraction 33%). The real sequences use
    the same estimator with the same 600/300 sub-sampling, so both published Mode-2 data points are
    re-measured the same way:

        street_08     reject : NIS 4.4145 > 2.5, Wilson 0.4626
        room_dark_02  accept : NIS 0.6532 <= 2.5, Wilson 0.9235

    For every scored holdout pair this reports, on the estimator's own 600/300 sub-sample: 8-NN
    radius, plane thickness, planarity, cross-surface mixing fraction, thin-only and mixed-only
    NIS, pooled mean/median, thin fraction, and a bootstrap CI over keyframe pairs.

street_08 protocol
    The producing script was never committed (`merge_unseen_heldout_results.py` only merges), so
    this reproduces the E3 protocol (scan stride 5, pair step 2, sigma 0.25) plus the reference
    support rule the gate applies. It is NOT bit-exact against the published 4.4145 and the gap is
    reported next to every result.

room_dark_02 protocol
    Mirrors evaluate_room_dark_02.py (scan pair S_{k-5} -> S_k over [t0+15, t0+38], sigma 0.25,
    ORB-SLAM3 B6 reconstructed offline from the B2 trajectory). The reconstruction is checked
    against the published 0.6532 before the neighbourhood split is reported.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _REPO)

try:
    import rosbag
except ImportError as exc:  # pragma: no cover - environment guard
    raise SystemExit(
        "rosbag is required: run with /home/R26534/mm/ros/bin/python (see module docstring)"
    ) from exc

from slam_recovery.validation import compute_disjoint_holdout_point_to_plane_nis  # noqa: E402

_DT = np.dtype({"names": ["x", "y", "z", "intensity", "time", "ring"],
                "formats": ["<f4", "<f4", "<f4", "<f4", "<f4", "<u2"],
                "offsets": [0, 4, 8, 12, 16, 20], "itemsize": 24})

THIN_THRESHOLDS = (0.03, 0.05, 0.07, 0.10)


def _stamp_sec(msg) -> float:
    return float(msg.header.stamp.to_sec())


def read_odom(path: str, topic: str = "/lio_sam/mapping/odometry"):
    ts, xyz, quat = [], [], []
    with rosbag.Bag(path, "r") as b:
        for _, m, _ in b.read_messages(topics=[topic]):
            ts.append(_stamp_sec(m))
            p, q = m.pose.pose.position, m.pose.pose.orientation
            xyz.append([p.x, p.y, p.z])
            quat.append([q.x, q.y, q.z, q.w])
    order = np.argsort(ts)
    return np.asarray(ts)[order], np.asarray(xyz)[order], np.asarray(quat)[order]


def read_scans(path: str, topic: str = "/velodyne_points", rmin: float = 0.8, rmax: float = 25.0):
    out = []
    with rosbag.Bag(path, "r") as b:
        for _, m, _ in b.read_messages(topics=[topic]):
            arr = np.frombuffer(m.data, dtype=_DT)
            pts = np.column_stack([arr["x"], arr["y"], arr["z"]]).astype(np.float64)
            rad = np.linalg.norm(pts, axis=1)
            out.append((_stamp_sec(m), pts[(rad > rmin) & (rad < rmax)]))
    return out


def _support_fraction(ref: np.ndarray, query: np.ndarray, radius: float = 1.0) -> float:
    """Fraction of `query` points within `radius` of `ref` (brute force: the ROS python has no scipy)."""
    if len(ref) == 0 or len(query) == 0:
        return 0.0
    best = np.full(len(query), np.inf)
    for start in range(0, len(ref), 512):
        chunk = ref[start:start + 512]
        d = np.linalg.norm(query[:, None, :] - chunk[None, :, :], axis=-1).min(axis=1)
        best = np.minimum(best, d)
    return float(np.mean(best < radius))


def quat_to_rot(q) -> np.ndarray:
    x, y, z, w = (float(v) for v in q)
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ])


def pair_diagnostics(ref_pts, cur_pts, T, sigma: float) -> dict:
    """One holdout pair, measured exactly where the estimator fits its planes."""
    ref = np.asarray(ref_pts, dtype=np.float64)[:, :3]
    cur = np.asarray(cur_pts, dtype=np.float64)[:, :3]
    if len(ref) < 30 or len(cur) < 10:
        return {"scored": False}
    t_sub = ref[:: max(1, len(ref) // 600)][:600]
    hold = (cur @ T[:3, :3].T) + T[:3, 3]
    h_sub = hold[:: max(1, len(hold) // 300)][:300]
    kk = min(8, len(t_sub) - 1)
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
    thinness = np.sqrt(np.maximum(l0, 0.0)) / np.maximum(np.sqrt(np.maximum(l1, 1e-12)), 1e-12)
    radius = np.sqrt(np.max(d2[np.arange(len(h_sub))[:, None], nn], axis=1))
    out = {
        "scored": True,
        "nis_estimator": float(compute_disjoint_holdout_point_to_plane_nis(
            ref, cur, T, sigma_meas_m=sigma)),
        "nis_median_pooled": float(np.median(nis)),
        "nis_mean_pooled": float(np.mean(nis)),
        "nn_radius_m_mean": float(np.mean(radius)),
        "plane_thickness_rms_m_median": float(np.median(np.sqrt(np.maximum(l0, 0.0)))),
        "residual_abs_median_m": float(np.median(resid)),
        "residual_frac_gt_0p5m": float(np.mean(resid > 0.5)),
        "n_ref_used": int(len(t_sub)),
        "n_holdout_used": int(len(h_sub)),
    }
    for thr in THIN_THRESHOLDS:
        thin = thinness <= thr
        out[f"thin_frac_{thr}"] = float(np.mean(thin))
        out[f"nis_thin_{thr}"] = float(np.mean(nis[thin])) if thin.any() else None
        out[f"nis_mixed_{thr}"] = float(np.mean(nis[~thin])) if (~thin).any() else None
    return out


def _boot_ci(values, n_boot: int = 2000, seed: int = 0):
    v = np.asarray([x for x in values if x is not None and np.isfinite(x)], dtype=np.float64)
    if len(v) == 0:
        return None
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(v), size=(n_boot, len(v)))
    means = v[idx].mean(axis=1)
    return [float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))]


def _aggregate(rows, sigma: float, thin_thr: float = 0.05) -> dict:
    ok = [r for r in rows if r.get("scored")]
    if not ok:
        return {"n_pairs": 0}

    def vals(key):
        return [r[key] for r in ok if r.get(key) is not None and np.isfinite(r[key])]

    def stat(key):
        v = vals(key)
        if not v:
            return {"mean": None, "median": None, "ci95": None}
        return {"mean": float(np.mean(v)), "median": float(np.median(v)),
                "ci95": _boot_ci(v)}          # bootstrap over keyframe pairs

    out = {
        "n_pairs_scored": len(ok),
        "sigma_meas_m": sigma,
        "thin_threshold": thin_thr,
        "nis_estimator": stat("nis_estimator"),
        "nis_thin_only": stat(f"nis_thin_{thin_thr}"),
        "nis_mixed_only": stat(f"nis_mixed_{thin_thr}"),
        "nis_mean_pooled": stat("nis_mean_pooled"),
        "nis_median_pooled": stat("nis_median_pooled"),
        "thin_fraction": stat(f"thin_frac_{thin_thr}"),
        "nn_radius_m_mean": stat("nn_radius_m_mean"),
        "plane_thickness_rms_m_median": stat("plane_thickness_rms_m_median"),
        "residual_abs_median_m": stat("residual_abs_median_m"),
        "residual_frac_gt_0p5m": stat("residual_frac_gt_0p5m"),
    }
    for thr in THIN_THRESHOLDS:
        t = stat(f"nis_thin_{thr}")
        out[f"thin_sweep_{thr}"] = {
            "thin_fraction": stat(f"thin_frac_{thr}")["mean"],
            "thin_only_mean": t["mean"],
            "thin_only_ci95": t["ci95"],
            "passes_tau_2p5": (t["mean"] is not None and t["mean"] <= 2.5),
            "ci_entirely_below_tau": (t["ci95"] is not None and t["ci95"][1] <= 2.5),
        }
    est = out["nis_estimator"]["mean"]
    out["verdict_at_tau_2p5"] = None if est is None else ("FAILED" if est > 2.5 else "PASSED")
    th = out["nis_thin_only"]["mean"]
    out["verdict_thin_only_at_tau_2p5"] = None if th is None else ("FAILED" if th > 2.5 else "PASSED")
    return out


def street_08(sigma_list=(0.25, 0.12), inject_window=(50.0, 70.0)):
    V = "/tmp/unseen_val"
    scans_all = read_scans(f"{V}/street_08_pbag_deg.bag")
    t_start = scans_all[0][0]
    out = {}
    for tag, bag in (("B2_degraded_native", f"{V}/res_lio_street08_pbag_deg.bag"),
                     ("B6_repaired", f"{V}/res_lio_street08_pbag_rep.bag")):
        ts_o, xyz_o, q_o = read_odom(bag)
        rec = []
        for sec, pts in scans_all:
            i = int(np.argmin(np.abs(ts_o - sec)))
            R = quat_to_rot(q_o[i])
            rec.append((sec, pts @ R.T, i, R))
        pairs = []
        for k in range(5, len(rec), 2):
            sec_ref, ref, i_ref, R_ref = rec[k - 5]
            _, cur, i_cur, _ = rec[k]
            d = R_ref.T @ (xyz_o[i_cur] - xyz_o[i_ref])
            q = cur[:: max(1, len(cur) // 200)][:200]
            if _support_fraction(ref, q + d, 1.0) < 0.60:   # support rule the gate applies
                continue
            T = np.eye(4)
            T[:3, 3] = d
            pairs.append((sec_ref - t_start, ref, cur, T))
        out[tag] = {}
        for sigma in sigma_list:
            rows = [pair_diagnostics(r, c, T, sigma) for _, r, c, T in pairs]
            block = {"all": _aggregate(rows, sigma)}
            for label, inside in (("inside_injection_window", True),
                                  ("outside_injection_window", False)):
                sub = [row for row, (tr, _, _, _) in zip(rows, pairs)
                       if (inject_window[0] <= tr <= inject_window[1]) == inside]
                block[label] = _aggregate(sub, sigma)
            out[tag][f"sigma_{sigma}"] = block
    out["published_reference"] = {
        "cross_scan_nis_mean_b2": 4.8799,
        "cross_scan_nis_mean_b6": 4.4145,
        "sigma_meas_m": 0.25,
        "note": "the producing script was never committed; this probe uses the E3 protocol "
                "(stride 5, step 2) plus the gate's reference-support rule and is NOT bit-exact",
    }
    b6 = (out.get("B6_repaired", {}).get("sigma_0.25", {}).get("all", {})
          .get("nis_estimator", {}).get("mean"))
    out["reproduction_gap_b6"] = None if b6 is None else round(float(b6) - 4.4145, 4)
    return out


def room_dark_02(sigma_list=(0.25, 0.12)):
    """Rebuild the evaluator's holdout pairs, mirroring evaluate_room_dark_02.py."""
    traj = "/tmp/unseen_val/orb_room_dark_02/trajectories"
    fl_bag = "/tmp/unseen_val/room_dark_02_fl.bag"
    from slam_recovery.experiments.evaluation import load_tum_trajectory_se3, umeyama_se3_align

    ts_fl, xyz_fl, q_fl = read_odom("/tmp/mmlins_roomdark02_clean.bag", "/Odometry")
    ts_b2, xyz_b2, _ = load_tum_trajectory_se3(os.path.join(traj, "raw_CameraTrajectory_all.txt"))
    cam_ts = np.array([float(l.split()[0]) for l in open(
        "/tmp/unseen_val/orb_room_dark_02/associations_raw.txt") if l.strip()])
    t0 = float(ts_fl[0])
    t_q0, t_q1 = t0 + 13.0, t0 + 38.0

    b2_full = np.column_stack([np.interp(cam_ts, ts_b2, xyz_b2[:, d]) for d in range(3)])
    pre = np.flatnonzero(cam_ts < t_q0)
    post = np.flatnonzero(cam_ts > t_q1)
    quar = np.flatnonzero((cam_ts >= t_q0) & (cam_ts <= t_q1))
    aux = np.column_stack([np.interp(cam_ts, ts_fl, xyz_fl[:, d]) for d in range(3)])
    cal = ((cam_ts >= t_q0 - 12.0) & (cam_ts < t_q0)) | ((cam_ts > t_q1) & (cam_ts <= t_q1 + 12.0))
    if cal.sum() < 10:
        return {"reproducible": False, "reason": "calibration window empty",
                "t0": t0, "cam_ts0": float(cam_ts[0]), "n_cal": int(cal.sum())}
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
        out[tag] = {f"sigma_{sigma}": {"all": _aggregate(
            [pair_diagnostics(r, c, T, sigma) for r, c, T in pairs], sigma)}
            for sigma in sigma_list}
    out["published_reference"] = {"cross_scan_holdout_nis_b2": 0.9097,
                                  "cross_scan_holdout_nis_b6": 0.6532,
                                  "sigma_meas_m": 0.25}
    got = (out["B6_offline_construct"]["sigma_0.25"]["all"]
           .get("nis_estimator", {}).get("mean"))
    out["reproduction_gap_b6"] = None if got is None else round(float(got) - 0.6532, 4)
    out["n_holdout_pairs"] = len(rec)
    return out


def _row(arm, group, s):
    if not isinstance(s, dict) or "nis_estimator" not in s:
        return
    e, t, m = s["nis_estimator"], s["nis_thin_only"], s["nis_mixed_only"]
    lo, hi = e["ci95"]
    thin = "-" if t["mean"] is None else f"{t['mean']:7.3f}"
    mixed = "-" if m["mean"] is None else f"{m['mean']:7.2f}"
    print(f"  {arm:20s} {group:28s} pairs={s['n_pairs_scored']:4d} "
          f"NIS={e['mean']:7.3f}[{lo:6.3f},{hi:6.3f}] thin={thin} mixed={mixed} "
          f"thin%={100*s['thin_fraction']['mean']:5.1f} med={s['nis_median_pooled']['mean']:6.3f} "
          f"V={s['verdict_at_tau_2p5']}/thin={s['verdict_thin_only_at_tau_2p5']}")


def _fmt(name, block):
    print(f"\n== {name} ==")
    for arm, v in block.items():
        if not isinstance(v, dict):
            print(f"  {arm}: {v}")
            continue
        if "reproducible" in v:
            print(f"  {arm}: reproducible={v['reproducible']} {v.get('reason', '')}")
            continue
        if "nis_estimator" in v:                     # already a single group
            _row(arm, "all", v)
            continue
        for sigma, groups in v.items():
            if not isinstance(groups, dict):
                print(f"  {arm}.{sigma}: {groups}")
                continue
            for group, s in groups.items():
                _row(arm, f"{sigma}/{group}", s)


def _thin_sweep(name, block, arm="B6_repaired", sigma="sigma_0.25", group="all"):
    s = block.get(arm, {}).get(sigma, {}).get(group)
    if not s:
        return
    print(f"  thin-threshold sweep [{name} {arm} {sigma} {group}]")
    for thr in THIN_THRESHOLDS:
        w = s.get(f"thin_sweep_{thr}")
        if not w:
            continue
        ci = w["thin_only_ci95"]
        print(f"    thr={thr:.2f} thin%={100*w['thin_fraction']:5.1f} "
              f"thin-only={w['thin_only_mean']:7.3f} CI=[{ci[0]:6.3f},{ci[1]:6.3f}] "
              f"passes={w['passes_tau_2p5']} ci_below_tau={w['ci_entirely_below_tau']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/tmp/real_plane_mix.json")
    args = ap.parse_args()

    res = {"street_08": street_08(), "room_dark_02": room_dark_02()}
    _fmt("street_08 (published: reject, NIS 4.4145 @ sigma 0.25)", res["street_08"])
    _fmt("room_dark_02 (published: accept, NIS 0.6532 @ sigma 0.25)", res["room_dark_02"])
    for seq in ("street_08", "room_dark_02"):
        for arm in ("B6_repaired", "B6_offline_construct", "B2_degraded_native", "B2_native"):
            _thin_sweep(seq, res[seq], arm=arm)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2, ensure_ascii=False)
    print("\nsaved", args.out)
