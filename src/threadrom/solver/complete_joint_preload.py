"""Governed complete-joint preload definitions.

This module contains configuration only. Mesh-dependent node IDs,
element IDs, areas, preload regions, and contact identities must be
derived elsewhere from the governed model.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import tomllib


@dataclass(frozen=True)
class ThermalPreloadDefinition:
    """Equivalent thermal-contraction preload settings."""

    enabled: bool
    reference_temperature_c: float
    expansion_coefficient_per_c: float
    equivalent_delta_temperature_c: float
    calibration_method: str
    calibration_delta_temperature_c: float
    calibration_measured_clamp_force_n: float
    calibration_run_id: str


@dataclass(frozen=True)
class InitialStressPreloadDefinition:
    """Mesh-derived initial-stress preload settings."""

    enabled: bool
    selection_mode: str
    stress_magnitude_mode: str
    stress_direction_mode: str
    band_start_fraction: float
    band_end_fraction: float


@dataclass(frozen=True)
class CompleteJointPreloadModelDefinition:
    """Governed semantic model roles used by preload workflows."""

    bolt_component: str


@dataclass(frozen=True)
class PreloadValidationDefinition:
    """Physical acceptance requirements for preload cases."""

    require_under_head_cfn: bool
    require_nut_bearing_cfn: bool
    require_member_interface_cfn: bool
    require_thread_cfn: bool
    require_bolt_net_tension: bool
    require_member_net_compression: bool
    require_thread_flank_validation: bool
    require_global_equilibrium: bool
    forbid_native_pretension_section: bool
    forbid_manual_node_ids: bool
    forbid_manual_element_ids: bool
    forbid_contact_adjacent_initial_stress_elements: bool


@dataclass(frozen=True)
class CompleteJointPreloadDefinition:
    """Shared governed preload contract for Run A and Run B."""

    schema_version: int
    preload_id: str
    target_force_n: float
    target_relative_tolerance: float
    interface_spread_relative_tolerance: float
    model: CompleteJointPreloadModelDefinition
    thermal: ThermalPreloadDefinition
    initial_stress: InitialStressPreloadDefinition
    validation: PreloadValidationDefinition


def _require_table(
    data: dict[str, object],
    name: str,
) -> dict[str, object]:
    value = data.get(name)

    if not isinstance(value, dict):
        raise ValueError(
            f"Required TOML table [{name}] is missing."
        )

    return value


def _require_bool(
    table: dict[str, object],
    name: str,
) -> bool:
    value = table.get(name)

    if not isinstance(value, bool):
        raise ValueError(
            f"{name} must be a boolean."
        )

    return value


def _require_string(
    table: dict[str, object],
    name: str,
) -> str:
    value = table.get(name)

    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"{name} must be a non-empty string."
        )

    return value


def _require_float(
    table: dict[str, object],
    name: str,
) -> float:
    value = table.get(name)

    if isinstance(value, bool) or not isinstance(
        value,
        (int, float),
    ):
        raise ValueError(
            f"{name} must be numeric."
        )

    result = float(value)

    if not math.isfinite(result):
        raise ValueError(
            f"{name} must be finite."
        )

    return result


def load_complete_joint_preload_definition(
    path: Path,
) -> CompleteJointPreloadDefinition:
    """Load and validate the governed preload configuration."""

    with path.open("rb") as handle:
        data = tomllib.load(handle)

    schema_version = data.get("schema_version")

    if schema_version != 1:
        raise ValueError(
            "Complete-joint preload schema_version must be 1."
        )

    preload_id = data.get("preload_id")

    if not isinstance(preload_id, str) or not preload_id.strip():
        raise ValueError(
            "preload_id must be a non-empty string."
        )

    preload = _require_table(
        data,
        "preload",
    )
    model = _require_table(
        data,
        "model",
    )
    thermal = _require_table(
        data,
        "thermal",
    )
    initial_stress = _require_table(
        data,
        "initial_stress",
    )
    validation = _require_table(
        data,
        "validation",
    )

    target_force_n = _require_float(
        preload,
        "target_force_n",
    )
    target_relative_tolerance = _require_float(
        preload,
        "target_relative_tolerance",
    )
    interface_spread_relative_tolerance = _require_float(
        preload,
        "interface_spread_relative_tolerance",
    )

    if target_force_n <= 0.0:
        raise ValueError(
            "target_force_n must be strictly positive."
        )

    if not 0.0 < target_relative_tolerance < 1.0:
        raise ValueError(
            "target_relative_tolerance must lie between 0 and 1."
        )

    if not 0.0 < interface_spread_relative_tolerance < 1.0:
        raise ValueError(
            "interface_spread_relative_tolerance "
            "must lie between 0 and 1."
        )

    model_definition = CompleteJointPreloadModelDefinition(
        bolt_component=_require_string(
            model,
            "bolt_component",
        ),
    )

    thermal_definition = ThermalPreloadDefinition(
        enabled=_require_bool(
            thermal,
            "enabled",
        ),
        reference_temperature_c=_require_float(
            thermal,
            "reference_temperature_c",
        ),
        expansion_coefficient_per_c=_require_float(
            thermal,
            "expansion_coefficient_per_c",
        ),
        equivalent_delta_temperature_c=_require_float(
            thermal,
            "equivalent_delta_temperature_c",
        ),
        calibration_method=_require_string(
            thermal,
            "calibration_method",
        ),
        calibration_delta_temperature_c=_require_float(
            thermal,
            "calibration_delta_temperature_c",
        ),
        calibration_measured_clamp_force_n=_require_float(
            thermal,
            "calibration_measured_clamp_force_n",
        ),
        calibration_run_id=_require_string(
            thermal,
            "calibration_run_id",
        ),
    )

    if thermal_definition.expansion_coefficient_per_c <= 0.0:
        raise ValueError(
            "Thermal expansion coefficient must be positive."
        )

    if thermal_definition.equivalent_delta_temperature_c >= 0.0:
        raise ValueError(
            "Equivalent preload temperature change "
            "must represent contraction."
        )

    if thermal_definition.calibration_measured_clamp_force_n <= 0.0:
        raise ValueError(
            "Calibration clamp force must be positive."
        )

    initial_stress_definition = InitialStressPreloadDefinition(
        enabled=_require_bool(
            initial_stress,
            "enabled",
        ),
        selection_mode=_require_string(
            initial_stress,
            "selection_mode",
        ),
        stress_magnitude_mode=_require_string(
            initial_stress,
            "stress_magnitude_mode",
        ),
        stress_direction_mode=_require_string(
            initial_stress,
            "stress_direction_mode",
        ),
        band_start_fraction=_require_float(
            initial_stress,
            "band_start_fraction",
        ),
        band_end_fraction=_require_float(
            initial_stress,
            "band_end_fraction",
        ),
    )

    if (
        initial_stress_definition.selection_mode
        != "automatic_free_thread_span_band"
    ):
        raise ValueError(
            "Initial-stress selection must be "
            "automatic_free_thread_span_band."
        )

    if not (
        0.0
        <= initial_stress_definition.band_start_fraction
        < initial_stress_definition.band_end_fraction
        <= 1.0
    ):
        raise ValueError(
            "Initial-stress band fractions must satisfy "
            "0 <= start < end <= 1."
        )

    if (
        initial_stress_definition.stress_magnitude_mode
        != "target_force_over_meshed_area"
    ):
        raise ValueError(
            "Initial stress magnitude must be derived "
            "from target force and meshed area."
        )

    if (
        initial_stress_definition.stress_direction_mode
        != "derived_bolt_axis"
    ):
        raise ValueError(
            "Initial stress direction must be derived "
            "from the bolt axis."
        )

    validation_definition = PreloadValidationDefinition(
        require_under_head_cfn=_require_bool(
            validation,
            "require_under_head_cfn",
        ),
        require_nut_bearing_cfn=_require_bool(
            validation,
            "require_nut_bearing_cfn",
        ),
        require_member_interface_cfn=_require_bool(
            validation,
            "require_member_interface_cfn",
        ),
        require_thread_cfn=_require_bool(
            validation,
            "require_thread_cfn",
        ),
        require_bolt_net_tension=_require_bool(
            validation,
            "require_bolt_net_tension",
        ),
        require_member_net_compression=_require_bool(
            validation,
            "require_member_net_compression",
        ),
        require_thread_flank_validation=_require_bool(
            validation,
            "require_thread_flank_validation",
        ),
        require_global_equilibrium=_require_bool(
            validation,
            "require_global_equilibrium",
        ),
        forbid_native_pretension_section=_require_bool(
            validation,
            "forbid_native_pretension_section",
        ),
        forbid_manual_node_ids=_require_bool(
            validation,
            "forbid_manual_node_ids",
        ),
        forbid_manual_element_ids=_require_bool(
            validation,
            "forbid_manual_element_ids",
        ),
        forbid_contact_adjacent_initial_stress_elements=(
            _require_bool(
                validation,
                "forbid_contact_adjacent_initial_stress_elements",
            )
        ),
    )

    return CompleteJointPreloadDefinition(
        schema_version=1,
        preload_id=preload_id,
        target_force_n=target_force_n,
        target_relative_tolerance=target_relative_tolerance,
        interface_spread_relative_tolerance=(
            interface_spread_relative_tolerance
        ),
        model=model_definition,
        thermal=thermal_definition,
        initial_stress=initial_stress_definition,
        validation=validation_definition,
    )