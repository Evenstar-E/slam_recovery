#!/usr/bin/env bash
set -eo pipefail
release=$(realpath "${1:?path to frozen replay release}")
code=$(cd "$(dirname "$0")" && pwd)
cd "$release/clock_ingress_comparison"
cp "$code/score_clock_comparison.py" score_integrated.py
cp "$code/score_fallback_candidate.py" .
bash offline.sh score_fallback_candidate.py | tee CLOCK_FALLBACK_PILOT.json
python3 -c 'import json; raise SystemExit(not json.load(open("CLOCK_FALLBACK_PILOT.json"))["passed"])'
export LIO_CLOCK_READONLY_PREVIEW=1
for profile in z_shift rigid_ramp occlusion attenuation narrow_fov accept_drop rigid_occlusion sbs_clean; do
    name="fallback_$profile"
    rc=0
    bash run_fallback_case.sh "$name" "$profile" fallback || rc=$?
    if [[ -s "$name/finished_at.txt" && -s "$name/exit.txt" ]]; then
        bash offline.sh compact.py "$name"
    fi
    if [[ "$rc" != 0 ]]; then exit "$rc"; fi
done
bash offline.sh score_fallback_candidate.py matrix | tee CLOCK_FALLBACK_MATRIX.json
python3 -c 'import json; raise SystemExit(not json.load(open("CLOCK_FALLBACK_MATRIX.json"))["passed"])'
bash offline.sh score_integrated.py | tee CLOCK_INTEGRATED_COMPARISON.json
