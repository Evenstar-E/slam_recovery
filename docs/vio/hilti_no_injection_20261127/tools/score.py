"""Read acknowledged public outputs and their independent 1x input clocks."""
from collections import Counter, defaultdict
import csv
from decimal import Decimal
import json
from pathlib import Path
import sys

import numpy as np


root = Path.home() / "vio-multiseq-20261127"
calibration = json.loads((root / "config/calibration.json").read_text())
body_camera = np.asarray(calibration["body_from_camera"][0])
states = ("isolate", "promote", "reject", "rearmed", "standby_ineligible", "standby_requalified",
          "standby_unavailable", "standby_qualification_lost", "standby_rebuilt", "native_checkpoint_saved")
sparse_names = {"exp01": "exp01_construction_ground_level",
                "exp04": "exp04_construction_upper_level",
                "exp05": "exp05_construction_upper_level_2"}


def read_jsonl(path):
    if not path.is_file():
        return []
    with path.open() as handle:
        return [json.loads(line) for line in handle]


def qstats(values):
    if not len(values):
        return {"n": 0}
    return dict(n=len(values), mean=float(np.mean(values)),
                p50=float(np.percentile(values, 50)), p95=float(np.percentile(values, 95)),
                p99=float(np.percentile(values, 99)), max=float(np.max(values)))


def rotation(quat):
    x, y, z, w = np.array(quat) / np.linalg.norm(quat)
    return np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                     [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                     [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])


def trajectory_position(row, pole_tip):
    p = row["pose_cw"]
    wc = rotation(p[3:]).T
    offset = -body_camera[:3, :3].T @ body_camera[:3, 3]
    if pole_tip:
        offset += body_camera[:3, :3].T @ np.array([.059, -.00855, .1964])
    return wc @ (offset - p[:3])


def fit(samples, ground_truth):
    if len(samples) < 3:
        return {"matched": len(samples)}, np.zeros(0)
    u = np.asarray(samples)
    v = np.asarray(ground_truth)
    uc, vc = u-u.mean(axis=0), v-v.mean(axis=0)
    left, singular, right = np.linalg.svd(uc.T @ vc)
    if np.count_nonzero(singular > 1e-8) < 2:
        return {"matched": len(samples), "alignment": "insufficient non-collinear geometry"}, np.zeros(0)
    sign = np.eye(3)
    sign[-1, -1] = np.linalg.det(left @ right)
    errors = np.linalg.norm(uc @ left @ sign @ right + v.mean(axis=0) - v, axis=1)
    return dict(matched=len(errors), rmse_m=float(np.sqrt(np.mean(errors**2))),
                error_m=qstats(errors)), errors


def interpolate(times, xyz, stamp, maximum_gap):
    i = int(np.searchsorted(times, stamp))
    if i < len(times) and times[i] == stamp:
        return xyz[i]
    if i == len(times) or i == 0 or times[i] - times[i-1] > maximum_gap:
        return None
    alpha = (stamp - times[i-1]) / (times[i] - times[i-1])
    return (1-alpha) * xyz[i-1] + alpha * xyz[i]


def load_reference(sequence):
    name = sparse_names.get(sequence)
    path = root / "config" / (f"{name}.txt" if name else f"{sequence}-reference.txt")
    rows = [line.split() for line in path.read_text().splitlines() if line.strip() and not line.startswith("#")]
    assert all(len(row) == 8 for row in rows)
    time = [int(Decimal(row[0]) * 10**9) for row in rows]
    assert all(a < b for a, b in zip(time, time[1:]))
    return np.asarray(time), np.asarray([[float(x) for x in row[1:4]] for row in rows])


