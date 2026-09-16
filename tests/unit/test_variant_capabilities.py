"""Contract tests for governed fastener-variant capability maturity."""

import pytest

from threadrom.case.variant_capabilities import (
    FastenerVariantCapability,
    FastenerVariantCapabilityRegistry,
    FastenerVariantKey,
    VariantCapabilityLevel,
    PHASE3_FASTENER_VARIANT_CAPABILITIES,
)
from threadrom.engineering.analytical_inputs import ThreadHandedness


def _key(
    *,
    bolt_standard: str = "ISO 4017:2022",
    thread_designation: str = "M16x2.0",
    nut_standard: str = "ISO 4032:2023",
    handedness: ThreadHandedness = ThreadHandedness.RIGHT,
    starts: int = 1,
) -> FastenerVariantKey:
    return FastenerVariantKey(
        bolt_standard=bolt_standard,
        thread_designation=thread_designation,
        nut_standard=nut_standard,
        handedness=handedness,
        starts=starts,
    )


def _record(
    *,
    key: FastenerVariantKey | None = None,
    level: VariantCapabilityLevel = (
        VariantCapabilityLevel.DIMENSIONAL_DATA
    ),
    evidence_reference: str = "docs/verification/example.md",
) -> FastenerVariantCapability:
    return FastenerVariantCapability(
        key=_key() if key is None else key,
        capability=level,
        evidence_reference=evidence_reference,
    )


def test_variant_key_is_size_and_standard_driven() -> None:
    key = _key(thread_designation="M48x5.0")

    assert key.thread_designation == "M48x5.0"
    assert key.bolt_standard == "ISO 4017:2022"
    assert key.nut_standard == "ISO 4032:2023"
    assert key.handedness is ThreadHandedness.RIGHT
    assert key.starts == 1


def test_variant_key_rejects_invalid_identity() -> None:
    with pytest.raises(ValueError):
        _key(thread_designation="")

    with pytest.raises(ValueError):
        _key(starts=0)


def test_registry_accepts_new_size_without_code_branch() -> None:
    m16 = _record(
        key=_key(thread_designation="M16x2.0"),
        level=VariantCapabilityLevel.CAD_SUPPORTED,
    )
    m48 = _record(
        key=_key(thread_designation="M48x5.0"),
        level=VariantCapabilityLevel.DIMENSIONAL_DATA,
    )

    registry = FastenerVariantCapabilityRegistry(
        registry_id="test-diversified-registry",
        records=(m16, m48),
    )

    assert registry.get(m16.key) == m16
    assert registry.get(m48.key) == m48


def test_registry_lookup_can_report_not_yet_admitted_variant() -> None:
    registry = FastenerVariantCapabilityRegistry(
        registry_id="test-empty-registry",
        records=(),
    )

    assert registry.find(_key()) is None


def test_duplicate_variant_records_are_rejected() -> None:
    record = _record()

    with pytest.raises(ValueError, match="duplicate"):
        FastenerVariantCapabilityRegistry(
            registry_id="duplicate-test",
            records=(record, record),
        )


def test_capability_levels_preserve_pipeline_maturity() -> None:
    assert VariantCapabilityLevel.DIMENSIONAL_DATA.rank == 1
    assert VariantCapabilityLevel.CAD_SUPPORTED.rank == 2
    assert VariantCapabilityLevel.FEM_SUPPORTED.rank == 3
    assert VariantCapabilityLevel.FEM_CERTIFIED.rank == 4
    assert VariantCapabilityLevel.ROM_SUPPORTED.rank == 5


def test_current_m10_right_hand_single_start_variant_is_fem_certified() -> None:
    key = FastenerVariantKey(
        bolt_standard="ISO 4017:2022",
        thread_designation="M10x1.5",
        nut_standard="ISO 4032:2023",
        handedness=ThreadHandedness.RIGHT,
        starts=1,
    )

    record = PHASE3_FASTENER_VARIANT_CAPABILITIES.get(key)

    assert record.capability is VariantCapabilityLevel.FEM_CERTIFIED
    assert (
        record.evidence_reference
        == "docs/verification/PHASE_3_CP4_CERTIFIED_FEM_REPRODUCTION.md"
    )


@pytest.mark.parametrize(
    "designation",
    (
        "M8x1.25",
        "M12x1.75",
    ),
)
def test_cross_size_variants_are_admitted_at_dimensional_data_only(
    designation: str,
) -> None:
    key = FastenerVariantKey(
        bolt_standard="ISO 4017:2022",
        thread_designation=designation,
        nut_standard="ISO 4032:2023",
        handedness=ThreadHandedness.RIGHT,
        starts=1,
    )

    record = PHASE3_FASTENER_VARIANT_CAPABILITIES.get(key)

    assert (
        record.capability
        is VariantCapabilityLevel.DIMENSIONAL_DATA
    )
    assert (
        record.evidence_reference
        == "docs/verification/"
        "TRM-STD-000002_CROSS_SIZE_DIMENSIONAL_PROVENANCE.md"
    )


def test_unverified_future_size_is_not_falsely_admitted() -> None:
    key = FastenerVariantKey(
        bolt_standard="ISO 4017:2022",
        thread_designation="M16x2.0",
        nut_standard="ISO 4032:2023",
        handedness=ThreadHandedness.RIGHT,
        starts=1,
    )

    assert PHASE3_FASTENER_VARIANT_CAPABILITIES.find(key) is None
