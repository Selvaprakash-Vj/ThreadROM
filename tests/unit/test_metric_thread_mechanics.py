"""Tests for parametric metric-thread mechanics."""

import math

import pytest

from threadrom.engineering.analytical_inputs import (
    MetricThreadInput,
)
from threadrom.engineering.metric_thread_mechanics import (
    calculate_metric_thread_mechanics,
)


def test_m10_15_thread_mechanics_match_reference() -> None:
    """M10 x 1.5 produces the governed mechanics-ready values."""

    result = calculate_metric_thread_mechanics(
        MetricThreadInput(
            nominal_diameter_mm=10.0,
            pitch_mm=1.5,
        ),
        engagement_length_mm=8.0,
    )

    assert result.method == ("iso_metric_basic_profile_60_deg")

    assert result.fundamental_triangle_height_mm == pytest.approx(1.2990381057)

    assert result.basic_pitch_diameter_mm == pytest.approx(9.0257214207)

    assert result.basic_internal_minor_diameter_mm == pytest.approx(8.3762023679)

    assert result.basic_external_minor_diameter_mm == pytest.approx(8.1596960170)

    assert result.nominal_area_mm2 == pytest.approx(78.5398163397)

    assert result.pitch_diameter_area_mm2 == pytest.approx(63.9813988669)

    assert result.tensile_stress_area_mm2 == pytest.approx(57.9895969018)

    assert result.external_root_area_mm2 == pytest.approx(52.2923116585)

    assert result.external_thread_radial_depth_mm == pytest.approx(0.9201519915)

    assert result.internal_thread_radial_depth_mm == pytest.approx(0.8118988160)

    assert result.helix_angle_at_pitch_diameter_deg == pytest.approx(3.0281505696)

    assert result.engaged_pitch_count == pytest.approx(8.0 / 1.5)

    assert result.engaged_lead_turn_count == pytest.approx(8.0 / 1.5)


def test_multistart_thread_uses_lead_for_helix_angle() -> None:
    """A multistart thread derives lead independently of pitch."""

    single_start = calculate_metric_thread_mechanics(
        MetricThreadInput(
            nominal_diameter_mm=12.0,
            pitch_mm=1.75,
            starts=1,
        ),
        engagement_length_mm=10.5,
    )

    double_start = calculate_metric_thread_mechanics(
        MetricThreadInput(
            nominal_diameter_mm=12.0,
            pitch_mm=1.75,
            starts=2,
        ),
        engagement_length_mm=10.5,
    )

    assert single_start.lead_mm == pytest.approx(1.75)
    assert double_start.lead_mm == pytest.approx(3.5)

    assert double_start.engaged_pitch_count == pytest.approx(single_start.engaged_pitch_count)

    assert double_start.engaged_lead_turn_count == pytest.approx(
        single_start.engaged_lead_turn_count / 2.0
    )

    assert (
        double_start.helix_angle_at_pitch_diameter_deg
        > single_start.helix_angle_at_pitch_diameter_deg
    )


def test_thread_area_ratios_are_dimensionless_and_bounded() -> None:
    """Derived area ratios remain physically ordered."""

    result = calculate_metric_thread_mechanics(
        MetricThreadInput(
            nominal_diameter_mm=8.0,
            pitch_mm=1.25,
        ),
        engagement_length_mm=6.5,
    )

    assert 0.0 < result.root_to_nominal_area_ratio < 1.0
    assert 0.0 < result.tensile_to_nominal_area_ratio < 1.0

    assert result.external_root_area_mm2 < result.tensile_stress_area_mm2 < result.nominal_area_mm2

    assert math.isfinite(result.helix_angle_at_pitch_diameter_deg)


def test_nonpositive_engagement_is_rejected() -> None:
    """Thread mechanics requires positive engagement."""

    with pytest.raises(
        ValueError,
        match="engagement length must be positive",
    ):
        calculate_metric_thread_mechanics(
            MetricThreadInput(
                nominal_diameter_mm=10.0,
                pitch_mm=1.5,
            ),
            engagement_length_mm=0.0,
        )


def test_non_iso_included_angle_is_explicitly_unsupported() -> None:
    """A 60-degree ISO formula is not silently used for other forms."""

    with pytest.raises(
        NotImplementedError,
        match="only a 60-degree included thread angle",
    ):
        calculate_metric_thread_mechanics(
            MetricThreadInput(
                nominal_diameter_mm=10.0,
                pitch_mm=1.5,
                included_angle_deg=55.0,
            ),
            engagement_length_mm=8.0,
        )
