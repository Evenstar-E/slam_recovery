"""Read back each paired experiment's evidence before publishing its summary."""
from pathlib import Path
import gzip
import hashlib
import json
import tarfile

root = Path.home() / "vio_matrix_evidence_20261127"
completed, incomplete = {}, []
staged = ["exp01", "exp04", "exp05", "exp16", "exp18"]
hosts = ("orb", "vins", "okvis")


def json_file(p):
    return json.loads(p.read_text())


def rows(p):
    if not p.is_file():
        return []
    return [json.loads(line) for line in p.open()]


for sequence in staged:
    results = {}
    expected = root / sequence / "receipts" / f"{sequence}-sha.json"
    if not expected.is_file():
        incomplete.append(sequence)
        continue
    assert json_file(expected)["match"], sequence
    archive = root / sequence / "evidence.tar.gz"
    with tarfile.open(archive, "r:gz") as stream:
        files = len(stream.getnames())
    assert files > 10
    cleanup = json_file(root/sequence/"cleanup.json")
    assert cleanup["copied_rosbag"]["bytes"] == json_file(expected)["bytes"]
    expected_input = json_file(root / sequence / "receipts" / f"{sequence}-input.json")
    for host in hosts:
        name = sequence
        if host == "orb" and sequence == "exp18" and (root/"exp18-nodrain"/"cleanup.json").is_file():
            name = "exp18-nodrain"
            proof = json_file(root/name/"receipts"/f"{name}-content.json")
            assert proof["all_image_sha_match"] and proof["compared_with_exp18_original_frozen_images"] == expected_input["pairs_in_imu_support"]
        tag = "-startup-fixed" if name == "exp18" and host in ("orb", "vins") else ""
        arm_data, arm_clock = {}, {}
        for mode in ("native", "recover"):
            run = root / name / "results" / f"{name}-{host}-{mode}{tag}"
            result = json_file(run/"result.json")
            score = json_file(root/name/"receipts"/f"{name}-score.json")[host]["arms"][mode]
            log = rows(run/"log/events.jsonl")
            public = rows(run/"external.jsonl")
            assert not result["injected_faults"] and result["input_pairs"] == expected_input["pairs_in_imu_support"]
            assert len(public) == score["status"]["public_pairs"]
            assert all(a["timestamp"] < b["timestamp"] for a,b in zip(public, public[1:]))
            assert all(n == row["delivery_id"] for n,row in enumerate(public,1))
            parameters = next(row for row in log if row["type"]=="run")
            assert not parameters["fault_intervals_s"] and parameters["realtime"]
            if host == "orb" and name != "exp18":
                assert not parameters["drain_local_mapping"]
            arm_clock[mode] = {r["timestamp"]: r for r in rows(run/"log/input_clock.jsonl")}
            arm_data[mode] = {
                "worker_fingerprint": result["worker_sha256"],
                "plugin_revision": result["plugin_revision"],
                "input_clocked": len(arm_clock[mode]),
                "public": len(public),
                "controller_exit": result.get("controller_exit"),
                "subscriber_exit": result.get("subscriber_exit"),
                "cpu_slot": result["cpu_slot"],
            }
        shared = arm_clock["native"].keys() & arm_clock["recover"].keys()
        assert bool(shared)
        assert all(arm_clock["native"][t]["image_sha256"] == arm_clock["recover"][t]["image_sha256"]
                   and arm_clock["native"][t]["imu_count"] == arm_clock["recover"][t]["imu_count"] for t in shared)
        for key in ("worker_fingerprint","plugin_revision","cpu_slot"):
            assert arm_data["native"][key] == arm_data["recover"][key]
        results[host] = {"run_pair": arm_data, "matched_observed_input_digests": len(shared)}
    completed[sequence] = {"results": results, "archive_items": files,
                           "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
                           "temporary_source_removed_bytes": cleanup["copied_rosbag"]["bytes"],
                           "temporary_derived_removed_bytes": cleanup["derived_images_and_imu"]["bytes"]}

status = {"completed": completed, "missing_sequences": incomplete,
          "campus12": "0 image streams according to native rosbag info"}
(root / "AUDIT.json").write_text(json.dumps(status, indent=2))
print("verified recordings", sorted(completed), "pending", incomplete)
