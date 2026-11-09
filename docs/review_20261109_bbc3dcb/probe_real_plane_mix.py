"""Probe: what actually decides the two published Mode-2 verdicts -- NIS, sigma, or Wilson?

Run with the ROS python (rosbag lives there):

    /home/R26534/mm/ros/bin/python -B docs/review_20261109_bbc3dcb/probe_real_plane_mix.py

All message times are `m.header.stamp`; the bag record time is a different clock on this machine and
using it silently moves a stream into another epoch.

Scope: DIAGNOSTIC ONLY. No estimator default and no published manifest is modified. Results go to
`--out` (default /tmp/real_plane_mix.json); the timeline figure is drawn by
plot_real_plane_mix.py from that JSON.

What is measured
  1. sigma calibration on CLEAN runs: residuals r of the same S_{k-5}->S_k point-to-plane protocol
     (identical 600/300 sub-sampling and 8-NN fit), reported as
        sigma* = sqrt(mean r^2)   (the scale at which clean data scores NIS = 1)
        sigma_robust = 1.4826 * MAD(r), std(r), percentile(|r|, 68)
     plus the residual distribution and the |r| > 0.15 / 0.5 / 2.0 m fractions.
     sigma* is an EMPIRICAL NORMALISATION SCALE, not a noise model and not a chi-square bound:
       * fitted on a CLEAN run of the same sequence, over the same time window the holdout covers
         (street_08: clean bags, full 130 s; room_dark_02: FAST-LIO clean, [t0+15, t0+38]);
       * validated by splitting the clean pairs in half -- sigma* fitted on the even pairs scores
         0.99-1.01 on the odd pairs in every source below, so the scale transfers inside the window;
       * for deployment take it from a short clean segment of the same platform and scene (or from
         the per-sequence table this probe prints), never from a constant shared across sequences.
         The gate's 0.12 fails the clean data of BOTH sequences (2.7-12.1), the evaluator's 0.25
         fails street_08 (2.8-3.6).
  2. Per-pair NIS for every arm, rescaled exactly (NIS is proportional to 1/sigma^2) to sigma* and
     to the gate's 0.12 and the evaluator's 0.25, with bootstrap CIs over keyframe pairs.
  3. Neighbourhood split (thin / mixed) at the estimator's own sub-sample.
  4. The Wilson lower bound, which carries no sigma at all.
  5. street_08 odometry-density variants (base vs _1x), because the published 4.4145 does not say
     which recording produced it.

Frames: every scan is rotated into world axes by its own pose and the pair translation is the
world position difference (convention of evaluate_room_dark_02.py). Mixing a body-frame
displacement with world-axis clouds is a bug; `analytic_frame_check()` builds a 90 deg yaw case
whose residual is known in closed form and asserts the convention.

street_08 has no committed generator (`merge_unseen_heldout_results.py` only merges), so its pairs
are a RECONSTRUCTION of the E3 protocol (stride 5, step 2) plus the gate's reference-support rule.
The gap against 4.4145 / 4.8799 is reported with every run.
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
except ImportError as exc:  # pragma: no cover
    raise SystemExit("rosbag is required: run with /home/R26534/mm/ros/bin/python") from exc

from slam_recovery.validation import (
    compute_disjoint_holdout_point_to_plane_nis,
    evaluate_paired_sequential_benefit,
)

_DT = np.dtype({"names": ["x", "y", "z", "intensity", "time", "ring"],
                "formats": ["<f4", "<f4", "<f4", "<f4", "<f4", "<u2"],
                "offsets": [0, 4, 8, 12, 16, 20], "itemsize": 24})

THIN_THRESHOLDS = (0.03, 0.05, 0.07, 0.10)
SIGMA_COMPUTE = 0.25          # every row is computed once here and rescaled


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


# Scanning a 1.5 GB ROS1 bag takes minutes; these caches were built once from the same bags with
# the same topics and range filter. Delete them to force a re-read.
_SCAN_CACHE = {
    "/tmp/unseen_val/street_08_pbag_deg.bag": "/tmp/scans_s08_deg.npz",
    "/tmp/unseen_val/street_08_fl.bag": "/tmp/scans_s08_fl.npz",
    "/tmp/unseen_val/room_dark_02_fl.bag": "/tmp/scans_room02.npz",
}


def read_scans(path: str, topic: str = "/velodyne_points", rmin: float = 0.8, rmax: float = 25.0):
    cache = _SCAN_CACHE.get(path)
    if cache and os.path.exists(cache):
        z = np.load(cache)
        ts, pts, offs = z["ts"], z["pts"], z["offs"]
        return [(float(ts[i]), pts[offs[i]:offs[i + 1]]) for i in range(len(ts))]
    out = []
    with rosbag.Bag(path, "r") as b:
        for _, m, _ in b.read_messages(topics=[topic]):
            arr = np.frombuffer(m.data, dtype=_DT)
            pts = np.column_stack([arr["x"], arr["y"], arr["z"]]).astype(np.float64)
            rad = np.linalg.norm(pts, axis=1)
            out.append((_stamp_sec(m), pts[(rad > rmin) & (rad < rmax)]))
    return out


def _support_fraction(ref: np.ndarray, query: np.ndarray, radius: float = 1.0) -> float:
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


def _pair_arrays(ref_pts, cur_pts, T):
    """The estimator's own sub-sample and 8-NN fit; returns residuals and plane geometry."""
    ref = np.asarray(ref_pts, dtype=np.float64)[:, :3]
    cur = np.asarray(cur_pts, dtype=np.float64)[:, :3]
    if len(ref) < 30 or len(cur) < 10:
        return None
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
    resid = np.abs(np.sum(eigvecs[:, :, 0] * (h_sub - mean_nn), axis=1))
    thinness = np.sqrt(np.maximum(l0, 0.0)) / np.maximum(np.sqrt(np.maximum(l1, 1e-12)), 1e-12)
    radius = np.sqrt(np.max(d2[np.arange(len(h_sub))[:, None], nn], axis=1))
    return {"resid": resid, "thinness": thinness, "radius": radius, "l0": l0,
            "n_ref": len(t_sub), "n_hold": len(h_sub)}


