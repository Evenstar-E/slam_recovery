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


def nis_param(train, hold, sigma=0.12, ref_cap=600, hold_cap=300, k=8):
    """Clone of compute_disjoint_holdout_point_to_plane_nis with the caps exposed.

    The 2.0 m inlier truncation and the 0.70 coverage gate are part of the production estimator
    (validation/fim_and_holdout.py:143-149). Omitting them reports the untruncated mean square,
    which is dominated by tail residuals and is not the number the gate sees.
    """
    tr = np.asarray(train, dtype=np.float64)[:, :3]
    ho = np.asarray(hold, dtype=np.float64)[:, :3]
    if len(tr) < 30 or len(ho) < 10:
        return float("inf"), 0, float("nan"), np.zeros(0), 0.0
    t_sub = tr[:: max(1, len(tr) // ref_cap)][:ref_cap]
    h_sub = ho[:: max(1, len(ho) // hold_cap)][:hold_cap]
    d = np.sum((h_sub[:, None, :] - t_sub[None, :, :]) ** 2, axis=-1)
    kk = min(k, len(t_sub) - 1)
    idx = np.argpartition(d, kth=kk, axis=1)[:, :kk]
    nb = t_sub[idx]
    mu = nb.mean(axis=1)
    cen = nb - mu[:, None, :]
    cov = np.einsum("mki,mkj->mij", cen, cen) / float(kk)
    _, ev = np.linalg.eigh(cov)
    res = np.abs(np.sum(ev[:, :, 0] * (h_sub - mu), axis=1))
    nn_radius = float(np.mean(np.sqrt(np.take_along_axis(d, idx, axis=1).mean(axis=1))))
    valid = res[res < 2.0]
    inlier_coverage = float(len(valid)) / float(max(len(res), 1))
    if len(valid) == 0 or inlier_coverage < 0.70:
        return (float(np.mean((res / sigma) ** 2)), len(t_sub), nn_radius, res,
                inlier_coverage)
    return float(np.mean((valid / sigma) ** 2)), len(t_sub), nn_radius, res, inlier_coverage


def main():
    inj, _ = fa.pair_keyframes(fa.DEFAULT_INJ_SCANS, fa.DEFAULT_INJ_POSES, False)
    cln, _ = fa.pair_keyframes(fa.DEFAULT_CLN_SCANS, fa.DEFAULT_CLN_POSES, False)
    st, _en, ev = fa.detect_onset(fa.DEFAULT_CLN_SCANS, fa.DEFAULT_INJ_SCANS)
    print(f"onset = {st} .. {_en}  {ev.get('method')}")

    pre = [k for k in inj if k["rel"] < st]
    # Every post-onset frame, not just the injection window: that is what the node quarantines
    # (578 keyframes - 133 pre-onset = 445) and what the review table is built on.
    quar = [k for k in inj if k["rel"] >= st]

    # The trusted reference lives in the INJECTED run's world frame; the clean run has its own.
    # Carrying the clean pose over requires the same rigid transform the four-arm script uses,
    # fitted on the pre-onset overlap. Without it the query and the reference sit metres apart
    # and every NIS below is meaningless.
    cln_ts_all = np.asarray([k["ts"] for k in cln])
    cln_xyz_all = np.asarray([k["pose"][:3, 3] for k in cln])
    m_ts, m_i, m_c = fa.associate_trajectories(
        np.asarray([k["ts"] for k in pre]), np.asarray([k["pose"][:3, 3] for k in pre]),
        cln_ts_all, cln_xyz_all, 0.05)
    R_ic, t_ic, _ = fa.umeyama_se3_align(m_i, m_c, with_scale=False)
    T_inv = np.eye(4)
    T_inv[:3, :3] = R_ic.T
    T_inv[:3, 3] = -R_ic.T @ t_ic
    resid = np.linalg.norm(m_i @ R_ic.T + t_ic - m_c, axis=1)
    print(f"alignment on {len(resid)} pre-onset frames: "
          f"median={np.median(resid):.4f} m p95={np.percentile(resid, 95):.4f} m", flush=True)

    ref_pts = np.vstack([fa.world_points(k) for k in pre]) if pre else np.zeros((0, 3))
    print(f"pre={len(pre)} quar={len(quar)} ref_pts={len(ref_pts)}", flush=True)

    idx_cln = [int(np.argmin(np.abs(cln_ts_all - k["ts"]))) for k in quar]

    def pts_world(pts_body, T):
        return pts_body @ T[:3, :3].T + T[:3, 3]

    # The node scores only the frames its support check passes (0.30 m voxel reference, 1 m
    # radius, >= 60% of the scan covered). Averaging over every quarantine frame instead folds in
    # frames that have drifted metres outside the map, where "NIS against the trusted surface" has
    # no referent. That difference alone separates this probe's 917 from the published 18.07, so
    # both sets are reported.
    SUPPORT_VOXEL, SUPPORT_RADIUS, SUPPORT_MIN_FRAC = 0.30, 1.0, 0.60
    SUPPORT_SUBSAMPLE = 400
    support_ref = fa.voxel_downsample(ref_pts, SUPPORT_VOXEL)
    sgrid = fa.NearestGrid(support_ref, cell=SUPPORT_VOXEL)
    print(f"support reference: {len(ref_pts)} -> {len(support_ref)} at {SUPPORT_VOXEL} m", flush=True)

    names = ("raw_injected", "filtered_injected", "oracle_clean")
    per_frame = {n: {} for n in names}
    clouds_all = {n: {} for n in names}
    frame_support = {}
    dropped_frac = []

    for fi, (k, j) in enumerate(zip(quar, idx_cln)):
        T = T_inv @ cln[j]["pose"]              # the SAME clean pose for all three, injected frame
        raw = k["pts"]
        rng_all = np.linalg.norm(raw, axis=1)
        keep = ~((rng_all >= 4.0) & (rng_all <= 4.6))
        dropped_frac.append([float(1.0 - np.mean(keep)),
                             float(np.mean((rng_all >= 4.0) & (rng_all <= 4.6)))])
        step = max(1, len(raw) // SUPPORT_SUBSAMPLE)
        dmin = sgrid.query(raw[::step][:SUPPORT_SUBSAMPLE], max_r=2.0)
        frame_support[fi] = float(np.mean(dmin <= SUPPORT_RADIUS))
        for name, w in (("raw_injected", pts_world(raw, T)),
                        ("filtered_injected", pts_world(raw[keep], T)),
                        ("oracle_clean", pts_world(cln[j]["pts"], T))):
            if len(w) == 0:
                continue
            clouds_all[name][fi] = w
            per_frame[name][fi] = nis_param(ref_pts, w)
        if fi % 40 == 0:
            print(f"  frame {fi}/{len(quar)} support={frame_support[fi]:.3f}", flush=True)

    supported = [i for i in range(len(quar)) if frame_support.get(i, 0.0) >= SUPPORT_MIN_FRAC]
    subsets = {
        "all_quarantine_frames": list(range(len(quar))),
        "support_checked_frames": supported,
        "node_style_every_5th_supported": supported[::5],
    }
    print(f"supported {len(supported)}/{len(quar)} "
          f"(node-style subset {len(subsets['node_style_every_5th_supported'])})", flush=True)

    def _agg(name, frames, cap=None):
        nises, all_res, refs, radii = [], [], set(), []
        for i in frames:
            rec = per_frame[name].get(i)
            if rec is None:
                continue
            nis, nref, rad, res, _cov = rec
            if cap is not None:
                nis, nref, rad, res, _cov = nis_param(ref_pts, clouds_all[name][i], ref_cap=cap)
            if not np.isfinite(nis):
                continue
            nises.append(nis)
            all_res.append(res)
            refs.add(nref)
            if np.isfinite(rad):
                radii.append(rad)
        res = np.concatenate(all_res) if all_res else np.zeros(0)
        return {
            "frames_scored": len(nises),
            "nis_mean": round(float(np.mean(nises)), 3) if nises else None,
            "nis_median": round(float(np.median(nises)), 3) if nises else None,
            "residual_p50_m": round(float(np.percentile(res, 50)), 4) if len(res) else None,
            "residual_p90_m": round(float(np.percentile(res, 90)), 4) if len(res) else None,
            "residual_p95_m": round(float(np.percentile(res, 95)), 4) if len(res) else None,
            "residual_p99_m": round(float(np.percentile(res, 99)), 4) if len(res) else None,
            "mean_support_fraction_lt_1m": (
                round(float(np.mean([frame_support[i] for i in frames if i in frame_support])), 4)
                if frames else None),
            "estimator_reference_points_used": sorted(refs),
            "mean_nn_radius_m": round(float(np.mean(radii)), 4) if radii else None,
        }

    out = {"onset": {"start_rel_sec": round(float(st), 3), "end_rel_sec": round(float(_en), 3),
                     "differing_frames": ev.get("differing_frames")},
           "n_frames": len(quar), "reference_points": int(len(ref_pts)),
           "cross_run_alignment": {
               "fitted_on": "pre-onset overlap of the two trajectories",
               "frames": int(len(resid)),
               "residual_median_m": round(float(np.median(resid)), 4) if len(resid) else None,
               "residual_p95_m": round(float(np.percentile(resid, 95)), 4) if len(resid) else None,
               "note": ("clean poses are carried into the injected frame by T_inv; without this "
                        "the reference and the queries are in two different world frames"),
           },
           "filter_rule": "drop returns with range in [4.0, 4.6] m (the injected sheet shell)",
           "support_check": {
               "voxel_m": SUPPORT_VOXEL, "radius_m": SUPPORT_RADIUS,
               "min_fraction": SUPPORT_MIN_FRAC, "subsample_per_frame": SUPPORT_SUBSAMPLE,
               "supported_frames": len(supported),
               "source": "slam_recovery/sim/transaction_manager_node.py::_frame_has_reference_support",
           },
           "shell_fraction_per_frame": {
               "mean": round(float(np.mean([d[1] for d in dropped_frac])), 4) if dropped_frac else None,
               "median": round(float(np.median([d[1] for d in dropped_frac])), 4) if dropped_frac else None,
               "p90": round(float(np.percentile([d[1] for d in dropped_frac], 90)), 4) if dropped_frac else None,
           },
           "observations": {}, "budget_sweep_support_checked": {}}

    for subset, frames in subsets.items():
        out["observations"][subset] = {name: _agg(name, frames) for name in names}
        for name in names:
            row = out["observations"][subset][name]
            print(f"[{subset}] {name:20s} nis_mean={row['nis_mean']} "
                  f"nis_med={row['nis_median']} p50={row['residual_p50_m']} "
                  f"p99={row['residual_p99_m']} frames={row['frames_scored']} "
                  f"nn_r={row['mean_nn_radius_m']}", flush=True)

    for cap in (600, 1200, 2400):
        out["budget_sweep_support_checked"][f"ref_cap_{cap}"] = {
            name: _agg(name, supported, cap=cap)["nis_mean"] for name in names}
        print(f"budget ref_cap={cap} (support-checked): "
              f"{out['budget_sweep_support_checked'][f'ref_cap_{cap}']}", flush=True)

    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "three_observation_nis_probe.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(fa.json_safe(out), f, indent=2, allow_nan=False)
    print("wrote", path)


if __name__ == "__main__":
    main()
