"""Integration tests for parametric Phase-3 FEM geometry."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from threadrom.case.reference_cases import (
    phase2_certification_case,
)
from threadrom.case.resolver import resolve_case
from threadrom.factory.fem_case_geometry import (
    build_fem_case_geometry,
)
from threadrom.geometry.complete_joint_assembly import (
    load_assembly_geometry_validation_policy,
)


def _validation_policy():
    return load_assembly_geometry_validation_policy(
        Path("config/assembly_geometry_validation.toml")
    )


def test_generic_fem_geometry_builds_validated_baseline_step(
    tmp_path: Path,
) -> None:
    resolved = resolve_case(
        phase2_certification_case()
    )

    artifact = build_fem_case_geometry(
        resolved,
        artifact_root=tmp_path,
        validation_policy=_validation_policy(),
    )

    assert artifact.case_hash == resolved.case_hash
    assert (
        artifact.assembly_id
        == resolved.assembly.assembly_id
    )
    assert (
        artifact.run_id
        == f"trm_fem_{resolved.case_hash[:12]}"
    )

    assert artifact.step_path.exists()
    assert artifact.step_path.stat().st_size > 0

    assert (
        artifact.step_measurements.native_solid_count
        == 4
    )
    assert (
        artifact.step_measurements.reimported_solid_count
        == 4
    )


def test_generic_fem_geometry_uses_resolved_asymmetric_members(
    tmp_path: Path,
) -> None:
    baseline = phase2_certification_case()

    upper, lower = baseline.members.layers

    asymmetric = replace(
        baseline,
        members=replace(
            baseline.members,
            layers=(
                replace(
                    upper,
                    thickness_mm=8.0,
                ),
                replace(
                    lower,
                    thickness_mm=12.0,
                ),
            ),
        ),
    )

    resolved = resolve_case(
        asymmetric
    )

    artifact = build_fem_case_geometry(
        resolved,
        artifact_root=tmp_path,
        validation_policy=_validation_policy(),
    )

    assert (
        resolved.assembly.upper_member_thickness_mm
        == 8.0
    )
    assert (
        resolved.assembly.lower_member_thickness_mm
        == 12.0
    )

    assert artifact.step_path.exists()
    assert artifact.step_path.stat().st_size > 0

    bounds = artifact.native_measurements

    assert bounds.assembly_solid_count == 4
