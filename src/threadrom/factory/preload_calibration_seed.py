"""Physics-derived initial thermal-preload calibration seed."""

from __future__ import annotations

import math
from dataclasses import dataclass

from threadrom.case.resolved_case import ResolvedCase
from threadrom.engineering.analytical_bolt_mechanics import (
    calculate_analytical_bolt_mechanics,
)
from threadrom.engineering.analytical_member_mechanics import (
    calculate_analytical_member_mechanics,
)
from threadrom.engineering.analytical_thread_distribution import (
    calculate_thread_load_distribution,
)
from threadrom.factory.analytical_adapter import (
    build_analytical_joint_input,
)



@dataclass(frozen=True, slots=True)
class ThermalPreloadCompatibilityMechanics:
    """Physics basis for the V2 thermal-preload compatibility seed.

    This model deliberately separates:

    1. the physical thermal actuation span,
    2. free-span bolt mechanical compliance, and
    3. engaged-thread load-transfer compliance.

    It does not include the generic analytical head/nut participation
    lengths used by the general bolt-stiffness model.
    """

    method: str

    thermal_actuation_length_mm: float

    free_span_bolt_length_mm: float
    free_span_bolt_compliance_mm_per_n: float

    thread_transfer_equivalent_length_mm: float
    thread_transfer_bolt_compliance_mm_per_n: float

    bolt_compliance_mm_per_n: float

    def __post_init__(self) -> None:
        positive_values = (
            self.thermal_actuation_length_mm,
            self.free_span_bolt_length_mm,
            self.free_span_bolt_compliance_mm_per_n,
            self.thread_transfer_equivalent_length_mm,
            self.thread_transfer_bolt_compliance_mm_per_n,
            self.bolt_compliance_mm_per_n,
        )

        if any(
            not math.isfinite(value)
            or value <= 0.0
            for value in positive_values
        ):
            raise ValueError(
                "V2 thermal-preload compatibility mechanics "
                "must be finite and positive."
            )


