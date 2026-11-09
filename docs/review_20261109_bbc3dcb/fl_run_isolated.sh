#!/bin/bash
# FAST-LIVO2 replay on an isolated ROS master.
# Same node/config/rate as the archived run (/tmp/fl_record.sh, /tmp/run43.sh) but it never
# touches a global rosmaster and only kills its own PIDs, so a concurrent session's ROS graph
# is left alone.
set -eo pipefail
BAG="$1"; OUT="$2"; RATE="${3:-0.5}"; DRAIN="${4:-150}"

source /home/R26534/mm/ros/setup.bash
source /home/R26534/fast_livo2_ws/devel/setup.bash
export ROS_HOME=/tmp/ros_home_c3_$(date +%s)
mkdir -p "$ROS_HOME"
PORT=$(python3 -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1]);s.close()')
export ROS_MASTER_URI="http://127.0.0.1:$PORT"
export ROS_HOSTNAME=127.0.0.1
echo "master=$ROS_MASTER_URI bag=$BAG out=$OUT rate=$RATE drain=$DRAIN"

roscore -p "$PORT" > /tmp/c3_roscore.log 2>&1 &
RC=$!
for i in $(seq 1 60); do rosnode list >/dev/null 2>&1 && break; sleep 1; done

rosparam load /home/R26534/FAST-LIVO2/config/m2dgr.yaml /
rosparam load /home/R26534/FAST-LIVO2/config/camera_m2dgr.yaml /laserMapping

rm -f "$OUT"
rosbag record -O "$OUT" /aft_mapped_to_init > /tmp/c3_record.log 2>&1 &
REC=$!
sleep 2
rosrun fast_livo fastlivo_mapping > /tmp/c3_node.log 2>&1 &
NODE=$!
sleep 3

rosbag play "$BAG" -r "$RATE" > /tmp/c3_play.log 2>&1
echo "play done, draining ${DRAIN}s"
sleep "$DRAIN"

kill -INT "$REC" 2>/dev/null || true
for i in $(seq 1 30); do kill -0 "$REC" 2>/dev/null || break; sleep 1; done
sleep 2
kill -9 "$NODE" 2>/dev/null || true
kill -9 "$RC" 2>/dev/null || true
echo "bag bytes $(stat -c %s "$OUT" 2>/dev/null || echo 0)"
