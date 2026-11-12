#!/usr/bin/env python3
"""ALI-H v1 research observer: evidence inventory and shadow state, T0 on saved archives.

Independent research code. It does not import or modify manager/recovery code, and it never
feeds a decision back into the detector. The only shared tool it uses is the existing SE(3)
transport pair, for the T1 coordinate check.

Frozen configuration (docs/ADAPTIVE_LOW_INFORMATION_HEALTH_V1_20261112.md §4.2):

  block                     0.5 s of sensor time (pose_stamp_ns), not wall time
  channel alarm             u_c >= 0.95 on two ADJACENT evidence blocks
  channel normal-compatible u_c <= 0.80 on two adjacent evidence blocks
  normal reference          per (channel, map_support) condition, >= 20 blocks, else INCOMPLETE
  u_c                       (1 + #{b in B_c : b <= s}) / (len(B_c) + 1)

Channels:
  M  node-map LiDAR residual (`nis.selected_reference_source == "node_map"`, computed, finite)
  T  previous-scan LiDAR residual (`prev_scan`), relative-motion only
  I  IMU pre-update prediction vs LiDAR update. NOT AVAILABLE in either archive: neither file
     carries an IMU propagation, innovation, timestamped interval or covariance.

The normal reference is NOT taken from HEALTHY/trusted/no-injection. The archives carry no
independently confirmed healthy prefix, so T0 runs with an empty calibration table: every
channel is CALIBRATION_BLOCKED and every state is UNKNOWN. That is the measurement, not a
fallback.

    python -I docs/ali_h_v1_research/ali_h_v1.py t0
    python -I docs/ali_h_v1_research/ali_h_v1.py selftest
"""

from __future__ import annotations

import gzip
import hashlib
import json
import math
import os
import statistics
import sys
from typing import Any, Dict, Iterable, List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.dirname(os.path.dirname(HERE)))

BLOCK_NS = 500_000_000
ALARM_U = 0.95
NORMAL_U = 0.80
MIN_BLOCKS = 20

RUNS = {
    "A": {
        "run_id": "fl_native_20261112T065500Z_187992",
        "frames": os.path.join(ROOT, "docs/review_20261112_availability/availability_frames.jsonl.gz"),
        "receipt": os.path.join(ROOT, "docs/review_20261112_availability/receipt.json"),
        "summary": os.path.join(ROOT, "docs/review_20261112_availability/run_summary.json"),
        "report": os.path.join(ROOT, "docs/review_20261112_availability/REPORT.md"),
    },
    "B": {
        "run_id": "fl_native_20261112T070801Z_197026",
        "frames": os.path.join(
            ROOT, "docs/review_20261112_availability/predicted_pose/availability_frames.jsonl.gz"),
        "receipt": os.path.join(ROOT, "docs/review_20261112_availability/predicted_pose/receipt.json"),
        "summary": os.path.join(ROOT, "docs/review_20261112_availability/predicted_pose/run_summary.json"),
        "report": os.path.join(ROOT, "docs/review_20261112_availability/predicted_pose/REPORT.md"),
    },
}


