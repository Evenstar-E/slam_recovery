#!/bin/bash
set +u
source /home/R26534/mm/ros/setup.bash >/dev/null 2>&1
source /home/R26534/fast_livo2_ws/devel/setup.bash >/dev/null 2>&1
set -u
TAG="${1:?tag}"
OUT="/tmp/wt-sim/docs/review_20261112_four_host/host_change_trace_cov/probe_${TAG}"
rm -rf "$OUT"; mkdir -p "$OUT"
PORT=$((58900 + RANDOM % 100))
export ROS_HOME="$OUT/ros_home"; mkdir -p "$ROS_HOME"
export ROS_MASTER_URI="http://localhost:$PORT"
{ sha256sum /home/R26534/fast_livo2_ws/devel/lib/liblaser_mapping.so; sha256sum /home/R26534/fast_livo2_ws/devel/lib/fast_livo/fastlivo_mapping; } > "$OUT/env_and_sha.txt"
setsid roscore -p $PORT > "$OUT/roscore.log" 2>&1 &
RCPID=$!
for i in $(seq 1 30); do rosnode list >/dev/null 2>&1 && break; sleep 1; done
rosparam load /home/R26534/FAST-LIVO2/config/m2dgr.yaml / >/dev/null 2>&1
rosparam load /home/R26534/FAST-LIVO2/config/camera_m2dgr.yaml /laserMapping >/dev/null 2>&1
env -i PATH="$PATH" HOME="$HOME" ROS_MASTER_URI="$ROS_MASTER_URI" ROS_HOME="$ROS_HOME" \
  ROS_PACKAGE_PATH="$ROS_PACKAGE_PATH" LD_LIBRARY_PATH="${LD_LIBRARY_PATH:-}" PYTHONPATH="${PYTHONPATH:-}" \
  /home/R26534/fast_livo2_ws/devel/lib/fast_livo/fastlivo_mapping > "$OUT/host.log" 2>&1 &
HOSTPID=$!
ALIVE=0
for i in $(seq 1 20); do
  ST=$(ps -o stat= -p $HOSTPID 2>/dev/null | tr -d ' ')
  if [ -n "$ST" ] && [ "${ST:0:1}" != "Z" ]; then ALIVE=$((ALIVE+1)); else break; fi
  sleep 1
done
ST=$(ps -o stat= -p $HOSTPID 2>/dev/null | tr -d ' ')
if [ -n "$ST" ] && [ "${ST:0:1}" != "Z" ]; then
  echo "PASS alive ${ALIVE}s" > "$OUT/result.txt"
  kill -INT $HOSTPID 2>/dev/null; sleep 3; kill -KILL $HOSTPID 2>/dev/null
else
  wait $HOSTPID; RC=$?
  echo "FAIL died rc=$RC after ~${ALIVE}s" > "$OUT/result.txt"
fi
kill -9 $RCPID >/dev/null 2>&1; wait >/dev/null 2>&1
cat "$OUT/result.txt"; echo "--- tail:"; tail -3 "$OUT/host.log"
