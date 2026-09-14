"""Geometry fingerprints separate CAD shape from full resolved physics."""

from dataclasses import replace

from threadrom.case.resolver import resolve_case
from threadrom.factory.geometry_identity import (
    component_geometry_sha256,
    joint_geometry_sha256,
)
from threadrom.factory.geometry_profile import (
    CERTIFIED_PHASE2_GEOMETRY_PROFILE,
)
from tests.unit.test_case_resolver import _baseline_case


def _resolved():
    return resolve_case(_baseline_case())


def test_material_change_does_not_change_geometry_identity() -> None:
    resolved = _resolved()

    changed = replace(
        resolved,
        bolt_material=replace(
            resolved.bolt_material,
            youngs_modulus_mpa=205000.0,
        ),
    )

    assert changed.resolution_hash != resolved.resolution_hash

    assert (
        component_geometry_sha256(changed)
        == component_geometry_sha256(resolved)
    )
    assert (
        joint_geometry_sha256(changed)
        == joint_geometry_sha256(resolved)
    )


def test_member_geometry_changes_joint_but_not_component_identity() -> None:
    resolved = _resolved()

    changed = replace(
        resolved,
        assembly=replace(
            resolved.assembly,
            outer_diameter_mm=31.0,
        ),
    )

    assert (
        component_geometry_sha256(changed)
        == component_geometry_sha256(resolved)
    )
    assert (
        joint_geometry_sha256(changed)
        != joint_geometry_sha256(resolved)
    )


def test_fastener_shape_change_changes_both_geometry_identities() -> None:
    resolved = _resolved()

    changed = replace(
        resolved,
        bolt_standard=replace(
            resolved.bolt_standard,
            head_height_mm=6.5,
        ),
    )

    assert (
        component_geometry_sha256(changed)
        != component_geometry_sha256(resolved)
    )
    assert (
        joint_geometry_sha256(changed)
        != joint_geometry_sha256(resolved)
    )


def test_provenance_only_change_does_not_change_geometry_identity() -> None:
    resolved = _resolved()

    changed_evidence = replace(
        resolved.nut_standard.thickness_evidence,
        evidence_id="TRM-DIM-M10-ALT001",
    )
    changed = replace(
        resolved,
        nut_standard=replace(
            resolved.nut_standard,
            thickness_evidence=changed_evidence,
        ),
    )

    assert changed.resolution_hash != resolved.resolution_hash

    assert (
        component_geometry_sha256(changed)
        == component_geometry_sha256(resolved)
    )
    assert (
        joint_geometry_sha256(changed)
        == joint_geometry_sha256(resolved)
    )


def test_component_cad_policy_change_changes_component_and_joint_identity() -> None:
    resolved = _resolved()

    changed_profile = replace(
        CERTIFIED_PHASE2_GEOMETRY_PROFILE,
        external_thread_radial_clearance_mm=0.06,
    )

    assert (
        component_geometry_sha256(
            resolved,
            profile=changed_profile,
        )
        != component_geometry_sha256(resolved)
    )
    assert (
        joint_geometry_sha256(
            resolved,
            profile=changed_profile,
        )
        != joint_geometry_sha256(resolved)
    )


def test_mating_phase_changes_joint_but_not_component_identity() -> None:
    resolved = _resolved()

    changed_profile = replace(
        CERTIFIED_PHASE2_GEOMETRY_PROFILE,
        mating_phase_offset_deg=1.0,
    )

    assert (
        component_geometry_sha256(
            resolved,
            profile=changed_profile,
        )
        == component_geometry_sha256(resolved)
    )
    assert (
        joint_geometry_sha256(
            resolved,
            profile=changed_profile,
        )
        != joint_geometry_sha256(resolved)
    )
