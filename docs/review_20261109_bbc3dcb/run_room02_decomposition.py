#!/usr/bin/env python3
"""room_02 decomposition: where does the failure come from?

Same 326 frames, same clean reference (CLEAN_RUN_FROM_RAW_WINDOW), same bounded metric.  Five arms
that differ only in the scan source and the pose source, so each consecutive pair isolates one
factor:

  A  raw injected      + host pose          (baseline, the score the paper would quote)
  B  raw injected      + clean reference pose      A->B isolates the POSE
  C  oracle-clean      + clean reference pose      B->C isolates the MEASUREMENT (oracle ceiling)
  D  actual filter     + clean reference pose      C->D isolates the FILTER versus the oracle
  E  actual filter     + actual re-estimation      D->E isolates the RE-ESTIMATION

The oracle used by C is exact rather than geometric: inside the injection window the injector
rewrote only some rows of each scan, so the rows that differ from the clean frame at the same
header nanosecond are precisely the injected ones.

Reported: coverage and patch-unsupported per arm, the four deltas, the healthy-window removal of
the real filter against the oracle's (zero by construction), and the in-window unsupported
fraction per arm.

    python3 -B docs/review_20261109_bbc3dcb/run_room02_decomposition.py
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
CLN_SCANS = "/tmp/fastlivo/room02_clean_60s.bag"
CLN_POSES = "/tmp/fastlivo/res_room02_clean_60s.bag"
FILTERED = "/tmp/fastlivo/room02_inj43_filtered.bag"
RERUN = "/tmp/fastlivo/res_room02_filtered.bag"
RESULTS = os.path.join(_HERE, "room02_decomposition_results.json")

ARMS = {"A": ("RAW_INJECTED", "HOST"),
        "B": ("RAW_INJECTED", "CLEAN_REFERENCE"),
        "C": ("ORACLE_CLEAN", "CLEAN_REFERENCE"),
        "D": ("ACTUAL_FILTER", "CLEAN_REFERENCE"),
        "E": ("ACTUAL_FILTER", "ACTUAL_REESTIMATION")}


def _raw(path):
    out = {}
    with V.Reader(path) as r:
        for conn, _t, raw in r.messages(
                connections=[c for c in r.connections if c.topic == V.SCAN_TOPIC]):
            m = V.TYPESTORE.deserialize_ros1(raw, conn.msgtype)
            ns = int(m.header.stamp.sec) * 10**9 + int(m.header.stamp.nanosec)
            out[ns] = (int(m.point_step), np.asarray(m.data, dtype=np.uint8).tobytes(),
                       V._cloud_dtype(m))
    return out


def main():
    sha = {r: V._sha_file(p) for r, p in
           (("injected_scans", INJ_SCANS), ("injected_poses", INJ_POSES),
            ("clean_scans", CLN_SCANS), ("clean_poses", CLN_POSES),
            ("filtered_scans", FILTERED), ("rerun_poses", RERUN))}

    inj_raw, cln_raw = _raw(INJ_SCANS), _raw(CLN_SCANS)
    common = sorted(set(inj_raw) & set(cln_raw))
    differing = {ns for ns in common if inj_raw[ns] != cln_raw[ns]}
    onset_ns, end_ns = min(differing), max(differing)
    print(f"[] oracle window: {len(differing)}/{len(common)} frames, {onset_ns} .. {end_ns}")

    inj_scans, _ = V.load_scans(INJ_SCANS, sha["injected_scans"])
    cln_scans, _ = V.load_scans(CLN_SCANS, sha["clean_scans"])
    inj_kfs, _ = V.pair_keyframes(inj_scans, V.load_poses(INJ_POSES))
    cln_kfs, _ = V.pair_keyframes(cln_scans, V.load_poses(CLN_POSES))
    ns_all = R.load_scan_ns(INJ_SCANS, sha["injected_scans"])
    j = np.searchsorted(ns_all, np.asarray([round(k["ts"] * 1e9) for k in inj_kfs],
                                           dtype=np.int64))
    kf_ns = np.asarray([int(ns_all[min([c for c in (q - 1, q) if 0 <= c < len(ns_all)],
                                       key=lambda c: abs(ns_all[c] / 1e9 - t))])
                        for t, q in zip([k["ts"] for k in inj_kfs], j)], dtype=np.int64)
    prefix = [i for i in range(len(inj_kfs)) if kf_ns[i] < onset_ns]
    keys = [i for i in range(len(inj_kfs)) if kf_ns[i] >= onset_ns]

    by_stamp = {round(t, 6): p for t, p in V.load_scans(FILTERED, sha["filtered_scans"])[0]}
    host_poses, _ = R.pose_lookup(V.load_poses(INJ_POSES), range(len(inj_kfs)),
                                  lambda i: inj_kfs[i]["ts"])
    rerun_poses, _ = R.pose_lookup(V.load_poses(RERUN), range(len(inj_kfs)),
                                   lambda i: inj_kfs[i]["ts"])
    cln_poses, _ = R.pose_lookup(V.load_poses(CLN_POSES), range(len(inj_kfs)),
                                 lambda i: inj_kfs[i]["ts"])

    cln_ts = np.asarray([k["ts"] for k in cln_kfs])
    cln_xyz = np.asarray([k["T"][:3, 3] for k in cln_kfs])

    def _align(poses):
        use = [i for i in prefix if i in poses]
        _mt, mi, mc = V.associate(np.asarray([inj_kfs[i]["ts"] for i in use]),
                                  np.asarray([poses[i][:3, 3] for i in use]), cln_ts, cln_xyz)
        return V.umeyama(mi, mc)

    # clean reference poses expressed in the injected frame (same construction as hall_01 C1)
    _mt, mi, mc = V.associate(np.asarray([inj_kfs[i]["ts"] for i in prefix if i in host_poses]),
                              np.asarray([host_poses[i][:3, 3] for i in prefix if i in host_poses]),
                              cln_ts, cln_xyz)
    R_hc, t_hc = V.umeyama(mi, mc)
    T_inv = np.eye(4)
    T_inv[:3, :3] = R_hc.T
    T_inv[:3, 3] = -R_hc.T @ t_hc
    ref_poses = {i: T_inv @ cln_poses[i] for i in cln_poses}

    frames = [i for i in keys
              if i in rerun_poses and round(inj_kfs[i]["ts"], 6) in by_stamp]
    missing = [int(i) for i in keys if i not in frames]
    print(f"[] frame set {len(frames)} of {len(keys)} (missing {len(missing)})")

    # ---- oracle scan: drop exactly the rows the injector rewrote -------------------------
    def _oracle_body(i):
        ns = int(kf_ns[i])
        step, raw_i, dt = inj_raw[ns]
        raw_c = cln_raw[ns][1]
        a = np.frombuffer(raw_i, dtype=np.uint8).reshape(-1, step)
        b = np.frombuffer(raw_c, dtype=np.uint8).reshape(-1, step)
        if a.shape != b.shape:
            return inj_kfs[i]["pts"]           # cannot split rows; fall back to the raw scan
        keep_row = ~(a != b).any(axis=1)
        xyz = np.frombuffer(raw_i, dtype=dt)
        p = np.column_stack([xyz["x"], xyz["y"], xyz["z"]]).astype(np.float64)
        rr = np.linalg.norm(p, axis=1)
        keep = keep_row & (rr > 0.5) & (rr < 30.0)
        p = p[keep]
        if len(p) > V.MAX_KF_POINTS:
            p = p[:: max(1, len(p) // V.MAX_KF_POINTS)][:V.MAX_KF_POINTS]
        return p

    def _map(ids, poses, source):
        out = []
        for i in ids:
            if source == "RAW_INJECTED":
                body = inj_kfs[i]["pts"]
            elif source == "ORACLE_CLEAN":
                body = _oracle_body(i) if kf_ns[i] in differing else inj_kfs[i]["pts"]
            else:
                body = by_stamp[round(inj_kfs[i]["ts"], 6)]
            w = body @ poses[i][:3, :3].T + poses[i][:3, 3]
            if len(w) > V.KF_CAP:
                w = w[:: max(1, len(w) // V.KF_CAP)][:V.KF_CAP]
            out.append(w)
        return np.vstack(out)

    proxy = np.vstack([V.world_pts(k) for k in cln_kfs])
    proxy_tree = cKDTree(proxy)

    pose_for = {"HOST": host_poses, "CLEAN_REFERENCE": ref_poses,
                "ACTUAL_REESTIMATION": rerun_poses}
    res_arms, maps = {}, {}
    for tag, (source, pose_src) in ARMS.items():
        poses = pose_for[pose_src]
        R_a, t_a = _align(poses)
        pts = _map(frames, poses, source) @ R_a.T + t_a
        tree = cKDTree(pts)
        d, _ = tree.query(proxy, k=1, distance_upper_bound=R.R_NN)
        covered = np.isfinite(d)
        bm = R.bounded_metrics(pts, proxy_tree, proxy)
        uns = int(round(bm["patch"]["unsupported_fraction"] * len(pts)))
        res_arms[tag] = {
            "scan_source": source, "pose_source": pose_src,
            "map_points": int(len(pts)),
            "proxy_covered": int(covered.sum()),
            "proxy_coverage_fraction": float(covered.mean()),
            "patch_unsupported_points": uns,
            "patch_unsupported_fraction": float(uns / len(pts)),
            "patch_median_m": bm["patch"]["median_m"],
        }
        maps[tag] = pts
        print(f"   {tag} {source:14s}+{pose_src:20s} cover {covered.mean():.4f} "
              f"unsup {uns/len(pts):.4f}")

    deltas = {}
    for a, b in (("A", "B"), ("B", "C"), ("C", "D"), ("D", "E")):
        deltas[f"{a}->{b}"] = {
            "coverage_delta": res_arms[b]["proxy_coverage_fraction"]
            - res_arms[a]["proxy_coverage_fraction"],
            "unsupported_delta": res_arms[b]["patch_unsupported_fraction"]
            - res_arms[a]["patch_unsupported_fraction"],
            "isolates": {"A->B": "pose", "B->C": "measurement (oracle ceiling)",
                         "C->D": "filter versus oracle", "D->E": "re-estimation"}[f"{a}->{b}"]}

    # ---- healthy window: filter removal versus oracle removal ----------------------------
    rep = os.path.join(_HERE, "room02_filter_report.json")
    healthy = {"status": "MISSING"}
    if os.path.exists(rep):
        fr = json.load(open(rep))
        ok = (fr.get("binding", {}).get("verdict") == "BOUND"
              and fr.get("input_sha256") == sha["injected_scans"])
        if not ok:
            healthy = {"status": "STALE_AUDIT"}
        else:
            pf = fr["per_frame"]
            out_frames = [f for f in pf if f["t"] * 1e9 < onset_ns - 5e5
                          or f["t"] * 1e9 > end_ns + 5e5]
            rem = sum(f["n"] - f["kept"] for f in out_frames)
            tot = sum(f["n"] for f in out_frames)
            # oracle removal outside the window is zero by construction; verify it
            oracle_out = 0
            for ns, (step, raw_i, _dt) in inj_raw.items():
                if ns in cln_raw and (ns < onset_ns or ns > end_ns):
                    a = np.frombuffer(raw_i, np.uint8).reshape(-1, step)
                    b = np.frombuffer(cln_raw[ns][1], np.uint8).reshape(-1, step)
                    if a.shape == b.shape:
                        oracle_out += int((a != b).any(axis=1).sum())
            healthy = {"status": "BOUND",
                       "input_sha256": fr.get("input_sha256"),
                       "frames_outside": len(out_frames), "points_outside": int(tot),
                       "real_filter_removed": int(rem),
                       "real_filter_fraction": float(rem / tot) if tot else None,
                       "oracle_removed": int(oracle_out),
                       "oracle_fraction": float(oracle_out / tot) if tot else None}

    res = {
        "protocol": {"source": "docs/MILESTONE_fixed_input_repair.md (M3 decomposition)",
                     "question": "is the room_02 failure measurement (filter), native "
                                 "re-estimation, or reference quality?",
                     "arms": {k: {"scan": v[0], "pose": v[1]} for k, v in ARMS.items()}},
        "provenance": "REAL_HOST for A and E; B/C/D reuse existing poses and scans",
        "reference": {"source": "CLEAN_RUN_FROM_RAW_WINDOW", "note": "proxy, not GT; single "
                                                                     "sequence"},
        "inputs_sha256": sha,
        "injection_window": {"onset_ns": onset_ns, "end_ns": end_ns,
                             "differing_frames": len(differing)},
        "frame_set": {"n_frames": len(frames), "n_keys": len(keys), "missing": missing,
                      "ns_sha256": hashlib.sha256(",".join(str(int(kf_ns[i])) for i in
                                                          sorted(frames)).encode()).hexdigest()},
        "arms": res_arms, "deltas": deltas, "healthy_window": healthy,
    }
    with open(RESULTS, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=float)
    print(f"[] deltas: " + ", ".join(f"{k} cov {v['coverage_delta']:+.4f} unsup "
                                     f"{v['unsupported_delta']:+.4f}" for k, v in deltas.items()))
    print(f"saved {RESULTS}")


if __name__ == "__main__":
    main()
