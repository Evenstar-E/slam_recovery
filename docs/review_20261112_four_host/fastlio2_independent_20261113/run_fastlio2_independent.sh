#!/usr/bin/env bash
# FAST-LIO2 from the independent workspace /home/R26534/fastlio2_ws (NATIVE_INDEPENDENT).
# Same bag, same timeline, same topics and rate as run_fastlio2_shared.sh. No PGO.
set -o pipefail
export PATH="$HOME/mm/ros/bin:$PATH"
export LD_LIBRARY_PATH="$HOME/mm/ros/lib:${LD_LIBRARY_PATH:-}"
source /home/R26534/fastlio2_ws/devel/setup.bash
export ROS_HOSTNAME=127.0.0.1
PORT="$($HOME/mm/ros/bin/python -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()')"
export ROS_MASTER_URI="http://127.0.0.1:${PORT}"
BAG="${1:?bag}"; OUT="${2:?out}"; mkdir -p "$OUT"
mkdir -p "$OUT"
# /proc/loadavg is HOST-global in this container (no lxcfs): it says nothing about the CPU this
# container can use, so it is recorded and warned about, never used as a hard gate. The real gate
# is the playback rate measured below, plus cgroup throttling of the container itself.
LOAD1=$(awk '{print int($1)}' /proc/loadavg)
echo "load1_at_start=$LOAD1 (host-global, informational)" >> "$OUT/binary_identity.txt"
[ "$LOAD1" -gt 200 ] && echo "WARN_HOST_LOAD: load1=$LOAD1 is host-global; continuing, gating on rate" | tee -a "$OUT/runner.log"
CGROUP=/sys/fs/cgroup/cpu.stat
if [ -r "$CGROUP" ]; then grep -E 'nr_throttled|throttled_usec' "$CGROUP" > "$OUT/cgroup_start.txt" 2>/dev/null; fi
# one load sample per minute, for the whole run
( while true; do awk '{print systime(), $1, $2, $3}' /proc/loadavg >> "$OUT/loadavg.log"; sleep 60; done ) &
LOADPID=$!
{
  echo "# rosrun resolves through ROS_PACKAGE_PATH, not PATH: `command -v` is empty by design."
  echo "bash_source_ws=/home/R26534/fastlio2_ws/devel/setup.bash"
  echo "expected_binary=/home/R26534/fastlio2_ws/devel/lib/fast_lio/fastlio_mapping"
  sha256sum /home/R26534/fastlio2_ws/devel/lib/fast_lio/fastlio_mapping
  echo "bag=$BAG"; sha256sum "$BAG"
} > "$OUT/binary_identity.txt"
cat "$OUT/binary_identity.txt"
BAGLOG="$OUT/fastlio_node.log"
RC=""; LAUNCH=""; REC=""; PLAY=""
cleanup() {
  for pid in "$PLAY" "$REC" "$LAUNCH" "$RC"; do [ -n "$pid" ] && kill -INT -- "-$pid" 2>/dev/null || true; done
  sleep 3
  for pid in "$PLAY" "$REC" "$LAUNCH" "$RC"; do [ -n "$pid" ] && kill -TERM -- "-$pid" 2>/dev/null || true; done
  for pid in "$PLAY" "$REC" "$LAUNCH" "$RC"; do [ -n "$pid" ] && wait "$pid" 2>/dev/null || true; done
}
trap cleanup EXIT
setsid roscore -p "$PORT" > "$OUT/roscore.log" 2>&1 & RC=$!
for _ in $(seq 1 30); do rosnode list >/dev/null 2>&1 && break; sleep 1; done
setsid roslaunch fast_lio mapping_velodyne_m2dgr.launch rviz:=false > "$BAGLOG" 2>&1 & LAUNCH=$!
for _ in $(seq 1 60); do rosnode list 2>/dev/null | grep -q '^/laserMapping$' && break; sleep 1; done
rosnode list | grep -q '^/laserMapping$' || { echo "BLOCKED: /laserMapping did not start" >&2; exit 1; }
# Prove which binary this master's node actually runs: resolve /proc/<pid>/exe for the node under
# OUR roslaunch (other sessions' fastlio_mapping processes must not be counted).
for p in $(pgrep -f fastlio_mapping); do
  exe=$(readlink -f /proc/$p/exe 2>/dev/null)
  case "$exe" in
    /home/R26534/fastlio2_ws/*) echo "node_pid=$p exe=$exe" >> "$OUT/binary_identity.txt" ;;
  esac
done
setsid rosbag record --lz4 -O "$OUT/frontend.bag" \
  /Odometry /path /cloud_registered /cloud_registered_body /Issleeping /Isbuilding \
  > "$OUT/record.log" 2>&1 & REC=$!
sleep 2
setsid rosbag play --clock "$BAG" > "$OUT/play.log" 2>&1 & PLAY=$!
sleep 120
RATE=$(tr '\r' '\n' < "$OUT/play.log" | grep -o 'Duration: [0-9.]*' | tail -1 | awk '{print $2}')
echo "bag_duration_after_120s=${RATE:-unknown}" >> "$OUT/runner.log"
if [ -r "$CGROUP" ]; then
  grep -E 'nr_throttled|throttled_usec' "$CGROUP" > "$OUT/cgroup_120s.txt" 2>/dev/null
  T0=$(awk '/nr_throttled/{print $2}' "$OUT/cgroup_start.txt" 2>/dev/null)
  T1=$(awk '/nr_throttled/{print $2}' "$OUT/cgroup_120s.txt" 2>/dev/null)
  echo "cgroup_throttled_delta=${T0:-?}->${T1:-?}" >> "$OUT/runner.log"
fi
if [ -n "${RATE:-}" ] && awk -v r="$RATE" 'BEGIN{exit !(r < 96.0)}'; then
  echo "EARLY_STOP_RATE: only ${RATE}s of bag in 120s wall (<0.8x); stopping" | tee -a "$OUT/runner.log"
  kill -INT "$PLAY" 2>/dev/null || true
  kill -INT "$REC" 2>/dev/null || true
  wait "$REC" 2>/dev/null || true
  kill "$LOADPID" 2>/dev/null || true
  exit 3
fi
wait "$PLAY"
sleep 5
kill -INT "$REC" 2>/dev/null || true; wait "$REC" 2>/dev/null || true
sleep 2
rosbag info "$OUT/frontend.bag" > "$OUT/bag_info.txt" 2>&1 || true
kill "$LOADPID" 2>/dev/null || true
echo "[fastlio2-independent] done"
