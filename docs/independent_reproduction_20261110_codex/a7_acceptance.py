"""Desired A7 behavior: preserve the decision for a gauge re-expression.

The upstream script asserts the known failure. This script instead exits 1 when
the invariant fails, so its success cannot be mistaken for an algorithm fix.
"""
import json
import sys
import numpy as np
from upstream_a7_gauge_probes import evaluate, adjoint, transport, transport_information
from upstream_a7_gauge_probes import compute_6dof_point_to_plane_fim


def check(weak, before, after, covariance, shift):
    results = [evaluate(weak, before, after, covariance, s) for s in (0., shift)]
    transform = np.eye(4)
    transform[1, 3] = shift
    moved = transport(weak, transform)
    original_q = float(weak @ after @ weak)
    moved_q = float(moved @ transport_information(after, transform) @ moved)
    ad = adjoint(transform)
    back_cov = np.linalg.inv(ad) @ (ad @ covariance @ ad.T) @ np.linalg.inv(ad).T
    algebra_ok = bool(np.isclose(original_q, moved_q) and np.allclose(covariance, back_cov))
    passed = algebra_ok and results[0]["mode"] == results[1]["mode"]
    return {"status": "PASS" if passed else "FAIL", "passed": passed,
            "gate": results, "raw_quadratic_form": [original_q, moved_q],
            "algebra_control_passed": algebra_ok,
            "max_covariance_roundtrip_error": float(np.max(np.abs(covariance-back_cov)))}


def main():
    cloud = np.random.default_rng(0).normal(size=(400, 3))
    before, _, _, _, weak = compute_6dof_point_to_plane_fim(.5*cloud, sigma_meas_m=.075)
    after, _, _, _, _ = compute_6dof_point_to_plane_fim(.8*cloud, sigma_meas_m=.075)
    results = {"weak_direction": check(weak, before, after, np.linalg.inv(after+np.eye(6)*.001), 2.)}
    before, after = np.diag([60,60,60,20,40,40]), np.diag([60,60,60,30,5,5])
    results["covariance_origin"] = check(np.array([0.,0.,0.,1.,0.,0.]), before, after, np.linalg.inv(after), 5.)
    passed = all(value["passed"] for value in results.values())
    print(json.dumps({"checks": results, "passed": passed}, indent=2, allow_nan=False))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
