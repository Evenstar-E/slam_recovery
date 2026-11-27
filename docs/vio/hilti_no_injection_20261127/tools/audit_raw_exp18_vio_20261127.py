import json
from pathlib import Path

import cv2
import numpy as np
import rosbag
import rospy

base = Path.home() / "vio_matrix_evidence_20261127"
source = Path.home() / "datasets/hilti2022_surface_20261125/exp18_corridor_lower_gallery_2.bag"
obs = json.loads((base / "exp18/receipts/exp18-isolation-observations.json").read_text())
shift_ns = json.loads((base / "config/calibration.json").read_text())["camera_to_imu_shift_ns"]
targets = {row["timestamp"] - shift_ns for event in obs.values() for row in event["observations"]}
def stamp(value):
    return rospy.Time(value // 10**9, value % 10**9)

cam = ["/alphasense/cam1/image_raw", "/alphasense/cam0/image_raw"]
fast = cv2.FastFeatureDetector_create(threshold=15)
seen = {}
with rosbag.Bag(str(source)) as reader:
    for topic, msg, received in reader.read_messages(cam, start_time=stamp(min(targets)-10**9),
                                                     end_time=stamp(max(targets)+10**9)):
        timestamp = msg.header.stamp.to_nsec()
        if timestamp in targets:
            im = np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.height,msg.step)[:,:msg.width]
            seen.setdefault(timestamp + shift_ns, {})[cam.index(topic)] = {
                "count": len(fast.detect(im)), "mean_gray": float(im.mean()),
                "std_gray": float(im.std())}
missing = [t+shift_ns for t in sorted(targets) if len(seen.get(t+shift_ns,{})) != 2]
for event, data in obs.items():
    for row in data["observations"]:
        row["unrectified"] = seen.get(row["timestamp"], {})
out = {"samples_without_both_raw_cameras": missing, "observations": obs, "raw_read_only": str(source)}
(base / "EXP18_RAW_EVENT_OBSERVATIONS.json").write_text(json.dumps(out, indent=2))
for event, data in obs.items():
    print(event, data["runs"], [(round(row["relative_ms"],2), [cam["fast_count"] for cam in row["cams"]],
                                  [cam["count"] for cam in row["unrectified"].values()])
                                 for row in data["observations"]])
