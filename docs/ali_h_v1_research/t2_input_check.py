#!/usr/bin/env python3
"""T2 input contract: validate the new-trace manifest and compute e_I, without running T2.

This is preparation. It does NOT claim T2/T3 results and does NOT read any real trace: the S2
export has not been delivered. The validator refuses a trace whose declarations are incomplete or
whose covariance is the measurement-space S / information H_T_H, and the residual code only uses
the 6D pose blocks P- / P+ with a declared state order, rotation parameterisation and perturbation
side. All selftest inputs are SYNTHETIC/UNIT.

    python -I docs/ali_h_v1_research/t2_input_check.py selftest
"""

from __future__ import annotations

import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "t2_prep_selftest.json")

OLD_RUN_IDS = {"fl_native_20261112T065500Z_187992", "fl_native_20261112T070801Z_197026"}

REQUIRED_TOP = ("run_id", "same_build_off_on", "inputs", "behavior_control", "exports",
                "declarations", "covariance", "join")
REQUIRED_INPUTS = ("bag_sha256", "library_sha256", "config_sha256")
REQUIRED_EXPORTS = ("P_minus", "P_plus", "vec", "effct_feat_num",
                    "pose_pre", "pose_post", "stamps", "has_out",
                    "scan_header_stamp", "last_lio_update_time",
                    "scan_source_index", "native_group_id", "native_phase")
REQUIRED_DECL = ("state_order", "rotation_param", "perturbation", "pose_frame",
                 "vec_frame", "extrinsic", "bias_source")
VALID_STATE_ORDER = {"rot_trans", "trans_rot"}
VALID_PERTURBATION = {"left", "right"}


def check_manifest(m: dict) -> dict:
    """Validate a proposed trace manifest. Returns READY / READY_UNIT_ONLY / INCOMPLETE."""
    missing, errors, warnings = [], [], []
    for key in REQUIRED_TOP:
        if key not in m:
            missing.append(key)
    if missing:
        return {"status": "INCOMPLETE", "missing": sorted(missing), "errors": errors,
                "warnings": warnings}
    if m["run_id"] in OLD_RUN_IDS:
        errors.append("run_id_is_an_old_archive_run")
    if m.get("same_build_off_on") is not True:
        errors.append("off/on runs are not the same build")
    inputs = m.get("inputs") or {}
    for key in REQUIRED_INPUTS:
        if not inputs.get(key):
            missing.append(f"inputs.{key}")
    exports = m.get("exports") or {}
    for key in REQUIRED_EXPORTS:
        if exports.get(key) is not True:
            missing.append(f"exports.{key}")
    decl = m.get("declarations") or {}
    for key in REQUIRED_DECL:
        if key not in decl:
            missing.append(f"declarations.{key}")
    if decl.get("state_order") not in VALID_STATE_ORDER:
        errors.append("declarations.state_order must be rot_trans or trans_rot")
    if decl.get("perturbation") not in VALID_PERTURBATION:
        errors.append("declarations.perturbation must be left or right")
    if decl.get("pose_frame") not in ("body", "world"):
        errors.append("declarations.pose_frame must be body or world")
    if decl.get("vec_frame") not in ("body", "world"):
        errors.append("declarations.vec_frame must be body or world")
    if decl.get("bias_source") in (None, "", "zero"):
        errors.append("declarations.bias_source must name a real source, not zero/placeholder")
    if decl.get("extrinsic") is not True:
        missing.append("declarations.extrinsic")

    join = m.get("join") or {}
    # A constant header/end offset is not evidence of identity, and a variable offset is not
    # evidence against it. Both correspondence claims must be established by the exporter.
    if join.get("identity_correspondence") is not True:
        errors.append("join_identity_unresolved: scan_source_index/native_group_id do not "
                      "establish one physical scan")
    if join.get("time_correspondence") is not True:
        errors.append("join_time_unresolved: the two ends are not the same physical interval")
    forbidden = set(m.get("not_included") or [])
    cov = m.get("covariance") or {}
    for name in ("S", "H_T_H"):
        if name in (decl.get("covariance_field") or ""):
            errors.append(f"covariance must not be {name} (measurement-space/information matrix)")
    if cov.get("usable") is True:
        if cov.get("blocks") not in ("P_minus/P_plus", "P_minus", "P_plus"):
            errors.append("covariance.blocks must name the 6x6 pose blocks")
        # e_I = Log(inv(pre) * post) is a RIGHT perturbation expressed in the pre-pose body
        # frame. A covariance declared left, or in another frame, is a different tangent; using
        # it here can be off by orders of magnitude. Conversion is not implemented, so refuse.
        if decl.get("perturbation") != "right":
            errors.append("declarations.perturbation must be right for this e_I convention")
        if cov.get("perturbation") != "right":
            errors.append("covariance.perturbation must be right")
        if cov.get("frame") != "pre_body":
            errors.append("covariance.frame must be pre_body (the tangent of inv(pre)*post)")
        status = "READY"
    elif cov.get("usable") is False and cov.get("reason"):
        if decl.get("perturbation") != "right":
            warnings.append("perturbation_not_right_but_unit_only")
        warnings.append(f"unit_weighted_only:{cov['reason']}")
        status = "READY_UNIT_ONLY"
    else:
        missing.append("covariance.usable (+ reason when false)")
        status = "INCOMPLETE"
    if "S" not in forbidden or "H_T_H" not in forbidden:
        warnings.append("manifest should list S and H_T_H under not_included")
    if missing or errors:
        return {"status": "INCOMPLETE", "missing": sorted(set(missing)), "errors": errors,
                "warnings": warnings}
    return {"status": status, "missing": [], "errors": [], "warnings": warnings}


