"""Governed material inventory reproducing the certified Phase-2 baseline."""

from __future__ import annotations

from threadrom.materials.catalog import MaterialCatalog
from threadrom.materials.fastener_classes import (
    FastenerComponentKind,
    FastenerPropertyClass,
)
from threadrom.materials.models import MaterialFamily


FASTENER_STEEL = MaterialFamily(
    material_id="fastener_steel",
    display_name="Baseline fastener steel",
    youngs_modulus_mpa=210000.0,
    poissons_ratio=0.30,
    elastic_source_reference=(
        "config/baseline_fastener.toml [material]"
    ),
    density_kg_per_m3=7850.0,
    density_source_reference=(
        "config/baseline_fastener.toml [material]"
    ),
    thermal_expansion_per_c=1.2e-5,
    thermal_source_reference=(
        "config/complete_joint_preload.toml [thermal]"
    ),
)


STEEL_MEMBER = MaterialFamily(
    material_id="steel_member",
    display_name="Baseline member steel",
    youngs_modulus_mpa=210000.0,
    poissons_ratio=0.30,
    elastic_source_reference=(
        "config/analytical_m10_20kn.toml [[materials]] "
        "material_id=member_steel"
    ),
)


BOLT_PROPERTY_CLASS_8_8 = FastenerPropertyClass(
    component_kind=FastenerComponentKind.BOLT,
    property_class="8.8",
    source_reference=(
        "config/baseline_fastener.toml [strength_reference]"
    ),
    proof_stress_mpa=580.0,
    yield_strength_mpa=640.0,
    ultimate_strength_mpa=800.0,
)


NUT_PROPERTY_CLASS_8 = FastenerPropertyClass(
    component_kind=FastenerComponentKind.NUT,
    property_class="8",
    source_reference=(
        "config/baseline_fastener.toml [nut]"
    ),
)


BASELINE_MATERIAL_CATALOG = MaterialCatalog(
    catalog_id="threadrom_phase2_baseline_v1",
    material_families=(
        FASTENER_STEEL,
        STEEL_MEMBER,
    ),
    fastener_property_classes=(
        BOLT_PROPERTY_CLASS_8_8,
        NUT_PROPERTY_CLASS_8,
    ),
)
