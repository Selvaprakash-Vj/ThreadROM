"""Tests for governed ThreadROM case capability assessment."""

from dataclasses import replace

from threadrom.case import CaseSupportStatus
from threadrom.case.capabilities import assess_case_capability
from threadrom.case.reference_cases import phase2_certification_case
from threadrom.engineering.analytical_inputs import ThreadHandedness


def test_certified_m10_variant_is_supported() -> None:
    assessment = assess_case_capability(
        phase2_certification_case()
    )

    assert assessment.status is CaseSupportStatus.SUPPORTED
    assert assessment.reasons == ()


def test_left_hand_m10_variant_is_experimental_not_certified() -> None:
    case = phase2_certification_case()

    changed = replace(
        case,
        fastener=replace(
            case.fastener,
            handedness=ThreadHandedness.LEFT,
        ),
    )

    assessment = assess_case_capability(changed)

    assert assessment.status is CaseSupportStatus.EXPERIMENTAL
    assert any(
        "variant" in reason.lower()
        for reason in assessment.reasons
    )


def test_unadmitted_metric_size_is_experimental() -> None:
    case = phase2_certification_case()

    changed = replace(
        case,
        fastener=replace(
            case.fastener,
            thread_designation="M12x1.75",
        ),
    )

    assessment = assess_case_capability(changed)

    assert assessment.status is CaseSupportStatus.EXPERIMENTAL
    assert any(
        "variant" in reason.lower()
        for reason in assessment.reasons
    )


def test_multistart_variant_is_unsupported() -> None:
    case = phase2_certification_case()

    changed = replace(
        case,
        fastener=replace(
            case.fastener,
            starts=2,
        ),
    )

    assessment = assess_case_capability(changed)

    assert assessment.status is CaseSupportStatus.UNSUPPORTED
    assert any(
        "multi-start" in reason.lower()
        for reason in assessment.reasons
    )


def test_unknown_bolt_standard_is_unsupported() -> None:
    case = phase2_certification_case()

    changed = replace(
        case,
        fastener=replace(
            case.fastener,
            bolt_standard="CUSTOM",
        ),
    )

    assessment = assess_case_capability(changed)

    assert assessment.status is CaseSupportStatus.UNSUPPORTED


def test_unknown_nut_standard_is_unsupported() -> None:
    case = phase2_certification_case()

    changed = replace(
        case,
        fastener=replace(
            case.fastener,
            nut_standard="CUSTOM",
        ),
    )

    assessment = assess_case_capability(changed)

    assert assessment.status is CaseSupportStatus.UNSUPPORTED