def pair_diagnostics(ref_pts, cur_pts, T, sigma: float = SIGMA_COMPUTE) -> dict:
    a = _pair_arrays(ref_pts, cur_pts, T)
    if a is None:
        return {"scored": False}
    resid, thinness = a["resid"], a["thinness"]
    coverage = float(np.mean(resid < 2.0))
    keep = np.ones(len(resid), dtype=bool) if coverage < 0.70 else (resid < 2.0)
    used = resid[keep]
    thin_k = thinness[keep]
    nis = (resid / sigma) ** 2
    nis_used = (used / sigma) ** 2
    out = {
        "scored": True,
        "sigma_computed_at": sigma,
        "mean_sq_residual": float(np.mean(used ** 2)),
        "nis_estimator": float(compute_disjoint_holdout_point_to_plane_nis(
            ref_pts, cur_pts, T, sigma_meas_m=sigma)),
        "nis_median_pooled": float(np.median(nis)),
        "nis_mean_pooled": float(np.mean(nis_used)),
        "nn_radius_m_mean": float(np.mean(a["radius"])),
        "plane_thickness_rms_m_median": float(np.median(np.sqrt(np.maximum(a["l0"], 0.0)))),
        "residual_abs_median_m": float(np.median(resid)),
        "residual_frac_gt_0p5m": float(np.mean(resid > 0.5)),
    }
    for thr in THIN_THRESHOLDS:
        thin = thin_k <= thr
        out[f"thin_frac_{thr}"] = float(np.mean(thinness <= thr))
        out[f"nis_thin_{thr}"] = float(np.mean(nis_used[thin])) if thin.any() else None
        out[f"nis_mixed_{thr}"] = float(np.mean(nis_used[~thin])) if (~thin).any() else None
    return out


def _boot_ci(values, n_boot: int = 2000, seed: int = 0):
    v = np.asarray([x for x in values if x is not None and np.isfinite(x)], dtype=np.float64)
    if len(v) == 0:
        return None
    rng = np.random.default_rng(seed)
    means = v[rng.integers(0, len(v), size=(n_boot, len(v)))].mean(axis=1)
    return [float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))]


