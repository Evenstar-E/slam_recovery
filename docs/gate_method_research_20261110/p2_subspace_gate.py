#!/usr/bin/env python3
"""Part 2, form 2: an observable-subspace gate, and the control that locates what it is NOT.

DEFINITION (frozen before running)

  lambda_k            eigenvalues of the 6x6 information in the evaluation basis (A7 anchor body)
  "unconstrained"     lambda_k < LAMBDA_FLOOR = 1/sigma_tol = 2.0, i.e. the variance along that
                      direction exceeds the covariance bound the gate already uses in its
                      posterior-covariance leg. The number is inherited from sigma_tol, not chosen.
  m_after             how many directions of Lambda_after are unconstrained
  subspace gate       admit only if m_after == 0   (all six directions constrainable)

WHAT THE EARLIER VERSION OF THIS SCRIPT GOT WRONG

  It compared, for each scan, the projection along that matrix's own minimum eigenvector with
  lambda_min. That is a tautology (v^T L v == lambda when v is the eigenvector), not evidence
  about the gate, whose v is the FIXED trigger direction. The numbers are kept below, relabelled,
  and the conclusion is drawn instead from an actual `evaluate_four_mode_gate` call.

WHAT THE ACTUAL GATE CONTROL SHOWS

  With the trigger direction fixed and a candidate whose weakest eigenvalue is 38.8889, the gate's
  information leg reads 100 and admits the candidate (Mode 2). The gate's v is therefore NOT the
  candidate's weakest eigenvector, and `m_after == 0` is not a re-parameterisation of that leg. In
  the same basis, with P = Lambda^-1 exactly, `m_after == 0` is exactly the gate's covariance-norm
  leg (lambda_min(Lambda) >= 1/sigma_tol  <=>  ||P||_2 <= sigma_tol). Loewner order remains a
  genuinely different, researchable matrix condition -- but not the only non-degenerate form.

Form 1 (the current conjunction) and form 3 (sequential admission) are defined in the report;
their decision-level comparison needs `after`, which the archive does not carry, so they stay
BLOCKED.

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

from slam_recovery.core import (  # noqa: E402
    CandidateMap, Checkpoint, GateThresholds, QuarantineSegment, TangentFrame,
    evaluate_four_mode_gate, transport, transport_information,
)

VARIANCE_FLOOR = 2.0        # = 1 / sigma_tol (core.py's covariance leg); inherited, not tuned
N_SCANS = 24
BAG = "/tmp/fastlivo/room02_2x2_O.bag"
CAP = 6000


def se3(deg, t):
    c, s = np.cos(np.deg2rad(deg)), np.sin(np.deg2rad(deg))
    T = np.eye(4)
    T[:3, :3] = np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])
    T[:3, 3] = np.asarray(t, dtype=np.float64)
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


def _spd_transport_control():
    """The reviewer's exact SPD control: transport v and L together, do not re-normalise.

    v0 has Euclidean norm sqrt(6) on purpose.  v^T L v = 1 at v0; transporting both leaves the
    scalar at 1 to machine precision; re-normalising the transported direction divides the
    Rayleigh quotient by ||Ad v0||^2 = 6.  The 1/6 is a norm artefact, not a physical change, and
    it is why a rotation control must state which of the two protocols it uses.
    """
    L0 = np.eye(6) / 6.0
    v0 = np.ones(6)
    base = float(v0 @ L0 @ v0)
    G = se3(30.0, [0.0, 0.0, 0.0])
    v1 = transport(v0, G)
    L1 = transport_information(L0, G)
    raw = float(v1 @ L1 @ v1)
    unit = v1 / np.linalg.norm(v1)
    renorm = float(unit @ L1 @ unit)
    return {
        "base_projection": base,
        "transported_no_renormalisation": raw,
        "abs_diff_no_renormalisation": abs(raw - base),
        "ad_v0_norm_squared": float(v1 @ v1),
        "transported_then_renormalised": renorm,
        "renormalised_over_base": renorm / base,
        "reading": ("1 -> 1.000000000000016 -> 1/6. The first two differ by round-off; the third "
                    "differs by ||Ad v0||^2 = 6, a scale introduced by the re-normalisation "
                    "itself. A protocol that re-normalises is reporting a different Rayleigh "
                    "quantity and must say so"),
    }


def _old_mixed_protocol(cloud, label):
    """The OLD control, kept verbatim and labelled: SE(3) INCLUDING translation, and the
    transported direction re-normalised. Its percentages mix three effects (matrix, direction,
    re-normalisation) and must not be read as rotation sensitivity."""
    from slam_recovery.validation import compute_6dof_point_to_plane_fim as fim_old

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
            "rotation_deg": deg, "translation_m": [0.0, 0.0, 0.0] if deg == 0 else [2.0, -1.0, 0.5],
            "old_own_direction_rel": abs(float(vo_ @ io_ @ vo_) - base["old"])
            / max(abs(base["old"]), 1e-12),
            "new_own_direction_rel": abs(float(vn_ @ inn_ @ vn_) - base["new"])
            / max(abs(base["new"]), 1e-12),
            "old_fixed_direction_rel": abs(float(vo_fixed @ io_ @ vo_fixed) - base["old"])
            / max(abs(base["old"]), 1e-12),
            "new_fixed_direction_rel": abs(float(vn_fixed @ inn_ @ vn_fixed) - base["new"])
            / max(abs(base["new"]), 1e-12),
        })
    return {"source": label, "protocol": "SE3 (translation + rotation) AND re-normalised after "
            "transport -- the old reading; retained, not used for the conclusion", "rows": rows}


def _anchored_rotation_control(cloud, label):
    """Correct protocol: evaluate every transformed scan back in the ORIGINAL anchor frame.

    The matrix is transported back with transport_information(L, G^-1) and the anchor direction
    v0 is used unchanged. No re-normalisation anywhere. Three transforms are separated so the
    cause of any deviation is attributable:

      pure_rotation     G = R, t = 0          -- the rotation-sensitivity question
      pure_translation  G = I, t != 0         -- the grid's translation sensitivity (diagnostic)
      full_se3          G = [R|t]             -- rigid re-expression, both at once

    A producer that is covariant under rigid re-expression returns the 0-degree value in all
    three; any deviation is the producer's, not the protocol's.
    """
    from slam_recovery.validation import compute_6dof_point_to_plane_fim as fim_old

    io0, _, _, _, wo0 = fim_old(cloud, sigma_meas_m=0.075)
    in0, _, _, _, wn0 = c2.fim_spatial(cloud)
    vo0 = wo0 / np.linalg.norm(wo0)
    vn0 = wn0 / np.linalg.norm(wn0)
    base_o = float(vo0 @ io0 @ vo0)
    base_n = float(vn0 @ in0 @ vn0)

    transforms = []
    for deg in (10, 30, 45):
        transforms.append(("pure_rotation", deg, [0.0, 0.0, 0.0]))
    transforms.append(("pure_translation", 0, [2.0, -1.0, 0.5]))
    for deg in (10, 30, 45):
        transforms.append(("full_se3", deg, [2.0, -1.0, 0.5]))

    rows = []
    for kind, deg, t in transforms:
        G = se3(deg, t)
        moved = cloud @ G[:3, :3].T + G[:3, 3]
        io, _, _, _, _ = fim_old(moved, sigma_meas_m=0.075)
        inn, _, _, _, _ = c2.fim_spatial(moved)
        back_o = transport_information(io, np.linalg.inv(G))
        back_n = transport_information(inn, np.linalg.inv(G))
        po = float(vo0 @ back_o @ vo0)
        pn = float(vn0 @ back_n @ vn0)
        rows.append({
            "transform": kind, "rotation_deg": deg, "translation_m": t,
            "old_rel": abs(po - base_o) / max(abs(base_o), 1e-12),
            "new_rel": abs(pn - base_n) / max(abs(base_n), 1e-12),
        })
    return {"source": label, "protocol": "information transported back to the 0-degree anchor "
            "frame; anchor direction unchanged; no re-normalisation",
            "base_old": base_o, "base_new": base_n, "rows": rows}


def _rotation_control(cloud_room02):
    sources = [_anchored_rotation_control(cloud_room02,
                                          "room02_2x2_O (/velodyne_points sample, cap 6000)")]
    c1_path = os.path.join(HERE, "c1_fim_controls.py")
    hall_cloud = None
    if os.path.exists(c1_path):
        spec = importlib.util.spec_from_file_location("c1", c1_path)
        c1 = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(c1)
        hall_cloud = c1.load_scan()
        sources.append(_anchored_rotation_control(
            hall_cloud, "hall01_100_160 (/velodyne_points, 30 m crop, 8000 pts)"))
    old = [_old_mixed_protocol(cloud_room02, "room02_2x2_O")]
    if hall_cloud is not None:
        old.append(_old_mixed_protocol(hall_cloud, "hall01_100_160"))
    return {"note": ("The decision-relevant columns are the `rel` values of `pure_rotation` on the "
                     "anchored protocol: the same scene re-expressed by a rotation only, with "
                     "information and direction transported back to one anchor, no "
                     "re-normalisation. `pure_translation` and `full_se3` are diagnostics. The "
                     "`mixed_protocol_old` block is the earlier reading (translation + "
                     "re-normalisation); its percentages are retained and must not be quoted as "
                     "rotation sensitivity"),
            "sources": sources, "mixed_protocol_old": old,
            "spd_control": _spd_transport_control()}


def _actual_gate_control():
    """Run the real gate. The trigger direction is fixed; the candidate's weakest eigenvalue is
    not the axis the information leg reads."""
    frame = TangentFrame("body", "rot_trans", "scan:control")
    v = np.array([0.0, 0.0, 0.0, 1.0, 0.0, 0.0])       # trigger weak direction: translation x
    before = np.diag([0.1, 0.1, 0.1, 5.0, 0.1, 0.1])   # v^T Lambda v = 5
    after = np.diag([300.0, 300.0, 300.0, 100.0, 38.8889, 38.8889])
    cov = np.linalg.inv(after)
    cp = Checkpoint("control", 0, 1, {0: np.eye(4)}, [], np.zeros(3), np.zeros(3))
    seg = QuarantineSegment("control", cp, 0, 2_000_000_000, v, before, 1.0,
                            weak_direction_frame=frame, info_before_frame=frame)
    cand = CandidateMap("control", 1, {0: np.eye(4)}, after, cov, 1.0,
                        info_after_frame=frame, cov_after_frame=frame,
                        paired_benefit_approved=True, wilson_lower_bound=1.0,
                        reentry_pos_jump_m=0.0, boundary_continuity_ok=True)
    rep = evaluate_four_mode_gate(seg, cand, GateThresholds())
    eigs = np.linalg.eigvalsh(after)
    lam_min = float(eigs[0])
    gate_scalar = float(rep.weak_dir_info_after)
    p_norm = float(np.linalg.norm(cov, ord=2))
    return {
        "what": "actual evaluate_four_mode_gate call, synthetic candidate fixed before the run",
        "trigger_direction": v.tolist(),
        "candidate_diag": np.diag(after).tolist(),
        "gate_scalar_along_fixed_direction": gate_scalar,
        "lambda_min_after": lam_min,
        "fixed_direction_is_candidate_weakest_eigenvector": bool(
            abs(gate_scalar - lam_min) <= 1e-9 * max(abs(gate_scalar), 1.0)),
        "gate_mode": rep.mode.name,
        "accepted": bool(rep.accepted),
        "posterior_cov_norm": p_norm,
        "m_after_at_floor_2": int(np.sum(eigs < VARIANCE_FLOOR)),
        "equivalence_with_covariance_leg": {
            "statement": ("in one basis and with P = Lambda^-1 exactly, "
                          "min(eig(Lambda)) >= 1/sigma_tol  <=>  ||P||_2 <= sigma_tol"),
            "here_min_eig_ge_2": bool(lam_min >= VARIANCE_FLOOR),
            "here_cov_norm_le_sigma_tol": bool(p_norm <= GateThresholds().sigma_tol),
        },
        "reading": ("the candidate's weakest eigenvalue is 38.8889, yet the gate reads 100 and "
                    "commits (Mode 2): the information leg profiles a FIXED trigger direction, not "
                    "the candidate's weakest eigenvector. `m_after == 0` therefore is not that leg "
                    "in another form -- with P = Lambda^-1 it is the covariance-norm leg"),
    }


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

    order_scalar = np.argsort(scalars)
    order_min = np.argsort(mins)
    same_order = int(np.sum(order_scalar == order_min))
    rank_pairs = [(int(np.where(order_scalar == i)[0][0]), int(np.where(order_min == i)[0][0]))
                  for i in range(len(rows))]

    # spectral gauge on one scan: transport the rotated matrix back to the anchor and compare the
    # whole spectrum there. This is not the own-direction self-comparison -- the two spectra are
    # of the same physical scene in the same basis, so a covariant producer returns them equal.
    s0 = scans[0]
    info0, _, _, _, _ = c2.fim_spatial(s0["cloud"])
    G = se3(30.0, [2.0, -1.0, 0.5])
    moved = (s0["cloud"] @ G[:3, :3].T) + G[:3, 3]
    info_m, _, _, _, _ = c2.fim_spatial(moved)
    back_m = transport_information(info_m, np.linalg.inv(G))
    eigs0 = np.linalg.eigvalsh(0.5 * (info0 + info0.T))
    eigs_back = np.linalg.eigvalsh(0.5 * (back_m + back_m.T))
    gauge = {"transform": "full_se3 30 deg, matrix transported back to the 0-degree anchor",
             "lambda_min_relative_diff": float(abs(eigs_back[0] - eigs0[0])
                                               / max(abs(eigs0[0]), 1e-12)),
             "lambda_max_relative_diff": float(abs(eigs_back[-1] - eigs0[-1])
                                               / max(abs(eigs0[-1]), 1e-12)),
             "spectrum_relative_diff_l2": float(np.linalg.norm(eigs_back - eigs0)
                                                / max(np.linalg.norm(eigs0), 1e-12)),
             "m_unconstrained_before_after": [int(np.sum(eigs0 < VARIANCE_FLOOR)),
                                              int(np.sum(eigs_back < VARIANCE_FLOOR))]}

    rotation = _rotation_control(scans[0]["cloud"])
    gate_control = _actual_gate_control()

    out = {
        "_meta": {
            "what": "form 2: observable-subspace gate; what it is, and what it is not",
            "written": "2026-11-10",
            "definition": {
                "variance_floor": VARIANCE_FLOOR,
                "why_this_number": "1/sigma_tol, the covariance bound the gate already applies",
                "gate": "admit only if m_after == 0 (no direction with lambda < 2.0)",
                "what_it_is": "a full-spectrum minimum-eigenvalue threshold; with P = Lambda^-1 "
                              "it coincides with the gate's covariance-norm leg",
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
                "not_the_only_form": "Loewner survives its controls, but it is one alternative "
                                     "matrix-level condition, not the unique non-degenerate form",
            },
            "form2_scalar_floor_frozen": {
                "condition": "count(eig(L_after) < LAMBDA_FLOOR) == 0",
                "status": "this is the COVARIANCE leg in disguise (P = Lambda^-1), not the "
                          "information leg; see gate_control",
            },
            "not_done": ["no host run", "no threshold changed", "no production edit",
                         "decision-level comparison BLOCKED on `after`"],
        },
        "rows": rows,
        "tautology_check": {
            "what": "each matrix's OWN minimum eigenvector vs its lambda_min",
            "pearson_r": round(corr, 4) if corr is not None else None,
            "rank_identical_positions": same_order, "n": len(rows),
            "rank_pairs_own_eigenvector_vs_min_eig": rank_pairs,
            "reading": ("pearson_r = 1.0 and 24/24 identical positions is ALGEBRA, not a finding: "
                        "the script compares each matrix with itself (v^T L v == lambda when v is "
                        "the eigenvector). It says nothing about the gate, whose v is the fixed "
                        "trigger direction. Kept as a numeric self-check only"),
        },
        "gate_control": gate_control,
        "gauge_control": gauge,
        "rotation_control": rotation,
    }
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, "p2_subspace_gate.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    print(json.dumps({k: out[k] for k in ("tautology_check", "gate_control", "gauge_control")},
                     indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
