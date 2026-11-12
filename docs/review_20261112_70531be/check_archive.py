"""Read only pinned Git archive blobs; never import or execute archived code.
Run with python -I. Optional --output writes only this audit's compact JSON.
"""
import argparse
import collections
import gzip
import hashlib
import json
import math
import statistics
import subprocess
from pathlib import Path

TARGET = "70531bef27467519e370ac4819609398f1933533"
PREFIX = "docs/review_20261112_availability/"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()

    def blob(name):
        return subprocess.check_output(
            ["git", "-C", args.repo, "show", TARGET + ":" + PREFIX + name]
        )

    names = subprocess.check_output(
        ["git", "-C", args.repo, "ls-tree", "--name-only", TARGET + ":" + PREFIX.rstrip("/")]
    ).decode().splitlines()
    manifest = {}
    for line in blob("SHA256SUMS").decode().splitlines():
        expected, name = line.split()
        name = name.removeprefix("./")
        actual = hashlib.sha256(blob(name)).hexdigest()
        manifest[name] = actual == expected
    compressed = blob("availability_frames.jsonl.gz")
    raw = gzip.decompress(compressed)
    frames = [json.loads(line) for line in raw.splitlines()]
    summary = json.loads(blob("run_summary.json"))
    receipt = json.loads(blob("receipt.json"))
    analysis = json.loads(blob("analysis.json"))
    candidates = [json.loads(line) for line in blob("candidates.jsonl").splitlines()]
    wiring = json.loads(blob("wiring.json"))
    archived_report = blob("REPORT.md").decode()
    driver_sha = blob("recovery_node_source.sha256").decode().strip()

    def counts(items):
        return dict(collections.Counter(items))

    errors = collections.Counter()
    maxima = collections.defaultdict(float)
    complete_support = complete_nis = plane_intersections = 0
    branch_population = collections.defaultdict(list)
    for frame, diag in zip(frames, summary["frame_diagnostics"]):
        for key, value in (
            ("kf_id", frame["kf_id"]), ("ts_ns", frame["pose_stamp_ns"]),
            ("nis", frame["nis"]["effective_nis"]), ("nis_source", frame["nis"]["source"]),
            ("nis_reference", frame["nis"]["selected_reference_source"]),
            ("detection_status", frame["status"]),
        ):
            if diag[key] != value:
                errors["summary_frame_correspondence"] += 1
        if frame["pose_stamp_ns"] - frame["scan_stamp_ns"] != frame["pose_scan_dt_ns"]:
            errors["stamp_difference"] += 1
        status = "AVAILABLE" if frame["support_pass"] and frame["nis_present"] else "UNAVAILABLE"
        if status != frame["status"] or status != frame["status_from_conditions"]:
            errors["availability_conditions"] += 1
        nis = frame["nis"]
        if nis.get("raw_value") != nis["effective_nis"]:
            errors["raw_effective_difference"] += 1
        support = frame["support"]
        points = support.get("points", [])
        if points:
            if len(points) != support.get("points_saved", support["sampled_query_count"]):
                errors["support_saved_length"] += 1
            if support["within_radius_count"] / support["sampled_query_count"] != support["supported_fraction"]:
                errors["support_summary_fraction"] += 1
            if (support["supported_fraction"] >= support["threshold_fraction"]) != frame["support_pass"]:
                errors["support_threshold"] += 1
            if [p["row"] for p in points] != list(range(0, len(points) * support["query_stride"], support["query_stride"])):
                errors["support_postcap_row_stride"] += 1
            if len(points) == support["sampled_query_count"]:
                complete_support += 1
                if sum(p["within_1m"] for p in points) != support["within_radius_count"]:
                    errors["support_full_mask_count"] += 1
            transform = frame["T_wb"]
            for point in points:
                for j in range(3):
                    predicted = sum(transform[4*j+k] * point["body"][k] for k in range(3)) + transform[4*j+3]
                    maxima["body_world_transform"] = max(maxima["body_world_transform"], abs(predicted-point["world"][j]))
        holdout = nis.get("holdout", {})
        residuals = holdout.get("points", [])
        if not residuals:
            continue
        if len(residuals) != holdout.get("points_saved", holdout["residual_total"]):
            errors["nis_saved_length"] += 1
        if [p["query"] for p in residuals] != list(range(len(residuals))):
            errors["nis_query_index"] += 1
        expected_branch = "clipped_residuals" if holdout["inlier_coverage"] >= 0.7 else "all_residuals"
        if expected_branch != holdout["branch"]:
            errors["observed_coverage_branch_rule"] += 1
        support_world = {p["row"]: p["world"] for p in points}
        for point in residuals:
            if point["within_2m"] != (abs(point["residual_m"]) < 2):
                errors["coverage_mask_vs_residual"] += 1
            maxima["chi2_from_residual"] = max(maxima["chi2_from_residual"], abs((point["residual_m"]/holdout["sigma"])**2-point["chi2"]))
            if len(point["nn_ids"]) != holdout["k_neighbours"] or any(i < 0 or i >= holdout["train_sampled"] for i in point["nn_ids"]):
                errors["nn_ids_range"] += 1
            row = point["query"] * holdout["holdout_stride"]
            if row in support_world:
                predicted = abs(sum((support_world[row][j]-point["centroid"][j])*point["normal"][j] for j in range(3)))
                maxima["saved_plane_residual_intersections"] = max(maxima["saved_plane_residual_intersections"], abs(predicted-point["residual_m"]))
                plane_intersections += 1
        if len(residuals) != holdout["residual_total"]:
            continue
        complete_nis += 1
        valid = [p for p in residuals if abs(p["residual_m"]) < 2]
        coverage = len(valid)/len(residuals)
        chosen = valid if expected_branch == "clipped_residuals" else residuals
        if len(valid) != holdout["residual_valid"]:
            errors["full_coverage_count"] += 1
        maxima["coverage"] = max(maxima["coverage"], abs(coverage-holdout["inlier_coverage"]))
        mean_nis = statistics.fmean((p["residual_m"]/holdout["sigma"])**2 for p in chosen)
        maxima["branch_nis"] = max(maxima["branch_nis"], abs(mean_nis-holdout["nis"]))
        values = sorted(p["residual_m"] for p in chosen)
        calculations = {
            "mean_residual": statistics.fmean(values),
            "rms_residual": math.sqrt(statistics.fmean(v*v for v in values)),
            "max_residual": max(values),
        }
        for field, quantile in (("q50_residual", .5), ("q90_residual", .9)):
            pos = (len(values)-1)*quantile
            lo, hi = int(pos), math.ceil(pos)
            calculations[field] = values[lo]+(values[hi]-values[lo])*(pos-lo)
        for key, value in calculations.items():
            maxima[key] = max(maxima[key], abs(value-holdout[key]))
        branch_population[expected_branch].append(coverage)

    runs = []
    start = 0
    for end in range(1, len(frames)+1):
        if end == len(frames) or frames[end]["status"] != frames[start]["status"]:
            runs.append({"status": frames[start]["status"], "first_row": start, "last_row": end-1,
                         "frames": end-start, "start_pose_stamp_ns": frames[start]["pose_stamp_ns"],
                         "end_pose_stamp_ns": frames[end-1]["pose_stamp_ns"]})
            start = end
    tsv = blob("segment_53_117.tsv").decode().splitlines()
    tsv_bad = 0
    for line in tsv[1:]:
        row = line.split("\t")
        frame = frames[int(row[0])]
        expected = [str(frame["kf_id"]), str(frame["pose_stamp_ns"]), str(frame["support"]["supported_fraction"]),
                    str(frame["support_pass"]), frame["nis"]["raw_kind"], str(frame["nis"].get("raw_reason")),
                    str(frame["nis"]["effective_nis"]), frame["nis"]["source"]]
        tsv_bad += row[1:] != expected

    examples = []
    for index in (1, 22, 50, 53, 157, 199, 401):
        frame = frames[index]
        support, nis = frame["support"], frame["nis"]
        holdout = nis.get("holdout", {})
        points, residuals = support.get("points", []), holdout.get("points", [])
        valid = [p for p in residuals if abs(p["residual_m"]) < 2]
        chosen = valid if holdout.get("branch") == "clipped_residuals" else residuals
        examples.append({
            "kf_id": index, "status": frame["status"], "pose_stamp_ns": frame["pose_stamp_ns"],
            "scan_stamp_ns": frame["scan_stamp_ns"], "pose_scan_dt_ns": frame["pose_scan_dt_ns"],
            "manager": frame["manager"], "support_reference_points": support["reference_points"],
            "support_saved_total": [len(points), support.get("sampled_query_count", 0)],
            "support_saved_within": sum(p["within_1m"] for p in points),
            "support_reported_within": support.get("within_radius_count"),
            "support_reported_fraction": support.get("supported_fraction"),
            "nis_reference": nis["selected_reference_source"], "nis_reference_points": nis["selected_reference_points"],
            "nis_saved_total": [len(residuals), holdout.get("residual_total", 0)],
            "nis_reported": holdout.get("nis"), "nis_saved_branch_mean": statistics.fmean((p["residual_m"]/holdout["sigma"])**2 for p in chosen),
            "coverage_saved_valid": len(valid), "coverage_reported_valid": holdout.get("residual_valid"),
            "coverage_reported": holdout.get("inlier_coverage"), "branch": holdout.get("branch"),
        })

    episodes = []
    for episode, candidate in zip(summary["quarantine"]["episode_detail"], candidates):
        restore = episode["native_checkpoint"]
        ack_fields = dict(field.split("=", 1) for field in restore.get("ack", "").split() if "=" in field)
        episodes.append({
            "index": episode["index"], "trigger_ts_ns": episode["trigger_ts_ns"],
            "candidate_decision_ts_ns": candidate["t_decision_ns"],
            "frame_freeze": episode["frame_freeze"], "first_alarm_ts_ns": episode["first_alarm_ts_ns"],
            "accepted": candidate["accepted"], "mode": candidate["mode"], "refusal_reason": candidate["refusal_reason"],
            "committed_keys": candidate["committed_pose_keys"], "deferred_keys": candidate["deferred_pose_keys"],
            "paired_evidence": episode["paired_evidence"], "state_after": episode["state_after"],
            "native_restore_ok": restore["ok"], "native_restore_ack_fields": ack_fields,
        })
    events = summary["native_checkpoint"]["events"]
    closes = [e for e in summary["lifecycle"]["events"] if e["event"] == "wait_limit_closed"]
    result = {
        "target": TARGET, "scope": PREFIX, "reader_uses": "python -I; subprocess git show; gzip in memory; JSON only; no archived scripts executed",
        "hashes": {"manifest_files": len(manifest), "all_match": all(manifest.values()),
                   "mismatches": [n for n, ok in manifest.items() if not ok],
                   "unlisted": sorted(set(names)-set(manifest)), "compressed_bytes": len(compressed), "raw_bytes": len(raw),
                   "compressed_sha256": hashlib.sha256(compressed).hexdigest(), "raw_sha256": hashlib.sha256(raw).hexdigest()},
        "identity": {"run_id": receipt["run_id"], "inputs": receipt["inputs"], "driver_sidecar_matches_receipt": driver_sha == receipt["inputs"]["recovery_node_source"],
                     "launch": receipt["launch"], "actual_node_launch_args": summary["launch_args"],
                     "runtime": summary["runtime"], "machine_load": receipt["machine_load_at_launch"],
                     "termination": receipt["termination"], "identity_limit": "Receipt attests hashes; archive has no actual library bytes, process mapped-library proof, bag/config bytes or driver source bytes to independently establish loaded identity."},
        "population": {"rows": len(frames), "summary_diagnostics": len(summary["frame_diagnostics"]),
                       "run_ids": counts(f["run_id"] for f in frames), "kf_contiguous_0_401": [f["kf_id"] for f in frames] == list(range(402)),
                       "unique_pose_stamps": len({f["pose_stamp_ns"] for f in frames}), "unique_scan_stamps": len({f["scan_stamp_ns"] for f in frames}),
                       "strict_pose_order": all(a["pose_stamp_ns"] < b["pose_stamp_ns"] for a,b in zip(frames,frames[1:])),
                       "strict_scan_order": all(a["scan_stamp_ns"] < b["scan_stamp_ns"] for a,b in zip(frames,frames[1:])),
                       "max_abs_dt_ns": max(abs(f["pose_scan_dt_ns"]) for f in frames), "pairing": summary["pairing"], "frames": summary["frames"],
                       "pairing_diagnosis": summary["pairing_diagnosis"], "scan_points_min_max": [min(f["scan"]["points"] for f in frames), max(f["scan"]["points"] for f in frames)],
                       "all_scan_points_finite": all(f["scan"]["finite"] == f["scan"]["points"] for f in frames)},
        "counts": {"status": counts(f["status"] for f in frames), "support_reason": counts(f["support"]["reason"] for f in frames),
                   "support_false_nis_true_reasons": counts(f["support"]["reason"] for f in frames if not f["support_pass"] and f["nis_present"]),
                   "condition_combinations": counts(str(f["support_pass"])+"/"+str(f["nis_present"]) for f in frames),
                   "nis_raw_source": counts(f["nis"]["raw_kind"]+"/"+f["nis"]["source"] for f in frames),
                   "nis_reference_status": counts(f["nis"]["selected_reference_source"]+"/"+f["status"] for f in frames),
                   "nis_nonfinite": sum(f["nis"]["effective_nis"] is not None and not math.isfinite(f["nis"]["effective_nis"]) for f in frames)},
        "runs": runs, "analysis_runs_match": runs == analysis["runs"], "segment_tsv_rows": len(tsv)-1, "segment_tsv_mismatches": tsv_bad,
        "recompute": {"complete_support_frames": complete_support, "complete_nis_frames": complete_nis,
                      "support_saved_population": counts(f["status"]+"/"+str(len(f["support"].get("points", []))) for f in frames),
                      "nis_saved_population": counts(f["status"]+"/"+str(len(f["nis"].get("holdout", {}).get("points", []))) for f in frames),
                      "full_nis_branch_coverage": {b: {"frames": len(v), "coverage_min_max": [min(v), max(v)]} for b,v in branch_population.items()},
                      "all_logged_branch_counts": counts(f["nis"].get("holdout", {}).get("branch", "not_computed") for f in frames),
                      "observed_branch_rule": "coverage >= 0.7: mean over abs(residual)<2; else mean over all saved residuals; chi2=(residual/0.884)^2",
                      "errors": dict(errors), "max_abs_numeric_errors": dict(maxima), "saved_plane_query_intersections": plane_intersections},
        "examples": examples,
        "geometry_reproduction_limits": ["Full UNAVAILABLE masks/residuals permit internal arithmetic reproduction, not independent support or nearest-neighbor geometry reproduction.",
                                         "Support query body/world and post-cap row/stride exist. No support reference coordinates or immutable reference snapshot/hash is archived.",
                                         "NIS nn_ids index the sampled train array; train/holdout strides and query ordinal exist, but actual selected reference/train coordinates and original raw/bag row mapping are absent.",
                                         "Saved centroid/normal permit plane residual checks at 24,120 support/holdout query intersections, but do not independently verify KNN selection or PCA normal derivation.",
                                         "Manager trusted_version/counts and native snapshot stamp/frame/counts are metadata, not linked reproducible coordinate snapshots."],
        "detector": {"enabled": summary["detection_enabled"], "run_mode": summary["run_mode"],
                     "scripted_trigger_lists": {k: summary["scripted_triggers"][k] for k in ("declared_s", "declared_ns", "fired")},
                     "warmup_counts": summary["warmup"]["detection_status_counts"],
                     "trigger_frame_diagnostics": [d for d in summary["frame_diagnostics"] if d["ts_ns"] in summary["quarantine"]["trigger_ts_ns"]]},
        "episodes": episodes, "gate": summary["gate"],
        "native": {"headline": {k:v for k,v in summary["native_checkpoint"].items() if k not in ("events", "note", "snapshot_ack_s")},
                   "event_counts": counts(e["command"]+"/"+str(e["ok"]) for e in events),
                   "failed_snapshot_example": next(e for e in events if not e["ok"]),
                   "wait_closes": [{k:v for k,v in e.items() if k != "frames_unresolved"} | {"unresolved_frame_count": len(e["frames_unresolved"])} for e in closes],
                   "rearms": sum(e["event"] == "rearm" for e in summary["lifecycle"]["events"]),
                   "final_state": summary["final_state"], "quarantine_open_at_exit": summary["quarantine_open_at_exit"],
                   "E2_limit": "Second and third online admission/restore/rearm cycles exercised; zero accepts/commits/reprocesses/repair applications. No independent fault labels, recovery-success measure or expected two-event alignment is archived."},
        "report_corrections_and_limits": [
            "REPORT section 6 says 306 UNAVAILABLE frames had fraction<0.60. Actual: 285 fraction failures + 22 empty_reference (21 with fresh finite prev_scan NIS, one with no NIS). 306 is support_false AND nis_present, not the fraction-failure count.",
            "No saved support points exist for 22 empty_reference frames; no NIS points for the one no_reference frame. Full samples exist for 285 evaluated unsupported frames and 306 NIS-computed UNAVAILABLE frames.",
            "Receipt repair_publish='1' disagrees with actual node launch_args repair_publish=false and recovery_node.log repair publisher off. Actual native hold/restore/resume is distinct from repair publication.",
            "wiring.all_ok and HEALTHY are operational/state labels, not detection or recovery success. 14 snapshot_ack_timeout failures are recorded.",
            "Historical87 comparison is only 22+65=87; scoped archive does not establish old-run identity or population/event equivalence.",
            "No-log/log decision invariance and S1 tests are claims not independently demonstrated by this single scoped archive.",
            "UNAVAILABLE/high-NIS establishes recorded support failure with available NIS, not proven pose drift or its cause.",
            "pose_convention.one_frame_check is REVERSED_SELECTED; 18.280525337810758 forward vs 15.871990342592234 reverse. This is a recorded diagnostic, not a causal orientation verdict.",
            "All three episode first_alarm_ts_ns repeat 1627785264206571102; later episode onset/trigger timestamps differ. Do not treat that field as fresh per-episode evidence."
        ],
        "wiring_all_ok": wiring["all_ok"],
        "report_contains_fraction_306_claim": "306 帧是" in archived_report,
    }
    text = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+"\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    print(json.dumps({"target": TARGET, "rows": len(frames), "manifest_all_match": all(manifest.values()),
                      "numeric_errors": dict(errors), "full_support_frames": complete_support, "full_nis_frames": complete_nis,
                      "output": args.output}, ensure_ascii=False))
    return 0 if all(manifest.values()) and not errors and not tsv_bad and runs == analysis["runs"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
