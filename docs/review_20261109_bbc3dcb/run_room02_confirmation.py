#!/usr/bin/env python3
"""Independent-sequence confirmation on room_02 (4.30 m injection).

Preregistered in docs/MILESTONE_fixed_input_repair.md (main 107c05a).  Same filter, same host
config, same runner and the same reconstruction as hall_01; the only change is the sequence.

  R   the injected scan + the host's own pose (the archived run on room02_inj43.bag)
  C3  the filtered scan + the re-run pose on the filtered bag

The injection window is measured per frame by raw-buffer equality against the clean room_02
recording -- an oracle, not an assumption.  The frame set is frozen and exported before any metric:
every keyframe that has both a filtered scan and a re-run pose.

Criterion (same as hall_01, declared here before the numbers): the novel added subset must have
more supported than unsupported points, and the added unsupported fraction must not exceed R's.
Failure is reported as failure; no region, frame-set or threshold is retried.

    python3 -B docs/review_20261109_bbc3dcb/run_room02_confirmation.py
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
import verify_four_arm_independent as V          # noqa: E402
import run_fixed_input_repair_c0c3 as R          # noqa: E402

INJ_SCANS = "/tmp/fastlivo/room02_inj43.bag"
INJ_POSES = "/tmp/fastlivo/res_r2_inj43_vis.bag"
CLN_SCANS = os.environ.get("ROOM02_CLEAN_BAG",
                          "/tmp/fastlivo/room02_clean_60s.bag")
CLN_POSES = os.environ.get("ROOM02_CLEAN_POSES",
                          "/tmp/fastlivo/res_room02_clean_60s.bag")
FILTERED = "/tmp/fastlivo/room02_inj43_filtered.bag"
RERUN = "/tmp/fastlivo/res_room02_filtered.bag"
RESULTS = os.path.join(_HERE, "room02_confirmation_results.json")
FREEZE = os.path.join(_HERE, "room02_frozen_frames.json")

CRITERION = ("novel_added_supported > novel_added_unsupported AND "
             "added_unsupported_fraction <= R_unsupported_fraction")


def _stamps(path, topic):
    out = []
    with V.Reader(path) as r:
        conns = [c for c in r.connections if c.topic == topic]
        for conn, _t, raw in r.messages(connections=conns):
            m = V.TYPESTORE.deserialize_ros1(raw, conn.msgtype)
            out.append(int(m.header.stamp.sec) * 10**9 + int(m.header.stamp.nanosec))
    return np.asarray(sorted(out), dtype=np.int64)


def _raw_by_ns(path, topic):
    out = {}
    with V.Reader(path) as r:
        conns = [c for c in r.connections if c.topic == topic]
        for conn, _t, raw in r.messages(connections=conns):
            m = V.TYPESTORE.deserialize_ros1(raw, conn.msgtype)
            ns = int(m.header.stamp.sec) * 10**9 + int(m.header.stamp.nanosec)
            out[ns] = bytes(np.asarray(m.data, dtype=np.uint8).tobytes())
    return out


def main():
    sha = {r: V._sha_file(p) for r, p in
           (("injected_scans", INJ_SCANS), ("injected_poses", INJ_POSES),
            ("clean_scans", CLN_SCANS), ("clean_poses", CLN_POSES),
            ("filtered_scans", FILTERED), ("rerun_poses", RERUN))}

    # ---- oracle injection window: per-frame raw-buffer equality --------------------------
    inj_raw = _raw_by_ns(INJ_SCANS, "/velodyne_points")
    cln_raw = _raw_by_ns(CLN_SCANS, "/velodyne_points")
    common = sorted(set(inj_raw) & set(cln_raw))
    diff = [ns for ns in common if inj_raw[ns] != cln_raw[ns]]
    if not diff:
        raise SystemExit("no differing frame: this is not an injected recording")
    if len(common) < len(inj_raw):
        raise SystemExit(f"clean bag covers only {len(common)} of {len(inj_raw)} injected frames; "
                         f"refusing to score a partial reference")
    onset_ns, end_ns = int(diff[0]), int(diff[-1])
    print(f"[] oracle window: {len(diff)}/{len(common)} frames differ, "
          f"{onset_ns} .. {end_ns}")

    # ---- loaders ------------------------------------------------------------------------
    inj_scans, _ = V.load_scans(INJ_SCANS, sha["injected_scans"])
    cln_scans, _ = V.load_scans(CLN_SCANS, sha["clean_scans"])
    inj_kfs, _ = V.pair_keyframes(inj_scans, V.load_poses(INJ_POSES))
    cln_kfs, _ = V.pair_keyframes(cln_scans, V.load_poses(CLN_POSES))
    ns_all = R.load_scan_ns(INJ_SCANS, sha["injected_scans"])
    pos = np.searchsorted(ns_all, np.asarray([round(k["ts"] * 1e9) for k in inj_kfs],
                                             dtype=np.int64))
    kf_ns = np.asarray([int(ns_all[min([c for c in (j - 1, j) if 0 <= c < len(ns_all)],
                                       key=lambda c: abs(ns_all[c] / 1e9 - t))])
                        for t, j in zip([k["ts"] for k in inj_kfs], pos)], dtype=np.int64)
    keys = [i for i in range(len(inj_kfs)) if kf_ns[i] >= onset_ns]
    prefix = [i for i in range(len(inj_kfs)) if kf_ns[i] < onset_ns]
    print(f"[] keyframes: {len(keys)} quarantine, {len(prefix)} pre-onset")

    by_stamp = {}
    f_scans, _ = V.load_scans(FILTERED, sha["filtered_scans"])
    by_stamp = {round(t, 6): p for t, p in f_scans}
    _rerun_ts, _rx, _rq = V.load_poses(RERUN)
    rerun_poses, rerun_stats = R.pose_lookup((_rerun_ts, _rx, _rq), range(len(inj_kfs)),
                                             lambda i: inj_kfs[i]["ts"])
    host_poses, host_stats = R.pose_lookup(V.load_poses(INJ_POSES), range(len(inj_kfs)),
                                           lambda i: inj_kfs[i]["ts"])

    # ---- frozen frame set: filtered scan AND re-run pose --------------------------------
    frames = [i for i in keys
              if i in rerun_poses and round(inj_kfs[i]["ts"], 6) in by_stamp
              and len(by_stamp[round(inj_kfs[i]["ts"], 6)]) > 0]
    missing = [int(i) for i in keys if i not in frames]
    def _hash_ns(vals):
        return hashlib.sha256(",".join(str(int(v)) for v in sorted(vals)).encode()).hexdigest()

    # Primary population first: every scan of the prepared window, before anything is dropped.
    primary_ns = [int(x) for x in ns_all]
    missing_reasons = []
    for i in missing:
        ts = inj_kfs[i]["ts"]
        has_scan = round(ts, 6) in by_stamp and len(by_stamp[round(ts, 6)]) > 0
        dt = None
        j = int(np.searchsorted(_rerun_ts, ts))
        near = [k for k in (j - 1, j) if 0 <= k < len(_rerun_ts)]
        if near:
            dt = float(abs(_rerun_ts[min(near, key=lambda k: abs(_rerun_ts[k] - ts))] - ts))
        missing_reasons.append({
            "id": int(i), "ns": int(kf_ns[i]),
            "cause": ("FILTERED_SCAN_MISSING" if not has_scan
                      else "NO_RERUN_POSE_UNDER_THE_75MS_RULE"),
            "nearest_rerun_pose_dt_ms": None if dt is None else round(dt * 1e3, 2)})
    causes = {}
    for m in missing_reasons:
        causes[m["cause"]] = causes.get(m["cause"], 0) + 1

    freeze = {
        "primary_scan_set": {"definition": "every scan of the prepared room_02 window",
                             "count": len(primary_ns), "ns_sha256": _hash_ns(primary_ns)},
        "healthy_prefix": {"definition": "paired keyframes with ns < onset_ns",
                           "count": len(prefix),
                           "ns_sha256": _hash_ns([kf_ns[i] for i in prefix])},
        "quarantine_keys": {"definition": "paired keyframes with ns >= onset_ns",
                            "count": len(keys), "ns_sha256": _hash_ns([kf_ns[i] for i in keys])},
        "frame_set": {"definition": "quarantine keyframes with both a filtered scan and a re-run "
                                    "pose",
                      "n_frames": len(frames), "ns_sha256": _hash_ns([kf_ns[i] for i in frames])},
        "missing": {"count": len(missing), "by_cause": causes, "detail": missing_reasons},
        "onset_ns": onset_ns, "end_ns": end_ns,
        "injection_window_measured_by": "raw buffer equality against the clean recording",
        "rerun_pairing": rerun_stats, "host_pairing": host_stats,
    }
    with open(FREEZE, "w", encoding="utf-8") as fh:
        json.dump(freeze, fh, indent=1)
    print(f"[] frozen frame set: {len(frames)} of {len(keys)} (missing {len(missing)})")

    cln_ts = np.asarray([k["ts"] for k in cln_kfs])
    cln_xyz = np.asarray([k["T"][:3, 3] for k in cln_kfs])

    def _align(poses):
        use = [i for i in prefix if i in poses]
        _mt, mi, mc = V.associate(np.asarray([inj_kfs[i]["ts"] for i in use]),
                                  np.asarray([poses[i][:3, 3] for i in use]), cln_ts, cln_xyz)
        return V.umeyama(mi, mc)

    R_h, t_h = _align(host_poses)
    R_c, t_c = _align(rerun_poses)

    def _map(ids, poses, filtered):
        out = []
        for i in ids:
            body = by_stamp[round(inj_kfs[i]["ts"], 6)] if filtered else inj_kfs[i]["pts"]
            w = body @ poses[i][:3, :3].T + poses[i][:3, 3]
            if len(w) > V.KF_CAP:
                w = w[:: max(1, len(w) // V.KF_CAP)][:V.KF_CAP]
            out.append(w)
        return np.vstack(out)

    r_pts = _map(frames, host_poses, False) @ R_h.T + t_h
    c3_pts = _map(frames, rerun_poses, True) @ R_c.T + t_c
    base_pts = _map(prefix, host_poses, False) @ R_h.T + t_h
    print(f"[] maps: R {len(r_pts)}, C3 {len(c3_pts)}, base {len(base_pts)}")

    proxy = np.vstack([V.world_pts(k) for k in cln_kfs])
    proxy_tree = cKDTree(proxy)

    def _arm(pts):
        tree = cKDTree(pts)
        d, _ = tree.query(proxy, k=1, distance_upper_bound=R.R_NN)
        covered = np.isfinite(d)
        bm = R.bounded_metrics(pts, proxy_tree, proxy)
        uns = int(round(bm["patch"]["unsupported_fraction"] * len(pts)))
        return {"map_points": int(len(pts)), "proxy_covered": int(covered.sum()),
                "proxy_coverage_fraction": float(covered.mean()),
                "patch_unsupported_points": uns,
                "patch_unsupported_fraction": float(uns / len(pts))}, tree

    s_r, r_tree = _arm(r_pts)
    s_c3, c3_tree = _arm(c3_pts)
    base_tree = cKDTree(base_pts)

    def _split(subset):
        if not len(subset):
            return {"n": 0, "supported": 0, "unsupported": 0, "supported_fraction": None}
        bm = R.bounded_metrics(subset, proxy_tree, proxy)
        uns = int(round(bm["patch"]["unsupported_fraction"] * len(subset)))
        out = base_tree.query(subset, k=1, distance_upper_bound=R.R_NN)[0]
        return {"n": int(len(subset)), "supported": int(len(subset) - uns), "unsupported": uns,
                "supported_fraction": float((len(subset) - uns) / len(subset)),
                "novel_outside_base": int((~np.isfinite(out)).sum())}

    added = c3_pts[~np.isfinite(r_tree.query(c3_pts, k=1,
                                             distance_upper_bound=R.R_NN)[0])]
    added_novel = added[~np.isfinite(base_tree.query(added, k=1,
                                                     distance_upper_bound=R.R_NN)[0])]
    lost = r_pts[~np.isfinite(c3_tree.query(r_pts, k=1,
                                            distance_upper_bound=R.R_NN)[0])]
    lost_novel = lost[~np.isfinite(base_tree.query(lost, k=1,
                                                   distance_upper_bound=R.R_NN)[0])]
    sp_add, sp_add_n = _split(added), _split(added_novel)
    sp_lost, sp_lost_n = _split(lost), _split(lost_novel)
    lost_good = {"definition": "R points C3 does not have that are supported",
                 "points": int(sp_lost["supported"]),
                 "fraction_of_lost": (sp_lost["supported"] / sp_lost["n"]
                                      if sp_lost["n"] else None),
                 "novel_outside_base": int(sp_lost_n["supported"])}

    frac_added_unsup = sp_add["unsupported"] / sp_add["n"] if sp_add["n"] else None
    cond_a = sp_add_n["supported"] > sp_add_n["unsupported"]
    cond_b = frac_added_unsup is not None and frac_added_unsup <= s_r["patch_unsupported_fraction"]
    verdict = "REPAIR_BENEFIT_SUPPORTED" if (cond_a and cond_b) else \
        "SAME_FRAME_COMPARISON_DOES_NOT_SUPPORT_NET_BENEFIT"

    # healthy-region removal, from the filter build sidecar
    healthy = None
    rep = "/tmp/filtered_bag_report.json"
    if os.path.exists(rep):
        fr = json.load(open(rep))
        pf = fr.get("per_frame", [])
        out_frames = [f for f in pf if not (onset_ns / 1e9 - 5e-4 <= f["t"] <= end_ns / 1e9 + 5e-4)]
        rem = sum(f["n"] - f["kept"] for f in out_frames)
        tot = sum(f["n"] for f in out_frames)
        healthy = {"frames_outside": len(out_frames), "points_outside": int(tot),
                   "removed_outside": int(rem),
                   "fraction_outside": float(rem / tot) if tot else None,
                   "frames_with_any_removal": int(sum(1 for f in out_frames
                                                      if f["n"] - f["kept"] > 0))}

    res = {
        "protocol": {
            "source": "docs/MILESTONE_fixed_input_repair.md @ 107c05a",
            "text": ("sequence room_02 at 4.30 m injection; same filter, same host config, same "
                     "runner, same reconstruction; injection window measured per frame by raw "
                     "buffer equality against clean room_02; frame set = frames with both a "
                     "filtered scan and a re-run pose, frozen and exported before metrics; "
                     "criterion: novel added supported > unsupported AND added unsupported "
                     "fraction <= R; report total and novel added/lost, service completeness with "
                     "declared frames as denominator, healthy-region removal; failure is reported "
                     "as failure; no ROI, frame-set or threshold retry."),
        },
        "provenance": "REAL_HOST for the new runs; R uses the archived host run",
        "reference": "clean run map (proxy), not GT; single sequence",
        "inputs_sha256": sha,
        "input_identity_chain": {
            "injected_scans": INJ_SCANS, "clean_reference_scans": CLN_SCANS,
            "clean_reference_poses": CLN_POSES,
            "host_poses_raw_arm": INJ_POSES, "filtered_scans": FILTERED,
            "rerun_poses": RERUN,
            "runner": os.path.join(_HERE, "fl_run_isolated.sh"),
            "runner_sha256": V._sha_file(os.path.join(_HERE, "fl_run_isolated.sh")),
            "host_binary_sha256": V._sha_file(
                "/home/R26534/fast_livo2_ws/devel/lib/fast_livo/fastlivo_mapping"),
            "configs": {"m2dgr": "/home/R26534/FAST-LIVO2/config/m2dgr.yaml",
                        "camera": "/home/R26534/FAST-LIVO2/config/camera_m2dgr.yaml"},
            "host_binary": "/home/R26534/fast_livo2_ws/devel/lib/fast_livo/fastlivo_mapping",
        },
        "evaluation_rules": {
            "nn_cap_m": R.R_NN, "patch_radius_m": R.R_PATCH, "patch_plane_rms_m": R.PATCH_RMS,
            "frame_set": "quarantine keyframes with both a filtered scan and a re-run pose",
            "completeness_denominator": "declared quarantine keys; a frame without output is "
                                        "MISSING and stays in the denominator",
            "healthy_region": "frames outside [onset_ns, end_ns]",
        },
        "injection_window": {"onset_ns": onset_ns, "end_ns": end_ns,
                             "method": "per-frame raw buffer equality (oracle)",
                             "differing_frames": len(diff), "common_frames": len(common)},
        "frame_set": freeze,
        "roi": {"definition": "the whole clean reference cloud",
                "n_points": int(len(proxy)),
                "reference_sha256": hashlib.sha256(proxy.astype("<f8").tobytes()).hexdigest()},
        "arms": {"R": {"label": "RAW_NATIVE", **s_r},
                 "C3": {"label": "OFFLINE_NATIVE_REESTIMATION", **s_c3}},
        "added_by_C3": {"total": sp_add, "novel_outside_base": sp_add_n},
        "lost_from_R": {"total": sp_lost, "novel_outside_base": sp_lost_n},
        "lost_good": lost_good,
        "service_completeness": {
            "declared_frames": len(keys), "frames_with_output": len(frames),
            "missing_frames": len(missing),
            "missing_by_cause": causes,
            "completeness": len(frames) / len(keys) if keys else None},
        "healthy_region_removal": healthy,
        "criterion": {"declared": CRITERION, "novel_added_supported_gt_unsupported": bool(cond_a),
                      "added_unsupported_fraction": frac_added_unsup,
                      "R_unsupported_fraction": s_r["patch_unsupported_fraction"],
                      "added_unsup_not_above_R": bool(cond_b), "verdict": verdict},
    }
    with open(RESULTS, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=float)

    print(f"[] R : {s_r['map_points']} pts, cover {s_r['proxy_covered']} "
          f"({s_r['proxy_coverage_fraction']:.4f}), unsup {s_r['patch_unsupported_points']} "
          f"({s_r['patch_unsupported_fraction']:.4f})")
    print(f"[] C3: {s_c3['map_points']} pts, cover {s_c3['proxy_covered']} "
          f"({s_c3['proxy_coverage_fraction']:.4f}), unsup {s_c3['patch_unsupported_points']} "
          f"({s_c3['patch_unsupported_fraction']:.4f})")
    print(f"[] added {sp_add['n']} (sup {sp_add['supported']} / unsup {sp_add['unsupported']}), "
          f"novel {sp_add_n['n']} (sup {sp_add_n['supported']} / unsup {sp_add_n['unsupported']})")
    print(f"[] lost {sp_lost['n']} (sup {sp_lost['supported']} / unsup {sp_lost['unsupported']}), "
          f"novel {sp_lost_n['n']} (sup {sp_lost_n['supported']} / unsup {sp_lost_n['unsupported']})")
    print(f"[] completeness {len(frames)}/{len(keys)}; healthy {healthy}")
    print(f"[] verdict: {verdict}")
    print(f"saved {RESULTS}")


if __name__ == "__main__":
    main()
