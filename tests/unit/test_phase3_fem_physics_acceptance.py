"""Tests for general Phase-3 FEM physics acceptance."""

from __future__ import annotations

from threadrom.case.resolved import ResolvedAssembly
from threadrom.factory.fem_acceptance_policy import (
    FemNonlinearRetryPolicy,
    FemPhysicsAcceptancePolicy,
    FemThreadFlankNormalFamily,
    derive_complete_joint_physics_acceptance_policy,
)
from threadrom.factory.fem_physics_acceptance import (
    build_policy_numerical_completion_acceptance_checks,
    build_policy_thread_flank_acceptance_checks,
    evaluate_fem_physics_acceptance,
)
from threadrom.factory.fem_reproduction_acceptance import (
    FemAcceptanceCheckKind,
)
from threadrom.factory.preload_calibration_controller import (
    ClampForceMeasurement,
    evaluate_preload_calibration,
)
from threadrom.postprocessing.calculix_nonlinear_progress import (
    AcceptedIncrement,
)
from threadrom.postprocessing.calculix_semantic_mechanics import (
    BoltFreeSpanStressRegion,
    CompleteJointAxialStressState,
    CompleteJointDeformationState,
    TetrahedralAxialStressSummary,
)
from threadrom.postprocessing.calculix_thread_flank import (
    ThreadFlankStressState,
    ThreadFlankStressSummary,
)


def _summary(
    name: str,
    mean_compression_mpa: float,
) -> ThreadFlankStressSummary:
    return ThreadFlankStressSummary(
        name=name,
        triangle_count=100,
        area_mm2=10.0,
        mean_compression_mpa=mean_compression_mpa,
        median_compression_mpa=mean_compression_mpa,
        p95_compression_mpa=mean_compression_mpa,
        maximum_compression_mpa=mean_compression_mpa,
        compressed_area_percent=80.0,
        force_proxy_n=1000.0,
    )


def _flank_state(
    *,
    positive_mean_mpa: float,
    negative_mean_mpa: float,
) -> ThreadFlankStressState:
    positive = _summary(
        "+Z-normal flank",
        positive_mean_mpa,
    )
    negative = _summary(
        "-Z-normal flank",
        negative_mean_mpa,
    )

    if positive_mean_mpa >= negative_mean_mpa:
        dominant = positive
        opposite = negative
    else:
        dominant = negative
        opposite = positive

    return ThreadFlankStressState(
        engagement_min_z_mm=20.0,
        engagement_max_z_mm=28.0,
        engaged_triangle_count=200,
        low_cluster_center_abs_nz=0.01,
        high_cluster_center_abs_nz=0.50,
        flank_threshold_abs_nz=0.255,
        positive_z_flank=positive,
        negative_z_flank=negative,
        dominant_flank_name=dominant.name,
        dominance_ratio=(
            dominant.mean_compression_mpa
            / max(
                opposite.mean_compression_mpa,
                1.0e-12,
            )
        ),
    )


def _policy(
    *,
    flank: FemThreadFlankNormalFamily,
    retries: FemNonlinearRetryPolicy,
) -> FemPhysicsAcceptancePolicy:
    return FemPhysicsAcceptancePolicy(
        policy_id="test_policy",
        intended_thread_flank_normal_family=flank,
        nonlinear_retry_policy=retries,
    )


def test_negative_z_policy_accepts_negative_z_dominance() -> None:
    checks = build_policy_thread_flank_acceptance_checks(
        state=_flank_state(
            positive_mean_mpa=20.0,
            negative_mean_mpa=200.0,
        ),
        policy=_policy(
            flank=FemThreadFlankNormalFamily.NEGATIVE_Z,
            retries=FemNonlinearRetryPolicy.ALLOW,
        ),
    )

    assert checks[0].passed


def test_positive_z_policy_accepts_positive_z_dominance() -> None:
    checks = build_policy_thread_flank_acceptance_checks(
        state=_flank_state(
            positive_mean_mpa=200.0,
            negative_mean_mpa=20.0,
        ),
        policy=_policy(
            flank=FemThreadFlankNormalFamily.POSITIVE_Z,
            retries=FemNonlinearRetryPolicy.ALLOW,
        ),
    )

    assert checks[0].passed


def test_wrong_dominant_flank_fails() -> None:
    checks = build_policy_thread_flank_acceptance_checks(
        state=_flank_state(
            positive_mean_mpa=200.0,
            negative_mean_mpa=20.0,
        ),
        policy=_policy(
            flank=FemThreadFlankNormalFamily.NEGATIVE_Z,
            retries=FemNonlinearRetryPolicy.ALLOW,
        ),
    )

    assert not checks[0].passed


