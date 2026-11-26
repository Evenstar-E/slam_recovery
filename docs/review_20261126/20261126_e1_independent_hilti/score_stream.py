"""Score the fixed-rate source and the observable outputs separately."""
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "fastlio_full_cycle_matrix_20261126"))
from score_matrix import base

NS = 1_000_000_000


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()] if path.is_file() else []


def p95(values):
    return float(np.quantile(values, .95)) if values else None


def load(profile, arm):
    name = f"{profile}_{arm}"
    src = ROOT / (name + "_ingress")
    producer = rows(src / "producer.jsonl")
    imu = rows(src / "imu_arrival.jsonl")
    draws = rows(src / "memory.jsonl")
    case = ROOT / name
    receipt = base.read(case / "receipt.json")
    trace = base.read(case / "telemetry.json")
    track = base.read(case / "trajectory.json")
    corrections = {e["scan_ns"]: e["corrected_ns"] for e in receipt["events"]
                   if e["action"] == "preview_retime"}
    relay = track["input_identities"]
    public, unbound = base.frame_bind(
        dict(trace, fates=[dict(r, fate="ingested") if r["fate"] == "quarantined" else r
                           for r in trace["fates"]]),
        [dict(r, fed_ns=corrections.get(r["fed_ns"], r["fed_ns"])) for r in relay])
    feed = dict(trace["feeds"])
    delays = [(feed[r["stamp_ns"]] - r["received_wall_ns"]) / 1e6 for r in producer
              if r["stamp_ns"] in feed]
    arrivals = {r["stamp_ns"]: r["received_wall_ns"] for r in producer}
    publish_latency = [(r["wall_ns"] - arrivals[k]) / 1e6 for k, r in public.items()
                       if k in arrivals]
    health = base.historical_native_phase(trace)
    reset = [r for r in health if r["kind"] in ("native_imu_reset", "native_re_slam")]
    result = dict(
        exit=receipt["code"], source_scans=len(producer), controller_scans=len(relay),
        source_drops=sum(r["dropped"] for r in producer), imu_arrivals=len(imu),
        peak_queued_scans=max((r["depth"] for r in producer), default=None),
        lidar_deadline_lateness_p95_ms=p95([(r["received_wall_ns"] - r["deadline_ns"]) / 1e6
                                            for r in producer]),
        imu_deadline_lateness_p95_ms=p95([(r[2]-r[1]) / 1e6 for r in imu]),
        queue_delay_p95_ms=p95(delays), queue_delay_max_ms=max(delays, default=None),
        publication_latency_p95_ms=p95(publish_latency), public=len(public),
        unbound_public=len(unbound), output_monotonic=receipt["public_increasing"],
        peak_pss_and_swap_mib=max((sum(sum(mem.values()) for mem in r["pid_kib"].values()) / 1024
                                   for r in draws), default=None),
        reset_markers=reset, corrected_scans=len(corrections),
        transitions=[e["action"] for e in receipt["events"] if e["action"] in
                     ("preview_readonly_map_verified", "preview_native_fallback", "triggered",
                      "refused_caught_up_released", "committed_released", "rearmed", "preview_stopped")],
        map_evidence=[e for e in receipt["events"] if e["action"] == "preview_readonly_map_verified"],
        preview_stops=[e for e in receipt["events"] if e["action"] == "preview_stopped"])
    end = receipt["final"] or {}
    reports = []
    for event in end.get("windows", []):
        begin, finish = event["onset_ns"], event["end_ns"]
        physical = [r["stamp_ns"] for r in producer if r["event"] == event["id"]]
        during = [k for k in physical if k in public]
        before = max((k for k in public if k < begin), default=begin)
        after = min((k for k in public if k >= finish), default=None)
        marks = [before] + during + [after if after is not None else finish]
        source_gaps = max(np.diff(marks), default=0)
        reports.append(dict(id=event["id"], kind=event["kind"], input=len(physical),
                            public=len(during), gap_data_seconds=float(source_gaps) / NS,
                            after_fault_s=(after - finish) / NS if after is not None else None,
                            historical_api_delivered=0))
    result["events"] = reports
    result["final_mode"] = end.get("mode")
    key = ("stamp_ns", "fed_ns", "event", "sha256")
    return result, [tuple(r[k] for k in key) for r in producer], [tuple(r[i] for i in (0, 3)) for r in imu]


def main(profile):
    native, scans, imu = load(profile, "native")
    plugin, other_scans, other_imu = load(profile, "plugin")
    print(json.dumps(dict(profile=profile, rate=1, recovery_controls_source_clock=False,
                         same_lidar=bool(scans) and scans == other_scans,
                         same_imu=bool(imu) and imu == other_imu,
                         native=native, plugin=plugin), indent=2, allow_nan=False))


if __name__ == "__main__":
    main(sys.argv[1])
