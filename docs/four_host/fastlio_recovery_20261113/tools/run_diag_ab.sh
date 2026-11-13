#!/bin/bash
# Diagnostic native run: v4 FAST-LIO host, 260 s of campus_12, optional recovery channel, no driver.
# usage: run_diag_ab.sh <out> <bag> <A|B> [duration]
set -o pipefail
OUT="${1:?out}"; BAG="${2:?bag}"; MODE="${3:?A|B}"; DUR="${4:-260}"
mkdir -p "$OUT"; CTL="$OUT/ctl"
export PATH="$HOME/mm/ros/bin:$PATH"
export LD_LIBRARY_PATH="$HOME/mm/ros/lib:${LD_LIBRARY_PATH:-}"
source /home/R26534/fastlio2_ws/devel/setup.bash
export ROS_HOSTNAME=127.0.0.1
PORT="$($HOME/mm/ros/bin/python -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()')"
export ROS_MASTER_URI="http://127.0.0.1:${PORT}"
RC=""; LAUNCH=""; PLAY=""; REC=""
cleanup(){ for p in "$PLAY" "$REC" "$LAUNCH" "$RC"; do [ -n "$p" ] && kill -INT -- "-$p" 2>/dev/null; done; sleep 3
  for p in "$PLAY" "$REC" "$LAUNCH" "$RC"; do [ -n "$p" ] && kill -TERM -- "-$p" 2>/dev/null; done
  for p in "$PLAY" "$REC" "$LAUNCH" "$RC"; do [ -n "$p" ] && wait "$p" 2>/dev/null; done; }
trap cleanup EXIT
setsid roscore -p "$PORT" > "$OUT/roscore.log" 2>&1 & RC=$!
for _ in $(seq 1 30); do rosnode list >/dev/null 2>&1 && break; sleep 1; done
if [ "$MODE" = "B" ]; then mkdir -p "$CTL"; rosparam set /native_recovery_dir "$CTL"; fi
setsid roslaunch fast_lio mapping_velodyne_m2dgr.launch rviz:=false > "$OUT/host.log" 2>&1 & LAUNCH=$!
for _ in $(seq 1 60); do rosnode list 2>/dev/null | grep -q '^/laserMapping$' && break; sleep 1; done
rosnode list | grep -q '^/laserMapping$' || { echo "BLOCKED: host did not start" > "$OUT/result.txt"; exit 1; }
if [ "$MODE" = "B" ]; then
  for _ in $(seq 1 60); do [ -f "$CTL/capabilities.json" ] && break; sleep 0.5; done
  [ -f "$CTL/capabilities.json" ] || { echo "BLOCKED: capabilities.json not written" > "$OUT/result.txt"; exit 2; }
fi
setsid rosbag record --lz4 -O "$OUT/frontend.bag" /Odometry /Issleeping /Isbuilding > "$OUT/record.log" 2>&1 & REC=$!
sleep 2
setsid rosbag play --clock -r 1.0 --duration "$DUR" "$BAG" > "$OUT/play.log" 2>&1 & PLAY=$!
wait "$PLAY"
sleep 5
kill -INT "$REC" 2>/dev/null; wait "$REC" 2>/dev/null
sleep 2
rosbag info "$OUT/frontend.bag" > "$OUT/bag_info.txt" 2>&1 || true
echo done > "$OUT/result.txt"