def describe(run, receipt):
    sequence = receipt["sequence"]
    sparse = sequence in sparse_names
    ref_times, ref_xyz = load_reference(sequence)
    intake = read_jsonl(run / "log/input_clock.jsonl")
    events = read_jsonl(run / "log/events.jsonl")
    external = read_jsonl(run / "external.jsonl")
    resources = read_jsonl(run / "resources.jsonl")
    clock = {row["timestamp"]: row for row in intake}
    consumed = {row["timestamp"]: row for row in events if row["type"] == "consume"}
    public = {row["timestamp"]: row for row in external}
    verified = {t: row for t, row in public.items() if row["coordinate_verified"]}
    counts = Counter(row["type"] for row in events)
    tracking = Counter(str(row.get("tracking")) for row in events if row["type"] == "frame")
    latency = {t: (row["received_ns"]-clock[t]["arrival_ns"])/1e6 for t, row in public.items() if t in clock}
    from_due = [(row["received_ns"]-clock[t]["scheduled_ns"])/1e6 for t, row in public.items() if t in clock]
    stage = defaultdict(list)
    per_frame = defaultdict(dict)
    for row in events:
        t = row.get("timestamp")
        timings = {}
        if row["type"] == "stage":
            timings[row["stage"]] = row["elapsed_ns"]
        elif row["type"] == "native_stage" and row["role"] == "public":
            timings = {key: val for key, val in row.items() if key.endswith("_ns")}
        elif row["type"] == "input_prepared":
            timings = {k: row[k] for k in ("decode_ns", "detector_ns")}
        elif row["type"] == "consume":
            timings["consumer_wait_ns"] = row["consume_ns"] - row["arrival_ns"]
        for k, val in timings.items():
            stage[k].append(val/1e6)
            per_frame[t][k] = val/1e6
    included = verified
    times = np.asarray(sorted(included), dtype=np.int64)
    xyz = [trajectory_position(included[t], sparse) for t in times]
    matched = {}
    reference_population = []
    if sparse:
        reference_population = [int(t) for t in ref_times]
        for i, t in enumerate(ref_times):
            pos = interpolate(times, xyz, t, 250_000_000)
            if pos is not None:
                matched[int(t)] = (pos, ref_xyz[i])
    else:
        for t in clock:
            ref = interpolate(ref_times, ref_xyz, t, 150_000_000)
            if ref is not None:
                reference_population.append(t)
        for t, position in zip(times, xyz):
            ref = interpolate(ref_times, ref_xyz, t, 150_000_000)
            if ref is not None:
                matched[int(t)] = (position, ref)
    keys = sorted(matched)
    accuracy, error = fit([matched[t][0] for t in keys], [matched[t][1] for t in keys])
    accuracy.update(reference_count=len(reference_population), type="sparse_pole_tip" if sparse else "dense_imu")
    if not sparse:
        score = sum(bool(e <= .5 and 0 <= latency.get(t, float("inf")) <= 1000)
                    for t, e in zip(keys, error)) if len(error) else None
        accuracy["timely_accurate_1sec_half_meter"] = score

    input_summary = receipt.get("input_input_receipt", {})
    expected_start = input_summary.get("first_stamp_ns")
    expected_end = input_summary.get("last_stamp_ns")
    n = receipt["input_pairs"]
    observed_timestamps = sorted(clock)
    scheduled_full = len(observed_timestamps) == n and len(intake) == n
    start = min((r["scheduled_ns"] for r in intake), default=None)
    end = start + expected_end - expected_start if start is not None else None
    instants = [row["received_ns"] for row in external]
    delays = np.diff(instants) / 1e9
    no_output = {
        "leading_wall_s": (instants[0]-start)/1e9 if instants and start is not None else None,
        "maximum_internal_wall_s": float(max(delays)) if len(delays) else None,
        "trailing_in_planned_wall_s": max(0., (end-instants[-1])/1e9) if instants and end is not None else None,
        "tail_sensor_s": (expected_end - max(public))/1e9 if public else None,
        "max_sensor_gap_s": float(max(np.diff(sorted(public)))/1e9) if len(public) >= 2 else None,
        "entire_window_without_output_s": receipt["duration_s"] if not public and scheduled_full else None,
    }
    workers = [row for row in events if row["type"] == "worker_exit"]
    status = dict(controller_exit=receipt.get("controller_exit"), subscriber_exit=receipt.get("subscriber_exit"),
                  worker_exits=workers, harness_error=receipt.get("harness_error"),
                  input_faults=[r for r in events if r["type"] == "input_fault"],
                  requested_pairs=n, clocked_pairs=len(clock), scheduled_full=scheduled_full,
                  consumed_pairs=len(consumed), source_dropped=sum(not row["enqueued"] for row in intake),
                  tail_consumed_s=(expected_end-max(consumed))/1e9 if consumed else None,
                  public_pairs=len(public), verified_pairs=len(verified), ingestion_errors=counts["input_fault"],
                  modes=dict(Counter(x["channel"] for x in external)))
    cpu_totals = {}
    for row in resources:
        for key, val in row["cpu_s_by_pid"].items():
            cpu_totals[key] = max(val, cpu_totals.get(key, 0))
    report = dict(status=status, latency_ms=qstats(list(latency.values())), latency_from_due_ms=qstats(from_due),
                  stage_ms={key: qstats(values) for key, values in stage.items()}, accuracy=accuracy,
                  timely_public_1sec=sum(0 <= value <= 1000 for value in latency.values()),
                  timely_verified_1sec=sum(0 <= latency.get(t, float("inf")) <= 1000 for t in verified),
                  no_output=no_output, lifecycle={key: counts[key] for key in states},
                  orb_tracking_states=tracking,
                  peak_sum_rss_mib=max((r["process_tree_rss_bytes"] / 2**20 for r in resources), default=None),
                  sampled_process_tree_cpu_s=sum(cpu_totals.values()) if resources else None,
                  wall_s=receipt["wall_elapsed_s"],
                  release_lateness_ms=qstats([(r["arrival_ns"]-r["scheduled_ns"])/1e6 for r in intake]))
    if clock:
        fields = sorted(stage)
        with (run / "per_frame.csv").open("w", newline="") as stream:
            cols = ["timestamp_ns", "input_enqueued", "consumed", "external_public", "coordinate_verified",
                    "external_latency_ms", *[f"{key}_ms" for key in fields]]
            writer = csv.writer(stream)
            writer.writerow(cols)
            for t in observed_timestamps:
                writer.writerow([t, int(clock[t]["enqueued"]), int(t in consumed), int(t in public),
                                 int(t in verified), latency.get(t), *[per_frame[t].get(k) for k in fields]])
    return report, matched, clock, per_frame, latency


