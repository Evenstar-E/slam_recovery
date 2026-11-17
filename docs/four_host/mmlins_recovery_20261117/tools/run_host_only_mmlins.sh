#!/bin/bash
# MM-LINS host-only run: front end + SC-PGO, same bag and rate as run v2, but NO recovery driver and
# therefore no hold/snapshot/restore/resume commands. Purpose is to test whether the empty-sleeping-map
# path is reachable without the freeze (and whether the guard added in PGO keeps the node alive).
#
# usage: run_host_only_mmlins.sh OUT BAG [DUR_BAG_SEC]
set -o pipefail
OUT="${1:?out}"; BAG="${2:?bag}"; DUR="${3:-470}"
PLAY_RATE="${PLAY_RATE:-0.5}"
CTL="$OUT/ctl"; mkdir -p "$CTL" "$OUT"
export PATH="$HOME/mm/ros/bin:$PATH"
export LD_LIBRARY_PATH="$HOME/mm/ros/lib:${LD_LIBRARY_PATH:-}"
source /home/R26534/mmlins_ws/devel/setup.bash
export ROS_HOSTNAME=127.0.0.1
PORT="$($HOME/mm/ros/bin/python -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()')"
export ROS_MASTER_URI="http://127.0.0.1:${PORT}"
RC=""; FE=""; PGO=""; PLAY=""; REC=""
cleanup(){ for p in "$PLAY" "$REC" "$FE" "$PGO" "$RC"; do [ -n "$p" ] && kill -INT -- "-$p" 2>/dev/null; done; sleep 3
  for p in "$PLAY" "$REC" "$FE" "$PGO" "$RC"; do [ -n "$p" ] && kill -TERM -- "-$p" 2>/dev/null; done
  for p in "$PLAY" "$REC" "$FE" "$PGO" "$RC"; do [ -n "$p" ] && wait "$p" 2>/dev/null; done; }
trap cleanup EXIT
{
  echo "bag=$BAG"; echo "bag_sha=$(sha256sum "$BAG" | cut -d' ' -f1)"; echo "dur_bag_sec=$DUR"
  echo "play_rate=$PLAY_RATE"; echo "recovery_commands=NONE"; echo "master=$ROS_MASTER_URI"; date -Is
  for f in /home/R26534/mmlins_ws/devel/lib/fast_lio/fastlio_mapping \
           /home/R26534/mmlins_ws/devel/lib/aloam_velodyne/alaserPGO \
           /home/R26534/MM-LINS/SC-PGO/src/laserPosegraphOptimization.cpp; do
    [ -f "$f" ] && echo "$(sha256sum "$f" | cut -d' ' -f1)  $(stat -c '%y' "$f")  $f"
  done
  echo "mmlins_head=$(git -C /home/R26534/MM-LINS rev-parse HEAD 2>/dev/null)"
} > "$OUT/pre_run.txt" 2>&1
setsid roscore -p "$PORT" > "$OUT/roscore.log" 2>&1 & RC=$!
for _ in $(seq 1 30); do rosnode list >/dev/null 2>&1 && break; sleep 1; done
rosparam set /native_recovery_dir "$CTL"
setsid roslaunch fast_lio mapping_velodyne_m2dgr.launch rviz:=false > "$OUT/frontend.log" 2>&1 & FE=$!
setsid roslaunch aloam_velodyne fastlio_ouster64.launch rvizscpgo:=false > "$OUT/pgo.log" 2>&1 & PGO=$!
READY=0
for _ in $(seq 1 90); do
  nodes="$(rosnode list 2>/dev/null || true)"
  if grep -q '^/laserMapping$' <<< "$nodes" && grep -q '^/alaserPGO$' <<< "$nodes"; then READY=1; break; fi
  sleep 1
done
[ "$READY" -eq 1 ] || { echo "BLOCKED: host did not start" | tee "$OUT/result.txt"; exit 1; }
setsid rosbag record --lz4 -O "$OUT/host.bag" /Odometry /aft_pgo_odom /Issleeping /Isbuilding \
  > "$OUT/record.log" 2>&1 & REC=$!
sleep 2
setsid rosbag play --clock -r "$PLAY_RATE" --duration "$DUR" "$BAG" > "$OUT/play.log" 2>&1 & PLAY=$!
wait "$PLAY"
sleep "${POST_PLAY_DRAIN:-20}"
# Liveness at end of playback: this is the whole point of the run.
if kill -0 "$PGO" 2>/dev/null; then echo "pgo_alive_at_exit=1" > "$OUT/pgo_status.txt";
else echo "pgo_alive_at_exit=0" > "$OUT/pgo_status.txt"; fi
kill -INT "$REC" 2>/dev/null; wait "$REC" 2>/dev/null
rosbag info "$OUT/host.bag" > "$OUT/bag_info.txt" 2>&1 || true
echo "skip_lines=$(grep -c 'skipping sleeping map' "$OUT/pgo.log" 2>/dev/null || echo 0)" >> "$OUT/pgo_status.txt"
grep -c "IMU Initial Done" "$OUT/frontend.log" > "$OUT/frontend_inits.txt" 2>/dev/null || true
echo done > "$OUT/result.txt"
