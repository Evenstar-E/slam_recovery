#!/usr/bin/env python3
"""T2 on the delivered trace run fl_native_20261112T115734Z_483777.

Read-only. No host run, no threshold change, no production edit. It applies the pre-registered
T2 protocol (T2_PROTOCOL.md) to one run: span-containment join, M/T from the availability log,
I from the trace's vec6/Ppre under the trace header's declarations, 0.5 s blocks, phase split,
and the known post-E2 no-catch-up tail. No normal reference exists, so every state is UNKNOWN
and every label-dependent metric is NOT_EVALUABLE; the deliverable is eligibility and intervals.

    python -I docs/ali_h_v1_research/t2_run.py --run /tmp/fl_native_20261112T115734Z_483777
"""

from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import math
import os
import sys
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional

import numpy as np

def so3_exp(w: np.ndarray) -> np.ndarray:
    w = np.asarray(w, dtype=np.float64).reshape(3)
    th = float(np.linalg.norm(w))
    K = np.array([[0.0, -w[2], w[1]], [w[2], 0.0, -w[0]], [-w[1], w[0], 0.0]])
    if th < 1e-12:
        return np.eye(3) + K + 0.5 * (K @ K)
    return (np.eye(3) + math.sin(th) / th * K
            + (1.0 - math.cos(th)) / (th * th) * (K @ K))


def so3_left_jacobian_inv(w: np.ndarray) -> np.ndarray:
    """V(w)^-1 for the SE(3) Log: V(w)^-1 = I - 0.5*hat(w) + c*hat(w)^2."""
    w = np.asarray(w, dtype=np.float64).reshape(3)
    th = float(np.linalg.norm(w))
    K = np.array([[0.0, -w[2], w[1]], [w[2], 0.0, -w[0]], [-w[1], w[0], 0.0]])
    if th < 1e-4:
        return np.eye(3) - 0.5 * K + (1.0 / 12.0) * (K @ K)
    c = (1.0 - 0.5 * th / math.tan(0.5 * th)) / (th * th)
    return np.eye(3) - 0.5 * K + c * (K @ K)


def quat_to_rot(q: np.ndarray) -> np.ndarray:
    x, y, z, w = np.asarray(q, dtype=np.float64)
    n = math.sqrt(x * x + y * y + z * z + w * w)
    if n < 1e-12:
        return np.eye(3)
    x, y, z, w = x / n, y / n, z / n, w / n
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ])


def exact_e(vec6: np.ndarray, R_post: np.ndarray) -> np.ndarray:
    """e_I = Log(inv(T_pre) T_post), with vec6 = state_pre - state_post (operator-).

    operator- returns [Log(R_post^T R_pre), pos_pre - pos_post].  Hence
    R_pre = R_post Exp(w), and the body-frame translation is -R_pre^T v.
    """
    w = np.asarray(vec6[:3], dtype=np.float64)
    v = np.asarray(vec6[3:], dtype=np.float64)
    R_pre = R_post @ so3_exp(w)
    rot = -w
    t_body = -R_pre.T @ v
    # SE(3) Log: the translation is V(rot)^-1 * t_body, not t_body itself.
    return np.concatenate([rot, so3_left_jacobian_inv(rot) @ t_body])


HERE = os.path.dirname(os.path.abspath(__file__))
BLOCK_NS = 500_000_000
E2_REL_S = 54.0
OLD_RUN_IDS = {"fl_native_20261112T065500Z_187992", "fl_native_20261112T070801Z_197026"}


def sha256(path: str, chunk: int = 1 << 22) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(chunk), b""):
            h.update(b)
    return h.hexdigest()


def _tail_value(tail: Dict[str, float], prefix: str, leaf: str) -> Optional[float]:
    key = f"{prefix}_{leaf}"
    if key in (tail or {}):
        return float(tail[key])
    if prefix == "pose" and leaf in (tail or {}):
        return float(tail[leaf])
    return None


def pose_from_tail(tail: Dict[str, float], prefix: str = "pose") -> Optional[np.ndarray]:
    """(x,y,z,qx,qy,qz,qw) from a named tail; prefix='pose' or 'pre_pose'."""
    if not tail:
        return None
    vals = [_tail_value(tail, prefix, k) for k in ("x", "y", "z", "qx", "qy", "qz", "qw")]
    if any(v is None for v in vals):
        return None
    return np.array(vals, dtype=np.float64)


def so3_log(R: np.ndarray) -> np.ndarray:
    R = np.asarray(R, dtype=np.float64)
    c = max(-1.0, min(1.0, 0.5 * (float(np.trace(R)) - 1.0)))
    th = math.acos(c)
    if th < 1e-12:
        return np.zeros(3)
    w = np.array([R[2, 1] - R[1, 2], R[0, 2] - R[2, 0], R[1, 0] - R[0, 1]]) / (2.0 * math.sin(th))
    return w * th


def e_i_from_poses(pre7: np.ndarray, post7: np.ndarray) -> np.ndarray:
    """e_I = Log(inv(T_pre) T_post) from same-row pre/post poses; SE(3) Log includes V^-1."""
    Tpre = np.eye(4); Tpre[:3, :3] = quat_to_rot(pre7[3:7]); Tpre[:3, 3] = pre7[0:3]
    Tpost = np.eye(4); Tpost[:3, :3] = quat_to_rot(post7[3:7]); Tpost[:3, 3] = post7[0:3]
    D = np.linalg.inv(Tpre) @ Tpost
    rot = so3_log(D[:3, :3])
    return np.concatenate([rot, so3_left_jacobian_inv(rot) @ D[:3, 3]])


