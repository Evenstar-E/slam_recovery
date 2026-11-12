#!/bin/bash
# Prove the accepted-pose write-back: after set_state the host's own state is the written one, and
# the following frames continue from it rather than from where it was.
#
#   bash slam_recovery/ros/smoke_writeback.sh <bag> <out_dir> [rate] [duration]
set -uo pipefail
BAG="${1:-/tmp/fastlivo/hall01_inj43_filtered.bag}"
OUT="${2:-/tmp/writeback_smoke}"
RATE="${3:-1.0}"
DUR="${4:-30}"

# Keep earlier run artifacts; this smoke test requires a new output directory.
if ! mkdir -- "$OUT"; then
  echo "Cannot create output directory: $OUT. Use a new path; existing outputs are preserved." >&2
  exit 1
fi
mkdir -p -- "$OUT/ctrl" "$OUT/ros_home" || exit 1

set +u
source /home/R26534/mm/ros/setup.bash
source /home/R26534/fast_livo2_ws/devel/setup.bash
set -u
export ROS_HOME="$OUT/ros_home"
PORT=$(/usr/bin/python3 -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1]);s.close()')
export ROS_MASTER_URI="http://127.0.0.1:$PORT"; export ROS_HOSTNAME=127.0.0.1

setsid roscore -p "$PORT" > "$OUT/roscore.log" 2>&1 & RC=$!
for _ in $(seq 1 60); do rosnode list >/dev/null 2>&1 && break; sleep 1; done
rosparam load /home/R26534/FAST-LIVO2/config/m2dgr.yaml /
rosparam load /home/R26534/FAST-LIVO2/config/camera_m2dgr.yaml /laserMapping
rosrun fast_livo fastlivo_mapping _native_checkpoint_dir:="$OUT/ctrl" > "$OUT/host.log" 2>&1 &
HOST=$!
sleep 2
rosbag play "$BAG" -r "$RATE" --duration "$DUR" > "$OUT/play.log" 2>&1 & PLAY=$!

send() {  # send <command> [payload]
  rm -f "$OUT/ctrl/ack"
  printf '%s\n%s\n' "$1" "${2:-}" > "$OUT/ctrl/cmd.tmp"; mv "$OUT/ctrl/cmd.tmp" "$OUT/ctrl/cmd"
  for _ in $(seq 1 500); do
    [ -s "$OUT/ctrl/ack" ] && { cat "$OUT/ctrl/ack"; return 0; }
    sleep 0.02
  done
  echo "NO_ACK"; return 1
}

sleep 18
echo "before|$(send status)"
echo "write |$(send set_state '10.000000000 0.000000000 0.000000000 0.000000000 0.000000000 0.000000000 1.000000000')"
sleep 1
echo "after1|$(send status)"
sleep 3
echo "after4|$(send status)"

wait $PLAY 2>/dev/null
kill -TERM -- "-$RC" 2>/dev/null; kill "$HOST" 2>/dev/null
grep -n "set_state" "$OUT/host.log" | tail -2
