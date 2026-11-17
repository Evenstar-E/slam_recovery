#!/bin/bash
# LIO-SAM scripted two-event interface run: single-node LIO-SAM with the native recovery channel
# (hold / snapshot / restore / resume) plus the slam_recovery driver.
#
# Both events are placed BEFORE the known input degradation of this bag (120-140 s, 26k -> 203
# points/frame), so a refusal here is about the candidate, not about a degenerate input window.
# E1/E2 are scripted observation points (CONTROLLED_INTERFACE_TEST), not detections.
#
# usage: run_two_event_liosam.sh OUT BAG [DUR_BAG_SEC] [E1_NS] [E2_NS]
set -o pipefail
OUT="${1:?out}"; BAG="${2:?bag}"; DUR="${3:-118}"
E1="${4:-1711547493390621184}"; E2="${5:-1711547533390621184}"
PLAY_RATE="${PLAY_RATE:-0.5}"
ARM_LEAD="${ARM_LEAD:-3}"
CANDIDATE_SOURCE="${CANDIDATE_SOURCE:-host_poses}"
MARGIN="${MARGIN:-2.0}"
CTL="$OUT/ctl"; mkdir -p "$CTL" "$OUT"
set +u; source /home/R26534/mm/ros/setup.bash; source /home/R26534/catkin_ws/devel/setup.bash; set -u
export LD_LIBRARY_PATH="$HOME/mm/ros/lib:${LD_LIBRARY_PATH:-}"
export PYTHONPATH="/tmp/wt-sim:${PYTHONPATH:-}"
export ROS_HOSTNAME=127.0.0.1
PORT="$($HOME/mm/ros/bin/python -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()')"
export ROS_MASTER_URI="http://127.0.0.1:${PORT}"
export ROS_HOME="$OUT/ros_home"; mkdir -p "$ROS_HOME"
PY="$HOME/mm/ros/bin/python"
RC=""; LS=""; PLAY=""; NODE=""; REC=""
cleanup(){ [ -n "$NODE" ] && kill -INT "$NODE" 2>/dev/null; sleep 1
  for p in "$PLAY" "$REC" "$LS" "$RC"; do [ -n "$p" ] && kill -INT -- "-$p" 2>/dev/null; done; sleep 3
  [ -n "$NODE" ] && kill -TERM "$NODE" 2>/dev/null
  for p in "$PLAY" "$REC" "$LS" "$RC"; do [ -n "$p" ] && kill -TERM -- "-$p" 2>/dev/null; done
  for p in "$PLAY" "$NODE" "$REC" "$LS" "$RC"; do [ -n "$p" ] && wait "$p" 2>/dev/null; done; }
trap cleanup EXIT
{
  echo "bag=$BAG"; echo "bag_sha=$(sha256sum "$BAG" | cut -d' ' -f1)"; echo "dur_bag_sec=$DUR"
  echo "E1=$E1"; echo "E2=$E2"; echo "play_rate=$PLAY_RATE"; echo "arm_lead=$ARM_LEAD"
  echo "candidate_source=$CANDIDATE_SOURCE"; echo "margin=$MARGIN"
  echo "guard_pose_stale=${POSE_STALE:-30} guard_signal_window=${SIGNAL_WINDOW:-60} guard_hib_max=${HIB_MAX:-180} guard_repair_sync=${REPAIR_SYNC:-10} guard_first_grace=${FIRST_GRACE:-120}"
  echo "master=$ROS_MASTER_URI"; date -Is
  for f in /home/R26534/catkin_ws/devel/lib/lio_sam/lio_sam_mapOptmization \
           /home/R26534/LIO-SAM/src/mapOptmization.cpp \
           /home/R26534/LIO-SAM/config/params_mmlins.yaml \
           /home/R26534/MM-LINS/slam_recovery/ros/recovery_node.py; do
    [ -f "$f" ] && echo "$(sha256sum "$f" | cut -d' ' -f1)  $(stat -c '%y' "$f")  $f"
  done
  echo "liosam_commit=$(git -C /home/R26534/LIO-SAM rev-parse HEAD 2>/dev/null)"
} > "$OUT/pre_run.txt" 2>&1

