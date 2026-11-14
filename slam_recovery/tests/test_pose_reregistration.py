"""Tests for the stage-(d) pose re-registration.

Synthetic scenes with a known answer, so a change in the solver shows up as a wrong pose rather
than as a different number nobody can check.
"""

from __future__ import annotations

import numpy as np

from slam_recovery.repair.pose_reregistration import (
    ICP_CONFIG,
    MOTION_PRIOR_MAX_M,
    IcpConfig,
    VoxelGrid,
    build_icp_candidate,
    build_motion_prior_candidate,
    clamp_pose_to_envelope,
    estimate_normals,
    motion_prior_envelope_m,
    reregister_frame,
    reregister_frame_motion_prior,
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


# ---------------------------------------------------------------------------------------------
# motion-prior constrained, multi-scale re-registration
# ---------------------------------------------------------------------------------------------
def test_motion_prior_envelope_grows_with_elapsed_time_and_caps():
    # The envelope is the declared prior-drift model: base uncertainty plus half an acceleration
    # bound, capped. It must not depend on anything observed in a run.
    assert motion_prior_envelope_m(0.0) == 0.25
    assert abs(motion_prior_envelope_m(1.0) - 0.5) < 1e-12     # 0.25 + 0.5*0.5*1
    assert motion_prior_envelope_m(100.0) == MOTION_PRIOR_MAX_M


def test_envelope_clamp_holds_translation_and_attitude():
    init = np.eye(4)
    moved = _se3(np.eye(3), [1.5, 0.0, 0.0])
    out, clamped = clamp_pose_to_envelope(moved, init, 0.3, 5.0)
    assert clamped is True
    assert abs(np.linalg.norm(out[:3, 3]) - 0.3) < 1e-9
    turned = _se3(_rot("z", 20.0), [0.0, 0.0, 0.0])
    out2, clamped2 = clamp_pose_to_envelope(turned, init, 0.3, 5.0)
    assert clamped2 is True
    residual = np.degrees(np.arccos(np.clip((np.trace(out2[:3, :3]) - 1) / 2, -1, 1)))
    assert abs(residual - 5.0) < 1e-6
    # inside the envelope nothing is touched
    inside = _se3(np.eye(3), [0.05, 0.0, 0.0])
    out3, clamped3 = clamp_pose_to_envelope(inside, init, 0.3, 5.0)
    assert clamped3 is False and np.allclose(out3, inside)


def test_motion_prior_registration_cannot_leave_the_envelope():
    # The cloud sits 1 m from where the prior says it should be. The fit wants to follow it; the
    # envelope is what stops the pose from leaving what the motion model permits, and it binds
    # across both scales (each level must not spend the envelope again).
    ref = _room(n=1500)
    scan = ref + np.array([0.0, 0.0, 1.0])
    res = reregister_frame_motion_prior(scan, ref, np.eye(4), 0.2)
    assert res.displacement_from_init_m <= 0.2 + 1e-6
    assert res.envelope_clamps > 0
    assert res.envelope_m == 0.2


def test_motion_prior_registration_recovers_a_shift_inside_the_envelope():
    # With an envelope that permits it, the coarse-to-fine fit recovers the same 1 m shift the
    # frozen solver recovers -- the envelope constrains, it does not cripple.
    ref = _room(n=1500)
    scan = ref + np.array([0.0, 0.0, 1.0])
    res = reregister_frame_motion_prior(scan, ref, np.eye(4), 2.0)
    assert res.status == "CONVERGED"
    assert abs(res.displacement_from_init_m - 1.0) < 0.05
    assert res.rotation_from_init_deg < 1.0


def test_motion_prior_candidate_records_per_frame_envelopes_and_skips_frames_without_a_prior():
    ref = _room(n=1200)
    scans = {1: ref + np.array([0.0, 0.0, 0.2]),
             2: ref + np.array([0.0, 0.0, 0.2]),
             3: ref + np.array([0.0, 0.0, 0.2])}        # frame 3 has no prior pose
    priors = {1: np.eye(4), 2: np.eye(4)}
    ts = {1: 0, 2: 1_000_000_000, 3: 2_000_000_000}
    poses, results = build_motion_prior_candidate(scans, ref, priors, ts, anchor_ts_ns=0)
    assert sorted(poses) == [1, 2]
    assert [k for k, _r in results] == [1, 2]
    envelopes = {k: r.envelope_m for k, r in results}
    assert envelopes[1] == 0.25 and abs(envelopes[2] - 0.5) < 1e-12
