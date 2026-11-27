import hashlib
import json
from pathlib import Path
import sys

root = Path.home() / "vio-multiseq-20261127"
selected = sys.argv[1]
path = Path("/mnt/e/vio-multiseq-20261127") / f"{selected}.bag"
published = json.loads((root / "config/UPSTREAM_ROSBAGS.json").read_text())
matches = [row for row in published if Path(row["path"]).name.startswith(f"{selected}_")]
assert len(matches) == 1
entry = matches[0]
sha = hashlib.sha256()
with path.open("rb") as stream:
    while True:
        block = stream.read(8 << 20)
        if not block:
            break
        sha.update(block)
digest = sha.hexdigest()
size = path.stat().st_size
report = {"sequence": selected, "sha256": digest, "bytes": size,
          "official_rosbag": entry["path"], "official_bytes": entry["size"],
          "official_sha256": entry["lfs"]["oid"]}
if selected == "exp01":
    input_receipt = json.loads((root / "config/EXP01_INPUT_RECEIPT.json").read_text())
    report["official_verified_before_projection"] = (
        input_receipt["raw_stream_fully_verified"] and input_receipt["raw_bytes"] == entry["size"]
        and input_receipt["raw_sha256"] == entry["lfs"]["oid"] and input_receipt["compact_bytes"] == size)
    report["projection_receipt"] = input_receipt
    report["match"] = report["official_verified_before_projection"]
else:
    report["match"] = digest == entry["lfs"]["oid"] and size == entry["size"]
(root / "receipts" / f"{selected}-sha.json").write_text(json.dumps(report, indent=2))
print(report, flush=True)
if not report["match"]:
    raise SystemExit(1)
