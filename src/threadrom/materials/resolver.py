"""Resolution from governed ThreadROM materials to analytical materials."""

from __future__ import annotations

from threadrom.engineering.analytical_inputs import ElasticMaterial
from threadrom.materials.catalog import MaterialCatalog
from threadrom.materials.fastener_classes import FastenerComponentKind


def resolved_fastener_material_id(
    *,
    material_id: str,
    component_kind: FastenerComponentKind,
    property_class: str,
) -> str:
    """Return the deterministic analytical identity for a fastener material."""

    if not material_id.strip():
        raise ValueError("Material identity must not be blank.")

    if not property_class.strip():
        raise ValueError("Fastener property class must not be blank.")

    return (
        f"{material_id}::"
        f"{component_kind.value}::"
        f"{property_class}"
    )


def resolve_fastener_elastic_material(
    *,
    catalog: MaterialCatalog,
    material_id: str,
    component_kind: FastenerComponentKind,
    property_class: str,
) -> ElasticMaterial:
    """Resolve one governed fastener material for analytical mechanics."""

    family = catalog.get_material(material_id)

    strength = catalog.get_fastener_property_class(
        component_kind,
        property_class,
    )

    return ElasticMaterial(
        material_id=resolved_fastener_material_id(
            material_id=material_id,
            component_kind=component_kind,
            property_class=property_class,
        ),
        youngs_modulus_mpa=family.youngs_modulus_mpa,
        poissons_ratio=family.poissons_ratio,
        proof_stress_mpa=strength.proof_stress_mpa,
        yield_strength_mpa=strength.yield_strength_mpa,
        ultimate_strength_mpa=strength.ultimate_strength_mpa,
    )


def resolve_member_elastic_material(
    *,
    catalog: MaterialCatalog,
    material_id: str,
) -> ElasticMaterial:
    """Resolve one governed member material for analytical mechanics."""

    family = catalog.get_material(material_id)

    return ElasticMaterial(
        material_id=family.material_id,
        youngs_modulus_mpa=family.youngs_modulus_mpa,
        poissons_ratio=family.poissons_ratio,
    )
