"""Tests for governed material resolution."""

import pytest

from threadrom.materials.baseline_catalog import (
    BASELINE_MATERIAL_CATALOG,
)
from threadrom.materials.fastener_classes import (
    FastenerComponentKind,
)
from threadrom.materials.resolver import (
    resolve_fastener_elastic_material,
    resolve_member_elastic_material,
    resolved_fastener_material_id,
)


def test_bolt_8_8_resolves_to_unique_analytical_material() -> None:
    material = resolve_fastener_elastic_material(
        catalog=BASELINE_MATERIAL_CATALOG,
        material_id="fastener_steel",
        component_kind=FastenerComponentKind.BOLT,
        property_class="8.8",
    )

    assert material.material_id == "fastener_steel::bolt::8.8"
    assert material.youngs_modulus_mpa == 210000.0
    assert material.poissons_ratio == 0.3
    assert material.proof_stress_mpa == 580.0
    assert material.yield_strength_mpa == 640.0
    assert material.ultimate_strength_mpa == 800.0


def test_nut_8_resolves_separately_from_bolt_material() -> None:
    material = resolve_fastener_elastic_material(
        catalog=BASELINE_MATERIAL_CATALOG,
        material_id="fastener_steel",
        component_kind=FastenerComponentKind.NUT,
        property_class="8",
    )

    assert material.material_id == "fastener_steel::nut::8"
    assert material.youngs_modulus_mpa == 210000.0
    assert material.poissons_ratio == 0.3
    assert material.proof_stress_mpa is None
    assert material.yield_strength_mpa is None
    assert material.ultimate_strength_mpa is None


def test_bolt_and_nut_resolved_identities_do_not_collide() -> None:
    bolt_id = resolved_fastener_material_id(
        material_id="fastener_steel",
        component_kind=FastenerComponentKind.BOLT,
        property_class="8.8",
    )

    nut_id = resolved_fastener_material_id(
        material_id="fastener_steel",
        component_kind=FastenerComponentKind.NUT,
        property_class="8",
    )

    assert bolt_id != nut_id


def test_member_material_preserves_family_identity() -> None:
    material = resolve_member_elastic_material(
        catalog=BASELINE_MATERIAL_CATALOG,
        material_id="steel_member",
    )

    assert material.material_id == "steel_member"
    assert material.youngs_modulus_mpa == 210000.0
    assert material.poissons_ratio == 0.3
    assert material.proof_stress_mpa is None


def test_unknown_fastener_material_is_rejected() -> None:
    with pytest.raises(ValueError):
        resolve_fastener_elastic_material(
            catalog=BASELINE_MATERIAL_CATALOG,
            material_id="unknown",
            component_kind=FastenerComponentKind.BOLT,
            property_class="8.8",
        )


def test_unknown_fastener_property_class_is_rejected() -> None:
    with pytest.raises(ValueError):
        resolve_fastener_elastic_material(
            catalog=BASELINE_MATERIAL_CATALOG,
            material_id="fastener_steel",
            component_kind=FastenerComponentKind.BOLT,
            property_class="12.9",
        )


def test_unknown_member_material_is_rejected() -> None:
    with pytest.raises(ValueError):
        resolve_member_elastic_material(
            catalog=BASELINE_MATERIAL_CATALOG,
            material_id="unknown",
        )


def test_resolved_fastener_identity_requires_material_id() -> None:
    with pytest.raises(ValueError):
        resolved_fastener_material_id(
            material_id="",
            component_kind=FastenerComponentKind.BOLT,
            property_class="8.8",
        )


def test_resolved_fastener_identity_requires_property_class() -> None:
    with pytest.raises(ValueError):
        resolved_fastener_material_id(
            material_id="fastener_steel",
            component_kind=FastenerComponentKind.BOLT,
            property_class="",
        )
