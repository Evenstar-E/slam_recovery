#!/bin/bash
# MM-LINS scripted two-event整链 run:
#   FAST-LIO front end (v9 native recovery channel + pgo_hold marker)
# + SC-PGO alaserPGO (freezes keyframe insertion while the marker exists)
# + slam_recovery driver (hold -> snapshot -> restore -> repaired scan -> resume).
#
# E1/E2 are DECLARED OBSERVATION points (natural hibernation windows of campus_12), not injections.
# Nothing here changes gate thresholds, ICP configuration or the front-end physics: the only host
# change is the channel port plus the marker file that links the two processes.
#
# usage: run_two_event_mmlins.sh OUT BAG [DUR_BAG_SEC] [E1_NS] [E2_NS]
set -o pipefail
OUT="${1:?out}"; BAG="${2:?bag}"; DUR="${3:-470}"
E1="${4:-1711547999352267771}"; E2="${5:-1711548113452267771}"
PLAY_RATE="${PLAY_RATE:-1.0}"
ARM_LEAD="${ARM_LEAD:-3}"
CANDIDATE_SOURCE="${CANDIDATE_SOURCE:-host_poses}"
MARGIN="${MARGIN:-2.0}"
WAIT_LIMIT="${WAIT_LIMIT:-20}"
CTL="$OUT/ctl"; mkdir -p "$CTL" "$OUT"
export PATH="$HOME/mm/ros/bin:$PATH"
export LD_LIBRARY_PATH="$HOME/mm/ros/lib:${LD_LIBRARY_PATH:-}"
source /home/R26534/mmlins_ws/devel/setup.bash
export PYTHONPATH="/tmp/wt-sim:${PYTHONPATH:-}"
export ROS_HOSTNAME=127.0.0.1
PORT="$($HOME/mm/ros/bin/python -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()')"
export ROS_MASTER_URI="http://127.0.0.1:${PORT}"
PY="$HOME/mm/ros/bin/python"
RC=""; FE=""; PGO=""; PLAY=""; NODE=""; REC=""
cleanup(){ [ -n "$NODE" ] && kill -INT "$NODE" 2>/dev/null; sleep 1
  for p in "$PLAY" "$REC" "$FE" "$PGO" "$RC"; do [ -n "$p" ] && kill -INT -- "-$p" 2>/dev/null; done; sleep 3
  [ -n "$NODE" ] && kill -TERM "$NODE" 2>/dev/null
  for p in "$PLAY" "$REC" "$FE" "$PGO" "$RC"; do [ -n "$p" ] && kill -TERM -- "-$p" 2>/dev/null; done
  for p in "$PLAY" "$NODE" "$REC" "$FE" "$PGO" "$RC"; do [ -n "$p" ] && wait "$p" 2>/dev/null; done; }
trap cleanup EXIT

# Pre-run identity: what was actually launched, before anything can change it.
{
  echo "bag=$BAG"; echo "bag_sha=$(sha256sum "$BAG" | cut -d' ' -f1)"; echo "dur_bag_sec=$DUR"
  echo "E1=$E1"; echo "E2=$E2"; echo "play_rate=$PLAY_RATE"; echo "arm_lead=${ARM_LEAD}"
  echo "candidate_source=$CANDIDATE_SOURCE"; echo "margin=$MARGIN"; echo "wait_limit=$WAIT_LIMIT"
  echo "guard_pose_stale=${POSE_STALE:-15} guard_signal_window=${SIGNAL_WINDOW:-30} guard_hib_max=${HIB_MAX:-90} guard_repair_sync=${REPAIR_SYNC:-5} guard_first_grace=${FIRST_GRACE:-60}"
  echo "master=$ROS_MASTER_URI"; date -Is
  for f in /home/R26534/mmlins_ws/devel/lib/fast_lio/fastlio_mapping \
           /home/R26534/mmlins_ws/devel/lib/aloam_velodyne/alaserPGO \
           /home/R26534/MM-LINS/FAST-LIO/src/laserMapping.cpp \
           /home/R26534/MM-LINS/SC-PGO/src/laserPosegraphOptimization.cpp \
           /home/R26534/MM-LINS/slam_recovery/ros/recovery_node.py; do
    [ -f "$f" ] && echo "$(sha256sum "$f" | cut -d' ' -f1)  $(stat -c '%y' "$f")  $f"
  done
  echo "mmlins_head=$(git -C /home/R26534/MM-LINS rev-parse HEAD 2>/dev/null)"
} > "$OUT/pre_run.txt" 2>&1

setsid roscore -p "$PORT" > "$OUT/roscore.log" 2>&1 & RC=$!
for _ in $(seq 1 30); do rosnode list >/dev/null 2>&1 && break; sleep 1; done
# Both nodes read this: the front end opens its file channel here, the pose graph watches
# <dir>/pgo_hold. It must be set before either launch, because each reads the parameter once.
rosparam set /native_recovery_dir "$CTL"
setsid roslaunch fast_lio mapping_velodyne_m2dgr.launch rviz:=false > "$OUT/frontend.log" 2>&1 & FE=$!
setsid roslaunch aloam_velodyne fastlio_ouster64.launch rvizscpgo:=false > "$OUT/pgo.log" 2>&1 & PGO=$!
READY=0
for _ in $(seq 1 90); do
  nodes="$(rosnode list 2>/dev/null || true)"
  if grep -q '^/laserMapping$' <<< "$nodes" && grep -q '^/alaserPGO$' <<< "$nodes"; then READY=1; break; fi
  sleep 1
done
if [ "$READY" -ne 1 ]; then
  echo "BLOCKED: front end or pose graph did not start" | tee "$OUT/result.txt"; exit 1
fi

if [ "${RECORD:-1}" = "1" ]; then
  setsid rosbag record --lz4 -O "$OUT/host.bag" /Odometry /aft_pgo_odom /Issleeping /Isbuilding \
    > "$OUT/record.log" 2>&1 & REC=$!
  sleep 2
fi

# No setsid here: $! must be the driver itself so the liveness gate tests the real process.
$PY -u -I -c "import sys; sys.path.insert(0,'/home/R26534/MM-LINS'); import runpy; runpy.run_module('slam_recovery.ros.recovery_node', run_name='__main__')" \
  --run-dir "$OUT" --pose-topic /Odometry --scan-topic /velodyne_points --checkpoint-dir "$CTL" \
  --scripted-trigger-stamps "${E1},${E2}" --detection off --repair-publish \
  --candidate-source "${CANDIDATE_SOURCE}" \
  --require-contract --repair-sync-timeout-sec "${REPAIR_SYNC:-5}" --wait-limit-sec "${WAIT_LIMIT}" \
  --pose-stale-sec "${POSE_STALE:-15}" \
  --confirmation-margin-sec "${MARGIN}" \
  --first-pose-grace-sec "${FIRST_GRACE:-60}" --host-signal-window-sec "${SIGNAL_WINDOW:-30}" \
  --arm-lead-sec "${ARM_LEAD}" \
  --host-hibernation-max-sec "${HIB_MAX:-90}" --host-sleep-topic /Issleeping --host-build-topic /Isbuilding \
  --duration-sec "${DRIVER_DUR:-$((DUR + 180))}" \
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
rosbag info "$OUT/host.bag" > "$OUT/bag_info.txt" 2>&1 || true
cp "$CTL/pgo_hold" "$OUT/pgo_hold_at_exit.txt" 2>/dev/null || echo "absent" > "$OUT/pgo_hold_at_exit.txt"
ls -la "$CTL" > "$OUT/ctl_listing_at_exit.txt" 2>&1 || true
echo done > "$OUT/result.txt"
