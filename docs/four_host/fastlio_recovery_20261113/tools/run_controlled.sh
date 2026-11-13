#!/bin/bash
# Bounded controlled interface test for the FAST-LIO native recovery channel.
# 120 s of the campus bag, one hold/snapshot/restore/reprocess cycle with one repaired cloud.
set -o pipefail
OUT="${1:?out dir}"; BAG="${2:?bag}"; DUR="${3:-120}"
CTL="$OUT/ctl"; mkdir -p "$CTL" "$OUT"
export PATH="$HOME/mm/ros/bin:$PATH"
export LD_LIBRARY_PATH="$HOME/mm/ros/lib:${LD_LIBRARY_PATH:-}"
source /home/R26534/fastlio2_ws/devel/setup.bash
export ROS_HOSTNAME=127.0.0.1
PORT="$($HOME/mm/ros/bin/python -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()')"
export ROS_MASTER_URI="http://127.0.0.1:${PORT}"
PY="$HOME/mm/ros/bin/python3"
RC=""; LAUNCH=""; PLAY=""; FEED=""
cleanup(){ for p in "$PLAY" "$FEED" "$LAUNCH" "$RC"; do [ -n "$p" ] && kill -INT -- "-$p" 2>/dev/null; done; sleep 2
  for p in "$PLAY" "$FEED" "$LAUNCH" "$RC"; do [ -n "$p" ] && kill -TERM -- "-$p" 2>/dev/null; done
  for p in "$PLAY" "$FEED" "$LAUNCH" "$RC"; do [ -n "$p" ] && wait "$p" 2>/dev/null; done; }
trap cleanup EXIT
setsid roscore -p "$PORT" > "$OUT/roscore.log" 2>&1 & RC=$!
for _ in $(seq 1 30); do rosnode list >/dev/null 2>&1 && break; sleep 1; done
rosparam set /native_recovery_dir "$CTL"
setsid roslaunch fast_lio mapping_velodyne_m2dgr.launch rviz:=false > "$OUT/host.log" 2>&1 & LAUNCH=$!
for _ in $(seq 1 60); do rosnode list 2>/dev/null | grep -q '^/laserMapping$' && break; sleep 1; done
rosnode list | grep -q '^/laserMapping$' || { echo "BLOCKED: node did not start" | tee "$OUT/result.txt"; exit 1; }
setsid $PY "$(dirname "$0")/nr_repair.py" "$CTL" > "$OUT/repair.log" 2>&1 & FEED=$!
sleep 2
setsid rosbag play --clock -r 1.0 --duration "$DUR" "$BAG" > "$OUT/play.log" 2>&1 & PLAY=$!
sleep 30
{
 echo "== status before"; $PY "$(dirname "$0")/nr_cmd.py" "$CTL" status
 echo "== capabilities"; $PY "$(dirname "$0")/nr_cmd.py" "$CTL" capabilities
 echo "== hold"; $PY "$(dirname "$0")/nr_cmd.py" "$CTL" hold
 sleep 1
 echo "== snapshot A"; $PY "$(dirname "$0")/nr_cmd.py" "$CTL" snapshot
 echo "== resume"; $PY "$(dirname "$0")/nr_cmd.py" "$CTL" resume
 sleep 6
 echo "== publish repaired cloud"; touch "$CTL/publish"; sleep 2
 echo "== restore"; $PY "$(dirname "$0")/nr_cmd.py" "$CTL" restore
 echo "== reprocess"; $PY "$(dirname "$0")/nr_cmd.py" "$CTL" reprocess
 sleep 8
 echo "== snapshot B"; $PY "$(dirname "$0")/nr_cmd.py" "$CTL" snapshot
 echo "== status after"; $PY "$(dirname "$0")/nr_cmd.py" "$CTL" status
} > "$OUT/commands.log" 2>&1
wait "$PLAY"
sleep 3
kill -INT "$FEED" 2>/dev/null; wait "$FEED" 2>/dev/null
echo "done" > "$OUT/result.txt"
