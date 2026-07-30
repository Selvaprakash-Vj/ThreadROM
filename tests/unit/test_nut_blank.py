"""Tests for the parametric hexagonal nut blank."""

import math
from pathlib import Path

import pytest

from threadrom.geometry.nut_blank import (
    NutBlankDefinition,
    build_nut_blank,
    load_nut_blank_definition,
    measure_nut_blank,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_baseline_nut_blank_definition() -> None:
    """The governed M10 nut blank loads consistently."""

    definition = load_nut_blank_definition(
        PROJECT_ROOT / "config" / "nut_geometry.toml",
        PROJECT_ROOT / "config" / "baseline_fastener.toml",
        PROJECT_ROOT / "config" / "baseline_assembly.toml",
    )

    assert definition.geometry_id == "TRM-GEO-000001"
    assert definition.assembly_id == "TRM-ASM-000001"
    assert definition.nominal_diameter_mm == pytest.approx(10.0)
    assert definition.pitch_mm == pytest.approx(1.5)
    assert definition.across_flats_mm == pytest.approx(16.0)
    assert definition.thickness_mm == pytest.approx(8.0)
    assert definition.bore_diameter_mm == pytest.approx(
        8.3762023679,
    )
    assert definition.across_corners_mm == pytest.approx(
        18.4752086141,
    )


def test_baseline_nut_blank_is_valid() -> None:
    """The generated baseline blank is one valid solid."""

    definition = load_nut_blank_definition(
        PROJECT_ROOT / "config" / "nut_geometry.toml",
        PROJECT_ROOT / "config" / "baseline_fastener.toml",
        PROJECT_ROOT / "config" / "baseline_assembly.toml",
    )

    nut_blank = build_nut_blank(definition)
    measurements = measure_nut_blank(nut_blank)

    planar_lengths = sorted(
        (
            measurements.x_length_mm,
            measurements.y_length_mm,
        )
    )

    assert measurements.solid_count == 1
    assert measurements.is_valid
    assert measurements.volume_mm3 == pytest.approx(
        definition.analytical_volume_mm3,
        rel=1.0e-9,
    )
    assert planar_lengths[0] == pytest.approx(
        definition.across_flats_mm,
    )
    assert planar_lengths[1] == pytest.approx(
        definition.across_corners_mm,
    )
    assert measurements.z_min_mm == pytest.approx(0.0)
    assert measurements.z_max_mm == pytest.approx(
        definition.thickness_mm,
    )


def test_nut_blank_builder_is_not_m10_specific() -> None:
    """The CAD builder accepts another controlled nut size."""

    definition = NutBlankDefinition(
        geometry_id="TEST-GEO",
        assembly_id="TEST-ASM",
        component_name="test_hex_nut",
        nominal_diameter_mm=12.0,
        pitch_mm=1.75,
        across_flats_mm=18.0,
        thickness_mm=10.0,
        bore_diameter_mm=10.106,
        bore_basis="basic_internal_minor_diameter",
        chamfer_included=False,
    )

    nut_blank = build_nut_blank(definition)
    measurements = measure_nut_blank(nut_blank)

    expected_across_corners = 18.0 / math.cos(
        math.radians(30.0)
    )

    assert measurements.solid_count == 1
    assert measurements.is_valid
    assert max(
        measurements.x_length_mm,
        measurements.y_length_mm,
    ) == pytest.approx(expected_across_corners)
    assert measurements.z_max_mm == pytest.approx(10.0)
