"""Tests for the stage-(d) pose re-registration.

Synthetic scenes with a known answer, so a change in the solver shows up as a wrong pose rather
than as a different number nobody can check.
"""

from __future__ import annotations

import numpy as np

from slam_recovery.repair.pose_reregistration import (
    ICP_CONFIG,
    IcpConfig,
    VoxelGrid,
    build_icp_candidate,
    estimate_normals,
    reregister_frame,
    reregister_segment,
    restrict_reference,
    sample_scan,
)


def _room(n=4000, seed=0):
    """Three orthogonal walls plus a floor: enough geometric variety to constrain 6 DoF."""
    rng = np.random.default_rng(seed)
    xs = rng.uniform(-4, 4, n)
    ys = rng.uniform(-4, 4, n)
    zs = rng.uniform(0, 3, n)
    parts = [
        np.column_stack([xs, ys, np.zeros(n)]),              # floor
        np.column_stack([np.full(n, -4.0), ys, zs]),         # wall x
        np.column_stack([np.full(n, 4.0), ys, zs]),          # wall x
        np.column_stack([xs, np.full(n, -4.0), zs]),         # wall y
    ]
    return np.vstack(parts)


def _rot(axis, deg):
    a = np.radians(deg)
    c, s = np.cos(a), np.sin(a)
    if axis == "z":
        return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
    if axis == "y":
        return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def _se3(R, t):
    T = np.eye(4)
    T[:3, :3] = R
    T[:3, 3] = t
    return T


# ---------------------------------------------------------------------------------------------
# neighbour search
# ---------------------------------------------------------------------------------------------
def test_voxel_grid_matches_brute_force():
    rng = np.random.default_rng(1)
    ref = rng.uniform(-5, 5, (1500, 3))
    q = rng.uniform(-5, 5, (200, 3))
    grid = VoxelGrid(ref, cell_m=1.0)
    idx, d2 = grid.query(q, k=1)
    brute = np.sum((q[:, None, :] - ref[None, :, :]) ** 2, axis=2)
    best = brute.argmin(axis=1)
    found = idx[:, 0] >= 0
    # where the grid finds something, it must be the true nearest (ties aside)
    assert np.allclose(d2[found, 0], brute[np.arange(len(q))[found], best[found]])
    assert found.mean() > 0.98


def test_voxel_grid_reports_misses_as_minus_one():
    grid = VoxelGrid(np.zeros((10, 3)))
    idx, d2 = grid.query(np.array([[100.0, 100.0, 100.0]]), k=1)
    assert idx[0, 0] == -1 and not np.isfinite(d2[0, 0])


def test_voxel_grid_k_neighbours_are_sorted():
    rng = np.random.default_rng(2)
    ref = rng.uniform(-3, 3, (800, 3))
    grid = VoxelGrid(ref, cell_m=1.0)
    idx, d2 = grid.query(rng.uniform(-3, 3, (50, 3)), k=4)
    ok = idx[:, 0] >= 0
    assert np.all(np.diff(d2[ok], axis=1) >= 0)


# ---------------------------------------------------------------------------------------------
# normals
# ---------------------------------------------------------------------------------------------
def test_normals_on_a_plane_are_parallel_to_its_normal():
    rng = np.random.default_rng(3)
    pts = np.column_stack([rng.uniform(-3, 3, 2000), rng.uniform(-3, 3, 2000),
                           np.zeros(2000)])
    normals, valid = estimate_normals(pts, VoxelGrid(pts, 1.0))
    assert valid.mean() > 0.95
    assert np.allclose(np.abs(normals[valid][:, 2]), 1.0, atol=1e-6)


# ---------------------------------------------------------------------------------------------
# the solver
# ---------------------------------------------------------------------------------------------
def test_reregistration_recovers_a_known_small_transform():
    world = _room()
    truth = _se3(_rot("z", 1.5) @ _rot("x", 0.8), np.array([0.12, -0.08, 0.05]))
    body = (world - truth[:3, 3]) @ truth[:3, :3]      # inverse of world = R p + t
    cfg = IcpConfig(scan_samples=3000, max_iters=30, convergence_tol=1e-9)
    init = np.eye(4)
    res = reregister_frame(body, world, init, cfg)
    assert res.status in ("CONVERGED", "ITERATION_LIMIT")
    assert np.linalg.norm(res.pose[:3, 3] - truth[:3, 3]) < 0.02
    ang = np.degrees(np.arccos(np.clip((np.trace(res.pose[:3, :3].T @ truth[:3, :3]) - 1) / 2,
                                       -1, 1)))
    assert ang < 0.5


def test_reregistration_leaves_an_already_correct_pose_alone():
    world = _room()
    body = (world - np.array([0.3, 0.2, 0.0])) @ np.eye(3)
    init = _se3(np.eye(3), np.array([0.3, 0.2, 0.0]))
    res = reregister_frame(body, world, init)
    assert res.status in ("CONVERGED", "ITERATION_LIMIT")
    assert res.displacement_from_init_m < 0.02
    assert res.rotation_from_init_deg < 0.2


def test_empty_reference_is_reported_not_guessed():
    res = reregister_frame(_room(100), np.zeros((0, 3)), np.eye(4))
    assert res.status == "REFERENCE_TOO_SMALL"
    assert res.iterations == 0


