#!/bin/bash
# Scripted two-event interface run: host (FAST-LIO native recovery) + slam_recovery driver.
set -o pipefail
OUT="${1:?out}"; BAG="${2:?bag}"; DUR="${3:-260}"
E1="${4:-1711547999352267771}"; E2="${5:-1711548113452267771}"
CTL="$OUT/ctl"; mkdir -p "$CTL" "$OUT"
export PATH="$HOME/mm/ros/bin:$PATH"
export LD_LIBRARY_PATH="$HOME/mm/ros/lib:${LD_LIBRARY_PATH:-}"
source /home/R26534/fastlio2_ws/devel/setup.bash
export PYTHONPATH="/tmp/wt-sim:${PYTHONPATH:-}"
export ROS_HOSTNAME=127.0.0.1
PORT="$($HOME/mm/ros/bin/python -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()')"
export ROS_MASTER_URI="http://127.0.0.1:${PORT}"
PY="$HOME/mm/ros/bin/python"
RC=""; LAUNCH=""; PLAY=""; NODE=""
cleanup(){ [ -n "$NODE" ] && kill -INT "$NODE" 2>/dev/null; sleep 1
  for p in "$PLAY" "$REC" "$LAUNCH" "$RC"; do [ -n "$p" ] && kill -INT -- "-$p" 2>/dev/null; done; sleep 2
  [ -n "$NODE" ] && kill -TERM "$NODE" 2>/dev/null
  for p in "$PLAY" "$REC" "$LAUNCH" "$RC"; do [ -n "$p" ] && kill -TERM -- "-$p" 2>/dev/null; done
  for p in "$PLAY" "$NODE" "$REC" "$LAUNCH" "$RC"; do [ -n "$p" ] && wait "$p" 2>/dev/null; done; }
trap cleanup EXIT
setsid roscore -p "$PORT" > "$OUT/roscore.log" 2>&1 & RC=$!
for _ in $(seq 1 30); do rosnode list >/dev/null 2>&1 && break; sleep 1; done
rosparam set /native_recovery_dir "$CTL"
setsid roslaunch fast_lio mapping_velodyne_m2dgr.launch rviz:=false > "$OUT/host.log" 2>&1 & LAUNCH=$!
for _ in $(seq 1 60); do rosnode list 2>/dev/null | grep -q '^/laserMapping$' && break; sleep 1; done
rosnode list | grep -q '^/laserMapping$' || { echo "BLOCKED: host did not start" > "$OUT/result.txt"; exit 1; }
# No setsid here: $! must be the driver itself, otherwise the liveness gate tests a wrapper that
# has already exited and its cleanup SIGINTs a healthy driver.
$PY -u -I -c "import sys; sys.path.insert(0,'/home/R26534/MM-LINS'); import runpy; runpy.run_module('slam_recovery.ros.recovery_node', run_name='__main__')" \
  --run-dir "$OUT" --pose-topic /Odometry --scan-topic /velodyne_points --checkpoint-dir "$CTL" \
  --scripted-trigger-stamps "${E1},${E2}" --detection off --repair-publish \
  --require-contract --repair-sync-timeout-sec 5 --wait-limit-sec 20 --pose-stale-sec 15 \
  --first-pose-grace-sec 60 --host-signal-window-sec 30 \
  --host-hibernation-max-sec 90 --host-sleep-topic /Issleeping --host-build-topic /Isbuilding \
  --duration-sec "$DUR" \
  > "$OUT/recovery_node.log" 2>&1 & NODE=$!
# The bag must not start unless the driver is alive: an earlier run played 102 s with a driver
# that had never imported (ModuleNotFoundError under -I) and produced no evidence at all.
# Gate on the driver's presence in the ROS graph, not on its log file: stdout to a file is
# block-buffered, so the log can still be empty while the driver is healthy (this cost attempt #4).
NODE_OK=0
for _ in $(seq 1 20); do
  if kill -0 "$NODE" 2>/dev/null && rosnode list 2>/dev/null | grep -q '^/slam_recovery_native_loop$'; then
    NODE_OK=1; break
  fi
  sleep 0.5
done
if [ "$NODE_OK" -ne 1 ]; then
  echo "BLOCKED: driver did not register (see recovery_node.log)" | tee "$OUT/result.txt"
  exit 2
fi
RECORD="${RECORD:-1}"
if [ "$RECORD" = "1" ]; then
  setsid rosbag record --lz4 -O "$OUT/frontend.bag" /Odometry /Issleeping /Isbuilding > "$OUT/record.log" 2>&1 & REC=$!
  sleep 2
fi
setsid rosbag play --clock -r 1.0 --duration "$DUR" "$BAG" > "$OUT/play.log" 2>&1 & PLAY=$!
wait "$PLAY"
# Drain: the driver processes the bag at ~7 Hz while the host publishes at ~8-10 Hz, so a queue of
# bag-end frames remains when playback stops. Keep the driver alive long enough to work through it
# before signalling; POST_PLAY_DRAIN controls how long (default keeps the old 20 s).
sleep "${POST_PLAY_DRAIN:-20}"
kill -INT "$NODE" 2>/dev/null
if [ -n "$REC" ]; then kill -INT "$REC" 2>/dev/null; wait "$REC" 2>/dev/null; fi
for _ in $(seq 1 120); do [ -d "/proc/$NODE" ] && sleep 1 || break; done
kill -0 "$NODE" 2>/dev/null && kill -TERM "$NODE" 2>/dev/null
wait "$NODE" 2>/dev/null
rosbag info "$OUT/frontend.bag" > "$OUT/bag_info.txt" 2>&1 || true
echo done > "$OUT/result.txt"
