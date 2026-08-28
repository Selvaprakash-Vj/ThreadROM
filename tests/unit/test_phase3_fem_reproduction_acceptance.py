from pathlib import Path

"""Tests for the governed FEM reproduction acceptance model."""

import pytest

import threadrom.factory.fem_reproduction_acceptance as acceptance_module

from threadrom.factory.fem_reproduction_acceptance import (
    FemAcceptanceCheck,
    FemAcceptanceCheckKind,
    FemAcceptanceDisposition,
    FemReproductionAcceptanceResult,
    build_axial_state_acceptance_checks,
    build_deformation_acceptance_checks,
    build_numerical_completion_acceptance_checks,
    build_preload_acceptance_checks,
    build_reproduction_parity_checks,
    build_thread_contact_acceptance_checks,
    build_thread_flank_acceptance_checks,
    evaluate_certified_reproduction,
)
from threadrom.factory.preload_calibration_controller import (
    ClampForceMeasurement,
    evaluate_preload_calibration,
)
from threadrom.factory.fem_result_oracle import (
    load_fem_certified_result_oracle,
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
from threadrom.postprocessing.calculix_nonlinear_progress import (
    AcceptedIncrement,
)


def test_acceptance_result_passes_when_all_gates_pass() -> None:
    result = FemReproductionAcceptanceResult(
        checks=(
            FemAcceptanceCheck(
                name="preload target",
                kind=FemAcceptanceCheckKind.HARD_GATE,
                passed=True,
                measured=20_063.5,
                expected=20_000.0,
            ),
            FemAcceptanceCheck(
                name="bolt stress parity",
                kind=(
                    FemAcceptanceCheckKind.REPRODUCTION_PARITY
                ),
                passed=True,
                measured=315.656054,
                expected=315.656,
            ),
            FemAcceptanceCheck(
                name="local displacement diagnostic",
                kind=FemAcceptanceCheckKind.DIAGNOSTIC,
                passed=False,
                measured=0.524556893,
            ),
        )
    )

    assert result.passed
    assert (
        result.disposition
        is FemAcceptanceDisposition.PASS
    )
    assert result.failed_checks == ()
    assert len(result.hard_gate_checks) == 1
    assert len(result.parity_checks) == 1
    assert len(result.diagnostic_checks) == 1


def test_failed_hard_gate_fails_overall_result() -> None:
    result = FemReproductionAcceptanceResult(
        checks=(
            FemAcceptanceCheck(
                name="bolt tension",
                kind=FemAcceptanceCheckKind.HARD_GATE,
                passed=False,
                measured=-1.0,
                expected="positive axial stress",
            ),
        )
    )

    assert not result.passed
    assert (
        result.disposition
        is FemAcceptanceDisposition.FAIL
    )
    assert tuple(
        check.name
        for check in result.failed_checks
    ) == ("bolt tension",)


def test_failed_parity_check_fails_reproduction() -> None:
    result = FemReproductionAcceptanceResult(
        checks=(
            FemAcceptanceCheck(
                name="member shortening parity",
                kind=(
                    FemAcceptanceCheckKind.REPRODUCTION_PARITY
                ),
                passed=False,
                measured=0.004,
                expected=0.003212695,
            ),
        )
    )

    assert not result.passed
    assert len(result.failed_checks) == 1


def test_diagnostic_failure_does_not_fail_result() -> None:
    result = FemReproductionAcceptanceResult(
        checks=(
            FemAcceptanceCheck(
                name="physical gate",
                kind=FemAcceptanceCheckKind.HARD_GATE,
                passed=True,
            ),
            FemAcceptanceCheck(
                name="diagnostic only",
                kind=FemAcceptanceCheckKind.DIAGNOSTIC,
                passed=False,
            ),
        )
    )

    assert result.passed
    assert result.failed_checks == ()


def test_acceptance_result_rejects_duplicate_names() -> None:
    check = FemAcceptanceCheck(
        name="duplicate",
        kind=FemAcceptanceCheckKind.HARD_GATE,
        passed=True,
    )

    with pytest.raises(
        ValueError,
        match="unique",
    ):
        FemReproductionAcceptanceResult(
            checks=(check, check)
        )


def test_acceptance_result_requires_a_governed_gate() -> None:
    with pytest.raises(
        ValueError,
        match="governed gate",
    ):
        FemReproductionAcceptanceResult(
            checks=(
                FemAcceptanceCheck(
                    name="diagnostic",
                    kind=FemAcceptanceCheckKind.DIAGNOSTIC,
                    passed=True,
                ),
            )
        )


def test_acceptance_check_requires_a_name() -> None:
    with pytest.raises(
        ValueError,
        match="name",
    ):
        FemAcceptanceCheck(
            name="   ",
            kind=FemAcceptanceCheckKind.HARD_GATE,
            passed=True,
        )

def test_certified_a2_preload_builds_passing_gates() -> None:
    measurement = ClampForceMeasurement(
        under_head_force_n=20_060.270,
        nut_bearing_force_n=20_066.050,
        member_interface_force_n=20_064.180,
    )

    decision = evaluate_preload_calibration(
        target_force_n=20_000.0,
        target_relative_tolerance=0.01,
        spread_relative_tolerance=0.01,
        measurement=measurement,
        previous_point=None,
        current_delta_temperature_c=-243.2744971,
    )

    checks = build_preload_acceptance_checks(
        decision
    )

    assert tuple(
        check.name
        for check in checks
    ) == (
        "preload target force",
        "planar clamp-force consistency",
    )

    assert all(
        check.kind
        is FemAcceptanceCheckKind.HARD_GATE
        for check in checks
    )

    assert all(
        check.passed
        for check in checks
    )

    assert checks[0].measured == pytest.approx(
        20_063.5
    )

    assert checks[1].measured == pytest.approx(
        5.780 / 20_063.5
    )


def test_preload_gate_preserves_governed_failure() -> None:
    measurement = ClampForceMeasurement(
        under_head_force_n=18_000.0,
        nut_bearing_force_n=18_010.0,
        member_interface_force_n=17_990.0,
    )

    decision = evaluate_preload_calibration(
        target_force_n=20_000.0,
        target_relative_tolerance=0.01,
        spread_relative_tolerance=0.01,
        measurement=measurement,
        previous_point=None,
        current_delta_temperature_c=-200.0,
    )

    checks = build_preload_acceptance_checks(
        decision
    )

    assert not checks[0].passed
    assert checks[1].passed

    result = FemReproductionAcceptanceResult(
        checks=checks
    )

    assert not result.passed

def _axial_summary(
    mean_szz_mpa: float,
) -> TetrahedralAxialStressSummary:
    return TetrahedralAxialStressSummary(
        mean_szz_mpa=mean_szz_mpa,
        median_szz_mpa=mean_szz_mpa,
        element_count=1,
        total_volume_mm3=1.0,
    )


def _axial_state(
    *,
    bolt_szz_mpa: float,
    head_szz_mpa: float,
    nut_szz_mpa: float,
) -> CompleteJointAxialStressState:
    return CompleteJointAxialStressState(
        bolt_region=BoltFreeSpanStressRegion(
            free_span_start_z_mm=0.0,
            free_span_end_z_mm=20.0,
            band_start_z_mm=5.0,
            band_end_z_mm=15.0,
            selected_element_indices=(0,),
        ),
        bolt=_axial_summary(
            bolt_szz_mpa
        ),
        head_side_member=_axial_summary(
            head_szz_mpa
        ),
        nut_side_member=_axial_summary(
            nut_szz_mpa
        ),
    )


def test_certified_a2_axial_state_builds_passing_gates() -> None:
    state = _axial_state(
        bolt_szz_mpa=315.656054,
        head_szz_mpa=-33.081018,
        nut_szz_mpa=-32.951690,
    )

    checks = build_axial_state_acceptance_checks(
        state
    )

    assert tuple(
        check.name
        for check in checks
    ) == (
        "bolt free-span axial state = tension",
        "head-side member axial state = compression",
        "nut-side member axial state = compression",
    )

    assert all(
        check.kind
        is FemAcceptanceCheckKind.HARD_GATE
        for check in checks
    )

    assert all(
        check.passed
        for check in checks
    )

    result = FemReproductionAcceptanceResult(
        checks=checks
    )

    assert result.passed


def test_axial_state_rejects_bolt_compression() -> None:
    checks = build_axial_state_acceptance_checks(
        _axial_state(
            bolt_szz_mpa=-1.0,
            head_szz_mpa=-33.0,
            nut_szz_mpa=-32.0,
        )
    )

    assert not checks[0].passed
    assert checks[1].passed
    assert checks[2].passed

    assert not FemReproductionAcceptanceResult(
        checks=checks
    ).passed


def test_axial_state_rejects_head_member_tension() -> None:
    checks = build_axial_state_acceptance_checks(
        _axial_state(
            bolt_szz_mpa=300.0,
            head_szz_mpa=1.0,
            nut_szz_mpa=-32.0,
        )
    )

    assert checks[0].passed
    assert not checks[1].passed
    assert checks[2].passed


def test_axial_state_rejects_nut_member_tension() -> None:
    checks = build_axial_state_acceptance_checks(
        _axial_state(
            bolt_szz_mpa=300.0,
            head_szz_mpa=-33.0,
            nut_szz_mpa=1.0,
        )
    )

    assert checks[0].passed
    assert checks[1].passed
    assert not checks[2].passed

def _deformation_state(
    *,
    member_shortening_mm: float,
    bolt_mechanical_extension_mm: float,
) -> CompleteJointDeformationState:
    return CompleteJointDeformationState(
        free_span_start_z_mm=0.0,
        free_span_end_z_mm=20.0,
        free_span_length_mm=20.0,
        head_bearing_mean_uz_mm=0.0014,
        nut_bearing_mean_uz_mm=-0.0018,
        member_shortening_mm=member_shortening_mm,
        bolt_under_head_mean_uz_mm=0.008,
        bolt_engagement_entry_mean_uz_mm=-0.012,
        bolt_geometric_change_mm=-0.020,
        bolt_thermal_free_change_mm=-0.058,
        bolt_mechanical_extension_mm=(
            bolt_mechanical_extension_mm
        ),
        engagement_entry_node_count=1,
    )


def test_certified_a2_deformation_builds_passing_gates() -> None:
    state = _deformation_state(
        member_shortening_mm=0.003212695019,
        bolt_mechanical_extension_mm=0.038321380457,
    )

    checks = build_deformation_acceptance_checks(
        state
    )

    assert tuple(
        check.name
        for check in checks
    ) == (
        "member stack physically shortens",
        "bolt mechanical extension positive",
    )

    assert all(
        check.kind
        is FemAcceptanceCheckKind.HARD_GATE
        for check in checks
    )

    assert all(
        check.passed
        for check in checks
    )

    assert FemReproductionAcceptanceResult(
        checks=checks
    ).passed


def test_deformation_rejects_nonshortening_member_stack() -> None:
    checks = build_deformation_acceptance_checks(
        _deformation_state(
            member_shortening_mm=-0.001,
            bolt_mechanical_extension_mm=0.038,
        )
    )

    assert not checks[0].passed
    assert checks[1].passed

    assert not FemReproductionAcceptanceResult(
        checks=checks
    ).passed


def test_deformation_rejects_nonpositive_bolt_extension() -> None:
    checks = build_deformation_acceptance_checks(
        _deformation_state(
            member_shortening_mm=0.003,
            bolt_mechanical_extension_mm=-0.001,
        )
    )

    assert checks[0].passed
    assert not checks[1].passed

    assert not FemReproductionAcceptanceResult(
        checks=checks
    ).passed

def _flank_summary(
    *,
    name: str,
    mean_compression_mpa: float,
) -> ThreadFlankStressSummary:
    return ThreadFlankStressSummary(
        name=name,
        triangle_count=10,
        area_mm2=10.0,
        mean_compression_mpa=mean_compression_mpa,
        median_compression_mpa=mean_compression_mpa,
        p95_compression_mpa=mean_compression_mpa,
        maximum_compression_mpa=mean_compression_mpa,
        compressed_area_percent=100.0,
        force_proxy_n=(
            mean_compression_mpa
            * 10.0
        ),
    )


def _thread_flank_state(
    *,
    positive_mean_mpa: float,
    negative_mean_mpa: float,
) -> ThreadFlankStressState:
    positive = _flank_summary(
        name="+Z-normal flank",
        mean_compression_mpa=positive_mean_mpa,
    )

    negative = _flank_summary(
        name="-Z-normal flank",
        mean_compression_mpa=negative_mean_mpa,
    )

    if positive_mean_mpa >= negative_mean_mpa:
        dominant_name = "+Z-normal flank"
        dominant_mean = positive_mean_mpa
        opposite_mean = negative_mean_mpa
    else:
        dominant_name = "-Z-normal flank"
        dominant_mean = negative_mean_mpa
        opposite_mean = positive_mean_mpa

    ratio = (
        dominant_mean
        / max(
            opposite_mean,
            1.0e-12,
        )
    )

    return ThreadFlankStressState(
        engagement_min_z_mm=20.0,
        engagement_max_z_mm=28.0,
        engaged_triangle_count=20,
        low_cluster_center_abs_nz=0.01,
        high_cluster_center_abs_nz=0.865,
        flank_threshold_abs_nz=0.4375,
        positive_z_flank=positive,
        negative_z_flank=negative,
        dominant_flank_name=dominant_name,
        dominance_ratio=ratio,
    )


def test_certified_a2_thread_flank_builds_passing_gate() -> None:
    state = _thread_flank_state(
        positive_mean_mpa=38.442914,
        negative_mean_mpa=317.140284,
    )

    checks = build_thread_flank_acceptance_checks(
        state
    )

    assert len(checks) == 1

    check = checks[0]

    assert (
        check.name
        == "intended thread flank carries dominant compression"
    )

    assert (
        check.kind
        is FemAcceptanceCheckKind.HARD_GATE
    )

    assert check.passed

    assert check.measured == pytest.approx(
        8.249642,
        rel=1.0e-6,
    )

    assert FemReproductionAcceptanceResult(
        checks=checks
    ).passed


def test_thread_flank_rejects_opposite_flank_dominance() -> None:
    state = _thread_flank_state(
        positive_mean_mpa=120.0,
        negative_mean_mpa=20.0,
    )

    checks = build_thread_flank_acceptance_checks(
        state
    )

    assert not checks[0].passed

    assert not FemReproductionAcceptanceResult(
        checks=checks
    ).passed


def test_thread_flank_gate_does_not_require_certified_ratio() -> None:
    state = _thread_flank_state(
        positive_mean_mpa=100.0,
        negative_mean_mpa=101.0,
    )

    checks = build_thread_flank_acceptance_checks(
        state
    )

    assert checks[0].passed

    assert checks[0].measured == pytest.approx(
        1.01
    )

def _accepted_increment(
    *,
    increment: int = 1,
    attempt: int = 1,
    iterations: int = 5,
) -> AcceptedIncrement:
    return AcceptedIncrement(
        step=1,
        increment=increment,
        attempt=attempt,
        iterations=iterations,
        total_time=0.05 * increment,
        step_time=0.05 * increment,
        increment_time=0.05,
    )


def test_certified_numerical_completion_builds_passing_gates() -> None:
    increments = tuple(
        _accepted_increment(
            increment=index,
            iterations=(
                21
                if index == 20
                else 5
            ),
        )
        for index in range(
            1,
            21,
        )
    )

    checks = build_numerical_completion_acceptance_checks(
        return_code=0,
        stdout="CalculiX output\nJob finished\n",
        accepted_increments=increments,
    )

    assert len(checks) == 4

    assert all(
        check.kind
        is FemAcceptanceCheckKind.HARD_GATE
        for check in checks
    )

    assert all(
        check.passed
        for check in checks
    )

    assert FemReproductionAcceptanceResult(
        checks=checks
    ).passed


def test_numerical_completion_rejects_solver_failure() -> None:
    checks = build_numerical_completion_acceptance_checks(
        return_code=1,
        stdout="Job finished",
        accepted_increments=(
            _accepted_increment(),
        ),
    )

    assert not checks[0].passed

    assert not FemReproductionAcceptanceResult(
        checks=checks
    ).passed


def test_numerical_completion_requires_accepted_history() -> None:
    checks = build_numerical_completion_acceptance_checks(
        return_code=0,
        stdout="Job finished",
        accepted_increments=(),
    )

    assert not checks[1].passed
    assert not checks[2].passed

    assert not FemReproductionAcceptanceResult(
        checks=checks
    ).passed


def test_numerical_completion_rejects_cutback_attempt() -> None:
    checks = build_numerical_completion_acceptance_checks(
        return_code=0,
        stdout="Job finished",
        accepted_increments=(
            _accepted_increment(
                increment=1,
                attempt=1,
            ),
            _accepted_increment(
                increment=2,
                attempt=2,
            ),
        ),
    )

    assert checks[0].passed
    assert checks[1].passed
    assert not checks[2].passed
    assert checks[3].passed


def test_numerical_completion_requires_job_finished_marker() -> None:
    checks = build_numerical_completion_acceptance_checks(
        return_code=0,
        stdout="CalculiX terminated without completion marker.",
        accepted_increments=(
            _accepted_increment(),
        ),
    )

    assert checks[0].passed
    assert checks[1].passed
    assert checks[2].passed
    assert not checks[3].passed


def _certified_preload_decision():
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

def test_certified_a2_reproduction_parity_checks_pass() -> None:
    root = Path(__file__).resolve().parents[2]

    oracle = load_fem_certified_result_oracle(
        root
        / "config"
        / "phase2_certified_result_oracle.toml"
    )

    axial_state = CompleteJointAxialStressState(
        bolt_region=BoltFreeSpanStressRegion(
            free_span_start_z_mm=0.0,
            free_span_end_z_mm=20.0,
            band_start_z_mm=5.0,
            band_end_z_mm=15.0,
            selected_element_indices=tuple(
                range(128619)
            ),
        ),
        bolt=TetrahedralAxialStressSummary(
            mean_szz_mpa=315.656054,
            median_szz_mpa=335.368500,
            element_count=128619,
            total_volume_mm3=1.0,
        ),
        head_side_member=TetrahedralAxialStressSummary(
            mean_szz_mpa=-33.081018,
            median_szz_mpa=-18.280125,
            element_count=29037,
            total_volume_mm3=1.0,
        ),
        nut_side_member=TetrahedralAxialStressSummary(
            mean_szz_mpa=-32.951690,
            median_szz_mpa=-14.991915,
            element_count=28835,
            total_volume_mm3=1.0,
        ),
    )

    deformation_state = _deformation_state(
        member_shortening_mm=0.003212695019,
        bolt_mechanical_extension_mm=0.038321380457,
    )

    flank_state = _thread_flank_state(
        positive_mean_mpa=38.442914,
        negative_mean_mpa=317.140284,
    )

    flank_state = ThreadFlankStressState(
        engagement_min_z_mm=20.0,
        engagement_max_z_mm=28.0,
        engaged_triangle_count=11943,
        low_cluster_center_abs_nz=0.011113,
        high_cluster_center_abs_nz=0.865148,
        flank_threshold_abs_nz=0.438130,
        positive_z_flank=ThreadFlankStressSummary(
            name="+Z-normal flank",
            triangle_count=3949,
            area_mm2=1.0,
            mean_compression_mpa=38.442914,
            median_compression_mpa=0.0,
            p95_compression_mpa=1.0,
            maximum_compression_mpa=1.0,
            compressed_area_percent=19.162511,
            force_proxy_n=1.0,
        ),
        negative_z_flank=ThreadFlankStressSummary(
            name="-Z-normal flank",
            triangle_count=3948,
            area_mm2=1.0,
            mean_compression_mpa=317.140284,
            median_compression_mpa=46.029994,
            p95_compression_mpa=1.0,
            maximum_compression_mpa=1.0,
            compressed_area_percent=59.843728,
            force_proxy_n=1.0,
        ),
        dominant_flank_name="-Z-normal flank",
        dominance_ratio=8.249642,
    )

    increments = tuple(
        _accepted_increment(
            increment=index,
            attempt=1,
            iterations=(
                21
                if index == 20
                else 5
            ),
        )
        for index in range(
            1,
            21,
        )
    )

    checks = build_reproduction_parity_checks(
        oracle=oracle,
        preload_decision=_certified_preload_decision(),
        thread_normal_force_n=15_318.240,
        analytical_member_shortening_mm=0.003113245,
        axial_state=axial_state,
        deformation_state=deformation_state,
        thread_flank_state=flank_state,
        accepted_increments=increments,
    )

    assert checks
    assert all(
        check.kind
        is FemAcceptanceCheckKind.REPRODUCTION_PARITY
        for check in checks
    )

    assert all(
        check.passed
        for check in checks
    )

    assert FemReproductionAcceptanceResult(
        checks=checks
    ).passed


def test_reproduction_parity_rejects_wrong_final_iterations() -> None:
    root = Path(__file__).resolve().parents[2]

    oracle = load_fem_certified_result_oracle(
        root
        / "config"
        / "phase2_certified_result_oracle.toml"
    )

    axial_state = CompleteJointAxialStressState(
        bolt_region=BoltFreeSpanStressRegion(
            free_span_start_z_mm=0.0,
            free_span_end_z_mm=20.0,
            band_start_z_mm=5.0,
            band_end_z_mm=15.0,
            selected_element_indices=tuple(
                range(128619)
            ),
        ),
        bolt=TetrahedralAxialStressSummary(
            mean_szz_mpa=315.656,
            median_szz_mpa=335.369,
            element_count=128619,
            total_volume_mm3=1.0,
        ),
        head_side_member=TetrahedralAxialStressSummary(
            mean_szz_mpa=-33.081,
            median_szz_mpa=0.0,
            element_count=29037,
            total_volume_mm3=1.0,
        ),
        nut_side_member=TetrahedralAxialStressSummary(
            mean_szz_mpa=-32.952,
            median_szz_mpa=0.0,
            element_count=28835,
            total_volume_mm3=1.0,
        ),
    )

    deformation_state = _deformation_state(
        member_shortening_mm=0.003212695,
        bolt_mechanical_extension_mm=0.038321380,
    )

    flank_state = ThreadFlankStressState(
        engagement_min_z_mm=20.0,
        engagement_max_z_mm=28.0,
        engaged_triangle_count=11943,
        low_cluster_center_abs_nz=0.01,
        high_cluster_center_abs_nz=0.865,
        flank_threshold_abs_nz=0.438,
        positive_z_flank=ThreadFlankStressSummary(
            name="+Z-normal flank",
            triangle_count=3949,
            area_mm2=1.0,
            mean_compression_mpa=38.443,
            median_compression_mpa=0.0,
            p95_compression_mpa=1.0,
            maximum_compression_mpa=1.0,
            compressed_area_percent=19.163,
            force_proxy_n=1.0,
        ),
        negative_z_flank=ThreadFlankStressSummary(
            name="-Z-normal flank",
            triangle_count=3948,
            area_mm2=1.0,
            mean_compression_mpa=317.140,
            median_compression_mpa=46.030,
            p95_compression_mpa=1.0,
            maximum_compression_mpa=1.0,
            compressed_area_percent=59.844,
            force_proxy_n=1.0,
        ),
        dominant_flank_name="-Z-normal flank",
        dominance_ratio=8.2496,
    )

    increments = tuple(
        _accepted_increment(
            increment=index,
            attempt=1,
            iterations=(
                20
                if index == 20
                else 5
            ),
        )
        for index in range(
            1,
            21,
        )
    )

    checks = build_reproduction_parity_checks(
        oracle=oracle,
        preload_decision=_certified_preload_decision(),
        thread_normal_force_n=15_318.240,
        analytical_member_shortening_mm=0.003113245,
        axial_state=axial_state,
        deformation_state=deformation_state,
        thread_flank_state=flank_state,
        accepted_increments=increments,
    )

    failed = tuple(
        check
        for check in checks
        if not check.passed
    )

    assert tuple(
        check.name
        for check in failed
    ) == (
        "A2 final nonlinear increment parity",
    )

def _aggregate_test_check(
    *,
    name: str,
    kind: FemAcceptanceCheckKind,
    passed: bool = True,
) -> FemAcceptanceCheck:
    return FemAcceptanceCheck(
        name=name,
        kind=kind,
        passed=passed,
        measured=passed,
        expected=True,
        reason="aggregate composition test",
    )


def test_aggregate_reproduction_evaluator_combines_all_layers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hard_builders = (
        "build_preload_acceptance_checks",
        "build_thread_contact_acceptance_checks",
        "build_axial_state_acceptance_checks",
        "build_deformation_acceptance_checks",
        "build_thread_flank_acceptance_checks",
        "build_numerical_completion_acceptance_checks",
    )

    for index, builder_name in enumerate(
        hard_builders,
        start=1,
    ):
        check = _aggregate_test_check(
            name=f"hard-{index}",
            kind=FemAcceptanceCheckKind.HARD_GATE,
        )

        monkeypatch.setattr(
            acceptance_module,
            builder_name,
            lambda *args, _check=check, **kwargs: (
                _check,
            ),
        )

    parity_check = _aggregate_test_check(
        name="parity-1",
        kind=(
            FemAcceptanceCheckKind.REPRODUCTION_PARITY
        ),
    )

    monkeypatch.setattr(
        acceptance_module,
        "build_reproduction_parity_checks",
        lambda *args, **kwargs: (
            parity_check,
        ),
    )

    result = evaluate_certified_reproduction(
        oracle=object(),
        preload_decision=object(),
        thread_normal_force_n=1.0,
        analytical_member_shortening_mm=1.0,
        axial_state=object(),
        deformation_state=object(),
        thread_flank_state=object(),
        accepted_increments=(),
        return_code=0,
        stdout="Job finished",
    )

    assert result.passed
    assert len(result.checks) == 7
    assert len(result.hard_gate_checks) == 6
    assert len(result.parity_checks) == 1
    assert not result.failed_checks


def test_aggregate_reproduction_evaluator_propagates_parity_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hard_builders = (
        "build_preload_acceptance_checks",
        "build_thread_contact_acceptance_checks",
        "build_axial_state_acceptance_checks",
        "build_deformation_acceptance_checks",
        "build_thread_flank_acceptance_checks",
        "build_numerical_completion_acceptance_checks",
    )

    for index, builder_name in enumerate(
        hard_builders,
        start=1,
    ):
        passing_hard = _aggregate_test_check(
            name=f"hard-pass-{index}",
            kind=FemAcceptanceCheckKind.HARD_GATE,
        )

        monkeypatch.setattr(
            acceptance_module,
            builder_name,
            lambda *args, _check=passing_hard, **kwargs: (
                _check,
            ),
        )

    failing_parity = _aggregate_test_check(
        name="parity-fail",
        kind=(
            FemAcceptanceCheckKind.REPRODUCTION_PARITY
        ),
        passed=False,
    )

    monkeypatch.setattr(
        acceptance_module,
        "build_reproduction_parity_checks",
        lambda *args, **kwargs: (
            failing_parity,
        ),
    )

    result = evaluate_certified_reproduction(
        oracle=object(),
        preload_decision=object(),
        thread_normal_force_n=1.0,
        analytical_member_shortening_mm=1.0,
        axial_state=object(),
        deformation_state=object(),
        thread_flank_state=object(),
        accepted_increments=(),
        return_code=0,
        stdout="Job finished",
    )

    assert not result.passed

    assert tuple(
        check.name
        for check in result.failed_checks
    ) == (
        "parity-fail",
    )

def test_numerical_completion_rejects_missing_live_return_code() -> None:
    checks = build_numerical_completion_acceptance_checks(
        return_code=None,
        stdout="Job finished",
        accepted_increments=(
            _accepted_increment(),
        ),
    )

    return_check = checks[0]

    assert (
        return_check.kind
        is FemAcceptanceCheckKind.HARD_GATE
    )
    assert not return_check.passed

    assert not FemReproductionAcceptanceResult(
        checks=checks
    ).passed


def test_numerical_completion_preserves_legacy_return_code_gap_as_diagnostic() -> None:
    checks = build_numerical_completion_acceptance_checks(
        return_code=None,
        stdout="Job finished",
        accepted_increments=(
            _accepted_increment(),
        ),
        require_process_return_code=False,
    )

    return_check = checks[0]

    assert (
        return_check.kind
        is FemAcceptanceCheckKind.DIAGNOSTIC
    )
    assert return_check.passed
    assert return_check.measured is None

    result = FemReproductionAcceptanceResult(
        checks=checks
    )

    assert result.passed
    assert len(result.diagnostic_checks) == 1


def test_numerical_completion_never_ignores_observed_nonzero_return_code() -> None:
    checks = build_numerical_completion_acceptance_checks(
        return_code=1,
        stdout="Job finished",
        accepted_increments=(
            _accepted_increment(),
        ),
        require_process_return_code=False,
    )

    return_check = checks[0]

    assert (
        return_check.kind
        is FemAcceptanceCheckKind.HARD_GATE
    )
    assert not return_check.passed

    assert not FemReproductionAcceptanceResult(
        checks=checks
    ).passed

def test_thread_contact_requires_positive_native_normal_force() -> None:
    checks = build_thread_contact_acceptance_checks(
        thread_normal_force_n=15_318.240,
    )

    assert len(checks) == 1
    assert checks[0].passed
    assert (
        checks[0].kind
        is FemAcceptanceCheckKind.HARD_GATE
    )


def test_thread_contact_rejects_missing_contact_force() -> None:
    checks = build_thread_contact_acceptance_checks(
        thread_normal_force_n=0.0,
    )

    assert not checks[0].passed

    assert not FemReproductionAcceptanceResult(
        checks=checks
    ).passed
