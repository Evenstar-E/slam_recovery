#!/bin/bash
# Smoke test for the host's native checkpoint channel: start the host on a short window of a real
# bag, ask it to snapshot and then restore, and print what it acknowledged. Nothing is judged here;
# the point is to see the copy and the rollback happen in the host's own log.
set -uo pipefail

BAG="${1:-/tmp/fastlivo/hall01_inj43_filtered.bag}"
OUT="${2:-/tmp/cp_smoke}"
RATE="${3:-3.0}"
DUR="${4:-12}"

set +u
source /home/R26534/mm/ros/setup.bash
source /home/R26534/fast_livo2_ws/devel/setup.bash
set -u
export ROS_HOME="$OUT/ros_home"; mkdir -p "$ROS_HOME" "$OUT/ctrl"
rm -f "$OUT"/ctrl/*
PORT=$(/usr/bin/python3 -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1]);s.close()')
export ROS_MASTER_URI="http://127.0.0.1:$PORT"; export ROS_HOSTNAME=127.0.0.1

setsid roscore -p "$PORT" > "$OUT/roscore.log" 2>&1 & RC=$!
for _ in $(seq 1 60); do rosnode list >/dev/null 2>&1 && break; sleep 1; done
rosparam load /home/R26534/FAST-LIVO2/config/m2dgr.yaml / || exit 1
rosparam load /home/R26534/FAST-LIVO2/config/camera_m2dgr.yaml /laserMapping || exit 1

rosrun fast_livo fastlivo_mapping _native_checkpoint_dir:="$OUT/ctrl" > "$OUT/host.log" 2>&1 &
HOST=$!
sleep 2
rosbag play "$BAG" -r "$RATE" --duration "$DUR" > "$OUT/play.log" 2>&1 & PLAY=$!

send() {  # send <command> <wait_s>
  rm -f "$OUT/ctrl/ack"
  local t0 t1
  t0=$(date +%s.%N)
  printf '%s\n' "$1" > "$OUT/ctrl/cmd.tmp"
  mv "$OUT/ctrl/cmd.tmp" "$OUT/ctrl/cmd"
  for _ in $(seq 1 $((10 * $2))); do
    if [ -s "$OUT/ctrl/ack" ]; then
      t1=$(date +%s.%N)
      # Ack latency is the only end-to-end cost the driver can see: it covers the host's poll
      # interval, the copy itself, and the write.
      echo "[smoke] $1 -> $(cat "$OUT/ctrl/ack") [latency $(/usr/bin/python3 -c "print(round(float($t1)-float($t0),3))") s]"
      return 0
    fi
    sleep 0.02
  done
  echo "[smoke] $1 -> NO ACK within $2 s"
  return 1
}

sleep 8
send snapshot 5
sleep 3
send snapshot 5
sleep 3
send snapshot 5
send status 5
send restore 10
send status 5
send reprocess 20
send status 5

wait $PLAY 2>/dev/null
kill -TERM -- "-$RC" 2>/dev/null
kill "${HOST:-0}" 2>/dev/null
echo "--- host checkpoint lines ---"
grep -n "NATIVE_CHECKPOINT" "$OUT/host.log" | tail -20
