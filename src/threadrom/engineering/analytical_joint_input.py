"""Canonical bolt-nut joint input for the analytical engine."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from threadrom.engineering.analytical_inputs import (
    BoltAxialSegmentInput,
    ElasticMaterial,
    LoadingInput,
    MemberLayerInput,
    MetricThreadInput,
)


class BoltComplianceMethod(StrEnum):
    """Supported bolt-compliance calculation methods."""

    UNIFORM_TENSILE_AREA = "uniform_tensile_area"
    SEGMENTED = "segmented"


class MemberCompressionMethod(StrEnum):
    """Supported clamped-member compression methods."""

    UNIFORM_ANNULAR_CYLINDER = "uniform_annular_cylinder"
    COMPRESSION_CONE = "compression_cone"


class ExternalLoadMethod(StrEnum):
    """Supported external-load introduction methods."""

    BASIC_SPRING_RATIO = "basic_spring_ratio"
    LOAD_INTRODUCTION_FACTOR = "load_introduction_factor"


class ThreadLoadDistributionMethod(StrEnum):
    """Supported engaged-thread load-distribution methods."""

    UNIFORM = "uniform"
    DISCRETE_SPRING = "discrete_spring"


@dataclass(frozen=True)
class BoltInput:
    """Parametric bolt definition."""

    bolt_id: str
    material_id: str
    nominal_length_mm: float
    axial_segments: tuple[BoltAxialSegmentInput, ...]
    head_bearing_outer_diameter_mm: float
    head_bearing_inner_diameter_mm: float

    def __post_init__(self) -> None:
        if not self.bolt_id.strip():
            raise ValueError("Bolt identity must not be blank.")

        if not self.material_id.strip():
            raise ValueError("Bolt material identity must not be blank.")

        if self.nominal_length_mm <= 0.0:
            raise ValueError("Bolt nominal length must be positive.")

        if not self.axial_segments:
            raise ValueError("At least one bolt axial segment is required.")

        segment_ids = [segment.segment_id for segment in self.axial_segments]

        if len(segment_ids) != len(set(segment_ids)):
            raise ValueError("Bolt axial-segment identities must be unique.")

        _validate_bearing_ring(
            component_name="Bolt head",
            outer_diameter_mm=self.head_bearing_outer_diameter_mm,
            inner_diameter_mm=self.head_bearing_inner_diameter_mm,
        )

        if self.axial_segment_length_mm > self.nominal_length_mm:
            raise ValueError(
                "Total bolt axial-segment length must not exceed the nominal bolt length."
            )

    @property
    def axial_segment_length_mm(self) -> float:
        """Return the total explicitly modelled bolt-segment length."""

        return sum(segment.length_mm for segment in self.axial_segments)


@dataclass(frozen=True)
class NutInput:
    """Parametric nut definition."""

    nut_id: str
    material_id: str
    thickness_mm: float
    thread_engagement_length_mm: float
    bearing_outer_diameter_mm: float
    bearing_inner_diameter_mm: float

    def __post_init__(self) -> None:
        if not self.nut_id.strip():
            raise ValueError("Nut identity must not be blank.")

        if not self.material_id.strip():
            raise ValueError("Nut material identity must not be blank.")

        if self.thickness_mm <= 0.0:
            raise ValueError("Nut thickness must be positive.")

        if self.thread_engagement_length_mm <= 0.0:
            raise ValueError("Thread engagement length must be positive.")

        if self.thread_engagement_length_mm > self.thickness_mm:
            raise ValueError("Thread engagement length must not exceed nut thickness.")

        _validate_bearing_ring(
            component_name="Nut",
            outer_diameter_mm=self.bearing_outer_diameter_mm,
            inner_diameter_mm=self.bearing_inner_diameter_mm,
        )


@dataclass(frozen=True)
class AnalyticalMethodSelection:
    """Explicit analytical-method and assumption selection."""

    bolt_compliance: BoltComplianceMethod
    member_compression: MemberCompressionMethod
    external_load: ExternalLoadMethod
    thread_load_distribution: ThreadLoadDistributionMethod
    head_participation_factor: float
    nut_participation_factor: float
    load_introduction_factor: float = 1.0

    def __post_init__(self) -> None:
        if self.head_participation_factor < 0.0:
            raise ValueError("Head participation factor must not be negative.")

        if self.nut_participation_factor < 0.0:
            raise ValueError("Nut participation factor must not be negative.")

        if not 0.0 <= self.load_introduction_factor <= 1.0:
            raise ValueError("Load-introduction factor must lie in [0, 1].")


@dataclass(frozen=True)
class AnalyticalJointInput:
    """Complete canonical input for one analytical bolt-nut joint."""

    joint_id: str
    thread: MetricThreadInput
    bolt: BoltInput
    nut: NutInput
    member_layers: tuple[MemberLayerInput, ...]
    materials: tuple[ElasticMaterial, ...]
    loading: LoadingInput
    methods: AnalyticalMethodSelection

    def __post_init__(self) -> None:
        if not self.joint_id.strip():
            raise ValueError("Joint identity must not be blank.")

        if not self.materials:
            raise ValueError("At least one material definition is required.")

        if not self.member_layers:
            raise ValueError("At least one clamped-member layer is required.")

        material_ids = [material.material_id for material in self.materials]

        if len(material_ids) != len(set(material_ids)):
            raise ValueError("Material identities must be unique.")

        layer_ids = [layer.layer_id for layer in self.member_layers]

        if len(layer_ids) != len(set(layer_ids)):
            raise ValueError("Member-layer identities must be unique.")

        available_materials = set(material_ids)

        required_materials = {
            self.bolt.material_id,
            self.nut.material_id,
            *(layer.material_id for layer in self.member_layers),
            *(
                segment.material_id
                for segment in self.bolt.axial_segments
                if segment.material_id is not None
            ),
        }

        unresolved_materials = required_materials - available_materials

        if unresolved_materials:
            formatted = ", ".join(sorted(unresolved_materials))

            raise ValueError(f"Unresolved material references: {formatted}")

        for layer in self.member_layers:
            if layer.clearance_hole_diameter_mm <= self.thread.nominal_diameter_mm:
                raise ValueError(
                    "Every member clearance hole must exceed the nominal thread diameter."
                )

        if self.bolt.nominal_length_mm <= self.grip_length_mm:
            raise ValueError(
                "Bolt nominal length must exceed the total grip length for a bolt-nut assembly."
            )

    @property
    def grip_length_mm(self) -> float:
        """Return the total clamped-member thickness."""

        return sum(layer.thickness_mm for layer in self.member_layers)

    @property
    def engaged_thread_count(self) -> float:
        """Return the nominal engaged thread-pitch count."""

        return self.nut.thread_engagement_length_mm / self.thread.pitch_mm

    def material_by_id(
        self,
        material_id: str,
    ) -> ElasticMaterial:
        """Return one validated material by identity."""

        for material in self.materials:
            if material.material_id == material_id:
                return material

        raise KeyError(f"Unknown material identity: {material_id}")


def _validate_bearing_ring(
    *,
    component_name: str,
    outer_diameter_mm: float,
    inner_diameter_mm: float,
) -> None:
    """Validate one annular bearing region."""

    if inner_diameter_mm <= 0.0:
        raise ValueError(f"{component_name} bearing inner diameter must be positive.")

    if outer_diameter_mm <= inner_diameter_mm:
        raise ValueError(f"{component_name} bearing outer diameter must exceed its inner diameter.")
