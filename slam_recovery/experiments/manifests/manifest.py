"""Reproducible experiment manifest recording (Section 8.3 & 9.5)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
import hashlib
import json
import os


class DataProvenance(str, Enum):
    """Explicit provenance tag required by Review Recommendation #1."""

    REAL_HOST = "REAL_HOST"                  # Executed end-to-end on real compiled SLAM host binary
    INJECTION = "INJECTION"                  # Real host binary executed on deterministically fault-injected bag
    OFFLINE_CONSTRUCT = "OFFLINE_CONSTRUCT"  # Trajectory or state computed by offline replay / graph solver on real host logs
    SYNTHETIC = "SYNTHETIC"                  # Parametric / simulated feature stream
    PLACEHOLDER = "PLACEHOLDER"              # Unverified constant (forbidden in final tables)


def sha256_file_prefix(path: str, max_bytes: int = 4 * 1024 * 1024) -> str:
    """Compute SHA-256 over the first `max_bytes` and file size for fast bag provenance."""
    h = hashlib.sha256()
    size = os.path.getsize(path)
    h.update(f"size:{size}:".encode())
    with open(path, "rb") as f:
        h.update(f.read(max_bytes))
    return h.hexdigest()


@dataclass
class RunManifest:
    run_id: str
    host_system: str                  # e.g., "LIO-SAM", "MM-LINS", "ORB-SLAM3"
    baseline_variant: str             # "B0" .. "B7"
    sequence_name: str
    input_bag_path: str
    input_bag_hash: str
    provenance: str = DataProvenance.REAL_HOST.value
    gt_source: str = "Leica"          # "Leica" for hall/door/lift, "Mocap" for room/room_dark, "RTK_INS" for street/gate
    seed: int = 42
    injection_type: str = "clean"
    injection_params: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, Any] = field(default_factory=dict)
    created_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def save_json(self, output_path: str) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2, ensure_ascii=False)