def _aggregate(rows, sigma: float, thin_thr: float = 0.05) -> dict:
    """Rescale the sigma=0.25 rows to `sigma` (NIS is exactly proportional to 1/sigma^2)."""
    ok = [r for r in rows if r.get("scored")]
    if not ok:
        return {"n_pairs_scored": 0}
    scale = (SIGMA_COMPUTE / sigma) ** 2

    def stat(key):
        v = []
        for r in ok:
            x = r.get(key)
            if x is None:
                continue
            if key.startswith("nis"):
                x *= scale
            if np.isfinite(x):
                v.append(x)
        if not v:
            return {"mean": None, "median": None, "ci95": None}
        return {"mean": float(np.mean(v)), "median": float(np.median(v)), "ci95": _boot_ci(v)}

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
            "thin_only_mean": t["mean"], "thin_only_ci95": t["ci95"],
            "passes_tau_2p5": (t["mean"] is not None and t["mean"] <= 2.5),
            "ci_entirely_below_tau": (t["ci95"] is not None and t["ci95"][1] <= 2.5),
        }
    est, th = out["nis_estimator"]["mean"], out["nis_thin_only"]["mean"]
    out["verdict_at_tau_2p5"] = None if est is None else ("FAILED" if est > 2.5 else "PASSED")
    out["verdict_thin_only_at_tau_2p5"] = None if th is None else ("FAILED" if th > 2.5 else "PASSED")
    return out


def calibrate_sigma(pairs, label: str) -> dict:
    """Noise scale of a CLEAN run under the same S_{k-5}->S_k protocol."""
    per_pair_sq, all_used, all_raw = [], [], []
    for *_, ref, cur, T in pairs:
        a = _pair_arrays(ref, cur, T)
        if a is None:
            continue
        resid = a["resid"]
        used = resid if np.mean(resid < 2.0) < 0.70 else resid[resid < 2.0]
        per_pair_sq.append(float(np.mean(used ** 2)))
        all_used.append(used)
        all_raw.append(resid)
    if not per_pair_sq:
        return {"label": label, "n_pairs": 0}
    used = np.concatenate(all_used)
    raw = np.concatenate(all_raw)
    mean_sq = float(np.mean(per_pair_sq))
    sigma_star = float(np.sqrt(mean_sq))
    med = float(np.median(used))
    # Half-split transfer: sigma* fitted on one half of the pairs, NIS evaluated on the other.
    # This is what makes sigma* an EMPIRICAL NORMALISATION SCALE rather than a noise model: it says
    # "this window's residuals have this RMS", not "the residuals are chi-square with this sigma".
    sq = np.asarray(per_pair_sq, dtype=np.float64)
    transfer = {}
    if len(sq) >= 20:
        for tag, fit, val in (("even_fit_odd_eval", sq[::2], sq[1::2]),
                              ("odd_fit_even_eval", sq[1::2], sq[::2])):
            s_fit = float(np.sqrt(np.mean(fit)))
            transfer[tag] = {
                "sigma_star_fit_half": s_fit,
                "nis_on_other_half": float(np.mean(val) / s_fit ** 2),
            }
    return {
        "label": label,
        "n_pairs": len(per_pair_sq),
        "split_half_transfer": transfer,
        "definition": "sigma* = sqrt(mean_over_pairs(mean_over_points(r^2))); an empirical "
                      "normalisation scale. The transfer check below is an interleaved even/odd "
                      "PAIR split inside one window, not two disjoint time intervals: adjacent "
                      "folds share scan endpoints and are temporally correlated, so it shows the "
                      "residual scale is stable within the window, not that it generalises across "
                      "windows or sequences. NOT a per-frame chi-square noise model.",
        "n_residuals_used": int(len(used)),
        "sigma_star_rms": sigma_star,
        "sigma_robust_mad": 1.4826 * float(np.median(np.abs(used - med))),
        "std_residual_m": float(np.std(used)),
        "p68_abs_residual_m": float(np.percentile(np.abs(used), 68)),
        "abs_p50": float(np.percentile(np.abs(used), 50)),
        "abs_p90": float(np.percentile(np.abs(used), 90)),
        "abs_p95": float(np.percentile(np.abs(used), 95)),
        "abs_p99": float(np.percentile(np.abs(used), 99)),
        "frac_abs_gt_0p15m": float(np.mean(raw > 0.15)),
        "frac_abs_gt_0p5m": float(np.mean(raw > 0.5)),
        "frac_abs_gt_2p0m": float(np.mean(raw > 2.0)),
        "mean_sq_residual_m2": mean_sq,
        "clean_nis": {f"{name}": {"sigma": float(v), "nis": mean_sq / float(v) ** 2,
                                  "verdict": "FAILED" if mean_sq / float(v) ** 2 > 2.5 else "PASSED"}
                      for name, v in (("sigma_star", sigma_star), ("gate_0.12", 0.12),
                                      ("evaluator_0.25", 0.25))},
    }


