"""Qualify overlap and propose scoring rays without opening any tested map output."""
import json
from pathlib import Path
import sys

import numpy as np
import rosbag
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation, Slerp
from sensor_msgs import point_cloud2
import yaml

HOME = Path("/home/tong")
ASSETS = HOME / "datasets/hilti2022_surface_20261125"
ADAPTED = HOME / "slam_recovery_step3_runs/hilti_surface_qualification_20261125/EXP18_CLEAN_SMOKE.bag"
VOXEL = .10
TOLERANCE = .15
NS = 1_000_000_000


def extract_clean_clouds():
    truth = np.loadtxt(ASSETS / "exp18_corridor_lower_gallery_2_imu.txt")
    origin = float(truth[0, 0])
    ts = truth[:, 0] - origin
    if np.any(np.diff(ts) <= 0):
        raise ValueError("official pose stamps are not increasing")
    interpolate_rotation = Slerp(ts, Rotation.from_quat(truth[:, 4:8]))
    link = yaml.safe_load((ASSETS / "lidar_calibration.yaml").read_text())[
        "sensors"]["PandarXT-32"]["extrinsics"]
    rotation = Rotation.from_quat(link["quaternion"])
    translation = np.array(link["translation"])
    clouds = []
    with rosbag.Bag(str(ADAPTED)) as bag:
        messages = bag.read_messages(topics=["/hilti_surface/hesai_adapted"])
        for index, (_, msg, _) in enumerate(messages):
            if index % 5:
                continue
            stamp = msg.header.stamp.to_nsec()
            data = np.array(list(point_cloud2.read_points(msg, field_names=("x", "y", "z", "time"),
                                                         skip_nans=True)))[::20]
            if len(data) == 0:
                continue
            point_t = (stamp / NS - origin) + data[:, 3] * 1e-6
            valid = (point_t >= ts[0]) & (point_t <= ts[-1])
            distances = np.linalg.norm(data[:, :3], axis=1)
            valid &= (distances >= .4) & (distances <= 30)
            if valid.sum() < 300:
                continue
            point_t = point_t[valid]
            attitude = interpolate_rotation(point_t)
            xyz = np.column_stack([np.interp(point_t, ts, truth[:, axis]) for axis in range(1, 4)])
            sensor = xyz + attitude.apply(translation)
            points = xyz + attitude.apply(rotation.apply(data[valid, :3]) + translation)
            clouds.append((stamp, sensor, points))
    return clouds


def voxel_count(points):
    return np.unique(np.floor(points / VOXEL).astype(np.int64), axis=0).shape[0]


def main(out):
    out.mkdir(exist_ok=False)
    clouds = extract_clean_clouds()
    stamps = np.array([stamp for stamp, _, _ in clouds], dtype=np.int64)
    elapsed = (stamps - stamps[0]) / NS
    plans = []
    for start in range(6, 15):
        prior = [c for c, t in zip(clouds, elapsed) if start - 6 <= t < start]
        suffix = [c for c, t in zip(clouds, elapsed) if start + 6 <= t < start + 8]
        if len(prior) < 8 or len(suffix) < 3:
            continue
        position_prior = cKDTree(np.array([sensor.mean(axis=0) for _, sensor, _ in prior]))
        physical = position_prior.query(np.array([sensor.mean(axis=0)
                                                 for _, sensor, _ in suffix]))[0]
        prior_geometry = cKDTree(np.vstack([xyz for _, _, xyz in prior]))
        probes = []
        for stamp, _, xyz in suffix:
            neighbors = prior_geometry.query(xyz)[0]
            probes.append(dict(stamp_ns=stamp, matched=int((neighbors <= TOLERANCE).sum()),
                               samples=len(neighbors)))
        ratios = np.array([p["matched"] / p["samples"] for p in probes])
        kind = "unqualified"
        if (physical >= 1.0).all() and not ratios.any():
            kind = "no_verified_overlap"
        elif (physical >= 1.0).all() and (ratios >= .05).all() and (ratios <= .80).all():
            kind = "no_revisit_partial_overlap"
        elif (physical <= .50).any() and (ratios >= .05).any():
            kind = "revisit_candidate"
        plans.append(dict(occlusion_candidate_from_s=start, prefix_s=[start - 6, start],
                          fault_s=[start, start + 6], suffix_s=[start + 6, start + 8],
                          physical_nearest_prefix_m=physical.tolist(), suffix=probes, status=kind))
    hit_cloud = np.vstack([xyz for _, _, xyz in clouds])
    # Proposal only. Candidate free points must still pass the predeclared
    # TLS surface match and blind visibility-mask construction.
    free_candidates = []
    for _, sensor, xyz in clouds:
        distance = np.linalg.norm(xyz - sensor, axis=1)
        for fraction in (.25, .50, .75):
            keep = (1 - fraction) * distance > TOLERANCE
            free_candidates.append(sensor[keep] + fraction * (xyz[keep] - sensor[keep]))
    free_points = np.vstack(free_candidates)
    np.savez_compressed(out / "clean_ray_endpoints.npz", xyz=hit_cloud,
                        sensor_xyz=np.vstack([sensor for _, sensor, _ in clouds]),
                        scan_ns=stamps, scan_counts=np.array([len(p) for _, _, p in clouds]))
    (out / "QUALIFICATION.json").write_text(json.dumps(dict(
        pose_source="official TLS-aligned development poses, scoring only",
        point_clock="adapted scan start plus per-point relative microseconds",
        fixed_rules=dict(grid_m=VOXEL, support_m=TOLERANCE, retest_after_s=6,
                         true_revisit_below_m=.50, no_revisit_at_least_m=1.,
                         partial_support=[.05, .80], requires_three_suffix_scans=True),
        scan_count=len(stamps), samples=len(hit_cloud), surface_voxel_candidates=voxel_count(hit_cloud),
        empty_voxel_candidates=voxel_count(free_points),
        empty_status="unqualified: TLS first-hit agreement and visibility exclusion not applied",
        loop_status="qualification only; requires upstream observed map merge",
        routes=plans), indent=2) + "\n")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