def so3_log(R: np.ndarray) -> np.ndarray:
    R = np.asarray(R, dtype=np.float64)
    tr = float(np.trace(R))
    c = max(-1.0, min(1.0, 0.5 * (tr - 1.0)))
    theta = math.acos(c)
    if theta < 1e-12:
        return np.zeros(3)
    w = np.array([R[2, 1] - R[1, 2], R[0, 2] - R[2, 0], R[1, 0] - R[0, 1]]) / (2.0 * math.sin(theta))
    return w * theta


def _hat(w: np.ndarray) -> np.ndarray:
    w = np.asarray(w, dtype=np.float64).reshape(3)
    return np.array([[0.0, -w[2], w[1]], [w[2], 0.0, -w[0]], [-w[1], w[0], 0.0]])


def so3_left_jacobian_inv(w: np.ndarray) -> np.ndarray:
    """V(w)^-1 for the SE(3) Log: t = V(w) rho, so rho = V(w)^-1 t.

    The small-angle series is used below 1e-4 to avoid the 1 - (theta/2)cot(theta/2)
    cancellation; above it the closed form is
        V^-1 = I - 0.5*hat(w) + c*hat(w)^2,  c = (1 - (theta/2)cot(theta/2)) / theta^2.
    """
    w = np.asarray(w, dtype=np.float64).reshape(3)
    th = float(np.linalg.norm(w))
    W = _hat(w)
    if th < 1e-4:
        return np.eye(3) - 0.5 * W + (1.0 / 12.0) * (W @ W)
    c = (1.0 - 0.5 * th / math.tan(0.5 * th)) / (th * th)
    return np.eye(3) - 0.5 * W + c * (W @ W)


def e_i(pose_pre: np.ndarray, pose_post: np.ndarray, state_order: str = "rot_trans") -> np.ndarray:
    """e_I = Log(inv(DeltaT_pre) * DeltaT_post) in the declared block order.

    The translation of an SE(3) Log is V(w)^-1 * t, not t: the exponential maps rho through the
    left Jacobian V. Returning t directly understates/rotates the translation whenever the
    relative rotation is non-zero.

    Both poses must already be in the same declared frame with the declared extrinsic applied;
    the caller owns that mapping. A frame mismatch is a caller error, not something this function
    guesses.
    """
    if state_order not in VALID_STATE_ORDER:
        raise ValueError(f"unknown state_order {state_order!r}")
    A = np.asarray(pose_pre, dtype=np.float64)
    B = np.asarray(pose_post, dtype=np.float64)
    if A.shape != (4, 4) or B.shape != (4, 4):
        raise ValueError("pose_pre/pose_post must be 4x4")
    D = np.linalg.inv(A) @ B
    rot = so3_log(D[:3, :3])
    trans = so3_left_jacobian_inv(rot) @ D[:3, 3]
    return np.concatenate([rot, trans]) if state_order == "rot_trans" else np.concatenate([trans, rot])


