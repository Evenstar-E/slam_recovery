"""Apply the archived near-field occlusion to the preregistered revisit candidate."""
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import rosbag

from slam_recovery.experiments.injection.injectors import inject_plastic_bag_near_field_occlusion


base = Path(__file__).resolve().parent
source = Path("/home/tong/slam_recovery_step3_runs/hilti_surface_qualification_20261125/EXP18_CLEAN_SMOKE.bag")
output = Path(sys.argv[1])
topic = "/hilti_surface/hesai_adapted"
if output.exists():
    raise FileExistsError(output)
geometry = np.load(base / "hilti_geometry_scored/clean_ray_endpoints.npz")
origin = int(geometry["scan_ns"][0])
begin, end = origin + 6_000_000_000, origin + 12_000_000_000
layout = np.dtype([("x","<f4"), ("y","<f4"), ("z","<f4"), ("intensity","<f4"),
                   ("time","<f4"), ("ring","<u2")])
index = 0
affected = []
scans = 0
imu = 0
with rosbag.Bag(str(source)) as original, rosbag.Bag(str(output), "w", compression="lz4") as trial:
    for name, msg, receipt in original.read_messages(topics=[topic, "/alphasense/imu"]):
        ns = msg.header.stamp.to_nsec()
        if name == topic:
            scans += 1
        else:
            imu += 1
        if name == topic and begin <= ns < end:
            assert msg.point_step == layout.itemsize and msg.height == 1
            points = np.frombuffer(msg.data, dtype=layout).copy()
            xyz = np.column_stack([points[key] for key in ("x","y","z","intensity")])
            valid = np.isfinite(xyz).all(axis=1) & (np.linalg.norm(xyz[:, :3], axis=1) > 0)
            index += 1
            cloudy, mask = inject_plastic_bag_near_field_occlusion(
                xyz[valid], .88, 4.30, .01, 42000 + index)
            selected = np.flatnonzero(valid)[mask]
            for axis, name_field in enumerate(("x","y","z","intensity")):
                points[name_field][selected] = cloudy[mask, axis]
            msg.data = points.tobytes()
            affected.append(dict(scan_ns=ns, altered_points=len(selected),
                                 payload_sha256=hashlib.sha256(msg.data).hexdigest()))
        trial.write(name, msg, receipt)
print(json.dumps(dict(
    origin_ns=origin, fault_start_ns=begin, fault_end_ns=end, scans=scans, imu=imu,
    occlusion=dict(fraction=.88, screen_m=4.30, noise_m=.01, seed_base=42000),
    faults=affected), indent=2))
