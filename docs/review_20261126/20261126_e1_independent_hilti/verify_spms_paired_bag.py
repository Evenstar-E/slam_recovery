"""Read back the MM-LINS source bag and check the scheduled two-arm input ledger."""
import hashlib
import io
import json
from pathlib import Path
import sys

import rosbag


bag, ledgers = map(Path, sys.argv[1:])
expected_cloud = [json.loads(line) for line in (ledgers / "producer.jsonl").read_text().splitlines()]
expected_imu = [json.loads(line) for line in (ledgers / "imu_arrival.jsonl").read_text().splitlines()]
cloud, imu = [], []
with rosbag.Bag(str(bag)) as source:
    for topic, msg, receipt in source.read_messages(topics=["/velodyne_points", "/imu_raw"]):
        stamp = msg.header.stamp.to_nsec()
        if topic == "/velodyne_points":
            cloud.append((stamp, hashlib.sha256(msg.data).hexdigest(), receipt.to_nsec()))
        else:
            packed = io.BytesIO()
            msg.serialize(packed)
            imu.append((stamp, hashlib.sha256(packed.getvalue()).hexdigest()))
assert cloud == [(row["fed_ns"], row["sha256"], row["recorded_ns"]) for row in expected_cloud]
assert imu == [(row[0], row[3]) for row in expected_imu]
print(json.dumps(dict(lidar=len(cloud), imu=len(imu), lidar_stamp_payload_and_arrival_match=True,
                      imu_stamp_and_serialized_payload_match=True), indent=2))
