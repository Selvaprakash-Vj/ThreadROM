"""Tests for the governed ThreadROM material catalog."""

import pytest

from threadrom.materials.catalog import MaterialCatalog
from threadrom.materials.fastener_classes import (
    FastenerComponentKind,
    FastenerPropertyClass,
)
from threadrom.materials.models import MaterialFamily


def _fastener_steel() -> MaterialFamily:
    return MaterialFamily(
        material_id="fastener_steel",
        display_name="Fastener steel",
        youngs_modulus_mpa=210000.0,
        poissons_ratio=0.3,
        elastic_source_reference="config/baseline_fastener.toml",
        density_kg_per_m3=7850.0,
        density_source_reference="config/baseline_fastener.toml",
        thermal_expansion_per_c=1.2e-5,
        thermal_source_reference="config/complete_joint_preload.toml",
    )


def _member_steel() -> MaterialFamily:
    return MaterialFamily(
        material_id="steel_member",
        display_name="Member steel",
        youngs_modulus_mpa=210000.0,
        poissons_ratio=0.3,
        elastic_source_reference="config/analytical_m10_20kn.toml",
    )


def _bolt_8_8() -> FastenerPropertyClass:
    return FastenerPropertyClass(
        component_kind=FastenerComponentKind.BOLT,
        property_class="8.8",
        source_reference="config/analytical_m10_20kn.toml",
        proof_stress_mpa=580.0,
        yield_strength_mpa=640.0,
        ultimate_strength_mpa=800.0,
    )


def _nut_8() -> FastenerPropertyClass:
    return FastenerPropertyClass(
        component_kind=FastenerComponentKind.NUT,
        property_class="8",
        source_reference="config/analytical_m10_20kn.toml",
    )


def _catalog() -> MaterialCatalog:
    return MaterialCatalog(
        catalog_id="test_catalog",
        material_families=(
            _fastener_steel(),
            _member_steel(),
        ),
        fastener_property_classes=(
            _bolt_8_8(),
            _nut_8(),
        ),
    )


def test_material_lookup() -> None:
    catalog = _catalog()

    material = catalog.get_material("fastener_steel")

    assert material.youngs_modulus_mpa == 210000.0
    assert material.density_kg_per_m3 == 7850.0
    assert material.thermal_expansion_per_c == 1.2e-5


def test_member_material_may_omit_ungoverned_properties() -> None:
    catalog = _catalog()

    material = catalog.get_material("steel_member")

    assert material.density_kg_per_m3 is None
    assert material.thermal_expansion_per_c is None


def test_fastener_property_class_lookup() -> None:
    catalog = _catalog()

    record = catalog.get_fastener_property_class(
        FastenerComponentKind.BOLT,
        "8.8",
    )

    assert record.proof_stress_mpa == 580.0
    assert record.ultimate_strength_mpa == 800.0
    assert record.source_reference == "config/analytical_m10_20kn.toml"


def test_bolt_and_nut_classes_are_distinct_namespaces() -> None:
    catalog = _catalog()

    nut = catalog.get_fastener_property_class(
        FastenerComponentKind.NUT,
        "8",
    )

    assert nut.component_kind is FastenerComponentKind.NUT


def test_material_ids_preserve_catalog_order() -> None:
    catalog = _catalog()

    assert catalog.material_ids == (
        "fastener_steel",
        "steel_member",
    )


def test_duplicate_material_ids_are_rejected() -> None:
    material = _fastener_steel()

    with pytest.raises(ValueError):
        MaterialCatalog(
            catalog_id="test_catalog",
            material_families=(material, material),
            fastener_property_classes=(),
        )


def test_duplicate_property_class_keys_are_rejected() -> None:
    property_class = _bolt_8_8()

    with pytest.raises(ValueError):
        MaterialCatalog(
            catalog_id="test_catalog",
            material_families=(),
            fastener_property_classes=(
                property_class,
                property_class,
            ),
        )


def test_unknown_material_is_rejected() -> None:
    catalog = _catalog()

    with pytest.raises(ValueError):
        catalog.get_material("unknown_material")


def test_unknown_property_class_is_rejected() -> None:
    catalog = _catalog()

    with pytest.raises(ValueError):
        catalog.get_fastener_property_class(
            FastenerComponentKind.BOLT,
            "12.9",
        )


def test_density_requires_provenance() -> None:
    with pytest.raises(ValueError):
        MaterialFamily(
            material_id="test_material",
            display_name="Test material",
            youngs_modulus_mpa=100000.0,
            poissons_ratio=0.3,
            elastic_source_reference="test_source",
            density_kg_per_m3=1000.0,
        )


def test_thermal_expansion_requires_provenance() -> None:
    with pytest.raises(ValueError):
        MaterialFamily(
            material_id="test_material",
            display_name="Test material",
            youngs_modulus_mpa=100000.0,
            poissons_ratio=0.3,
            elastic_source_reference="test_source",
            thermal_expansion_per_c=1.0e-5,
        )


def test_property_class_requires_provenance() -> None:
    with pytest.raises(ValueError):
        FastenerPropertyClass(
            component_kind=FastenerComponentKind.BOLT,
            property_class="8.8",
            source_reference="",
            proof_stress_mpa=580.0,
        )
