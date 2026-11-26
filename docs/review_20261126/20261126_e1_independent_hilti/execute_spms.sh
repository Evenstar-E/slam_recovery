#!/usr/bin/env bash
set -eo pipefail
cd "$(dirname "$0")"
source /opt/ros/noetic/setup.bash
if [[ ! -s spms_02/CLIP.json ]]; then
  python3 freeze_spms_window.py
fi
export STREAM_ROUND=stream_1x_precropped
bash run_stream.sh spms_clean spms_fault
