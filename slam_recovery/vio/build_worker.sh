#!/usr/bin/env bash
# Build in a dedicated ORB-SLAM3 checkout using the same dependencies as its native build.
set -euo pipefail

orb="$(realpath "$1")"
build="$(realpath -m "$2")"
pangolin="$(realpath "$3")"
here="$(cd "$(dirname "$0")" && pwd)"

python3 "$here/orb_snapshot.py" "$orb"
cmake -S "$orb" -B "$build" -DCMAKE_BUILD_TYPE=Release "-DPangolin_DIR=$pangolin"
cmake --build "$build" --target g2o --parallel 2
cmake -S "$orb/Thirdparty/DBoW2" -B "$build/dbow2" -DCMAKE_BUILD_TYPE=Release
cmake --build "$build/dbow2" --parallel 2
cmake --build "$build" --target ORB_SLAM3 --parallel 2
cmake -S "$here" -B "$build/worker" "-DORB_SOURCE=$orb" "-DPangolin_DIR=$pangolin"
cmake --build "$build/worker"
