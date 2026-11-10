#!/bin/bash
# CONTROLLED_INTERFACE_TEST for repaired-measurement injection.
#
# Not a detection result and not a repair-quality result. The trigger is a test script calling the
# recovery interface directly; the only claims under test are:
#   * a repaired scan is matched to the frame it belongs to by timestamp and replaces that frame's
#     measurement inside the host's replay;
#   * the number replaced and the number that found no frame are both recorded;
#   * the replay after substitution changes the host's own state and map.
#
# The live path cannot be used for this: a repair is decided after the frame was processed, so it
# can only enter through reprocess-from-checkpoint. Trying it live first showed the race directly
# (received, never applied).
#
#   bash slam_recovery/ros/smoke_repair.sh <bag> <out_dir> [rate] [duration] [dz]
set -uo pipefail
BAG="${1:-/tmp/fastlivo/hall01_inj43_filtered.bag}"
OUT="${2:-/tmp/repair_smoke}"
RATE="${3:-0.5}"
DUR="${4:-26}"
DZ="${5:-1.0}"
PY=/home/R26534/mm/ros/bin/python3

set +u
source /home/R26534/mm/ros/setup.bash
source /home/R26534/fast_livo2_ws/devel/setup.bash
set -u
rm -rf "$OUT"; mkdir -p "$OUT/ctrl" "$OUT/ros_home"
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
rosbag record -O "$OUT/odom.bag" /aft_mapped_to_init > "$OUT/record.log" 2>&1 & REC=$!
sleep 1
# The injector starts with the bag so its --after-sec is bag time.
# At rate 0.5, wall seconds are twice bag seconds: the repair window is wall 40..44 = bag 20..22.
PYTHONPATH=/tmp/wt-sim "$PY" -B -u -m slam_recovery.ros.inject_repaired_scan \
    --after-sec 40 --window-sec 4 --shift-z "$DZ" --stamp-file "$OUT/inj_stamp.txt" \
    > "$OUT/inject.log" 2>&1 & INJ=$!
rosbag play "$BAG" -r "$RATE" --duration "$DUR" > "$OUT/play.log" 2>&1 & PLAY=$!

send() {  # send <command> <wait_s> [tag]
  rm -f "$OUT/ctrl/ack"
  printf '%s\n' "$1" > "$OUT/ctrl/cmd.tmp"; mv "$OUT/ctrl/cmd.tmp" "$OUT/ctrl/cmd"
  for _ in $(seq 1 $((50 * $2))); do
    if [ -s "$OUT/ctrl/ack" ]; then echo "${3:-$1}|$(cat "$OUT/ctrl/ack")"; return 0; fi
    sleep 0.02
  done
  echo "${3:-$1}|NO_ACK"; return 1
}

sleep 24
send snapshot 5 before_hold
send hold 5 hold
sleep 28           # the injector publishes into this window
send status 5 before_reprocess
send reprocess 60 reprocess
send status 5 after_reprocess

wait $PLAY 2>/dev/null
kill "$INJ" 2>/dev/null
kill -INT "$REC" 2>/dev/null; sleep 2
kill -TERM -- "-$RC" 2>/dev/null; kill "$HOST" 2>/dev/null
wait 2>/dev/null

echo "--- injector ---"
grep -c "published repaired scan" "$OUT/inject.log" 2>/dev/null
echo "--- host repair lines ---"
grep -n "NATIVE_REPAIR" "$OUT/host.log" | tail -5
