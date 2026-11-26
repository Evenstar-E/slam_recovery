"""Independent stereo reprojection gate and causal observation checks."""
import math

import cv2 as cv
import numpy as np


def rotation(quaternion):
    x, y, z, w = np.array(quaternion) / np.linalg.norm(quaternion)
    return np.array([
        [1 - 2*(y*y + z*z), 2*(x*y - z*w), 2*(x*z + y*w)],
        [2*(x*y + z*w), 1 - 2*(x*x + z*z), 2*(y*z - x*w)],
        [2*(x*z - y*w), 2*(y*z + x*w), 1 - 2*(x*x + y*y)],
    ])


def angle(matrix):
    return math.acos(float(np.clip((np.trace(matrix) - 1) / 2, -1, 1)))


def relative(before, after):
    first, second = (np.asarray(x["pose_cw"]) for x in (before, after))
    delta = rotation(second[3:]) @ rotation(first[3:]).T
    return delta, second[:3] - delta @ first[:3]


def healthy(snapshot):
    return (snapshot["tracking"] == 2 and snapshot["imu_initialized"]
            and snapshot["inliers"] >= 20 and snapshot["occupied_cells"] >= 4
            and snapshot["reprojection_px"] is not None
            and snapshot["reprojection_px"] <= 3.0)


def input_support(images):
    detect = cv.FastFeatureDetector_create(threshold=15)
    return tuple(len(detect.detect(image)) for image in images)


def gauge_from(saved, replayed):
    """Rigid, unit-scale transform from public world to the private worker world."""
    public, private = (np.asarray(row["pose_cw"]) for row in (saved, replayed))
    private_inv = rotation(private[3:]).T
    return private_inv @ rotation(public[3:]), private_inv @ (public[:3] - private[:3])


def in_public_world(snapshot, gauge):
    if gauge is None:
        return snapshot
    world_rotation, world_translation = gauge
    pose = np.asarray(snapshot["pose_cw"])
    Rcw = rotation(pose[3:])
    axis = cv.Rodrigues(Rcw @ world_rotation)[0].ravel()
    magnitude = float(np.linalg.norm(axis))
    q = [0.0, 0.0, 0.0, 1.0]
    if magnitude > 1e-10:
        q = [*(axis * (math.sin(magnitude / 2) / magnitude)), math.cos(magnitude / 2)]
    state = snapshot["inertial"]
    if state is not None:
        state = [*(world_rotation.T @ state[:3]), *state[3:]]
    return dict(snapshot, pose_cw=[*(pose[:3] + Rcw @ world_translation), *q],
                inertial=state)


def qualify_replay(public, private, event_log, record_type, **context):
    # Fit the gauge to one earlier shared frame. The actual checkpoint and all later
    # prefix frames are held out. This also catches frame-varying drift and scale.
    before = list(public.recent)
    after = list(private.recent)
    if len(before) < 12 or len(before) != len(after):
        event_log.emit(record_type, qualified=False, reason="insufficient_prefix_overlap", **context)
        return False
    same_map = all(
        old["timestamp"] == new["timestamp"]
        and old["map_id"] == before[-1]["map_id"]
        and new["map_id"] == after[-1]["map_id"]
        and old["maps"] == before[-1]["maps"]
        and new["maps"] == after[-1]["maps"]
        for old, new in zip(before, after)
    )
    if not same_map or not healthy(before[0]) or not healthy(after[0]):
        event_log.emit(record_type, qualified=False, reason="prefix_map_or_tracking_changed", **context)
        return False
    raw_checkpoint = replay_delta(before[-1], after[-1])
    gauge = gauge_from(before[0], after[0])
    checks = [replay_delta(old, in_public_world(new, gauge))
              for old, new in zip(before[1:], after[1:])]
    qualified = all(check["qualified"] for check in checks)
    event_log.emit(record_type, **context, qualified=qualified,
                   gauge_anchor=before[0]["timestamp"], checkpoint=checks[-1],
                   raw_checkpoint=raw_checkpoint, verified_prefix_pairs=len(checks),
                   failed_prefix_pairs=[dict(row, timestamp=state["timestamp"])
                                        for state, row in zip(before[1:], checks)
                                        if not row["qualified"]])
    private.gauge = gauge
    private.recent.clear()
    private.recent.extend(in_public_world(row, gauge) for row in after)
    private.snapshot = private.recent[-1]
    return qualified


def replay_delta(saved, replayed):
    if not saved["inertial"] or not replayed["inertial"]:
        return {"qualified": False, "reason": "missing_native_inertial_state"}
    rot, shift = relative(saved, replayed)
    old = np.array(saved["inertial"])
    new = np.array(replayed["inertial"])
    result = {
        "position_m": float(np.linalg.norm(shift)),
        "orientation_rad": angle(rot),
        "velocity_mps": float(np.linalg.norm(old[:3] - new[:3])),
        "accel_bias_delta": float(np.linalg.norm(old[3:6] - new[3:6])),
        "gyro_bias_delta": float(np.linalg.norm(old[6:9] - new[6:9])),
        "preintegration_dt_delta_s": abs(float(old[9] - new[9])),
        "preintegration_position_delta_m": float(np.linalg.norm(old[10:13] - new[10:13])),
        "preintegration_velocity_delta_mps": float(np.linalg.norm(old[13:16] - new[13:16])),
        "preintegration_rotation_delta_rad": angle(
            rotation(old[16:20]) @ rotation(new[16:20]).T),
        "keyframe_count_delta": abs(saved["keyframes"] - replayed["keyframes"]),
    }
    limits = (0.05, 0.05, 0.15, 0.15, 0.025, 1e-5, 0.02, 0.04, 0.02,
              max(2, saved["keyframes"] * 0.05))
    result["qualified"] = (
        saved["timestamp"] == replayed["timestamp"] and healthy(saved) and healthy(replayed)
        and saved["map_id"] == replayed["map_id"] and saved["maps"] == replayed["maps"]
        and all(value <= limit for value, limit in zip(result.values(), limits))
    )
    return result


