#!/usr/bin/env bash
# Run MM-LINS and LIO-SAM on an injected bag at 3x speed using isolated ROS master ports
set -eo pipefail

BAG="$1"
TAG="$2"
RATE="${3:-3}"

export PATH="$HOME/mm/ros/bin:$PATH"
export LD_LIBRARY_PATH="$HOME/mm/ros/lib:${LD_LIBRARY_PATH:-}"
export ROS_HOSTNAME=127.0.0.1

run_mmlins_fast() {
  source ~/mmlins_ws/devel/setup.bash
  local port
  port="$($HOME/mm/ros/bin/python -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()')"
  export ROS_MASTER_URI="http://127.0.0.1:${port}"
  local out="/tmp/mmlins_${TAG}.bag"
  rm -f "$out"

  setsid roscore -p "$port" > "/tmp/roscore_mm_${TAG}.log" 2>&1 &
  local rc_pid=$!
  for _ in {1..20}; do rosnode list >/dev/null 2>&1 && break; sleep 1; done

  setsid roslaunch fast_lio mapping_velodyne_m2dgr.launch > "/tmp/fl_${TAG}.log" 2>&1 &
  local fl_pid=$!
  setsid roslaunch aloam_velodyne fastlio_ouster64.launch rvizscpgo:=false > "/tmp/scpgo_${TAG}.log" 2>&1 &
  local sc_pid=$!

  for _ in {1..40}; do
    nodes="$(rosnode list 2>/dev/null || true)"
    if grep -q '^/laserMapping$' <<< "$nodes" && grep -q '^/alaserPGO$' <<< "$nodes"; then break; fi
    sleep 1
  done

  setsid rosbag record --lz4 -O "$out" /Odometry /aft_pgo_odom /Issleeping /loop_scan_local > "/tmp/rec_mm_${TAG}.log" 2>&1 &
  local rec_pid=$!
  sleep 2

  rosbag play --clock -r "$RATE" "$BAG" > "/tmp/play_mm_${TAG}.log" 2>&1
  sleep 8

  for p in "$rec_pid" "$sc_pid" "$fl_pid" "$rc_pid"; do
    kill -INT -- "-$p" 2>/dev/null || kill -INT "$p" 2>/dev/null || true
  done
  sleep 2
  for p in "$rec_pid" "$sc_pid" "$fl_pid" "$rc_pid"; do
    kill -TERM -- "-$p" 2>/dev/null || true
  done
  echo "[done] MM-LINS on $TAG -> $out"
}

run_liosam_fast() {
  source ~/mm/ros/setup.bash
  source ~/catkin_ws/devel/setup.bash
  local port
  port="$($HOME/mm/ros/bin/python -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()')"
  export ROS_MASTER_URI="http://127.0.0.1:${port}"
  local out="/tmp/liosam_${TAG}.bag"
  rm -f "$out"

  setsid roscore -p "$port" > "/tmp/roscore_lio_${TAG}.log" 2>&1 &
  local rc_pid=$!
  for _ in {1..20}; do rosnode list >/dev/null 2>&1 && break; sleep 1; done

  setsid roslaunch /tmp/run_hall.launch > "/tmp/lio_${TAG}.log" 2>&1 &
  local lio_pid=$!
  for _ in {1..30}; do
    rosnode list 2>/dev/null | grep -q lio_sam_mapOptmization && break
    sleep 1
  done

  setsid rosbag record --lz4 -O "$out" /lio_sam/mapping/odometry > "/tmp/rec_lio_${TAG}.log" 2>&1 &
  local rec_pid=$!
  sleep 2

  rosbag play --clock -r "$RATE" "$BAG" --topics /velodyne_points /handsfree/imu > "/tmp/play_lio_${TAG}.log" 2>&1
  sleep 5

  for p in "$rec_pid" "$lio_pid" "$rc_pid"; do
    kill -INT -- "-$p" 2>/dev/null || kill -INT "$p" 2>/dev/null || true
  done
  sleep 2
  for p in "$rec_pid" "$lio_pid" "$rc_pid"; do
    kill -TERM -- "-$p" 2>/dev/null || true
  done
  echo "[done] LIO-SAM on $TAG -> $out"
}

run_mmlins_fast &
PID_MM=$!
run_liosam_fast &
PID_LIO=$!
wait "$PID_MM" "$PID_LIO"
