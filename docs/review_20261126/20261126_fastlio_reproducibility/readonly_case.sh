#!/usr/bin/env bash
set -eo pipefail

release=$(realpath "${1:?path to frozen replay release}")
code=$(cd "$(dirname "$0")" && pwd)
root="$release/clock_ingress_comparison"
readonly_host="$release/fastlio_stability_20261126/readonly"
frozen_host="$release/fastlio_stability_20261126/v2"
test -s "$root/CLOCK_COMPARISON.json"
mkdir "$readonly_host"
(
    cd "$frozen_host"
    sha256sum -c --quiet HOST_SHA256
    while read -r hash path; do cp --parents -- "$path" "$readonly_host"; done < HOST_SHA256
    cp build.sh ntulab.launch ntulab.yaml "$readonly_host"
)
mkdir -p "$readonly_host/ws/src/FAST-LIO/Log"
python3 "$code/patch_readonly_host.py" "$readonly_host/ws/src/FAST-LIO/src/laserMapping.cpp"
sha256sum "$readonly_host/ws/src/FAST-LIO/src/laserMapping.cpp" > "$readonly_host/PATCHED_HOST.sha256"
source /opt/ros/noetic/setup.bash
catkin_init_workspace "$readonly_host/ws/src"
bash "$readonly_host/build.sh"
cd "$root"
mkdir readonly_version
cp "$code/clock_ingress_preview.py" readonly_version/
cp run_return.py FIXTURES.json readonly_version/
sed 's|fastlio_stability_20261126/v2|fastlio_stability_20261126/readonly|; s|clock_ingress_preview.py "$out"|readonly_version/clock_ingress_preview.py "$out"|' run_case.sh > run_readonly_case.sh
cp "$frozen_host/mixed_controller.py" "$readonly_host/"
export LIO_CLOCK_READONLY_PREVIEW=1
rc=0
bash run_readonly_case.sh readonly sync readonly || rc=$?
if [[ -s readonly/finished_at.txt && -s readonly/exit.txt ]]; then
    bash offline.sh compact.py readonly
fi
if [[ "$rc" != 0 ]]; then exit "$rc"; fi
cp "$code/score_clock_comparison.py" score_readonly_comparison.py
bash offline.sh score_readonly_comparison.py | tee CLOCK_READONLY_COMPARISON.json
