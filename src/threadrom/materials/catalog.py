"""Governed ThreadROM material catalog."""

from __future__ import annotations

from dataclasses import dataclass

from threadrom.materials.fastener_classes import (
    FastenerComponentKind,
    FastenerPropertyClass,
)
from threadrom.materials.models import MaterialFamily


@dataclass(frozen=True)
class MaterialCatalog:
    """Immutable governed inventory of material and fastener-class records."""

    catalog_id: str
    material_families: tuple[MaterialFamily, ...]
    fastener_property_classes: tuple[FastenerPropertyClass, ...]

    def __post_init__(self) -> None:
        if not self.catalog_id.strip():
            raise ValueError("Material catalog identity must not be blank.")

        material_ids = tuple(
            material.material_id
            for material in self.material_families
        )

        if len(material_ids) != len(set(material_ids)):
            raise ValueError(
                "Material-family identities must be unique."
            )

        property_keys = tuple(
            (
                record.component_kind,
                record.property_class,
            )
            for record in self.fastener_property_classes
        )

        if len(property_keys) != len(set(property_keys)):
            raise ValueError(
                "Fastener property-class identities must be unique."
            )

    def get_material(
        self,
        material_id: str,
    ) -> MaterialFamily:
        """Return one governed material family."""

        for material in self.material_families:
            if material.material_id == material_id:
                return material

        raise ValueError(
            f"Unknown ThreadROM material family: {material_id!r}."
        )

    def get_fastener_property_class(
        self,
        component_kind: FastenerComponentKind,
        property_class: str,
    ) -> FastenerPropertyClass:
        """Return one governed fastener property-class record."""

        for record in self.fastener_property_classes:
            if (
                record.component_kind is component_kind
                and record.property_class == property_class
            ):
                return record

        raise ValueError(
            "Unknown ThreadROM fastener property class: "
            f"{component_kind.value}/{property_class}."
        )

    @property
    def material_ids(self) -> tuple[str, ...]:
        """Return deterministic material-family identities."""

        return tuple(
            material.material_id
            for material in self.material_families
        )
