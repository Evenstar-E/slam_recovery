"""Preserve the fixed SPMS clip's raw messages and original arrival times."""
import hashlib
import json
from pathlib import Path

import rosbag
import rospy

ROOT = Path(__file__).resolve().parent / "spms_02"
lidar, imu = "/os1_cloud_node1/points", "/imu/imu"
source = ROOT / "spms_02.bag"
target = ROOT / "spms_02_26_65.bag"
ns = 1_000_000_000


def digest(path):
    sha = hashlib.sha256()
    with path.open("rb") as f:
        while block := f.read(1024 * 1024):
            sha.update(block)
    return sha.hexdigest()


with rosbag.Bag(str(source)) as bag:
    origin = min(next(bag.read_messages(topics=[topic])).message.header.stamp.to_nsec()
                 for topic in (lidar, imu))
    with rosbag.Bag(str(target) + ".partial", "w", compression="lz4") as out:
        counts = {lidar: 0, imu: 0}
        for topic, msg, stamp in bag.read_messages(
                topics=[lidar, imu], start_time=rospy.Time.from_sec((origin + 26 * ns) / ns),
                end_time=rospy.Time.from_sec((origin + 65 * ns) / ns)):
            out.write(topic, msg, stamp)
            counts[topic] += 1
Path(str(target) + ".partial").rename(target)
(ROOT / "CLIP.json").write_text(json.dumps(dict(
    origin_ns=origin, read_s=[26, 65], lidar_feed_s=[27, 64],
    topics=counts, clipped_bag_sha256=digest(target), original_bag_sha256=[
        line.split()[0] for line in (ROOT / "VERIFIED.sha256").read_text().splitlines()
        if line.endswith("  spms_02.bag")][0]),
    indent=2) + "\n")