POSE_LEAVES = ("x", "y", "z", "qx", "qy", "qz", "qw")


def expand_tail_names(tail_names: List[str]) -> List[str]:
    """Expand aggregate pose7 / pre_pose7 names into their 7 scalar field names."""
    keys = []
    for name in tail_names:
        if name == "pose7":
            keys += [f"pose_{k}" for k in POSE_LEAVES]
        elif name == "pre_pose7":
            keys += [f"pre_pose_{k}" for k in POSE_LEAVES]
        else:
            keys.append(name)
    return keys


def parse_trace(path: str) -> Dict[str, Any]:
    names: Optional[List[str]] = None
    rows, malformed = [], []
    with open(path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            if line.startswith("#"):
                parts = line.lstrip("#").strip().split()
                if parts and parts[0] == "idx":
                    names = parts
                continue
            f = line.split()
            if not f:
                continue
            if names is None:
                malformed.append({"line": lineno, "ncols": len(f)})
                continue
            col = {name: i for i, name in enumerate(names)}
            vec_start = names.index("r_chi2w") + 1
            block_end = vec_start + 78
            # v10 appends pose7; v11 appends pose7 + pre_pose7; parse them by NAME.
            tail_names = (names[names.index("Ppost6x6") + 1:]
                          if "Ppost6x6" in names else [])
            tail_keys = expand_tail_names(tail_names)
            if len(f) == block_end:
                pose_tail = None
            elif len(f) == block_end + len(tail_keys) and tail_keys:
                pose_tail = {tail_keys[i]: float(f[block_end + i])
                             for i in range(len(tail_keys))}
            else:
                malformed.append({"line": lineno, "ncols": len(f)})
                continue
            # Read scalars by NAME (v8 inserted n_scans); vec6/Ppre/Ppost are 6+36+36 blocks.
            rows.append({
                "idx": int(f[col["idx"]]), "rel_s": float(f[col["rel_s"]]),
                "abs_ns": int(f[col["abs_ns"]]), "grp_idx": int(f[col["grp_idx"]]),
                "scan_first_ns": int(f[col["scan_first_ns"]]),
                "scan_last_ns": int(f[col["scan_last_ns"]]),
                "n_scans": int(f[col["n_scans"]]) if "n_scans" in col else 1,
                "has_out": int(f[col["has_out"]]), "phase": int(f[col["phase"]]),
                "eff": int(float(f[col["eff"]])),
                "vec6": np.array([float(x) for x in f[vec_start:vec_start + 6]]),
                "Ppre": np.array([float(x) for x in f[vec_start + 6:vec_start + 42]]).reshape(6, 6),
                "Ppost": np.array([float(x) for x in f[vec_start + 42:vec_start + 78]]).reshape(6, 6),
                "pose_tail": pose_tail,
                "pre_pose": pose_from_tail(pose_tail, "pre_pose") if pose_tail else None,
            })
    return {"names": names, "rows": rows, "malformed": malformed}


def parse_availability(path: str) -> List[Dict[str, Any]]:
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                out.append(json.loads(line))
    return out


def map_support(sup: Dict[str, Any]) -> str:
    if (sup.get("reference_points") or 0) == 0:
        return "EMPTY"
    if sup.get("pass") is True:
        return "SUPPORTED"
    return "LOW"


def build_join(av: List[Dict[str, Any]], trace: Dict[str, Any],
               tol_ns: int = 512) -> Dict[str, Any]:
    rows = trace["rows"]
    true_span = bool(rows) and all(r["scan_first_ns"] >= 0 for r in rows)
    if true_span:
        mapped = []
        for a in av:
            S = int(a["scan_stamp_ns"])
            m = [r for r in rows
                 if r["scan_first_ns"] - tol_ns <= S <= r["scan_last_ns"] + tol_ns]
            mapped.append({"av": a,
                           "last": max((r["scan_last_ns"] for r in m), default=None),
                           "rows": m})
        return {"mapped": mapped, "mode": "true_span_512",
                "status": "TRUE_SPAN_CONTAINMENT_WITH_512NS_QUANTIZATION"}
    by_last: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_last[r["scan_last_ns"]].append(r)
    lasts = sorted(by_last)
    mapped = []
    for a in av:
        S = int(a["scan_stamp_ns"])
        i = bisect.bisect_left(lasts, S)
        if i >= len(lasts):
            mapped.append({"av": a, "last": None, "rows": []})
            continue
        L = lasts[i]
        mapped.append({"av": a, "last": L, "rows": by_last[L]})
    return {"mapped": mapped, "mode": "mechanical_prev_last",
            "status": "HEURISTIC_UNPROVEN"}


def i_evidence(group_rows: List[Dict[str, Any]],
               exact_by_idx: Optional[Dict[int, np.ndarray]] = None) -> Dict[str, Any]:
    if not group_rows:
        return {"present": False, "reason": "NO_TRACE_ROW"}
    live = [r for r in group_rows if r["phase"] == 0] or group_rows
    r = live[0]
    out = {"present": False, "grp_idx": r["grp_idx"], "phase": r["phase"],
           "has_out": r["has_out"], "trace_idx": r["idx"]}
    if r["has_out"] != 1:
        out["reason"] = "HAS_OUT_0"
        return out
    vec = np.asarray(r["vec6"], dtype=np.float64)
    P = np.asarray(r["Ppre"], dtype=np.float64)
    if not (np.isfinite(vec).all() and np.isfinite(P).all()):
        out["reason"] = "NONFINITE_I_FIELDS"
        return out
    w, V = np.linalg.eigh(0.5 * (P + P.T))
    keep = w > 1e-9 * max(float(w.max()), 1e-12)
    rank = int(keep.sum())
    s = float(np.sum((V[:, keep].T @ vec) ** 2 / w[keep])) if rank else None
    approx = -vec
    e = exact_by_idx.get(r["idx"]) if exact_by_idx else None
    if e is None:
        out.update({"present": True, "reason": "NO_M2DGR_POSE", "rank": rank, "s_i": s,
                    "e_norm": float(np.linalg.norm(approx)),
                    "mode": "small_angle_approx"})
        return out
    wP, VP = np.linalg.eigh(0.5 * (P + P.T))
    keepP = wP > 1e-9 * max(float(wP.max()), 1e-12)
    s_exact = float(np.sum((VP[:, keepP].T @ e) ** 2 / wP[keepP])) if keepP.any() else None
    out.update({"present": True, "reason": None, "rank": rank, "s_i": s_exact,
                "s_i_approx": s,
                "e_norm": float(np.linalg.norm(e)),
                "e_norm_approx": float(np.linalg.norm(approx)),
                "e_trans_exact": float(np.linalg.norm(e[3:])),
                "e_trans_approx": float(np.linalg.norm(approx[3:])),
                "e_trans_diff": float(np.linalg.norm(e[3:] - approx[3:])),
                "mode": "exact_from_vec6_and_m2dgr_post"})
    return out


def _qs(vals: List[float]) -> Dict[str, Any]:
    if not vals:
        return {"n": 0}
    a = np.asarray(vals, dtype=np.float64)
    return {"n": len(vals), "min": float(a.min()), "p10": float(np.percentile(a, 10)),
            "p50": float(np.percentile(a, 50)), "p90": float(np.percentile(a, 90)),
            "max": float(a.max())}


def _phase_i(rows: List[Dict[str, Any]], exact_by_idx: Dict[int, np.ndarray]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for ph in (0, 1):
        vals = [r for r in rows if r["phase"] == ph and r["has_out"] == 1]
        if not vals:
            out[str(ph)] = {"n": 0}
            continue
        e = np.array([np.linalg.norm(exact_by_idx.get(r["idx"], -r["vec6"])) for r in vals])
        ss = []
        for r in vals:
            ev = exact_by_idx.get(r["idx"], -r["vec6"])
            w, V = np.linalg.eigh(0.5 * (r["Ppre"] + r["Ppre"].T))
            keep = w > 1e-9 * max(float(w.max()), 1e-12)
            if keep.any():
                ss.append(float(np.sum((V[:, keep].T @ ev) ** 2 / w[keep])))
        out[str(ph)] = {"n": len(vals), "e_norm_median": float(np.median(e)),
                        "e_norm_max": float(e.max()),
                        "s_median": float(np.median(ss)) if ss else None,
                        "s_max": max(ss) if ss else None}
    return out


def selftest_100col() -> Dict[str, Any]:
    """One normal control: a 100-column v10 row parses, and the 7 pose values are exact."""
    import tempfile
    names = ["idx", "rel_s", "abs_ns", "grp_idx", "scan_first_ns", "scan_last_ns",
             "n_scans", "has_out", "phase", "eff", "r_mean", "r_med", "r_abs_mean",
             "r_chi2", "r_chi2w", "vec6", "Ppre6x6", "Ppost6x6",
             "pose_x", "pose_y", "pose_z", "pose_qx", "pose_qy", "pose_qz", "pose_qw"]
    pose_vals = [1.5, -2.0, 0.25, 0.1, 0.2, 0.3, 0.92736185]
    scalars = [7, 12.5, 1627785261379575296, 42, 1627785261379575000,
               1627785261379575296, 1, 1, 0, 99, 0.1, 0.2, 0.3, 4.0, 5.0]
    vec6 = [0.01, -0.02, 0.03, -0.04, 0.05, -0.06]
    Ppre = (np.eye(6) * 0.01).reshape(-1).tolist()
    Ppost = (np.eye(6) * 0.02).reshape(-1).tolist()
    fields = scalars + vec6 + Ppre + Ppost + pose_vals
    assert len(fields) == 100
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
        fh.write("# ALI-H v1 trace\n# " + " ".join(names) + "\n")
        fh.write(" ".join(str(x) for x in fields) + "\n")
        path = fh.name
    try:
        tr = parse_trace(path)
        ok_rows = len(tr["rows"]) == 1 and not tr["malformed"]
        p = pose_from_tail(tr["rows"][0]["pose_tail"]) if ok_rows else None
        ok_pose = p is not None and np.allclose(p, pose_vals, atol=1e-9)
        return {"status": "PASS" if (ok_rows and ok_pose) else "FAIL",
                "rows": len(tr["rows"]), "malformed": tr["malformed"],
                "pose": None if p is None else p.tolist(), "expected": pose_vals}
    finally:
        os.unlink(path)


def selftest_107col() -> Dict[str, Any]:
    """One normal control: a 107-column v11 row parses both pose7 and pre_pose7."""
    import tempfile
    names = ["idx", "rel_s", "abs_ns", "grp_idx", "scan_first_ns", "scan_last_ns",
             "n_scans", "has_out", "phase", "eff", "r_mean", "r_med", "r_abs_mean",
             "r_chi2", "r_chi2w", "vec6", "Ppre6x6", "Ppost6x6"]
    names += ["pose_" + k for k in ("x", "y", "z", "qx", "qy", "qz", "qw")]
    names += ["pre_pose_" + k for k in ("x", "y", "z", "qx", "qy", "qz", "qw")]
    pose = [1.5, -2.0, 0.25, 0.1, 0.2, 0.3, 0.92736185]
    pre = [-0.5, 0.75, 1.0, 0.0, 0.0, 0.0, 1.0]
    scalars = [7, 12.5, 1627785261379575296, 42, 1627785261379575000,
               1627785261379575296, 1, 1, 0, 99, 0.1, 0.2, 0.3, 4.0, 5.0]
    fields = (scalars + [0.01, -0.02, 0.03, -0.04, 0.05, -0.06]
              + (np.eye(6) * 0.01).reshape(-1).tolist()
              + (np.eye(6) * 0.02).reshape(-1).tolist() + pose + pre)
    assert len(fields) == 107
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
        fh.write("# ALI-H v1 trace\n# " + " ".join(names) + "\n")
        fh.write(" ".join(str(x) for x in fields) + "\n")
        path = fh.name
    try:
        tr = parse_trace(path)
        row = tr["rows"][0] if len(tr["rows"]) == 1 else None
        p = pose_from_tail(row["pose_tail"], "pose") if row else None
        q = pose_from_tail(row["pose_tail"], "pre_pose") if row else None
        ok = (len(tr["rows"]) == 1 and not tr["malformed"]
              and p is not None and np.allclose(p, pose, atol=1e-9)
              and q is not None and np.allclose(q, pre, atol=1e-9))
        return {"status": "PASS" if ok else "FAIL", "rows": len(tr["rows"]),
                "pose": None if p is None else p.tolist(),
                "pre_pose": None if q is None else q.tolist()}
    finally:
        os.unlink(path)


def _compare_i(joined: List[Dict[str, Any]]) -> Dict[str, Any]:
    ex, ap, tr, xe, xa = [], [], [], [], []
    for r in joined:
        i = r.get("i") or {}
        if i.get("mode") == "exact_from_vec6_and_m2dgr_post":
            ex.append(i["e_norm"]); ap.append(i["e_norm_approx"])
            tr.append(i.get("e_trans_diff", 0.0))
            xe.append(i["s_i"]); xa.append(i.get("s_i_approx"))
    if not ex:
        return {"n": 0}
    ex_a, ap_a, tr_a = np.array(ex), np.array(ap), np.array(tr)
    return {"n": len(ex), "e_norm_median_exact": float(np.median(ex_a)),
            "e_norm_median_approx": float(np.median(ap_a)),
            "e_norm_max_exact": float(ex_a.max()), "e_norm_max_approx": float(ap_a.max()),
            "s_median_exact": float(np.median(xe)) if xe else None,
            "s_median_approx": float(np.median([x for x in xa if x is not None])) if xa else None,
            "trans_vector_diff_median": float(np.median(tr_a)),
            "trans_vector_diff_max": float(tr_a.max()),
            "rows_trans_diff_gt_1pct": int(np.sum(tr_a > 0.01 * np.maximum(ap_a, 1e-9)))}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "selftest100":
        print(json.dumps(selftest_100col(), indent=1))
        return 0
    if argv and argv[0] == "selftest107":
        print(json.dumps(selftest_107col(), indent=1))
        return 0
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--tag", default="", help="optional output tag (t2_<tag>_summary.json)")
    args = ap.parse_args(argv)
    base = os.path.abspath(args.run)
    trace_path = os.path.join(base, "host_logs", "trace_cov.txt")
    av_path = os.path.join(base, "availability_frames.jsonl")
    receipt_path = os.path.join(base, "receipt.json")
    summary_path = os.path.join(base, "run_summary.json")

    trace = parse_trace(trace_path)
    av = parse_availability(av_path)
    receipt = json.load(open(receipt_path, encoding="utf-8"))
    summary = json.load(open(summary_path, encoding="utf-8"))
    # M2DGR is the published post-update pose, in the same order as the has_out trace rows
    # (975 rows vs 974 parsed has_out + 1 truncated). Verify the time offset, then align by order.
    m2_path = os.path.join(base, "host_logs", "M2DGR_room_02.txt")
    m2 = (np.array([[float(x) for x in l.split()] for l in open(m2_path) if l.split()])
          if os.path.exists(m2_path) else np.zeros((0, 8)))
    ho_rows = [r for r in trace["rows"] if r["has_out"] == 1]
    # Join by time, not global row order. Replay repeats timestamps in both files, so within
    # one time group the k-th trace row (phase 0 then 1, trace order) takes the k-th pose row.
    pose_rows = [(int(round(float(x[0]) * 1e9)), x) for x in m2]
    pose_rows.sort(key=lambda t: t[0])
    pose_ns = [t[0] for t in pose_rows]
    groups: Dict[int, List[int]] = defaultdict(list)
    for i, (ns, _) in enumerate(pose_rows):
        groups[ns].append(i)
    exact_by_idx = {}
    same_row_pose = 0
    same_row_pre_post = 0
    for r in ho_rows:
        pre = r.get("pre_pose")
        post = pose_from_tail(r.get("pose_tail"), "pose")
        if post is not None:
            same_row_pose += 1
        if pre is not None and post is not None:
            exact_by_idx[r["idx"]] = e_i_from_poses(pre, post)
            same_row_pre_post += 1
    for r in ho_rows:
        if r["idx"] in exact_by_idx:
            continue
        p = pose_from_tail(r.get("pose_tail"), "pose")
        if p is not None:
            exact_by_idx[r["idx"]] = exact_e(r["vec6"], quat_to_rot(p[3:7]))
    time_err = []
    used: Dict[int, int] = defaultdict(int)
    ambiguous_groups = 0
    for r in ho_rows:
        if r["idx"] in exact_by_idx or len(m2) == 0:
            continue
        ns = r["abs_ns"]
        i = bisect.bisect_left(pose_ns, ns)
        cands = []
        for j in (i - 1, i, i + 1):
            if 0 <= j < len(pose_rows) and abs(pose_ns[j] - ns) <= 2000:
                cands.append(j)
        if not cands:
            continue
        # group candidates by identical pose time; within a group, consume in pose-file order
        # as trace rows of the same time appear (phase 0 first, replay later)
        key = min(pose_ns[j] for j in cands)
        group_idx = sorted(groups.get(key, cands))
        k = used[key]
        if len(group_idx) > 1:
            ambiguous_groups += 1 if k == 0 else 0
        j = group_idx[min(k, len(group_idx) - 1)]
        used[key] = k + 1
        exact_by_idx[r["idx"]] = exact_e(r["vec6"], quat_to_rot(pose_rows[j][1][4:8]))
        time_err.append(pose_ns[j] - ns)
    time_err = np.array(time_err, dtype=np.int64)
    join = build_join(av, trace)

    mapped = join["mapped"]
    unmapped = [m for m in mapped if m["last"] is None]
    map_counts = Counter(len(m["rows"]) for m in mapped)
    phase_sets = Counter(tuple(sorted({r["phase"] for r in m["rows"]})) for m in mapped if m["rows"])
    has_sets = Counter(tuple(sorted({r["has_out"] for r in m["rows"]})) for m in mapped if m["rows"])
    av_per_group = Counter(min(r["grp_idx"] for r in m["rows"]) for m in mapped if m["rows"])
    phase_coverage = Counter("both" if {r["phase"] for r in m["rows"]} == {0, 1} else "live_only"
                             for m in mapped if m["rows"])
    exact = sum(1 for m in mapped
                if any(int(r["scan_first_ns"]) == int(m["av"]["scan_stamp_ns"]) == int(r["scan_last_ns"])
                       for r in m["rows"]))

    first_pose_ns = min(int(a["pose_stamp_ns"]) for a in av)
    joined_rows = []
    state_counts = Counter()
    block_map: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    i_stats = Counter()
    i_norms, i_s = [], []
    tail_rows = 0
    for m in mapped:
        a = m["av"]
        sup = a.get("support") or {}
        nis = a.get("nis") or {}
        ie = i_evidence(m["rows"], exact_by_idx)
        rel_av_s = (int(a["pose_stamp_ns"]) - first_pose_ns) / 1e9
        tail = bool(rel_av_s >= E2_REL_S)
        if tail:
            tail_rows += 1
        m_status = map_support(sup)
        status = "UNKNOWN"
        reasons = ["CALIBRATION_BLOCKED:no_normal_reference"]
        if not ie["present"]:
            reasons.append("I_" + str(ie.get("reason")))
        if tail:
            reasons.append("POST_E2_NO_CATCHUP")
        state = "UNKNOWN"
        state_counts[(state, tail)] += 1
        joined_rows.append({
            "kf_id": a.get("kf_id"), "scan_stamp_ns": a.get("scan_stamp_ns"),
            "pose_stamp_ns": a.get("pose_stamp_ns"), "old_status": a.get("status"),
            "map_support": m_status, "supported_fraction": sup.get("supported_fraction"),
            "support_reason": sup.get("reason"), "support_pass": a.get("support_pass"),
            "nis_source": nis.get("source"), "nis_reference": nis.get("selected_reference_source"),
            "nis_effective": nis.get("effective_nis"),
            "M_present": (nis.get("selected_reference_source") == "node_map"
                          and nis.get("computed") is True and isinstance(nis.get("effective_nis"), (int, float))),
            "T_present": (nis.get("selected_reference_source") == "prev_scan"
                          and nis.get("computed") is True and isinstance(nis.get("effective_nis"), (int, float))),
            "join_last_ns": m["last"],
            "grp_idx": sorted({r["grp_idx"] for r in m["rows"]}) if m["rows"] else None,
            "grp_rows": [r["idx"] for r in m["rows"]],
            "phases": sorted({r["phase"] for r in m["rows"]}) if m["rows"] else None,
            "has_out": sorted({r["has_out"] for r in m["rows"]}) if m["rows"] else None,
            "i": ie, "tail": tail, "shadow_state": state, "reason_codes": reasons,
        })
        if ie["present"]:
            i_stats["present"] += 1
            i_norms.append(ie["e_norm"]); i_s.append(ie["s_i"])
            i_stats[f"phase_{ie['phase']}"] += 1
        else:
            i_stats[f"missing_{ie.get('reason')}"] += 1
        if m["rows"]:
            ts = int(a["pose_stamp_ns"])
            block_map[ts // BLOCK_NS].append({"phase": ie["phase"], "tail": tail,
                                              "map_support": m_status})
        else:
            block_map[int(a["pose_stamp_ns"]) // BLOCK_NS].append(
                {"phase": None, "tail": False, "map_support": m_status})

    # fill missing blocks inside the availability time range; all UNKNOWN
    block_ids = sorted(block_map)
    block_rows = []
    for bid in range(block_ids[0], block_ids[-1] + 1):
        fs = block_map.get(bid, [])
        phases = {f["phase"] for f in fs if f["phase"] is not None}
        phase = next(iter(phases)) if len(phases) == 1 else ("MIXED" if phases else "NO_DATA")
        tails = any(f["tail"] for f in fs)
        block_rows.append({"block_id": bid, "n_frames": len(fs), "phase": phase,
                           "tail": tails, "state": "UNKNOWN",
                           "reason_codes": ["CALIBRATION_BLOCKED:no_normal_reference"]
                           + (["POST_E2_NO_CATCHUP"] if tails else [])})
    # An empty block inside the post-E2 span inherits the tail flag; otherwise a zero-row gap
    # would look like a normal UNKNOWN interval inside the tail.
    tail_ids = [b["block_id"] for b in block_rows if b["tail"]]
    if tail_ids:
        lo, hi = tail_ids[0], tail_ids[-1]
        for b in block_rows:
            if b["n_frames"] == 0 and lo <= b["block_id"] <= hi:
                b["tail"] = True
    unknown_blocks = sum(1 for b in block_rows if b["state"] == "UNKNOWN")
    def _runs(bs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not bs:
            return []
        out, start, prev = [], bs[0]["block_id"], bs[0]["block_id"]
        for b in bs[1:]:
            if b["block_id"] == prev + 1:
                prev = b["block_id"]
            else:
                out.append((start, prev)); start = prev = b["block_id"]
        out.append((start, prev))
        first = block_rows[0]["block_id"]
        return [{"block_first": a, "block_last": b, "blocks": b - a + 1,
                 "duration_s": (b - a + 1) * (BLOCK_NS / 1e9),
                 "rel_start_s": (a - first) * (BLOCK_NS / 1e9),
                 "rel_end_s": (b - first + 1) * (BLOCK_NS / 1e9),
                 "start_ns": a * BLOCK_NS, "end_ns": (b + 1) * BLOCK_NS}
                for a, b in out]
    normal_blocks = [b for b in block_rows if not b["tail"]]
    tail_blocks = [b for b in block_rows if b["tail"]]
    normal_runs = _runs(normal_blocks)
    tail_runs = _runs(tail_blocks)

    joined_counter = Counter()
    for r in joined_rows:
        joined_counter[(r["old_status"], r["M_present"], r["T_present"])] += 1
    status_count = Counter(a.get("status") for a in av)
    support_reason = Counter((a.get("support") or {}).get("reason") for a in av)
    support_class = Counter(map_support(a.get("support") or {}) for a in av)

    repair = {}
    ack_path = os.path.join(base, "host_control", "ack")
    if os.path.exists(ack_path):
        txt = open(ack_path, encoding="utf-8", errors="replace").read()
        for key in ("repair_received", "repair_applied", "repair_dropped", "repair_queued"):
            m = None
            for tok in txt.split():
                if tok.startswith(key + "="):
                    m = tok.split("=", 1)[1]
            if m is not None:
                repair[key] = int(m)

    if same_row_pre_post > 0:
        i_qual = "PASS_SAME_ROW_UNIT_WEIGHTED"
        i_reasons = [
            f"{same_row_pre_post} rows have same-row pre_pose7+pose7; e_I is a true SE(3) Log "
            "(V^-1 included)",
            "vec6 remains NOT_VERIFIED and is used only as a comparison",
            "Ppre/Ppost are mixed-convention state blocks; covariance is NOT_AVAILABLE",
            "I primary quantity is the unit-weighted |e_I|^2; no chi-square probability"]
    elif same_row_pose > 0:
        i_qual = "INCOMPLETE/UNKNOWN"
        i_reasons = [
            f"{same_row_pose} rows have same-row post pose only; pre pose is not same-row",
            "vec6 is captured before the final solution; covariance is NOT_AVAILABLE"]
    else:
        i_qual = "INCOMPLETE/UNKNOWN"
        i_reasons = [
            "vec6 is captured before the final solution (state_ += solution); the final "
            "solution is not exported, so vec6 is not the final pre-post increment",
            "pre pose is not independently exported for the LIO handler; mat_pre has "
            "VIO/LIO double writes without a handler tag",
            "Ppre/Ppost are mixed-convention state blocks; no verified 6D tangent covariance",
            "numeric I rows are not qualified independent I observations"]

    out = {
        "_meta": {
            "run": os.path.basename(base), "run_id": summary.get("run_id"),
            "branch_head_at_run": "see git log",
            "trace_sha256": sha256(trace_path), "availability_sha256": sha256(av_path),
            "receipt_sha256": sha256(receipt_path), "summary_sha256": sha256(summary_path),
            "protocol": "T2_PROTOCOL.md (pre-registered)", "block_ns": BLOCK_NS,
            "e2_rel_s": E2_REL_S,
            "pose_source_status": ("SAME_ROW_PRE_POST" if same_row_pre_post
                                   else ("SAME_ROW_POST" if same_row_pose
                                         else "LEGACY_M2DGR_TIME_JOIN")),
            "join_status": join["status"],
            "results_conditional_on": ("true span containment with 512 ns quantization; "
                                        "multi-to-one kept"
                                        if join["mode"] == "true_span_512" else
                                        "unproven group-membership mapping"),
            "e_i_convention": ("host mixed convention: rot = R*Exp(d_rot) (body right), "
                               "pos = p + d_pos (world additive); rot=-w, t_body=-R_pre^T v, "
                               "then SE(3) Log t_log = so3_left_jacobian_inv(rot) @ t_body"),
            "pose_source": ("same-row pre_pose+pose (v11, 107 cols) when both exist; "
                            "same-row pose only (v10, 100 cols); M2DGR time join only for "
                            "legacy 92/93-column rows as a cross-check"),
            "same_row_pre_post_rows": same_row_pre_post,
            "same_row_post_pose_rows": same_row_pose,
            "pose_source_scope": ("SAME_ROW_PRE_POST applies to v11 165438Z; SAME_ROW_POST to "
                                  "v10 100-col rows; LEGACY_M2DGR_TIME_JOIN to v7/v8, where v7 "
                                  "join remains HEURISTIC_UNPROVEN"),
            "i_qualification": i_qual,
            "i_qualification_reasons": i_reasons,
            "covariance_status": ("NOT_AVAILABLE_FOR_E_I: Ppre/Ppost are mixed-convention state "
                                  "blocks; no verified 6x6 tangent conversion"),
            "vec6_status": ("NOT_VERIFIED: saved before the final solution; same pre/post and "
                            "carryover membership are unproven; do not infer physical meaning "
                            "from vec6 alone"),
            "e_i_formula": "e_I = [rot, V(rot)^-1 * t_body], rot=-w, t_body=-R_pre^T v",
            "i_sign_note": "exact e_I uses vec6 and the M2DGR post pose under the host "
                           "StatesGroup::operator- convention; if M2DGR is not the post pose of "
                           "the same frame, the exact values are invalid. -vec6 is kept as the "
                           "small-angle comparison column.",
            "not_done": ["no normal reference", "no independent labels", "no host run"],
        },
        "run": {
            "run_mode": summary.get("run_mode"), "detection_enabled": summary.get("detection_enabled"),
            "final_state": summary.get("final_state"), "paired": (summary.get("frames") or {}).get("paired"),
            "injection": (receipt.get("launch") or {}).get("injection"),
            "candidate_source": (receipt.get("launch") or {}).get("candidate_source"),
            "recovery_node_source": (receipt.get("inputs") or {}).get("recovery_node_source"),
            "runtime_library": (receipt.get("inputs") or {}).get("runtime_library_sha256"),
            "status_counts": dict(status_count), "support_non_null": sum(1 for a in av if a.get("support")),
            "repair_ack": repair,
            "support_reasons": dict(support_reason), "support_classes": dict(support_class),
        },
        "trace": {
            "rows_total_lines": len(trace["rows"]) + len(trace["malformed"]),
            "rows_valid": len(trace["rows"]), "malformed": trace["malformed"],
            "TRUNCATED_ROW": len(trace["malformed"]),
            "phase1_rows": sum(1 for r in trace["rows"] if r["phase"] == 1),
            "has_out_rows": sum(r["has_out"] for r in trace["rows"]),
            "groups": len({r["grp_idx"] for r in trace["rows"]}),
            "duplicate_groups": sum(1 for g, n in Counter(r["grp_idx"] for r in trace["rows"]).items() if n > 1),
            "scan_first_sentinel_all": all(r["scan_first_ns"] == -1 for r in trace["rows"]),
            "m2dgr_rows": len(m2), "m2dgr_time_err_ns_max": int(np.abs(time_err).max()) if len(time_err) else None,
            "pose_join_mode": ("same_row_pre_post" if same_row_pre_post
                               else ("same_row_post" if same_row_pose
                                     else "time_with_duplicate_order")),
            "duplicate_time_groups": ambiguous_groups,
        },
        "join": {
            "status": join["status"],
            "mode": join["mode"],
            "availability_rows": len(av), "mapped": len(mapped) - len(unmapped),
            "unmapped": len(unmapped), "exact_equality": exact,
            "trace_rows_per_group": dict(map_counts),
            "availability_per_group": dict(Counter(av_per_group.values())),
            "multi_grp_idx_rows": sum(1 for r in joined_rows if r["grp_idx"] and len(r["grp_idx"]) > 1),
            "shared_last_groups": sum(1 for g in {tuple(sorted({r["grp_idx"] for r in trace["rows"]
                                                                if r["scan_last_ns"] == L}))
                                                  for L in {r["scan_last_ns"] for r in trace["rows"]}}
                                      if len(g) > 1),
            "grp_per_last_distribution": dict(Counter(
                len({r["grp_idx"] for r in trace["rows"] if r["scan_last_ns"] == L})
                for L in {r["scan_last_ns"] for r in trace["rows"]})),
            "avail_rows_per_last_distribution": dict(Counter(
                Counter(m["last"] for m in mapped if m["last"] is not None).values())),
            "multi_grp_idx_row_examples": [r["kf_id"] for r in joined_rows
                                            if r["grp_idx"] and len(r["grp_idx"]) > 1][:5],
            "groups_used_by_availability": len(av_per_group),
            "phase_coverage_availability": dict(phase_coverage),
            "phase_sets": {str(k): v for k, v in phase_sets.items()},
            "has_out_sets": {str(k): v for k, v in has_sets.items()},
            "rule": ("true span containment: first-512 <= scan_stamp_ns <= last+512"
                     if join["mode"] == "true_span_512" else
                     "mechanical: previous distinct scan_last < scan_stamp_ns <= scan_last"),
        },
        "channels": {
            "M_present_all": sum(1 for r in joined_rows if r["M_present"]),
            "T_present_all": sum(1 for r in joined_rows if r["T_present"]),
            "I_present": i_stats["present"], "I_missing": {k: v for k, v in i_stats.items()
                                                          if k.startswith("missing_")},
            "I_phase": {k: v for k, v in i_stats.items() if k.startswith("phase_")},
            "I_rank6": sum(1 for r in joined_rows if r["i"].get("rank") == 6),
            "I_e_norm": {"min": min(i_norms) if i_norms else None,
                         "median": float(np.median(i_norms)) if i_norms else None,
                         "max": max(i_norms) if i_norms else None},
            "I_s": {"min": min(i_s) if i_s else None,
                    "median": float(np.median(i_s)) if i_s else None,
                    "max": max(i_s) if i_s else None},
            "I_by_phase": _phase_i(trace["rows"], exact_by_idx),
            "I_compare": _compare_i(joined_rows),
            "I_unit_energy": _qs([float(r["i"]["e_norm"] ** 2) for r in joined_rows
                                  if r["i"].get("mode") == "exact_from_vec6_and_m2dgr_post"]),
            "I_s_status": "DIAGNOSTIC_ONLY_MIXED_CONVENTION_NOT_A_CHI2",
            "I_quantiles": {
                "e_norm_exact": _qs([r["i"]["e_norm"] for r in joined_rows
                                     if r["i"].get("mode") == "exact_from_vec6_and_m2dgr_post"]),
                "e_norm_approx": _qs([r["i"]["e_norm_approx"] for r in joined_rows
                                      if r["i"].get("mode") == "exact_from_vec6_and_m2dgr_post"]),
                "s_exact": _qs([r["i"]["s_i"] for r in joined_rows
                                if r["i"].get("mode") == "exact_from_vec6_and_m2dgr_post"]),
                "s_approx": _qs([r["i"]["s_i_approx"] for r in joined_rows
                                 if r["i"].get("mode") == "exact_from_vec6_and_m2dgr_post"
                                 and r["i"].get("s_i_approx") is not None]),
                "e_trans_exact": _qs([r["i"]["e_trans_exact"] for r in joined_rows
                                      if r["i"].get("mode") == "exact_from_vec6_and_m2dgr_post"]),
                "e_trans_approx": _qs([r["i"]["e_trans_approx"] for r in joined_rows
                                       if r["i"].get("mode") == "exact_from_vec6_and_m2dgr_post"]),
            },
            "M_T_denominators": {
                "all": len(joined_rows),
                "M_present": sum(1 for r in joined_rows if r["M_present"]),
                "T_present": sum(1 for r in joined_rows if r["T_present"]),
                "both": sum(1 for r in joined_rows if r["M_present"] and r["T_present"]),
                "neither": sum(1 for r in joined_rows if not r["M_present"] and not r["T_present"]),
                "M_pct": 100.0 * sum(1 for r in joined_rows if r["M_present"]) / max(len(joined_rows), 1),
                "T_pct": 100.0 * sum(1 for r in joined_rows if r["T_present"]) / max(len(joined_rows), 1),
            },
            "old_status_by_M_T": {str(k): v for k, v in joined_counter.items()},
        },
        "states": {
            "by_status_and_tail": {str(k): v for k, v in state_counts.items()},
            "blocks": len(block_rows), "unknown_blocks": unknown_blocks,
            "tail_rows": tail_rows, "tail_blocks": len(tail_blocks),
            "tail_rows_by_pose_rel_54": sum(
                1 for r in joined_rows if (int(r["pose_stamp_ns"]) - first_pose_ns) / 1e9 >= E2_REL_S),
            "tail_rows_by_block": sum(
                1 for r in joined_rows
                if (int(r["pose_stamp_ns"]) // BLOCK_NS) in {b["block_id"] for b in block_rows if b["tail"]}),
            "span_s": (block_ids[-1] - block_ids[0] + 1) * (BLOCK_NS / 1e9),
            "unknown_normal": {
                "blocks": len(normal_blocks),
                "duration_s": len(normal_blocks) * (BLOCK_NS / 1e9),
                "longest_run": max((r["duration_s"] for r in normal_runs), default=0.0),
                "runs": normal_runs},
            "unknown_post_e2": {
                "blocks": len(tail_blocks),
                "duration_s": len(tail_blocks) * (BLOCK_NS / 1e9),
                "longest_run": max((r["duration_s"] for r in tail_runs), default=0.0),
                "runs": tail_runs},
            "not_evaluable": ["NORMAL_CONSISTENT", "SUSPECT", "false positive", "missed detection",
                              "detection delay", "wrong NORMAL"],
        },
        "blocks": block_rows,
    }
    os.makedirs(HERE, exist_ok=True)
    prefix = f"t2_{args.tag}_" if args.tag else "t2_"
    with open(os.path.join(HERE, prefix + "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, ensure_ascii=False)
    with open(os.path.join(HERE, prefix + "join.jsonl"), "w", encoding="utf-8") as fh:
        for r in joined_rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(json.dumps({k: out[k] for k in ("run", "trace", "join", "channels", "states")},
                     indent=1, ensure_ascii=False)[:8000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
