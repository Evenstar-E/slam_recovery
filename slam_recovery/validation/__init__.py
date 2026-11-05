"""Validation subpackage: True 6-DoF FIM, disjoint holdout NIS, Wilson sequential benefit, and boundary continuity."""

from .fim_and_holdout import (
    compute_6dof_point_to_plane_fim,
    compute_disjoint_holdout_point_to_plane_nis,
)
from .wilson_validator import (
    SequentialBenefitReport,
    evaluate_paired_sequential_benefit,
    wilson_score_lower_bound,
)

__all__ = [
    "compute_6dof_point_to_plane_fim",
    "compute_disjoint_holdout_point_to_plane_nis",
    "SequentialBenefitReport",
    "evaluate_paired_sequential_benefit",
    "wilson_score_lower_bound",
]