def s_i(e: np.ndarray, cov: np.ndarray, rel_tol: float = 1e-9) -> dict:
    """s_I on the observable subspace of a real 6x6 covariance, or a unit-weighted residual."""
    e = np.asarray(e, dtype=np.float64).reshape(6)
    P = np.asarray(cov, dtype=np.float64)
    if P.shape != (6, 6):
        raise ValueError("covariance must be 6x6")
    w, V = np.linalg.eigh(0.5 * (P + P.T))
    keep = w > rel_tol * max(float(w.max()), 1e-12)
    rank = int(keep.sum())
    if rank == 0:
        return {"status": "NOT_AVAILABLE", "reason": "zero_rank_covariance", "rank": 0}
    coeff = V[:, keep].T @ e
    s = float(np.sum(coeff ** 2 / w[keep]))
    return {"status": "OK", "s": s, "rank": rank, "e": e.tolist()}


def unit_only(e: np.ndarray) -> dict:
    e = np.asarray(e, dtype=np.float64).reshape(6)
    return {"status": "NOT_AVAILABLE", "reason": "no_pose_covariance", "unit_weighted": e.tolist(),
            "sum_squares": float(e @ e)}


# ---------------------------------------------------------------------------------------------
def _manifest(**over):
    m = {
        "run_id": "fl_native_SYNTHETIC_TRACE_000",
        "same_build_off_on": True,
        "inputs": {"bag_sha256": "a" * 64, "library_sha256": "b" * 64, "config_sha256": "c" * 64},
        "behavior_control": {"trace_off_run": "off", "trace_on_run": "on",
                             "old_decisions_identical": True},
        "exports": {k: True for k in REQUIRED_EXPORTS},
        "declarations": {"state_order": "rot_trans", "rotation_param": "rotvec",
                         "perturbation": "right", "pose_frame": "world", "vec_frame": "body",
                         "extrinsic": True, "bias_source": "host_estimate",
                         "covariance_field": "P_minus/P_plus"},
        "covariance": {"usable": True, "blocks": "P_minus/P_plus",
                       "frame": "pre_body", "perturbation": "right"},
        "not_included": ["S", "H_T_H"],
        "join": {"identity_correspondence": True, "time_correspondence": True,
                 "identity_method": "scan_source_index + native_group_id",
                 "time_method": "same physical interval, original ns",
                 "offset_constant": True},
    }
    m.update(over)
    return m


