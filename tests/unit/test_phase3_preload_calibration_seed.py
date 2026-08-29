"""Tests for physics-derived FEM preload calibration seed."""

from __future__ import annotations

from dataclasses import replace

import pytest

from threadrom.case.reference_cases import (
    phase2_certification_case,
)
from threadrom.case.resolver import resolve_case
from threadrom.factory.preload_calibration_seed import (
    derive_analytical_thermal_preload_seed,
)


def test_reference_case_seed_is_finite_contraction() -> None:
    resolved = resolve_case(
        phase2_certification_case()
    )

    seed = derive_analytical_thermal_preload_seed(
        resolved
    )

    assert seed.target_force_n == 20_000.0
    assert seed.bolt_compliance_mm_per_n > 0.0
    assert seed.member_compliance_mm_per_n > 0.0
    assert seed.total_compliance_mm_per_n == pytest.approx(
        seed.bolt_compliance_mm_per_n
        + seed.member_compliance_mm_per_n
    )
    assert seed.effective_bolt_length_mm > 0.0
    assert seed.expansion_coefficient_per_c > 0.0
    assert seed.predicted_delta_temperature_c < 0.0


def test_seed_satisfies_analytical_compatibility_identity() -> None:
    resolved = resolve_case(
        phase2_certification_case()
    )

    seed = derive_analytical_thermal_preload_seed(
        resolved
    )

    thermal_free_contraction_mm = (
        seed.expansion_coefficient_per_c
        * abs(seed.predicted_delta_temperature_c)
        * seed.effective_bolt_length_mm
    )

    joint_elastic_deformation_mm = (
        seed.target_force_n
        * seed.total_compliance_mm_per_n
    )

    assert thermal_free_contraction_mm == pytest.approx(
        joint_elastic_deformation_mm,
        rel=1.0e-12,
    )


def test_seed_scales_with_target_preload_for_same_case_mechanics() -> None:
    baseline = phase2_certification_case()

    lower_preload = replace(
        baseline,
        loading=replace(
            baseline.loading,
            target_preload_n=10_000.0,
        ),
    )

    baseline_seed = (
        derive_analytical_thermal_preload_seed(
            resolve_case(baseline)
        )
    )

    lower_seed = (
        derive_analytical_thermal_preload_seed(
            resolve_case(lower_preload)
        )
    )

    assert lower_seed.predicted_delta_temperature_c == pytest.approx(
        0.5
        * baseline_seed.predicted_delta_temperature_c,
        rel=1.0e-12,
    )


def test_seed_is_deterministic() -> None:
    resolved = resolve_case(
        phase2_certification_case()
    )

    first = derive_analytical_thermal_preload_seed(
        resolved
    )
    second = derive_analytical_thermal_preload_seed(
        resolved
    )

    assert first == second
