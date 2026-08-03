"""Piecewise axial behaviour of one preloaded bolted joint."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from threadrom.engineering.analytical_bolt_mechanics import (
    calculate_analytical_bolt_mechanics,
)
from threadrom.engineering.analytical_joint_input import (
    AnalyticalJointInput,
    ExternalLoadMethod,
)
from threadrom.engineering.analytical_member_mechanics import (
    calculate_analytical_member_mechanics,
)


class JointContactRegime(StrEnum):
    """Axial contact state of the clamped interface."""

    CLAMPED = "clamped"
    SEPARATED = "separated"


@dataclass(frozen=True)
class AnalyticalJointState:
    """Resolved axial state at one preload and external load."""

    method: str
    joint_id: str
    regime: JointContactRegime
    preload_n: float
    external_axial_load_n: float
    bolt_stiffness_n_per_mm: float
    member_stiffness_n_per_mm: float
    basic_load_fraction: float
    load_introduction_factor: float
    effective_load_fraction: float
    separation_load_n: float
    separation_margin_n: float
    bolt_force_n: float
    member_compression_force_n: float
    bolt_external_increment_n: float
    member_unloading_n: float
    bolt_additional_elongation_mm: float
    member_compression_recovery_mm: float
    bolt_total_elongation_mm: float
    member_shortening_mm: float
    joint_opening_mm: float
    external_load_equilibrium_error_n: float


def calculate_analytical_joint_state(
    joint: AnalyticalJointInput,
    *,
    external_axial_load_n: float | None = None,
    preload_n: float | None = None,
) -> AnalyticalJointState:
    """Calculate one piecewise linear-elastic joint state."""

    resolved_preload_n = joint.loading.preload_n if preload_n is None else preload_n

    resolved_external_load_n = (
        joint.loading.external_axial_load_n
        if external_axial_load_n is None
        else external_axial_load_n
    )

    _validate_state_loads(
        preload_n=resolved_preload_n,
        external_axial_load_n=resolved_external_load_n,
    )

    bolt = calculate_analytical_bolt_mechanics(joint)

    member = calculate_analytical_member_mechanics(joint)

    bolt_stiffness_n_per_mm = bolt.axial_stiffness_n_per_mm

    member_stiffness_n_per_mm = member.axial_stiffness_n_per_mm

    basic_load_fraction = bolt_stiffness_n_per_mm / (
        bolt_stiffness_n_per_mm + member_stiffness_n_per_mm
    )

    effective_load_fraction = _effective_external_load_fraction(
        joint=joint,
        basic_load_fraction=basic_load_fraction,
    )

    member_unloading_fraction = 1.0 - effective_load_fraction

    if member_unloading_fraction <= 0.0:
        raise ValueError("Member-unloading fraction must be positive.")

    separation_load_n = resolved_preload_n / member_unloading_fraction

    if resolved_external_load_n <= separation_load_n:
        regime = JointContactRegime.CLAMPED

        bolt_force_n = resolved_preload_n + effective_load_fraction * resolved_external_load_n

        member_compression_force_n = max(
            0.0,
            resolved_preload_n - member_unloading_fraction * resolved_external_load_n,
        )

        joint_opening_mm = 0.0
    else:
        regime = JointContactRegime.SEPARATED

        bolt_force_n = resolved_external_load_n
        member_compression_force_n = 0.0

        joint_opening_mm = (resolved_external_load_n - separation_load_n) / bolt_stiffness_n_per_mm

    bolt_external_increment_n = bolt_force_n - resolved_preload_n

    member_unloading_n = resolved_preload_n - member_compression_force_n

    bolt_additional_elongation_mm = bolt_external_increment_n / bolt_stiffness_n_per_mm

    member_compression_recovery_mm = member_unloading_n / member_stiffness_n_per_mm

    external_load_equilibrium_error_n = (
        bolt_force_n - member_compression_force_n - resolved_external_load_n
    )

    return AnalyticalJointState(
        method=joint.methods.external_load.value,
        joint_id=joint.joint_id,
        regime=regime,
        preload_n=resolved_preload_n,
        external_axial_load_n=(resolved_external_load_n),
        bolt_stiffness_n_per_mm=(bolt_stiffness_n_per_mm),
        member_stiffness_n_per_mm=(member_stiffness_n_per_mm),
        basic_load_fraction=basic_load_fraction,
        load_introduction_factor=(joint.methods.load_introduction_factor),
        effective_load_fraction=(effective_load_fraction),
        separation_load_n=separation_load_n,
        separation_margin_n=(separation_load_n - resolved_external_load_n),
        bolt_force_n=bolt_force_n,
        member_compression_force_n=(member_compression_force_n),
        bolt_external_increment_n=(bolt_external_increment_n),
        member_unloading_n=member_unloading_n,
        bolt_additional_elongation_mm=(bolt_additional_elongation_mm),
        member_compression_recovery_mm=(member_compression_recovery_mm),
        bolt_total_elongation_mm=(bolt_force_n / bolt_stiffness_n_per_mm),
        member_shortening_mm=(member_compression_force_n / member_stiffness_n_per_mm),
        joint_opening_mm=joint_opening_mm,
        external_load_equilibrium_error_n=(external_load_equilibrium_error_n),
    )


def _effective_external_load_fraction(
    *,
    joint: AnalyticalJointInput,
    basic_load_fraction: float,
) -> float:
    """Return the selected fraction of external load added to the bolt."""

    if joint.methods.external_load is ExternalLoadMethod.BASIC_SPRING_RATIO:
        return basic_load_fraction

    if joint.methods.external_load is ExternalLoadMethod.LOAD_INTRODUCTION_FACTOR:
        return joint.methods.load_introduction_factor * basic_load_fraction

    raise NotImplementedError(
        f"Unsupported external-load method: {joint.methods.external_load.value}"
    )


def _validate_state_loads(
    *,
    preload_n: float,
    external_axial_load_n: float,
) -> None:
    """Validate one requested axial joint state."""

    if not math.isfinite(preload_n):
        raise ValueError("Preload must be finite.")

    if not math.isfinite(external_axial_load_n):
        raise ValueError("External axial load must be finite.")

    if preload_n < 0.0:
        raise ValueError("Preload must not be negative.")

    if external_axial_load_n < 0.0:
        raise ValueError("External separating axial load must not be negative.")
