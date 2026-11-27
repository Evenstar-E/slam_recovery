"""Independent stereo pairing and camera-clock qualification for stereo-inertial input."""
from bisect import bisect_right
from dataclasses import dataclass
from pathlib import Path

import cv2 as cv
import numpy as np

from .stream import InputFault, Pair


@dataclass(frozen=True)
class ImagePacket:
    side: int
    stamp: int
    path: Path


def pair_stereo(packets, max_lag_ns):
    """Pair by capture timestamp. The stream supplies an increasing arrival watermark."""
    pending = {}
    closed_through = -1
    last_exposure = [-1, -1]
    last_emitted = -1
    for arrival, packet in packets:
        if arrival < closed_through:
            raise InputFault("stereo_pairing", "arrival watermark moved backwards")
        closed_through = arrival
        if packet.side not in (0, 1) or not 0 <= arrival - packet.stamp <= max_lag_ns:
            raise InputFault("stereo_pairing", "invalid camera or capture age")
        if packet.stamp <= max(last_exposure[packet.side], last_emitted):
            raise InputFault("stereo_pairing", "duplicate or reordered camera exposure")
        last_exposure[packet.side] = packet.stamp
        slot = pending.setdefault(packet.stamp, {})
        slot[packet.side] = packet.path
        while pending:
            stamp = min(pending)
            pair = pending[stamp]
            if len(pair) != 2:
                if arrival - stamp >= max_lag_ns:
                    raise InputFault("stereo_pairing", f"missing stereo mate for {stamp}")
                break
            del pending[stamp]
            last_emitted = stamp
            yield stamp, pair[0], pair[1]
    if pending:
        raise InputFault("stereo_pairing", "stream ended with unmatched stereo exposures")


class ImuTimeline:
    """Reuse raw samples, assigning them to the corrected camera frame boundaries."""
    def __init__(self, samples):
        self.samples = tuple(samples)
        self.stamps = tuple(row[0] for row in self.samples)
        if len(self.stamps) < 2 or any(a >= b for a, b in zip(self.stamps, self.stamps[1:])):
            raise InputFault("imu", "unordered or insufficient raw IMU")
        if not np.isfinite(np.asarray([row[1:] for row in self.samples])).all():
            raise InputFault("imu", "non-finite raw IMU")
        origin = self.stamps[0]
        self.times = np.asarray([stamp-origin for stamp in self.stamps], dtype=float)/1e9
        self.gyro = np.asarray([row[4:] for row in self.samples])
        self.delta = (self.gyro[:-1] + self.gyro[1:])*0.5*np.diff(self.times)[:, None]
        self.rotations = [np.eye(3)]
        for delta in self.delta:
            self.rotations.append(self.rotations[-1] @ cv.Rodrigues(delta)[0])

    def imu_between(self, first, last):
        if not self.stamps[0] <= first < last <= self.stamps[-1]:
            raise InputFault("imu", "camera boundary outside raw IMU span")
        result = self.samples[bisect_right(self.stamps, first):bisect_right(self.stamps, last)]
        boundaries = (first, *(r[0] for r in result), last)
        if not result or max(b-a for a, b in zip(boundaries, boundaries[1:])) > 15_000_000:
            raise InputFault("imu", "missing IMU samples within corrected interval")
        return result

    def rotation_at(self, stamp):
        if stamp == self.stamps[-1]:
            return self.rotations[-1]
        if not self.stamps[0] <= stamp < self.stamps[-1]:
            raise InputFault("imu", "rotation query outside raw IMU span")
        i = bisect_right(self.stamps, stamp) - 1
        fraction = (stamp-self.stamps[i])/(self.stamps[i+1]-self.stamps[i])
        return self.rotations[i] @ cv.Rodrigues(self.delta[i]*fraction)[0]

    def camera_rotation(self, first, last, body_from_camera):
        self.imu_between(first, last)
        delta = self.rotation_at(first).T @ self.rotation_at(last)
        return body_from_camera.T @ delta.T @ body_from_camera

    def reassign(self, exposures, previous, correction_ns=0):
        for exposure in exposures:
            stamp = exposure.timestamp + correction_ns
            yield Pair(stamp, exposure.left, exposure.right, self.imu_between(previous, stamp))
            previous = stamp


def rotation_error(first, second):
    return float(np.linalg.norm(cv.Rodrigues(first @ second.T)[0]))


def qualify_offset(observations, timeline, body_from_camera):
    """Fit a constant time correction on early rotations and verify on later rotations."""
    cut = len(observations)//2
    if cut < 8:
        return {"accepted": False, "reason": "insufficient_visual_rotation"}
    shifts = np.arange(-100, 101, 5, dtype=int)*1_000_000
    scores = []
    predictions = []
    try:
        for offset in shifts:
            hypothesis = [timeline.camera_rotation(a+int(offset), b+int(offset), body_from_camera)
                          for a, b, _ in observations]
            predictions.append(hypothesis)
            errors = [rotation_error(observed, expected)
                      for (_, _, observed), expected in zip(observations, hypothesis)]
            scores.append((float(np.median(errors[:cut])), float(np.median(errors[cut:]))))
    except InputFault as error:
        return {"accepted": False, "reason": "imu_support_incomplete", "detail": str(error)}
    scores = np.asarray(scores)
    zero = len(shifts)//2
    fit = int(np.argmin(scores[:, 0]))
    check = int(np.argmin(scores[:, 1]))
    excitation = [rotation_error(first, last) for first, last in zip(predictions[0], predictions[-1])]
    excitation = tuple(float(np.median(values)) for values in (excitation[:cut], excitation[cut:]))
    reason = "qualified"
    if min(excitation) < 0.015:
        reason = "insufficient_angular_excitation"
    elif abs(shifts[fit]) < 15_000_000:
        reason = "no_resolvable_offset"
    elif fit in (0, len(shifts)-1) or abs(shifts[fit]-shifts[check]) > 10_000_000:
        reason = "disjoint_windows_disagree"
    elif np.any(scores[zero]-scores[fit] < np.maximum(0.003, .25*scores[zero])):
        reason = "no_independent_residual_improvement"
    return {
        "accepted": reason == "qualified", "reason": reason,
        "estimated_correction_ms": float(shifts[fit])/1e6,
        "heldout_best_ms": float(shifts[check])/1e6,
        "zero_residual_rad": scores[zero].tolist(), "corrected_residual_rad": scores[fit].tolist(),
        "rotation_excitation_rad": list(excitation), "fit_frames": cut,
        "verification_frames": len(observations)-cut,
    }
