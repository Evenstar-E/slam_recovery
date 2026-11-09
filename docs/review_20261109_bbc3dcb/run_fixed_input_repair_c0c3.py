#!/usr/bin/env python3
"""Fixed-input end-to-end repair measurement: C0 / C1 / C2 (+ C3 if the host re-run exists).

Sequence and fault are fixed: hall_01, the 4.30 m plastic-sheet injection, the same clip
(`hall01_inj43.bag`) the four-arm benchmark uses.  The key set is frozen and exported before any
metric is computed.

Conditions (same keys, same evaluation region):

  C0  polluted scans      + host poses          (the archived FAST-LIVO2 run)
  C1  polluted scans      + reference poses     (clean-run poses carried into the injected frame
                                                 by the pre-onset SE(3); same construction as the
                                                 four-arm `good` candidate)
  C2  oracle-clean scans  + reference poses     (UPPER BOUND ONLY: returns inside the absolute
                                                 injection window whose azimuth and range match the
                                                 injector's sheet model are deleted; the occluded
                                                 background is NOT restored)
  C3  really-filtered scans + re-estimated poses (repo filter
                                                 `filter_self_consistent_near_field_contaminants`
                                                 + FAST-LIVO2 re-run on the filtered bag)

Nothing here changes node/core/manager, `fim_and_holdout.py` or a published manifest.

Why the metrics are not global-threshold metrics: the reference is the **full** clean-run cloud
(no 120k cap) and every distance is a **local** point-to-plane distance against an 8-neighbour
PCA plane, split by neighbourhood quality (planar vs mixed).  Coverage is reported on a
neighbourhood-stratified query sample.  Raising a global cap or sigma is explicitly not used.

Subcommands
    python3 run_fixed_input_repair_c0c3.py measure
    python3 run_fixed_input_repair_c0c3.py build-filtered-bag
"""

from __future__ import annotations

import hashlib
import json
import os
import sys

import numpy as np
from scipy.spatial import cKDTree

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_HERE))
for _p in (_HERE, _REPO):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import verify_four_arm_independent as V  # noqa: E402  (reviewed loader/cache/pairing)

from slam_recovery.repair.point_mixture_repairer import (  # noqa: E402
    MixtureFilterConfig,
    filter_self_consistent_near_field_contaminants,
)

RESULT_JSON = os.path.join(_HERE, "fixed_input_repair_c0c3_results.json")
FILTERED_BAG = "/tmp/fastlivo/hall01_inj43_filtered.bag"
RERUN_BAG = "/tmp/fastlivo/res_h1_inj43_filtered.bag"
C3_HOST_BAG = "/tmp/fastlivo/res_h1_inj43_rerun_unfiltered.bag"

INJ_SCANS = V.INJ_SCANS
INJ_POSES = V.INJ_POSES
CLN_SCANS = V.CLN_SCANS
CLN_POSES = V.CLN_POSES

VOXEL = 0.10                 # connectivity grid, same as the repo-wide VOXEL
GAP_R = 1.0                  # a keyframe with no committed point within this radius is a gap
K_PLANE = 8                  # local PCA neighbourhood for point-to-plane distance
PLANAR_RATIO = 0.10          # lambda_min / lambda_mid below this -> planar neighbourhood
WELL_RMS_M = 0.02            # plane-fit RMS below this ...
WELL_RADIUS_M = 0.30         # ... and an 8-NN radius below this -> well-constrained reference
COV_Q = 40000

INJECTION_AZIMUTH_FRACTION = 0.88
INJECTION_BAG_DISTANCE_M = 4.30
INJECTION_THICKNESS_M = 0.01  # bag_Thickness_jitter_m used by the hall_01 generator


