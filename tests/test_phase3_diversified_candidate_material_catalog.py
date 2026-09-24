"""No-solver checks for the first diversified material candidate."""

from dataclasses import replace

import pytest

from threadrom.case.reference_cases import phase2_certification_case
from threadrom.case.resolver import resolve_case
from threadrom.case.serialization import case_sha256
from threadrom.factory.fem_case_preparation import (
    derive_fem_case_preparation,
)
from threadrom.materials.baseline_catalog import (
    BASELINE_MATERIAL_CATALOG,
)
from threadrom.materials.diversified_candidate_catalog import (
    DIVERSIFIED_CANDIDATE_MATERIAL_CATALOG,
    MEMBER_ALUMINIUM_EN_AW_6082_T6,
)


CANDIDATE_ID = "member_aluminium_en_aw_6082_t6"


def _candidate_case():
    baseline = phase2_certification_case()
    return replace(
        baseline,
        members=replace(
            baseline.members,
            layers=tuple(
                replace(layer, material_id=CANDIDATE_ID)
                for layer in baseline.members.layers
            ),
        ),
    )


def test_candidate_catalog_preserves_baseline_catalog():
    assert set(BASELINE_MATERIAL_CATALOG.material_ids) == {
        "fastener_steel",
        "steel_member",
    }
    assert set(DIVERSIFIED_CANDIDATE_MATERIAL_CATALOG.material_ids) == {
        "fastener_steel",
        "steel_member",
        CANDIDATE_ID,
    }
    assert (
        DIVERSIFIED_CANDIDATE_MATERIAL_CATALOG.fastener_property_classes
        == BASELINE_MATERIAL_CATALOG.fastener_property_classes
    )
    assert (
        DIVERSIFIED_CANDIDATE_MATERIAL_CATALOG.get_material(
            "fastener_steel"
        )
        == BASELINE_MATERIAL_CATALOG.get_material("fastener_steel")
    )


def test_candidate_has_distinct_source_backed_elastic_properties():
    material = MEMBER_ALUMINIUM_EN_AW_6082_T6
    assert material.youngs_modulus_mpa == 70000.0
    assert material.poissons_ratio == 0.33
    assert "euralliage.com/6082_english.htm" in (
        material.elastic_source_reference
    )
    assert material.thermal_expansion_per_c is None
    assert material.density_kg_per_m3 is None


def test_paired_aluminium_members_resolve_and_prepare_without_solver():
    baseline = phase2_certification_case()
    candidate = _candidate_case()

    assert case_sha256(candidate) != case_sha256(baseline)
    assert candidate.fastener == baseline.fastener
    assert candidate.loading == baseline.loading
    assert candidate.interfaces == baseline.interfaces

    assert all(
        layer.material_id == CANDIDATE_ID
        for layer in candidate.members.layers
    )

    resolved = resolve_case(
        candidate,
        material_catalog=DIVERSIFIED_CANDIDATE_MATERIAL_CATALOG,
    )

    assert resolved.case_hash == case_sha256(candidate)

    preparation = derive_fem_case_preparation(resolved)
    physics = preparation.physics

    assert physics.youngs_modulus_mpa == 210000.0
    assert physics.poissons_ratio == 0.30
    assert physics.member_youngs_modulus_mpa == 70000.0
    assert physics.member_poissons_ratio == 0.33
    assert physics.common_friction_coefficient == 0.15
    assert physics.target_preload_n == (
        candidate.loading.target_preload_n
    )


def test_unequal_member_material_pair_is_rejected():
    baseline = phase2_certification_case()
    upper, lower = baseline.members.layers

    unequal = replace(
        baseline,
        members=replace(
            baseline.members,
            layers=(
                replace(upper, material_id=CANDIDATE_ID),
                lower,
            ),
        ),
    )

    resolved = resolve_case(
        unequal,
        material_catalog=DIVERSIFIED_CANDIDATE_MATERIAL_CATALOG,
    )

    with pytest.raises(ValueError, match="material identity"):
        derive_fem_case_preparation(resolved)
