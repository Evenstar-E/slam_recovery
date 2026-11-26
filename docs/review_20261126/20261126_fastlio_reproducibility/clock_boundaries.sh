#!/usr/bin/env bash
set -eo pipefail

release=$(realpath "${1:?path to frozen replay release}")
cd "$release/clock_ingress_comparison"
test -s CLOCK_READONLY_COMPARISON.json
export LIO_CLOCK_READONLY_PREVIEW=1
for profile in eee_clean sync_narrow; do
    name="readonly_$profile"
    rc=0
    bash run_readonly_case.sh "$name" "$profile" readonly || rc=$?
    if [[ -s "$name/finished_at.txt" && -s "$name/exit.txt" ]]; then
        bash offline.sh compact.py "$name"
    fi
    if [[ "$rc" != 0 ]]; then exit "$rc"; fi
done
python3 - <<'PY' | tee CLOCK_BOUNDARIES.json
import json
from pathlib import Path

fixtures = json.loads(Path("FIXTURES.json").read_text())
result = {}
for profile in ("eee_clean", "sync_narrow"):
    case = Path("readonly_" + profile)
    receipt = json.loads((case / "receipt.json").read_text())
    trajectory = json.loads((case / "trajectory.json").read_text())
    expected = fixtures[profile]["input"]["inputs"]
    identities = [{key: row[key] for key in expected[0]} for row in trajectory["input_identities"]]
    events = receipt["events"]
    stops = [e for e in events if e["action"] == "preview_stopped"]
    first_fault = {row["fed_ns"] for row in expected if row["event"] == 1}
    second_fault = {row["fed_ns"] for row in expected if row["event"] == 2}
    corrected = [e["scan_ns"] for e in events if e["action"] == "preview_retime"]
    result[profile] = {
        "exit": receipt["code"], "exact_inputs": identities == expected,
        "public": receipt["public"], "increasing": receipt["public_increasing"],
        "corrected": len(corrected), "first_fault_correction_exact": (
            set(corrected) == first_fault and len(corrected) == len(first_fault)
        ),
        "stops": stops,
        "map_evidence": [e for e in events if e["action"] == "preview_readonly_map_verified"],
        "stopped_during_second_fault": len(stops) == 1 and stops[0]["scan_ns"] in second_fault,
        "mode": (receipt["final"] or {}).get("mode"),
    }
print(json.dumps(result, indent=2))
PY