def derive_thermal_preload_compatibility_mechanics(
    resolved: ResolvedCase,
) -> ThermalPreloadCompatibilityMechanics:
    """Derive the V2 analytical thermal-preload load path.

    The current governed FEM topology defines the thermal free span
    from the bolt under-head bearing plane to the thread-engagement
    entry at the nut bearing plane.  For the current assembly contract
    this is the physical grip length.

    Bolt mechanical compliance is resolved as:

        C_bolt =
            C_free_span
            + C_engaged_thread_transfer

    The engaged-thread contribution uses the existing governed
    discrete thread-load distribution.  For point load transfers at
    axial centroids z_i with load shares s_i, the equivalent bolt
    transfer length is

        L_transfer = sum(s_i * z_i)

    which is the discrete equivalent of integrating the remaining
    bolt-force fraction through the engagement.
    """

    joint = build_analytical_joint_input(
        resolved
    )

    bolt = calculate_analytical_bolt_mechanics(
        joint
    )

    if bolt.method != "segmented":
        raise NotImplementedError(
            "V2 thermal-preload compatibility currently requires "
            "the governed segmented bolt-compliance model."
        )

    physical_segment_count = len(
        joint.bolt.axial_segments
    )

    if physical_segment_count <= 0:
        raise ValueError(
            "V2 thermal-preload compatibility requires at least "
            "one physical bolt axial segment."
        )

    if len(bolt.segments) < physical_segment_count:
        raise RuntimeError(
            "Analytical bolt mechanics lost physical segment parity."
        )

    physical_segments = bolt.segments[
        :physical_segment_count
    ]

    free_span_bolt_length_mm = math.fsum(
        segment.length_mm
        for segment in physical_segments
    )

    free_span_bolt_compliance_mm_per_n = math.fsum(
        segment.compliance_mm_per_n
        for segment in physical_segments
    )

    thermal_actuation_length_mm = (
        resolved.assembly.total_grip_length_mm
    )

    if not math.isclose(
        free_span_bolt_length_mm,
        thermal_actuation_length_mm,
        rel_tol=1.0e-12,
        abs_tol=1.0e-12,
    ):
        raise RuntimeError(
            "V2 thermal-preload compatibility requires the "
            "physical bolt free-span segments to reproduce the "
            "under-head-to-engagement-entry actuation span."
        )

    target_force_n = (
        resolved.source_case.loading.target_preload_n
    )

    distribution = calculate_thread_load_distribution(
        joint,
        total_transferred_load_n=target_force_n,
    )

    load_share_sum = math.fsum(
        turn.load_share
        for turn in distribution.turn_loads
    )

    if not math.isclose(
        load_share_sum,
        1.0,
        rel_tol=1.0e-10,
        abs_tol=1.0e-12,
    ):
        raise RuntimeError(
            "Thread-load distribution does not conserve the "
            "transferred bolt load."
        )

    thread_transfer_equivalent_length_mm = (
        math.fsum(
            turn.load_share
            * turn.axial_centroid_mm
            for turn in distribution.turn_loads
        )
    )

    engagement_length_mm = (
        distribution.engagement
        .total_engagement_length_mm
    )

    if not (
        0.0
        < thread_transfer_equivalent_length_mm
        <= engagement_length_mm
    ):
        raise RuntimeError(
            "Equivalent thread-transfer length lies outside "
            "the physical engagement."
        )

    bolt_material = joint.material_by_id(
        joint.bolt.material_id
    )

    thread_transfer_area_mm2 = (
        distribution.stiffness.bolt_axial_area_mm2
    )

    if thread_transfer_area_mm2 <= 0.0:
        raise RuntimeError(
            "Thread-transfer bolt axial area must be positive."
        )

    thread_transfer_bolt_compliance_mm_per_n = (
        thread_transfer_equivalent_length_mm
        / (
            bolt_material.youngs_modulus_mpa
            * thread_transfer_area_mm2
        )
    )

    bolt_compliance_mm_per_n = (
        free_span_bolt_compliance_mm_per_n
        + thread_transfer_bolt_compliance_mm_per_n
    )

    return ThermalPreloadCompatibilityMechanics(
        method=(
            "free_span_plus_distributed_thread_transfer_v2"
        ),
        thermal_actuation_length_mm=(
            thermal_actuation_length_mm
        ),
        free_span_bolt_length_mm=(
            free_span_bolt_length_mm
        ),
        free_span_bolt_compliance_mm_per_n=(
            free_span_bolt_compliance_mm_per_n
        ),
        thread_transfer_equivalent_length_mm=(
            thread_transfer_equivalent_length_mm
        ),
        thread_transfer_bolt_compliance_mm_per_n=(
            thread_transfer_bolt_compliance_mm_per_n
        ),
        bolt_compliance_mm_per_n=(
            bolt_compliance_mm_per_n
        ),
    )

@dataclass(frozen=True, slots=True)
class ThermalPreloadCalibrationSeed:
    """Deterministic analytical first trial for FEM preload calibration."""

    target_force_n: float
    bolt_compliance_mm_per_n: float
    member_compliance_mm_per_n: float
    total_compliance_mm_per_n: float
    effective_bolt_length_mm: float
    expansion_coefficient_per_c: float
    predicted_delta_temperature_c: float

    def __post_init__(self) -> None:
        positive_values = (
            self.target_force_n,
            self.bolt_compliance_mm_per_n,
            self.member_compliance_mm_per_n,
            self.total_compliance_mm_per_n,
            self.effective_bolt_length_mm,
            self.expansion_coefficient_per_c,
        )

        if any(
            not math.isfinite(value)
            or value <= 0.0
            for value in positive_values
        ):
            raise ValueError(
                "Thermal preload calibration seed inputs "
                "must be finite and positive."
            )

        if (
            not math.isfinite(
                self.predicted_delta_temperature_c
            )
            or self.predicted_delta_temperature_c >= 0.0
        ):
            raise ValueError(
                "Predicted thermal preload seed must represent "
                "finite contraction."
            )


