"""Score the availability support test against a map that this run did not build.

The support test compares a scan to the trusted map sampled at the frame's own pose. When it
fails, two explanations remain: the map does not cover that scan, or the pose that places the
scan is wrong. A map from a separate clean run is independent of this run's map and pose
history (it is still the same sensor and host, which is a stated limit), so testing the same
saved samples against it separates those two cases.

This module is read-only over archived availability rows: it reads the body-frame samples and
the T_wb each row recorded, transforms them, and counts how many land within the radius of the
independent cloud. Frames whose samples were trimmed (AVAILABLE rows keep 20) are marked.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import numpy as np


def read_pcd_xyz(path: str) -> np.ndarray:
    """Read x,y,z from an ASCII or binary PCD (the host writes binary PCDs)."""
    with open(path, "rb") as fh:
        header_lines = []
        while True:
            line = fh.readline()
            if not line:
                raise ValueError(f"PCD header not terminated in {path}")
            text = line.decode("ascii", errors="replace").strip()
            header_lines.append(text)
            if text.upper().startswith("DATA"):
                break
        fields, sizes, types, counts = [], [], [], []
        data_kind = "ascii"
        points = 0
        for text in header_lines:
            key, _, value = text.partition(" ")
            key = key.upper()
            if key == "FIELDS":
                fields = value.split()
            elif key == "SIZE":
                sizes = [int(v) for v in value.split()]
            elif key == "TYPE":
                types = value.split()
            elif key == "COUNT":
                counts = [int(v) for v in value.split()]
            elif key == "POINTS":
                points = int(value)
            elif key == "DATA":
                data_kind = value.strip().lower()
        if not counts:
            counts = [1] * len(fields)
        # offsets of the x,y,z float32 fields
        fmt = {"F": 4, "I": 4, "U": 4}
        offsets, off = {}, 0
        for name, size, typ, cnt in zip(fields, sizes, types, counts):
            offsets[name] = (off, typ, size)
            off += size * cnt
        point_step = off
        if data_kind == "ascii":
            arr = np.loadtxt(fh, dtype=np.float64, ndmin=2)
            ix = fields.index("x"); iy = fields.index("y"); iz = fields.index("z")
            return np.ascontiguousarray(arr[:, [ix, iy, iz]])
        raw = np.frombuffer(fh.read(points * point_step), dtype=np.uint8).reshape(-1, point_step)
        cols = []
        for name in ("x", "y", "z"):
            base, typ, size = offsets[name]
            if typ != "F" or size != 4:
                raise ValueError(f"PCD field {name} is {typ}{size}, expected F4")
            cols.append(raw[:, base:base + 4].copy().view(np.float32).reshape(-1))
        return np.stack(cols, axis=1).astype(np.float64)


def load_rows(path: str) -> List[Dict[str, Any]]:
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt") as fh:
        return [json.loads(line) for line in fh]


def estimate_se3(src_xyz: np.ndarray, dst_xyz: np.ndarray) -> Dict[str, Any]:
    """Single rigid transform between two runs' positions over a matched prefix.

    The two runs share a bag but not a world gauge: each starts from its own first IMU sample and
    drifts its own way. Comparing points across runs needs one declared transform, estimated on a
    healthy prefix where both runs are trusted, not a per-frame fit.
    """
    src = np.asarray(src_xyz, dtype=np.float64)[:, :3]
    dst = np.asarray(dst_xyz, dtype=np.float64)[:, :3]
    if len(src) != len(dst) or len(src) < 3:
        raise ValueError("need at least three matched positions")
    cs, cd = src.mean(0), dst.mean(0)
    H = (src - cs).T @ (dst - cd)
    U, _S, Vt = np.linalg.svd(H)
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    R = Vt.T @ np.diag([1.0, 1.0, d]) @ U.T
    t = cd - R @ cs
    T = np.eye(4)
    T[:3, :3] = R
    T[:3, 3] = t
    resid = np.linalg.norm((src @ R.T + t) - dst, axis=1)
    return {"T": T, "n": int(len(src)), "rms_residual_m": float(np.sqrt(np.mean(resid ** 2))),
            "max_residual_m": float(np.max(resid))}


def voxel_downsample(points: np.ndarray, voxel_m: float = 1.0) -> np.ndarray:
    pts = np.asarray(points, dtype=np.float64)[:, :3]
    if len(pts) == 0:
        return pts
    q = np.floor(pts / float(voxel_m)).astype(np.int64)
    _, first = np.unique(q, axis=0, return_index=True)
    return pts[np.sort(first)]


def icp_align(body: np.ndarray, reference: np.ndarray, seed: np.ndarray,
              max_iter: int = 12, gate_m: float = 2.0) -> Dict[str, Any]:
    """Rigid ICP of the saved body samples onto the independent map, seeded by the host pose.

    The seed is the host pose itself, so a large correction says the host pose is what the map
    disagrees with; the fraction after alignment says whether the scan geometry is covered at all.
    """
    from scipy.spatial import cKDTree

    tree = cKDTree(reference)
    T = np.asarray(seed, dtype=np.float64).copy()
    body_h = np.hstack([body, np.ones((len(body), 1))])
    corrections = []
    for _ in range(max_iter):
        world = (T @ body_h.T).T[:, :3]
        dist, idx = tree.query(world)
        good = dist <= gate_m
        if np.count_nonzero(good) < 10:
            break
        src = world[good]
        dst = reference[idx[good]]
        cs, cd = src.mean(0), dst.mean(0)
        H = (src - cs).T @ (dst - cd)
        U, _S, Vt = np.linalg.svd(H)
        d = np.sign(np.linalg.det(Vt.T @ U.T))
        R = Vt.T @ np.diag([1.0, 1.0, d]) @ U.T
        t = cd - R @ cs
        dT = np.eye(4)
        dT[:3, :3] = R
        dT[:3, 3] = t
        T = dT @ T
        corrections.append(float(np.linalg.norm(t)))
        if corrections[-1] < 1e-3:
            break
    world = (T @ body_h.T).T[:, :3]
    dist, _ = tree.query(world)
    return {"T": T, "correction_m": float(np.linalg.norm(T[:3, 3] - np.asarray(seed)[:3, 3])),
            "last_step_m": corrections[-1] if corrections else None,
            "iterations": len(corrections),
            "fraction_within_1m": float(np.mean(dist <= 1.0))}


def score_rows(rows: Iterable[Dict[str, Any]], reference_xyz: np.ndarray,
               radius_m: float = 1.0, align: bool = False,
               reference_transform: Optional[np.ndarray] = None) -> List[Dict[str, Any]]:
    """Fraction of each frame's saved samples inside ``radius_m`` of the reference."""
    from slam_recovery.sim.transaction_manager_node import _RadiusIndex

    ref = np.asarray(reference_xyz, dtype=np.float64)[:, :3]
    index = _RadiusIndex(ref, radius_m) if len(ref) else None
    gauge = np.eye(4) if reference_transform is None else np.asarray(reference_transform, dtype=np.float64)
    out = []
    for row in rows:
        support = row.get("support") or {}
        samples = support.get("points") or []
        if not samples or index is None:
            out.append({"kf_id": row.get("kf_id"), "independent_fraction": None,
                        "independent_pass": None, "samples": 0,
                        "reason": "no_samples_or_reference"})
            continue
        body = np.asarray([p["body"] for p in samples], dtype=np.float64)
        T = gauge @ np.asarray(row["T_wb"], dtype=np.float64).reshape(4, 4)
        world = (body @ T[:3, :3].T) + T[:3, 3]
        inside = index.within_radius_mask(world, radius_m)
        fraction = float(np.mean(inside))
        aligned = None
        if align:
            try:
                aligned = icp_align(body, ref, T)
            except Exception as exc:            # recorded, not hidden
                aligned = {"error": f"{type(exc).__name__}: {exc}"}
        out.append({
            "kf_id": row.get("kf_id"),
            "independent_fraction": fraction,
            "independent_pass": bool(fraction >= 0.60),
            "samples": int(len(samples)),
            "samples_trimmed": bool(support.get("points_total", len(samples)) > len(samples)),
            "host_fraction": support.get("supported_fraction"),
            "host_pass": support.get("pass"),
            "status": row.get("status"),
            "partial_sample": bool(support.get("points_total", len(samples)) > len(samples)),
            "aligned": aligned,
        })
    return out


