#!/usr/bin/env bash
# MM-LINS 一键运行: FAST-LIO 前端 + SC-PGO 后端 + 录制结果 bag (Foxglove 可直接打开)
# 全量录制 + LZ4 压缩; 跑完自动生成轻量版(轨迹+回环)和中量版(稀疏点云)两个 Foxglove bag
set -e
export PATH="$HOME/mm/ros/bin:$PATH"
export LD_LIBRARY_PATH="$HOME/mm/ros/lib:${LD_LIBRARY_PATH:-}"
source ~/mmlins_ws/devel/setup.bash

# Use a private local master for each run; the shared host's default 11311
# port may be occupied by another ROS process.
export ROS_HOSTNAME=127.0.0.1
ROS_PORT="$($HOME/mm/ros/bin/python -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()')"
export ROS_MASTER_URI="http://127.0.0.1:${ROS_PORT}"
echo "[run_mmlins] ROS master: $ROS_MASTER_URI"

BAG="${1:-/home/R26534/datasets/mmlins/campus_3-004_fl.bag}"
OUT="${2:-/home/R26534/mmlins_ws/output/result_$(date +%m%d_%H%M%S)}"
mkdir -p "$(dirname "$OUT")"

ROSCORE_PID=""
FASTLIO_PID=""
SCPGO_PID=""
RECORD_PID=""

cleanup() {
  echo "[run_mmlins] stopping only process groups started by this run..."
  for pid in "$RECORD_PID" "$SCPGO_PID" "$FASTLIO_PID" "$ROSCORE_PID"; do
    if [[ -n "$pid" ]]; then kill -INT -- "-$pid" 2>/dev/null || true; fi
  done
  sleep 3
  for pid in "$RECORD_PID" "$SCPGO_PID" "$FASTLIO_PID" "$ROSCORE_PID"; do
    if [[ -n "$pid" ]]; then kill -TERM -- "-$pid" 2>/dev/null || true; fi
  done
  for pid in "$RECORD_PID" "$SCPGO_PID" "$FASTLIO_PID" "$ROSCORE_PID"; do
    if [[ -n "$pid" ]]; then wait "$pid" 2>/dev/null || true; fi
  done
  return 0
}
trap cleanup EXIT

setsid roscore -p "$ROS_PORT" > /tmp/mm_roscore.log 2>&1 &
ROSCORE_PID=$!
for _ in {1..30}; do
  rosnode list > /dev/null 2>&1 && break
  sleep 1
done
rosnode list > /dev/null

setsid roslaunch fast_lio mapping_velodyne_m2dgr.launch > /tmp/mm_fastlio.log 2>&1 &
FASTLIO_PID=$!
setsid roslaunch aloam_velodyne fastlio_ouster64.launch rvizscpgo:=false > /tmp/mm_scpgo.log 2>&1 &
SCPGO_PID=$!
ready=0
for _ in {1..90}; do
  nodes="$(rosnode list 2>/dev/null || true)"
  if grep -q '^/laserMapping$' <<< "$nodes" && grep -q '^/alaserPGO$' <<< "$nodes"; then
    ready=1
    break
  fi
  sleep 1
done
rosnode list
if [[ "$ready" -ne 1 ]]; then
  echo '[run_mmlins] FAST-LIO or SC-PGO did not become ready within 90s' >&2
  exit 1
fi

# 全量 + lz4 压缩; 含回环可视化话题
setsid rosbag record --lz4 -O "$OUT" \
  /Odometry /path /cloud_registered /aft_pgo_odom /aft_pgo_path /aft_pgo_map \
  Issleeping /loop_scan_local /loop_submap_local /repub_odom \
  > /tmp/mm_record.log 2>&1 &
RECORD_PID=$!
sleep 2

echo "[run_mmlins] playing bag: $BAG"
rosbag play --clock "$BAG" > /tmp/mm_play.log 2>&1
echo "[run_mmlins] bag finished, waiting 15s for PGO to settle..."
sleep 15
echo "[run_mmlins] stopping recorder and finalizing: $OUT.bag"
kill -INT "$RECORD_PID" 2>/dev/null || true
wait "$RECORD_PID" 2>/dev/null || true
sleep 2

# 自动生成 Foxglove 精简版
~/mm/micromamba run -p ~/mm/ros -- python "$HOME/mmlins_ws/postprocess.py" "$OUT".bag || true
echo "[run_mmlins] done"
exit 0
