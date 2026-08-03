"""Tests for metric-thread mechanics validation."""

import pytest

from threadrom.engineering.analytical_inputs import (
    MetricThreadInput,
)
from threadrom.engineering.metric_thread_mechanics import (
    calculate_metric_thread_mechanics,
)
from threadrom.engineering.metric_thread_validation import (
    validate_metric_thread_mechanics,
)


def test_m10_thread_passes_all_physics_checks() -> None:
    """The governed M10 thread satisfies all invariants."""

    mechanics = calculate_metric_thread_mechanics(
        MetricThreadInput(
            nominal_diameter_mm=10.0,
            pitch_mm=1.5,
        ),
        engagement_length_mm=8.0,
    )

    validation = validate_metric_thread_mechanics(mechanics)

    assert validation.method == ("deterministic_geometry_invariants_v1")

    assert validation.passed
    assert validation.failed_check_ids == ()
    assert len(validation.checks) == 8

    validation.require_valid()


def test_nonphysical_diameter_pitch_ratio_is_detected() -> None:
    """An extreme diameter-pitch combination fails validation."""

    mechanics = calculate_metric_thread_mechanics(
        MetricThreadInput(
            nominal_diameter_mm=1.0,
            pitch_mm=1.0,
        ),
        engagement_length_mm=2.0,
    )

    validation = validate_metric_thread_mechanics(mechanics)

    assert not validation.passed
    assert "diameter_order" in validation.failed_check_ids
    assert "area_order" in validation.failed_check_ids

    with pytest.raises(
        ValueError,
        match="Metric-thread mechanics validation failed",
    ):
        validation.require_valid()


def test_geometric_similitude_scales_lengths_and_areas() -> None:
    """Geometrically similar threads obey dimensional scaling."""

    base = calculate_metric_thread_mechanics(
        MetricThreadInput(
            nominal_diameter_mm=8.0,
            pitch_mm=1.25,
        ),
        engagement_length_mm=6.25,
    )

    scaled = calculate_metric_thread_mechanics(
        MetricThreadInput(
            nominal_diameter_mm=16.0,
            pitch_mm=2.5,
        ),
        engagement_length_mm=12.5,
    )

    scale = 2.0

    assert scaled.basic_pitch_diameter_mm == pytest.approx(scale * base.basic_pitch_diameter_mm)

    assert scaled.basic_external_minor_diameter_mm == pytest.approx(
        scale * base.basic_external_minor_diameter_mm
    )

    assert scaled.tensile_stress_area_mm2 == pytest.approx(scale**2 * base.tensile_stress_area_mm2)

    assert scaled.external_root_area_mm2 == pytest.approx(scale**2 * base.external_root_area_mm2)

    assert scaled.engaged_pitch_count == pytest.approx(base.engaged_pitch_count)

    assert scaled.helix_angle_at_pitch_diameter_deg == pytest.approx(
        base.helix_angle_at_pitch_diameter_deg
    )


def test_finer_pitch_increases_axial_section_areas() -> None:
    """At fixed diameter, a finer pitch retains more bolt area."""

    coarse = calculate_metric_thread_mechanics(
        MetricThreadInput(
            nominal_diameter_mm=12.0,
            pitch_mm=1.75,
        ),
        engagement_length_mm=10.5,
    )

    fine = calculate_metric_thread_mechanics(
        MetricThreadInput(
            nominal_diameter_mm=12.0,
            pitch_mm=1.25,
        ),
        engagement_length_mm=10.5,
    )

    assert fine.tensile_stress_area_mm2 > coarse.tensile_stress_area_mm2

    assert fine.external_root_area_mm2 > coarse.external_root_area_mm2

    assert fine.engaged_pitch_count > coarse.engaged_pitch_count

    assert fine.helix_angle_at_pitch_diameter_deg < coarse.helix_angle_at_pitch_diameter_deg
