"""Tests for the annular compression-frustum kernel."""

import math

import pytest

from threadrom.engineering.analytical_compression_cone import (
    calculate_annular_frustum_compliance,
)


def test_uncapped_m10_frustum_matches_closed_form() -> None:
    """An uncapped M10 frustum matches the reference equation."""

    result = calculate_annular_frustum_compliance(
        axial_length_mm=10.0,
        youngs_modulus_mpa=210000.0,
        clearance_hole_diameter_mm=11.0,
        bearing_diameter_mm=16.0,
        member_outer_diameter_mm=30.0,
        half_angle_deg=30.0,
    )

    assert result.method == ("closed_form_annular_frustum_with_outer_cap")

    assert result.unconstrained_end_diameter_mm == pytest.approx(27.5470053838)

    assert result.effective_end_diameter_mm == pytest.approx(27.5470053838)

    assert result.frustum_length_mm == pytest.approx(10.0)

    assert result.cylindrical_length_mm == pytest.approx(0.0)

    assert result.compliance_mm_per_n == pytest.approx(2.0065643307363e-7)

    assert result.axial_stiffness_n_per_mm == pytest.approx(4983642.8599977)

    assert result.equivalent_area_mm2 == pytest.approx(237.3163266666)


def test_outer_diameter_cap_adds_cylindrical_region() -> None:
    """A long cone becomes cylindrical after reaching member OD."""

    result = calculate_annular_frustum_compliance(
        axial_length_mm=20.0,
        youngs_modulus_mpa=210000.0,
        clearance_hole_diameter_mm=11.0,
        bearing_diameter_mm=16.0,
        member_outer_diameter_mm=30.0,
        half_angle_deg=30.0,
    )

    expected_frustum_length = (30.0 - 16.0) / (2.0 * math.tan(math.radians(30.0)))

    assert result.frustum_length_mm == pytest.approx(expected_frustum_length)

    assert result.cylindrical_length_mm == pytest.approx(20.0 - expected_frustum_length)

    assert result.effective_end_diameter_mm == pytest.approx(30.0)

    assert result.compliance_mm_per_n == pytest.approx(2.8022135311823e-7)

    assert result.axial_stiffness_n_per_mm == pytest.approx(3568607.4200708)


def test_bearing_larger_than_member_is_cylinder_limited() -> None:
    """Bearing overhang cannot create area beyond the member OD."""

    result = calculate_annular_frustum_compliance(
        axial_length_mm=10.0,
        youngs_modulus_mpa=210000.0,
        clearance_hole_diameter_mm=11.0,
        bearing_diameter_mm=35.0,
        member_outer_diameter_mm=30.0,
        half_angle_deg=30.0,
    )

    expected_area = math.pi / 4.0 * (30.0**2 - 11.0**2)

    expected_compliance = 10.0 / (210000.0 * expected_area)

    assert result.frustum_length_mm == pytest.approx(0.0)

    assert result.cylindrical_length_mm == pytest.approx(10.0)

    assert result.minimum_area_mm2 == pytest.approx(expected_area)

    assert result.maximum_area_mm2 == pytest.approx(expected_area)

    assert result.compliance_mm_per_n == pytest.approx(expected_compliance)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        (
            "axial_length_mm",
            0.0,
            "axial length",
        ),
        (
            "youngs_modulus_mpa",
            0.0,
            "Young's modulus",
        ),
        (
            "bearing_diameter_mm",
            11.0,
            "Bearing diameter",
        ),
        (
            "member_outer_diameter_mm",
            11.0,
            "Member outer diameter",
        ),
        (
            "half_angle_deg",
            90.0,
            "half-angle",
        ),
    ],
)
def test_invalid_frustum_inputs_are_rejected(
    field: str,
    value: float,
    message: str,
) -> None:
    """Nonphysical frustum definitions are rejected."""

    inputs = {
        "axial_length_mm": 10.0,
        "youngs_modulus_mpa": 210000.0,
        "clearance_hole_diameter_mm": 11.0,
        "bearing_diameter_mm": 16.0,
        "member_outer_diameter_mm": 30.0,
        "half_angle_deg": 30.0,
    }

    inputs[field] = value

    with pytest.raises(
        ValueError,
        match=message,
    ):
        calculate_annular_frustum_compliance(**inputs)
