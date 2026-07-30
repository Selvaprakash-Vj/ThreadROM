"""Tests for the governed four-component joint assembly."""

from __future__ import annotations

from pathlib import Path

from threadrom.engineering.baseline_assembly import (
    BaselineAssembly,
    load_baseline_assembly,
)
from threadrom.geometry.bolt_nut_assembly import (
    build_bolt_nut_assembly,
)
from threadrom.geometry.complete_bolt import (
    build_complete_bolt,
)
from threadrom.geometry.complete_joint_assembly import (
    AssemblyGeometryValidationPolicy,
    CompleteJointAssemblyBuild,
    build_complete_joint_assembly,
    export_and_reimport_complete_joint_assembly,
    load_assembly_geometry_validation_policy,
    measure_complete_joint_assembly,
    validate_complete_joint_assembly,
    validate_complete_joint_step_round_trip,
)
from threadrom.geometry.complete_nut import (
    build_complete_nut,
    load_complete_nut_definitions,
)
from threadrom.geometry.geometry_quality import (
    load_geometry_quality_policy,
)
from threadrom.geometry.threaded_shank import (
    load_threaded_shank_definitions,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def build_test_joint() -> tuple[
    CompleteJointAssemblyBuild,
    BaselineAssembly,
    AssemblyGeometryValidationPolicy,
]:
    """Build the governed baseline four-component joint."""

    assembly_definition = load_baseline_assembly(
        PROJECT_ROOT
        / "config"
        / "baseline_assembly.toml"
    )

    policy = load_assembly_geometry_validation_policy(
        PROJECT_ROOT
        / "config"
        / "assembly_geometry_validation.toml"
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
    )

    bolt_nut = build_bolt_nut_assembly(
        bolt_build.complete_bolt,
        nut_build.complete_nut,
        assembly_definition,
    )

    joint = build_complete_joint_assembly(
        bolt_nut,
        assembly_definition,
    )

    return joint, assembly_definition, policy


def test_complete_joint_contains_four_solids() -> None:
    """Every baseline component remains independent."""

    joint, _, _ = build_test_joint()

    measurements = measure_complete_joint_assembly(
        joint
    )

    assert measurements.assembly_solid_count == 4

    assert dict(
        measurements.component_solid_counts
    ) == {
        "bolt": 1,
        "nut": 1,
        "head_side_member": 1,
        "nut_side_member": 1,
    }


def test_complete_joint_passes_geometry_gates() -> None:
    """The baseline stack has correct placement and no overlap."""

    joint, assembly_definition, policy = (
        build_test_joint()
    )

    measurements = measure_complete_joint_assembly(
        joint
    )

    validate_complete_joint_assembly(
        measurements,
        assembly_definition,
        policy,
    )

    assert (
        measurements.maximum_interference_volume_mm3
        <= policy.maximum_pairwise_volume_mm3
    )

    assert len(measurements.interferences) == 6


def test_complete_joint_step_round_trip(
    tmp_path: Path,
) -> None:
    """STEP export preserves all four independent solids."""

    joint, _, policy = build_test_joint()

    quality_policy = load_geometry_quality_policy(
        PROJECT_ROOT
        / "config"
        / "geometry_quality.toml"
    )

    _, measurements = (
        export_and_reimport_complete_joint_assembly(
            joint,
            tmp_path / "complete_joint_assembly.step",
        )
    )

    validate_complete_joint_step_round_trip(
        measurements,
        quality_policy,
        policy.expected_component_count,
    )

    assert measurements.native_solid_count == 4
    assert measurements.reimported_solid_count == 4
