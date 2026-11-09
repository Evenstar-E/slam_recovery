#!/usr/bin/env python3
"""Independent recomputation of the four-arm contamination numbers (reviewer request).

The archived manifest (``four_arm_same_input_benchmark.json``) reports, for the same input:

    A0 / A2 (write everything, 578 keyframes)   tail>0.5 m = 0.3647   coverage@0.5 m = 0.9496
    A1 / A3 (quarantine only, 133 keyframes)    tail>0.5 m = 0.0079   coverage@0.5 m = 0.9199

This script recomputes those four numbers without calling the producer's ``NearestGrid`` or
``distance_stats``.  What is *shared* with the producer, because the task asks for the same
protocol, is the protocol: same bag inputs (checked by sha256), same scan filtering, same
scan->pose pairing rules, same keyframe point cap, same 120 000-point proxy cap, same pre-onset
SE(3) alignment target.  What is *not* shared:

  * bag parsing   -- rosbags + the message's own PointField layout, not the hard-coded 24-byte
                     VelodynePointXYZIR ``np.dtype``;
  * nearest neighbour -- ``scipy.spatial.cKDTree``, not a hand-written hash grid;
  * alignment     -- own Umeyama SVD, cross-checked against the manifest's residual table;
  * statistics    -- own tail/coverage/bootstrap, cross-checked against the archived CIs.

Run with the system python (has numpy, scipy, rosbags):

    python3 -B docs/review_20261109_bbc3dcb/verify_four_arm_independent.py

Notes on independence that the report must carry: this is a *reimplementation* check, not new
data.  It can catch implementation errors and sampling artefacts in the producer; it cannot make
the underlying replay independent of the archived host poses.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys

import numpy as np
from rosbags.rosbag1 import Reader
from rosbags.typesys import Stores, get_typestore
from scipy.spatial import cKDTree

TYPESTORE = get_typestore(Stores.ROS1_NOETIC)
CACHE = "/tmp/fourarm_cache"
MANIFEST = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "slam_recovery", "experiments", "manifests", "four_arm_same_input_benchmark.json")

INJ_SCANS = "/tmp/fastlivo/hall01_inj43.bag"
INJ_POSES = "/tmp/fastlivo/res_h1_inj43_vis.bag"
CLN_SCANS = "/tmp/fastlivo/hall01_100_160.bag"
CLN_POSES = "/tmp/fastlivo/res_hall01_clean_05x.bag"

SCAN_TOPIC = "/velodyne_points"
POSE_TOPIC = "/aft_mapped_to_init"
RMIN, RMAX = 0.5, 30.0
MAX_KF_POINTS = 15000
KF_CAP = 250
NEAR_DT = 0.020
MAX_GAP = 0.075
PROXY_CAP = 120000
COV_Q = 40000
SEARCH_R = 2.5
THRESHOLDS = (0.25, 0.5, 1.0, 2.0)

_PF = {1: "i1", 2: "u1", 3: "i2", 4: "u2", 5: "i4", 6: "u4", 7: "f4", 8: "f8"}


# --------------------------------------------------------------------------------------- bags
def _cloud_dtype(msg):
    """Structured dtype from the message's own PointField table (not a hard-coded layout)."""
    end = ">" if msg.is_bigendian else "<"
    names, formats, offsets = [], [], []
    for f in msg.fields:
        names.append(f.name)
        formats.append(end + _PF[int(f.datatype)])
        offsets.append(int(f.offset))
    return np.dtype({"names": names, "formats": formats, "offsets": offsets,
                     "itemsize": int(msg.point_step)})


