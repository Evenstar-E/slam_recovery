"""Build the exact same fault stream for the uninstrumented upstream ROS subscriber."""
import json
from pathlib import Path
import sys

import rosbag

from stream_1x import NS, definition, read_clouds, frozen


out = Path(sys.argv[1])
if out.exists():
    raise FileExistsError(out)
bag_path, lidar, imu, origin, windows, _ = definition("spms_fault")
lo, hi = (frozen.time_to_ros(origin + offset * NS) for offset in (26, 65))
with rosbag.Bag(str(bag_path)) as raw:
    cloud = list(read_clouds(raw, lidar, lo, hi, origin, windows))
    inertial = [(msg, stamp.to_nsec()) for _, msg, stamp in
                raw.read_messages(topics=[imu], start_time=lo, end_time=hi)]
archive = Path(__file__).resolve().parent
expected = [json.loads(line) for line in
            (archive / "spms_fault_native_ingress/producer.jsonl").read_text().splitlines()]
keys = ("stamp_ns", "fed_ns", "event", "sha256")
assert [tuple(row[k] for k in keys) for _, _, row in cloud] == [
    tuple(row[k] for k in keys) for row in expected]
events = [(stamp, "/velodyne_points", msg) for msg, stamp, _ in cloud]
events.extend((stamp, "/imu_raw", msg) for msg, stamp in inertial)
events.sort(key=lambda row: row[0])
with rosbag.Bag(str(out), "w", compression="lz4") as bag:
    for stamp, topic, msg in events:
        bag.write(topic, msg, frozen.time_to_ros(stamp))
print(json.dumps(dict(lidar=len(cloud), imu=len(inertial), windows=windows,
                      identical_native_input_identity=True), indent=2))
