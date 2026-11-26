#!/usr/bin/env bash
set -eo pipefail
cd "$(dirname "$0")"
expected=e449d56d3aae2a49338d262b9c262410693ebdd6
test "$(git -C upstream rev-parse HEAD)" = "$expected"
test -z "$(git -C upstream status --porcelain --untracked-files=no)"
frozen=/home/tong/fastlio_repro_work_20261126/frozen/fastlio_stability_20261126/v2
build_dir=ros1
suffix=
if [[ "${1:-}" == private ]]; then
  build_dir=ros1_ceres
  suffix=_CERES
  private="$(realpath ceres-root)/usr"
  export CMAKE_PREFIX_PATH="$private:${CMAKE_PREFIX_PATH:-}"
  export LD_LIBRARY_PATH="$private/lib/x86_64-linux-gnu:$private/lib/x86_64-linux-gnu/atlas:${LD_LIBRARY_PATH:-}"
fi
mkdir -p "$build_dir/src"
ln -s "$(realpath upstream)" "$build_dir/src/MM-LINS"
cp -r "$frozen/ws/src/livox_ros_driver" "$build_dir/src/"
mkdir -p upstream/FAST-LIO/Log
(cd "$build_dir/src" && find livox_ros_driver -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum) > "LIVOX_MSG$suffix.sha256"
source /opt/ros/noetic/setup.bash
export OMP_NUM_THREADS=2 OMP_THREAD_LIMIT=2 OPENBLAS_NUM_THREADS=1
cd "$build_dir"
rc=0
timeout --signal=TERM --kill-after=15s 1000s catkin_make -j2 -l2 > "../UPSTREAM_BUILD$suffix.log" 2>&1 || rc=$?
printf '%s\n' "$rc" > "../UPSTREAM_BUILD$suffix.exit"
if [[ "$rc" == 0 ]]; then
  for bin in devel/lib/fast_lio/fastlio_mapping devel/lib/aloam_velodyne/alaserPGO; do
    sha256sum "$bin"
    ldd "$bin" > "../$(basename "$bin").ldd"
    if grep -q 'not found' "../$(basename "$bin").ldd"; then exit 2; fi
  done > "../UPSTREAM_BINARY$suffix.sha256"
fi
exit "$rc"
