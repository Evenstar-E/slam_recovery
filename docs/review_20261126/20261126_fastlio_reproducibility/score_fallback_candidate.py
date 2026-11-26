"""Check the clock lane and the original geometry recovery in one native process."""
import json
import sys

from score_integrated import ROOT, load


sys.path.insert(0, str(ROOT.parent / "fastlio_closed_loop_acceptance_20261126"))
from score_acceptance import RUN_ORDER, event_check


def main(profiles):
    fixtures = json.loads((ROOT / "FIXTURES.json").read_text())
    result = {}
    for name in profiles:
        fixture = fixtures[name]["input"]
        expected = fixture["inputs"]
        data = load(ROOT, f"fallback_{name}", expected)
        receipt = data["receipt"]
        events = receipt["events"]
        retimed = [e["scan_ns"] for e in events if e["action"] == "preview_retime"]
        clock_ids = {window["id"] for window in fixture["windows"] if window["kind"] == "sync"}
        expected_clock = {row["fed_ns"] for row in expected if row["event"] in clock_ids}
        map_checks = [e for e in events if e["action"] == "preview_readonly_map_verified"]
        stopped = [e for e in events if e["action"] == "preview_stopped"]
        verdict = {
            "exit": receipt["code"],
            "inputs_exact": data["complete_input"],
            "public": len(data["public"]),
            "public_increasing": receipt["public_increasing"],
            "unbound_public": len(data["unbound"]),
            "final_mode": (receipt["final"] or {}).get("mode"),
            "retimed": len(retimed),
            "exact_clock_population": len(retimed) == len(expected_clock) and set(retimed) == expected_clock,
            "map_evidence": map_checks,
            "preview_stops": stopped,
            "fallback_requests": [e for e in events if e["action"] == "preview_native_fallback"],
        }
        verdict["events"] = []
        for window in fixture["windows"]:
            if window["kind"] == "sync" and verdict["exact_clock_population"] and retimed:
                slots = {row["stamp_ns"] for row in expected if row["event"] == window["id"]}
                released = [key for key in data["public"] if key >= window["end_ns"]]
                verdict["events"].append({
                    "kind": window["kind"],
                    "lane": "readonly_clock",
                    "fault_output_coverage": len(slots & data["public"].keys()),
                    "clock_exact": len(retimed) == len(slots),
                    "full_pass": bool(
                        slots <= data["public"].keys() and released and len(map_checks) == 1
                        and map_checks[0]["unchanged"] and not stopped
                    ),
                })
            else:
                begin = window["onset_ns"]
                geometry_events = [
                    e for e in events
                    if e["action"] not in ("clock_confirmed", "sensor_clock_frame")
                    or e["scan_ns"] >= begin
                ]
                geometry_data = dict(data, receipt=dict(receipt, events=geometry_events))
                verdict["events"].append(event_check(geometry_data, window, expected))
        if not fixture["windows"]:
            frozen = load(ROOT.parent / "fastlio_closed_loop_acceptance_20261126", name, expected)
            verdict["clean_pass"] = (data["public"].keys() == frozen["public"].keys()
                                     and not retimed and not stopped and not verdict["fallback_requests"])
        verdict["passed"] = (
            verdict["exit"] == 0 and verdict["inputs_exact"] and verdict["public_increasing"]
            and verdict["unbound_public"] == 0 and verdict["final_mode"] == "ARMED"
            and verdict.get("clean_pass", True) and all(row["full_pass"] for row in verdict["events"])
        )
        result[name] = verdict
    print(json.dumps({"passed": all(row["passed"] for row in result.values()), "cases": result},
                     indent=2, allow_nan=False))


if __name__ == "__main__":
    main(RUN_ORDER if sys.argv[1:] == ["matrix"] else ("sync", "sync_narrow", "eee_clean"))
