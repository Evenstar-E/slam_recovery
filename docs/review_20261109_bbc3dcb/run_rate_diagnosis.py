#!/usr/bin/env python3
"""Short-rate diagnosis: why does the host publish odometry at ~7.5 Hz in two stretches?

One short run of the hardened runner over a 30 s clip that contains both stretches where the C3
re-run published no usable pose (1627785275.808-1627785285.226 and 1627785295.246-1627785295.446)
and the healthy segments on either side.  Same input, same fault severity, same 0.5x playback; the
75 ms pairing rule is not touched.

Collected:
  1. the /aft_mapped_to_init publish-interval series, so the 133 ms stretches are measured rather
     than inferred;
  2. the node log timings;
  3. input arrival intervals for /velodyne_points and /handsfree/imu -- if the input has holes in
     the same stretches, the cause is input, not the host;
  4. load average and the node's CPU time, so scheduling starvation can be excluded or confirmed;
  5. the runner's receipt (pre-run hashes, output hash, coverage, exit status).

    python3 -B docs/review_20261109_bbc3dcb/run_rate_diagnosis.py
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_HERE))
for _p in (_HERE, _REPO):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import verify_four_arm_independent as V          # noqa: E402

CLIP = "/tmp/fastlivo/rate_diag_clip.bag"
OUT = "/tmp/fastlivo/rate_diag_out.bag"
RESOURCE_LOG = "/tmp/rate_diag_resource.log"
RUN_LOG = "/tmp/rate_diag_run.log"
RESULT_JSON = os.path.join(_HERE, "rate_diagnosis_results.json")

SEGMENTS = [(1627785275.808, 1627785285.226), (1627785295.246, 1627785295.446)]
TOPICS = {"/velodyne_points": "lidar", "/handsfree/imu": "imu",
          "/aft_mapped_to_init": "odom"}


def _stamps(path, topic):
    ts = []
    with V.Reader(path) as r:
        conns = [c for c in r.connections if c.topic == topic]
        for conn, _t, raw in r.messages(connections=conns):
            m = V.TYPESTORE.deserialize_ros1(raw, conn.msgtype)
            ts.append(m.header.stamp.sec + m.header.stamp.nanosec * 1e-9)
    return np.asarray(sorted(ts))


HOLE_MS = 50.0     # a gap this long is a missing message, not jitter


def _intervals(ts):
    d = np.diff(ts)
    med = float(np.median(d)) if len(d) else 0.0
    hole = max(2.0 * med, HOLE_MS / 1e3)
    return {"n": int(len(ts)),
            "median_ms": float(med * 1e3) if len(d) else None,
            "p95_ms": float(np.percentile(d, 95) * 1e3) if len(d) else None,
            "max_ms": float(d.max() * 1e3) if len(d) else None,
            "n_over_1.5x_median": int((d > 1.5 * med).sum()) if len(d) else 0,
            "hole_definition_ms": round(hole * 1e3, 2),
            "n_holes": int((d > hole).sum()) if len(d) else 0,
            "hole_times": [float(ts[i + 1]) for i in np.flatnonzero(d > hole)][:40]}


def _segment_stats(ts, lo, hi):
    m = (ts >= lo) & (ts <= hi)
    inside = np.diff(ts[m]) if m.sum() > 1 else np.zeros(0)
    # The neighbours are two disjoint stretches, so their intervals must be computed
    # separately. Concatenating the samples first and then diffing invents an interval that
    # spans the fault window: ts=[0,.066,1,1.066,2,2.066] with fault=[.9,1.1] would yield
    # [.066, 1.934, .066] and report a 1/3 slow fraction from two 66 ms gaps.
    left = ts[(ts >= lo - 15.0) & (ts < lo)]
    right = ts[(ts > hi) & (ts <= hi + 15.0)]
    outside = np.concatenate([np.diff(left) if len(left) > 1 else np.zeros(0),
                              np.diff(right) if len(right) > 1 else np.zeros(0)])
    slow = inside > 0.100 if len(inside) else np.zeros(0, bool)   # 133 ms = a skipped publish
    return {"n_inside": int(m.sum()),
            "median_ms_inside": float(np.median(inside) * 1e3) if len(inside) else None,
            "median_ms_neighbours": float(np.median(outside) * 1e3) if len(outside) else None,
            "max_ms_inside": float(inside.max() * 1e3) if len(inside) else None,
            "slow_interval_fraction_inside": float(slow.mean()) if len(slow) else None,
            "slow_interval_fraction_neighbours": (float((outside > 0.100).mean())
                                                  if len(outside) else None)}


def _parse_node_log(path):
    if not os.path.exists(path):
        return {"status": "MISSING"}
    txt = open(path, errors="ignore").read()
    totals = [float(x) for x in re.findall(r"Current Total Time\s*\|\s*([0-9.]+)", txt)]
    icp = [float(x) for x in re.findall(r"\|\s*ICP\s*\|\s*([0-9.]+)", txt)]
    return {"bytes": len(txt), "frames_logged": len(totals),
            "total_time_median_s": float(np.median(totals)) if totals else None,
            "total_time_p95_s": float(np.percentile(totals, 95)) if totals else None,
            "total_time_max_s": float(max(totals)) if totals else None,
            "icp_median_s": float(np.median(icp)) if icp else None,
            "above_frame_budget": int(sum(1 for x in totals if x > 0.1)),
            "note": "frame budget at 10 Hz is 0.100 s"}


def _parse_resources(path):
    if not os.path.exists(path):
        return {"status": "MISSING"}
    loads, cpu = [], []
    prev = None
    for line in open(path):
        if line.startswith("  pid"):
            f = line.split()
            try:
                j = int(f[3]) + int(f[5])          # utime + stime in clock ticks
            except Exception:
                continue
            if prev is not None:
                cpu.append((j - prev) / 100.0)     # seconds of CPU per sample
            prev = j
        else:
            m = re.search(r"load=([\d.]+)", line)
            if m:
                loads.append(float(m.group(1)))
    return {"samples": len(loads),
            "load1_min": min(loads) if loads else None,
            "load1_median": float(np.median(loads)) if loads else None,
            "load1_max": max(loads) if loads else None,
            "cpu_sec_per_sample_median": float(np.median(cpu)) if cpu else None,
            "cpu_sec_per_sample_max": max(cpu) if cpu else None,
            "note": "sampled every 2 s; cpu = utime+stime deltas of fastlivo_mapping"}


def main():
    res = {"inputs": {"clip": CLIP, "clip_sha256": V._sha_file(CLIP),
                      "output": OUT, "output_sha256": V._sha_file(OUT)},
           "segments": [{"start": a, "end": b} for a, b in SEGMENTS],
           "runs": {}}

    for tag, path, topic in (("lidar", CLIP, "/velodyne_points"),
                             ("imu", CLIP, "/handsfree/imu"),
                             ("odom_out", OUT, "/aft_mapped_to_init")):
        if not os.path.exists(path):
            res["runs"][tag] = {"status": "MISSING"}
            continue
        ts = _stamps(path, topic)
        res["runs"][tag] = {"series": _intervals(ts),
                            "per_segment": [_segment_stats(ts, a, b) for a, b in SEGMENTS],
                            "first": float(ts.min()) if len(ts) else None,
                            "last": float(ts.max()) if len(ts) else None}

    node_log = None
    if os.path.exists(RUN_LOG):
        m = re.search(r"/tmp/fl_run_[0-9TZ_]+", open(RUN_LOG, errors="ignore").read())
        if m:
            rd = m.group(0)
            node_log = os.path.join(rd, "node.log")
            res["run_dir"] = rd
            rj = os.path.join(rd, "receipt.json")
            if os.path.exists(rj):
                res["receipt"] = json.load(open(rj))
    res["node"] = _parse_node_log(node_log or "")
    res["resources"] = _parse_resources(RESOURCE_LOG)

    # ---- judgement ------------------------------------------------------------------------
    lid = res["runs"].get("lidar", {}).get("series", {})
    imu = res["runs"].get("imu", {}).get("series", {})
    od = res["runs"].get("odom_out", {}).get("series", {})
    holes_input = (lid.get("n_holes", 0) > 0 or imu.get("n_holes", 0) > 0)
    od_slow = (od.get("n_over_1.5x_median", 0) > 0)
    load_med = res["resources"].get("load1_median")
    cpu_med = res["resources"].get("cpu_sec_per_sample_median")
    node_budget = res["node"].get("above_frame_budget", 0)

    if holes_input:
        verdict = "INPUT_HOLES"
        why = ("the input streams themselves have gaps longer than 1.5x their median inside the "
               "clip")
    elif load_med is not None and load_med >= (os.cpu_count() or 1) and od_slow:
        # Load average counts runnable and uninterruptible tasks and says nothing about the
        # runnable wait itself; low CPU use can also come from sync, IO or blocking. Without a
        # same-prefix low-load control this is a correlation, not a cause.
        verdict = "CONTENTION_SUSPECTED"
        why = (f"the host skipped publications while its inputs were continuous; load average was "
               f"{load_med} against {os.cpu_count()} cores. That is a candidate mechanism, not a "
               f"runnable-wait measurement; a same-prefix low-load control is required")
    elif load_med is not None and load_med >= (os.cpu_count() or 1):
        verdict = "RESOURCE_LOAD_HIGH_NO_PUBLICATION_STRETCH"
        why = (f"load average was {load_med} against {os.cpu_count()} cores but the odometry "
               f"cadence did not stretch inside the clip")
    elif od_slow and not holes_input:
        verdict = "INTERNAL (input continuous, host publishes slower)"
        why = ("the LiDAR and IMU arrive at their normal cadence while /aft_mapped_to_init "
               "stretches to the 133 ms cadence; that is the host dropping publications, not a "
               "missing input")
    else:
        verdict = "NO_ANOMALY_REPRODUCED"
        why = "the clip did not reproduce the slow stretches"

    res["judgement"] = {
        "verdict": verdict, "reason": why,
        "input_holes_detected": bool(holes_input),
        "odom_stretch_detected": bool(od_slow),
        "load_median": load_med,
        "n_cpu": os.cpu_count(),
        "cpu_sec_per_sample_median": cpu_med,
        "node_frames_over_100ms_budget": node_budget,
        "segment_comparison": [
            {"segment": i, "odom_ms_inside": res["runs"].get("odom_out", {})
             .get("per_segment", [{}] * 2)[i].get("median_ms_inside"),
             "odom_ms_neighbours": res["runs"].get("odom_out", {})
             .get("per_segment", [{}] * 2)[i].get("median_ms_neighbours"),
             "lidar_ms_inside": res["runs"].get("lidar", {})
             .get("per_segment", [{}] * 2)[i].get("median_ms_inside"),
             "imu_ms_inside": res["runs"].get("imu", {})
             .get("per_segment", [{}] * 2)[i].get("median_ms_inside"),
             "slow_fraction_inside": res["runs"].get("odom_out", {})
             .get("per_segment", [{}] * 2)[i].get("slow_interval_fraction_inside"),
             "slow_fraction_neighbours": res["runs"].get("odom_out", {})
             .get("per_segment", [{}] * 2)[i].get("slow_interval_fraction_neighbours")}
            for i in range(len(SEGMENTS))],
    }
    with open(RESULT_JSON, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=float)
    print(json.dumps(res["judgement"], indent=1))
    print(f"saved {RESULT_JSON}")


if __name__ == "__main__":
    main()
