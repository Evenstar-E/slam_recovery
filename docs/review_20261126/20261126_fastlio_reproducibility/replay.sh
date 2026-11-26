#!/usr/bin/env bash
set -eo pipefail
cd "$(dirname "$0")"

case "${1:-}" in
  build)
    sha256sum -c --quiet RELEASE.sha256
    source /opt/ros/noetic/setup.bash
    mkdir -p fastlio_stability_20261126/v2/ws/src/FAST-LIO/Log
    catkin_init_workspace fastlio_stability_20261126/v2/ws/src
    bash fastlio_stability_20261126/v2/build.sh
    ;;
  pilot|matrix)
    sha256sum -c --quiet RELEASE.sha256
    (
      cd fastlio_stability_20261126/v2
      sha256sum -c --quiet INPUTS.sha256
    )
    cd fastlio_closed_loop_acceptance_20261126
    if [[ "$1" = pilot ]]; then
      cases=(accept_drop sync_narrow eee_clean)
    else
      cases=(z_shift rigid_ramp occlusion attenuation narrow_fov sync accept_drop rigid_occlusion sync_narrow eee_clean sbs_clean)
    fi
    for profile in "${cases[@]}"; do
      if [[ -s "$profile/receipt.json" ]]; then
        python3 -c 'import json, sys; sys.exit(json.load(open(sys.argv[1]))["code"] != 0)' "$profile/receipt.json"
        continue
      fi
      status=0
      started=$(date -Is)
      bash run_case.sh "$profile" "$profile" || status=$?
      printf '%s %s %s %s\n' "$profile" "$status" "$started" "$(date -Is)" >> REPLAY_STATUS.txt
      if [[ -s "$profile/finished_at.txt" && -s "$profile/exit.txt" ]]; then
        bash offline.sh compact.py "$profile"
      fi
      if [[ "$status" != 0 ]]; then exit "$status"; fi
    done
    if [[ "$1" = matrix ]]; then bash offline.sh score_acceptance.py; fi
    ;;
  *)
    printf 'Usage: bash replay.sh {build|pilot|matrix}\n' >&2
    exit 2
    ;;
esac
