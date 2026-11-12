"""One JSON line per paired frame: why the frame was, or was not, fed to the detector.

The summary keeps at most 2 000 diagnostics and says only UNAVAILABLE / AVAILABLE. That cannot
answer which precondition failed. This recorder is a separate stream: every paired frame gets a
line, appended and flushed, with no cap, carrying the support evaluation and the NIS branch that
produced the answer at the time it was produced.

It observes; it does not decide. The support mask and the NIS come from the same calls the
decision used, and the point lists are trimmed (not recomputed) for frames that were scored.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional


class AvailabilityRecorder:
    """Append-only JSONL stream of per-frame availability evidence."""

    # Scored frames keep a sample of their point lists; frames that could not be scored keep all
    # of them, because those are the ones whose reason has to be reproducible offline.
    POINT_SAMPLE_FOR_AVAILABLE = 20

    def __init__(self, path: Optional[str], run_id: str = "") -> None:
        self.path = path or ""
        self.run_id = run_id
        self.enabled = bool(self.path)
        self.rows = 0
        self._fh = None
        if self.enabled:
            os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
            self._fh = open(self.path, "a", encoding="utf-8")

    @classmethod
    def _finite(cls, value):
        """JSON has no inf/nan: keep the branch's kind field, write the value as null."""
        if isinstance(value, float) and not (value == value and abs(value) != float("inf")):
            return None
        if isinstance(value, dict):
            return {k: cls._finite(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls._finite(v) for v in value]
        return value

    def record(self, row: Dict[str, Any]) -> None:
        if not self.enabled or self._fh is None:
            return
        row = self._finite(dict(row))
        row.setdefault("run_id", self.run_id)
        self._trim(row)
        self._fh.write(json.dumps(row, allow_nan=False, default=float) + "\n")
        self._fh.flush()
        self.rows += 1

    def _trim(self, row: Dict[str, Any]) -> None:
        if row.get("status") == "AVAILABLE" and not row.get("boundary"):
            for key in ("support", "nis"):
                block = row.get(key)
                if not isinstance(block, dict):
                    continue
                points = block.pop("points", None)
                if points is not None:
                    block["points_saved"] = min(len(points), self.POINT_SAMPLE_FOR_AVAILABLE)
                    block["points_total"] = len(points)
                    block["points"] = points[: self.POINT_SAMPLE_FOR_AVAILABLE]
                hold = block.get("holdout")
                if isinstance(hold, dict):
                    pts = hold.pop("points", None)
                    if pts is not None:
                        hold["points_saved"] = min(len(pts), self.POINT_SAMPLE_FOR_AVAILABLE)
                        hold["points_total"] = len(pts)
                        hold["points"] = pts[: self.POINT_SAMPLE_FOR_AVAILABLE]

    def close(self) -> None:
        if self._fh is not None:
            self._fh.close()
            self._fh = None
