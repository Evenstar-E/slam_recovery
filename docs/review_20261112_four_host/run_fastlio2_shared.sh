#!/usr/bin/env bash
# FAST-LIO2 front end only, one run, on the same bag and timeline as the MM-LINS run.
#
# SHARED_EXECUTION: this binary is mmlins_ws/devel/lib/fast_lio/fastlio_mapping, i.e. the same
# front end that run_mmlins.sh launches. There is no separate FAST-LIO2 workspace on this machine
# (only one fastlio_mapping exists under /home/R26534). The PGO back end is NOT started here.
#
#   bash run_fastlio2_shared.sh <bag> <out_dir>
# No `set -u`: the catkin setup.sh references ZSH_VERSION unguarded, and an unbound-variable
# error is fatal in a non-interactive shell, which killed the script before roscore.
set -o pipefail
export PATH="$HOME/mm/ros/bin:$PATH"
export LD_LIBRARY_PATH="$HOME/mm/ros/lib:${LD_LIBRARY_PATH:-}"
source ~/mmlins_ws/devel/setup.bash
export ROS_HOSTNAME=127.0.0.1
PORT="$($HOME/mm/ros/bin/python -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()')"
export ROS_MASTER_URI="http://127.0.0.1:${PORT}"

BAG="${1:?bag path required}"
OUT="${2:?output dir required}"
mkdir -p "$OUT"
BAGLOG="$OUT/fastlio_node.log"

RC=""; LAUNCH=""; REC=""; PLAY=""
cleanup() {
  for pid in "$PLAY" "$REC" "$LAUNCH" "$RC"; do
    [ -n "$pid" ] && kill -INT -- "-$pid" 2>/dev/null || true
  done
  sleep 3
  for pid in "$PLAY" "$REC" "$LAUNCH" "$RC"; do
    [ -n "$pid" ] && kill -TERM -- "-$pid" 2>/dev/null || true
  done
  for pid in "$PLAY" "$REC" "$LAUNCH" "$RC"; do
    [ -n "$pid" ] && wait "$pid" 2>/dev/null || true
  done
  return 0
}
trap cleanup EXIT

setsid roscore -p "$PORT" > "$OUT/roscore.log" 2>&1 &
RC=$!
for _ in $(seq 1 30); do rosnode list >/dev/null 2>&1 && break; sleep 1; done

# rviz stays off; the launch loads config/velodyne_m2dgr.yaml and sets the same params the
# MM-LINS front end runs with.
setsid roslaunch fast_lio mapping_velodyne_m2dgr.launch rviz:=false > "$BAGLOG" 2>&1 &
LAUNCH=$!
for _ in $(seq 1 60); do rosnode list 2>/dev/null | grep -q '^/laserMapping$' && break; sleep 1; done
rosnode list | grep -q '^/laserMapping$' || { echo "BLOCKED: /laserMapping did not start" >&2; exit 1; }

setsid rosbag record --lz4 -O "$OUT/frontend.bag" \
  /Odometry /path /cloud_registered /cloud_registered_body /Issleeping /Isbuilding \
  > "$OUT/record.log" 2>&1 &
REC=$!
sleep 2

echo "[fastlio2] playing $BAG"
setsid rosbag play --clock "$BAG" > "$OUT/play.log" 2>&1 &
PLAY=$!
wait "$PLAY"
echo "[fastlio2] bag finished, 5 s settle"
sleep 5
kill -INT "$REC" 2>/dev/null || true
wait "$REC" 2>/dev/null || true
sleep 2
echo "[fastlio2] recorded $OUT/frontend.bag"
exit 0