def test_allowed_retry_is_diagnostic_not_failure() -> None:
    increments = (
        AcceptedIncrement(
            step=1,
            increment=1,
            attempt=2,
            iterations=5,
            total_time=1.0,
            step_time=1.0,
            increment_time=1.0,
        ),
    )

    checks = build_policy_numerical_completion_acceptance_checks(
        return_code=0,
        stdout="Job finished",
        accepted_increments=increments,
        policy=_policy(
            flank=FemThreadFlankNormalFamily.NEGATIVE_Z,
            retries=FemNonlinearRetryPolicy.ALLOW,
        ),
    )

    retry = next(
        check
        for check in checks
        if check.name == "nonlinear retry policy"
    )

    assert retry.kind is FemAcceptanceCheckKind.DIAGNOSTIC
    assert retry.passed
    assert retry.measured == 2


def test_strict_retry_policy_fails_att2() -> None:
    increments = (
        AcceptedIncrement(
            step=1,
            increment=1,
            attempt=2,
            iterations=5,
            total_time=1.0,
            step_time=1.0,
            increment_time=1.0,
        ),
    )

    checks = build_policy_numerical_completion_acceptance_checks(
        return_code=0,
        stdout="Job finished",
        accepted_increments=increments,
        policy=_policy(
            flank=FemThreadFlankNormalFamily.NEGATIVE_Z,
            retries=(
                FemNonlinearRetryPolicy.REQUIRE_FIRST_ATTEMPT
            ),
        ),
    )

    retry = next(
        check
        for check in checks
        if check.name == "nonlinear retry policy"
    )

    assert retry.kind is FemAcceptanceCheckKind.HARD_GATE
    assert not retry.passed


def test_completion_still_requires_job_finished() -> None:
    increments = (
        AcceptedIncrement(
            step=1,
            increment=1,
            attempt=1,
            iterations=5,
            total_time=1.0,
            step_time=1.0,
            increment_time=1.0,
        ),
    )

    checks = build_policy_numerical_completion_acceptance_checks(
        return_code=0,
        stdout="solver output without completion marker",
        accepted_increments=increments,
        policy=_policy(
            flank=FemThreadFlankNormalFamily.NEGATIVE_Z,
            retries=FemNonlinearRetryPolicy.ALLOW,
        ),
    )

    finished = next(
        check
        for check in checks
        if check.name == "CalculiX Job finished"
    )

    assert not finished.passed

def _cp4_axial_summary(
    mean_szz_mpa: float,
) -> TetrahedralAxialStressSummary:
    return TetrahedralAxialStressSummary(
        mean_szz_mpa=mean_szz_mpa,
        median_szz_mpa=mean_szz_mpa,
        element_count=1,
        total_volume_mm3=1.0,
    )


def _cp4_axial_state() -> CompleteJointAxialStressState:
    return CompleteJointAxialStressState(
        bolt_region=BoltFreeSpanStressRegion(
            free_span_start_z_mm=0.0,
            free_span_end_z_mm=20.0,
            band_start_z_mm=5.0,
            band_end_z_mm=15.0,
            selected_element_indices=(0,),
        ),
        bolt=_cp4_axial_summary(
            315.656054
        ),
        head_side_member=_cp4_axial_summary(
            -33.081018
        ),
        nut_side_member=_cp4_axial_summary(
            -32.951690
        ),
    )


def _cp4_deformation_state() -> CompleteJointDeformationState:
    return CompleteJointDeformationState(
        free_span_start_z_mm=0.0,
        free_span_end_z_mm=20.0,
        free_span_length_mm=20.0,
        head_bearing_mean_uz_mm=0.0014,
        nut_bearing_mean_uz_mm=-0.0018,
        member_shortening_mm=0.003212695019,
        bolt_under_head_mean_uz_mm=0.008,
        bolt_engagement_entry_mean_uz_mm=-0.012,
        bolt_geometric_change_mm=-0.020,
        bolt_thermal_free_change_mm=-0.058,
        bolt_mechanical_extension_mm=0.038321380457,
        engagement_entry_node_count=1,
    )


def _cp4_preload_decision():
    measurement = ClampForceMeasurement(
        under_head_force_n=20_060.270,
        nut_bearing_force_n=20_066.050,
        member_interface_force_n=20_064.180,
    )

    return evaluate_preload_calibration(
        target_force_n=20_000.0,
        target_relative_tolerance=0.01,
        spread_relative_tolerance=0.01,
        measurement=measurement,
        previous_point=None,
        current_delta_temperature_c=-243.2744971,
    )


def _cp4_accepted_increment(
    *,
    attempt: int = 1,
) -> AcceptedIncrement:
    return AcceptedIncrement(
        step=1,
        increment=1,
        attempt=attempt,
        iterations=5,
        total_time=0.05,
        step_time=0.05,
        increment_time=0.05,
    )


