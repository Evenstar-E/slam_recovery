#!/usr/bin/env bash
set -eo pipefail
cd "$(dirname "$0")"
source /opt/ros/noetic/setup.bash
for run in upstream_campus12_smoke upstream_spms_paired upstream_hilti_revisit; do
  if [[ ! -s "$run/SUMMARY.json" ]]; then
    python3 summarize_upstream.py "$run" > "$run/SUMMARY.json"
  fi
done
