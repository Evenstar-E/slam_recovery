"""Sequential Wilson confidence lower-bound and boundary continuity validator (Section 4.9)."""

from __future__ import annotations

from dataclasses import dataclass
import math
import numpy as np


@dataclass(frozen=True)
class SequentialBenefitReport:
    """Report for paired incumbent-vs-candidate sequential holdout validation."""

    num_observations: int
    num_improved_frames: int
    empirical_improved_fraction: float
    wilson_lower_bound: float
    reentry_position_jump_m: float
    reentry_rotation_jump_deg: float
    approved: bool
    reason: str


def wilson_score_lower_bound(
    successes: int,
    trials: int,
    confidence_z: float = 1.645,
) -> float:
    """
    Compute the one-sided Wilson score confidence interval lower bound (default z=1.645 for 95% one-sided):
        L = (p + z^2/(2n) - z * sqrt((p(1-p) + z^2/(4n))/n)) / (1 + z^2/n)
    """
    if trials <= 0:
        return 0.0
    n = float(trials)
    p = float(np.clip(successes / n, 0.0, 1.0))
    z2 = float(confidence_z * confidence_z)
    center = p + z2 / (2.0 * n)
    radius = float(confidence_z) * math.sqrt((p * (1.0 - p) + z2 / (4.0 * n)) / n)
    return float(max(0.0, (center - radius) / (1.0 + z2 / n)))


def evaluate_paired_sequential_benefit(
    incumbent_residuals: np.ndarray,
    candidate_residuals: np.ndarray,
    reentry_position_jump_m: float = 0.0,
    reentry_rotation_jump_deg: float = 0.0,
    min_observations: int = 20,
    min_relative_gain_per_frame: float = 0.05,
    min_wilson_lower_bound: float = 0.55,
    max_reentry_position_jump_m: float = 0.35,
    max_reentry_rotation_jump_deg: float = 5.0,
    confidence_z: float = 1.645,
) -> SequentialBenefitReport:
    """
    Verify that a candidate repair achieves statistically consistent frame-wise
    improvement on holdout observations (via Wilson score lower bound) AND
    satisfies boundary geometric continuity at re-entry (preventing RPE spikes).
    """
    inc = np.asarray(incumbent_residuals, dtype=np.float64).ravel()
    cand = np.asarray(candidate_residuals, dtype=np.float64).ravel()
    if len(inc) != len(cand):
        raise ValueError("incumbent_residuals and candidate_residuals must have equal length")

    n = len(inc)
    if n < min_observations:
        return SequentialBenefitReport(
            num_observations=n,
            num_improved_frames=0,
            empirical_improved_fraction=0.0,
            wilson_lower_bound=0.0,
            reentry_position_jump_m=float(reentry_position_jump_m),
            reentry_rotation_jump_deg=float(reentry_rotation_jump_deg),
            approved=False,
            reason="insufficient_sequential_observations",
        )

    denom = np.maximum(inc, 1e-12)
    rel_gain = (inc - cand) / denom
    improved_frames = int(np.sum(rel_gain >= min_relative_gain_per_frame))
    emp_frac = float(improved_frames / n)
    w_lb = wilson_score_lower_bound(improved_frames, n, confidence_z=confidence_z)

    if reentry_position_jump_m > max_reentry_position_jump_m:
        return SequentialBenefitReport(
            num_observations=n,
            num_improved_frames=improved_frames,
            empirical_improved_fraction=emp_frac,
            wilson_lower_bound=w_lb,
            reentry_position_jump_m=float(reentry_position_jump_m),
            reentry_rotation_jump_deg=float(reentry_rotation_jump_deg),
            approved=False,
            reason="reentry_position_discontinuity_exceeded",
        )

    if reentry_rotation_jump_deg > max_reentry_rotation_jump_deg:
        return SequentialBenefitReport(
            num_observations=n,
            num_improved_frames=improved_frames,
            empirical_improved_fraction=emp_frac,
            wilson_lower_bound=w_lb,
            reentry_position_jump_m=float(reentry_position_jump_m),
            reentry_rotation_jump_deg=float(reentry_rotation_jump_deg),
            approved=False,
            reason="reentry_rotation_discontinuity_exceeded",
        )

    if w_lb < min_wilson_lower_bound:
        return SequentialBenefitReport(
            num_observations=n,
            num_improved_frames=improved_frames,
            empirical_improved_fraction=emp_frac,
            wilson_lower_bound=w_lb,
            reentry_position_jump_m=float(reentry_position_jump_m),
            reentry_rotation_jump_deg=float(reentry_rotation_jump_deg),
            approved=False,
            reason="wilson_sequential_benefit_lower_bound_failed",
        )

    return SequentialBenefitReport(
        num_observations=n,
        num_improved_frames=improved_frames,
        empirical_improved_fraction=emp_frac,
        wilson_lower_bound=w_lb,
        reentry_position_jump_m=float(reentry_position_jump_m),
        reentry_rotation_jump_deg=float(reentry_rotation_jump_deg),
        approved=True,
        reason="passed_wilson_sequential_benefit_and_boundary_continuity",
    )
