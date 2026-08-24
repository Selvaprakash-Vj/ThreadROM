"""Tests for the governed bolt-nut assembly geometry."""

from __future__ import annotations

from pathlib import Path

from threadrom.engineering.baseline_assembly import (
    load_baseline_assembly,
)
from threadrom.geometry.bolt_nut_assembly import (
    BoltNutAssemblyBuild,
    build_bolt_nut_assembly,
    export_and_reimport_bolt_nut_assembly,
    measure_bolt_nut_assembly,
    validate_bolt_nut_step_round_trip,
)
from threadrom.geometry.complete_bolt import (
    build_complete_bolt,
)
from threadrom.geometry.complete_nut import (
    build_complete_nut,
    load_complete_nut_definitions,
)
from threadrom.geometry.geometry_quality import (
    GeometryQualityPolicy,
    load_geometry_quality_policy,
)
from threadrom.geometry.threaded_shank import (
    load_threaded_shank_definitions,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def build_test_assembly() -> tuple[
    BoltNutAssemblyBuild,
    GeometryQualityPolicy,
]:
    """Build the governed baseline assembly for testing."""

    assembly_definition = load_baseline_assembly(
        PROJECT_ROOT
        / "config"
        / "baseline_assembly.toml"
    )

    bolt_blank, bolt_thread = (
        load_threaded_shank_definitions(
            PROJECT_ROOT
        )
    )

    quality_policy = load_geometry_quality_policy(
        PROJECT_ROOT
        / "config"
        / "geometry_quality.toml"
    )

    nut_blank, nut_thread = (
        load_complete_nut_definitions(
            PROJECT_ROOT
        )
    )

    bolt_build = build_complete_bolt(
        bolt_blank,
        bolt_thread,
        quality_policy,
    )

    nut_build = build_complete_nut(
        nut_blank,
        nut_thread,
        quality_policy,
    )

    assembly_build = build_bolt_nut_assembly(
        bolt_build.complete_bolt,
        nut_build.complete_nut,
        assembly_definition,
        bolt_thread,
        nut_thread,
        quality_policy.thread_boolean_overlap_mm,
    )

    return assembly_build, quality_policy


def test_bolt_nut_assembly_contains_two_solids() -> None:
    """The native positioned assembly preserves both components."""

    assembly_build, _ = build_test_assembly()

    measurements = measure_bolt_nut_assembly(
        assembly_build
    )

    assert measurements.bolt_solid_count == 1
    assert measurements.nut_solid_count == 1
    assert measurements.assembly_solid_count == 2
    assert measurements.z_min_mm < -6.39
    assert measurements.z_max_mm > 29.99


def test_bolt_nut_assembly_step_round_trip(
    tmp_path: Path,
) -> None:
    """STEP export preserves both independent component solids."""

    assembly_build, quality_policy = (
        build_test_assembly()
    )

    _, measurements = (
        export_and_reimport_bolt_nut_assembly(
            assembly_build,
            tmp_path / "bolt_nut_assembly.step",
        )
    )

    validate_bolt_nut_step_round_trip(
        measurements,
        quality_policy,
    )

    assert measurements.native_solid_count == 2
    assert measurements.reimported_solid_count == 2
