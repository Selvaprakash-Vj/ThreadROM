"""Parametric behaviour tests for analytical member mechanics."""

import math
from dataclasses import replace
from pathlib import Path

import pytest

from threadrom.engineering.analytical_joint_loader import (
    load_analytical_joint_input,
)
from threadrom.engineering.analytical_member_mechanics import (
    calculate_analytical_member_mechanics,
)


def _benchmark_joint():
    """Load the governed analytical benchmark."""

    project_root = Path(__file__).resolve().parents[2]

    return load_analytical_joint_input(project_root / "config" / "analytical_m10_5kn.toml")


def test_preload_scaling_obeys_linear_elastic_response() -> None:
    """Stress and shortening scale linearly with preload."""

    joint = _benchmark_joint()

    base = calculate_analytical_member_mechanics(joint)

    doubled = calculate_analytical_member_mechanics(
        replace(
            joint,
            loading=replace(
                joint.loading,
                preload_n=2.0 * joint.loading.preload_n,
            ),
        )
    )

    assert doubled.total_compliance_mm_per_n == pytest.approx(base.total_compliance_mm_per_n)

    assert doubled.axial_stiffness_n_per_mm == pytest.approx(base.axial_stiffness_n_per_mm)

    assert doubled.total_shortening_mm == pytest.approx(2.0 * base.total_shortening_mm)

    assert doubled.maximum_compressive_stress_mpa == pytest.approx(
        2.0 * base.maximum_compressive_stress_mpa
    )

    assert doubled.head_mean_bearing_pressure_mpa == pytest.approx(
        2.0 * base.head_mean_bearing_pressure_mpa
    )

    assert doubled.nut_mean_bearing_pressure_mpa == pytest.approx(
        2.0 * base.nut_mean_bearing_pressure_mpa
    )

    assert doubled.total_strain_energy_n_mm == pytest.approx(4.0 * base.total_strain_energy_n_mm)


def test_lower_modulus_layer_increases_series_compliance() -> None:
    """A softer member layer reduces total stack stiffness."""

    joint = _benchmark_joint()

    base = calculate_analytical_member_mechanics(joint)

    original_material = joint.material_by_id("member_steel")

    soft_material = replace(
        original_material,
        material_id="soft_member",
        youngs_modulus_mpa=(0.5 * original_material.youngs_modulus_mpa),
    )

    modified_layers = (
        joint.member_layers[0],
        replace(
            joint.member_layers[1],
            material_id="soft_member",
        ),
    )

    modified_joint = replace(
        joint,
        materials=(
            *joint.materials,
            soft_material,
        ),
        member_layers=modified_layers,
    )

    result = calculate_analytical_member_mechanics(modified_joint)

    first_compliance = base.layers[0].compliance_mm_per_n

    second_compliance = 2.0 * base.layers[1].compliance_mm_per_n

    expected_total_compliance = first_compliance + second_compliance

    assert result.total_compliance_mm_per_n == pytest.approx(expected_total_compliance)

    assert result.axial_stiffness_n_per_mm == pytest.approx(1.0 / expected_total_compliance)

    assert result.axial_stiffness_n_per_mm < base.axial_stiffness_n_per_mm

    assert result.layers[1].shortening_mm > result.layers[0].shortening_mm


def test_larger_member_outer_diameter_increases_stiffness() -> None:
    """Increasing annular area stiffens the member stack."""

    joint = _benchmark_joint()

    base = calculate_analytical_member_mechanics(joint)

    enlarged_layers = tuple(
        replace(
            layer,
            outer_diameter_mm=40.0,
        )
        for layer in joint.member_layers
    )

    enlarged = calculate_analytical_member_mechanics(
        replace(
            joint,
            member_layers=enlarged_layers,
        )
    )

    expected_area = math.pi / 4.0 * (40.0**2 - 11.0**2)

    assert enlarged.minimum_compression_area_mm2 == pytest.approx(expected_area)

    assert enlarged.axial_stiffness_n_per_mm > base.axial_stiffness_n_per_mm

    assert enlarged.total_shortening_mm < base.total_shortening_mm

    assert enlarged.maximum_compressive_stress_mpa < base.maximum_compressive_stress_mpa


def test_bearing_geometry_changes_pressure_not_stack_stiffness() -> None:
    """Bearing-ring area is independent of annular stack stiffness."""

    joint = _benchmark_joint()

    base = calculate_analytical_member_mechanics(joint)

    modified_bolt = replace(
        joint.bolt,
        head_bearing_outer_diameter_mm=20.0,
    )

    modified_nut = replace(
        joint.nut,
        bearing_outer_diameter_mm=18.0,
    )

    modified = calculate_analytical_member_mechanics(
        replace(
            joint,
            bolt=modified_bolt,
            nut=modified_nut,
        )
    )

    expected_head_area = math.pi / 4.0 * (20.0**2 - 11.0**2)

    expected_nut_area = math.pi / 4.0 * (18.0**2 - 11.0**2)

    assert modified.head_bearing_area_mm2 == pytest.approx(expected_head_area)

    assert modified.nut_bearing_area_mm2 == pytest.approx(expected_nut_area)

    assert modified.axial_stiffness_n_per_mm == pytest.approx(base.axial_stiffness_n_per_mm)

    assert modified.total_shortening_mm == pytest.approx(base.total_shortening_mm)

    assert modified.head_mean_bearing_pressure_mpa < base.head_mean_bearing_pressure_mpa

    assert modified.nut_mean_bearing_pressure_mpa < base.nut_mean_bearing_pressure_mpa
