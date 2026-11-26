#!/usr/bin/env bash
set -eo pipefail

release=$(realpath "${1:?path to frozen replay release}")
code=$(cd "$(dirname "$0")" && pwd)
root="$release/clock_ingress_comparison"
frozen_host="$release/fastlio_stability_20261126/v2"
host="$release/fastlio_stability_20261126/fallback"
test -s "$root/CLOCK_BOUNDARIES.json"
mkdir "$host"
(
    cd "$frozen_host"
    sha256sum -c --quiet HOST_SHA256
    while read -r hash path; do cp --parents -- "$path" "$host"; done < HOST_SHA256
    cp build.sh ntulab.launch ntulab.yaml mixed_controller.py "$host"
)
mkdir -p "$host/ws/src/FAST-LIO/Log"
host_source="$host/ws/src/FAST-LIO/src/laserMapping.cpp"
python3 "$code/patch_readonly_host.py" "$host_source"
python3 "$code/patch_clock_fallback.py" "$host_source"
sha256sum "$host_source" > "$host/PATCHED_HOST.sha256"
source /opt/ros/noetic/setup.bash
catkin_init_workspace "$host/ws/src"
bash "$host/build.sh"
cd "$root"
mkdir fallback_version
cp "$code/clock_ingress_preview.py" fallback_version/
cp run_return.py FIXTURES.json fallback_version/
sed 's|fastlio_stability_20261126/readonly|fastlio_stability_20261126/fallback|; s|readonly_version/|fallback_version/|' run_readonly_case.sh > run_fallback_case.sh
export LIO_CLOCK_READONLY_PREVIEW=1
for profile in sync sync_narrow eee_clean; do
    name="fallback_$profile"
    rc=0
    bash run_fallback_case.sh "$name" "$profile" fallback || rc=$?
    if [[ -s "$name/finished_at.txt" && -s "$name/exit.txt" ]]; then
        bash offline.sh compact.py "$name"
    fi
    if [[ "$rc" != 0 ]]; then exit "$rc"; fi
done
