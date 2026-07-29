"""Tests for the TRM-GEO-000001 bolt control blank."""

import math
from pathlib import Path

import pytest

from threadrom.geometry.bolt_blank import (
    build_bolt_blank,
    load_bolt_blank_definition,
    measure_bolt_blank,
)


def test_bolt_blank_configuration_loads() -> None:
    """The controlled bolt-blank definition loads correctly."""

    project_root = Path(__file__).resolve().parents[2]

    definition = load_bolt_blank_definition(
        project_root / "config" / "baseline_geometry.toml"
    )

    assert definition.geometry_id == "TRM-GEO-000001"
    assert definition.nominal_diameter_mm == pytest.approx(10.0)
    assert definition.underhead_length_mm == pytest.approx(30.0)
    assert definition.head_across_flats_mm == pytest.approx(16.0)
    assert definition.head_height_mm == pytest.approx(6.4)


def test_bolt_blank_geometry_is_dimensionally_consistent() -> None:
    """The generated bolt blank matches its analytical definition."""

    project_root = Path(__file__).resolve().parents[2]

    definition = load_bolt_blank_definition(
        project_root / "config" / "baseline_geometry.toml"
    )

    model = build_bolt_blank(definition)
    measurements = measure_bolt_blank(model)

    horizontal_lengths = sorted(
        [
            measurements.x_length_mm,
            measurements.y_length_mm,
        ]
    )

    assert measurements.solid_count == 1
    assert measurements.is_valid

    assert horizontal_lengths[0] == pytest.approx(
        definition.head_across_flats_mm,
        abs=1.0e-6,
    )

    assert horizontal_lengths[1] == pytest.approx(
        definition.head_across_flats_mm
        / math.cos(math.pi / 6.0),
        abs=1.0e-6,
    )

    assert measurements.z_min_mm == pytest.approx(
        -definition.head_height_mm,
        abs=1.0e-6,
    )

    assert measurements.z_max_mm == pytest.approx(
        definition.underhead_length_mm,
        abs=1.0e-6,
    )

    assert measurements.volume_mm3 == pytest.approx(
        definition.analytical_volume_mm3,
        rel=1.0e-6,
    )