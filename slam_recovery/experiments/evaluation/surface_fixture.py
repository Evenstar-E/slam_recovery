"""Exercise four-arm surveyed-surface scoring on known synthetic geometry."""

from dataclasses import asdict
import json

import numpy as np

from ...validation.surface_admission import SurfaceView, centers, surface_admission
from .independent_surface import score_arms


def run_fixture() -> dict:
    # Two visible surface regions with a clean baseline, a missing patch, and a ghost.
    # The evaluation mask comes from this synthetic scene, before arm maps are generated.
    grid = np.array([(x, y, 0) for x in range(20) for y in range(10)])
    common = np.array([(x, y, z) for x in range(20) for y in range(10) for z in range(9)])
    survey = centers(grid)
    old = [tuple(key) for key in grid if key[0] < 12 or key[0] >= 17]
    good = [tuple(key) for key in grid if 12 <= key[0] < 17]
    ghost = [(x, y, 6) for x in range(16, 20) for y in range(10)]

    # Gate data come from separate simulated scans in the frozen checkpoint gauge.
    # Each observes the corresponding event region and shares no samples with the survey.
    rng = np.random.default_rng(104)
    views = {}
    for event, start, slab in (("beneficial", 10, grid[grid[:, 0] < 17]),
                               ("harmful", 20, grid[grid[:, 0] >= 14])):
        views[event] = tuple(
            SurfaceView(f"{event}:{j}", f"station:{j}", start + j + 1,
                        centers(slab) + rng.uniform(-0.025, 0.025, slab.shape))
            for j in range(2)
        )

    gated = set(old)
    receipts = {}
    for event, start, patch in (("beneficial", 10, good), ("harmful", 20, ghost)):
        decision = surface_admission(
            gated, patch, views[event], candidate_end_ns=start, decision_ns=start + 2,
        )
        receipts[event] = {**asdict(decision), "coverage_gain": decision.coverage_gain}
        if decision.status == "PASSED":
            gated.update(patch)

    arms = {
        "raw": centers(old + ghost),
        "isolation": centers(old),
        "forced": centers(old + good + ghost),
        "gated": centers(sorted(gated)),
    }
    return {
        "evidence": "SYNTHETIC_ONLY",
        "admission": receipts,
        "evaluation": score_arms(survey, {"common": common}, arms, centers(old)),
    }


if __name__ == "__main__":
    print(json.dumps(run_fixture(), indent=2, allow_nan=False))
