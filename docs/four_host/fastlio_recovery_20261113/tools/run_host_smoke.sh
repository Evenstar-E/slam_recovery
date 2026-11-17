#!/bin/bash
# Host-only seven-step interface smoke (A6). No recovery driver runs in this session, so the
# host's single cmd/ack slot has exactly one writer -- the smoke script. Interleaving the driver
# would let two writers share the receipt file and misattribute acks.
#
# usage: run_host_smoke.sh OUT BAG [DUR]
set -o pipefail
OUT="${1:?out}"; BAG="${2:?bag}"; DUR="${3:-80}"
CTL="$OUT/ctl"; mkdir -p "$CTL" "$OUT"
export PATH="$HOME/mm/ros/bin:$PATH"
export LD_LIBRARY_PATH="$HOME/mm/ros/lib:${LD_LIBRARY_PATH:-}"
source /home/R26534/fastlio2_ws/devel/setup.bash
export PYTHONPATH="/tmp/wt-sim:${PYTHONPATH:-}"
export ROS_HOSTNAME=127.0.0.1
PORT="$($HOME/mm/ros/bin/python -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()')"
export ROS_MASTER_URI="http://127.0.0.1:${PORT}"
RC=""; LAUNCH=""; PLAY=""
cleanup(){ [ -n "$PLAY" ] && kill -INT "$PLAY" 2>/dev/null
  for p in "$LAUNCH" "$RC"; do [ -n "$p" ] && kill -INT -- "-$p" 2>/dev/null; done; sleep 2
  for p in "$PLAY" "$LAUNCH" "$RC"; do [ -n "$p" ] && kill -TERM -- "-$p" 2>/dev/null; done
  for p in "$PLAY" "$LAUNCH" "$RC"; do [ -n "$p" ] && wait "$p" 2>/dev/null; done; }
trap cleanup EXIT
setsid roscore -p "$PORT" > "$OUT/roscore.log" 2>&1 & RC=$!
for _ in $(seq 1 30); do rosnode list >/dev/null 2>&1 && break; sleep 1; done
rosparam set /native_recovery_dir "$CTL"
setsid roslaunch fast_lio mapping_velodyne_m2dgr.launch rviz:=false > "$OUT/host.log" 2>&1 & LAUNCH=$!
for _ in $(seq 1 60); do rosnode list 2>/dev/null | grep -q '^/laserMapping$' && break; sleep 1; done
rosnode list | grep -q '^/laserMapping$' || { echo "BLOCKED: host did not start" > "$OUT/result.txt"; exit 1; }
setsid rosbag play --clock -r 1.0 --duration "$DUR" "$BAG" > "$OUT/play.log" 2>&1 & PLAY=$!
# Let the host build a map before snapshotting: a snapshot of an empty map would ACK OK and prove
# nothing about the checkpoint mechanism.
sleep "${SMOKE_LEAD_S:-45}"
$HOME/mm/ros/bin/python -u -I "$(dirname "$0")/smoke7.py" "$CTL" "$OUT/smoke7.jsonl" > "$OUT/smoke7.log" 2>&1
echo "SMOKE_EXIT=$?" >> "$OUT/smoke7.log"
wait "$PLAY" 2>/dev/null
rosbag info "$BAG" > "$OUT/bag_info.txt" 2>&1 || true
echo done > "$OUT/result.txt"
