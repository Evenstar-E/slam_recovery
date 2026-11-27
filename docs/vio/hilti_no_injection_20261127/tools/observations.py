from collections import defaultdict
import json
from pathlib import Path
import sys

import cv2
import numpy as np


root = Path.home() / "vio-multiseq-20261127"
seq = sys.argv[1]
frames = root / "inputs" / seq / "mav0/cam0"
if not frames.is_dir():
    sys.exit(0)
with (frames / "data.csv").open() as handle:
    stamps = [int(line.split(",")[0]) for line in handle if not line.startswith("#")]
events = defaultdict(list)
for log in sorted((root / "results").glob(f"{seq}-*-recover*/log/events.jsonl")):
    with log.open() as handle:
        for line in handle:
            row = json.loads(line)
            if row["type"] != "isolate":
                continue
            stamp = row["first_untrusted"]
            events[stamp].append(log.parents[1].name)
detector = cv2.FastFeatureDetector_create(threshold=15)
out = {}
for stamp, runs in events.items():
    i = stamps.index(stamp)
    observations = []
    for t in stamps[max(0, i-4):i+6]:
        features = []
        for cam in ("cam0", "cam1"):
            original = cv2.imread(str(root / "inputs" / seq / f"mav0/{cam}/data/{t}.png"),
                                  cv2.IMREAD_GRAYSCALE)
            features.append(dict(fast_count=len(detector.detect(original)), intensity_avg=float(np.mean(original)),
                                 intensity_p95=float(np.quantile(original, .95)),
                                 stddev=float(np.std(original))))
        observations.append(dict(timestamp=t, relative_ms=(t-stamp)/1e6, cams=features))
    out[stamp] = dict(runs=runs, observations=observations, t_from_start_s=(stamp-stamps[0])/1e9)
(root / "receipts" / f"{seq}-isolation-observations.json").write_text(json.dumps(out, indent=2))