class HeldOutStereo:
    def __init__(self, settings):
        config = cv.FileStorage(str(settings), cv.FILE_STORAGE_READ)
        def number(key):
            return config.getNode(key).real()

        cameras = []
        for prefix in ("Camera1.", "Camera2."):
            fx, fy, cx, cy = (number(prefix + field) for field in ("fx", "fy", "cx", "cy"))
            K = np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1.0]])
            distortion = np.array([number(prefix + field) for field in ("k1", "k2", "p1", "p2")])
            cameras.append((K, distortion))
        size = (int(number("Camera.width")), int(number("Camera.height")))
        left_to_right = np.linalg.inv(config.getNode("Stereo.T_c1_c2").mat()).astype(float)
        body_from_camera = config.getNode("IMU.T_b_c1").mat().astype(float)
        config.release()
        R0, R1, P0, P1, *_ = cv.stereoRectify(
            *cameras[0], *cameras[1], size, left_to_right[:3, :3], left_to_right[:3, 3],
            flags=cv.CALIB_ZERO_DISPARITY, alpha=-1,
        )
        self.calibration = list(zip(cameras, (R0, R1), (P0, P1)))
        self.body_from_camera = body_from_camera[:3, :3] @ R0.T
        self.camera_to_body = -self.body_from_camera.T @ body_from_camera[:3, 3]
        self.intrinsics = P0[:, :3]
        self.detector = cv.ORB_create(nfeatures=800, edgeThreshold=20)
        self.matcher = cv.BFMatcher(cv.NORM_HAMMING)

    def imu_residual(self, previous, current):
        if previous is None or current["inertial"] is None or previous["map_id"] != current["map_id"]:
            return None
        observed, _ = relative(previous, current)
        Rbc = self.body_from_camera
        prediction = Rbc.T @ rotation(current["inertial"][16:20]).T @ Rbc
        return angle(observed @ prediction.T)

    def features(self, image, camera):
        mask = np.zeros_like(image)
        mask[16:image.shape[0] // 3 - 24] = 255
        keys, descriptors = self.detector.detectAndCompute(image, mask)
        if descriptors is None:
            return np.empty((0, 2)), None
        (intrinsics, distortion), rectification, projection = self.calibration[camera]
        points = np.float32([key.pt for key in keys]).reshape(-1, 1, 2)
        rectified = cv.undistortPoints(points, intrinsics, distortion,
                                       R=rectification, P=projection).reshape(-1, 2)
        return rectified, descriptors

    def matches(self, before, after):
        if before is None or after is None or len(after) < 2:
            return {}
        neighbours = self.matcher.knnMatch(before, after, k=2)
        best = sorted((a for a, b in neighbours if a.distance < 0.75 * b.distance),
                      key=lambda pair: pair.distance)
        unique = {}
        used = set()
        for match in best:
            if match.trainIdx not in used:
                used.add(match.trainIdx)
                unique[match.queryIdx] = match.trainIdx
        return unique

    def validate(self, anchor_images, current_images, saved, candidate):
        left, dl = self.features(anchor_images[0], 0)
        right, dr = self.features(anchor_images[1], 1)
        later, dn = self.features(current_images[0], 0)
        stereo = self.matches(dl, dr)
        temporal = self.matches(dl, dn)
        triples = [(left[i], right[j], later[temporal[i]]) for i, j in stereo.items()
                   if i in temporal and abs(left[i][1] - right[j][1]) < 2.0
                   and left[i][0] - right[j][0] > 2.0]
        if len(triples) < 12:
            return {"passed": False, "reason": "insufficient_reserved_matches",
                    "matches": len(triples)}
        first, second, current = (np.asarray(column) for column in zip(*triples))
        _, _, p0 = self.calibration[0]
        _, _, p1 = self.calibration[1]
        homogeneous = cv.triangulatePoints(p0, p1, first.T, second.T).T
        xyz = homogeneous[:, :3] / homogeneous[:, 3, None]
        valid = np.isfinite(xyz).all(axis=1) & (xyz[:, 2] > 0) & (xyz[:, 2] < 30)
        xyz, current = xyz[valid], current[valid]
        if len(xyz) < 12:
            return {"passed": False, "reason": "insufficient_reserved_depth", "matches": len(xyz)}
        success, rvec, trans, inliers = cv.solvePnPRansac(
            xyz, current, self.intrinsics, None, iterationsCount=100,
            reprojectionError=2.5, confidence=0.99, flags=cv.SOLVEPNP_EPNP,
        )
        if not success or inliers is None or len(inliers) < 12:
            return {"passed": False, "reason": "insufficient_pnp_inliers", "matches": len(xyz)}
        fitted, shift = relative(saved, candidate)
        inliers = inliers.ravel()
        projected, _ = cv.projectPoints(xyz[inliers], cv.Rodrigues(fitted)[0],
                                        shift, self.intrinsics, None)
        errors = np.linalg.norm(projected.reshape(-1, 2) - current[inliers], axis=1)
        median = float(np.median(errors))
        translation = float(np.linalg.norm(shift - trans.ravel()))
        orientation = angle(fitted @ cv.Rodrigues(rvec)[0].T)
        return {"passed": (median <= 4.0 and translation <= 0.20 and orientation <= 0.0873),
                "matches": len(xyz), "inliers": len(inliers), "reprojection_px": median,
                "position_disagreement_m": translation, "orientation_disagreement_rad": orientation}
