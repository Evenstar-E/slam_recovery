#!/bin/bash
# Prove the isolation hold: after "hold" the map stops growing although frames keep being
# processed, and a restore taken before the hold is not undone by the frames that were held.
#
#   bash slam_recovery/ros/smoke_hold.sh <bag> <out_dir> [rate]
set -uo pipefail
BAG="${1:-/tmp/fastlivo/hall01_inj43_filtered.bag}"
OUT="${2:-/tmp/hold_smoke}"
RATE="${3:-1.0}"
DUR="${4:-40}"

set +u
source /home/R26534/mm/ros/setup.bash
source /home/R26534/fast_livo2_ws/devel/setup.bash
set -u
export ROS_HOME="$OUT/ros_home"; mkdir -p "$ROS_HOME" "$OUT/ctrl"; rm -f "$OUT"/ctrl/*
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

send() {  # send <command> <wait_s> [tag]
  rm -f "$OUT/ctrl/ack"
  printf '%s\n' "$1" > "$OUT/ctrl/cmd.tmp"; mv "$OUT/ctrl/cmd.tmp" "$OUT/ctrl/cmd"
  for _ in $(seq 1 $((50 * $2))); do
    if [ -s "$OUT/ctrl/ack" ]; then
      echo "${3:-$1}|$(cat "$OUT/ctrl/ack")"
      return 0
    fi
    sleep 0.02
  done
  echo "${3:-$1}|NO_ACK"
  return 1
}

sleep 20
send snapshot 5 before_hold_snapshot
sleep 3
send status 5 live_at_hold
send hold 5 hold
sleep 2
send status 5 held_t+2
sleep 2
send status 5 held_t+4
sleep 2
send status 5 held_t+6
send restore 10 restore_while_held
sleep 2
send status 5 after_restore_still_held
send resume 5 resume
sleep 4
send status 5 after_resume_t+4
sleep 4
send status 5 after_resume_t+8

wait $PLAY 2>/dev/null
kill -TERM -- "-$RC" 2>/dev/null; kill "$HOST" 2>/dev/null
echo "--- host hold/checkpoint lines ---"
grep -n "NATIVE_CHECKPOINT\|map_hold" "$OUT/host.log" | tail -20
