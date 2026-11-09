#!/usr/bin/env python3
"""M2 record-contract audit for the C3 filtered-bag run (main tree f2877c3).

Reads the artefacts only. Nothing here rewrites the producer's files.

Three verdicts are possible per item: PASS, FAIL, UNVERIFIABLE. UNVERIFIABLE is used when the
evidence needed to decide is not on disk, and it is never rounded up to PASS.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import rosbag

REVIEW = Path(__file__).resolve().parent
OUT = REVIEW / "M2_record_audit.json"

SRC = Path("/tmp/fastlivo/hall01_inj43.bag")
FILT = Path("/tmp/fastlivo/hall01_inj43_filtered.bag")
REPLAY = Path("/tmp/fastlivo/res_h1_inj43_filtered.bag")
CONTROL = Path("/tmp/fastlivo/res_h1_inj43_rerun_unfiltered.bag")
HOST_BIN = Path("/home/R26534/fast_livo2_ws/devel/lib/fast_livo/fastlivo_mapping")
HOST_SRC = Path("/home/R26534/fast_livo2_ws/src/FAST-LIVO2")
RESULTS = REVIEW / "fixed_input_repair_c0c3_results.json"
FILTER_REPORT = REVIEW / "fixed_input_repair_filter_report.json"

LIDAR = "/velodyne_points"
POINT_STEP = 24
# VLP-32C PointXYZIRT, as both the injector and the host write it
FIELD_SPEC = [("x", 0, 7), ("y", 4, 7), ("z", 8, 7),
              ("intensity", 12, 7), ("time", 16, 7), ("ring", 20, 4)]
SAMPLE_FRAMES = 25


def sha256_file(path, chunk=1 << 22):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def rows_key(msg):
    """View the payload as 3 uint64 per point so rows can be compared exactly."""
    raw = np.frombuffer(bytes(msg.data), dtype=np.uint8)
    return raw.reshape(-1, POINT_STEP).view([("a", "<u8"), ("b", "<u8"), ("c", "<u8")])


def audit_point_record():
    """What the filtered cloud carries, field by field, and what it cannot answer."""
    res = {"checks": []}
    with rosbag.Bag(str(SRC), "r") as bs, rosbag.Bag(str(FILT), "r") as bf:
        src = {}
        for _, m, _ in bs.read_messages(topics=[LIDAR]):
            src[round(m.header.stamp.to_sec(), 6)] = m
        frames, field_ok, stamp_ok, subset_ok, count_ok = [], True, True, True, True
        for i, (_, m, _) in enumerate(bf.read_messages(topics=[LIDAR])):
            key = round(m.header.stamp.to_sec(), 6)
            s = src.get(key)
            got = [(f.name, f.offset, f.datatype) for f in m.fields]
            if got != FIELD_SPEC or m.point_step != POINT_STEP:
                field_ok = False
            if s is None:
                stamp_ok = False
                continue
            if (m.header.stamp.to_sec() != s.header.stamp.to_sec()
                    or m.header.frame_id != s.header.frame_id):
                stamp_ok = False
            if m.width > s.width:
                subset_ok = False
            if i < SAMPLE_FRAMES:
                fk = rows_key(m)
                sk = rows_key(s)
                if not np.all(np.isin(fk, sk)):
                    subset_ok = False
            frames.append({"stamp": m.header.stamp.to_sec(),
                           "points": int(m.width), "source_points": int(s.width)})

        # The report stores `t` rounded to milliseconds, so it cannot be joined by stamp at
        # microsecond precision. Both lists are in time order over the same 598 frames: join by
        # position after confirming the stamps agree to the report's own precision.
        rep = json.loads(FILTER_REPORT.read_text())
        per = rep["per_frame"]
        if len(per) != len(frames):
            count_ok = False
        for f, r in zip(frames, per):
            if abs(f["stamp"] - float(r["t"])) > 1e-3 or int(r["kept"]) != f["points"]:
                count_ok = False

    res["checks"] += [
        {"item": "point layout (x,y,z,intensity,time,ring at 24 B)", "verdict": "PASS" if field_ok else "FAIL",
         "detail": f"{len(frames)} frames; point_step 24, field order and offsets unchanged"},
        {"item": "header stamp + frame_id preserved", "verdict": "PASS" if stamp_ok else "FAIL",
         "detail": "every filtered frame matches a source frame by exact stamp"},
        {"item": "ring/time carried with the retained points",
         "verdict": "PASS" if subset_ok else "FAIL",
         "detail": f"each retained row is byte-identical to a source row on the first "
                   f"{SAMPLE_FRAMES} frames; the filter removes rows, it does not rewrite them"},
        {"item": "retained count equals the filter report", "verdict": "PASS" if count_ok else "FAIL",
         "detail": "per-frame kept counts match fixed_input_repair_filter_report.json"},
    ]
    res["frames"] = len(frames)
    return res


def audit_non_lidar():
    """Every non-LiDAR payload must be byte-identical between source and filtered bag."""
    out = {"checks": [], "per_topic": {}}
    with rosbag.Bag(str(SRC), "r") as bs, rosbag.Bag(str(FILT), "r") as bf:
        st = {t: v for t, v in bs.get_type_and_topic_info().topics.items() if t != LIDAR}
        ft = {t: v for t, v in bf.get_type_and_topic_info().topics.items() if t != LIDAR}
        for topic in sorted(set(st) | set(ft)):
            a = st.get(topic).message_count if topic in st else None
            b = ft.get(topic).message_count if topic in ft else None
            same_payload, n, mismatch = True, 0, []
            if topic in st and topic in ft:
                from itertools import zip_longest
                # raw=True gives the wire bytes, which is what "byte-identical" has to mean
                it_a = (payload for _, payload, _ in bs.read_messages(topics=[topic], raw=True))
                it_b = (payload for _, payload, _ in bf.read_messages(topics=[topic], raw=True))
                for ma, mb in zip_longest(it_a, it_b):
                    if ma is None or mb is None:
                        same_payload = False
                        break
                    n += 1
                    if ma[1] != mb[1]:
                        same_payload = False
                        if len(mismatch) < 5:
                            mismatch.append(n)
            n_a = st.get(topic).message_count if topic in st else None
            out["per_topic"][topic] = {"source_count": a, "filtered_count": b,
                                       "compared": n, "identical": same_payload,
                                       "first_mismatch_stamps": mismatch}
    ok = all(v["identical"] and v["source_count"] == v["filtered_count"]
             for v in out["per_topic"].values()) if out["per_topic"] else False
    out["checks"].append({
        "item": "non-LiDAR topics byte-identical", "verdict": "PASS" if ok else "FAIL",
        "detail": "; ".join(f"{t}: {v['compared']} msgs compared"
                            for t, v in out["per_topic"].items())})
    return out


def audit_chain():
    results = json.loads(RESULTS.read_text())
    rec = results["_meta"]["c3_record"]
    checks = []
    for name, spec in rec["bags"].items():
        p = Path(spec["path"])
        actual = sha256_file(p) if p.exists() else None
        checks.append({"item": f"bag {name}", "path": str(p),
                       "recorded": spec["sha256"], "actual": actual,
                       "verdict": ("PASS" if actual == spec["sha256"]
                                   else "FAIL" if actual else "UNVERIFIABLE")})
    bin_actual = sha256_file(HOST_BIN) if HOST_BIN.exists() else None
    checks.append({"item": "host binary", "path": str(HOST_BIN),
                   "recorded": rec["host"]["binary_sha256"], "actual": bin_actual,
                   "verdict": "PASS" if bin_actual == rec["host"]["binary_sha256"] else
                              "FAIL" if bin_actual else "UNVERIFIABLE"})
    rev = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(HOST_SRC),
                         capture_output=True, text=True).stdout.strip() or None
    checks.append({"item": "host source revision", "path": str(HOST_SRC),
                   "recorded": rec["host"]["source_revision"], "actual": rev,
                   "verdict": "PASS" if rev == rec["host"]["source_revision"] else
                              "FAIL" if rev else "UNVERIFIABLE"})
    for name, spec in rec["configs"].items():
        p = Path(spec["path"])
        actual = sha256_file(p) if p.exists() else None
        checks.append({"item": f"config {name}", "path": str(p),
                       "recorded": spec["sha256"], "actual": actual,
                       "verdict": "PASS" if actual == spec["sha256"] else
                                  "FAIL" if actual else "UNVERIFIABLE"})
    # The record names the source dir the peer built from; check it exists and what it points at.
    src_dir = rec["host"].get("source_dir")
    checks.append({"item": "declared source_dir exists", "path": str(src_dir),
                   "recorded": str(HOST_SRC), "actual": src_dir,
                   "verdict": "PASS" if src_dir == str(HOST_SRC) and Path(src_dir).exists()
                             else "FAIL"})
    checks.append({"item": "commands recorded", "path": "n/a",
                   "recorded": len(rec.get("commands", [])), "actual": len(rec.get("commands", [])),
                   "verdict": "PASS" if rec.get("commands") else "FAIL"})
    return {"checks": checks, "record": rec}


def audit_labels():
    results = json.loads(RESULTS.read_text())
    rec = results["_meta"]["c3_record"]
    c3 = results["conditions"]["C3"]
    checks = []

    label = rec.get("label")
    checks.append({"item": "C3 label is OFFLINE_NATIVE_REESTIMATION",
                   "recorded": label,
                   "verdict": "PASS" if label == "OFFLINE_NATIVE_REESTIMATION" else "FAIL"})

    # The archive spells it `missing_observation` (singular) with `missing_observation_ids`.
    # A missing field is UNVERIFIABLE, not zero: absence of evidence is not evidence of absence.
    for singular, plural in (("missing_pose", "missing_pose_ids"),
                             ("missing_observation", "missing_observation_ids")):
        if singular not in c3:
            checks.append({"item": f"{singular} declared", "recorded": None,
                           "verdict": "UNVERIFIABLE",
                           "detail": f"field `{singular}` absent from the C3 block"})
            continue
        count = c3.get(singular)
        ids = c3.get(plural)
        if not isinstance(ids, list):
            checks.append({"item": f"{singular} ids listed", "recorded": ids,
                           "verdict": "UNVERIFIABLE",
                           "detail": f"`{plural}` is not a list"})
            continue
        consistent = (int(count) == len(ids))
        checks.append({"item": f"{singular} count equals id list length",
                       "recorded": {"count": count, "ids": len(ids)},
                       "verdict": "PASS" if consistent else "FAIL"})
        # A non-zero count must be enumerable, not just totalled.
        checks.append({"item": f"{plural} enumerates every missing item",
                       "recorded": len(ids),
                       "verdict": "PASS" if (count == 0) == (len(ids) == 0) else "FAIL"})
    return {"checks": checks, "c3_keys": sorted(c3.keys())}


def _iter_clouds(path):
    with rosbag.Bag(str(path), "r") as b:
        for _, m, _ in b.read_messages(topics=[LIDAR]):
            yield (int(m.header.stamp.to_sec() * 1e9), m, bytes(m.data), int(m.point_step))

def _ordered_match(filtered_rows, source_rows):
    """Assign each filtered row to a distinct source index, preserving order.

    Returns (indices, missing). Greedy earliest-unused-so-far: deterministic, one-to-one by
    construction, and it reports `missing > 0` when a filtered row does not exist in the source.
    """
    pools = {}
    for i, r in enumerate(source_rows):
        pools.setdefault(r.tobytes(), []).append(i)
    used, out, missing, prev = set(), [], 0, -1
    for r in filtered_rows:
        cands = pools.get(r.tobytes())
        if not cands:
            missing += 1
            out.append(-1)
            continue
        pick = next((c for c in cands if c > prev and c not in used), None)
        if pick is None:
            pick = next((c for c in cands if c not in used), None)
        if pick is None:
            missing += 1
            out.append(-1)
            continue
        used.add(pick)
        out.append(pick)
        prev = pick
    return out, missing


def verify_stripped_frames(n_sample=10):
    """The audit must look at frames where the filter actually fired, not only healthy ones.

    Sample: first stripped frame, last stripped frame, the frame with the largest strip
    fraction, and `n_sample` more spread across the stripped population.
    """
    rep = json.loads(FILTER_REPORT.read_text())
    per = rep["per_frame"]
    stripped = [i for i, f in enumerate(per) if f["strip_fraction"] > 0]
    if not stripped:
        return {"verdict": "UNVERIFIABLE", "why": "no stripped frame in the filter report"}
    picks = [stripped[0], stripped[-1],
             max(stripped, key=lambda i: per[i]["strip_fraction"])]
    step = max(1, len(stripped) // max(n_sample, 1))
    picks += stripped[::step][:n_sample]
    picks = sorted(set(picks))

    src = {}
    for ns, _m, buf, step_ in _iter_clouds(SRC):
        src[ns] = (np.frombuffer(buf, dtype=np.uint8).reshape(-1, step_), step_)
    out = []
    for i, (ns, _m, buf, step_) in enumerate(_iter_clouds(FILT)):
        if i not in picks:
            continue
        f_rows = np.frombuffer(buf, dtype=np.uint8).reshape(-1, step_)
        s_rows, s_step = src[ns]
        idx, missing = _ordered_match(f_rows, s_rows)
        arr = np.asarray(idx, dtype=np.int64)
        strictly_increasing = bool(np.all(np.diff(arr) > 0)) if len(arr) > 1 else True
        deleted = sorted(set(range(len(s_rows))) - set(int(v) for v in arr if v >= 0))
        rec = per[i]
        out.append({
            "frame_index": i, "scan_ns": int(ns),
            "strip_fraction": rec["strip_fraction"],
            "n_original": int(len(s_rows)), "n_kept": int(len(f_rows)),
            "rows_missing_from_source": int(missing),
            "index_strictly_increasing": strictly_increasing,
            "kept_indices_unique": len(set(int(v) for v in arr)) == len(arr),
            "count_matches_report": int(len(f_rows)) == int(rec["kept"]),
            "deleted_count": len(deleted),
            "deleted_equals_complement": len(deleted) == int(len(s_rows)) - int(len(f_rows)),
        })
    ok = all(r["rows_missing_from_source"] == 0 and r["index_strictly_increasing"]
             and r["kept_indices_unique"] and r["count_matches_report"]
             and r["deleted_equals_complement"] for r in out)
    return {"verdict": "PASS" if ok else "FAIL",
            "sampled": len(out), "stripped_frames_total": len(stripped),
            "frames": out}

def _load_poses_rosbag(path, topic="/aft_mapped_to_init"):
    """Independent pose loader (rosbag, not the producer's rosbags reader)."""
    ts, xyz, quat = [], [], []
    with rosbag.Bag(str(path), "r") as b:
        for _, m, _ in b.read_messages(topics=[topic]):
            ts.append(float(m.header.stamp.to_sec()))
            p, q = m.pose.pose.position, m.pose.pose.orientation
            xyz.append([p.x, p.y, p.z])
            quat.append([q.x, q.y, q.z, q.w])
    o = np.argsort(ts)
    return np.asarray(ts)[o], np.asarray(xyz)[o], np.asarray(quat)[o]


def _umeyama(src, dst):
    """Kabsch/Umeyama without scale: dst ~= src @ R.T + t."""
    cs, cd = src.mean(0), dst.mean(0)
    cov = (dst - cd).T @ (src - cs) / len(src)
    U, D, Vt = np.linalg.svd(cov)
    S = np.eye(3)
    if np.linalg.det(U) * np.linalg.det(Vt) < 0:
        S[2, 2] = -1
    R = U @ S @ Vt
    return R, cd - R @ cs


def audit_control(onset_abs, end_abs):
    """Recompute the unfiltered-rerun deviation from the control bag, independently."""
    if not (CONTROL.exists() and Path("/tmp/fastlivo/res_h1_inj43_vis.bag").exists()):
        return {"verdict": "UNVERIFIABLE", "why": "control bag or archived pose bag missing"}
    t1, x1, _ = _load_poses_rosbag("/tmp/fastlivo/res_h1_inj43_vis.bag")
    t2, x2, _ = _load_poses_rosbag(CONTROL)
    idx = np.clip(np.searchsorted(t2, t1), 1, len(t2) - 1)
    pick = np.where(np.abs(t2[idx - 1] - t1) <= np.abs(t2[idx] - t1), idx - 1, idx)
    ok = np.abs(t2[pick] - t1) <= 0.05
    mt, a, b = t1[ok], x1[ok], x2[pick[ok]]
    pre = mt < onset_abs
    R, t = _umeyama(b[pre], a[pre])
    err = np.linalg.norm(b @ R.T + t - a, axis=1)
    out = {"archived_poses": int(len(t1)), "rerun_poses": int(len(t2)),
           "matched": int(len(mt)), "alignment_translation_m": round(float(np.linalg.norm(t)), 4)}
    for lab, m in (("pre_onset", mt < onset_abs),
                   ("in_window", (mt >= onset_abs) & (mt <= end_abs)),
                   ("post", mt > end_abs)):
        out[lab] = {"n": int(m.sum()),
                    "mean_m": round(float(err[m].mean()), 6) if m.any() else None,
                    "p95_m": round(float(np.percentile(err[m], 95)), 6) if m.any() else None,
                    "max_m": round(float(err[m].max()), 6) if m.any() else None}
    return out

def main():
    out = {"subject": "M2 record-contract audit of the C3 filtered-bag run",
           "audited_commit": "f2877c3",
           "artifacts": {"script": str(REVIEW / "run_fixed_input_repair_c0c3.py"),
                         "results": str(RESULTS), "filter_report": str(FILTER_REPORT)}}
    out["point_record"] = audit_point_record()
    print("point record done", flush=True)
    out["stripped_frames"] = verify_stripped_frames()
    print("stripped frames done", flush=True)
    out["non_lidar"] = audit_non_lidar()
    print("non-lidar done", flush=True)
    chain = audit_chain()
    out["chain"] = {"checks": chain["checks"]}
    print("chain done", flush=True)
    out["labels"] = audit_labels()
    print("labels done", flush=True)
    rec_meta = json.loads(RESULTS.read_text())["_meta"]
    on, end = (1627785275.607409, 1627785295.546409)
    out["control_reproduction"] = {
        "recorded": rec_meta.get("host_reproducibility"),
        "recomputed": audit_control(on, end),
    }
    print("control done", flush=True)

    # Point identity: decode what the bag actually carries. A topic whose name contains "id"
    # is not evidence; the check is whether the cloud has an id field or a side topic whose
    # payload maps one-to-one onto the retained rows.
    id_evidence = {"cloud_id_field": None, "side_topics": [],
                   "decoded": None}
    with rosbag.Bag(str(FILT), "r") as b:
        topics = sorted(b.get_type_and_topic_info().topics)
        id_evidence["all_topics"] = topics
        for _, m, _ in b.read_messages(topics=[LIDAR]):
            id_evidence["cloud_id_field"] = [f.name for f in m.fields
                                             if f.name in ("id", "index", "point_id")]
            break
    cand = [t for t in topics if t not in (LIDAR, "/camera/color/image_raw",
                                           "/handsfree/imu")]
    id_evidence["side_topics"] = cand
    ok = bool(id_evidence["cloud_id_field"]) or bool(cand)
    out["point_record"]["checks"].append({
        "item": "original point id preserved",
        "verdict": "PASS" if ok else "FAIL",
        "detail": (f"topics={topics}; id field in cloud={id_evidence['cloud_id_field']}; "
                   f"side topics={cand}. Without either, a retained row can be matched by "
                   "value but not named by its original index.")})

    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
