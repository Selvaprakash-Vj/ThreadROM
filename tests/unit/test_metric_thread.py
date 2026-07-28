"""Tests for ISO metric-thread reference calculations."""

import pytest

from threadrom.engineering.metric_thread import (
    calculate_metric_thread_basic_dimensions,
)


def test_m10_coarse_thread_basic_dimensions() -> None:
    """M10 × 1.5 produces the expected analytical dimensions."""

    result = calculate_metric_thread_basic_dimensions(
        nominal_diameter_mm=10.0,
        pitch_mm=1.5,
    )

    assert result.fundamental_triangle_height_mm == pytest.approx(
        1.2990381057,
    )

    assert result.basic_pitch_diameter_mm == pytest.approx(
        9.0257214207,
    )

    assert result.basic_internal_minor_diameter_mm == pytest.approx(
        8.3762023679,
    )

    assert result.basic_external_minor_diameter_mm == pytest.approx(
        8.1596960170,
    )

    assert result.tensile_stress_area_mm2 == pytest.approx(
        57.9895969018,
    )


@pytest.mark.parametrize(
    ("diameter", "pitch"),
    [
        (0.0, 1.5),
        (-10.0, 1.5),
        (10.0, 0.0),
        (10.0, -1.5),
    ],
)
def test_invalid_thread_dimensions_are_rejected(
    diameter: float,
    pitch: float,
) -> None:
    """Non-positive thread inputs must be rejected."""

    with pytest.raises(ValueError):
        calculate_metric_thread_basic_dimensions(
            nominal_diameter_mm=diameter,
            pitch_mm=pitch,
        )