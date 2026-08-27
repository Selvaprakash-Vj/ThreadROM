"""Backend-neutral resolved ThreadROM case."""

from __future__ import annotations

from dataclasses import dataclass

from threadrom.case.contract import ThreadROMCase
from threadrom.case.resolved import ResolvedAssembly
from threadrom.case.standards import (
    BoltStandardRecord,
    MetricThreadStandardRecord,
    NutStandardRecord,
)
from threadrom.engineering.metric_thread import MetricThreadBasicDimensions
from threadrom.materials.fastener_classes import (
    FastenerComponentKind,
    FastenerPropertyClass,
)
from threadrom.materials.models import MaterialFamily


@dataclass(frozen=True)
class ResolvedCase:
    """Fully resolved physical case before backend-specific adaptation."""

    source_case: ThreadROMCase
    case_hash: str

    thread_standard: MetricThreadStandardRecord
    thread_basic_dimensions: MetricThreadBasicDimensions
    bolt_standard: BoltStandardRecord
    nut_standard: NutStandardRecord

    assembly: ResolvedAssembly

    bolt_material: MaterialFamily
    nut_material: MaterialFamily
    member_materials: tuple[MaterialFamily, ...]

    bolt_property_class: FastenerPropertyClass
    nut_property_class: FastenerPropertyClass

    def __post_init__(self) -> None:
        if len(self.case_hash) != 64:
            raise ValueError(
                "Resolved case hash must be a SHA256 hexadecimal digest."
            )

        try:
            int(self.case_hash, 16)
        except ValueError as exc:
            raise ValueError(
                "Resolved case hash must be hexadecimal."
            ) from exc

        fastener = self.source_case.fastener

        if self.thread_standard.designation != fastener.thread_designation:
            raise ValueError(
                "Resolved thread designation disagrees with source case."
            )

        if self.bolt_standard.product_standard != fastener.bolt_standard:
            raise ValueError(
                "Resolved bolt standard disagrees with source case."
            )

        if self.bolt_standard.thread_designation != fastener.thread_designation:
            raise ValueError(
                "Resolved bolt thread disagrees with source case."
            )

        if self.nut_standard.product_standard != fastener.nut_standard:
            raise ValueError(
                "Resolved nut standard disagrees with source case."
            )

        if self.nut_standard.thread_designation != fastener.thread_designation:
            raise ValueError(
                "Resolved nut thread disagrees with source case."
            )

        if (
            self.thread_basic_dimensions.nominal_diameter_mm
            != self.thread_standard.nominal_diameter_mm
        ):
            raise ValueError(
                "Resolved basic thread diameter disagrees with standard data."
            )

        if (
            self.thread_basic_dimensions.pitch_mm
            != self.thread_standard.pitch_mm
        ):
            raise ValueError(
                "Resolved basic thread pitch disagrees with standard data."
            )

        if self.bolt_material.material_id != fastener.bolt_material_id:
            raise ValueError(
                "Resolved bolt material disagrees with source case."
            )

        if self.nut_material.material_id != fastener.nut_material_id:
            raise ValueError(
                "Resolved nut material disagrees with source case."
            )

        if (
            self.bolt_property_class.component_kind
            is not FastenerComponentKind.BOLT
            or self.bolt_property_class.property_class
            != fastener.bolt_property_class
        ):
            raise ValueError(
                "Resolved bolt property class disagrees with source case."
            )

        if (
            self.nut_property_class.component_kind
            is not FastenerComponentKind.NUT
            or self.nut_property_class.property_class
            != fastener.nut_property_class
        ):
            raise ValueError(
                "Resolved nut property class disagrees with source case."
            )

        if len(self.member_materials) != self.source_case.members.member_count:
            raise ValueError(
                "Resolved member-material count disagrees with source case."
            )

        for layer, material in zip(
            self.source_case.members.layers,
            self.member_materials,
            strict=True,
        ):
            if material.material_id != layer.material_id:
                raise ValueError(
                    "Resolved member material disagrees with source case "
                    f"for layer {layer.layer_id!r}."
                )

        if self.assembly.bolt_length_mm != fastener.bolt_length_mm:
            raise ValueError(
                "Resolved assembly bolt length disagrees with source case."
            )

        if (
            self.assembly.total_grip_length_mm
            != self.source_case.members.total_grip_length_mm
        ):
            raise ValueError(
                "Resolved assembly grip disagrees with source case."
            )
