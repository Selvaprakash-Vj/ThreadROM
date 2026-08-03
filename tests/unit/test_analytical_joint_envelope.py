"""Tests for analytical joint preload and cyclic envelopes."""

from dataclasses import replace
from pathlib import Path

import pytest

from threadrom.engineering.analytical_joint_envelope import (
    ExternalLoadCase,
    PreloadCase,
    calculate_analytical_joint_envelope,
)
from threadrom.engineering.analytical_joint_loader import (
    load_analytical_joint_input,
)


def _benchmark_joint():
    """Load the governed M10 analytical benchmark."""

    project_root = Path(__file__).resolve().parents[2]

    return load_analytical_joint_input(project_root / "config" / "analytical_m10_5kn.toml")


def test_zero_scatter_still_exposes_three_preload_cases() -> None:
    """Minimum, nominal, and maximum cases remain explicit."""

    envelope = calculate_analytical_joint_envelope(_benchmark_joint())

    assert envelope.minimum_preload_n == pytest.approx(5000.0)

    assert envelope.nominal_preload_n == pytest.approx(5000.0)

    assert envelope.maximum_preload_n == pytest.approx(5000.0)

    assert len(envelope.points) == 3
    assert envelope.cyclic_responses == ()

    assert [point.preload_case for point in envelope.points] == [
        PreloadCase.MINIMUM,
        PreloadCase.NOMINAL,
        PreloadCase.MAXIMUM,
    ]

    assert all(point.external_load_case is ExternalLoadCase.STATIC for point in envelope.points)


def test_preload_scatter_creates_symmetric_bounds() -> None:
    """Scatter is applied symmetrically around nominal preload."""

    joint = _benchmark_joint()

    scattered = replace(
        joint,
        loading=replace(
            joint.loading,
            preload_scatter_fraction=0.2,
            external_axial_load_n=1000.0,
        ),
    )

    envelope = calculate_analytical_joint_envelope(scattered)

    assert envelope.minimum_preload_n == pytest.approx(4000.0)

    assert envelope.nominal_preload_n == pytest.approx(5000.0)

    assert envelope.maximum_preload_n == pytest.approx(6000.0)

    minimum_state = envelope.points[0].state
    nominal_state = envelope.points[1].state
    maximum_state = envelope.points[2].state

    assert (
        minimum_state.separation_load_n
        < nominal_state.separation_load_n
        < maximum_state.separation_load_n
    )

    assert envelope.minimum_separation_margin_n == pytest.approx(minimum_state.separation_margin_n)


def test_cyclic_inputs_create_full_case_grid() -> None:
    """Three preload cases are crossed with three load cases."""

    joint = _benchmark_joint()

    cyclic_joint = replace(
        joint,
        loading=replace(
            joint.loading,
            external_axial_load_n=2000.0,
            cyclic_minimum_axial_load_n=1000.0,
            cyclic_maximum_axial_load_n=6000.0,
            preload_scatter_fraction=0.1,
        ),
    )

    envelope = calculate_analytical_joint_envelope(cyclic_joint)

    assert len(envelope.points) == 9
    assert len(envelope.cyclic_responses) == 3

    assert len({point.point_id for point in envelope.points}) == 9

    assert [point.external_load_case for point in envelope.points[:3]] == [
        ExternalLoadCase.STATIC,
        ExternalLoadCase.CYCLIC_MINIMUM,
        ExternalLoadCase.CYCLIC_MAXIMUM,
    ]


def test_cyclic_force_statistics_are_consistent() -> None:
    """Mean, amplitude, and range are algebraically consistent."""

    joint = _benchmark_joint()

    cyclic_joint = replace(
        joint,
        loading=replace(
            joint.loading,
            cyclic_minimum_axial_load_n=1000.0,
            cyclic_maximum_axial_load_n=3000.0,
        ),
    )

    response = calculate_analytical_joint_envelope(cyclic_joint).cyclic_responses[1]

    assert response.preload_case is PreloadCase.NOMINAL

    assert response.bolt_force_range_n == pytest.approx(
        response.bolt_force_maximum_n - response.bolt_force_minimum_n
    )

    assert response.bolt_force_amplitude_n == pytest.approx(0.5 * response.bolt_force_range_n)

    assert response.bolt_force_mean_n == pytest.approx(
        0.5 * (response.bolt_force_maximum_n + response.bolt_force_minimum_n)
    )

    assert response.member_compression_maximum_n > response.member_compression_minimum_n

    assert not response.separated_during_cycle


def test_cycle_crossing_separation_is_reported() -> None:
    """A high cyclic load records clamp loss and opening."""

    joint = _benchmark_joint()

    cyclic_joint = replace(
        joint,
        loading=replace(
            joint.loading,
            cyclic_minimum_axial_load_n=1000.0,
            cyclic_maximum_axial_load_n=6000.0,
        ),
    )

    envelope = calculate_analytical_joint_envelope(cyclic_joint)

    nominal_response = envelope.cyclic_responses[1]

    assert nominal_response.separated_during_cycle
    assert nominal_response.maximum_joint_opening_mm > 0.0

    assert envelope.any_separation
    assert envelope.lowest_member_compression_force_n == pytest.approx(0.0)

    assert envelope.minimum_separation_margin_n < 0.0


def test_worst_opening_occurs_at_lowest_preload() -> None:
    """The minimum-preload case governs post-separation opening."""

    joint = _benchmark_joint()

    modified = replace(
        joint,
        loading=replace(
            joint.loading,
            external_axial_load_n=6000.0,
            preload_scatter_fraction=0.1,
        ),
    )

    envelope = calculate_analytical_joint_envelope(modified)

    minimum_state = envelope.points[0].state
    nominal_state = envelope.points[1].state
    maximum_state = envelope.points[2].state

    assert (
        minimum_state.joint_opening_mm
        > nominal_state.joint_opening_mm
        > maximum_state.joint_opening_mm
    )

    assert envelope.maximum_joint_opening_mm == pytest.approx(minimum_state.joint_opening_mm)


def test_highest_bolt_force_is_derived_from_all_points() -> None:
    """The envelope maximum equals the greatest evaluated state."""

    joint = _benchmark_joint()

    modified = replace(
        joint,
        loading=replace(
            joint.loading,
            external_axial_load_n=2000.0,
            cyclic_minimum_axial_load_n=500.0,
            cyclic_maximum_axial_load_n=7000.0,
            preload_scatter_fraction=0.15,
        ),
    )

    envelope = calculate_analytical_joint_envelope(modified)

    assert envelope.highest_bolt_force_n == pytest.approx(
        max(point.state.bolt_force_n for point in envelope.points)
    )
