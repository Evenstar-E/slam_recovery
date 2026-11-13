#!/usr/bin/env python3
"""Measure the driver's per-frame cost before a long run, on synthetic data.

Why this exists: on FAST-LIO the driver's per-frame work was about one core (244 ms per pose
callback) and the host's own covariance-triggered hibernation moved from 115.8 s to 66 s. The
host's degeneracy decision depends on IMU/LiDAR timing, so driver load is not a neutral observer.
The rule is to quantify this *before* a chain run: if the measured per-pair cost at the planned
frame rate is more than a quarter of a core, reduce it first.

    python3 -I slam_recovery/tools/bench_frame_cost.py --rate 10

The number is diagnostic: it is recorded with each run, it does not block one. Add
--max-core-fraction only when a hard ceiling is explicitly wanted.
"""

from __future__ import annotations

import argparse
import sys
import time

import numpy as np

sys.path.insert(0, "/home/R26534/MM-LINS")

from slam_recovery.ros.cloud_repair import ReferenceGrid  # noqa: E402
from slam_recovery.validation.fim_and_holdout import (  # noqa: E402
    compute_6dof_point_to_plane_fim,
    compute_disjoint_holdout_point_to_plane_nis,
)


def measure(points: int, reference: int) -> dict:
    rng = np.random.default_rng(0)
    scan = rng.uniform(-15, 15, (points, 3))
    ref = rng.uniform(-15, 15, (reference, 3))
    # Warm up: the first call carries allocation and BLAS warm-up costs that a long run does
    # not pay per frame.
    compute_6dof_point_to_plane_fim(scan, sigma_meas_m=0.075)
    compute_disjoint_holdout_point_to_plane_nis(ref, scan, sigma_meas_m=0.12)
    t = time.perf_counter()
    compute_6dof_point_to_plane_fim(scan, sigma_meas_m=0.075)
    fim_ms = (time.perf_counter() - t) * 1000.0
    t = time.perf_counter()
    compute_disjoint_holdout_point_to_plane_nis(ref, scan, sigma_meas_m=0.12)
    nis_ms = (time.perf_counter() - t) * 1000.0
    t = time.perf_counter()
    grid = ReferenceGrid(ref)
    grid_build_ms = (time.perf_counter() - t) * 1000.0
    t = time.perf_counter()
    grid.nearest_distances(scan[:1500])
    grid_ms = (time.perf_counter() - t) * 1000.0
    return {"fim_ms": fim_ms, "nis_ms": nis_ms,
            "grid_build_ms_reference": grid_build_ms, "grid_query1500_ms": grid_ms,
            "total_ms": fim_ms + nis_ms}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--points", type=int, default=6000, help="points per scan (scan_cap)")
    ap.add_argument("--reference-points", type=int, default=200000,
                    help="trusted-map reference points at the end of the run")
    ap.add_argument("--rate", type=float, default=10.0, help="paired frames per second")
    ap.add_argument("--max-core-fraction", type=float, default=0.0,
                    help="optional: exit non-zero when total_ms * rate exceeds this fraction of "
                         "one core (0 = report only; the measurement is diagnostic, not a gate)")
    args = ap.parse_args(argv)
    m = measure(args.points, args.reference_points)
    core = (m["total_ms"] / 1000.0) * args.rate
    gated = args.max_core_fraction > 0
    m.update({"rate_hz": args.rate, "core_fraction": round(core, 3),
              "max_core_fraction": args.max_core_fraction if gated else None,
              "status": ("PASS" if core <= args.max_core_fraction else "FAIL") if gated
                        else "REPORT_ONLY"})
    for k, v in m.items():
        print(f"{k}: {v if not isinstance(v, float) else round(v, 3)}")
    return (0 if core <= args.max_core_fraction else 1) if gated else 0


if __name__ == "__main__":
    raise SystemExit(main())
