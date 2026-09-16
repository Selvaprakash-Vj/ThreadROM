"""Governed capability assessment for ThreadROM product cases."""

from __future__ import annotations

from dataclasses import dataclass

from threadrom.case import CaseSupportStatus
from threadrom.case.contract import ThreadROMCase
from threadrom.case.variant_capabilities import (
    FastenerVariantKey,
    PHASE3_FASTENER_VARIANT_CAPABILITIES,
    VariantCapabilityLevel,
)


@dataclass(frozen=True)
class CapabilityAssessment:
    """Demonstrated maturity of one requested fastener variant.

    This assessment describes maturity of the fastener geometry variant.
    It does not by itself certify every material, member geometry, load,
    interface, or analysis request using that variant.

    Full-case execution permission remains governed by preflight and,
    where applicable, ROM applicability checks.
    """

    status: CaseSupportStatus
    reasons: tuple[str, ...]


def assess_case_capability(
    case: ThreadROMCase,
) -> CapabilityAssessment:
    """Assess governed maturity of the requested fastener variant."""

    fastener = case.fastener
    registry = PHASE3_FASTENER_VARIANT_CAPABILITIES

    known_bolt_standards = {
        record.key.bolt_standard
        for record in registry.records
    }
    known_nut_standards = {
        record.key.nut_standard
        for record in registry.records
    }

    unsupported_reasons: list[str] = []

    if fastener.starts != 1:
        unsupported_reasons.append(
            "Multi-start threads are not supported by the current "
            "certified thread-transfer topology."
        )

    if fastener.bolt_standard not in known_bolt_standards:
        unsupported_reasons.append(
            "The selected bolt standard has no governed fastener-variant "
            "capability family in the current registry."
        )

    if fastener.nut_standard not in known_nut_standards:
        unsupported_reasons.append(
            "The selected nut standard has no governed fastener-variant "
            "capability family in the current registry."
        )

    if unsupported_reasons:
        return CapabilityAssessment(
            status=CaseSupportStatus.UNSUPPORTED,
            reasons=tuple(unsupported_reasons),
        )

    key = FastenerVariantKey(
        bolt_standard=fastener.bolt_standard,
        thread_designation=fastener.thread_designation,
        nut_standard=fastener.nut_standard,
        handedness=fastener.handedness,
        starts=fastener.starts,
    )

    record = registry.find(key)

    if record is None:
        return CapabilityAssessment(
            status=CaseSupportStatus.EXPERIMENTAL,
            reasons=(
                "The requested fastener variant is representable by the "
                "parametric case architecture but has not yet been admitted "
                "to the governed variant-capability registry.",
            ),
        )

    if record.capability in {
        VariantCapabilityLevel.FEM_CERTIFIED,
        VariantCapabilityLevel.ROM_SUPPORTED,
    }:
        return CapabilityAssessment(
            status=CaseSupportStatus.SUPPORTED,
            reasons=(),
        )

    return CapabilityAssessment(
        status=CaseSupportStatus.EXPERIMENTAL,
        reasons=(
            "The requested fastener variant is governed but has not yet "
            "reached certified FEM maturity.",
        ),
    )
