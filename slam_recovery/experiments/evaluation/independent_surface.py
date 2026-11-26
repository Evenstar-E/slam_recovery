"""Score final map exports against a frozen, independently surveyed visible region."""

import argparse
from dataclasses import asdict, dataclass
import json
from typing import Optional

import numpy as np

from ...validation.spatial_index import RadiusIndex
from ...validation.surface_admission import TOLERANCE_M, VOXEL_M, centers, nearby, voxel_keys


ARMS = ("raw", "isolation", "forced", "gated")


@dataclass(frozen=True)
class SurfaceScore:
    surveyed_surface_voxels: int
    evaluated_map_voxels: int
    covered_surface_voxels: int
    off_surface_voxels: int
    coverage: float
    pollution: Optional[float]
    map_voxels_outside_mask: int


def read_mask(indices: np.ndarray) -> set:
    if indices.ndim != 2 or indices.shape[1] != 3 or indices.dtype.kind not in "iu":
        raise ValueError("visible_keys must contain integer XYZ voxel indices")
    return set(map(tuple, indices.tolist()))


def _visible(keys: np.ndarray, mask: set) -> np.ndarray:
    inside = np.fromiter((tuple(k) in mask for k in keys), dtype=bool, count=len(keys))
    return keys[inside]


def score_arms(
    tls_xyz: np.ndarray, masks: dict, arms: dict, pre_fault_xyz: np.ndarray,
) -> dict:
    """Masks and surveyed surface are fixed before opening any export.

    Each mask contains both observable surface voxels and surveyed free space.
    All XYZ inputs use the same fixed survey gauge and map voxel grid.
    """
    all_tls_keys = voxel_keys(tls_xyz)
    maps = {arm: voxel_keys(arms[arm]) for arm in ARMS}
    pre_fault = voxel_keys(pre_fault_xyz)
    pre_fault_keys = set(map(tuple, pre_fault.tolist()))
    results = {}
    for name, indices in masks.items():
        mask = read_mask(indices)
        tls = centers(_visible(all_tls_keys, mask))
        if not len(tls):
            raise ValueError(f"{name}: common visibility mask has no surveyed surface")
        tls_index = RadiusIndex(tls, TOLERANCE_M)
        protected_ref = nearby(centers(_visible(pre_fault, mask)), tls, TOLERANCE_M)
        reports = {}
        for name_arm, points in maps.items():
            map_keys = _visible(points, mask)
            visible_map = centers(map_keys)
            covered = nearby(visible_map, tls, TOLERANCE_M)
            off_surface = ~tls_index.within_radius_mask(visible_map, TOLERANCE_M)
            off = int(off_surface.sum())
            new_off = sum(tuple(k) not in pre_fault_keys for k in map_keys[off_surface])
            reports[name_arm] = {
                **asdict(SurfaceScore(
                    len(tls), len(visible_map), int(covered.sum()), off,
                    float(covered.mean()), off / len(visible_map) if len(visible_map) else None,
                    len(points) - len(visible_map),
                )),
                "new_off_surface_voxels": new_off,
                "lost_previously_covered_surface_voxels": int((protected_ref & ~covered).sum()),
            }

        g, i, f = (reports[arm] for arm in ("gated", "isolation", "forced"))
        cg = g["covered_surface_voxels"] - i["covered_surface_voxels"]

        def pollution_diff_pp(comparison):
            if g["pollution"] is None or comparison["pollution"] is None:
                return None
            return 100.0 * (g["pollution"] - comparison["pollution"])

        d_forced, d_isolated = pollution_diff_pp(f), pollution_diff_pp(i)
        gp, ip, fp = (reports[a]["evaluated_map_voxels"] for a in ("gated", "isolation", "forced"))
        go, io, fo = (reports[a]["off_surface_voxels"] for a in ("gated", "isolation", "forced"))
        coverage_ok = 100 * cg >= 5 * len(tls)
        forced_ok = None if d_forced is None else 100 * (go * fp - fo * gp) <= -5 * gp * fp
        isolated_ok = None if d_isolated is None else 100 * (go * ip - io * gp) <= 2 * gp * ip
        fewer_new_off = g["new_off_surface_voxels"] < f["new_off_surface_voxels"]
        comparable = forced_ok is not None and isolated_ok is not None
        results[name] = {
            "arms": reports,
            "coverage_gain_gated_vs_isolation_pp": 100.0 * cg / len(tls),
            "pollution_change_gated_vs_forced_pp": d_forced,
            "pollution_change_gated_vs_isolation_pp": d_isolated,
            "fewer_new_off_surface_voxels_than_forced": fewer_new_off,
            "coverage_margin_met": coverage_ok,
            "forced_pollution_margin_met": forced_ok,
            "isolation_pollution_margin_met": isolated_ok,
            "joint_criterion_met": ((coverage_ok and forced_ok and isolated_ok and fewer_new_off)
                                    if comparable else None),
        }
    return {"voxel_m": VOXEL_M, "tolerance_m": TOLERANCE_M, "regions": results}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--survey", required=True,
                        help="NPZ with tls_xyz and visible_keys; optional visible_keys_* regions")
    parser.add_argument("--maps", required=True, help="NPZ with pre_fault and the four ordered arms")
    args = parser.parse_args()
    with np.load(args.survey, allow_pickle=False) as survey, np.load(args.maps, allow_pickle=False) as maps:
        masks = {"common": survey["visible_keys"]}
        masks.update({key[len("visible_keys_"):]: survey[key]
                      for key in survey.files if key.startswith("visible_keys_")})
        result = score_arms(survey["tls_xyz"], masks, maps, maps["pre_fault"])
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
