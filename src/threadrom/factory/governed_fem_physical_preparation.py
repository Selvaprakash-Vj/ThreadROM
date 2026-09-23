"""Reusable governed FEM geometry and grouped-mesh preparation.

This module reuses the existing ThreadROM CAD and mesh builders.
It does not authorize FEM execution, certify physics, or replace
the caller's governed mesh-quality and provenance requirements.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from threadrom.factory.fem_case_geometry import (
    build_fem_case_geometry,
)
from threadrom.factory.fem_case_mesh import (
    generate_fem_case_grouped_mesh,
)


@dataclass(frozen=True, slots=True)
class GovernedPhysicalPreparation:
    geometry_artifact: object
    mesh_artifact: object
    step_path: Path
    msh_path: Path


def prepare_governed_fem_geometry_mesh(
    *,
    resolved_case,
    expected_case_hash: str,
    expected_run_id: str,
    expected_mesh_policy_name: str,
    artifact_root: Path,
    validation_policy,
    mesh_template,
    joint_classification_template,
    bolt_classification_template,
    nut_classification_template,
    bolt_mesh_level_policy,
    nut_mesh_level_policy,
    local_refinement_policy,
) -> GovernedPhysicalPreparation:
    """Build and verify physical artifacts for a governed FEM case.

    The caller must establish campaign provenance, case eligibility,
    supported mesh policy and configuration validity beforehand.

    Successful geometry and mesh generation does not establish
    FEM physics acceptance or authorize a solver launch.
    """

    if (
        not isinstance(expected_case_hash, str)
        or len(expected_case_hash) != 64
        or any(
            character not in "0123456789abcdef"
            for character in expected_case_hash
        )
    ):
        raise RuntimeError(
            "Invalid governed physical-preparation case hash."
        )

    if (
        not isinstance(expected_run_id, str)
        or not expected_run_id
        or expected_run_id != expected_run_id.strip()
    ):
        raise RuntimeError(
            "Invalid governed physical-preparation run identity."
        )

    if (
        not isinstance(expected_mesh_policy_name, str)
        or not expected_mesh_policy_name.strip()
    ):
        raise RuntimeError(
            "Invalid governed mesh-policy identity."
        )

    if resolved_case.case_hash != expected_case_hash:
        raise RuntimeError(
            "Resolved case hash differs from governed preparation."
        )

    # Preserve the existing parametric geometry implementation.

    geometry_artifact = build_fem_case_geometry(
        resolved_case,
        artifact_root=artifact_root,
        validation_policy=validation_policy,
    )

    if geometry_artifact.case_hash != expected_case_hash:
        raise RuntimeError(
            "Geometry artifact case hash mismatch."
        )

    if geometry_artifact.run_id != expected_run_id:
        raise RuntimeError(
            "Geometry artifact run ID mismatch."
        )

    step_path = geometry_artifact.step_path

    if (
        not step_path.is_file()
        or step_path.stat().st_size <= 0
    ):
        raise RuntimeError(
            "Validated STEP artifact was not produced."
        )

    # Preserve the existing parametric grouped-mesh implementation.

    mesh_artifact = generate_fem_case_grouped_mesh(
        resolved_case,
        geometry_artifact.geometry,
        step_path=step_path,
        artifact_root=artifact_root,
        mesh_template=mesh_template,
        joint_classification_template=(
            joint_classification_template
        ),
        bolt_classification_template=(
            bolt_classification_template
        ),
        nut_classification_template=(
            nut_classification_template
        ),
        bolt_mesh_level_policy=bolt_mesh_level_policy,
        nut_mesh_level_policy=nut_mesh_level_policy,
        local_refinement_policy=local_refinement_policy,
    )

    if mesh_artifact.case_hash != expected_case_hash:
        raise RuntimeError(
            "Mesh artifact case hash mismatch."
        )

    if mesh_artifact.run_id != expected_run_id:
        raise RuntimeError(
            "Mesh artifact run ID mismatch."
        )

    msh_path = mesh_artifact.msh_path

    if (
        not msh_path.is_file()
        or msh_path.stat().st_size <= 0
    ):
        raise RuntimeError(
            "Governed grouped mesh was not produced."
        )

    actual_mesh_variant = (
        mesh_artifact.sizes.level_name
        if mesh_artifact.local_refinement is None
        else mesh_artifact.local_refinement.policy_name
    )

    if actual_mesh_variant != expected_mesh_policy_name:
        raise RuntimeError(
            "Produced mesh variant does not match "
            "the governed mesh policy.\\n"
            f"Expected: {expected_mesh_policy_name}\\n"
            f"Produced: {actual_mesh_variant}"
        )

    return GovernedPhysicalPreparation(
        geometry_artifact=geometry_artifact,
        mesh_artifact=mesh_artifact,
        step_path=step_path,
        msh_path=msh_path,
    )
