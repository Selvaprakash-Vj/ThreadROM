"""Governed maturity of concrete fastener geometry variants.

Variant capability describes demonstrated maturity of a fastener geometry
family. It does not by itself certify every material, member geometry, load,
interface, or analysis request that may reference that fastener variant.

Full-case execution permission remains the responsibility of governed
preflight and applicability checks.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from threadrom.engineering.analytical_inputs import ThreadHandedness


class VariantCapabilityLevel(StrEnum):
    """Highest demonstrated maturity of one fastener variant."""

    DIMENSIONAL_DATA = "dimensional_data"
    CAD_SUPPORTED = "cad_supported"
    FEM_SUPPORTED = "fem_supported"
    FEM_CERTIFIED = "fem_certified"
    ROM_SUPPORTED = "rom_supported"

    @property
    def rank(self) -> int:
        """Return deterministic monotonic pipeline maturity."""

        return {
            VariantCapabilityLevel.DIMENSIONAL_DATA: 1,
            VariantCapabilityLevel.CAD_SUPPORTED: 2,
            VariantCapabilityLevel.FEM_SUPPORTED: 3,
            VariantCapabilityLevel.FEM_CERTIFIED: 4,
            VariantCapabilityLevel.ROM_SUPPORTED: 5,
        }[self]


@dataclass(frozen=True, slots=True)
class FastenerVariantKey:
    """Identity of one concrete fastener geometry variant."""

    bolt_standard: str
    thread_designation: str
    nut_standard: str
    handedness: ThreadHandedness
    starts: int

    def __post_init__(self) -> None:
        for value, name in (
            (self.bolt_standard, "Bolt standard"),
            (self.thread_designation, "Thread designation"),
            (self.nut_standard, "Nut standard"),
        ):
            if not value.strip():
                raise ValueError(
                    f"{name} must not be blank."
                )

        if self.starts <= 0:
            raise ValueError(
                "Thread start count must be positive."
            )


@dataclass(frozen=True, slots=True)
class FastenerVariantCapability:
    """Governed demonstrated maturity for one fastener variant."""

    key: FastenerVariantKey
    capability: VariantCapabilityLevel
    evidence_reference: str

    def __post_init__(self) -> None:
        if not self.evidence_reference.strip():
            raise ValueError(
                "Variant capability evidence reference must not be blank."
            )


@dataclass(frozen=True, slots=True)
class FastenerVariantCapabilityRegistry:
    """Immutable governed registry of fastener-variant maturity."""

    registry_id: str
    records: tuple[FastenerVariantCapability, ...]

    def __post_init__(self) -> None:
        if not self.registry_id.strip():
            raise ValueError(
                "Variant capability registry identity must not be blank."
            )

        keys = tuple(
            record.key
            for record in self.records
        )

        if len(keys) != len(set(keys)):
            raise ValueError(
                "Variant capability registry contains duplicate "
                "fastener-variant records."
            )

    def find(
        self,
        key: FastenerVariantKey,
    ) -> FastenerVariantCapability | None:
        """Return a record when the variant is admitted."""

        for record in self.records:
            if record.key == key:
                return record

        return None

    def get(
        self,
        key: FastenerVariantKey,
    ) -> FastenerVariantCapability:
        """Return an admitted variant or fail closed."""

        record = self.find(key)

        if record is None:
            raise ValueError(
                "No governed capability record exists for fastener "
                f"variant {key!r}."
            )

        return record


_CROSS_SIZE_DIMENSIONAL_EVIDENCE = (
    "docs/verification/"
    "TRM-STD-000002_CROSS_SIZE_DIMENSIONAL_PROVENANCE.md"
)


_M8_DIMENSIONAL_VARIANT = FastenerVariantCapability(
    key=FastenerVariantKey(
        bolt_standard="ISO 4017:2022",
        thread_designation="M8x1.25",
        nut_standard="ISO 4032:2023",
        handedness=ThreadHandedness.RIGHT,
        starts=1,
    ),
    capability=VariantCapabilityLevel.DIMENSIONAL_DATA,
    evidence_reference=_CROSS_SIZE_DIMENSIONAL_EVIDENCE,
)


_M12_DIMENSIONAL_VARIANT = FastenerVariantCapability(
    key=FastenerVariantKey(
        bolt_standard="ISO 4017:2022",
        thread_designation="M12x1.75",
        nut_standard="ISO 4032:2023",
        handedness=ThreadHandedness.RIGHT,
        starts=1,
    ),
    capability=VariantCapabilityLevel.DIMENSIONAL_DATA,
    evidence_reference=_CROSS_SIZE_DIMENSIONAL_EVIDENCE,
)


_M10_PHASE3_CERTIFIED_VARIANT = FastenerVariantCapability(
    key=FastenerVariantKey(
        bolt_standard="ISO 4017:2022",
        thread_designation="M10x1.5",
        nut_standard="ISO 4032:2023",
        handedness=ThreadHandedness.RIGHT,
        starts=1,
    ),
    capability=VariantCapabilityLevel.FEM_CERTIFIED,
    evidence_reference=(
        "docs/verification/"
        "PHASE_3_CP4_CERTIFIED_FEM_REPRODUCTION.md"
    ),
)


PHASE3_FASTENER_VARIANT_CAPABILITIES = (
    FastenerVariantCapabilityRegistry(
        registry_id="threadrom_phase3_fastener_variants_v1",
        records=(
            _M8_DIMENSIONAL_VARIANT,
            _M10_PHASE3_CERTIFIED_VARIANT,
            _M12_DIMENSIONAL_VARIANT,
        ),
    )
)
