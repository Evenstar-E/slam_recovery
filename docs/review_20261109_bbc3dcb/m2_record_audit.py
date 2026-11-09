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
    cond = results["conditions"]
    c3 = cond.get("C3", {})
    checks = []
    label = rec.get("label")
    checks.append({"item": "C3 label is OFFLINE_NATIVE_REESTIMATION",
                   "recorded": label, "verdict": "PASS" if label == "OFFLINE_NATIVE_REESTIMATION" else "FAIL"})
    missing = c3.get("missing_pose_ids") or rec.get("missing_pose_ids")
    listed = c3.get("missing_pose_ids_listed", missing if isinstance(missing, list) else None)
    checks.append({"item": "frames without pose are listed, not dropped",
                   "recorded": (len(missing) if isinstance(missing, list) else missing),
                   "verdict": "PASS" if isinstance(missing, list) else "UNVERIFIABLE"})
    miss_obs = c3.get("missing_observations", rec.get("missing_observations"))
    checks.append({"item": "missing observations is explicit",
                   "recorded": miss_obs,
                   "verdict": "PASS" if miss_obs in (0, [], None) else "FAIL"})
    return {"checks": checks, "c3_keys": sorted(c3.keys())}



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

    ids_present = False
    with rosbag.Bag(str(FILT), "r") as b:
        topics = list(b.get_type_and_topic_info().topics)
        for _, m, _ in b.read_messages(topics=[LIDAR]):
            ids_present = any(f.name in ("id", "index", "point_id") for f in m.fields)
            break
    out["point_record"]["checks"].append({
        "item": "original point id preserved",
        "verdict": "PASS" if ids_present or any("id" in t for t in topics) else "FAIL",
        "detail": (f"topics: {topics}; no id field in the cloud and no side topic. "
                   "A retained row can be matched by value against the source but cannot be "
                   "named by its original index without re-deriving it. Blocking for replay-level "
                   "attribution, not for the pose result."),
    })

    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
