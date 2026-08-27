"""Governed continuous-bolt thermal preload state."""

from __future__ import annotations

from dataclasses import dataclass

from threadrom.solver.complete_joint_preload import (
    CompleteJointPreloadDefinition,
)


@dataclass(frozen=True)
class ThermalPreloadState:
    """Derived thermal actuator state for one preload target."""

    target_force_n: float
    reference_temperature_c: float
    delta_temperature_c: float
    applied_bolt_temperature_c: float
    expansion_coefficient_per_c: float
    calibration_force_n: float
    calibration_delta_temperature_c: float


def derive_thermal_preload_state(
    preload: CompleteJointPreloadDefinition,
) -> ThermalPreloadState:
    """Derive the thermal preload actuator entirely from governance."""

    thermal = preload.thermal

    if not thermal.enabled:
        raise ValueError(
            "Thermal preload is disabled."
        )

    applied_bolt_temperature_c = (
        thermal.reference_temperature_c
        + thermal.equivalent_delta_temperature_c
    )

    return ThermalPreloadState(
        target_force_n=preload.target_force_n,
        reference_temperature_c=(
            thermal.reference_temperature_c
        ),
        delta_temperature_c=(
            thermal.equivalent_delta_temperature_c
        ),
        applied_bolt_temperature_c=(
            applied_bolt_temperature_c
        ),
        expansion_coefficient_per_c=(
            thermal.expansion_coefficient_per_c
        ),
        calibration_force_n=(
            thermal.calibration_measured_clamp_force_n
        ),
        calibration_delta_temperature_c=(
            thermal.calibration_delta_temperature_c
        ),
    )
def render_thermal_preload_keywords(
    *,
    state: ThermalPreloadState,
    all_nodes_set_name: str,
    bolt_nodes_set_name: str,
    bolt_material_name: str,
) -> str:
    """Render governed CalculiX thermal-preload keyword fragments.

    The function operates only on symbolic set/material names.
    Node IDs and element IDs are deliberately not accepted.
    """

    for name, value in (
        ("all_nodes_set_name", all_nodes_set_name),
        ("bolt_nodes_set_name", bolt_nodes_set_name),
        ("bolt_material_name", bolt_material_name),
    ):
        if not value or not value.strip():
            raise ValueError(
                f"{name} must be a non-empty symbolic name."
            )

    return "\n".join(
        [
            (
                f"** THERMAL PRELOAD MATERIAL: "
                f"{bolt_material_name}"
            ),
            (
                f"*EXPANSION, "
                f"ZERO={state.reference_temperature_c:.12g}"
            ),
            (
                f"{state.expansion_coefficient_per_c:.12e}"
            ),
            "",
            "*INITIAL CONDITIONS, TYPE=TEMPERATURE",
            (
                f"{all_nodes_set_name}, "
                f"{state.reference_temperature_c:.12g}"
            ),
            "",
            "*TEMPERATURE",
            (
                f"{bolt_nodes_set_name}, "
                f"{state.applied_bolt_temperature_c:.12g}"
            ),
            "",
        ]
    )