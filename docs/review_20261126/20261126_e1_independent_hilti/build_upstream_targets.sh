#!/usr/bin/env bash
set -eo pipefail
cd "$(dirname "$0")"
test "$(cat UPSTREAM_BUILD_CERES.exit)" != 0
grep -q 'fatal error: fast_lio/Pose6D.h: No such file or directory' UPSTREAM_BUILD_CERES.log
private="$(realpath ceres-root)/usr"
source /opt/ros/noetic/setup.bash
export LD_LIBRARY_PATH="$private/lib/x86_64-linux-gnu:$private/lib/x86_64-linux-gnu/atlas:$LD_LIBRARY_PATH"
export OMP_NUM_THREADS=2 OMP_THREAD_LIMIT=2 OPENBLAS_NUM_THREADS=1
cd ros1_ceres/build
rc=0
timeout --signal=TERM --kill-after=15s 1000s bash -c '
  set -e
  make -j2 -l2 fast_lio_generate_messages_cpp livox_ros_driver_generate_messages_cpp
  make -j2 -l2 fastlio_mapping alaserPGO
' > ../../UPSTREAM_TARGETS.log 2>&1 || rc=$?
printf '%s\n' "$rc" > ../../UPSTREAM_TARGETS.exit
if [[ "$rc" == 0 ]]; then
  cd ../devel
  for bin in lib/fast_lio/fastlio_mapping lib/aloam_velodyne/alaserPGO; do
    sha256sum "$bin"
    ldd "$bin" > "../../$(basename "$bin").ldd"
    if grep -q 'not found' "../../$(basename "$bin").ldd"; then exit 2; fi
  done > ../../UPSTREAM_TARGETS_BINARY.sha256
fi
exit "$rc"