# ------------------------------------------------------------------------------- oracle geometry
def load_scan_ns(path, src_sha):
    """Exact integer header stamps (ns) of every scan, sorted, cached by content hash.

    Float stamps cannot carry nanoseconds at 1.6e9 s (a double step there is ~240 ns), which is
    exactly how the 6-decimal boundary put the first injected scan in the healthy prefix.  Nothing
    downstream of this file should compare rounded floats again.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"input bag missing: {path}")
    os.makedirs(V.CACHE, exist_ok=True)
    key = hashlib.sha256(f"ns|{src_sha}|{V.SCRIPT_VERSION}".encode()).hexdigest()[:20]
    out = os.path.join(V.CACHE, f"ns_{key}.npz")
    if os.path.exists(out):
        return np.load(out)["ns"]
    ns = []
    with V.Reader(path) as r:
        conns = [c for c in r.connections if c.topic == V.SCAN_TOPIC]
        for conn, _t, raw in r.messages(connections=conns):
            m = V.TYPESTORE.deserialize_ros1(raw, conn.msgtype)
            ns.append(int(m.header.stamp.sec) * 10**9 + int(m.header.stamp.nanosec))
    arr = np.asarray(sorted(ns), dtype=np.int64)
    np.savez(out, ns=arr)
    return arr


def oracle_bag_mask(body_xyz):
    """Returns the injector's sheet by its own geometry: azimuth sector <= -pi + 2*pi*0.88, and a
    range consistent with the tilted plane n^T p = 4.30.  Nothing here looks at the clean bag."""
    p = np.asarray(body_xyz, float)
    az = np.arctan2(p[:, 1], p[:, 0])
    sector = az <= (-np.pi + 2.0 * np.pi * INJECTION_AZIMUTH_FRACTION)
    n = np.array([1.0, 0.15, 0.05])
    n /= np.linalg.norm(n)
    r = np.linalg.norm(p, axis=1)
    dirs = p / np.maximum(r[:, None], 1e-6)
    denom = np.maximum(np.abs(dirs @ n), 0.25)
    sheet_r = INJECTION_BAG_DISTANCE_M / denom
    on_sheet = np.abs(r - sheet_r) <= 40.0 * INJECTION_THICKNESS_M
    return sector & on_sheet


# ------------------------------------------------------------------------------- local metric
def local_plane_residual(q, ref_tree, ref_pts, k=K_PLANE, exclude_self=False):
    """Local point-to-plane distance against a k-NN PCA plane, plus the neighbourhood quality.

    The reference is the full clean cloud, so this is a local spatial reference: each query is
    scored against its own neighbourhood, not against a global cap or a global scale.
    """
    kk = k + 1 if exclude_self else k
    d, idx = ref_tree.query(q, k=kk)
    if exclude_self:
        idx, d = idx[:, 1:], d[:, 1:]
    P = ref_pts[idx]                                  # (n, k, 3)
    c = P.mean(axis=1)
    A = P - c[:, None, :]
    cov = np.einsum("nki,nkj->nij", A, A) / k
    w, vec = np.linalg.eigh(cov)                      # ascending eigenvalues
    n = vec[:, :, 0]
    resid = np.abs(np.einsum("ni,ni->n", q - c, n))
    ratio = w[:, 0] / np.maximum(w[:, 1], 1e-12)
    radius = d[:, -1]
    rms = np.sqrt(np.maximum(w[:, 0], 0.0))
    return resid, ratio, radius, rms


def tail_stats(d):
    out = {"n": int(len(d))}
    for t in (0.25, 0.5, 1.0):
        out[f"tail_over_{t}m"] = float(np.mean(d > t)) if len(d) else None
    out["median_m"] = float(np.median(d)) if len(d) else None
    out["p90_m"] = float(np.percentile(d, 90)) if len(d) else None
    return out


def voxel_keys(points):
    if len(points) == 0:
        return set()
    return set(map(tuple, np.floor(points / VOXEL).astype(np.int64).tolist()))


def voxel_keys_scale(points, size):
    if len(points) == 0:
        return set()
    return set(map(tuple, np.floor(points / size).astype(np.int64).tolist()))


def connectivity(keys):
    """Connected components of the committed voxel set under a 26-neighbourhood."""
    keys = list(keys)
    if not keys:
        return {"n_voxels": 0, "n_components": 0, "largest_fraction": 0.0,
                "second_fraction": 0.0}
    index = {k: i for i, k in enumerate(keys)}
    parent = list(range(len(keys)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    offs = [(dx, dy, dz) for dx in (-1, 0, 1) for dy in (-1, 0, 1) for dz in (-1, 0, 1)
            if (dx, dy, dz) != (0, 0, 0)]
    for k, i in index.items():
        for o in offs:
            j = index.get((k[0] + o[0], k[1] + o[1], k[2] + o[2]))
            if j is not None:
                ra, rb = find(i), find(j)
                if ra != rb:
                    parent[ra] = rb
    roots = {}
    for i in range(len(keys)):
        roots[find(i)] = roots.get(find(i), 0) + 1
    sizes = sorted(roots.values(), reverse=True)
    return {"n_voxels": len(keys), "n_components": len(sizes),
            "largest_fraction": sizes[0] / len(keys),
            "second_fraction": (sizes[1] / len(keys)) if len(sizes) > 1 else 0.0,
            "top5_fractions": [round(s / len(keys), 4) for s in sizes[:5]]}


def trajectory_gap(committed_by_key, key_order, poses_xyz, ts):
    """A keyframe is a gap if no committed point **from another keyframe** lies within GAP_R.

    Including the frame's own returns would make the metric vacuous -- a scan's own points are
    always next to its own pose -- so support here means support from the rest of the map.
    """
    if not committed_by_key:
        return {"gap_keyframes": None, "gap_fraction": None, "longest_gap_sec": None}
    all_pts = np.vstack([committed_by_key[i] for i in key_order])
    labels = np.concatenate([np.full(len(committed_by_key[i]), i) for i in key_order])
    tree = cKDTree(all_pts)
    k = min(24, len(all_pts))
    d, idx = tree.query(poses_xyz, k=k)
    nearest = np.full(len(poses_xyz), np.inf)
    for r in range(len(poses_xyz)):
        for j in range(k):
            if labels[idx[r, j]] != key_order[r]:
                nearest[r] = d[r, j]
                break
    bad = nearest > GAP_R
    return {"gap_keyframes": int(bad.sum()), "gap_fraction": float(bad.mean()),
            "median_nearest_other_m": float(np.median(nearest)) if np.isfinite(nearest).all()
            else None,
            "longest_gap_sec": longest_run_sec(bad.tolist(), list(ts))}


def longest_run_sec(mask, ts):
    best, cur, start = 0.0, False, 0.0
    for m, t in zip(mask, ts):
        if m and not cur:
            cur, start = True, t
        elif not m and cur:
            best, cur = max(best, t - start), False
    if cur:
        best = max(best, ts[-1] - start)
    return float(best)


# ------------------------------------------------------------------------------- conditions
def pose_injected_frame(cond, inj_kfs, id_list, ref_poses, c3_poses):
    """Per-id 4x4 poses in the injected world frame for a condition (keys and prefix alike)."""
    if cond == "C0":
        return {i: inj_kfs[i]["T"].copy() for i in id_list}
    if cond in ("C1", "C2"):
        return {i: ref_poses[i] for i in id_list if i in ref_poses}
    if cond == "C3":
        return {i: c3_poses[i] for i in id_list if i in c3_poses}
    raise ValueError(cond)


def host_reproducibility(onset_abs, end_abs):
    """Does a fresh FAST-LIVO2 replay of the same bag reproduce the archived pose bag?

    Without this, any C3-vs-C0 difference could be run-to-run variance rather than the filter.
    Compared after a pre-onset SE(3), i.e. the same rule every condition is scored under.
    """
    if not (os.path.exists(C3_HOST_BAG) and os.path.exists(V.INJ_POSES)):
        return {"status": "UNAVAILABLE", "missing": C3_HOST_BAG}
    t1, x1, _q1 = V.load_poses(V.INJ_POSES)
    t2, x2, _q2 = V.load_poses(C3_HOST_BAG)
    mt, a, b = V.associate(t1, x1, t2, x2, 0.05)
    if len(mt) < 10:
        return {"status": "UNAVAILABLE", "reason": "too few matched poses"}
    pre = mt < onset_abs
    R, t = V.umeyama(b[pre], a[pre])
    err = np.linalg.norm(b @ R.T + t - a, axis=1)
    out = {"archived_poses": int(len(t1)), "rerun_poses": int(len(t2)),
           "matched": int(len(mt)), "alignment_translation_m": float(np.linalg.norm(t))}
    for lab, m in (("pre_onset", mt < onset_abs),
                   ("in_window", (mt >= onset_abs) & (mt <= end_abs)),
                   ("post", mt > end_abs)):
        out[lab] = {"n": int(m.sum()), "mean_m": float(err[m].mean()) if m.any() else None,
                    "p95_m": float(np.percentile(err[m], 95)) if m.any() else None,
                    "max_m": float(err[m].max()) if m.any() else None}
    return out


def c3_provenance():
    """Everything needed to re-run C3 without asking what was used."""
    import subprocess

    def _sha(p):
        return V._sha_file(p) if os.path.exists(p) else None

    def _rev(p):
        try:
            out = subprocess.run(["git", "-C", p, "rev-parse", "HEAD"], capture_output=True,
                                 text=True, timeout=10)
            return out.stdout.strip() or None
        except Exception:
            return None

    host_bin = "/home/R26534/fast_livo2_ws/devel/lib/fast_livo/fastlivo_mapping"
    cfg = {"m2dgr.yaml": "/home/R26534/FAST-LIVO2/config/m2dgr.yaml",
           "camera_m2dgr.yaml": "/home/R26534/FAST-LIVO2/config/camera_m2dgr.yaml"}
    host_src = "/home/R26534/fast_livo2_ws/src/FAST-LIVO2"
    rec = {
        "label": "OFFLINE_NATIVE_REESTIMATION",
        "filter_module": "slam_recovery.repair.point_mixture_repairer",
        "filter_function": "filter_self_consistent_near_field_contaminants",
        "filter_config": "MixtureFilterConfig() shipped defaults",
        "bags": {
            "original_scans": {"path": INJ_SCANS, "sha256": _sha(INJ_SCANS)},
            "converted_scans": {"path": FILTERED_BAG,
                                "sha256": _sha(FILTERED_BAG),
                                "what": "converted = filtered copy of the same bag; only the "
                                        "/velodyne_points payload changes, every other topic is "
                                        "copied byte for byte"},
            "replay_poses_out": {"path": RERUN_BAG, "sha256": _sha(RERUN_BAG)},
            "control_poses_out": {"path": C3_HOST_BAG, "sha256": _sha(C3_HOST_BAG),
                                  "what": "unfiltered replay, used only as the reproducibility "
                                          "control for the host pipeline"},
        },
        "host": {
            "system": "FAST-LIVO2",
            "binary": host_bin,
            "binary_sha256": _sha(host_bin),
            "source_dir": host_src,
            "source_revision": _rev(host_src),
            "workspace": "/home/R26534/fast_livo2_ws",
            "ros_distro_env": "/home/R26534/mm/ros",
            "rate": 0.5,
            "drain_sec": 60,
            "recorded_topic": "/aft_mapped_to_init",
            "isolation": "private ROS master on a free port; the wrapper kills only its own PIDs",
        },
        "configs": {name: {"path": path, "sha256": _sha(path)} for name, path in cfg.items()},
        "commands": [
            "python3 -B docs/review_20261109_bbc3dcb/run_fixed_input_repair_c0c3.py "
            "build-filtered-bag",
            "bash /tmp/fl_run_isolated.sh /tmp/fastlivo/hall01_inj43_filtered.bag "
            "/tmp/fastlivo/res_h1_inj43_filtered.bag 0.5 60",
            "bash /tmp/fl_run_isolated.sh /tmp/fastlivo/hall01_inj43.bag "
            "/tmp/fastlivo/res_h1_inj43_rerun_unfiltered.bag 0.5 60",
            "python3 -B docs/review_20261109_bbc3dcb/run_fixed_input_repair_c0c3.py measure",
        ],
    }
    return rec


def main_measure():
    state = {}
    sha = {r: V._sha_file(p) for r, p in
           (("injected_scans", INJ_SCANS), ("injected_poses", INJ_POSES),
            ("clean_scans_proxy_only", CLN_SCANS), ("clean_poses_proxy_only", CLN_POSES))}
    print("[] inputs", json.dumps({k: v[:12] for k, v in sha.items()}))

    inj_scans, layout = V.load_scans(INJ_SCANS, sha["injected_scans"])
    cln_scans, _ = V.load_scans(CLN_SCANS, sha["clean_scans_proxy_only"])
    inj_kfs, inj_pair = V.pair_keyframes(inj_scans, V.load_poses(INJ_POSES))
    cln_kfs, cln_pair = V.pair_keyframes(cln_scans, V.load_poses(CLN_POSES))
    onset_abs, end_abs, first_common, n_diff, n_common = V.detect_onset(cln_scans, inj_scans)
    print(f"[] pairing {inj_pair['paired']} inj / {cln_pair['paired']} clean; "
          f"onset {onset_abs:.6f} end {end_abs:.6f}; {n_diff}/{n_common} frames differ")

    # ---- FROZEN BEFORE ANY METRIC: the M0 protocol --------------------------------------
    # docs/milestone_m0_keys.json is the source of truth; nothing here selects keys.  Identity
    # is integer header-stamp nanoseconds, and the list hash is sha256 of the comma-joined
    # sorted ns, exactly as the file declares.
    m0_path = os.path.join(_REPO, "docs", "milestone_m0_keys.json")
    m0 = json.load(open(m0_path, encoding="utf-8"))
    ns_all = load_scan_ns(INJ_SCANS, sha["injected_scans"])
    if len(ns_all) != len(inj_scans):
        raise RuntimeError("scan ns and scan payload disagree in count")
    # keyframe -> scan ns: the kf float stamp comes from the same header, and the gaps are
    # ~0.1 s while a double step is ~240 ns, so nearest is unambiguous.
    pos = np.searchsorted(ns_all, np.asarray([round(k["ts"] * 1e9) for k in inj_kfs], dtype=np.int64))
    kf_ns = []
    for t, j in zip([k["ts"] for k in inj_kfs], pos):
        cand = [c for c in (j - 1, j) if 0 <= c < len(ns_all)]
        best = min(cand, key=lambda c: abs(ns_all[c] / 1e9 - t))
        kf_ns.append(int(ns_all[best]))
    kf_ns = np.asarray(kf_ns, dtype=np.int64)
    if len(set(kf_ns.tolist())) != len(kf_ns):
        raise RuntimeError("keyframe ns are not unique")
    by_ns = {int(n): i for i, n in enumerate(kf_ns)}

    start_ns = int(m0["injection_window"]["start_ns"])
    end_ns = int(m0["injection_window"]["end_ns"])

    def _map_ids(ns_list):
        ids, missing = [], []
        for n in ns_list:
            i = by_ns.get(int(n))
            if i is None:
                missing.append(int(n))
            else:
                ids.append(i)
        return ids, missing

    def _list_hash(ns_list):
        return hashlib.sha256(",".join(str(n) for n in sorted(int(x) for x in ns_list))
                              .encode()).hexdigest()

    keys, miss_primary = _map_ids(m0["primary_scan_set"]["timestamps_ns"])
    subset_ids, miss_subset = _map_ids(m0["diagnostic_subset"]["timestamps_ns"])
    prefix_ids, miss_prefix = _map_ids(m0["healthy_prefix"]["timestamps_ns"])
    raw_only, miss_raw = _map_ids(m0["missing_raw_scans"]["timestamps_ns"])
    key_ts = np.asarray([inj_kfs[i]["ts"] for i in keys])
    own_primary = [i for i in range(len(inj_kfs)) if kf_ns[i] >= start_ns]
    freeze = {
        "source": "docs/milestone_m0_keys.json @ f36137b (integer-ns boundary)",
        "encoding": m0.get("encoding"),
        "primary": {"count": len(keys), "m0_sha256": m0["primary_scan_set"]["sha256"],
                    "recomputed_sha256": _list_hash(kf_ns[keys]),
                    "sha256_matches": _list_hash(kf_ns[keys]) == m0["primary_scan_set"]["sha256"],
                    "unmatched_ns": miss_primary,
                    "equals_ns_ge_start": sorted(keys) == own_primary},
        "diagnostic_subset": {"count": len(subset_ids),
                              "m0_sha256": m0["diagnostic_subset"]["sha256"],
                              "recomputed_sha256": _list_hash(kf_ns[subset_ids]),
                              "sha256_matches": _list_hash(kf_ns[subset_ids])
                              == m0["diagnostic_subset"]["sha256"],
                              "unmatched_ns": miss_subset},
        "healthy_prefix": {"count": len(prefix_ids),
                           "m0_sha256": m0["healthy_prefix"]["sha256"],
                           "recomputed_sha256": _list_hash(kf_ns[prefix_ids]),
                           "sha256_matches": _list_hash(kf_ns[prefix_ids])
                           == m0["healthy_prefix"]["sha256"],
                           "unmatched_ns": miss_prefix},
        "missing_raw_scans": {"definition": m0["missing_raw_scans"]["definition"],
                              "count_in_m0": m0["missing_raw_scans"]["count"],
                              "paired_by_rule": len(raw_only),
                              "not_paired": len(miss_raw),
                              "note": "listed separately; outside the paired cohort"},
        "injection_window_ns": {"start": start_ns, "end": end_ns},
        "reference_definition": ("FULL clean-run cloud in its own world frame, no cap; every "
                                 "distance is a local 8-NN PCA point-to-plane distance"),
    }
    print(f"[] FROZEN (M0 @ f36137b, integer ns): primary={len(keys)} subset={len(subset_ids)} "
          f"prefix={len(prefix_ids)} raw_only={len(raw_only)}")
    print(f"   primary hash {freeze['primary']['recomputed_sha256'][:16]} "
          f"match={freeze['primary']['sha256_matches']}  "
          f"equals_ns_ge_start={freeze['primary']['equals_ns_ge_start']}")
    with open(os.path.join(_HERE, "fixed_input_repair_frozen_keys.json"), "w") as fh:
        json.dump({"primary_ids": keys, "subset_ids": subset_ids, "prefix_ids": prefix_ids,
                   "primary_ns": [int(x) for x in kf_ns[keys]],
                   "prefix_ns": [int(x) for x in kf_ns[prefix_ids]],
                   **freeze}, fh, indent=1)

    # ---- alignment and reference poses ---------------------------------------------------
    pre = list(prefix_ids)
    pre_xyz = np.asarray([inj_kfs[i]["T"][:3, 3] for i in pre])
    cln_ts = np.asarray([k["ts"] for k in cln_kfs])
    cln_xyz = np.asarray([k["T"][:3, 3] for k in cln_kfs])
    mt, mi, mc = V.associate(np.asarray([inj_kfs[i]["ts"] for i in pre]), pre_xyz, cln_ts, cln_xyz)
    R_ic, t_ic = V.umeyama(mi, mc)
    T_inv = np.eye(4)
    T_inv[:3, :3] = R_ic.T
    T_inv[:3, 3] = -R_ic.T @ t_ic
    ref_poses = {}
    for i in pre + keys:
        j = int(np.argmin(np.abs(cln_ts - inj_kfs[i]["ts"])))
        ref_poses[i] = T_inv @ cln_kfs[j]["T"]
    print(f"[] alignment from {len(mi)} pre-onset pairs; |t|={np.linalg.norm(t_ic):.4f} m")

    # ---- reference surface ---------------------------------------------------------------
    proxy_all = np.vstack([V.world_pts(k) for k in cln_kfs])
    ref_tree = cKDTree(proxy_all)
    rng = np.random.default_rng(0)
    cov_idx = rng.choice(len(proxy_all), size=min(COV_Q, len(proxy_all)), replace=False)
    cov_q = proxy_all[cov_idx]
    print(f"[] reference: {len(proxy_all)} clean points (uncapped), {len(cov_q)} coverage queries")

    # Oracle geometry self-check: the mask must fire on injected frames and stay silent on the
    # pre-onset frames, which are byte-identical to the clean recording.
    def _mask_rate(id_list):
        r = [float(oracle_bag_mask(inj_kfs[i]["pts"]).mean()) for i in id_list]
        return {"frames": len(r), "mean_fraction_flagged": float(np.mean(r)) if r else None,
                "min": float(np.min(r)) if r else None, "max": float(np.max(r)) if r else None}

    oracle_check = {
        "pre_onset_frames (clean, must be ~0)":
            _mask_rate([i for i in range(len(inj_kfs)) if inj_kfs[i]["ts"] < onset_abs][:30]),
        "in_window_frames (must be high)":
            _mask_rate([i for i in keys if onset_abs <= inj_kfs[i]["ts"] <= end_abs][:30]),
    }
    print(f"[] oracle geometry check: {json.dumps(oracle_check)}")

    # ---- per-condition point sets --------------------------------------------------------
    c3_poses, c3_note, c3_by_stamp = None, None, None
    if os.path.exists(RERUN_BAG) and os.path.exists(FILTERED_BAG):
        f_sha = V._sha_file(FILTERED_BAG)
        f_scans, _ = V.load_scans(FILTERED_BAG, f_sha)
        c3_by_stamp = {round(t, 6): p for t, p in f_scans}
        n_ts, n_xyz, n_q = V.load_poses(RERUN_BAG)
        c3_poses = {}
        for i in pre + keys:
            j = int(np.argmin(np.abs(n_ts - inj_kfs[i]["ts"])))
            if abs(n_ts[j] - inj_kfs[i]["ts"]) > 0.05:
                continue
            T = np.eye(4)
            T[:3, :3] = V.quat_to_rot(n_q[j])
            T[:3, 3] = n_xyz[j]
            c3_poses[i] = T
        c3_note = {"poses": "FAST-LIVO2 re-run on the filtered bag",
                   "filtered_bag_sha256": f_sha, "n_poses": len(c3_poses),
                   "poses_bag": RERUN_BAG}
    else:
        c3_note = {"poses": "UNAVAILABLE -- no host re-run on the filtered bag",
                   "missing": [f"{FILTERED_BAG} (filtered input bag)",
                               f"{RERUN_BAG} (FAST-LIVO2 re-run on it)"],
                   "what_it_would_take": ("apply the repo filter per scan, write the bag, replay "
                                          "FAST-LIVO2 with the archived config")}

    by_key_store, pose_store, R_store, t_store = {}, {}, {}, {}
    CONDITION_LABEL = {"C0": "REAL_HOST", "C1": "OFFLINE_CONSTRUCT",
                       "C2": "ORACLE_CEILING", "C3": "OFFLINE_NATIVE_REESTIMATION"}
    CONDITION_NOTE = {
        "C0": "host poses as archived; contaminated scans; no repair",
        "C1": "clean-run poses carried into the injected frame by the pre-onset SE(3); "
              "contaminated scans kept -- oracle/proxy consistency control, not GT accuracy",
        "C2": "oracle removal of the injector's sheet inside the absolute window only; does NOT "
              "restore the occluded background, so not a general optimal-map bound; upper bound "
              "for this injected data only",
        "C3": "shipped point-mixture filter (no window, no clean bag) + FAST-LIVO2 re-estimated "
              "poses on the filtered bag; not called deployable",}
    results = {"_meta": {"what": "fixed-input end-to-end repair measurement C0-C3",
                         "inputs_sha256": sha, "layout": layout,
                         "freeze": freeze,
                         "host_reproducibility": host_reproducibility(onset_abs, end_abs),
                         "c3_record": c3_provenance(),
                         "superseded_by_ns_boundary": {
                             "commit": "057c266 (6-decimal float boundary)",
                             "why": ("the float 6-dp boundary put the first injected scan in the "
                                     "healthy prefix; primary/subset/prefix were 445/259/133 and "
                                     "are now 446/252/132"),
                             "old_common_support_n_keys": 401,
                             "old_common_support": {
                                 "C0": {"tail_over_0.5m": 0.3138, "coverage_0.5m": 0.6022},
                                 "C1": {"tail_over_0.5m": 0.1944, "coverage_0.5m": 0.9864},
                                 "C2": {"tail_over_0.5m": 0.0, "coverage_0.5m": 0.9839},
                                 "C3": {"tail_over_0.5m": 0.0013, "coverage_0.5m": 0.9854},
                             },
                             "old_primary": {"C0": 0.3229, "C1": 0.2251, "C2": 0.0, "C3": 0.0013},
                             "status": "kept for the record only; do not cite",
                         },
                         "thresholds": {"voxel_m": VOXEL, "gap_radius_m": GAP_R,
                                        "local_plane_k": K_PLANE,
                                        "planar_ratio": PLANAR_RATIO},
                         "oracle_geometry": {
                             "azimuth_fraction": INJECTION_AZIMUTH_FRACTION,
                             "bag_distance_m": INJECTION_BAG_DISTANCE_M,
                             "thickness_m": INJECTION_THICKNESS_M,
                             "scope": "UPPER BOUND ONLY, not deployable",
                             "self_check": oracle_check}},
               "conditions": {}}

    if os.path.exists("/tmp/filtered_bag_report.json"):
        with open("/tmp/filtered_bag_report.json", encoding="utf-8") as fh:
            fr = json.load(fh)
        results["_meta"]["real_filter"] = {k: v for k, v in fr.items() if k != "per_frame"}
        results["_meta"]["real_filter"]["per_frame_available"] = "/tmp/filtered_bag_report.json"
        pf = fr.get("per_frame", [])
        # the report rounds stamps to 1 ms; allow that before calling a frame "outside"
        inw = [x for x in pf if onset_abs - 5e-4 <= x["t"] <= end_abs + 5e-4]
        outw = [x for x in pf if not (onset_abs - 5e-4 <= x["t"] <= end_abs + 5e-4)]
        results["_meta"]["real_filter"]["strip_fraction_in_window"] = (
            float(np.mean([x["strip_fraction"] for x in inw])) if inw else None)
        results["_meta"]["real_filter"]["strip_fraction_outside_window"] = (
            float(np.mean([x["strip_fraction"] for x in outw])) if outw else None)
        results["_meta"]["real_filter"]["frames_in_window"] = len(inw)


    for cond in ("C0", "C1", "C2", "C3"):
        if cond == "C3" and c3_poses is None:
            results["conditions"][cond] = {"status": "UNAVAILABLE", **c3_note}
            print(f"   {cond}: UNAVAILABLE (no re-run bag)")
            continue
        poses_all = pose_injected_frame(cond, inj_kfs, pre + keys, ref_poses, c3_poses)
        # Each condition gets its own pre-onset SE(3) onto the clean frame, fitted on pre-onset
        # poses only -- the same rule for all four, so no condition is helped by a transform
        # fitted on the window it is being scored on.
        _ids = [i for i in pre if i in poses_all]
        _mt, _mi, _mc = V.associate(
            np.asarray([inj_kfs[i]["ts"] for i in _ids]),
            np.asarray([poses_all[i][:3, 3] for i in _ids]), cln_ts, cln_xyz)
        R_c, t_c = V.umeyama(_mi, _mc)
        print(f"   {cond}: own pre-onset alignment from {len(_mi)} pairs, "
              f"|t|={np.linalg.norm(t_c):.4f} m")
        pts_all, empty_ids, used, by_key = [], [], 0, {}
        missing_pose, missing_obs = [], []
        in_window = {i: (start_ns <= kf_ns[i] <= end_ns) for i in keys}
        removed, removed_of = 0, 0
        removed_w, removed_w_of = 0, 0
        for i in keys:
            if i not in poses_all:
                missing_pose.append(int(i))
                continue
            body = inj_kfs[i]["pts"]
            if cond == "C2":
                # oracle: only inside the absolute injection window, geometry only
                if in_window[i]:
                    m = oracle_bag_mask(body)
                    removed += int(m.sum())
                    removed_of += len(body)
                    removed_w += int(m.sum())
                    removed_w_of += len(body)
                    body = body[~m]
            elif cond == "C3":
                fb = c3_by_stamp.get(round(inj_kfs[i]["ts"], 6))
                if fb is not None:
                    removed += len(body) - len(fb)
                    removed_of += len(body)
                    if in_window[i]:
                        removed_w += len(body) - len(fb)
                        removed_w_of += len(body)
                body = fb
            if body is None or len(body) == 0:
                missing_obs.append(int(i))
                continue
            T = poses_all[i]
            w = body @ T[:3, :3].T + T[:3, 3]
            w = w @ R_c.T + t_c
            if len(w) > V.KF_CAP:
                w = w[:: max(1, len(w) // V.KF_CAP)][:V.KF_CAP]
            pts_all.append(w)
            by_key[i] = w
            used += 1
        if not pts_all:
            results["conditions"][cond] = {"status": "UNAVAILABLE",
                                           "missing_pose_ids": missing_pose,
                                           "missing_observation_ids": missing_obs}
            continue
        pts = np.vstack(pts_all)
        by_key_store[cond] = dict(by_key)
        pose_store[cond] = poses_all
        R_store[cond] = R_c
        t_store[cond] = t_c
        resid, ratio, radius, rms = local_plane_residual(pts, ref_tree, proxy_all)
        planar = ratio < PLANAR_RATIO
        well = (rms < WELL_RMS_M) & (radius < WELL_RADIUS_M)

        tree = cKDTree(pts)
        dq, _ = tree.query(cov_q, k=1, distance_upper_bound=2.0)
        cov = {f"covered_within_{t}m": float(np.mean(dq <= t)) for t in (0.25, 0.5, 1.0)}
        _rq, _qq, _radq, rmsq = local_plane_residual(cov_q, ref_tree, proxy_all,
                                                     exclude_self=True)
        q_well = (rmsq < WELL_RMS_M) & (_radq < WELL_RADIUS_M)
        cov_well = {f"covered_within_{t}m": float(np.mean(dq[q_well] <= t))
                    for t in (0.25, 0.5, 1.0)}

        comp = connectivity(voxel_keys(pts))
        comp20 = connectivity(voxel_keys_scale(pts, 0.20))
        pk = [i for i in keys if i in poses_all and i in by_key]
        pose_xyz = np.asarray([poses_all[i][:3, 3] for i in pk]) @ R_c.T + t_c
        gap = trajectory_gap(by_key, pk, pose_xyz, [inj_kfs[i]["ts"] for i in pk])
        ref_xyz = np.asarray([ref_poses[i][:3, 3] for i in pk]) @ R_ic.T + t_ic
        dev = np.linalg.norm(pose_xyz - ref_xyz, axis=1)

        results["conditions"][cond] = {
            "label": CONDITION_LABEL[cond],
            "label_note": CONDITION_NOTE[cond],
            "keys_requested": len(keys),
            "keyframes_committed": used,
            "committed_ids": sorted(by_key),
            "missing_pose": len(missing_pose),
            "missing_pose_ids": missing_pose,
            "missing_observation": len(missing_obs),
            "missing_observation_ids": missing_obs,
            "n_points": int(len(pts)),
            "removed_fraction_of_input": (float(removed / removed_of) if removed_of else None),
            "removed_fraction_in_window": (float(removed_w / removed_w_of) if removed_w_of
                                           else None),
            "removed_points": int(removed),
            "own_pre_onset_alignment": {"n_pairs": int(len(_mi)),
                                        "translation_m": float(np.linalg.norm(t_c))},
            "pose_deviation_from_reference_m": {
                "median": float(np.median(dev)), "p90": float(np.percentile(dev, 90)),
                "max": float(np.max(dev))},
            "plane_distance": {
                "all": tail_stats(resid),
                "well_constrained_reference": tail_stats(resid[well]),
                "other_reference": tail_stats(resid[~well]),
                "well_constrained_fraction": float(well.mean()),
                "planar_neighbourhood": tail_stats(resid[planar]),
                "planar_fraction": float(planar.mean()),
            },
            "coverage": cov,
            "coverage_on_well_constrained_queries": cov_well,
            "well_constrained_query_fraction": float(q_well.mean()),
            "connectivity_voxel_0.10m": comp,
            "connectivity_voxel_0.20m": comp20,
            "trajectory_support": gap,
        }
        print(f"   {cond}: KF={used}/{len(keys)} pts={len(pts)} "
              f"tail0.5(all)={tail_stats(resid)['tail_over_0.5m']:.4f} "
              f"(well={tail_stats(resid[well])['tail_over_0.5m']}) "
              f"cov0.5={cov['covered_within_0.5m']:.4f} "
              f"comps={comp['n_components']} largest={comp['largest_fraction']:.3f} "
              f"gaps={gap['gap_keyframes']}")

    # ---- common support and the diagnostic subset ---------------------------------------
    # C0-C2 commit all 445 keys; C3's re-run publishes no odometry for some of them, so the
    # per-condition tables above use different denominators.  The comparison that isolates the
    # condition effect is the one on the intersection, reported here.  The 259-frame diagnostic
    # subset from M0 is reported the same way, as a subset, never as the population.
    def _group_summary(name, id_list):
        ids_common = None
        for c in ("C0", "C1", "C2", "C3"):
            ids_common = set(by_key_store.get(c, {})) if ids_common is None \
                else (ids_common & set(by_key_store.get(c, {})))
        sel = [i for i in id_list if i in (ids_common or set())]
        block = {"n_keys": len(sel), "ids": sel}
        for c in ("C0", "C1", "C2", "C3"):
            if c not in by_key_store or not sel:
                continue
            pts_c = np.vstack([by_key_store[c][i] for i in sel])
            r_c, _ra, rad_c, rms_c = local_plane_residual(pts_c, ref_tree, proxy_all)
            well_c = (rms_c < WELL_RMS_M) & (rad_c < WELL_RADIUS_M)
            tree_c = cKDTree(pts_c)
            dq_c, _ = tree_c.query(cov_q, k=1, distance_upper_bound=2.0)
            pose_c = np.asarray([pose_store[c][i][:3, 3] for i in sel]) @ R_store[c].T \
                + t_store[c]
            gap_c = trajectory_gap({i: by_key_store[c][i] for i in sel}, sel, pose_c,
                                   [inj_kfs[i]["ts"] for i in sel])
            block[c] = {
                "n_points": int(len(pts_c)),
                "plane_distance_all": tail_stats(r_c),
                "plane_distance_well": tail_stats(r_c[well_c]),
                "well_fraction": float(well_c.mean()),
                "coverage_0.5m": float(np.mean(dq_c <= 0.5)),
                "connectivity_voxel_0.10m": connectivity(voxel_keys(pts_c)),
                "connectivity_voxel_0.20m": connectivity(voxel_keys_scale(pts_c, 0.20)),
                "trajectory_support": gap_c,
            }
        results[name] = block
        print(f"[] {name}: {len(sel)} keys (of {len(id_list)} listed)")
        return block

    if "C3" in results["conditions"] and results["conditions"]["C3"].get("keyframes_committed"):
        # lengths are not comparable: the injected scans are capped at 15000 by the loader while
        # the filtered bag is full resolution, so take the ratio from the filter report.
        results["conditions"]["C3"]["removed_fraction_in_window"] = (
            results["_meta"]["real_filter"]["strip_fraction_in_window"])
        results["conditions"]["C3"]["removed_fraction_source"] = (
            "/tmp/filtered_bag_report.json per-frame counts (full resolution)")

    if by_key_store:
        _group_summary("common_support", keys)
        _group_summary("diagnostic_subset", subset_ids)

    with open(RESULT_JSON, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=1, default=float)
    print(f"\nsaved {RESULT_JSON}")


def build_filtered_bag(in_path=INJ_SCANS, out_path=FILTERED_BAG):
    """Apply the repository's near-field mixture filter to every scan and write a replayable bag.

    The filter is `slam_recovery.repair.point_mixture_repairer.filter_self_consistent_near_field_
    contaminants` with its shipped defaults -- not an oracle and not a hand-written rule.  Only
    the /velodyne_points payload changes; every other topic is copied byte for byte.
    """
    from rosbags.rosbag1 import Writer

    cfg = MixtureFilterConfig()
    per_frame, n_kept, n_all = [], 0, 0
    with V.Reader(in_path) as r:
        w = Writer(out_path)
        w.open()
        try:
            conns = {c.topic: w.add_connection(c.topic, c.msgtype, typestore=V.TYPESTORE)
                     for c in r.connections}
            for conn, t, raw in r.messages():
                if conn.topic != V.SCAN_TOPIC:
                    w.write(conns[conn.topic], t, raw)
                    continue
                m = V.TYPESTORE.deserialize_ros1(raw, conn.msgtype)
                buf = np.asarray(m.data, dtype=np.uint8)
                step = int(m.point_step)
                a = np.frombuffer(buf.tobytes(), dtype=V._cloud_dtype(m))
                pts = np.column_stack([a["x"], a["y"], a["z"], a["intensity"]]).astype(np.float64)
                keep, ratio, min_eig, rep = filter_self_consistent_near_field_contaminants(pts, cfg)
                rows = buf.reshape(len(a), step)
                kept = rows[keep].tobytes()
                m.data = np.frombuffer(kept, dtype=np.uint8)
                m.width = int(keep.sum())
                m.height = 1
                m.row_step = int(step) * m.width
                w.write(conns[conn.topic], t, V.TYPESTORE.serialize_ros1(m, conn.msgtype))
                n_kept += int(keep.sum())
                n_all += len(a)
                per_frame.append({"t": round(float(m.header.stamp.sec
                                                  + m.header.stamp.nanosec * 1e-9), 3),
                                  "n": int(len(a)), "kept": int(keep.sum()),
                                  "strip_fraction": round(float(np.mean(~keep)), 4),
                                  "contam_ratio": round(float(ratio), 4),
                                  "min_bg_eigenvalue": round(float(min_eig), 4),
                                  "repairable": bool(rep)})
        finally:
            w.close()
    side = {"input": in_path, "output": out_path, "filter": "MixtureFilterConfig() defaults",
            "points_in": n_all, "points_kept": n_kept,
            "global_strip_fraction": round(1.0 - n_kept / max(n_all, 1), 4),
            "frames": len(per_frame),
            "frames_stripping_gt_10pct": int(sum(1 for f in per_frame
                                                 if f["strip_fraction"] > 0.10)),
            "per_frame": per_frame}
    with open("/tmp/filtered_bag_report.json", "w", encoding="utf-8") as fh:
        json.dump(side, fh, indent=1)
    print(f"wrote {out_path}: {len(per_frame)} frames, kept {n_kept}/{n_all} points "
          f"({side['global_strip_fraction']:.1%} stripped), "
          f"{side['frames_stripping_gt_10pct']} frames stripped >10%")
    return side


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "measure"
    if cmd == "measure":
        main_measure()
    elif cmd == "build-filtered-bag":
        build_filtered_bag()
    else:
        raise SystemExit(f"unknown subcommand {cmd}")
