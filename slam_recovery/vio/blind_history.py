"""Recover committed IMU-only history between two verified native visual states."""
import math

import cv2
import numpy as np

from .vision import angle, rotation


def camera_body(snapshot, calibration):
    pose = np.asarray(snapshot["pose_cw"])
    Rwc = rotation(pose[3:]).T
    return (Rwc @ calibration.body_from_camera.T,
            Rwc @ (calibration.camera_to_body - pose[:3]))


def world_camera(Rwb, p, calibration):
    Rcw = (Rwb @ calibration.body_from_camera).T
    camera_world = p - Rwb @ calibration.body_from_camera @ calibration.camera_to_body
    axis = cv2.Rodrigues(Rcw)[0].ravel()
    a = float(np.linalg.norm(axis))
    xyz = axis * (math.sin(a / 2) / a) if a > 1e-12 else np.zeros(3)
    return [*(-Rcw @ camera_world), *xyz, math.cos(a / 2)]


def recover_history(anchor, anchor_pair, pending, endpoint, calibration):
    """Use the original IMU with checkpoint bias, then close on the first verified view."""
    start, stop = anchor["timestamp"], endpoint["timestamp"]
    frames = [(pair, weak) for pair, _, weak in pending if pair.timestamp <= stop]
    if not anchor_pair.imu or not frames or frames[-1][0].timestamp != stop or stop <= start:
        return [], {"accepted": False, "reason": "missing_inertial_support"}
    R, p = camera_body(anchor, calibration)
    R_end, p_end = camera_body(endpoint, calibration)
    state = np.asarray(anchor["inertial"])
    v, ba, bg = state[:3].copy(), state[3:6], state[6:9]
    last = start
    held = np.asarray(anchor_pair.imu[-1][1:])
    gravity = np.array([0.0, 0.0, -9.81])
    history = []

    def advance(stamp):
        nonlocal R, p, v, last
        dt = (stamp - last) / 1e9
        delta = (held[3:] - bg) * dt
        acceleration = R @ cv2.Rodrigues(delta / 2)[0] @ (held[:3] - ba) + gravity
        p = p + dt * v + 0.5 * dt**2 * acceleration
        v = v + dt * acceleration
        R = R @ cv2.Rodrigues(delta)[0]
        last = stamp

    for pair, weak in frames:
        for stamp, *measurement in pair.imu:
            advance(stamp)
            held = np.asarray(measurement)
        advance(pair.timestamp)
        if weak:
            history.append((pair.timestamp, R.copy(), p.copy()))

    dp = p_end - p
    dR = R_end @ R.T
    orientation = angle(dR)
    position = float(np.linalg.norm(dp))
    report = {"endpoint_position_residual_m": position,
              "endpoint_orientation_residual_rad": orientation,
              "blind_frames": len(history),
              "accepted": bool(np.isfinite(dp).all() and position <= 0.20 and orientation <= 0.0873)}
    if not report["accepted"]:
        return [], report
    tangent = cv2.Rodrigues(dR)[0]
    result = []
    for stamp, attitude, position_world in history:
        u = (stamp - start) / (stop - start)
        correction = u*u*(3 - 2*u)
        pose = world_camera(cv2.Rodrigues(tangent * correction)[0] @ attitude,
                            position_world + correction * dp, calibration)
        result.append({"timestamp": stamp, "pose_cw": pose, "map_id": anchor["map_id"],
                       "provenance": "bias_corrected_imu_with_verified_visual_endpoints"})
    return result, report
