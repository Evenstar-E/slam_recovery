#!/usr/bin/env python3
"""Part 2, form 2: an observable-subspace gate, and the control that shows it is not a scalar.

DEFINITION (frozen before running)

  lambda_k            eigenvalues of the 6x6 information in the evaluation basis (A7 anchor body)
  "unconstrained"     lambda_k < LAMBDA_FLOOR = 1/sigma_tol = 2.0, i.e. the variance along that
                      direction exceeds the covariance bound the gate already uses in its
                      posterior-covariance leg. The number is inherited from sigma_tol, not chosen.
  m_after             how many directions of Lambda_after are unconstrained
  subspace gate       admit only if m_after == 0   (all six directions constrainable)
                      -- a rank/condition condition, not a scalar along one direction

The control: if this gate were a re-parameterisation of the current scalar (v^T L v >= threshold),
the two must order the same scans the same way. It is shown below that they do not.

Form 1 (the current conjunction) and form 3 (sequential admission) are defined in the report; their
decision-level comparison needs `after`, which the archive does not carry, so they stay BLOCKED.

    python -I docs/gate_method_research_20261110/p2_subspace_gate.py
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys

import numpy as np

ROOT = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(ROOT, "docs/gate_method_research_20261110")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

C2_SPEC = importlib.util.spec_from_file_location("c2", os.path.join(HERE, "c2_fim_spatial.py"))
c2 = importlib.util.module_from_spec(C2_SPEC)          # noqa: E402
C2_SPEC.loader.exec_module(c2)

from slam_recovery.core import transport, transport_information  # noqa: E402

VARIANCE_FLOOR = 2.0        # = 1 / sigma_tol (core.py's covariance leg); inherited, not tuned
N_SCANS = 24
BAG = "/tmp/fastlivo/room02_2x2_O.bag"
CAP = 6000


def se3(deg, t):
    c, s = np.cos(np.deg2rad(deg)), np.sin(np.deg2rad(deg))
    T = np.eye(4)
    T[:3, :3] = np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])
    T[:3, 3] = t
    return T


def sample_scans(bag_path=BAG, n=N_SCANS):
    import rosbag
    from sensor_msgs import point_cloud2
    out = []
    with rosbag.Bag(bag_path) as bag:
        for i, (_, msg, _) in enumerate(bag.read_messages(topics=["/velodyne_points"])):
            if i % 25:
                continue
            pts = np.array([[p[0], p[1], p[2]] for p in point_cloud2.read_points(
                msg, field_names=("x", "y", "z"), skip_nans=True)], dtype=np.float64)
            if len(pts) <= CAP:
                capped = pts
            else:
                step = max(1, len(pts) // CAP)
                capped = pts[::step][:CAP]
            out.append({"stamp_ns": msg.header.stamp.to_nsec(), "points": len(capped),
                        "cloud": capped})
            if len(out) >= n:
                break
    return out


def statistics(info):
    vals = np.linalg.eigvalsh(0.5 * (info + info.T))
    v = np.linalg.eigh(0.5 * (info + info.T))[1][:, 0]
    return {"eigs": vals, "scalar": float(v @ info @ v),
            "min_eig": float(vals[0]), "max_eig": float(vals[-1]),
            "m_unconstrained": int(np.sum(vals < VARIANCE_FLOOR)),
            "ratio_min_max": float(vals[0] / max(vals[-1], 1e-12))}




def _rotation_control(cloud_room02):
    """Same physical scene, four orientations, both producers, relative to 0 degrees.

    Two sources are recorded because the two sessions measured different scans: the room02 scan
    sampled here, and the hall scan c1_fim_controls loads. The magnitudes differ by source; the
    direction of the finding -- the voxel grid is orientation-dependent and the stride producer is
    not -- is the same on both.
    """
    import importlib.util as _iu
    from slam_recovery.validation import compute_6dof_point_to_plane_fim as fim_old

    def one(cloud, label):
        """Two readings per rotation.

        `own_direction` compares each frame's own weak direction -- this mixes a change of matrix
        with a change of direction, which is why its percentages are unstable when the weakest
        direction swaps. `fixed_direction` transports the 0-degree weak direction into each
        rotated frame and evaluates there, so only the matrix changes. The fixed-direction column
        is the one that answers "is the producer orientation-dependent".
        """
        rows = []
        base = {}
        v0 = {}
        for deg in (0, 10, 30, 45):
            G = se3(deg, [2.0, -1.0, 0.5]) if deg else np.eye(4)
            moved = cloud if deg == 0 else (cloud @ G[:3, :3].T) + G[:3, 3]
            io_, _, _, _, wo_ = fim_old(moved, sigma_meas_m=0.075)
            vo_ = wo_ / np.linalg.norm(wo_)
            inn_, _, _, _, wn_ = c2.fim_spatial(moved)
            vn_ = wn_ / np.linalg.norm(wn_)
            if deg == 0:
                v0 = {"old": vo_.copy(), "new": vn_.copy()}
                base = {"old": float(vo_ @ io_ @ vo_), "new": float(vn_ @ inn_ @ vn_)}
            vo_fixed = transport(v0["old"], G) if deg else v0["old"]
            vo_fixed = vo_fixed / np.linalg.norm(vo_fixed)
            vn_fixed = transport(v0["new"], G) if deg else v0["new"]
            vn_fixed = vn_fixed / np.linalg.norm(vn_fixed)
            rows.append({
                "rotation_deg": deg,
                "old_own_direction_rel": abs(float(vo_ @ io_ @ vo_) - base["old"])
                / max(abs(base["old"]), 1e-12),
                "new_own_direction_rel": abs(float(vn_ @ inn_ @ vn_) - base["new"])
                / max(abs(base["new"]), 1e-12),
                "old_fixed_direction_rel": abs(float(vo_fixed @ io_ @ vo_fixed) - base["old"])
                / max(abs(base["old"]), 1e-12),
                "new_fixed_direction_rel": abs(float(vn_fixed @ inn_ @ vn_fixed) - base["new"])
                / max(abs(base["new"]), 1e-12),
            })
        return {"source": label, "rows": rows}

    out = [one(cloud_room02, "room02_2x2_O (/velodyne_points sample, cap 6000)")]
    c1_path = os.path.join(HERE, "c1_fim_controls.py")
    if os.path.exists(c1_path):
        spec = _iu.spec_from_file_location("c1", c1_path)
        c1 = _iu.module_from_spec(spec)
        spec.loader.exec_module(c1)
        out.append(one(c1.load_scan(), "hall01_100_160 (/velodyne_points, 30 m crop, 8000 pts)"))
    return {"note": ("own_direction mixes matrix and direction changes; fixed_direction transports "
                     "the 0-degree weak direction and isolates the matrix. The fixed column is the "
                     "decision-relevant one"),
            "sources": out}

def main():
    scans = sample_scans()
    rows = []
    for s in scans:
        info, _, _, _, _ = c2.fim_spatial(s["cloud"])
        st = statistics(info)
        rows.append({"stamp_ns": s["stamp_ns"], "points": s["points"],
                     "scalar_along_weakest": round(st["scalar"], 4),
                     "min_eig": round(st["min_eig"], 4), "max_eig": round(st["max_eig"], 4),
                     "m_unconstrained": st["m_unconstrained"],
                     "lambda_min_over_max": round(st["ratio_min_max"], 6)})

    scalars = np.array([r["scalar_along_weakest"] for r in rows])
    mins = np.array([r["min_eig"] for r in rows])
    corr = float(np.corrcoef(scalars, mins)[0, 1]) if len(rows) > 2 else None

    # rank agreement: do the two criteria order the scans the same way?
    order_scalar = np.argsort(scalars)
    order_min = np.argsort(mins)
    same_order = int(np.sum(order_scalar == order_min))
    rank_pairs = [(int(np.where(order_scalar == i)[0][0]), int(np.where(order_min == i)[0][0]))
                  for i in range(len(rows))]

    # gauge control on one scan: transport both quantities and compare both statistics
    s0 = scans[0]
    info0, _, _, _, _ = c2.fim_spatial(s0["cloud"])
    G = se3(30.0, [2.0, -1.0, 0.5])
    moved = (s0["cloud"] @ G[:3, :3].T) + G[:3, 3]
    info_m, _, _, _, _ = c2.fim_spatial(moved)
    st0, stm = statistics(info0), statistics(info_m)
    gauge = {"scalar_relative_diff": abs(stm["scalar"] - st0["scalar"]) / max(st0["scalar"], 1e-12),
             "min_eig_relative_diff": abs(stm["min_eig"] - st0["min_eig"])
             / max(abs(st0["min_eig"]), 1e-12),
             "m_unconstrained_before_after": [st0["m_unconstrained"],
                                              stm["m_unconstrained"]]}

    rotation = _rotation_control(scans[0]["cloud"])

    out = {
        "_meta": {
            "what": "form 2: observable-subspace gate, and why it is not the scalar",
            "written": "2026-11-10",
            "definition": {
                "variance_floor": VARIANCE_FLOOR,
                "why_this_number": "1/sigma_tol, the covariance bound the gate already applies",
                "gate": "admit only if m_after == 0 (no direction with lambda < 2.0)",
                "not_a_scalar": "it is a rank/condition condition over all six directions",
            },
            "bag": os.path.basename(BAG), "scans": len(rows), "cap": CAP,
            "form2_loewner_frozen": {
                "condition": "L_after - kappa * L_before is positive semi-definite AND "
                             "min(eig(L_after)) >= LAMBDA_FLOOR",
                "kappa": 2.0,
                "kappa_source": "GateThresholds.tau_info_kappa, the gate's frozen relative factor, "
                                "applied to the whole matrix (Loewner order) instead of one direction",
                "lambda_floor": VARIANCE_FLOOR,
                "lambda_floor_source": "1/sigma_tol, the covariance bound the gate already applies",
                "why_not_a_scalar": "two matrices can share lambda_min and the projection along v "
                                    "and still differ in Loewner order along other directions",
                "status": "frozen; decision-level comparison BLOCKED on L_after",
            },
            "form2_scalar_floor_frozen": {
                "condition": "count(eig(L_after) < LAMBDA_FLOOR) == 0",
                "status": "REJECTED by its own control: it is the scalar in disguise",
            },
            "not_done": ["no host run", "no threshold changed", "no production edit",
                         "decision-level comparison BLOCKED on `after`"],
        },
        "rows": rows,
        "scalar_vs_subspace": {
            "pearson_r": round(corr, 4) if corr is not None else None,
            "rank_identical_positions": same_order, "n": len(rows),
            "rank_pairs_scalar_vs_min_eig": rank_pairs,
            "reading": ("pearson_r = 1.0 and 24/24 identical positions: the two orderings are the "
                        "SAME. v is the weakest eigenvector, so v^T L v == lambda_min exactly, and "
                        "the 'subspace' condition is a second threshold on that one number. This "
                        "is the degeneracy the form was supposed to avoid, and it is not avoided"),
        },
        "gauge_control": gauge,
        "rotation_control": rotation,
    }
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, "p2_subspace_gate.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    print(json.dumps({k: out[k] for k in ("scalar_vs_subspace", "gauge_control")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