def main():
    sequence = sys.argv[1]
    suffixes = {"orb": "-startup-fixed", "vins": "-startup-fixed", "okvis": ""} if sequence == "exp18" else {}
    report, all_matches = {}, {}
    for kind in ("orb", "vins", "okvis"):
        all_arms, matches, clocks, stages, latencies = {}, {}, {}, {}, {}
        for mode in ("native", "recover"):
            run = root / "results" / f"{sequence}-{kind}-{mode}{suffixes.get(kind, '')}"
            receipt = run / "result.json"
            if receipt.is_file():
                all_arms[mode], matches[mode], clocks[mode], stages[mode], latencies[mode] = describe(
                    run, json.loads(receipt.read_text()))
                all_matches[f'{kind}-{mode}'] = matches[mode]
        result = dict(arms=all_arms)
        if len(all_arms) == 2:
            common = sorted(matches["native"].keys() & matches["recover"].keys())
            result["common_accuracy"] = {
                mode: fit([matched[t][0] for t in common], [matched[t][1] for t in common])[0]
                for mode, matched in matches.items()}
            keys = set(clocks["native"]) & set(clocks["recover"])
            result["paired_input"] = dict(common_clocked=len(keys), digest_match=all(
                clocks["native"][t]["image_sha256"] == clocks["recover"][t]["image_sha256"]
                and clocks["native"][t]["imu_count"] == clocks["recover"][t]["imu_count"] for t in keys))
            rows = stages["native"]
            paired_delta = defaultdict(list)
            for t, values in stages["recover"].items():
                for k, v in values.items():
                    if k in rows.get(t, {}):
                        paired_delta[k].append(v - rows[t][k])
            result["same_frame_delta_ms"] = {k: qstats(x) for k, x in paired_delta.items()}
            keys = latencies["native"].keys() & latencies["recover"].keys()
            result["same_frame_delta_ms"]["external_latency"] = qstats([
                latencies["recover"][t] - latencies["native"][t] for t in keys])
        report[kind] = result
    if len(all_matches) == 6:
        common = sorted(set.intersection(*(set(m) for m in all_matches.values())))
        report["six_way_common_accuracy"] = {
            label: fit([m[t][0] for t in common], [m[t][1] for t in common])[0]
            for label, m in all_matches.items()}
    summary = root / "receipts" / f"{sequence}-score.json"
    temp = summary.with_suffix(".tmp")
    temp.write_text(json.dumps(report, indent=2, allow_nan=False, default=lambda x: x.item()))
    temp.replace(summary)


if __name__ == "__main__":
    main()
