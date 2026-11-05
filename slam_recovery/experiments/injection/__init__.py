"""Fault injection subpackage."""

from .injectors import (
    LiDARInjectionParams,
    inject_lidar_attenuation_and_dropout,
    inject_plastic_bag_near_field_occlusion,
    inject_timestamp_offset,
    inject_visual_exposure_drop,
)

__all__ = [
    "LiDARInjectionParams",
    "inject_lidar_attenuation_and_dropout",
    "inject_plastic_bag_near_field_occlusion",
    "inject_timestamp_offset",
    "inject_visual_exposure_drop",
]
