#!/usr/bin/env python3
"""Keep the latest /velodyne_points cloud and republish it (shifted) on
/native_recovery/repaired_scan when <dir>/publish exists."""
import os, sys, time, rospy
from sensor_msgs.msg import PointCloud2
import numpy as np
d = sys.argv[1]
last = {"msg": None}
def cb(m): last["msg"] = m
rospy.init_node("nr_repair", anonymous=True)
rospy.Subscriber("/velodyne_points", PointCloud2, cb, queue_size=5)
pub = rospy.Publisher("/native_recovery/repaired_scan", PointCloud2, queue_size=10)
trigger = os.path.join(d, "publish")
r = rospy.Rate(50)
while not rospy.is_shutdown():
    if os.path.exists(trigger) and last["msg"] is not None:
        m = PointCloud2(); m.header = last["msg"].header; m.height = last["msg"].height
        m.width = last["msg"].width; m.fields = last["msg"].fields
        m.is_bigendian = last["msg"].is_bigendian; m.point_step = last["msg"].point_step
        m.row_step = last["msg"].row_step; m.is_dense = last["msg"].is_dense
        data = bytearray(last["msg"].data)
        # deterministic marker: shift z by +0.5 m in each point (x,y,z float32 at offsets 0,4,8)
        arr = np.frombuffer(bytes(data), dtype=np.float32)
        n = len(arr) // (m.point_step // 4)
        arr = arr.reshape(n, m.point_step // 4).copy()
        arr[:, 2] += 0.5
        m.data = arr.tobytes()
        pub.publish(m)
        print("published repaired cloud stamp=%.9f points=%d" % (m.header.stamp.to_sec(), m.width * m.height), flush=True)
        os.remove(trigger)
        time.sleep(0.5)
    r.sleep()
