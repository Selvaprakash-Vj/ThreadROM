"""Tests for the complete parametric bolt."""

from pathlib import Path

import pytest

from threadrom.geometry.complete_bolt import (
    build_complete_bolt,
    expected_hex_across_corners_mm,
    export_and_reimport_step,
    measure_complete_bolt,
)
from threadrom.geometry.geometry_quality import (
    load_geometry_quality_policy,
)
from threadrom.geometry.threaded_shank import (
    load_threaded_shank_definitions,
)


def test_geometry_quality_policy_loads() -> None:
    """The central geometry quality policy is valid."""

    project_root = Path(__file__).resolve().parents[2]

    policy = load_geometry_quality_policy(project_root / "config" / "geometry_quality.toml")

    assert policy.policy_id == "TRM-GQP-000001"
    assert policy.boolean_tolerance_mm > 0.0
    assert policy.thread_boolean_overlap_mm == pytest.approx(0.03)
    assert policy.cad_envelope_tolerance_mm > 0.0
    assert 0.0 < policy.fusion_bridge_radius_fraction < 1.0


def test_complete_parametric_bolt_is_valid() -> None:
    """The head and threaded shank form one valid complete bolt."""

    project_root = Path(__file__).resolve().parents[2]

    blank_definition, thread_definition = load_threaded_shank_definitions(project_root)

    policy = load_geometry_quality_policy(project_root / "config" / "geometry_quality.toml")

    build = build_complete_bolt(
        blank_definition,
        thread_definition,
        policy,
    )

    measurements = measure_complete_bolt(build)

    assert measurements.solid_count == 1
    assert measurements.is_valid
    assert measurements.union_overlap_volume_mm3 > 0.0

    assert measurements.complete_volume_mm3 > (measurements.head_volume_mm3)

    assert measurements.complete_volume_mm3 > (measurements.threaded_shank_volume_mm3)

    assert measurements.z_min_mm == pytest.approx(
        -blank_definition.head_height_mm,
        abs=policy.cad_envelope_tolerance_mm,
    )

    assert measurements.z_max_mm == pytest.approx(
        blank_definition.underhead_length_mm,
        abs=policy.cad_envelope_tolerance_mm,
    )

    expected_lateral_dimensions = sorted(
        (
            blank_definition.head_across_flats_mm,
            expected_hex_across_corners_mm(blank_definition.head_across_flats_mm),
        )
    )

    measured_lateral_dimensions = sorted(
        (
            measurements.x_length_mm,
            measurements.y_length_mm,
        )
    )

    assert measured_lateral_dimensions[0] == pytest.approx(
        expected_lateral_dimensions[0],
        abs=policy.cad_envelope_tolerance_mm,
    )

    assert measured_lateral_dimensions[1] == pytest.approx(
        expected_lateral_dimensions[1],
        abs=policy.cad_envelope_tolerance_mm,
    )


def test_complete_bolt_survives_step_round_trip(
    tmp_path: Path,
) -> None:
    """STEP export and re-import preserve the complete bolt."""

    project_root = Path(__file__).resolve().parents[2]

    blank_definition, thread_definition = load_threaded_shank_definitions(project_root)

    policy = load_geometry_quality_policy(project_root / "config" / "geometry_quality.toml")

    build = build_complete_bolt(
        blank_definition,
        thread_definition,
        policy,
    )

    step_path = tmp_path / "complete_bolt.step"

    _, measurements = export_and_reimport_step(
        build.complete_bolt,
        step_path,
    )

    assert measurements.file_size_bytes > 0
    assert measurements.solid_count == 1
    assert measurements.is_valid

    assert measurements.relative_volume_error <= (policy.step_volume_relative_tolerance)

    assert measurements.maximum_bounds_error_mm <= (policy.step_bounds_tolerance_mm)
