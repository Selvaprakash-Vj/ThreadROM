"""Tests for analytical engaged-thread transfer stiffness."""

from dataclasses import replace
from pathlib import Path

import pytest

from threadrom.engineering.analytical_joint_loader import (
    load_analytical_joint_input,
)
from threadrom.engineering.analytical_thread_stiffness import (
    calculate_thread_transfer_stiffness,
)


def _benchmark_joint():
    """Load the governed M10 analytical benchmark."""

    project_root = Path(__file__).resolve().parents[2]

    return load_analytical_joint_input(project_root / "config" / "analytical_m10_5kn.toml")


def test_governed_m10_transfer_stiffness() -> None:
    """The benchmark resolves deterministic transfer quantities."""

    result = calculate_thread_transfer_stiffness(_benchmark_joint())

    assert result.method == ("iso_triangle_elastic_transfer_stiffness_v1")

    assert result.projection_convention == (
        "distributed_axial_stiffness_equals_helix_stiffness_times_sin_beta"
    )

    assert result.pitch_diameter_mm == pytest.approx(9.025721420742506)

    assert result.internal_minor_diameter_mm == pytest.approx(8.376202367904177)

    assert result.helix_angle_deg == pytest.approx(3.0281505696310247)

    assert result.bolt_axial_area_mm2 == pytest.approx(52.29231165845568)

    assert result.nut_axial_area_mm2 == pytest.approx(145.9577929859)

    assert result.bolt_thread_compliance_coefficient_mm2_per_n == pytest.approx(
        3.3839501615709633e-7
    )

    assert result.bolt_distributed_thread_stiffness_n_per_mm2 == pytest.approx(156109.2633558889)

    assert result.combined_distributed_thread_stiffness_n_per_mm2 == pytest.approx(
        78054.63167794445
    )

    assert result.transfer_parameter_per_mm == pytest.approx(0.09825707697284908)

    assert result.characteristic_transfer_length_mm == pytest.approx(10.177383968752961)


def test_equal_materials_have_equal_thread_compliance() -> None:
    """Equal elastic materials produce equal thread coefficients."""

    result = calculate_thread_transfer_stiffness(_benchmark_joint())

    assert result.bolt_thread_compliance_coefficient_mm2_per_n == pytest.approx(
        result.nut_thread_compliance_coefficient_mm2_per_n
    )

    assert result.bolt_distributed_thread_stiffness_n_per_mm2 == pytest.approx(
        result.nut_distributed_thread_stiffness_n_per_mm2
    )


def test_combined_thread_stiffness_is_series_equivalent() -> None:
    """Bolt and nut thread deformation combine in series."""

    result = calculate_thread_transfer_stiffness(_benchmark_joint())

    expected = 1.0 / (
        1.0 / result.bolt_distributed_thread_stiffness_n_per_mm2
        + 1.0 / result.nut_distributed_thread_stiffness_n_per_mm2
    )

    assert result.combined_distributed_thread_stiffness_n_per_mm2 == pytest.approx(expected)


def test_transfer_parameter_satisfies_compatibility_identity() -> None:
    """The transfer parameter follows axial/thread compatibility."""

    result = calculate_thread_transfer_stiffness(_benchmark_joint())

    expected_squared = (
        result.bolt_axial_compliance_per_force_inv_n + result.nut_axial_compliance_per_force_inv_n
    ) * result.combined_distributed_thread_stiffness_n_per_mm2

    assert result.transfer_parameter_per_mm**2 == pytest.approx(expected_squared)

    assert result.characteristic_transfer_length_mm == pytest.approx(
        1.0 / result.transfer_parameter_per_mm
    )


def test_nut_area_uses_internal_thread_minor_diameter() -> None:
    """Nut-body area is not based on the larger bearing bore."""

    result = calculate_thread_transfer_stiffness(_benchmark_joint())

    bearing_bore_diameter_mm = _benchmark_joint().nut.bearing_inner_diameter_mm

    assert result.internal_minor_diameter_mm < bearing_bore_diameter_mm

    assert result.nut_axial_area_mm2 > (106.02875205865551)


def test_softer_nut_increases_nut_thread_compliance() -> None:
    """Reducing nut modulus softens its thread contribution."""

    joint = _benchmark_joint()

    modified_materials = tuple(
        replace(
            material,
            youngs_modulus_mpa=105000.0,
        )
        if material.material_id == joint.nut.material_id
        else material
        for material in joint.materials
    )

    softened = calculate_thread_transfer_stiffness(
        replace(
            joint,
            materials=modified_materials,
        )
    )

    baseline = calculate_thread_transfer_stiffness(joint)

    assert (
        softened.nut_thread_compliance_coefficient_mm2_per_n
        > baseline.nut_thread_compliance_coefficient_mm2_per_n
    )

    assert (
        softened.nut_distributed_thread_stiffness_n_per_mm2
        < baseline.nut_distributed_thread_stiffness_n_per_mm2
    )

    assert (
        softened.combined_distributed_thread_stiffness_n_per_mm2
        < baseline.combined_distributed_thread_stiffness_n_per_mm2
    )