def test_reference_out_of_range_is_reported():
    world = _room() + np.array([500.0, 0.0, 0.0])
    res = reregister_frame(_room(200), world, np.eye(4))
    assert res.status == "REFERENCE_TOO_SMALL"


def test_result_records_what_the_frozen_spec_requires():
    world = _room()
    res = reregister_frame((world - np.array([0.1, 0.0, 0.0])), world, np.eye(4),
                           IcpConfig(scan_samples=2000))
    d = res.as_dict()
    for key in ("icp_iterations", "icp_residual", "icp_converged", "icp_inliers",
                "pose_se3", "reference_points", "scan_points"):
        assert key in d
    assert len(d["pose_se3"]) == 16
    assert d["icp_iterations"] <= ICP_CONFIG.max_iters


# ---------------------------------------------------------------------------------------------
# reference restriction and scan sampling
# ---------------------------------------------------------------------------------------------
def test_restrict_reference_applies_radius_and_cap():
    cfg = IcpConfig(reference_radius_m=2.0, reference_max_points=100)
    rng = np.random.default_rng(4)
    ref = rng.uniform(-10, 10, (5000, 3))
    near, total = restrict_reference(ref, np.eye(4), cfg)
    assert total == 5000
    assert np.all(np.linalg.norm(near, axis=1) <= 2.0)
    assert len(near) <= 100


def test_sample_scan_is_a_stride_subsample():
    pts = np.arange(10_000, dtype=float).reshape(-1, 1)
    out = sample_scan(pts, IcpConfig(scan_samples=1000))
    assert len(out) <= 1000
    assert out[0, 0] == 0.0


# ---------------------------------------------------------------------------------------------
# candidate assembly
# ---------------------------------------------------------------------------------------------
def test_build_candidate_keeps_successes_and_reports_failures():
    world = _room()
    scans, inits = {}, {}
    for i, dx in enumerate((0.05, 0.10)):
        t = np.array([dx, 0.0, 0.0])
        scans[i] = world - t
        T = np.eye(4)
        T[:3, 3] = t
        inits[i] = T
    poses, results = build_icp_candidate(scans, world, inits)
    assert set(poses) == {0, 1}
    assert len(results) == 2

    # a frame 900 m from the reference must not appear as a candidate, whatever the reason
    far = {0: world + np.array([900.0, 0.0, 0.0])}
    poses2, results2 = build_icp_candidate(far, world, {0: np.eye(4)})
    assert poses2 == {}
    assert results2[0][1].status in ("REFERENCE_TOO_SMALL", "TOO_FEW_CORRESPONDENCES")


def test_build_candidate_skips_frames_without_an_init_pose():
    world = _room()
    poses, results = build_icp_candidate({0: world, 1: world}, world, {0: np.eye(4)})
    assert set(poses) == {0}
    assert len(results) == 1


def test_segment_registration_recovers_one_rigid_correction():
    """Three frames placed wrong by the same rigid correction; one fit should undo all of it."""
    # a box alone leaves the yaw weakly constrained; add one plane whose normal is not axis
    # aligned, which is what makes the correction observable at the tolerance asserted below
    rng = np.random.default_rng(9)
    a, b = rng.uniform(-2, 2, 1200), rng.uniform(0, 2, 1200)
    e1 = np.array([1.0, 0.0, 0.0])
    n = np.array([1.0, 0.4, 0.2])
    n = n / np.linalg.norm(n)
    e1 = e1 - n * float(e1 @ n)
    e1 = e1 / np.linalg.norm(e1)
    e2 = np.cross(n, e1)
    slab = a[:, None] * e1 + b[:, None] * e2 + np.array([1.5, 1.5, 1.0]) - 4.0 * n
    world = np.vstack([_room(), slab])
    Rc = _rot("z", 1.0)
    tc = np.array([0.10, -0.05, 0.02])
    # world = Rc @ body + tc, so ICP on (body -> world) from identity recovers se3(Rc, tc)
    body = (world - tc) @ Rc          # row-vector convention: p @ R = R^T p
    scans = {i: body for i in range(3)}
    poses = {i: np.eye(4) for i in range(3)}      # every frame claims it is already in world
    cfg = IcpConfig(scan_samples=3000, max_iters=30, convergence_tol=1e-9)
    res = reregister_segment(scans, poses, world, cfg)
    assert res.status in ("CONVERGED", "ITERATION_LIMIT")
    assert np.linalg.norm(res.pose[:3, 3] - tc) < 0.01
    ang = np.degrees(np.arccos(np.clip(
        (np.trace(res.pose[:3, :3].T @ Rc) - 1) / 2, -1, 1)))
    assert ang < 0.3


def test_segment_registration_is_one_registration_not_one_per_frame():
    world = _room(1500)
    scans = {i: world for i in range(5)}
    poses = {i: np.eye(4) for i in range(5)}
    res = reregister_segment(scans, poses, world, IcpConfig(scan_samples=800, max_iters=5))
    # the reported scan size is the sampled merged cloud, not five frames' worth
    assert res.scan_points <= 800
    assert res.status in ("CONVERGED", "ITERATION_LIMIT")


def test_segment_registration_without_frames_reports_it():
    res = reregister_segment({}, {}, _room(500))
    assert res.status == "NO_FRAMES"
