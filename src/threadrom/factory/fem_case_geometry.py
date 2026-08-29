"""Executable parametric geometry stage for one FEM case."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from threadrom.case.resolved_case import ResolvedCase
from threadrom.factory.fem_case_preparation import (
    derive_fem_case_preparation,
)
from threadrom.factory.geometry_adapter import (
    GeometryDefinitionBundle,
    build_geometry_definitions,
)
from threadrom.factory.geometry_profile import (
    CERTIFIED_PHASE2_GEOMETRY_PROFILE,
    GeometryDefinitionProfile,
)
from threadrom.geometry.complete_bolt import (
    build_complete_bolt,
)
from threadrom.geometry.complete_joint_assembly import (
    AssemblyGeometryValidationPolicy,
    CompleteJointAssemblyMeasurements,
    CompleteJointAssemblyStepMeasurements,
    build_complete_joint_assembly,
    export_and_reimport_complete_joint_assembly,
    measure_complete_joint_assembly,
    validate_complete_joint_assembly,
    validate_complete_joint_step_round_trip,
)
from threadrom.geometry.complete_nut import (
    build_complete_nut,
)
from threadrom.geometry.bolt_nut_assembly import (
    build_bolt_nut_assembly,
)


@dataclass(frozen=True, slots=True)
class FemCaseGeometryArtifact:
    """Validated STEP artifact produced for one resolved FEM case."""

    case_hash: str
    run_id: str
    assembly_id: str
    geometry: GeometryDefinitionBundle
    step_path: Path
    native_measurements: CompleteJointAssemblyMeasurements
    step_measurements: CompleteJointAssemblyStepMeasurements


def build_fem_case_geometry(
    resolved: ResolvedCase,
    *,
    artifact_root: Path,
    validation_policy: AssemblyGeometryValidationPolicy,
    profile: GeometryDefinitionProfile = (
        CERTIFIED_PHASE2_GEOMETRY_PROFILE
    ),
) -> FemCaseGeometryArtifact:
    """Build, validate and STEP-round-trip one parametric joint.

    Geometry physics comes from ``ResolvedCase`` through the governed
    geometry adapter. The supplied validation policy remains reusable
    backend policy. No Phase-2 assembly/config geometry is loaded here.
    """

    preparation = derive_fem_case_preparation(
        resolved
    )

    geometry = build_geometry_definitions(
        resolved,
        profile=profile,
    )

    bolt = build_complete_bolt(
        geometry.bolt_blank,
        geometry.external_thread,
        geometry.quality_policy,
        mating_clearance_mm=(
            geometry.mating_clearance_mm
        ),
    )

    nut = build_complete_nut(
        geometry.nut_blank,
        geometry.internal_thread,
        geometry.quality_policy,
    )

    bolt_nut = build_bolt_nut_assembly(
        bolt.complete_bolt,
        nut.complete_nut,
        resolved.assembly,
        geometry.external_thread,
        geometry.internal_thread,
        geometry.quality_policy.thread_boolean_overlap_mm,
        mating_phase_offset_deg=(
            geometry.mating_phase_offset_deg
        ),
    )

    joint = build_complete_joint_assembly(
        bolt_nut,
        resolved.assembly,
    )

    native_measurements = (
        measure_complete_joint_assembly(
            joint
        )
    )

    case_validation_policy = replace(
        validation_policy,
        assembly_id=resolved.assembly.assembly_id,
    )

    validate_complete_joint_assembly(
        native_measurements,
        resolved.assembly,
        case_validation_policy,
    )

    geometry_directory = (
        artifact_root
        / preparation.identity.run_id
        / "geometry"
    )

    step_path = (
        geometry_directory
        / "complete_joint_assembly.step"
    )

    _reimported, step_measurements = (
        export_and_reimport_complete_joint_assembly(
            joint,
            step_path,
        )
    )

    validate_complete_joint_step_round_trip(
        step_measurements,
        geometry.quality_policy,
        case_validation_policy.expected_component_count,
    )

    return FemCaseGeometryArtifact(
        case_hash=resolved.case_hash,
        run_id=preparation.identity.run_id,
        assembly_id=resolved.assembly.assembly_id,
        geometry=geometry,
        step_path=step_path,
        native_measurements=native_measurements,
        step_measurements=step_measurements,
    )