def summarise(scored: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Joint counts on complete samples only; partially saved frames are listed separately.

    A trimmed frame's fraction is over the saved subset, not over the 200-point denominator the
    decision used, so it cannot enter the main table.
    """
    scored = [s for s in scored if s.get("independent_pass") is not None]
    full = [s for s in scored if not s.get("partial_sample")]
    partial = [s for s in scored if s.get("partial_sample")]
    both_low = [s for s in full if s["host_pass"] is False and s["independent_pass"] is False]
    host_low_new_pass = [s for s in full if s["host_pass"] is False and s["independent_pass"] is True]
    host_pass_new_low = [s for s in full if s["host_pass"] is True and s["independent_pass"] is False]
    both_pass = [s for s in full if s["host_pass"] and s["independent_pass"]]
    return {
        "frames_full_sample": len(full),
        "partial_sample_not_evaluable": len(partial),
        "both_low": len(both_low),
        "host_low_new_reference_pass": len(host_low_new_pass),
        "host_pass_new_reference_low": len(host_pass_new_low),
        "both_pass": len(both_pass),
        "reading": ("labels name the reference, not the cause: host_low_new_reference_pass means the "
                    "same body points and the same T_wb fall inside the new map but not the run's own "
                    "reference; the cause stays UNKNOWN. both_low means neither reference covers them. "
                    "Per-frame ICP results are fitted compatibility, not an unfitted verdict."),
    }
