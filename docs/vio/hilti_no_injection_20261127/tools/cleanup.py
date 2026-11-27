import json
from pathlib import Path
import shutil
import sys

seq = sys.argv[1]
assert seq in {"exp01", "exp04", "exp05", "exp16", "exp18"}
root = Path.home() / "vio-multiseq-20261127"
raw_root = Path("/mnt/e/vio-multiseq-20261127")
score = json.loads((root / "receipts" / f"{seq}-score.json").read_text())
sha = json.loads((root / "receipts" / f"{seq}-sha.json").read_text())
assert sha["match"]
assert all(set(score[host]["arms"]) == {"native", "recover"} for host in ("orb", "vins", "okvis"))
assert (root / "receipts" / f"{seq}-isolation-observations.json").is_file()
raw = raw_root / f"{seq}.bag"
assert raw.is_file() and not raw.is_symlink() and raw.resolve().parent == raw_root.resolve()
assert raw.stat().st_size == sha["bytes"]
derived = root / "inputs" / seq
assert derived.is_dir() and not derived.is_symlink() and derived.resolve().parent == (root / "inputs").resolve()
removed = {"copied_rosbag": {"path": str(raw), "bytes": sha["bytes"], "sha256": sha["sha256"]},
           "derived_images_and_imu": {"path": str(derived), "bytes": sum(
               p.stat().st_size for p in derived.rglob("*") if p.is_file())},
           "orb_checkpoint_payloads": []}
raw.unlink()
shutil.rmtree(derived)
for store in (root / "results").glob(f"{seq}-orb-*/log/checkpoints"):
    assert store.resolve().is_relative_to(root.resolve()) if sys.version_info >= (3, 9) else root.resolve() in store.resolve().parents
    pack = store / "map.pack"
    if pack.is_file() and not pack.is_symlink():
        removed["orb_checkpoint_payloads"].append({"path": str(pack), "bytes": pack.stat().st_size})
        pack.unlink()
    for file in store.rglob("*"):
        if file.is_file() and not file.is_symlink() and (file.suffix in (".map", ".state", ".atlas") or file.name.startswith("staged.")):
            removed["orb_checkpoint_payloads"].append({"path": str(file), "bytes": file.stat().st_size})
            file.unlink()
assert not raw.exists() and not derived.exists()
(root / "receipts" / f"{seq}-cleanup.json").write_text(json.dumps(removed, indent=2))
print(json.dumps(removed), flush=True)
