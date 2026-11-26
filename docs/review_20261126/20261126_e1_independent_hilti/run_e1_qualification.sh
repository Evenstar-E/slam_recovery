#!/usr/bin/env bash
set -eo pipefail
cd "$(dirname "$0")"
score=/home/tong/fastlio_repro_work_20261126/frozen/stream_1x_precropped/spms_fault.json
for _ in {1..60}; do
  if [[ -s "$score" ]]; then
    bash build_upstream_targets.sh
    bash upstream_smoke.sh
    exit
  fi
  sleep 5
done
exit 3
