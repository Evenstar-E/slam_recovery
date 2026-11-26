#!/usr/bin/env bash
set -eo pipefail

source_root=${1:?path to archived WSL run parent}
source_repo=${2:?path to local slam_recovery checkout}
release=${3:?new release directory}
source_root=$(realpath "$source_root")
source_repo=$(realpath "$source_repo")
test "$(git -C "$source_repo" rev-parse HEAD)" = 738cc90e0a9da9d50d1f4300e58e056bbe7f79df
mkdir "$release"
release=$(realpath "$release")
v2=fastlio_stability_20261126/v2
matrix=fastlio_full_cycle_matrix_20261126
clock=fastlio_clock_return_edge_20261126
fixed=fastlio_closed_loop_acceptance_20261126
dirs=("$v2" campus12_step3_native_20261124 campus12_e1_ray_candidate_20261124
  campus12_native_counterfactual_20261125 fastlio_native_bridge_commit_20261125 fastlio_fault_bridge_matrix_20261125
  rigid_ramp_bridge_20261125 short_window_bridge_20261125 fastlio_mixed_recovery_20261125 ntuviral_fastlio_step5_20261125
  fastlio_rtp03_clock_retiming_20261126 fastlio_rtp03_clock_confirmation_20261126
  fastlio_rtp03_v2_acceptance_20261126 "$matrix" "$clock" "$fixed")

(cd "$source_root/$fixed" && sha256sum -c --quiet EXPERIMENT.sha256)
(cd "$source_root" && sha256sum -c --quiet "$fixed/SOURCE_BINDINGS.sha256")
(cd "$source_root/$v2" && sha256sum -c --quiet FREEZE.sha256 &&
  sha256sum -c --quiet HOST_SHA256 && sha256sum -c --quiet INPUTS.sha256)

for relative in "${dirs[@]}"; do
  mkdir -p "$release/$relative"
  find "$source_root/$relative" -maxdepth 1 -type f \( -name '*.py' -o -name '*.sh' \
    -o -name '*INPUTS.json' -o -name 'CASES.json' -o -name 'FIXTURES.json' \
    -o -name '*calibration.json' -o -name 'protocol.json' \) \
    -exec cp -t "$release/$relative" -- {} +
done

mkdir -p "$release/$v2/ws/src"
(
  cd "$source_root/$v2"
  while read -r hash path; do cp --parents -- "$path" "$release/$v2"; done < HOST_SHA256
  cp HOST_SHA256 INPUTS.sha256 ntulab.launch ntulab.yaml "$release/$v2"
)
mkdir -p "$release/$v2/ws/src/FAST-LIO/Log"
mkdir "$release/python"
(
  cd "$source_repo"
  git ls-files -co --exclude-standard -z -- ':(glob)slam_recovery/**/*.py' |
    tar --null -T - -cf - | tar -xf - -C "$release/python"
  git status --short -- slam_recovery > "$release/PYTHON_SOURCE_STATUS.txt"
)

for site in eee_03 sbs_02; do
  rel="ntuviral_fastlio_step5_20261125/$site"
  mkdir "$release/$rel"
  find "$source_root/$rel" -maxdepth 1 -type f \( -name '*.json' -o -name '*.txt' -o -name '*.csv' \) \
    -exec cp -t "$release/$rel" -- {} +
  ln -s "$source_root/$rel/study.bag" "$release/$rel/study.bag"
done
incoming=ntuviral_fastlio_step5_20261125/incoming
mkdir "$release/$incoming"
cp "$source_root/$incoming"/{eee_03,sbs_02}_gt.csv "$release/$incoming/"
for case in z_shift rigid_ramp occlusion attenuation narrow_fov sync accept_drop rigid_occlusion sync_narrow eee_clean sbs_clean; do
  cp -r "$source_root/$matrix/${case}_native" "$release/$matrix/"
done

cp "$source_root/$clock/FIXTURES.json" "$release/$clock/FIXTURES.json"
python3 - "$release/$clock/FIXTURES.json" "$release/$fixed/FIXTURES.json" <<'PY'
import json
import sys
from pathlib import Path

archived, matrix = (Path(path) for path in sys.argv[1:])
fixtures = json.loads(matrix.read_text())
clock = json.loads(archived.read_text())
for case, old_name in (("sync", "eee_clock"), ("sync_narrow", "sbs_clock_narrow")):
    fixtures[case] = clock[old_name]
matrix.write_text(json.dumps(fixtures, separators=(",", ":")) + "\n")
PY
sed -i 's|/home/tong/src/slam_recovery|$parent/python|g' "$release/$fixed/run_case.sh"
sed -i 's|/home/tong/src/slam_recovery|$base/python|g' "$release/$fixed/offline.sh"
sed -i 's/rigid_occlusion|eee_clean/rigid_occlusion|sync|sync_narrow|eee_clean/' "$release/$fixed/run_case.sh"
sed -i 's/^REUSED = .*/REUSED = {}/' "$release/$fixed/score_acceptance.py"
cp "$(dirname "$0")/replay.sh" "$release/replay.sh"
(
  cd "$release"
  dpkg-query -W -f='${Package}\t${Version}\n' > ENVIRONMENT.tsv
  find . -type f ! -name RELEASE.sha256 -print0 | LC_ALL=C sort -z | xargs -0 sha256sum > RELEASE.sha256
  tar --exclude='*/study.bag' -cf ../"$(basename "$release").tar" .
)
