#!/usr/bin/env bash
set -eo pipefail
cd "$(dirname "$0")"
source /opt/ros/noetic/setup.bash
private="$(realpath scipy-root)/usr/lib"
export OPENBLAS_NUM_THREADS=1
export PYTHONPATH="$private/python3/dist-packages:$PYTHONPATH"
export LD_LIBRARY_PATH="$private/x86_64-linux-gnu:$LD_LIBRARY_PATH"
python3 qualify_hilti_geometry.py "${1:-hilti_geometry_scored}"
