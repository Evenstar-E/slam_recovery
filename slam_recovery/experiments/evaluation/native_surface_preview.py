"""Score an isolated native-map preview before committing it. Takes no survey data."""

import argparse
from dataclasses import asdict
import json

import numpy as np

from ...validation.surface_admission import SurfaceEvidence, SurfaceView, surface_admission, voxel_keys


def evaluate_bundle(data) -> SurfaceEvidence:
    trusted = set(map(tuple, voxel_keys(data["trusted_xyz"]).tolist()))
    preview = set(map(tuple, voxel_keys(data["preview_xyz"]).tolist()))
    if not trusted.issubset(preview):
        return SurfaceEvidence("MISSING", "preview_removes_trusted_voxels")
    views = tuple(
        SurfaceView(str(data[f"frame_{i}"].item()), str(data[f"station_{i}"].item()),
                    int(data[f"stamp_ns_{i}"].item()), data[f"xyz_{i}"])
        for i in (1, 2)
    )
    return surface_admission(trusted, preview, views,
                             candidate_end_ns=int(data["candidate_end_ns"].item()),
                             decision_ns=int(data["decision_ns"].item()))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", help="NPZ with frozen native checkpoint, isolated preview and two held-out views")
    args = parser.parse_args()
    with np.load(args.bundle, allow_pickle=False) as data:
        result = evaluate_bundle(data)
    print(json.dumps({**asdict(result), "coverage_gain": result.coverage_gain}, allow_nan=False))


if __name__ == "__main__":
    main()
