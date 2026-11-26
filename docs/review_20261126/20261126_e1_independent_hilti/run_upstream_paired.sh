#!/usr/bin/env bash
set -eo pipefail
cd "$(dirname "$0")"
root="$PWD"
active=/home/tong/fastlio_repro_work_20261126/frozen/stream_1x_precropped
version=/home/tong/fastlio_repro_work_20261126/frozen/fastlio_stability_20261126/fallback
test -s UPSTREAM_TARGETS_BINARY.sha256
test -s upstream_campus12_smoke/OBSERVED.yaml
source /opt/ros/noetic/setup.bash
source "$version/ws/devel/setup.bash"
frozen=$(dirname "$active")
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$version:$frozen/fastlio_native_bridge_commit_20261125:$frozen/fastlio_fault_bridge_matrix_20261125:$frozen/rigid_ramp_bridge_20261125:$frozen/short_window_bridge_20261125:$frozen/ntuviral_fastlio_step5_20261125:$frozen/python:$PYTHONPATH"
export PYTHONPATH="$frozen/fastlio_rtp03_clock_retiming_20261126:$frozen/fastlio_rtp03_clock_confirmation_20261126:$frozen/fastlio_full_cycle_matrix_20261126:$frozen/fastlio_clock_return_edge_20261126:$PYTHONPATH"
python3 "$active/write_spms_paired_bag.py" "$root/SPMS_FAULT_PAIRED.bag" > SPMS_FAULT_PAIRED.json
sha256sum SPMS_FAULT_PAIRED.bag > SPMS_FAULT_PAIRED.sha256
bash upstream_runner_v2.sh spms