def load_scans(path):
    """[(header_stamp_sec, xyz float64 filtered to 0.5..30 m and capped)] sorted by stamp."""
    os.makedirs(CACHE, exist_ok=True)
    tag = os.path.basename(path).replace(".bag", "")
    npz = os.path.join(CACHE, f"scans_{tag}.npz")
    if os.path.exists(npz):
        z = np.load(npz)
        starts, flat, stamps, layout = z["starts"], z["pts"], z["stamps"], str(z["layout"])
    else:
        out, stamps, layout = [], [], None
        with Reader(path) as r:
            conns = [c for c in r.connections if c.topic == SCAN_TOPIC]
            for conn, _t, raw in r.messages(connections=conns):
                m = TYPESTORE.deserialize_ros1(raw, conn.msgtype)
                if layout is None:
                    layout = (f"point_step={m.point_step} fields="
                              + ",".join(f"{f.name}@{f.offset}:{f.datatype}" for f in m.fields))
                a = np.frombuffer(np.asarray(m.data, dtype=np.uint8).tobytes(),
                                  dtype=_cloud_dtype(m))
                p = np.column_stack([a["x"], a["y"], a["z"]]).astype(np.float64)
                rr = np.linalg.norm(p, axis=1)
                p = p[(rr > RMIN) & (rr < RMAX)]
                if len(p) > MAX_KF_POINTS:
                    p = p[:: max(1, len(p) // MAX_KF_POINTS)][:MAX_KF_POINTS]
                # header stamp, never the bag record clock
                stamps.append(float(m.header.stamp.sec) + float(m.header.stamp.nanosec) * 1e-9)
                out.append(p)
        order = np.argsort(stamps)
        n = [len(out[i]) for i in order]
        starts = np.concatenate([[0], np.cumsum(n)])
        flat = np.vstack([out[i] for i in order]) if out else np.zeros((0, 3))
        stamps = np.asarray(stamps, float)[order]
        np.savez(npz, starts=starts, pts=flat, stamps=stamps, layout=np.array(layout or ""))
    return [(float(stamps[i]), flat[starts[i]:starts[i + 1]].copy()) for i in range(len(stamps))], layout


def load_poses(path):
    ts, xyz, quat = [], [], []
    with Reader(path) as r:
        conns = [c for c in r.connections if c.topic == POSE_TOPIC]
        for conn, _t, raw in r.messages(connections=conns):
            m = TYPESTORE.deserialize_ros1(raw, conn.msgtype)
            ts.append(float(m.header.stamp.sec) + float(m.header.stamp.nanosec) * 1e-9)
            p, q = m.pose.pose.position, m.pose.pose.orientation
            xyz.append([p.x, p.y, p.z])
            quat.append([q.x, q.y, q.z, q.w])
    o = np.argsort(ts)
    return np.asarray(ts)[o], np.asarray(xyz)[o], np.asarray(quat)[o]


def quat_to_rot(q):
    x, y, z, w = (float(v) for v in q)
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def slerp(q0, q1, a):
    d = float(np.dot(q0, q1))
    if d < 0.0:
        q1, d = -q1, -d
    if d > 0.9995:
        q = q0 + a * (q1 - q0)
    else:
        th = np.arccos(np.clip(d, -1.0, 1.0))
        q = (np.sin((1.0 - a) * th) * q0 + np.sin(a * th) * q1) / np.sin(th)
    return q / np.linalg.norm(q)


def _drop_ranges(drop_rel):
    """Contiguous dropped spans (>1 s apart starts a new span), same reporting as the manifest."""
    out, lo, prev = [], None, None
    for v in sorted(drop_rel):
        if lo is None:
            lo = prev = v
        elif v - prev > 1.0:
            out.append([round(lo, 2), round(prev, 2)])
            lo = prev = v
        else:
            prev = v
    if lo is not None:
        out.append([round(lo, 2), round(prev, 2)])
    return out


def pair_keyframes(scans, poses):
    """Same two rules as the producer: nearest within NEAR_DT, else interpolate across a gap
    <= MAX_GAP, else drop.  Kept identical on purpose -- pairing is protocol, not statistic."""
    pt, px, pq = poses
    kfs, interp, dropped, drop_rel = [], 0, 0, []
    t_start = scans[0][0] if scans else 0.0
    for ts, p in scans:
        j = int(np.searchsorted(pt, ts))
        near = [i for i in (j - 1, j) if 0 <= i < len(pt)]
        best = min(near, key=lambda i: abs(pt[i] - ts)) if near else None
        if best is not None and abs(pt[best] - ts) <= NEAR_DT:
            xyz, q, src = px[best], pq[best], "NEAREST"
        elif 0 < j < len(pt) and (pt[j] - pt[j - 1]) <= MAX_GAP:
            a = (ts - pt[j - 1]) / (pt[j] - pt[j - 1])
            xyz, q = (1 - a) * px[j - 1] + a * px[j], slerp(pq[j - 1], pq[j], float(a))
            interp, src = interp + 1, "INTERPOLATED"
        else:
            dropped += 1
            drop_rel.append(float(ts - t_start))
            continue
        T = np.eye(4)
        T[:3, :3] = quat_to_rot(q)
        T[:3, 3] = xyz
        kfs.append({"ts": ts, "pts": p, "T": T, "src": src})
    return kfs, {"scans": len(scans), "paired": len(kfs), "interpolated": interp,
                 "dropped": dropped, "dropped_time_ranges_rel_sec": _drop_ranges(drop_rel),
                 "first_raw_scan_abs_sec": t_start}


def world_pts(kf):
    T = kf["T"]
    return kf["pts"] @ T[:3, :3].T + T[:3, 3]


# ----------------------------------------------------------------------------------- geometry
def umeyama(src, dst):
    """Least-squares rigid transform mapping src onto dst: dst ~ src @ R.T + t."""
    n = len(src)
    mu_s, mu_d = src.mean(0), dst.mean(0)
    cov = (dst - mu_d).T @ (src - mu_s) / n
    U, _D, Vt = np.linalg.svd(cov)
    S = np.eye(3)
    if np.linalg.det(U) * np.linalg.det(Vt) < 0:
        S[2, 2] = -1.0
    R = U @ S @ Vt
    return R, mu_d - R @ mu_s


def associate(ts_a, xyz_a, ts_b, xyz_b, tol=0.05):
    """Nearest-in-time pairs, |dt| <= tol, one b per a."""
    idx = np.clip(np.searchsorted(ts_b, ts_a), 1, len(ts_b) - 1)
    left, right = idx - 1, idx
    pick = np.where(np.abs(ts_b[left] - ts_a) <= np.abs(ts_b[right] - ts_a), left, right)
    ok = np.abs(ts_b[pick] - ts_a) <= tol
    return ts_a[ok], xyz_a[ok], xyz_b[pick[ok]]


def detect_onset(clean_scans, inj_scans):
    """Oracle: first and last scan whose raw buffer differs from the clean bag, by header stamp."""
    c = {round(t, 6): bytes(p.tobytes()) for t, p in clean_scans}
    i = {round(t, 6): bytes(p.tobytes()) for t, p in inj_scans}
    common = sorted(set(c) & set(i))
    diff = [t for t in common if c[t] != i[t]]
    return diff[0], diff[-1], common[0], len(diff), len(common)


# ----------------------------------------------------------------------------------- metric
def tail_stats(dists, tag=""):
    """dists: list of per-keyframe arrays (inf = nothing within SEARCH_R)."""
    flat = np.concatenate(dists) if dists else np.zeros(0)
    return {
        "arm": tag,
        "n_keyframes": len(dists),
        "n_points": int(len(flat)),
        "n_beyond_search_radius": int(np.sum(~np.isfinite(flat))),
        **{f"tail_over_{t}m": float(np.mean(flat > t)) for t in THRESHOLDS},
        "median_m": float(np.median(flat[np.isfinite(flat)])) if np.any(np.isfinite(flat)) else None,
    }


def bootstrap_kf(dists, n_boot=1000, seed=0):
    """Resample KEYFRAMES (points inside a keyframe are correlated)."""
    rng = np.random.default_rng(seed)
    n = len(dists)
    out = {}
    for t in THRESHOLDS:
        per = np.asarray([float(np.mean(d > t)) for d in dists])
        idx = rng.integers(0, n, size=(n_boot, n))
        boot = per[idx].mean(axis=1)
        out[f"tail_over_{t}m"] = {"mean": float(per.mean()),
                                  "ci95": [float(np.percentile(boot, 2.5)),
                                           float(np.percentile(boot, 97.5))]}
    return out


def tail_by_point(dists, n_boot=1000, seed=0):
    """The wrong bootstrap, computed on purpose: resample POINTS, not keyframes."""
    rng = np.random.default_rng(seed)
    flat = np.concatenate(dists)
    idx = rng.integers(0, len(flat), size=(n_boot, len(flat)))
    out = {}
    for t in (0.5,):
        v = (flat > t)[idx].mean(axis=1)
        out[f"tail_over_{t}m"] = {"ci95": [float(np.percentile(v, 2.5)),
                                           float(np.percentile(v, 97.5))]}
    return out


def coverage(surface_q, committed_pts):
    tree = cKDTree(committed_pts)
    d, _ = tree.query(surface_q, k=1, distance_upper_bound=SEARCH_R)
    return {f"covered_within_{t}m": float(np.mean(d <= t)) for t in THRESHOLDS}, \
           float(np.median(d)), d


# -------------------------------------------------------------------------------------- main
def main():
    os.makedirs(CACHE, exist_ok=True)
    archived = json.load(open(MANIFEST, encoding="utf-8"))
    arms_a = archived["arms"]

    print("[] hashing inputs against the manifest")
    sha = {}
    for role, path in (("injected_scans", INJ_SCANS), ("injected_poses", INJ_POSES),
                       ("clean_scans_proxy_only", CLN_SCANS),
                       ("clean_poses_proxy_only", CLN_POSES)):
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 22), b""):
                h.update(chunk)
        sha[role] = h.hexdigest()
        print(f"   {role:26s} {h.hexdigest()}  match={h.hexdigest() == archived['inputs_sha256'][role]}")

    print("[] loading scans")
    inj_scans, inj_layout = load_scans(INJ_SCANS)
    cln_scans, cln_layout = load_scans(CLN_SCANS)
    print(f"   injected layout: {inj_layout}")
    print(f"   clean    layout: {cln_layout}")

    inj_pos = load_poses(INJ_POSES)
    cln_pos = load_poses(CLN_POSES)
    inj_kfs, inj_pair = pair_keyframes(inj_scans, inj_pos)
    cln_kfs, cln_pair = pair_keyframes(cln_scans, cln_pos)
    print(f"   injected pairing {inj_pair}   (manifest 578/217/20)")
    print(f"   clean    pairing {cln_pair}   (manifest 566/211/32)")

    onset_abs, end_abs, first_common, n_diff, n_common = detect_onset(cln_scans, inj_scans)
    rel0 = inj_kfs[0]["ts"]
    print(f"   onset {onset_abs:.6f} ({onset_abs - rel0:.3f}s rel), end {end_abs:.6f}, "
          f"{n_diff}/{n_common} frames differ   (manifest 14.528 / 34.467 / 200/598)")
    print(f"   dropped spans inj={inj_pair['dropped_time_ranges_rel_sec']} "
          f"clean={cln_pair['dropped_time_ranges_rel_sec']}")
    head_offset = float(inj_kfs[0]["ts"] - first_common)
    print(f"   head-frame offset inj_kfs[0] - first_common = {head_offset:.6f} s   "
          f"(manifest head_frame_offset_sec = {archived['onset_detection']['head_frame_offset_sec']})")
    print(f"   onset rel to first COMMON scan = {onset_abs - first_common:.6f} s   "
          f"(manifest start_rel_sec = {archived['onset_detection']['start_rel_sec']})")

    # --- pre-onset SE(3): injected -> clean --------------------------------------------------
    pre = [k for k in inj_kfs if k["ts"] < onset_abs]
    pre_ts = np.asarray([k["ts"] for k in pre])
    pre_xyz = np.asarray([k["T"][:3, 3] for k in pre])
    cln_ts = np.asarray([k["ts"] for k in cln_kfs])
    cln_xyz = np.asarray([k["T"][:3, 3] for k in cln_kfs])
    mt, mi, mc = associate(pre_ts, pre_xyz, cln_ts, cln_xyz)
    R_ic, t_ic = umeyama(mi, mc)
    print(f"   alignment from {len(mi)} pre-onset pairs; |t|={np.linalg.norm(t_ic):.4f} m, "
          f"rot={np.degrees(np.arccos(np.clip((np.trace(R_ic) - 1) / 2, -1, 1))):.2f} deg")

    def align_residuals(kfs):
        ts_a = np.asarray([k["ts"] for k in kfs])
        xyz_a = np.asarray([k["T"][:3, 3] for k in kfs])
        m_ts, mi_a, mc_a = associate(ts_a, xyz_a, cln_ts, cln_xyz)
        err = np.linalg.norm(mi_a @ R_ic.T + t_ic - mc_a, axis=1)
        out = {}
        for label, lo, hi in (("pre", 0.0, onset_abs), ("injection", onset_abs, end_abs),
                              ("post", end_abs, 1e18)):
            m = (m_ts >= lo) & (m_ts < hi)
            if m.any():
                out[label] = {"n": int(m.sum()), "mean_m": float(np.mean(err[m])),
                              "p95_m": float(np.percentile(err[m], 95)),
                              "max_m": float(np.max(err[m]))}
        return out

    resid = align_residuals(inj_kfs)
    print(f"   alignment residuals {json.dumps({k: {kk: round(vv, 4) if isinstance(vv, float) else vv for kk, vv in v.items()} for k, v in resid.items()})}")
    print("   manifest             pre 0.0401/0.3137   inj 4.0737/5.8976   post 13.3499/19.5751")

    # --- proxy surface: the clean run only, in its own world frame ---------------------------
    proxy_all = np.vstack([world_pts(k) for k in cln_kfs])
    proxy_cap = proxy_all[:: max(1, len(proxy_all) // PROXY_CAP)][:PROXY_CAP]
    print(f"   proxy: {len(proxy_all)} clean-run points, capped to {len(proxy_cap)}")
    proxy_tree = cKDTree(proxy_cap)
    cov_q = proxy_cap[:: max(1, len(proxy_cap) // COV_Q)][:COV_Q]

    # exactness of the independent NN: KD-tree vs brute force on 2000 random queries
    rng = np.random.default_rng(0)
    qsel = rng.choice(len(proxy_cap), size=2000, replace=False)
    d_kd, _ = proxy_tree.query(proxy_cap[qsel], k=1)
    d_bf = np.array([np.sqrt(((proxy_cap - proxy_cap[i]) ** 2).sum(1).min()) for i in qsel])
    print(f"   NN exactness: max |KD-tree - brute force| = {np.abs(d_kd - d_bf).max():.2e} m")

    def kf_pts(kf, cap=KF_CAP):
        w = world_pts(kf) @ R_ic.T + t_ic
        return w[:: max(1, len(w) // cap)][:cap] if len(w) > cap else w

    def arm_dists(ids):
        return [proxy_tree.query(kf_pts(inj_kfs[i]), k=1, distance_upper_bound=SEARCH_R)[0]
                for i in ids]

    full_ids = list(range(len(inj_kfs)))
    pre_ids = [i for i in range(len(inj_kfs)) if inj_kfs[i]["ts"] < onset_abs]
    post_ids = [i for i in range(len(inj_kfs)) if inj_kfs[i]["ts"] >= onset_abs]

    out = {"_meta": {
        "what": "independent recomputation of the four-arm contamination numbers",
        "independence": {"bag_reader": "rosbags + message PointField layout",
                         "nn": "scipy cKDTree (producer: hand-written hash grid)",
                         "alignment": "own Umeyama SVD",
                         "bootstrap": "own, keyframes resampled"},
        "shared_on_purpose": ["inputs (sha256-checked)", "scan filter 0.5..30 m",
                              "pairing rules", "250-point keyframe cap",
                              "120000-point proxy cap", "pre-onset alignment target"],
        "sampling": "NONE -- every keyframe of every arm was scored, no subsampling",
        "layout": {"injected": inj_layout, "clean": cln_layout},
        "inputs_sha256": sha,
        "onset_abs": onset_abs, "end_abs": end_abs, "first_common": first_common,
        "pairing": {"injected": inj_pair, "clean": cln_pair},
        "alignment": {"n_pairs": int(len(mi)), "R": R_ic.tolist(), "t": t_ic.tolist(),
                      "residuals": resid},
        "proxy_points_total": int(len(proxy_all)),
        "proxy_points_used": int(len(proxy_cap)),
    }, "arms": {}}

    cov_d_by = {}
    for tag, ids in (("A0_A2_write_everything", full_ids), ("A1_pre_onset_only", pre_ids)):
        t0 = __import__("time").perf_counter()
        d = arm_dists(ids)
        st = tail_stats(d, tag)
        committed = np.vstack([kf_pts(inj_kfs[i], cap=KF_CAP) for i in ids])
        cov, cov_med, cov_d = coverage(cov_q, committed)
        cov_d_by[tag] = cov_d
        out["arms"][tag] = {"distance": st, "bootstrap_kf": bootstrap_kf(d),
                            "bootstrap_point": tail_by_point(d),
                            "coverage": cov, "coverage_median_m": cov_med,
                            "seconds": round(__import__("time").perf_counter() - t0, 1)}
        print(f"   {tag:24s} KF={len(ids):4d} pts={st['n_points']:7d} "
              f"tail0.5={st['tail_over_0.5m']:.4f} cov0.5={cov['covered_within_0.5m']:.4f}")

    # --- decomposition: where does A0's extra tail come from? --------------------------------
    d_full = arm_dists(full_ids)
    d_pre = d_full[:len(pre_ids)]           # full_ids is ordered, pre_ids is a prefix
    d_post = d_full[len(pre_ids):]
    out["decomposition"] = {
        "full": tail_stats(d_full, "full"),
        "pre_onset_part": tail_stats(d_pre, "pre"),
        "post_onset_part": tail_stats(d_post, "post"),
        "note": ("A0's keyframe list is a superset of A1's; splitting A0 by segment shows "
                 "how much of the 36 pp comes from the frames A1 never writes"),
    }
    print(f"   A0 split: pre-onset tail0.5={out['decomposition']['pre_onset_part']['tail_over_0.5m']:.4f} "
          f"post-onset tail0.5={out['decomposition']['post_onset_part']['tail_over_0.5m']:.4f}")

    # coverage added by the frames A1 never writes
    cov_pre, _, cov_pre_d = coverage(cov_q, np.vstack([kf_pts(inj_kfs[i]) for i in pre_ids]))
    cov_post_only, _, _ = coverage(cov_q, np.vstack([kf_pts(inj_kfs[i]) for i in post_ids]))
    # Paired bootstrap of the coverage difference: the two arms are scored on the SAME query
    # points, so the difference is paired and only query sampling varies. The manifest reports no
    # CI for coverage at all.
    _d = (cov_d_by["A0_A2_write_everything"] <= 0.5).astype(float) \
        - (cov_d_by["A1_pre_onset_only"] <= 0.5).astype(float)
    _rng = np.random.default_rng(0)
    _b = _d[_rng.integers(0, len(_d), size=(1000, len(_d)))].mean(axis=1)
    cov_boot = {"mean": float(_d.mean()),
                "ci95": [float(np.percentile(_b, 2.5)), float(np.percentile(_b, 97.5))],
                "note": "paired over the 40000 proxy query points; A0 minus A1"}
    out["decomposition"]["coverage"] = {
        "pre_onset_only": cov_pre,
        "post_onset_frames_only": cov_post_only,
        "union": out["arms"]["A0_A2_write_everything"]["coverage"],
        "difference_A0_minus_A1_bootstrap": cov_boot,
        "note": "coverage is monotone in map size; the +3 pp is what 445 polluted frames add",
    }
    print(f"   coverage@0.5 pre={cov_pre['covered_within_0.5m']:.4f} "
          f"post-only={cov_post_only['covered_within_0.5m']:.4f} "
          f"union={out['arms']['A0_A2_write_everything']['coverage']['covered_within_0.5m']:.4f} "
          f"diff={cov_boot['mean']:+.4f} {cov_boot['ci95']}")

    # --- the floor: is it A1 itself? -------------------------------------------------------
    floor_ids = [i for i in range(len(inj_kfs)) if inj_kfs[i]["ts"] < onset_abs]
    out["floor_check"] = {
        "floor_definition_in_producer": "injected_run_pre_onset_keyframes",
        "floor_ids": floor_ids,
        "a1_ids": pre_ids,
        "identical": floor_ids == pre_ids,
        "a1_is_the_floor": floor_ids == pre_ids,
        "why": ("`floor_ids` and the A1 arm are built from the same predicate on the same "
                "keyframe list, so the cross-run floor is A1's own map. A1 cannot exceed its "
                "own floor, and overlapping CIs between them carry no information."),
    }
    print(f"   floor == A1 keyframe set: {floor_ids == pre_ids}")

    # --- sensitivity: the producer's choices that could move the number --------------------
    sens = {}
    # (a) proxy cap: the producer keeps 120 000 of 8 490 000 clean-run points (1.4 %). A coarse
    # proxy can only *inflate* the tail, so this bounds how much of A1's 0.0079 is sampling.
    proxy_big = cKDTree(proxy_all)
    unc = {}
    for tag, ids in (("A0_A2_write_everything", full_ids), ("A1_pre_onset_only", pre_ids)):
        dd = [proxy_big.query(kf_pts(inj_kfs[i]), k=1, distance_upper_bound=SEARCH_R)[0]
              for i in ids]
        unc[tag] = tail_stats(dd, tag)
        print(f"   uncapped proxy {tag:24s} tail0.5={unc[tag]['tail_over_0.5m']:.4f}")
    sens["proxy_cap_120k_vs_all"] = {
        "n_proxy_all": int(len(proxy_all)),
        "n_proxy_capped": int(len(proxy_cap)),
        "capped": {k: v["tail_over_0.5m"] for k, v in
                   ((t, out["arms"][t]["distance"]) for t in unc)},
        "uncapped": {k: v["tail_over_0.5m"] for k, v in unc.items()},
        "keyframes": "all",
    }
    # (b) keyframe point cap
    d_cap250 = [proxy_tree.query(kf_pts(inj_kfs[i], cap=KF_CAP), k=1,
                                 distance_upper_bound=SEARCH_R)[0] for i in pre_ids[:80]]
    d_cap1000 = [proxy_tree.query(kf_pts(inj_kfs[i], cap=1000), k=1,
                                  distance_upper_bound=SEARCH_R)[0] for i in pre_ids[:80]]
    sens["kf_cap_250_vs_1000"] = {
        "tail0.5_250": float(np.mean(np.concatenate(d_cap250) > 0.5)),
        "tail0.5_1000": float(np.mean(np.concatenate(d_cap1000) > 0.5)),
        "keyframes": 80,
    }
    # (c) relative vs absolute segment base. `rel` is keyed to the bag's first SCAN and ONSET_REL
    # to the first COMMON scan; both are 1627785261.079 here, so the two rules agree and the
    # floor fix does not move this run's numbers. The 1.30 s head offset is about the first
    # *keyframe* (scans with no pose are dropped), not about the time base.
    sens["time_base"] = {
        "first_common_abs_sec": first_common,
        "first_raw_scan_abs_sec": inj_pair["first_raw_scan_abs_sec"],
        "first_keyframe_abs_sec": float(inj_kfs[0]["ts"]),
        "head_frame_offset_sec_recomputed": head_offset,
        "head_frame_offset_sec_archived": archived["onset_detection"]["head_frame_offset_sec"],
        "relative_and_absolute_rules_equivalent": bool(
            abs(first_common - inj_pair["first_raw_scan_abs_sec"]) < 1e-6),
    }
    out["sensitivity"] = sens
    print(f"   proxy cap effect on A1 tail0.5: {sens['proxy_cap_120k_vs_all']['capped']['A1_pre_onset_only']:.4f}"
          f" -> {sens['proxy_cap_120k_vs_all']['uncapped']['A1_pre_onset_only']:.4f} (all points)")

    # --- archived vs recomputed ------------------------------------------------------------
    cmp_rows = []
    for tag, key in (("A0_A2_write_everything", "A0_Host_Native"),
                     ("A1_pre_onset_only", "A1_Quarantine_Only")):
        mine, arc = out["arms"][tag], arms_a[key]
        cmp_rows.append({
            "arm": key,
            "tail0.5_mine": round(mine["distance"]["tail_over_0.5m"], 4),
            "tail0.5_archived": arc["distance_stats"]["tail_over_0.5m"],
            "tail0.5_delta": round(mine["distance"]["tail_over_0.5m"]
                                   - arc["distance_stats"]["tail_over_0.5m"], 4),
            "cov0.5_mine": round(mine["coverage"]["covered_within_0.5m"], 4),
            "cov0.5_archived": arc["coverage_sweep"]["covered_within_0.5m"],
            "cov0.5_delta": round(mine["coverage"]["covered_within_0.5m"]
                                  - arc["coverage_sweep"]["covered_within_0.5m"], 4),
            "n_points_mine": mine["distance"]["n_points"],
            "n_points_archived": arc["distance_stats"]["n_points"],
            "ci0.5_mine": [round(v, 4) for v in mine["bootstrap_kf"]["tail_over_0.5m"]["ci95"]],
            "ci0.5_archived": arc["distance_tail_bootstrap"]["tail_over_0.5m"]["ci95"],
        })
    out["comparison"] = cmp_rows
    out["separation"] = {
        "delta_tail0.5": round(cmp_rows[0]["tail0.5_mine"] - cmp_rows[1]["tail0.5_mine"], 4),
        "delta_cov0.5": round(cmp_rows[1]["cov0.5_mine"] - cmp_rows[0]["cov0.5_mine"], 4),
        "ci_disjoint": (cmp_rows[0]["ci0.5_mine"][0] > cmp_rows[1]["ci0.5_mine"][1]),
    }

    dst = "/tmp/fourarm_independent.json"
    with open(dst, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, default=float)
    print(f"\nsaved {dst}")
    print("\n=== archived vs recomputed ===")
    for r in cmp_rows:
        print(f"  {r['arm']:26s} tail0.5 {r['tail0.5_mine']:.4f} vs {r['tail0.5_archived']:.4f} "
              f"(d={r['tail0.5_delta']:+.4f})  cov0.5 {r['cov0.5_mine']:.4f} vs "
              f"{r['cov0.5_archived']:.4f} (d={r['cov0.5_delta']:+.4f})")
    print(f"  separation: tail {out['separation']['delta_tail0.5']:.4f}, "
          f"coverage {out['separation']['delta_cov0.5']:.4f}, "
          f"CI disjoint={out['separation']['ci_disjoint']}")


if __name__ == "__main__":
    sys.exit(main())
