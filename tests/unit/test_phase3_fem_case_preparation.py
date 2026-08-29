"""Tests for generic Phase-3 FEM case preparation."""

from __future__ import annotations

from dataclasses import replace

import pytest

from threadrom.case.contract import InterfacesSelection
from threadrom.case.reference_cases import phase2_certification_case
from threadrom.case.resolver import resolve_case
from threadrom.factory.fem_case_preparation import (
    derive_bolt_thermal_expansion,
    derive_common_contact_friction,
    derive_common_elastic_properties,
    derive_fem_case_preparation,
)


def test_reference_case_derives_deterministic_fem_identity() -> None:
    case = phase2_certification_case()
    resolved = resolve_case(case)

    preparation = derive_fem_case_preparation(
        resolved
    )

    assert preparation.identity.case_hash == resolved.case_hash
    assert preparation.identity.run_id.startswith(
        "trm_fem_"
    )
    assert preparation.identity.job_name == preparation.identity.run_id
    assert preparation.physics.target_preload_n == 20_000.0
    assert preparation.physics.common_friction_coefficient == 0.15


def test_fem_identity_changes_when_case_changes() -> None:
    baseline = phase2_certification_case()

    changed = replace(
        baseline,
        loading=replace(
            baseline.loading,
            target_preload_n=18_000.0,
        ),
    )

    first = derive_fem_case_preparation(
        resolve_case(baseline)
    )
    second = derive_fem_case_preparation(
        resolve_case(changed)
    )

    assert first.identity.case_hash != second.identity.case_hash
    assert first.identity.run_id != second.identity.run_id


def test_common_contact_friction_is_case_derived() -> None:
    case = phase2_certification_case()

    assert derive_common_contact_friction(case) == 0.15


def test_unequal_interface_frictions_are_rejected_explicitly() -> None:
    baseline = phase2_certification_case()

    changed = replace(
        baseline,
        interfaces=InterfacesSelection(
            thread_friction_coefficient=0.12,
            head_bearing_friction_coefficient=0.15,
            nut_bearing_friction_coefficient=0.15,
            member_interface_friction_coefficient=0.15,
        ),
    )

    with pytest.raises(
        ValueError,
        match="requires a common friction coefficient",
    ):
        derive_fem_case_preparation(
            resolve_case(changed)
        )


def test_common_elastic_properties_are_derived_from_resolved_case() -> None:
    resolved = resolve_case(
        phase2_certification_case()
    )

    youngs_modulus_mpa, poissons_ratio = (
        derive_common_elastic_properties(
            resolved
        )
    )

    assert youngs_modulus_mpa == (
        resolved.bolt_material.youngs_modulus_mpa
    )
    assert poissons_ratio == (
        resolved.bolt_material.poissons_ratio
    )


def test_mixed_elastic_properties_are_rejected_explicitly() -> None:
    resolved = resolve_case(
        phase2_certification_case()
    )

    changed_nut = replace(
        resolved.nut_material,
        youngs_modulus_mpa=(
            resolved.nut_material.youngs_modulus_mpa
            * 0.95
        ),
    )

    changed = replace(
        resolved,
        nut_material=changed_nut,
    )

    with pytest.raises(
        ValueError,
        match="requires common isotropic elastic properties",
    ):
        derive_common_elastic_properties(
            changed
        )


def test_bolt_thermal_expansion_is_governed_by_resolved_material() -> None:
    resolved = resolve_case(
        phase2_certification_case()
    )

    coefficient, source = derive_bolt_thermal_expansion(
        resolved
    )

    assert coefficient == (
        resolved.bolt_material.thermal_expansion_per_c
    )
    assert source == (
        resolved.bolt_material.thermal_source_reference
    )


def test_missing_bolt_thermal_property_is_rejected() -> None:
    resolved = resolve_case(
        phase2_certification_case()
    )

    changed_bolt = replace(
        resolved.bolt_material,
        thermal_expansion_per_c=None,
        thermal_source_reference=None,
    )

    changed = replace(
        resolved,
        bolt_material=changed_bolt,
    )

    with pytest.raises(
        ValueError,
        match="requires a governed bolt thermal expansion coefficient",
    ):
        derive_bolt_thermal_expansion(
            changed
        )


def test_zero_preload_is_not_accepted_by_nonlinear_fem_preparation() -> None:
    baseline = phase2_certification_case()

    changed = replace(
        baseline,
        loading=replace(
            baseline.loading,
            target_preload_n=0.0,
        ),
    )

    with pytest.raises(
        ValueError,
        match="target preload",
    ):
        derive_fem_case_preparation(
            resolve_case(changed)
        )
