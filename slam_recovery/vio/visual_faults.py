"""Regional stereo evidence and disjoint fit/verification image regions."""
from dataclasses import dataclass

import cv2 as cv
import numpy as np


GRID = 3
CELLS = GRID * GRID


def region_mask(shape, selected, margin=0):
    mask = np.zeros(shape, dtype=np.uint8)
    h, w = shape
    for cell in selected:
        y, x = divmod(cell, GRID)
        mask[y*h//GRID+margin:(y+1)*h//GRID-margin,
             x*w//GRID+margin:(x+1)*w//GRID-margin] = 255
    return mask


def cells_for(shape, points):
    h, w = shape
    return np.clip((points[:, 1]*GRID/h).astype(int), 0, GRID-1)*GRID + np.clip(
        (points[:, 0]*GRID/w).astype(int), 0, GRID-1)


def textured_cover(images, selected):
    """Inject static textured near-field clutter in both images. Timestamps and IMU stay fixed."""
    result = []
    for image in images:
        mask = region_mask(image.shape, selected)
        y, x = np.ogrid[:image.shape[0], :image.shape[1]]
        pattern = np.where(((y//11 + x//13) % 2) == 0, 28, 226).astype(np.uint8)
        covered = image.copy()
        covered[mask != 0] = pattern[mask != 0]
        result.append(covered)
    return tuple(result)


@dataclass(frozen=True)
class RegionPlan:
    bad: tuple
    held: tuple

    def mask(self, images):
        result = []
        for image in images:
            omitted = region_mask(image.shape, self.bad + self.held)
            result.append(np.where(omitted != 0, 0, image).astype(np.uint8))
        return tuple(result)


class StereoEvidence:
    """Geometry from immutable images. Labels and injected regions are never inputs."""
    def __init__(self, vision):
        self.vision = vision
        self.detector = cv.ORB_create(nfeatures=1000, edgeThreshold=19)

    def extract(self, image, camera):
        keypoints, descriptors = self.detector.detectAndCompute(image, None)
        if descriptors is None:
            return np.empty((0, 2), dtype=np.float32), None, np.empty(0, dtype=int)
        raw = np.float32([key.pt for key in keypoints])
        (intrinsics, distortion), rectification, projection = self.vision.calibration[camera]
        rect = cv.undistortPoints(raw[:, None, :], intrinsics, distortion,
                                  R=rectification, P=projection).reshape(-1, 2)
        return rect, descriptors, cells_for(image.shape, raw)

    def stereo(self, left, right):
        a, da, cells = left
        b, db, _ = right
        links = self.vision.matches(da, db)
        pairs = [(i, j) for i, j in links.items()
                 if abs(a[i, 1] - b[j, 1]) < 2 and a[i, 0] - b[j, 0] > 2]
        if not pairs:
            return np.empty(0, dtype=int), np.empty((0, 3))
        i, j = np.asarray(pairs).T
        P0 = self.vision.calibration[0][2]
        P1 = self.vision.calibration[1][2]
        h = cv.triangulatePoints(P0, P1, a[i].T, b[j].T).T
        with np.errstate(divide="ignore", invalid="ignore"):
            xyz = h[:, :3]/h[:, 3, None]
        valid = np.isfinite(xyz).all(axis=1) & (xyz[:, 2] > 0) & (xyz[:, 2] < 30)
        return i[valid], xyz[valid]

    def prepare(self, images):
        left = self.extract(images[0], 0)
        right = self.extract(images[1], 1)
        ids, xyz = self.stereo(left, right)
        return left, ids, xyz

    def compare(self, anchor, current, *, refine=False):
        left, ids, xyz = anchor
        later, new_ids, _ = current
        _, before_descriptors, before_cells = left
        after, after_descriptors, after_cells = later
        links = self.vision.matches(before_descriptors, after_descriptors)
        matched = [(index, links[i]) for index, i in enumerate(ids) if i in links]
        if len(matched) < 12:
            return None
        i, j = np.asarray(matched).T
        ok, rotation, shift, indices = cv.solvePnPRansac(
            xyz[i], after[j], self.vision.intrinsics, None, iterationsCount=80,
            reprojectionError=2.5, flags=cv.SOLVEPNP_EPNP)
        if not ok or indices is None or len(indices) < 12:
            return None
        accepted = indices.ravel()
        if refine:
            rotation, shift = cv.solvePnPRefineLM(xyz[i[accepted]], after[j[accepted]],
                                                   self.vision.intrinsics, None, rotation, shift)
        observed_cells = before_cells[ids[i[accepted]]]
        return {
            "rotation": cv.Rodrigues(rotation)[0], "shift": shift.ravel(),
            "before_stereo": np.bincount(before_cells[ids], minlength=CELLS),
            "after_stereo": np.bincount(after_cells[new_ids], minlength=CELLS),
            "inliers_by_cell": np.bincount(observed_cells, minlength=CELLS),
            "inliers": len(accepted),
        }

    def reserve(self, anchor_images, current_images):
        """Freeze disjoint tiles using raw correspondences before fitting a pose."""
        left, ids, _ = self.prepare(anchor_images)
        current = self.extract(current_images[0], 0)
        links = self.vision.matches(left[1], current[1])
        persistent_cells = [left[2][index] for index in ids if index in links]
        counts = np.bincount(persistent_cells, minlength=CELLS)
        ranking = sorted(range(CELLS), key=lambda cell: (-counts[cell], cell))
        return RegionPlan((), tuple(ranking[1:8:2])), counts.tolist()

    def diagnose(self, first, second):
        obs = self.compare(first, second)
        if obs is None:
            return None, None
        ref = obs["before_stereo"]
        tracked = obs["inliers_by_cell"]
        stereo = obs["after_stereo"]
        # Confine the diagnosis to a regional drop while other cells still support a rigid motion.
        stable = np.flatnonzero((tracked >= 6) & (tracked >= .30*ref))
        bad = tuple(map(int, np.flatnonzero((ref >= 8) & (tracked <= .20*ref) & (stereo <= .35*ref))))
        if not bad or len(stable) < 3 or tracked[stable].sum() < 24:
            return None, obs
        ranking = sorted(stable, key=lambda cell: (-tracked[cell], cell))
        held = tuple(int(cell) for cell in ranking[1::2])
        if tracked[list(held)].sum() < 12:
            return None, obs
        return RegionPlan(bad, held), obs
