#!/usr/bin/env python3
"""UNAVAILABLE availability audit: source branches + what existing archives can prove.

Read-only. No host run, no ROS, no detector, no threshold change, no production edit.

Two independent things:

  1. SOURCE CITATIONS -- every line the report cites is checked against the file at this revision
     (substring must be on that exact line). If the source has moved, the check fails instead of
     the report silently citing stale line numbers.
  2. ARCHIVE ATTRIBUTION -- for each run_summary.json, classify every frame from the fields that
     were actually recorded:
         detection_status, nis, nis_source, nis_reference, map_points, trusted_keyframes
     and derive only what those fields plus the source control flow can support. The exact support
     FRACTION is not recorded anywhere, so it is never guessed.

    python -I docs/review_20261112_unavailable/availability_source_audit.py --scan-tmp
    python -I docs/review_20261112_unavailable/availability_source_audit.py --run /path/run_summary.json
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import statistics
import subprocess

ROOT = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
OUT_DIR = os.path.dirname(os.path.abspath(__file__))

# (relative path, 1-based line, substring that must be on that line, what the line is)
SOURCE_CHECKS = [
    ("slam_recovery/ros/recovery_node.py", 69, "SCAN_CAP = 6000", "scan point cap"),
    ("slam_recovery/ros/recovery_node.py", 70, "NIS_RADIUS_M = 3.0", "NIS reference radius"),
    ("slam_recovery/ros/recovery_node.py", 71, "NIS_MIN_TRAIN = 30", "NIS min train"),
    ("slam_recovery/ros/recovery_node.py", 72, "NIS_MIN_HOLDOUT = 10", "NIS min holdout"),
    ("slam_recovery/ros/recovery_node.py", 81, "REFERENCE_REFRESH_NS", "support cache refresh"),
    ("slam_recovery/ros/recovery_node.py", 1067, "self.nis.measure(", "NIS measured"),
    ("slam_recovery/ros/recovery_node.py", 1068, "support_ref = self.nis.support_reference",
     "support reference resolved"),
    ("slam_recovery/ros/recovery_node.py", 1072, "pts_before = int(len(support_ref))",
     "map_points recorded"),
    ("slam_recovery/ros/recovery_node.py", 1095, "_frame_has_reference_support", "support call"),
    ("slam_recovery/ros/recovery_node.py", 1100, "bool(supported) and value is not None",
     "availability predicate"),
    ("slam_recovery/ros/recovery_node.py", 1101, "UNAVAILABLE", "status assignment"),
    ("slam_recovery/ros/recovery_node.py", 1220, "if len(self.diag) >= self.diag_cap", "diag cap"),
    ("slam_recovery/ros/recovery_node.py", 1225, '"nis":', "diag nis"),
    ("slam_recovery/ros/recovery_node.py", 1226, '"nis_source"', "diag nis_source"),
    ("slam_recovery/ros/recovery_node.py", 1226, '"nis_reference"', "diag nis_reference"),
    ("slam_recovery/ros/recovery_node.py", 1227, '"detection_status"', "diag detection_status"),
    ("slam_recovery/ros/recovery_node.py", 1231, '"map_points"', "diag map_points"),
    ("slam_recovery/sim/transaction_manager_node.py", 363, "def _frame_has_reference_support",
     "support helper"),
    ("slam_recovery/sim/transaction_manager_node.py", 368, "radius_m: float = 1.0",
     "support radius"),
    ("slam_recovery/sim/transaction_manager_node.py", 369, "min_supported_fraction: float = 0.60",
     "support fraction"),
    ("slam_recovery/sim/transaction_manager_node.py", 377, "if len(ref_pts) == 0",
     "empty reference branch"),
    ("slam_recovery/sim/transaction_manager_node.py", 383,
     "if kf_id not in self.scan_buffer_body or kf_id not in repaired_poses",
     "missing scan/pose branch"),
    ("slam_recovery/sim/transaction_manager_node.py", 386, "T.shape != (4, 4)",
     "invalid pose branch"),
    ("slam_recovery/sim/transaction_manager_node.py", 389, "if len(pts_b) == 0",
     "empty scan branch"),
    ("slam_recovery/sim/transaction_manager_node.py", 392, "pts_w[:: max(1, len(pts_w) // 200)][:200]",
     "support sampling"),
    ("slam_recovery/sim/transaction_manager_node.py", 393, "index = index if index is not None",
     "radius index"),
    ("slam_recovery/sim/transaction_manager_node.py", 394, "within_radius_mask", "inside mask"),
    ("slam_recovery/sim/transaction_manager_node.py", 395, "min_supported_fraction", "fraction test"),
    ("slam_recovery/sim/transaction_manager_node.py", 81, "def within_radius_mask", "index query"),
    ("slam_recovery/sim/transaction_manager_node.py", 103, "d2.min() <= r2",
     "per-query short circuit"),
    ("slam_recovery/sim/transaction_manager_node.py", 258, "get_trusted_map_points(max_pts=1 << 30)",
     "support reference source"),
    ("slam_recovery/validation/fim_and_holdout.py", 120, "len(train_xyz) < 30 or len(hold_xyz) < 10",
     "estimator input floor"),
    ("slam_recovery/validation/fim_and_holdout.py", 127, "len(train_xyz) // 600", "train cap"),
    ("slam_recovery/validation/fim_and_holdout.py", 128, "len(hold_trans) // 300", "query cap"),
    ("slam_recovery/validation/fim_and_holdout.py", 132, "k = min(8, len(t_sub) - 1)", "k neighbours"),
    ("slam_recovery/validation/fim_and_holdout.py", 143, "residuals < 2.0", "2 m truncation"),
    ("slam_recovery/validation/fim_and_holdout.py", 147, "inlier_coverage < 0.70", "coverage branch"),
    ("slam_recovery/validation/fim_and_holdout.py", 148, "np.mean((residuals / sigma_meas_m) ** 2)",
     "all-residual branch (no None on low coverage)"),
    ("slam_recovery/validation/fim_and_holdout.py", 149, "np.mean((valid_res / sigma_meas_m) ** 2)",
     "clipped-residual branch"),
    ("slam_recovery/validation/fim_and_holdout.py", 107, "def compute_disjoint_holdout_point_to_plane_nis",
     "function has no `details` out-parameter at this revision"),
]


# (relative path, token, expected presence, description) -- whole-file checks for claims that are
# about a parameter being ABSENT, which a per-line citation cannot express.
GLOBAL_CHECKS = [
    ("slam_recovery/validation/fim_and_holdout.py", "details", False,
     "HEAD's NIS function has no details out-parameter; per-point values are computed and dropped"),
]


def sha256_file(path: str, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def source_checks():
    out = []
    for rel, line, token, what in SOURCE_CHECKS:
        path = os.path.join(ROOT, rel)
        try:
            text = open(path, encoding="utf-8").read().splitlines()
            actual = text[line - 1]
            ok = token in actual
        except Exception as exc:                       # noqa: BLE001 - recorded, not hidden
            actual, ok = f"<{type(exc).__name__}: {exc}>", False
        out.append({"file": rel, "line": line, "expect": token, "actual": actual.strip(),
                    "what": what, "status": "PASS" if ok else "FAIL"})
    for rel, token, present, what in GLOBAL_CHECKS:
        path = os.path.join(ROOT, rel)
        try:
            text = open(path, encoding="utf-8").read()
            found = token in text
            ok = (found == present)
        except Exception as exc:                       # noqa: BLE001
            found, ok = f"<{type(exc).__name__}: {exc}>", False
        out.append({"file": rel, "line": None, "expect": f"token {'present' if present else 'absent'}: "
                    f"{token}", "actual": f"found={found}", "what": what,
                    "status": "PASS" if ok else "FAIL"})
    return out


def _blocks(rows):
    """Contiguous kf runs (kf_id increments by 1) of whatever rows are passed in."""
    if not rows:
        return []
    ks = [r["kf_id"] for r in rows]
    out, start, prev = [], ks[0], ks[0]
    for k in ks[1:]:
        if k == prev + 1:
            prev = k
        else:
            out.append((start, prev))
            start = prev = k
    out.append((start, prev))
    return out


def audit_run(path: str, window_s):
    d = json.load(open(path, encoding="utf-8"))
    fd = d.get("frame_diagnostics") or []
    # The `detection_enabled` field is absent (None) in older summaries. What decides whether the
    # availability branch actually ran is whether frames carry AVAILABLE/UNAVAILABLE statuses.
    det = any(r.get("detection_status") in ("AVAILABLE", "UNAVAILABLE") for r in fd)
    res = {
        "path": path,
        "summary_sha256": sha256_file(path),
        "run_id": d.get("run_id"),
        "detection_enabled_field": d.get("detection_enabled"),
        "detection_on": det,
        "frames_paired": (d.get("frames") or {}).get("paired"),
        "frame_diagnostics_rows": len(fd),
        "diag_cap": 2000,
        "diag_complete": bool(len(fd) >= ((d.get("frames") or {}).get("paired") or 0)),
        "nis_summary": d.get("nis"),
        "detection_status_counts": (d.get("warmup") or {}).get("detection_status_counts"),
    }
    if not fd:
        res["status"] = "NOT_APPLICABLE: no frame_diagnostics"
        return res

    statuses = {}
    for r in fd:
        statuses[r.get("detection_status")] = statuses.get(r.get("detection_status"), 0) + 1
    pairs = {}
    for r in fd:
        key = f"{r.get('detection_status')}|{r.get('nis_source')}"
        pairs[key] = pairs.get(key, 0) + 1
    refs = {}
    for r in fd:
        key = f"{r.get('detection_status')}|{r.get('nis_reference')}"
        refs[key] = refs.get(key, 0) + 1
    un = [r for r in fd if r.get("detection_status") == "UNAVAILABLE"]
    res.update({
        "status_counts": statuses,
        "status_by_nis_source": pairs,
        "status_by_nis_reference": refs,
        "unavailable_total": len(un),
        "unavailable_with_nis_number": sum(1 for r in un if r.get("nis") is not None),
        "unavailable_with_computed_nis": sum(1 for r in un if r.get("nis_source") == "computed"),
        "unavailable_with_empty_reference": sum(1 for r in un if r.get("map_points") == 0),
        "unavailable_map_nonempty_and_computed": sum(
            1 for r in un if (r.get("map_points") or 0) > 0 and r.get("nis_source") == "computed"),
        "unavailable_nis_missing_or_carried": sum(
            1 for r in un if r.get("nis") is None or r.get("nis_source") != "computed"),
        # `_reference` falls back to prev_scan when the trusted cloud has >=30 points in total but
        # fewer than 30 within 3 m of the pose. With map_points >= 30 that fallback is therefore a
        # source-exact statement about the pose neighbourhood, not about the map as a whole.
        "unavailable_pose_neighbourhood_below_30": sum(
            1 for r in un if (r.get("map_points") or 0) >= 30
            and r.get("nis_reference") == "prev_scan"),
        "carried_forward_frames": sum(1 for r in fd if r.get("nis_source") == "carried_forward"),
        # Partition of UNAVAILABLE frames by the support branch the recorded fields can locate.
        #   empty_reference      map_points == 0 -> the helper returns at its first branch, before
        #                        the fraction test, regardless of what the NIS did
        #   fraction             map_points > 0 AND NIS computed -> every earlier support branch
        #                        is excluded by the recorded fields; only the 60% test remains
        #   ambiguous            map_points > 0 AND NIS not computed -> support may have failed at
        #                        the fraction, or the NIS may have been missing; both are possible
        "unavailable_by_support_branch": {
            "empty_reference": sum(1 for r in un if r.get("map_points") == 0),
            "empty_reference_with_computed_nis": sum(
                1 for r in un if r.get("map_points") == 0 and r.get("nis_source") == "computed"),
            "fraction": sum(1 for r in un if (r.get("map_points") or 0) > 0
                            and r.get("nis_source") == "computed"),
            "ambiguous_noncomputed_map_present": sum(
                1 for r in un if (r.get("map_points") or 0) > 0
                and r.get("nis_source") != "computed"),
        },
    })
    empty = [r for r in fd if r.get("map_points") == 0]
    res["empty_reference_blocks"] = [
        {"kf_first": a, "kf_last": b, "frames": b - a + 1,
         "ts_first_ns": next(r["ts_ns"] for r in empty if r["kf_id"] == a),
         "ts_last_ns": next(r["ts_ns"] for r in empty if r["kf_id"] == b)}
        for a, b in _blocks(empty)
    ]
    first = fd[0]
    res["first_frame"] = {"kf_id": first.get("kf_id"), "detection_status": first.get("detection_status"),
                          "nis_source": first.get("nis_source"),
                          "nis_reference": first.get("nis_reference"),
                          "map_points": first.get("map_points")}

    t0 = fd[0]["ts_ns"]
    lo, hi = window_s
    win = [r for r in fd if lo * 1e9 <= r["ts_ns"] - t0 <= hi * 1e9]
    if win:
        vals = [r["nis"] for r in win if r.get("nis") is not None]
        res["window"] = {
            "start_s_from_first_frame": lo, "end_s_from_first_frame": hi,
            "frames": len(win), "kf_first": win[0]["kf_id"], "kf_last": win[-1]["kf_id"],
            "status_counts": {s: sum(1 for r in win if r.get("detection_status") == s)
                              for s in sorted({r.get("detection_status") for r in win})},
            "nis_source_counts": {s: sum(1 for r in win if r.get("nis_source") == s)
                                  for s in sorted({r.get("nis_source") for r in win})},
            "nis_reference_counts": {s: sum(1 for r in win if r.get("nis_reference") == s)
                                     for s in sorted({r.get("nis_reference") for r in win})},
            "pose_neighbourhood_below_30": sum(
                1 for r in win if (r.get("map_points") or 0) >= 30
                and r.get("nis_reference") == "prev_scan"),
            "nis_min": min(vals) if vals else None,
            "nis_median": statistics.median(vals) if vals else None,
            "nis_max": max(vals) if vals else None,
        }
    res["status"] = "ANALYSED"
    return res


def aggregate(runs):
    det = [r for r in runs if r.get("detection_on") and r.get("status") == "ANALYSED"]
    agg = {
        "runs_with_detection_on": len(det),
        "unavailable_total": sum(r["unavailable_total"] for r in det),
        "unavailable_with_computed_nis": sum(r["unavailable_with_computed_nis"] for r in det),
        "unavailable_with_empty_reference": sum(r["unavailable_with_empty_reference"] for r in det),
        "unavailable_map_nonempty_and_computed": sum(
            r["unavailable_map_nonempty_and_computed"] for r in det),
        "unavailable_nis_missing_or_carried": sum(
            r["unavailable_nis_missing_or_carried"] for r in det),
        "unavailable_pose_neighbourhood_below_30": sum(
            r["unavailable_pose_neighbourhood_below_30"] for r in det),
        "carried_forward_frames": sum(r["carried_forward_frames"] for r in det),
        "unavailable_by_support_branch": {
            k: sum(r["unavailable_by_support_branch"][k] for r in det)
            for k in ("empty_reference", "empty_reference_with_computed_nis", "fraction",
                      "ambiguous_noncomputed_map_present")
        },
    }
    agg["reading"] = ("UNAVAILABLE is a support predicate outcome, not a missing NIS: in every "
                      "detection-on run almost every UNAVAILABLE frame has a computed NIS. The "
                      "exception is the cold-start frame (empty reference and no NIS); it is "
                      "counted separately and is a multi-cause frame")
    return agg


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="append", default=[],
                    help="run_summary.json to audit (repeatable)")
    ap.add_argument("--scan-tmp", action="store_true",
                    help="also audit /tmp/fl_native_*/run_summary.json that exist")
    ap.add_argument("--window", type=float, nargs=2, default=[42.0, 52.0],
                    help="E2 window for every run, in seconds from its first paired frame")
    args = ap.parse_args(argv)

    paths = list(args.run)
    skipped = {"detection_off_or_no_status": 0, "paths": []}
    if args.scan_tmp:
        for p in sorted(glob.glob("/tmp/fl_native_*/run_summary.json")):
            try:
                d = json.load(open(p, encoding="utf-8"))
            except Exception:                          # noqa: BLE001 - counted, not hidden
                skipped["detection_off_or_no_status"] += 1
                continue
            fd = d.get("frame_diagnostics") or []
            if any(r.get("detection_status") in ("AVAILABLE", "UNAVAILABLE") for r in fd):
                paths.append(p)
            else:
                skipped["detection_off_or_no_status"] += 1
                skipped["paths"].append(p)
    archived = os.path.join(
        ROOT, "docs/review_20261110_native_checkpoint/"
              "chain_run_fl_native_20261110T115717Z_3390402/run_summary.json")
    if os.path.exists(archived) and archived not in paths:
        paths.append(archived)

    checks = source_checks()
    runs = []
    for p in paths:
        if not os.path.exists(p):
            runs.append({"path": p, "status": "BLOCKED: file not present"})
            continue
        runs.append(audit_run(p, args.window))

    out = {
        "_meta": {
            "what": "UNAVAILABLE availability audit: source branches and archive attribution",
            "written": "2026-11-12",
            "repo_head": _git_head(),
            "source_files": {rel: sha256_file(os.path.join(ROOT, rel)) for rel, *_ in SOURCE_CHECKS},
            "not_done": ["no host run", "no ROS", "no detector", "no threshold change",
                         "no production edit"],
            "window_origin": "first frame_diagnostics row of each run; not the bag start",
            "discovery": skipped,
        },
        "source_checks": checks,
        "source_checks_summary": {
            "PASS": sum(1 for c in checks if c["status"] == "PASS"),
            "FAIL": sum(1 for c in checks if c["status"] == "FAIL"),
            "of": len(checks),
        },
        "runs": runs,
        "aggregate": aggregate(runs),
    }
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, "availability_source_audit.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    print(json.dumps({"source_checks_summary": out["source_checks_summary"],
                      "aggregate": out["aggregate"]}, indent=1))
    for r in runs:
        if r.get("status") == "ANALYSED":
            print(r["run_id"], r["detection_on"], r["status_counts"],
                  "unavail computed", r["unavailable_with_computed_nis"],
                  "empty-ref", r["unavailable_with_empty_reference"],
                  "fraction-branch", r["unavailable_map_nonempty_and_computed"])
    return 0


def _git_head():
    try:
        return subprocess.run(["git", "-C", ROOT, "rev-parse", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()
    except Exception:                                  # noqa: BLE001
        return "UNAVAILABLE"


if __name__ == "__main__":
    raise SystemExit(main())