def _finite(value) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def sha256(path: str, chunk: int = 1 << 22) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def load_rows(path: str) -> Iterable[Dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            yield json.loads(line)


def map_support(row: Dict[str, Any]) -> str:
    sup = row.get("support") or {}
    ref = sup.get("reference_points")
    if isinstance(ref, (int, float)) and ref == 0:
        return "EMPTY"
    if sup.get("pass") is True:
        return "SUPPORTED"
    if sup.get("pass") is False:
        return "LOW"
    if sup.get("reason") == "empty_reference":
        return "EMPTY"
    return "LOW"


def _channel_m(nis: Dict[str, Any]) -> Dict[str, Any]:
    present = (nis.get("selected_reference_source") == "node_map"
               and bool(nis.get("computed")) and _finite(nis.get("effective_nis")))
    return {"name": "M", "present": bool(present),
            "source": nis.get("selected_reference_source"),
            "fresh": nis.get("source") == "computed",
            "score": float(nis["effective_nis"]) if present else None,
            "qualification": ("EVIDENCE_PRESENT" if present else "MISSING"),
            "reason": None if present else "no_node_map_residual",
            "coverage": ((nis.get("holdout") or {}).get("inlier_coverage")
                         if isinstance(nis.get("holdout"), dict) else None),
            "reference_points": nis.get("selected_reference_points"),
            "reference_id": None, "age_ns": None,
            "age_status": "NOT_RECORDED_BY_ARCHIVE"}


def _channel_t(nis: Dict[str, Any]) -> Dict[str, Any]:
    present = (nis.get("selected_reference_source") == "prev_scan"
               and bool(nis.get("computed")) and _finite(nis.get("effective_nis")))
    return {"name": "T", "present": bool(present),
            "source": nis.get("selected_reference_source"),
            "fresh": nis.get("source") == "computed",
            "score": float(nis["effective_nis"]) if present else None,
            "qualification": ("EVIDENCE_PRESENT" if present else "MISSING"),
            "reason": None if present else "no_prev_scan_residual",
            "reference_points": nis.get("prev_scan_points"),
            "reference_id": None, "age_ns": None,
            "age_status": "NOT_RECORDED_BY_ARCHIVE"}


def _channel_i(_row: Dict[str, Any]) -> Dict[str, Any]:
    return {"name": "I", "present": False, "source": None, "fresh": False, "score": None,
            "qualification": "NOT_AVAILABLE",
            "reason": "no_imu_preupdate_vs_lidar_update_export",
            "reference_points": None, "reference_id": None, "age_ns": None,
            "age_status": "NOT_APPLICABLE"}


def frame_record(row: Dict[str, Any], run_id: str) -> Dict[str, Any]:
    nis = row.get("nis") or {}
    sup = row.get("support") or {}
    ts = int(row.get("pose_stamp_ns") or 0)
    rec = {
        "run_id": run_id, "kf_id": row.get("kf_id"),
        "pose_stamp_ns": ts, "scan_stamp_ns": row.get("scan_stamp_ns"),
        "pose_scan_dt_ns": row.get("pose_scan_dt_ns"),
        "block_id": ts // BLOCK_NS,
        "map_support": map_support(row),
        "support": {
            "reason": sup.get("reason"), "pass": sup.get("pass"),
            "reference_points": sup.get("reference_points"),
            "sampled_query_count": sup.get("sampled_query_count"),
            "within_radius_count": sup.get("within_radius_count"),
            "supported_fraction": sup.get("supported_fraction"),
            "radius_m": sup.get("radius_m"),
            "threshold_fraction": sup.get("threshold_fraction"),
        },
        "old": {
            "status": row.get("status"),
            "status_from_conditions": row.get("status_from_conditions"),
            "nis_source": nis.get("source"),
            "nis_reference": nis.get("selected_reference_source"),
            "nis_present": row.get("nis_present"),
        },
        "channels": {"M": _channel_m(nis), "T": _channel_t(nis), "I": _channel_i(row)},
    }
    if rec["old"]["status"] == "UNAVAILABLE":
        rec["old"]["reasons"] = old_reason(rec)
    return rec


# ---------------------------------------------------------------------------------------------
class Calibration:
    """Empirical normal references, per (channel, map_support). Empty in T0 by design."""

    def __init__(self, table: Optional[Dict[tuple, List[float]]] = None,
                 reference_status: str = "BLOCKED:no_independently_confirmed_normal_reference"):
        self.table = table or {}
        self.reference_status = reference_status

    def lookup(self, channel: str, context: str, score: float) -> Dict[str, Any]:
        if context == "MIXED":
            return {"status": "OUT_OF_SUPPORT", "reason": "mixed_context_in_block"}
        key = (channel, context)
        blocks = self.table.get(key)
        if not blocks:
            if any(k[0] == channel for k in self.table):
                return {"status": "OUT_OF_SUPPORT", "reason": f"no_reference_for_context:{context}"}
            return {"status": "BLOCKED", "reason": self.reference_status}
        if len(blocks) < MIN_BLOCKS:
            return {"status": "INCOMPLETE", "reason": f"{len(blocks)}_blocks_below_20"}
        u = (1.0 + sum(1 for b in blocks if b <= score)) / (len(blocks) + 1.0)
        return {"status": "OK", "u": u, "n": len(blocks)}


def channel_verdict(ch: Dict[str, Any], context: str, calib: Calibration) -> Dict[str, Any]:
    out = {"channel": ch["name"], "present": ch["present"], "fresh": ch["fresh"],
           "score": ch["score"], "verdict": None, "calibration": None, "u": None, "reason": None}
    if not ch["present"]:
        out.update(verdict="MISSING", calibration="NOT_APPLICABLE", reason=ch.get("reason"))
        return out
    if not ch["fresh"]:
        out.update(verdict="STALE", calibration="NOT_USED", reason="carried_forward_not_new_evidence")
        return out
    r = calib.lookup(ch["name"], context, float(ch["score"]))
    out["calibration"] = r["status"]
    if r["status"] != "OK":
        out.update(verdict="UNQUALIFIED", reason=r.get("reason"))
        return out
    u = r["u"]
    out["u"] = u
    out["verdict"] = "ALARM" if u >= ALARM_U else ("NORMAL" if u <= NORMAL_U else "GREY")
    return out


def classify_blocks(blocks: List[Dict[str, Any]], calib: Calibration) -> List[Dict[str, Any]]:
    """State machine over 0.5 s blocks. Two adjacent evidence blocks are required."""
    prev_verdict: Dict[str, Optional[str]] = {"M": None, "T": None, "I": None}
    last_suspect = None
    out = []
    for blk in blocks:
        v = blk["verdicts"]
        alarms = {k: (v[k]["verdict"] == "ALARM" and prev_verdict[k] == "ALARM")
                  for k in ("M", "T", "I")}
        normals = {k: (v[k]["verdict"] == "NORMAL" and prev_verdict[k] == "NORMAL")
                   for k in ("M", "T", "I")}
        reasons = []
        if alarms["M"] or alarms["I"]:
            state = "SUSPECT"
            scope = "MAP_AND_MOTION" if alarms["M"] else "RELATIVE_MOTION_ONLY"
            reasons.append("POSITIVE_CONFLICT:" + ",".join(k for k in ("M", "I") if alarms[k]))
        elif alarms["T"]:
            state, scope = "SUSPECT", "RELATIVE_MOTION_ONLY"
            reasons.append("MEASUREMENT_INCONSISTENT:T")
        elif normals["I"] and (normals["M"] or normals["T"]):
            state = "NORMAL_CONSISTENT"
            scope = "MAP_AND_MOTION" if normals["M"] else "RELATIVE_MOTION_ONLY"
        else:
            state, scope = "UNKNOWN", "NONE"
            if normals["M"] and not normals["I"]:
                reasons.append("M_NORMAL_WITHOUT_INDEPENDENT_I")
            if normals["T"] and not normals["I"]:
                reasons.append("T_NORMAL_ONLY_RELATIVE")
            if not any(v[k]["verdict"] in ("ALARM", "NORMAL", "GREY") for k in ("M", "T", "I")):
                missing = [k for k in ("M", "T", "I")
                           if v[k]["verdict"] in ("MISSING", "STALE", "NOT_AVAILABLE")]
                reasons.append("NO_QUALIFIED_EVIDENCE:" + (",".join(missing) or "all_unqualified"))
            if not reasons:
                reasons.append("INSUFFICIENT_PERSISTENCE_OR_CALIBRATION")
        if state == "SUSPECT":
            last_suspect = blk["block_id"]
        out.append({"block_id": blk["block_id"], "state": state, "scope": scope,
                    "reason_codes": reasons, "last_suspect_block": last_suspect,
                    "verdicts": {k: v[k]["verdict"] for k in ("M", "T", "I")},
                    "u": {k: v[k]["u"] for k in ("M", "T", "I")}})
        prev_verdict = {k: v[k]["verdict"] for k in ("M", "T", "I")}
    return out


def block_summary(frames: List[Dict[str, Any]], calib: Calibration) -> List[Dict[str, Any]]:
    by_block: Dict[int, List[Dict[str, Any]]] = {}
    for f in frames:
        by_block.setdefault(f["block_id"], []).append(f)
    blocks = []
    for bid in sorted(by_block):
        fs = by_block[bid]
        contexts = {f["map_support"] for f in fs}
        context = contexts.pop() if len(contexts) == 1 else "MIXED"
        median = {}
        counts = {}
        for ch in ("M", "T", "I"):
            vals = [f["channels"][ch]["score"] for f in fs
                    if f["channels"][ch]["present"] and f["channels"][ch]["fresh"]
                    and f["channels"][ch]["score"] is not None]
            median[ch] = float(statistics.median(vals)) if vals else None
            counts[ch] = len(vals)
        evidence = {ch: {"name": ch, "present": median[ch] is not None, "fresh": True,
                         "score": median[ch], "reason": None if median[ch] is not None else "no_fresh_score"}
                    for ch in ("M", "T", "I")}
        verdicts = {ch: channel_verdict(evidence[ch], context, calib) for ch in ("M", "T", "I")}
        # I is not merely missing: there is no exporter at all in these archives. Keep that
        # distinct from "this block had no fresh I sample", so the block table cannot hide it.
        verdicts["I"] = {"channel": "I", "present": False, "fresh": False, "score": None,
                         "verdict": "NOT_AVAILABLE", "calibration": "NOT_APPLICABLE", "u": None,
                         "reason": "no_imu_preupdate_vs_lidar_update_export"}
        blocks.append({"block_id": bid, "n_frames": len(fs), "context": context,
                       "old_status": {s: sum(1 for f in fs if f["old"]["status"] == s)
                                      for s in sorted({f["old"]["status"] for f in fs})},
                       "median_score": median, "fresh_count": counts, "verdicts": verdicts})
    states = classify_blocks(blocks, calib)
    for blk, st in zip(blocks, states):
        blk.update({k: st[k] for k in ("state", "scope", "reason_codes", "last_suspect_block")})
    return blocks


# ---------------------------------------------------------------------------------------------
def old_reason(frame: Dict[str, Any]) -> List[str]:
    reasons = []
    sup = frame["support"]
    if frame["map_support"] == "EMPTY":
        reasons.append("empty_reference")
    elif sup.get("pass") is False:
        reasons.append("insufficient_support")
    nis = frame["old"]
    if nis.get("nis_source") == "unavailable":
        reasons.append("nis_unavailable")
    elif nis.get("nis_source") == "carried_forward":
        reasons.append("nis_carried_forward")
    if not reasons:
        reasons.append("no_old_unavailable_reason")
    return reasons


def t0_run(key: str) -> Dict[str, Any]:
    spec = RUNS[key]
    frames = [frame_record(r, spec["run_id"]) for r in load_rows(spec["frames"])]
    calib = Calibration()          # empty by design; no independently confirmed normal prefix
    blocks = block_summary(frames, calib)

    def count(pred):
        return sum(1 for f in frames if pred(f))

    un = [f for f in frames if f["old"]["status"] == "UNAVAILABLE"]
    old_reasons: Dict[str, int] = {}
    for f in un:
        for r in old_reason(f):
            old_reasons[r] = old_reasons.get(r, 0) + 1
    state_counts: Dict[str, int] = {}
    for b in blocks:
        state_counts[b["state"]] = state_counts.get(b["state"], 0) + b["n_frames"]
    # Per-channel, how many BLOCKS were actually usable, and why not. OUT_OF_SUPPORT and
    # BLOCKED are kept apart: the first means the channel has a reference for some other
    # context, the second means no normal reference exists at all in this run.
    block_channel = {}
    for ch in ("M", "T", "I"):
        c: Dict[str, int] = {}
        for b in blocks:
            status_key = b["verdicts"][ch]["verdict"]
            if b["verdicts"][ch]["calibration"] in ("BLOCKED", "OUT_OF_SUPPORT", "INCOMPLETE"):
                status_key = f"{status_key}/{b['verdicts'][ch]['calibration']}"
            c[status_key] = c.get(status_key, 0) + 1
        block_channel[ch] = c

    summary = {
        "run_key": key, "run_id": spec["run_id"],
        "inputs": {"frames_sha256": sha256(spec["frames"]),
                   "receipt_sha256": sha256(spec["receipt"]),
                   "summary_sha256": sha256(spec["summary"])},
        "population": {"frames": len(frames), "blocks": len(blocks)},
        "old_status": {s: count(lambda f, s=s: f["old"]["status"] == s)
                       for s in sorted({f["old"]["status"] for f in frames})},
        "old_unavailable_reasons": old_reasons,
        "channel_availability": {
            "M_present": count(lambda f: f["channels"]["M"]["present"]),
            "T_present": count(lambda f: f["channels"]["T"]["present"]),
            "I_present": count(lambda f: f["channels"]["I"]["present"]),
            "M_present_in_unavailable": sum(1 for f in un if f["channels"]["M"]["present"]),
            "T_present_in_unavailable": sum(1 for f in un if f["channels"]["T"]["present"]),
            "M_or_I_present_in_unavailable": sum(
                1 for f in un if f["channels"]["M"]["present"] or f["channels"]["I"]["present"]),
        },
        "calibration": {
            "reference_status": calib.reference_status,
            "conditions": {}, "min_blocks": MIN_BLOCKS,
            "note": ("HEALTHY/trusted/no-injection are not normal truth; the archives carry no "
                     "independently confirmed healthy prefix, so no condition has a reference"),
        },
        "state_counts_by_frame": state_counts,
        "block_channel_status": block_channel,
        "blocks": [{k: b[k] for k in ("block_id", "n_frames", "context", "median_score",
                                      "fresh_count", "state", "scope", "reason_codes")}
                   for b in blocks],
        "missing_items": {
            "I": "no IMU pre-update prediction / LiDAR-update pair, interval, extrinsics or covariance",
            "normal_reference": "no independently confirmed healthy prefix in either archive",
            "labels": "no independent event labels in the archives for error-rate evaluation",
        },
    }
    shadow_path = os.path.join(HERE, f"shadow_{key}.jsonl")
    with open(shadow_path, "w", encoding="utf-8") as fh:
        # per-frame state is its block's state
        state_by_block = {b["block_id"]: b for b in blocks}
        for f in frames:
            b = state_by_block[f["block_id"]]
            row = dict(f)
            row["shadow"] = {"state": b["state"], "scope": b["scope"],
                             "reason_codes": b["reason_codes"],
                             "calibration": {ch: f["channels"][ch]["qualification"]
                                             for ch in ("M", "T", "I")},
                             "last_suspect_block": b["last_suspect_block"]}
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    summary["shadow_jsonl"] = {"path": shadow_path, "rows": len(frames),
                               "sha256": sha256(shadow_path)}
    return summary


def write_manifest():
    manifest = {
        "method": "ALI-H v1 (research observer)",
        "contract": "docs/ADAPTIVE_LOW_INFORMATION_HEALTH_V1_20261112.md (§2-§7, §10)",
        "code_sha256": sha256(os.path.abspath(__file__)),
        "config": {"block_ns": BLOCK_NS, "alarm_u": ALARM_U, "normal_u": NORMAL_U,
                   "min_blocks": MIN_BLOCKS, "require_two_adjacent_blocks": True,
                   "normal_reference": "none (BLOCKED)",
                   "channels": {"M": "node_map NIS", "T": "prev_scan NIS",
                                "I": "NOT_AVAILABLE"}},
        "runs": {k: {"run_id": v["run_id"], "frames": v["frames"],
                     "frames_sha256": sha256(v["frames"])} for k, v in RUNS.items()},
    }
    path = os.path.join(HERE, "manifest.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=1, ensure_ascii=False)
    return manifest


ARTIFACTS = ["t0_A.json", "t0_B.json", "shadow_A.jsonl", "shadow_B.jsonl", "t1_selftest.json"]


def update_artifact_digests() -> None:
    """Record the digest of every produced artifact in the manifest.

    The manifest is written before the run, so it cannot know these values then; this second
    write binds the outputs to the inputs and code the same run used. The manifest itself is not
    included (it cannot hash itself).
    """
    path = os.path.join(HERE, "manifest.json")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as fh:
        manifest = json.load(fh)
    manifest["artifacts"] = {
        name: {"path": os.path.join(HERE, name), "bytes": os.path.getsize(os.path.join(HERE, name)),
               "sha256": sha256(os.path.join(HERE, name))}
        for name in ARTIFACTS if os.path.exists(os.path.join(HERE, name))}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=1, ensure_ascii=False)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] == "t0":
        write_manifest()
        out = {"manifest": os.path.join(HERE, "manifest.json"), "runs": {}}
        for key in ("A", "B"):
            summary = t0_run(key)
            path = os.path.join(HERE, f"t0_{key}.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(summary, fh, indent=1, ensure_ascii=False)
            out["runs"][key] = {k: summary[k] for k in
                                ("population", "old_status", "old_unavailable_reasons",
                                 "channel_availability", "state_counts_by_frame")}
            out["runs"][key]["output"] = path
        update_artifact_digests()
        print(json.dumps(out, indent=1, ensure_ascii=False))
        return 0
    if argv[0] == "selftest":
        sys.path.insert(0, HERE)
        from selftest import run_all
        result = run_all()
        path = os.path.join(HERE, "t1_selftest.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=1, ensure_ascii=False)
        update_artifact_digests()
        print(json.dumps(result, indent=1, ensure_ascii=False))
        return 0 if result["failed"] == 0 else 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
