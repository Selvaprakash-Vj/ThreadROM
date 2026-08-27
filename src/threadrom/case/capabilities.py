"""Governed capability assessment for ThreadROM product cases."""

from __future__ import annotations

from dataclasses import dataclass

from threadrom.case import CaseSupportStatus
from threadrom.case.contract import ThreadROMCase
from threadrom.engineering.analytical_inputs import ThreadHandedness


@dataclass(frozen=True)
class CapabilityAssessment:
    """End-to-end support status for one requested case."""

    status: CaseSupportStatus
    reasons: tuple[str, ...]


def assess_case_capability(case: ThreadROMCase) -> CapabilityAssessment:
    """Assess current Phase-3 factory support for one product case.

    A representable case is not SUPPORTED until the complete
    ThreadROMCase -> factory -> solver -> physics-acceptance path has
    been demonstrated end-to-end.

    CP1 therefore cannot return SUPPORTED. Promotion of the certified
    baseline family is reserved for CP4 after automatic Phase-2
    baseline reproduction.
    """

    unsupported_reasons: list[str] = []
    experimental_reasons: list[str] = []

    if case.fastener.starts != 1:
        unsupported_reasons.append(
            "Multi-start threads are not supported by the current "
            "certified thread-transfer model."
        )

    if case.fastener.bolt_standard != "ISO 4017:2022":
        unsupported_reasons.append(
            "No governed Phase-3 resolver currently exists for the "
            "selected bolt standard."
        )

    if case.fastener.nut_standard != "ISO 4032:2023":
        unsupported_reasons.append(
            "No governed Phase-3 resolver currently exists for the "
            "selected nut standard."
        )

    if case.fastener.handedness is not ThreadHandedness.RIGHT:
        experimental_reasons.append(
            "Left-hand threads are representable but not end-to-end "
            "certified."
        )

    if case.fastener.thread_designation != "M10x1.5":
        experimental_reasons.append(
            "Non-M10x1.5 metric threads have not yet been reproduced "
            "through the complete Phase-3 factory."
        )

    experimental_reasons.append(
        "The new Phase-3 ThreadROMCase factory path has not yet "
        "reproduced the certified Phase-2 baseline; CP4 certification "
        "is required before any case is promoted to SUPPORTED."
    )

    if unsupported_reasons:
        return CapabilityAssessment(
            status=CaseSupportStatus.UNSUPPORTED,
            reasons=tuple(
                unsupported_reasons + experimental_reasons
            ),
        )

    return CapabilityAssessment(
        status=CaseSupportStatus.EXPERIMENTAL,
        reasons=tuple(experimental_reasons),
    )