setsid roscore -p "$PORT" > "$OUT/roscore.log" 2>&1 & RC=$!
for _ in $(seq 1 30); do rosnode list >/dev/null 2>&1 && break; sleep 1; done
# The node reads this once at construction, so it must be on the parameter server first.
rosparam set /native_recovery_dir "$CTL"
setsid roslaunch lio_sam run_offline.launch > "$OUT/liosam.log" 2>&1 & LS=$!
READY=0
for _ in $(seq 1 90); do
  n=$(rosnode list 2>/dev/null | grep -c '^/lio_sam_' || true)
  [ "$n" -ge 3 ] && READY=1 && break
  sleep 1
done
[ "$READY" -eq 1 ] || { echo "BLOCKED: lio_sam nodes did not start" | tee "$OUT/result.txt"; exit 1; }

if [ "${RECORD:-1}" = "1" ]; then
  setsid rosbag record --lz4 -O "$OUT/host.bag" /lio_sam/mapping/odometry \
    /lio_sam/mapping/loop_closure_constraints /lio_sam/mapping/path \
    > "$OUT/record.log" 2>&1 & REC=$!
  sleep 2
fi

$PY -u -I -c "import sys; sys.path.insert(0,'/home/R26534/MM-LINS'); import runpy; runpy.run_module('slam_recovery.ros.recovery_node', run_name='__main__')" \
  --run-dir "$OUT" --pose-topic /lio_sam/mapping/odometry --scan-topic /velodyne_points \
  --checkpoint-dir "$CTL" \
  --scripted-trigger-stamps "${E1},${E2}" --detection off \
  --candidate-source "${CANDIDATE_SOURCE}" \
  --repair-sync-timeout-sec "${REPAIR_SYNC:-10}" --wait-limit-sec "${WAIT_LIMIT:-40}" \
  --pose-stale-sec "${POSE_STALE:-30}" \
  --confirmation-margin-sec "${MARGIN}" \
  --first-pose-grace-sec "${FIRST_GRACE:-120}" --host-signal-window-sec "${SIGNAL_WINDOW:-60}" \
  --arm-lead-sec "${ARM_LEAD}" \
  --host-hibernation-max-sec "${HIB_MAX:-180}" \
  --duration-sec "${DRIVER_DUR:-$((DUR * 2 + 180))}" \
  > "$OUT/recovery_node.log" 2>&1 & NODE=$!
NODE_OK=0
for _ in $(seq 1 20); do
  if kill -0 "$NODE" 2>/dev/null && rosnode list 2>/dev/null | grep -q '^/slam_recovery_native_loop$'; then
    NODE_OK=1; break
  fi
  sleep 0.5
done
if [ "$NODE_OK" -ne 1 ]; then
  echo "BLOCKED: driver did not register (see recovery_node.log)" | tee "$OUT/result.txt"; exit 2
fi

setsid rosbag play --clock -r "$PLAY_RATE" --duration "$DUR" "$BAG" > "$OUT/play.log" 2>&1 & PLAY=$!
wait "$PLAY"
sleep "${POST_PLAY_DRAIN:-20}"
kill -INT "$NODE" 2>/dev/null
if [ -n "$REC" ]; then kill -INT "$REC" 2>/dev/null; wait "$REC" 2>/dev/null; fi
for _ in $(seq 1 120); do [ -d "/proc/$NODE" ] && sleep 1 || break; done
kill -0 "$NODE" 2>/dev/null && kill -TERM "$NODE" 2>/dev/null
wait "$NODE" 2>/dev/null
ls -la "$CTL" > "$OUT/ctl_listing_at_exit.txt" 2>&1 || true
echo done > "$OUT/result.txt"
