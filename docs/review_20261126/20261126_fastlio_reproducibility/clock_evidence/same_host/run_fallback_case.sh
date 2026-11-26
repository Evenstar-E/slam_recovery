#!/usr/bin/env bash
set -eo pipefail
root=$(cd "$(dirname "$0")" && pwd)
cd "$root"
source /opt/ros/noetic/setup.bash
parent=$(dirname "$root")
case "$2" in
  z_shift|rigid_ramp|occlusion|attenuation|narrow_fov|accept_drop|rigid_occlusion|sync|sync_narrow|eee_clean|sbs_clean) ;;
  *) exit 2;;
esac
export FROZEN_VERSION_DIR="$parent/fastlio_stability_20261126/fallback"
source "$FROZEN_VERSION_DIR/ws/devel/setup.bash"
export OMP_NUM_THREADS=2 OMP_THREAD_LIMIT=2 OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
export ROS_HOSTNAME=127.0.0.1
export LIO_TWO_EVENT_DIAGNOSTIC=1 LIO_FOUR_POLICY_DIAGNOSTIC=1 LIO_STEP5_EXACT_SCAN_KEY=1
export STEP5_INPUT="$root/independent"
export PYTHONPATH="$FROZEN_VERSION_DIR:$parent/fastlio_native_bridge_commit_20261125:$PYTHONPATH"
export PYTHONPATH="$parent/fastlio_fault_bridge_matrix_20261125:$parent/rigid_ramp_bridge_20261125:$parent/short_window_bridge_20261125:$parent/ntuviral_fastlio_step5_20261125:$parent/python:$PYTHONPATH"
export PYTHONPATH="$parent/fastlio_rtp03_clock_retiming_20261126:$parent/fastlio_rtp03_clock_confirmation_20261126:$PYTHONPATH"
export PYTHONPATH="$parent/fastlio_full_cycle_matrix_20261126:$PYTHONPATH"
export PYTHONPATH="$parent/fastlio_clock_return_edge_20261126:$PYTHONPATH"
test "$(cat "$FROZEN_VERSION_DIR/BUILD_TELEMETRY_EXIT.txt")" = 0
(cd "$FROZEN_VERSION_DIR/ws" && sha256sum -c --quiet ../BINARY.sha256)
for log in pos_log.txt imu.txt H_OUT.txt; do
  test ! -e "$FROZEN_VERSION_DIR/ws/src/FAST-LIO/Log/$log"
done
out="$root/$1"
mkdir "$out" "$out/ctl"
date -Is > "$out/started_at.txt"
port=$(/usr/bin/python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1])')
export ROS_MASTER_URI="http://127.0.0.1:$port" ROS_HOME="$out/ros_home" ROS_LOG_DIR="$out/ros_logs"
pids=()
cleanup() {
  for pid in "${pids[@]}"; do kill -INT -- "-$pid" 2>/dev/null || true; done
  for i in $(seq 1 20); do
    alive=false
    for pid in "${pids[@]}"; do if kill -0 -- "-$pid" 2>/dev/null; then alive=true; fi; done
    if ! $alive; then break; fi
    sleep .2
  done
  for pid in "${pids[@]}"; do kill -TERM -- "-$pid" 2>/dev/null || true; done
  for pid in "${pids[@]}"; do wait "$pid" 2>/dev/null || true; done
  for log in pos_log.txt imu.txt H_OUT.txt; do
    file="$FROZEN_VERSION_DIR/ws/src/FAST-LIO/Log/$log"
    if [[ -f "$file" && ! -L "$file" ]]; then
      sha256sum "$file" >> "$out/host_log_hashes.txt"
      unlink "$file"
    fi
  done
  date -Is > "$out/finished_at.txt"
}
trap cleanup EXIT
setsid roscore -p "$port" > "$out/roscore.log" 2>&1 & pids+=($!)
for i in $(seq 1 60); do rosparam list >/dev/null 2>&1 && break; sleep .2; done
rosparam set /native_recovery_dir "$out/ctl"
setsid bash -c 'PYTHONUNBUFFERED=1 roslaunch "$1" 2>&1 | /usr/bin/python3 -u "$2"' _ \
  "$FROZEN_VERSION_DIR/ntulab.launch" "$root/stamp_log.py" > "$out/host_markers.jsonl" 2>&1 & pids+=($!)
for i in $(seq 1 70); do test -s "$out/ctl/capabilities.json" && break; sleep .2; done
test -s "$out/ctl/capabilities.json"
code=0
timeout --signal=TERM --kill-after=5s 195s /usr/bin/python3 -u fallback_version/clock_ingress_preview.py "$out" "$2" "$3" > "$out/run.log" 2>&1 || code=$?
echo "$code" > "$out/exit.txt"
exit "$code"
