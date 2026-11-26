#!/usr/bin/env bash
set -eo pipefail

release=$(realpath "${1:?path to frozen replay release}")
code=$(cd "$(dirname "$0")" && pwd)
root="$release/clock_ingress_comparison"
fixed="$release/fastlio_closed_loop_acceptance_20261126"
test -s "$fixed/RESULTS.json"
mkdir "$root"
cp "$fixed"/{FIXTURES.json,run_case.sh,run_return.py,stamp_log.py,offline.sh,compact.py} "$root"
cp "$code"/{clock_ingress_preview.py,score_clock_comparison.py} "$root"
cd "$root"
python3 - <<'PY'
from pathlib import Path

def replace(file, old, new):
    path = Path(file)
    contents = path.read_text()
    assert contents.count(old) == 1, (file, old)
    path.write_text(contents.replace(old, new))

replace("run_return.py", "def main(out, profile):",
        'def main(out, profile, *, controller=ReturnController, arm="return_edge"):')
replace("run_return.py", "ctl = ReturnController(out,imu)", "ctl = controller(out,imu)")
replace("run_return.py", 'arm="return_edge",\n            events=', 'arm=arm,\n            events=')
replace("run_case.sh", 'run_return.py "$out" "$2"', 'clock_ingress_preview.py "$out" "$2" "$3"')
replace("compact.py", '    fed=np.asarray([r["fed_ns"] for r in relay],dtype=np.int64)', '''    events=read(p/"events_result.jsonl")
    corrected={r["scan_ns"]:r["corrected_ns"] for r in events if r["action"]=="preview_retime"}
    fed=np.asarray([corrected.get(r["fed_ns"],r["fed_ns"]) for r in relay],dtype=np.int64)''')
replace("compact.py", '    events=read(p/"events_result.jsonl")\n    refused=',
        "    refused=")
PY
sha256sum *.py *.sh FIXTURES.json > COMPARISON_SOURCE.sha256
for arm in native preview; do
  rc=0
  bash run_case.sh "$arm" sync "$arm" || rc=$?
  if [[ -s "$arm/finished_at.txt" && -s "$arm/exit.txt" ]]; then
    bash offline.sh compact.py "$arm"
  fi
  if [[ "$rc" != 0 ]]; then exit "$rc"; fi
done
bash offline.sh score_clock_comparison.py | tee CLOCK_COMPARISON.json