def derive_analytical_thermal_preload_seed(
    resolved: ResolvedCase,
) -> ThermalPreloadCalibrationSeed:
    """Derive the first FEM preload trial from analytical compatibility.

    Compatibility for the clamped linear-elastic approximation is

        alpha * abs(deltaT) * L_eff
            = F_target * (C_bolt + C_member)

    The FEM calibration campaign is responsible for correcting this
    analytical first estimate using solved physical clamp-force data.
    """

    joint = build_analytical_joint_input(
        resolved
    )

    bolt = calculate_analytical_bolt_mechanics(
        joint
    )

    member = calculate_analytical_member_mechanics(
        joint
    )

    coefficient = (
        resolved.bolt_material.thermal_expansion_per_c
    )

    if coefficient is None:
        raise ValueError(
            "Analytical thermal preload seeding requires a governed "
            "bolt thermal expansion coefficient."
        )

    total_compliance_mm_per_n = (
        bolt.total_compliance_mm_per_n
        + member.total_compliance_mm_per_n
    )

    predicted_delta_temperature_c = -(
        resolved.source_case.loading.target_preload_n
        * total_compliance_mm_per_n
        / (
            coefficient
            * bolt.effective_length_mm
        )
    )

    return ThermalPreloadCalibrationSeed(
        target_force_n=(
            resolved.source_case.loading.target_preload_n
        ),
        bolt_compliance_mm_per_n=(
            bolt.total_compliance_mm_per_n
        ),
        member_compliance_mm_per_n=(
            member.total_compliance_mm_per_n
        ),
        total_compliance_mm_per_n=(
            total_compliance_mm_per_n
        ),
        effective_bolt_length_mm=(
            bolt.effective_length_mm
        ),
        expansion_coefficient_per_c=coefficient,
        predicted_delta_temperature_c=(
            predicted_delta_temperature_c
        ),
    )


@dataclass(frozen=True, slots=True)
class ThermalPreloadCalibrationSeedV2:
    """Physics-separated V2 first trial for FEM preload calibration."""

    method: str
    target_force_n: float

    bolt_compliance_mm_per_n: float
    member_compliance_mm_per_n: float
    total_compliance_mm_per_n: float

    thermal_actuation_length_mm: float
    expansion_coefficient_per_c: float

    predicted_delta_temperature_c: float

    def __post_init__(self) -> None:
        positive_values = (
            self.target_force_n,
            self.bolt_compliance_mm_per_n,
            self.member_compliance_mm_per_n,
            self.total_compliance_mm_per_n,
            self.thermal_actuation_length_mm,
            self.expansion_coefficient_per_c,
        )

        if any(
            not math.isfinite(value)
            or value <= 0.0
            for value in positive_values
        ):
            raise ValueError(
                "V2 thermal preload seed inputs must be "
                "finite and positive."
            )

        if (
            not math.isfinite(
                self.predicted_delta_temperature_c
            )
            or self.predicted_delta_temperature_c >= 0.0
        ):
            raise ValueError(
                "V2 thermal preload seed must represent "
                "finite contraction."
            )


def derive_analytical_thermal_preload_seed_v2(
    resolved: ResolvedCase,
) -> ThermalPreloadCalibrationSeedV2:
    """Derive the physics-separated V2 FEM preload seed."""

    joint = build_analytical_joint_input(
        resolved
    )

    compatibility = (
        derive_thermal_preload_compatibility_mechanics(
            resolved
        )
    )

    member = calculate_analytical_member_mechanics(
        joint
    )

    coefficient = (
        resolved.bolt_material.thermal_expansion_per_c
    )

    if coefficient is None:
        raise ValueError(
            "V2 analytical thermal preload seeding requires "
            "a governed bolt thermal expansion coefficient."
        )

    total_compliance_mm_per_n = (
        compatibility.bolt_compliance_mm_per_n
        + member.total_compliance_mm_per_n
    )

    target_force_n = (
        resolved.source_case.loading.target_preload_n
    )

    predicted_delta_temperature_c = -(
        target_force_n
        * total_compliance_mm_per_n
        / (
            coefficient
            * compatibility.thermal_actuation_length_mm
        )
    )

    return ThermalPreloadCalibrationSeedV2(
        method=(
            "physical_free_span_plus_"
            "distributed_thread_transfer_v2"
        ),
        target_force_n=target_force_n,
        bolt_compliance_mm_per_n=(
            compatibility.bolt_compliance_mm_per_n
        ),
        member_compliance_mm_per_n=(
            member.total_compliance_mm_per_n
        ),
        total_compliance_mm_per_n=(
            total_compliance_mm_per_n
        ),
        thermal_actuation_length_mm=(
            compatibility.thermal_actuation_length_mm
        ),
        expansion_coefficient_per_c=coefficient,
        predicted_delta_temperature_c=(
            predicted_delta_temperature_c
        ),
    )
