"""Central numerical quality policy for parametric CAD geometry."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast


@dataclass(frozen=True)
class GeometryQualityPolicy:
    """Controlled numerical tolerances for CAD construction and validation."""

    policy_id: str
    boolean_tolerance_mm: float
    thread_boolean_overlap_mm: float
    fusion_bridge_half_height_mm: float
    fusion_bridge_radius_fraction: float
    cad_envelope_tolerance_mm: float
    step_bounds_tolerance_mm: float
    step_volume_relative_tolerance: float


def _section(
    data: Mapping[str, object],
    key: str,
) -> Mapping[str, object]:
    """Return a required TOML section."""

    value = data.get(key)

    if not isinstance(value, dict):
        raise TypeError(f"Missing or invalid configuration section: {key}")

    return cast(Mapping[str, object], value)


def _string(
    data: Mapping[str, object],
    key: str,
) -> str:
    """Return a required non-empty string."""

    value = data.get(key)

    if not isinstance(value, str) or not value.strip():
        raise TypeError(f"Missing or invalid string value: {key}")

    return value


def _number(
    data: Mapping[str, object],
    key: str,
) -> float:
    """Return a required numerical value."""

    value = data.get(key)

    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"Missing or invalid numerical value: {key}")

    return float(value)


def load_geometry_quality_policy(
    config_path: Path,
) -> GeometryQualityPolicy:
    """Load and validate the central geometry quality policy."""

    with config_path.open("rb") as config_file:
        data: dict[str, object] = tomllib.load(config_file)

    identity = _section(data, "identity")
    boolean_operations = _section(
        data,
        "boolean_operations",
    )
    verification = _section(
        data,
        "verification",
    )

    policy = GeometryQualityPolicy(
        policy_id=_string(identity, "policy_id"),
        boolean_tolerance_mm=_number(
            boolean_operations,
            "tolerance_mm",
        ),
        thread_boolean_overlap_mm=_number(
            boolean_operations,
            "thread_boolean_overlap_mm",
        ),
        fusion_bridge_half_height_mm=_number(
            boolean_operations,
            "fusion_bridge_half_height_mm",
        ),
        fusion_bridge_radius_fraction=_number(
            boolean_operations,
            "fusion_bridge_radius_fraction",
        ),
        cad_envelope_tolerance_mm=_number(
            verification,
            "cad_envelope_tolerance_mm",
        ),
        step_bounds_tolerance_mm=_number(
            verification,
            "step_bounds_tolerance_mm",
        ),
        step_volume_relative_tolerance=_number(
            verification,
            "step_volume_relative_tolerance",
        ),
    )

    positive_values = (
        policy.boolean_tolerance_mm,
        policy.thread_boolean_overlap_mm,
        policy.fusion_bridge_half_height_mm,
        policy.cad_envelope_tolerance_mm,
        policy.step_bounds_tolerance_mm,
        policy.step_volume_relative_tolerance,
    )

    if any(value <= 0.0 for value in positive_values):
        raise ValueError("All geometry quality tolerances must be positive.")

    if not 0.0 < policy.fusion_bridge_radius_fraction < 1.0:
        raise ValueError("Fusion bridge radius fraction must be between zero and one.")

    return policy
