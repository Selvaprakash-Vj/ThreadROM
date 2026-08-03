"""Tests for parametric analytical member mechanics."""

import math
from dataclasses import replace
from pathlib import Path

import pytest

from threadrom.engineering.analytical_joint_input import (
    MemberCompressionMethod,
)
from threadrom.engineering.analytical_joint_loader import (
    load_analytical_joint_input,
)
from threadrom.engineering.analytical_member_mechanics import (
    calculate_analytical_member_mechanics,
)


def _benchmark_joint():
    """Load the governed M10 analytical joint."""

    project_root = Path(__file__).resolve().parents[2]

    return load_analytical_joint_input(project_root / "config" / "analytical_m10_5kn.toml")


def test_m10_uniform_annular_member_reference() -> None:
    """The governed benchmark retains the annular model."""

    result = calculate_analytical_member_mechanics(_benchmark_joint())

    expected_area = math.pi / 4.0 * (30.0**2 - 11.0**2)

    expected_bearing_area = math.pi / 4.0 * (16.0**2 - 11.0**2)

    assert result.method == ("uniform_annular_cylinder")

    assert result.compression_cone_half_angle_deg is None
    assert len(result.layers) == 2

    assert all(layer.compression_model == "uniform_annular_cylinder" for layer in result.layers)

    assert result.total_thickness_mm == pytest.approx(20.0)

    assert result.layers[0].compression_area_mm2 == pytest.approx(expected_area)

    assert result.minimum_compression_area_mm2 == pytest.approx(611.8251692866)

    assert result.axial_stiffness_n_per_mm == pytest.approx(6424164.2775094)

    assert result.total_shortening_mm == pytest.approx(0.000778311354444)

    assert result.total_strain_energy_n_mm == pytest.approx(1.9457783861103)

    assert result.maximum_compressive_stress_mpa == pytest.approx(8.1722692217)

    assert result.head_bearing_area_mm2 == pytest.approx(expected_bearing_area)

    assert result.nut_bearing_area_mm2 == pytest.approx(expected_bearing_area)

    assert result.head_mean_bearing_pressure_mpa == pytest.approx(47.1570201754)

    assert result.nut_mean_bearing_pressure_mpa == pytest.approx(47.1570201754)


def test_layer_compliances_are_added_in_series() -> None:
    """Different annular layers contribute series compliance."""

    joint = _benchmark_joint()

    modified_layers = (
        joint.member_layers[0],
        replace(
            joint.member_layers[1],
            outer_diameter_mm=20.0,
        ),
    )

    result = calculate_analytical_member_mechanics(
        replace(
            joint,
            member_layers=modified_layers,
        )
    )

    first_area = math.pi / 4.0 * (30.0**2 - 11.0**2)

    second_area = math.pi / 4.0 * (20.0**2 - 11.0**2)

    expected_compliance = 10.0 / (210000.0 * first_area) + 10.0 / (210000.0 * second_area)

    assert result.total_compliance_mm_per_n == pytest.approx(expected_compliance)

    assert result.axial_stiffness_n_per_mm == pytest.approx(1.0 / expected_compliance)

    assert result.layers[1].compressive_stress_mpa > result.layers[0].compressive_stress_mpa

    assert result.minimum_compression_area_mm2 == pytest.approx(second_area)


def test_zero_preload_retains_stiffness_without_response() -> None:
    """Zero preload produces no stress, shortening or energy."""

    joint = _benchmark_joint()

    result = calculate_analytical_member_mechanics(
        replace(
            joint,
            loading=replace(
                joint.loading,
                preload_n=0.0,
            ),
        )
    )

    assert result.axial_stiffness_n_per_mm > 0.0
    assert result.total_shortening_mm == pytest.approx(0.0)
    assert result.total_strain_energy_n_mm == pytest.approx(0.0)
    assert result.maximum_compressive_stress_mpa == pytest.approx(0.0)
    assert result.head_mean_bearing_pressure_mpa == pytest.approx(0.0)
    assert result.nut_mean_bearing_pressure_mpa == pytest.approx(0.0)


def test_m10_compression_cone_is_available_through_main_api() -> None:
    """The main API resolves the verified opposed-cone model."""

    joint = _benchmark_joint()

    cone_joint = replace(
        joint,
        methods=replace(
            joint.methods,
            member_compression=(MemberCompressionMethod.COMPRESSION_CONE),
        ),
    )

    result = calculate_analytical_member_mechanics(cone_joint)

    assert result.method == "compression_cone"

    assert result.compression_cone_half_angle_deg == pytest.approx(30.0)

    assert len(result.layers) == 2

    assert all(layer.compression_model == "compression_cone_slice" for layer in result.layers)

    assert [layer.cone_side for layer in result.layers] == [
        "head_side",
        "nut_side",
    ]

    assert result.total_compliance_mm_per_n == pytest.approx(4.0131286614726e-7)

    assert result.axial_stiffness_n_per_mm == pytest.approx(2491821.4299988)

    assert result.total_shortening_mm == pytest.approx(0.0020065643307363)

    assert result.total_strain_energy_n_mm == pytest.approx(5.0164108268408)

    assert result.maximum_compressive_stress_mpa == pytest.approx(47.1570201754)

    assert result.layers[0].end_compression_area_mm2 > result.layers[0].compression_area_mm2

    assert result.layers[0].equivalent_compression_area_mm2 > result.layers[0].compression_area_mm2


def test_cone_and_annular_methods_remain_distinct() -> None:
    """The selected member methods do not collapse to one model."""

    joint = _benchmark_joint()

    uniform = calculate_analytical_member_mechanics(joint)

    cone = calculate_analytical_member_mechanics(
        replace(
            joint,
            methods=replace(
                joint.methods,
                member_compression=(MemberCompressionMethod.COMPRESSION_CONE),
            ),
        )
    )

    assert cone.method != uniform.method

    assert cone.axial_stiffness_n_per_mm < uniform.axial_stiffness_n_per_mm

    assert cone.total_shortening_mm > uniform.total_shortening_mm
