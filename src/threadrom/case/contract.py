"""Product-level ThreadROM case contract.

A ThreadROMCase describes the physical problem requested by a user.
Derived geometry, standards data, mesh entities, preload actuators,
solver settings, and certification state do not belong here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math

from threadrom.case import AnalysisFidelity, CalculationMode
from threadrom.engineering.analytical_inputs import ThreadHandedness


CASE_SCHEMA_VERSION = 1


def _require_text(value: str, name: str) -> None:
    if not value.strip():
        raise ValueError(f"{name} must not be blank.")


def _require_positive(value: float, name: str) -> None:
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError(f"{name} must be finite and positive.")


def _require_fraction(value: float, name: str) -> None:
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must lie between 0 and 1.")


@dataclass(frozen=True)
class FastenerSelection:
    """Authoritative product-level fastener selection."""

    bolt_standard: str
    thread_designation: str
    bolt_length_mm: float
    bolt_material_id: str
    bolt_property_class: str
    nut_standard: str
    nut_material_id: str
    nut_property_class: str
    handedness: ThreadHandedness = ThreadHandedness.RIGHT
    starts: int = 1

    def __post_init__(self) -> None:
        for value, name in (
            (self.bolt_standard, "Bolt standard"),
            (self.thread_designation, "Thread designation"),
            (self.bolt_material_id, "Bolt material identity"),
            (self.bolt_property_class, "Bolt property class"),
            (self.nut_standard, "Nut standard"),
            (self.nut_material_id, "Nut material identity"),
            (self.nut_property_class, "Nut property class"),
        ):
            _require_text(value, name)

        _require_positive(self.bolt_length_mm, "Bolt length")

        if self.starts < 1:
            raise ValueError("Thread start count must be at least one.")


@dataclass(frozen=True)
class MemberLayerSelection:
    """One physical layer in the clamped-member stack."""

    layer_id: str
    thickness_mm: float
    material_id: str
    outer_diameter_mm: float
    clearance_hole_diameter_mm: float

    def __post_init__(self) -> None:
        _require_text(self.layer_id, "Member layer identity")
        _require_text(self.material_id, "Member material identity")

        _require_positive(self.thickness_mm, "Member thickness")
        _require_positive(
            self.outer_diameter_mm,
            "Member outer diameter",
        )
        _require_positive(
            self.clearance_hole_diameter_mm,
            "Clearance-hole diameter",
        )

        if self.outer_diameter_mm <= self.clearance_hole_diameter_mm:
            raise ValueError(
                "Member outer diameter must exceed "
                "the clearance-hole diameter."
            )


@dataclass(frozen=True)
class MembersSelection:
    """Arbitrary physical stack of clamped-member layers."""

    layers: tuple[MemberLayerSelection, ...]

    def __post_init__(self) -> None:
        if not self.layers:
            raise ValueError(
                "At least one clamped-member layer is required."
            )

        layer_ids = tuple(layer.layer_id for layer in self.layers)

        if len(set(layer_ids)) != len(layer_ids):
            raise ValueError(
                "Member layer identities must be unique."
            )

    @property
    def member_count(self) -> int:
        """Return the number of physical member layers."""

        return len(self.layers)

    @property
    def total_grip_length_mm(self) -> float:
        """Derive total grip from the member stack."""

        return sum(layer.thickness_mm for layer in self.layers)


@dataclass(frozen=True)
class InterfacesSelection:
    """Physical friction selections for joint interfaces."""

    thread_friction_coefficient: float
    head_bearing_friction_coefficient: float
    nut_bearing_friction_coefficient: float
    member_interface_friction_coefficient: float

    def __post_init__(self) -> None:
        for value, name in (
            (
                self.thread_friction_coefficient,
                "Thread friction coefficient",
            ),
            (
                self.head_bearing_friction_coefficient,
                "Head-bearing friction coefficient",
            ),
            (
                self.nut_bearing_friction_coefficient,
                "Nut-bearing friction coefficient",
            ),
            (
                self.member_interface_friction_coefficient,
                "Member-interface friction coefficient",
            ),
        ):
            _require_fraction(value, name)


@dataclass(frozen=True)
class LoadingSelection:
    """Authoritative applied loading."""

    target_preload_n: float
    external_axial_load_n: float = 0.0

    def __post_init__(self) -> None:
        if (
            not math.isfinite(self.target_preload_n)
            or self.target_preload_n < 0.0
        ):
            raise ValueError(
                "Target preload must be finite and non-negative."
            )

        if not math.isfinite(self.external_axial_load_n):
            raise ValueError(
                "External axial load must be finite."
            )


@dataclass(frozen=True)
class AnalysisSelection:
    """Requested calculation backend and fidelity."""

    calculation_mode: CalculationMode = CalculationMode.AUTO
    fidelity: AnalysisFidelity = AnalysisFidelity.PRODUCTION


@dataclass(frozen=True)
class CaseMetadata:
    """Optional human-facing case metadata."""

    name: str = ""
    notes: str = ""


@dataclass(frozen=True)
class ThreadROMCase:
    """Single authoritative product-level ThreadROM input contract."""

    fastener: FastenerSelection
    members: MembersSelection
    interfaces: InterfacesSelection
    loading: LoadingSelection
    schema_version: int = CASE_SCHEMA_VERSION
    analysis: AnalysisSelection = field(
        default_factory=AnalysisSelection
    )
    metadata: CaseMetadata = field(
        default_factory=CaseMetadata
    )

    def __post_init__(self) -> None:
        if self.schema_version != CASE_SCHEMA_VERSION:
            raise ValueError(
                "Unsupported ThreadROM case schema version: "
                f"{self.schema_version}."
            )
