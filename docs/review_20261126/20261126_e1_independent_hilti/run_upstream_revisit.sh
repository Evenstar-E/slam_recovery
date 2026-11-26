#!/usr/bin/env bash
set -eo pipefail
cd "$(dirname "$0")"
source /opt/ros/noetic/setup.bash
frozen=/home/tong/fastlio_repro_work_20261126/frozen
export PYTHONPATH="$frozen/python:$PYTHONPATH"
export OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
python3 write_hilti_revisit_bag.py HILTI_REVISIT.bag > HILTI_REVISIT.json
sha256sum HILTI_REVISIT.bag > HILTI_REVISIT.sha256
bash upstream_runner_v3.sh hilti_revisit
