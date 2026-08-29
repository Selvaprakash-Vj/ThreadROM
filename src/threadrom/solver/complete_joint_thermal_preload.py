"""Governed continuous-bolt thermal preload state."""

from __future__ import annotations

import math

from dataclasses import dataclass

from threadrom.solver.complete_joint_preload import (
    CompleteJointPreloadDefinition,
)


@dataclass(frozen=True)
class ThermalPreloadActuatorState:
    """Physical thermal actuator state for one preload trial.

    This state deliberately contains no solved calibration evidence.
    It is therefore valid before a CalculiX calibration trial has run.
    """

    target_force_n: float
    reference_temperature_c: float
    delta_temperature_c: float
    applied_bolt_temperature_c: float
    expansion_coefficient_per_c: float


@dataclass(frozen=True)
class ThermalPreloadState(ThermalPreloadActuatorState):
    """Accepted thermal preload state with calibration evidence."""

    calibration_force_n: float
    calibration_delta_temperature_c: float


def derive_thermal_preload_actuator_state(
    *,
    target_force_n: float,
    reference_temperature_c: float,
    delta_temperature_c: float,
    expansion_coefficient_per_c: float,
) -> ThermalPreloadActuatorState:
    """Derive a governed pre-solve thermal actuator state."""

    if (
        not math.isfinite(target_force_n)
        or target_force_n <= 0.0
    ):
        raise ValueError(
            "Thermal preload target force must be finite and positive."
        )

    if not math.isfinite(reference_temperature_c):
        raise ValueError(
            "Thermal preload reference temperature must be finite."
        )

    if (
        not math.isfinite(delta_temperature_c)
        or delta_temperature_c >= 0.0
    ):
        raise ValueError(
            "Thermal preload delta temperature must represent "
            "finite contraction."
        )

    if (
        not math.isfinite(expansion_coefficient_per_c)
        or expansion_coefficient_per_c <= 0.0
    ):
        raise ValueError(
            "Thermal expansion coefficient must be finite and positive."
        )

    applied_bolt_temperature_c = (
        reference_temperature_c
        + delta_temperature_c
    )

    if not math.isfinite(
        applied_bolt_temperature_c
    ):
        raise ValueError(
            "Applied bolt temperature must be finite."
        )

    return ThermalPreloadActuatorState(
        target_force_n=target_force_n,
        reference_temperature_c=reference_temperature_c,
        delta_temperature_c=delta_temperature_c,
        applied_bolt_temperature_c=(
            applied_bolt_temperature_c
        ),
        expansion_coefficient_per_c=(
            expansion_coefficient_per_c
        ),
    )


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
def render_thermal_expansion_keywords(
    *,
    state: ThermalPreloadActuatorState,
) -> tuple[str, ...]:
    """Render bolt-material thermal-expansion keywords."""

    return (
        (
            "*EXPANSION, "
            f"ZERO={float(state.reference_temperature_c)}"
        ),
        (
            f"{state.expansion_coefficient_per_c:.12e}"
        ),
    )


def render_initial_temperature_keywords(
    *,
    state: ThermalPreloadActuatorState,
    all_nodes_set_name: str,
) -> tuple[str, ...]:
    """Render the model-level initial temperature field."""

    if not all_nodes_set_name or not all_nodes_set_name.strip():
        raise ValueError(
            "all_nodes_set_name must be a non-empty symbolic name."
        )

    return (
        "**",
        (
            "** Initial thermal reference state: "
            f"{state.reference_temperature_c:+.12g} degC"
        ),
        "*INITIAL CONDITIONS, TYPE=TEMPERATURE",
        (
            f"{all_nodes_set_name}, "
            f"{state.reference_temperature_c:.12e}"
        ),
    )


def render_bolt_temperature_keywords(
    *,
    state: ThermalPreloadActuatorState,
    bolt_nodes_set_name: str,
) -> tuple[str, ...]:
    """Render the in-step bolt-only thermal preload field."""

    if not bolt_nodes_set_name or not bolt_nodes_set_name.strip():
        raise ValueError(
            "bolt_nodes_set_name must be a non-empty symbolic name."
        )

    return (
        "** Thermal bolt preload",
        "*TEMPERATURE",
        (
            f"{bolt_nodes_set_name}, "
            f"{state.applied_bolt_temperature_c:.12e}"
        ),
        "**",
    )


def render_thermal_preload_keywords(
    *,
    state: ThermalPreloadActuatorState,
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