def selftest() -> dict:
    tests = []

    def add(name, ok, detail):
        tests.append({"test": name, "status": "PASS" if ok else "FAIL", "detail": detail})

    m = _manifest()
    r = check_manifest(m)
    add("valid manifest is READY", r["status"] == "READY", r)

    m2 = _manifest()
    del m2["exports"]["P_minus"]
    r2 = check_manifest(m2)
    add("missing P_minus is INCOMPLETE", r2["status"] == "INCOMPLETE"
        and "exports.P_minus" in r2["missing"], r2)

    m3 = _manifest()
    m3["declarations"]["covariance_field"] = "S"
    r3 = check_manifest(m3)
    add("measurement-space S rejected", r3["status"] == "INCOMPLETE"
        and any("S" in e for e in r3["errors"]), r3)

    m4 = _manifest(run_id="fl_native_20261112T065500Z_187992")
    r4 = check_manifest(m4)
    add("old run id rejected", r4["status"] == "INCOMPLETE"
        and "run_id_is_an_old_archive_run" in r4["errors"], r4)

    m5 = _manifest(covariance={"usable": False, "reason": "no_pose_block"})
    r5 = check_manifest(m5)
    add("unit-only manifest is READY_UNIT_ONLY", r5["status"] == "READY_UNIT_ONLY", r5)

    m6 = _manifest()
    m6["declarations"]["perturbation"] = "left"
    r6 = check_manifest(m6)
    add("left perturbation is refused", r6["status"] == "INCOMPLETE"
        and any("perturbation must be right" in e for e in r6["errors"]), r6)

    m7 = _manifest()
    m7["covariance"]["frame"] = "world"
    r7 = check_manifest(m7)
    add("covariance in another frame is refused", r7["status"] == "INCOMPLETE"
        and any("pre_body" in e for e in r7["errors"]), r7)

    m8 = _manifest()
    del m8["covariance"]["frame"]
    r8 = check_manifest(m8)
    add("missing covariance frame is refused", r8["status"] == "INCOMPLETE"
        and any("pre_body" in e for e in r8["errors"]), r8)

    # Constant offset, but identity is not established -> still INCOMPLETE.
    m9 = _manifest()
    m9["join"]["identity_correspondence"] = False
    m9["join"]["offset_constant"] = True
    r9 = check_manifest(m9)
    add("constant offset without identity is refused", r9["status"] == "INCOMPLETE"
        and any("join_identity_unresolved" in e for e in r9["errors"]), r9)

    m10 = _manifest()
    m10["join"]["time_correspondence"] = False
    r10 = check_manifest(m10)
    add("missing time correspondence is refused", r10["status"] == "INCOMPLETE"
        and any("join_time_unresolved" in e for e in r10["errors"]), r10)

    # identity -> zero residual
    I = np.eye(4)
    e0 = e_i(I, I)
    add("identity gives zero e_I", float(np.linalg.norm(e0)) < 1e-12, {"e": e0.tolist()})

    # known rotation about z and translation
    th = 0.2
    B = np.eye(4)
    B[:3, :3] = np.array([[math.cos(th), -math.sin(th), 0],
                          [math.sin(th), math.cos(th), 0], [0, 0, 1]])
    B[:3, 3] = [0.1, 0.0, 0.0]
    e1 = e_i(I, B)
    expected_trans = np.array([0.099666444232592, -0.01, 0.0])   # V(w)^-1 t, not t
    ok_e = (abs(e1[2] - th) < 1e-12 and np.allclose(e1[3:], expected_trans, atol=1e-12)
            and abs(e1[0]) < 1e-12)
    ok_regression = bool(abs(e1[3] - 0.1) > 1e-4)  # the old (missing V^-1) value would be 0.1
    add("rotvec+V^-1 translation recovered", ok_e and ok_regression,
        {"e": e1.tolist(), "expected_trans": expected_trans.tolist(),
         "old_bug_value_rejected": ok_regression})

    # state order changes the block order, not the values
    e2 = e_i(I, B, state_order="trans_rot")
    add("state order is honoured", np.allclose(e2[:3], e1[3:], atol=1e-12)
        and np.allclose(e2[3:], e1[:3], atol=1e-12), {"e": e2.tolist()})

    # covariance identity -> s = |e|^2
    res = s_i(e1, np.eye(6))
    add("identity covariance gives |e|^2", res["status"] == "OK"
        and abs(res["s"] - float(e1 @ e1)) < 1e-12 and res["rank"] == 6, res)

    # rank-deficient covariance skips the null direction
    P = np.eye(6)
    P[5, 5] = 0.0
    res2 = s_i(e1, P)
    expected = float(e1[0] ** 2 + e1[1] ** 2 + e1[2] ** 2 + e1[3] ** 2 + e1[4] ** 2)
    add("rank-deficient covariance uses observable subspace",
        res2["status"] == "OK" and res2["rank"] == 5 and abs(res2["s"] - expected) < 1e-12, res2)

    u = unit_only(e1)
    add("no covariance -> unit-weighted only", u["status"] == "NOT_AVAILABLE"
        and "unit_weighted" in u and "s" not in u, u)

    failed = sum(1 for t in tests if t["status"] != "PASS")
    return {"marker": "SYNTHETIC_UNIT", "t2_real_status": "NOT_EXECUTED",
            "tests": tests, "failed": failed}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "selftest":
        result = selftest()
        with open(OUT, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=1, ensure_ascii=False)
        print(json.dumps(result, indent=1, ensure_ascii=False))
        return 0 if result["failed"] == 0 else 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