def _pairs_from_odom(scans, ts_o, xyz_o, q_o, stride=5, step=2, support=True, frame="world"):
    """Build S_{k-stride} -> S_k pairs in ONE frame.

    Convention (matches evaluate_room_dark_02.py): every scan is rotated by its own pose into world
    axes, and the translation between the two scans is the WORLD position difference. The
    alternative below ("body") rotates the displacement back into the reference body frame while
    leaving the clouds world-oriented; that is a frame mix and is only kept so the analytic check
    can demonstrate it.
    """
    rec = []
    for sec, pts in scans:
        i = int(np.argmin(np.abs(ts_o - sec)))
        R = quat_to_rot(q_o[i])
        rec.append((sec, pts @ R.T, i, R))
    pairs = []
    for k in range(stride, len(rec), step):
        sec_ref, ref, i_ref, R_ref = rec[k - stride]
        _, cur, i_cur, _ = rec[k]
        d_world = xyz_o[i_cur] - xyz_o[i_ref]
        d = d_world if frame == "world" else (R_ref.T @ d_world)
        if support:
            q = cur[:: max(1, len(cur) // 200)][:200]
            # 2000 reference points are enough for a 60 % coverage decision and keep the probe
            # from doing a 200 x 37k distance test per pair
            ref_test = ref if len(ref) <= 2000 else ref[:: max(1, len(ref) // 2000)][:2000]
            if _support_fraction(ref_test, q + d, 1.0) < 0.60:
                continue
        T = np.eye(4)
        T[:3, 3] = d
        pairs.append((sec_ref, ref, cur, T))
    return pairs



def analytic_frame_check(sigma: float = 0.25) -> dict:
    """90-degree yaw + a known translation, against an analytically predictable residual.

    Three separated planar patches, each lying in one coordinate plane:
        A: 40 points in x = 0   (normal +x)
        B: 10 points in y = 0   (normal +y)
        C: 50 points in z = 0   (normal +z)
    The vehicle is rotated 90 deg about z. Its true world displacement is d = (0.2, 0, 0), so the
    transformed holdout points move along world x:
        patch A -> residual |d| on the x-plane, B and C -> 0
    mean NIS = (40/100) * (0.2/sigma)^2.
    The body-frame variant rotates d into the reference body axes and therefore shifts the points
    along world -y instead:
        patch B -> residual |d|, A and C -> 0
    mean NIS = (10/100) * (0.2/sigma)^2.
    The two conventions agree only at yaw = 0.
    """
    rng = np.random.default_rng(0)

    def patch(axis: int, value: float, centre, n: int):
        p = np.tile(np.asarray(centre, float), (n, 1))
        p += rng.normal(0.0, 0.02, p.shape)
        p[:, axis] = value
        return p

    ref = np.vstack([patch(0, 0.0, (0.0, 5.0, 0.0), 40),
                     patch(1, 0.0, (5.0, 0.0, 0.0), 10),
                     patch(2, 0.0, (5.0, 5.0, 0.0), 50)])
    d_true = np.array([0.2, 0.0, 0.0])
    yaw = np.pi / 2
    R = np.array([[np.cos(yaw), -np.sin(yaw), 0.0],
                  [np.sin(yaw), np.cos(yaw), 0.0],
                  [0.0, 0.0, 1.0]])

    # holdout = the same points; the candidate translation is carried entirely by T (the estimator
    # applies T to the holdout, so pre-shifting here would double the displacement)
    cur_world = ref.copy()
    out = {}
    for name, d in (("world", d_true), ("body", R.T @ d_true)):
        T = np.eye(4)
        T[:3, 3] = d
        out[name] = float(compute_disjoint_holdout_point_to_plane_nis(
            ref, cur_world, T, sigma_meas_m=sigma))
    expected = {
        "world": 0.40 * (0.2 / sigma) ** 2,
        "body": 0.10 * (0.2 / sigma) ** 2,
    }
    return {
        "expected": expected,
        "measured": out,
        "world_matches": abs(out["world"] - expected["world"]) <= 0.05 * expected["world"],
        "body_is_wrong_by_factor": (out["body"] / out["world"]) if out["world"] else None,
        "sigma": sigma,
        "note": "at yaw = 0 both conventions coincide; the divergence needs a non-zero yaw",
    }


def street_08(inject_window=(50.0, 70.0), documented_reentry_jump=0.4042):
    V = "/tmp/unseen_val"
    scans = read_scans(f"{V}/street_08_pbag_deg.bag")
    scans_clean = read_scans(f"{V}/street_08_fl.bag")
    t_start = scans[0][0]

    # Clean-run sigma FIRST: the candidate must be judged on a scale it did not define.
    cal = {}
    for name, bag, topic in (("mm_lins_clean", f"{V}/res_mm_street08_clean.bag", "/Odometry"),
                             ("lio_sam_clean", f"{V}/res_lio_street08_clean.bag",
                              "/lio_sam/mapping/odometry")):
        try:
            ts_c, xyz_c, q_c = read_odom(bag, topic)
            cal[name] = calibrate_sigma(_pairs_from_odom(scans_clean, ts_c, xyz_c, q_c), name)
            print(f"[street_08] clean {name}: sigma*={cal[name].get('sigma_star_rms')}", flush=True)
        except Exception as exc:                       # noqa: BLE001
            cal[name] = {"label": name, "error": str(exc)}
    clean_sigma = cal.get("mm_lins_clean", {}).get("sigma_star_rms") or \
        cal.get("lio_sam_clean", {}).get("sigma_star_rms")

    out = {"series": {}, "arms": {}, "odometry_variants": {}, "sigma_calibration": cal,
           "clean_sigma_used": clean_sigma}

    for tag, bag in (("B2_degraded_native", f"{V}/res_lio_street08_pbag_deg.bag"),
                     ("B6_repaired", f"{V}/res_lio_street08_pbag_rep.bag")):
        ts_o, xyz_o, q_o = read_odom(bag)
        pairs = _pairs_from_odom(scans, ts_o, xyz_o, q_o)
        rows = [pair_diagnostics(r, c, T) for _, r, c, T in pairs]
        arm_rms = float(np.sqrt(np.mean([r["mean_sq_residual"] for r in rows if r["scored"]])))
        print(f"[street_08] {tag}: {len(rows)} pairs, arm-rms={arm_rms:.4f}", flush=True)
        block = {"at_0.25": _aggregate(rows, 0.25),
                 "at_0.12": _aggregate(rows, 0.12),
                 "at_arm_rms": _aggregate(rows, arm_rms),
                 "arm_rms_sigma": arm_rms}
        if clean_sigma:
            block["at_clean_sigma"] = _aggregate(rows, clean_sigma)
        for label, inside in (("inside_injection_window", True), ("outside_injection_window", False)):
            sub = [row for row, (tr, _, _, _) in zip(rows, pairs)
                   if (inject_window[0] <= tr - t_start <= inject_window[1]) == inside]
            g = {"at_0.25": _aggregate(sub, 0.25), "n_pairs": len(sub)}
            if clean_sigma:
                g["at_clean_sigma"] = _aggregate(sub, clean_sigma)
            block[label] = g
        out["arms"][tag] = block
        out["series"][tag] = {
            "t_rel_s": [float(tr - t_start) for tr, _, _, _ in pairs],
            "nis_sigma_0.25": [r["nis_estimator"] for r in rows],
            "sigma_star": clean_sigma or arm_rms,
        }

    # odometry-density variants: the published 4.4145 does not record which recording produced it
    for name, path in (("lio_deg_base", f"{V}/res_lio_street08_pbag_deg.bag"),
                       ("lio_deg_1x", f"{V}/res_lio_street08_pbag_deg_1x.bag"),
                       ("lio_rep_base", f"{V}/res_lio_street08_pbag_rep.bag"),
                       ("lio_rep_1x", f"{V}/res_lio_street08_pbag_rep_1x.bag")):
        try:
            ts_o, xyz_o, q_o = read_odom(path)
            pr = _pairs_from_odom(scans, ts_o, xyz_o, q_o)
            rows = [pair_diagnostics(r, c, T) for _, r, c, T in pr]
            agg = _aggregate(rows, 0.25)
            out["odometry_variants"][name] = {
                "n_odom": int(len(ts_o)), "n_pairs": agg["n_pairs_scored"],
                "nis_at_0.25": agg["nis_estimator"]["mean"],
                "ci95": agg["nis_estimator"]["ci95"],
            }
            print(f"[street_08] variant {name}: {len(ts_o)} odom", flush=True)
        except Exception as exc:                       # noqa: BLE001
            out["odometry_variants"][name] = {"error": str(exc)}

    # Wilson lower bound: scale free, so it must not move with sigma
    ts_deg, xyz_deg, q_deg = read_odom(f"{V}/res_lio_street08_pbag_deg.bag")
    ts_rep, xyz_rep, q_rep = read_odom(f"{V}/res_lio_street08_pbag_rep.bag")
    p_deg = _pairs_from_odom(scans, ts_deg, xyz_deg, q_deg, support=False)
    p_rep = _pairs_from_odom(scans, ts_rep, xyz_rep, q_rep, support=False)
    n = min(len(p_deg), len(p_rep))
    inc = np.array([pair_diagnostics(r, c, T)["nis_estimator"] for _, r, c, T in p_deg[:n]])
    cand = np.array([pair_diagnostics(r, c, T)["nis_estimator"] for _, r, c, T in p_rep[:n]])
    wilson = {}
    for label, scale in (("at_0.25", 1.0), ("at_0.12", (0.25 / 0.12) ** 2),
                         ("at_clean_sigma", (0.25 / clean_sigma) ** 2 if clean_sigma else 1.0)):
        rep = evaluate_paired_sequential_benefit(
            inc * scale, cand * scale,
            reentry_position_jump_m=documented_reentry_jump,
            min_relative_gain_per_frame=0.01)
        wilson[label] = {"wilson_lower_bound": float(rep.wilson_lower_bound),
                         "approved": bool(rep.approved)}
    out["wilson"] = {"n_pairs": int(n), "reentry_jump_m_used": documented_reentry_jump,
                     "note": "0.4042 is the archived value; the trajectory that produced it is "
                             "not on disk, so it cannot be recomputed here",
                     "by_sigma": wilson}
    out["published_reference"] = {"cross_scan_nis_mean_b2": 4.8799,
                                  "cross_scan_nis_mean_b6": 4.4145,
                                  "wilson_lower_bound": 0.4626, "sigma_meas_m": 0.25}
    b6 = out["arms"]["B6_repaired"]["at_0.25"]["nis_estimator"]["mean"]
    out["reproduction_gap_b6"] = None if b6 is None else round(float(b6) - 4.4145, 4)
    return out


def room_dark_02():
    """Mirror evaluate_room_dark_02.py: S_{k-5}->S_k over [t0+15, t0+38], sigma 0.25."""
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
        return {"reproducible": False, "reason": "calibration window empty", "n_cal": int(cal.sum())}
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
        rec.append((sec, pts @ quat_to_rot(q_fl[i]).T, int(np.argmin(np.abs(cam_ts - sec)))))

    cal_all = {"fastlio_clean": calibrate_sigma(_pairs_from_odom(raw, ts_fl, xyz_fl, q_fl),
                                               "fastlio_clean")}
    # Second clean source: ORB-SLAM3 B0 (the host whose NIS the paper quotes), aligned the same way
    try:
        ts_b0, xyz_b0, _ = load_tum_trajectory_se3(os.path.join(traj, "raw_b0_real_CameraTrajectory.txt"))
        iu = np.argsort(ts_b0)
        ts_b0, xyz_b0 = ts_b0[iu], xyz_b0[iu]
        b0_full = np.column_stack([np.interp(cam_ts, ts_b0, xyz_b0[:, d]) for d in range(3)])
        R_b0, t_b0, s_b0 = umeyama_se3_align(b0_full[cal], aux[cal], with_scale=True)
        xyz_b0_in_l = (s_b0 * (b0_full @ R_b0.T)) + t_b0
        pairs_b0 = []
        for k in range(5, len(rec), 2):
            _, ref, i_ref = rec[k - 5]
            _, cur, i_cur = rec[k]
            T = np.eye(4)
            T[:3, 3] = xyz_b0_in_l[i_cur] - xyz_b0_in_l[i_ref]
            pairs_b0.append((None, ref, cur, T))
        cal_all["orb_b0_clean"] = calibrate_sigma(pairs_b0, "orb_b0_clean")
    except Exception as exc:                            # noqa: BLE001
        cal_all["orb_b0_clean"] = {"label": "orb_b0_clean", "error": str(exc)}
    clean = cal_all["fastlio_clean"]
    clean_sigma = clean.get("sigma_star_rms")
    print(f"[room_dark_02] clean sigma*={clean_sigma}", flush=True)

    out = {"series": {}, "arms": {}, "sigma_calibration": cal_all,
           "clean_sigma_used": clean_sigma}
    per_arm_nis = {}
    for tag, xyz in (("B2_native", (s_o2l * (b2_full @ R_o2l.T)) + t_o2l),
                     ("B6_offline_construct", (s_o2l * (b6 @ R_o2l.T)) + t_o2l)):
        pairs, pair_t = [], []
        for k in range(5, len(rec), 2):
            sec_cur, ref, i_ref = rec[k - 5]
            sec_cur, cur, i_cur = rec[k]
            T = np.eye(4)
            T[:3, 3] = xyz[i_cur] - xyz[i_ref]
            pairs.append((ref, cur, T))
            pair_t.append(float(sec_cur - t0))
        rows = [pair_diagnostics(r, c, T) for r, c, T in pairs]
        per_arm_nis[tag] = [r["nis_estimator"] for r in rows]
        arm_rms = float(np.sqrt(np.mean([r["mean_sq_residual"] for r in rows if r["scored"]])))
        block = {"at_0.25": _aggregate(rows, 0.25), "at_0.12": _aggregate(rows, 0.12),
                 "at_arm_rms": _aggregate(rows, arm_rms), "arm_rms_sigma": arm_rms}
        if clean_sigma:
            block["at_clean_sigma"] = _aggregate(rows, clean_sigma)
        out["arms"][tag] = block
        out["series"][tag] = {
            "t_rel_s": pair_t,
            "nis_sigma_0.25": per_arm_nis[tag], "sigma_star": clean_sigma or arm_rms}

    idx = int(np.searchsorted(cam_ts, t_q1))
    idx = min(max(idx, 1), len(b6) - 1)
    jump = float(np.linalg.norm(b6[idx] - b6[idx - 1]))
    inc = np.asarray(per_arm_nis["B2_native"])
    cand = np.asarray(per_arm_nis["B6_offline_construct"])
    wil = {}
    for label, scale in (("at_0.25", 1.0), ("at_0.12", (0.25 / 0.12) ** 2),
                         ("at_clean_sigma", (0.25 / clean_sigma) ** 2 if clean_sigma else 1.0)):
        rep = evaluate_paired_sequential_benefit(
            inc * scale, cand * scale, reentry_position_jump_m=jump,
            min_relative_gain_per_frame=0.01)
        wil[label] = {"wilson_lower_bound": float(rep.wilson_lower_bound),
                      "approved": bool(rep.approved)}
    out["wilson"] = {"n_pairs": int(len(inc)), "reentry_jump_m": jump, "by_sigma": wil}

    out["published_reference"] = {"cross_scan_holdout_nis_b2": 0.9097,
                                  "cross_scan_holdout_nis_b6": 0.6532,
                                  "wilson_lower_bound": 0.9235, "sigma_meas_m": 0.25}
    got = out["arms"]["B6_offline_construct"]["at_0.25"]["nis_estimator"]["mean"]
    out["reproduction_gap_b6"] = None if got is None else round(float(got) - 0.6532, 4)
    return out


def _show_arm(name, arm):
    for key in ("at_0.25", "at_0.12", "at_arm_rms", "at_clean_sigma"):
        s = arm.get(key)
        if not s or not s.get("nis_estimator"):
            continue
        e, t, m = s["nis_estimator"], s["nis_thin_only"], s["nis_mixed_only"]
        lo, hi = e["ci95"]
        thin = "-" if t["mean"] is None else f"{t['mean']:8.3f}"
        mixed = "-" if m["mean"] is None else f"{m['mean']:8.2f}"
        print(f"  {name:22s} {key:14s} sigma={s['sigma_meas_m']:.4f} pairs={s['n_pairs_scored']:4d} "
              f"NIS={e['mean']:8.3f}[{lo:7.3f},{hi:7.3f}] thin={thin} mixed={mixed} "
              f"thin%={100*s['thin_fraction']['mean']:5.1f} V={s['verdict_at_tau_2p5']}")
    for key in ("inside_injection_window", "outside_injection_window"):
        g = arm.get(key)
        if not g:
            continue
        for sk, s in g.items():
            if not isinstance(s, dict) or not s.get("nis_estimator"):
                continue
            print(f"  {name:22s} {key}/{sk:12s} pairs={s['n_pairs_scored']:4d} "
                  f"NIS={s['nis_estimator']['mean']:8.3f} thin={s['nis_thin_only']['mean']:8.3f} "
                  f"thin%={100*s['thin_fraction']['mean']:5.1f}")


def _show_calibration(seq, cal):
    print(f"\n  sigma calibration [{seq}] — clean run, same protocol")
    for name, c in cal.items():
        if c.get("error") or not c.get("n_pairs"):
            print(f"    {name}: unavailable ({c.get('error', 'no pairs')})")
            continue
        print(f"    {name:18s} pairs={c['n_pairs']:4d} sigma*={c['sigma_star_rms']:.4f} "
              f"sigma_robust={c['sigma_robust_mad']:.4f} std={c['std_residual_m']:.4f} "
              f"p68={c['p68_abs_residual_m']:.4f}")
        print(f"      |r| p50/p90/p95/p99 = {c['abs_p50']:.3f}/{c['abs_p90']:.3f}/"
              f"{c['abs_p95']:.3f}/{c['abs_p99']:.3f}   "
              f">0.15/0.5/2.0m = {c['frac_abs_gt_0p15m']:.3f}/{c['frac_abs_gt_0p5m']:.3f}/"
              f"{c['frac_abs_gt_2p0m']:.3f}")
        for tag, t in c.get("split_half_transfer", {}).items():
            print(f"      split {tag:18s} sigma*_fit={t['sigma_star_fit_half']:.4f} "
                  f"-> NIS on held-out half {t['nis_on_other_half']:.3f}")
        for k, v in c["clean_nis"].items():
            print(f"      clean NIS @ {k:14s} sigma={v['sigma']:.4f} -> {v['nis']:.3f} ({v['verdict']})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/tmp/real_plane_mix.json")
    args = ap.parse_args()

    frame_check = analytic_frame_check()
    print("\n== analytic frame check (90 deg yaw, d=(0.2,0,0), sigma=0.25) ==")
    print(f"  expected world {frame_check['expected']['world']:.4f} / body "
          f"{frame_check['expected']['body']:.4f}  ->  measured "
          f"{frame_check['measured']['world']:.4f} / {frame_check['measured']['body']:.4f}"
          f"  world_ok={frame_check['world_matches']}")
    res = {"frame_check": frame_check,
           "street_08": street_08(), "room_dark_02": room_dark_02()}
    for seq in ("street_08", "room_dark_02"):
        print(f"\n===== {seq} =====")
        for tag, arm in res[seq].get("arms", {}).items():
            _show_arm(tag, arm)
        _show_calibration(seq, res[seq].get("sigma_calibration", {}))
        if "wilson" in res[seq]:
            w = res[seq]["wilson"]
            rj = w.get("reentry_jump_m", w.get("reentry_jump_m_used"))
            print(f"  wilson: n={w['n_pairs']} reentry={rj:.4f}m -> "
                  + ", ".join(f"{k}:{v['wilson_lower_bound']:.4f}/{v['approved']}"
                              for k, v in w["by_sigma"].items()))
        if "odometry_variants" in res[seq]:
            print("  odometry variants @ sigma 0.25:")
            for k, v in res[seq]["odometry_variants"].items():
                print(f"    {k:16s} {v}")
        print("  reproduction gap vs published:", res[seq].get("reproduction_gap_b6"))
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2, ensure_ascii=False)
    print("\nsaved", args.out)
