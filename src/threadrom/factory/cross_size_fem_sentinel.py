"""Governed cross-size FEM certification sentinels.

These cases exist only to establish cross-size FEM transfer evidence.
They are not members of the frozen M10 Production DOE and do not
pre-authorize FEM capability for M8 or M12.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from threadrom.case.contract import ThreadROMCase
from threadrom.case.reference_cases import phase2_certification_case
from threadrom.case.standards import resolve_metric_thread_standard
from threadrom.engineering.metric_thread import (
    calculate_metric_thread_basic_dimensions,
)


_M10_REFERENCE_DESIGNATION = "M10x1.5"
_M10_REFERENCE_PRELOAD_N = 20_000.0


@dataclass(frozen=True, slots=True)
class CrossSizeFemSentinelDefinition:
    """Governed dimensional definition of one certification sentinel."""

    sentinel_id: str
    thread_designation: str
    bolt_length_mm: float
    member_thickness_mm: float
    member_outer_diameter_mm: float
    clearance_hole_diameter_mm: float


@dataclass(frozen=True, slots=True)
class CrossSizeFemSentinel:
    """Resolved product-level case plus normalized preload provenance."""

    definition: CrossSizeFemSentinelDefinition
    case: ThreadROMCase
    tensile_stress_area_mm2: float
    reference_nominal_stress_mpa: float
    target_preload_n: float


CROSS_SIZE_FEM_SENTINEL_DEFINITIONS = (
    CrossSizeFemSentinelDefinition(
        sentinel_id="TRM-XFEM-M8-001",
        thread_designation="M8x1.25",
        bolt_length_mm=30.0,
        member_thickness_mm=8.0,
        member_outer_diameter_mm=24.0,
        clearance_hole_diameter_mm=8.8,
    ),
    CrossSizeFemSentinelDefinition(
        sentinel_id="TRM-XFEM-M12-001",
        thread_designation="M12x1.75",
        bolt_length_mm=40.0,
        member_thickness_mm=12.0,
        member_outer_diameter_mm=36.0,
        clearance_hole_diameter_mm=13.2,
    ),
)


def _tensile_stress_area_mm2(
    designation: str,
) -> float:
    standard = resolve_metric_thread_standard(
        designation
    )

    dimensions = (
        calculate_metric_thread_basic_dimensions(
            standard.nominal_diameter_mm,
            standard.pitch_mm,
        )
    )

    return dimensions.tensile_stress_area_mm2


def reference_nominal_tensile_stress_mpa() -> float:
    """Return the M10 20-kN sentinel reference F/As stress."""

    reference_area = _tensile_stress_area_mm2(
        _M10_REFERENCE_DESIGNATION
    )

    return (
        _M10_REFERENCE_PRELOAD_N
        / reference_area
    )


def build_cross_size_fem_sentinel(
    definition: CrossSizeFemSentinelDefinition,
) -> CrossSizeFemSentinel:
    """Build one certification-only cross-size FEM sentinel case."""

    baseline = phase2_certification_case()
    upper, lower = baseline.members.layers

    target_area = _tensile_stress_area_mm2(
        definition.thread_designation
    )

    reference_stress = (
        reference_nominal_tensile_stress_mpa()
    )

    target_preload = (
        reference_stress
        * target_area
    )

    case = replace(
        baseline,
        fastener=replace(
            baseline.fastener,
            thread_designation=(
                definition.thread_designation
            ),
            bolt_length_mm=(
                definition.bolt_length_mm
            ),
        ),
        members=replace(
            baseline.members,
            layers=(
                replace(
                    upper,
                    thickness_mm=(
                        definition.member_thickness_mm
                    ),
                    outer_diameter_mm=(
                        definition.member_outer_diameter_mm
                    ),
                    clearance_hole_diameter_mm=(
                        definition.clearance_hole_diameter_mm
                    ),
                ),
                replace(
                    lower,
                    thickness_mm=(
                        definition.member_thickness_mm
                    ),
                    outer_diameter_mm=(
                        definition.member_outer_diameter_mm
                    ),
                    clearance_hole_diameter_mm=(
                        definition.clearance_hole_diameter_mm
                    ),
                ),
            ),
        ),
        loading=replace(
            baseline.loading,
            target_preload_n=target_preload,
        ),
        metadata=replace(
            baseline.metadata,
            notes=(
                "Cross-size FEM certification sentinel "
                f"{definition.sentinel_id}; "
                "certification-only, not Production DOE."
            ),
        ),
    )

    return CrossSizeFemSentinel(
        definition=definition,
        case=case,
        tensile_stress_area_mm2=target_area,
        reference_nominal_stress_mpa=(
            reference_stress
        ),
        target_preload_n=target_preload,
    )


def build_phase3_cross_size_fem_sentinels() -> tuple[
    CrossSizeFemSentinel,
    ...,
]:
    """Return the frozen M8/M12 cross-size certification sentinels."""

    return tuple(
        build_cross_size_fem_sentinel(
            definition
        )
        for definition
        in CROSS_SIZE_FEM_SENTINEL_DEFINITIONS
    )
