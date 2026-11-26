#!/usr/bin/env bash
set -eo pipefail
cd "$(dirname "$0")"
root="$PWD"
test "$(git -C upstream rev-parse HEAD)" = e449d56d3aae2a49338d262b9c262410693ebdd6
test -s UPSTREAM_TARGETS_BINARY.sha256
private="$(realpath ceres-root)/usr"
source /opt/ros/noetic/setup.bash
source ros1_ceres/devel/setup.bash
export LD_LIBRARY_PATH="$private/lib/x86_64-linux-gnu:$private/lib/x86_64-linux-gnu/atlas:$LD_LIBRARY_PATH"
export OMP_NUM_THREADS=2 OMP_THREAD_LIMIT=2 OPENBLAS_NUM_THREADS=1 ROS_HOSTNAME=127.0.0.1
(cd ros1_ceres/devel && sha256sum -c --quiet "$root/UPSTREAM_TARGETS_BINARY.sha256")
mode="${1:-campus12}"
case "$mode" in
  campus12)
    out="$root/upstream_campus12_smoke"
    input=/home/tong/datasets/mmlins/campus_12.bag
    frontend=(roslaunch fast_lio mapping_velodyne.launch rviz:=false)
    ;;
  spms)
    out="$root/upstream_spms_paired"
    input="$root/SPMS_FAULT_PAIRED.bag"
    frozen="/home/tong/fastlio_repro_work_20261126/frozen/fastlio_stability_20261126/fallback"
    frontend=(roslaunch "$out/ntulab.launch")
    ;;
  hilti_revisit)
    out="$root/upstream_hilti_revisit"
    input="$root/HILTI_REVISIT.bag"
    frontend=(roslaunch "$out/hilti.launch")
    ;;
  *)
    exit 2
    ;;
esac
test -s "$input"
mkdir "$out"
if [[ "$mode" == spms ]]; then cp "$frozen"/{ntulab.launch,ntulab.yaml} "$out"; fi
if [[ "$mode" == hilti_revisit ]]; then
  qualified=/home/tong/slam_recovery_step3_runs/hilti_surface_qualification_20261125
  cp "$qualified/HILTI_SMOKE.yaml" "$out"
  cat > "$out/hilti.launch" <<'XML'
<launch>
  <rosparam command="load" file="$(dirname)/HILTI_SMOKE.yaml" />
  <param name="publish/scan_publish_en" value="true" />
  <param name="publish/scan_bodyframe_pub_en" value="true" />
  <node pkg="fast_lio" type="fastlio_mapping" name="laserMapping" output="screen" />
</launch>
XML
fi
port=$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1])')
export ROS_MASTER_URI="http://127.0.0.1:$port" ROS_HOME="$out/ros_home" ROS_LOG_DIR="$out/ros_logs"
pids=()
cleanup() {
  for pid in "${pids[@]}"; do kill -INT -- "-$pid" 2>/dev/null || true; done
  sleep 2
  for pid in "${pids[@]}"; do kill -TERM -- "-$pid" 2>/dev/null || true; done
  for pid in "${pids[@]}"; do wait "$pid" 2>/dev/null || true; done
}
trap cleanup EXIT
setsid roscore -p "$port" > "$out/roscore.log" 2>&1 & pids+=($!)
for _ in $(seq 1 60); do rosparam list >/dev/null 2>&1 && break; sleep .2; done
setsid "${frontend[@]}" > "$out/frontend.log" 2>&1 & pids+=($!)
setsid roslaunch aloam_velodyne fastlio_ouster64.launch rvizscpgo:=false > "$out/backend.log" 2>&1 & pids+=($!)
setsid rosbag record -O "$out/observed.bag" /Odometry /aft_pgo_odom /aft_pgo_path /Isbuilding /Issleeping \
  > "$out/record.log" 2>&1 & recorder=$!; pids+=("$recorder")
sleep 3
rosnode list > "$out/nodes_before.txt"
rc=0
topics=(/velodyne_points /imu_raw)
if [[ "$mode" == hilti_revisit ]]; then topics=(/hilti_surface/hesai_adapted /alphasense/imu); fi
timeout --signal=TERM --kill-after=5s 48s rosbag play --quiet --duration 40 \
  "$input" --topics "${topics[@]}" > "$out/play.log" 2>&1 || rc=$?
printf '%s\n' "$rc" > "$out/play.exit"
rosnode list > "$out/nodes_after.txt"
kill -INT -- "-$recorder" 2>/dev/null || true
wait "$recorder" || true
test -s "$out/observed.bag"
rosbag info --yaml "$out/observed.bag" > "$out/OBSERVED.yaml"
sha256sum "$out/observed.bag" > "$out/OBSERVED.sha256"
exit "$rc"