def test_generic_evaluator_accepts_cp4_like_physical_state() -> None:
    result = evaluate_fem_physics_acceptance(
        policy=_policy(
            flank=FemThreadFlankNormalFamily.NEGATIVE_Z,
            retries=FemNonlinearRetryPolicy.ALLOW,
        ),
        preload_decision=_cp4_preload_decision(),
        thread_normal_force_n=15_318.240,
        axial_state=_cp4_axial_state(),
        deformation_state=_cp4_deformation_state(),
        thread_flank_state=_flank_state(
            positive_mean_mpa=38.442914,
            negative_mean_mpa=317.140284,
        ),
        accepted_increments=(
            _cp4_accepted_increment()
        ,),
        return_code=0,
        stdout="CalculiX\nJob finished",
    )

    assert result.passed
    assert not result.failed_checks
    assert all(
        check.kind is not FemAcceptanceCheckKind.REPRODUCTION_PARITY
        for check in result.checks
    )


def test_generic_evaluator_rejects_wrong_loaded_flank() -> None:
    result = evaluate_fem_physics_acceptance(
        policy=_policy(
            flank=FemThreadFlankNormalFamily.NEGATIVE_Z,
            retries=FemNonlinearRetryPolicy.ALLOW,
        ),
        preload_decision=_cp4_preload_decision(),
        thread_normal_force_n=15_318.240,
        axial_state=_cp4_axial_state(),
        deformation_state=_cp4_deformation_state(),
        thread_flank_state=_flank_state(
            positive_mean_mpa=317.140284,
            negative_mean_mpa=38.442914,
        ),
        accepted_increments=(
            _cp4_accepted_increment()
        ,),
        return_code=0,
        stdout="CalculiX\nJob finished",
    )

    assert not result.passed

    assert tuple(
        check.name
        for check in result.failed_checks
    ) == (
        "intended thread flank carries dominant compression",
    )

def test_non_reference_case_passes_without_reproduction_oracle() -> None:
    assembly = ResolvedAssembly(
        assembly_id="non_reference_joint",
        bolt_length_mm=42.0,
        pitch_mm=2.0,
        upper_member_thickness_mm=14.0,
        lower_member_thickness_mm=12.0,
        total_grip_length_mm=26.0,
        nut_thickness_mm=10.0,
        thread_engagement_length_mm=9.0,
        protrusion_length_mm=6.0,
        clearance_hole_diameter_mm=14.0,
        outer_diameter_mm=36.0,
    )

    policy = derive_complete_joint_physics_acceptance_policy(
        assembly,
        policy_id="non_reference_general_v1",
        nonlinear_retry_policy=FemNonlinearRetryPolicy.ALLOW,
    )

    measurement = ClampForceMeasurement(
        under_head_force_n=12_060.0,
        nut_bearing_force_n=12_045.0,
        member_interface_force_n=12_050.0,
    )

    preload_decision = evaluate_preload_calibration(
        target_force_n=12_000.0,
        target_relative_tolerance=0.01,
        spread_relative_tolerance=0.01,
        measurement=measurement,
        previous_point=None,
        current_delta_temperature_c=-170.0,
    )

    axial_state = CompleteJointAxialStressState(
        bolt_region=BoltFreeSpanStressRegion(
            free_span_start_z_mm=0.0,
            free_span_end_z_mm=26.0,
            band_start_z_mm=6.0,
            band_end_z_mm=20.0,
            selected_element_indices=(0,),
        ),
        bolt=_cp4_axial_summary(
            185.0
        ),
        head_side_member=_cp4_axial_summary(
            -21.0
        ),
        nut_side_member=_cp4_axial_summary(
            -20.5
        ),
    )

    deformation_state = CompleteJointDeformationState(
        free_span_start_z_mm=0.0,
        free_span_end_z_mm=26.0,
        free_span_length_mm=26.0,
        head_bearing_mean_uz_mm=0.0010,
        nut_bearing_mean_uz_mm=-0.0015,
        member_shortening_mm=0.0025,
        bolt_under_head_mean_uz_mm=0.006,
        bolt_engagement_entry_mean_uz_mm=-0.010,
        bolt_geometric_change_mm=-0.016,
        bolt_thermal_free_change_mm=-0.045,
        bolt_mechanical_extension_mm=0.029,
        engagement_entry_node_count=1,
    )

    accepted_increment = AcceptedIncrement(
        step=1,
        increment=1,
        attempt=2,
        iterations=8,
        total_time=0.04,
        step_time=0.04,
        increment_time=0.04,
    )

    result = evaluate_fem_physics_acceptance(
        policy=policy,
        preload_decision=preload_decision,
        thread_normal_force_n=9_100.0,
        axial_state=axial_state,
        deformation_state=deformation_state,
        thread_flank_state=_flank_state(
            positive_mean_mpa=24.0,
            negative_mean_mpa=165.0,
        ),
        accepted_increments=(
            accepted_increment,
        ),
        return_code=0,
        stdout="CalculiX\nJob finished",
    )

    assert result.passed
    assert result.policy_id == "non_reference_general_v1"

    assert all(
        check.kind is not FemAcceptanceCheckKind.REPRODUCTION_PARITY
        for check in result.checks
    )

    retry = next(
        check
        for check in result.checks
        if check.name == "nonlinear retry policy"
    )

    assert retry.kind is FemAcceptanceCheckKind.DIAGNOSTIC
    assert retry.passed
    assert retry.measured == 2

