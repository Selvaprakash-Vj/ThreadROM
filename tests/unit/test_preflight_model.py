from __future__ import annotations

import pytest

from threadrom.case import CaseSupportStatus
from threadrom.case.preflight import (
    PreflightDisposition,
    PreflightFinding,
    PreflightReport,
    PreflightRuleCode,
    PreflightSeverity,
    PreflightTarget,
)


def test_preflight_report_passes_without_errors() -> None:
    report = PreflightReport(
        case_hash="abc123",
        target=PreflightTarget.GEOMETRY,
        support_status=CaseSupportStatus.EXPERIMENTAL,
        findings=(
            PreflightFinding(
                code=PreflightRuleCode.ANALYSIS_CAPABILITY_SUPPORTED,
                severity=PreflightSeverity.WARNING,
                message="Geometry path is experimental.",
            ),
        ),
    )

    assert report.disposition is PreflightDisposition.PASS
    assert report.can_proceed is True
    assert report.blocking_findings == ()
    assert len(report.warnings) == 1


def test_preflight_report_blocks_on_error() -> None:
    finding = PreflightFinding(
        code=PreflightRuleCode.BOLT_LENGTH_FEASIBLE,
        severity=PreflightSeverity.ERROR,
        message="Bolt length is insufficient.",
    )

    report = PreflightReport(
        case_hash="abc123",
        target=PreflightTarget.GEOMETRY,
        support_status=CaseSupportStatus.UNSUPPORTED,
        findings=(finding,),
    )

    assert report.disposition is PreflightDisposition.BLOCKED
    assert report.can_proceed is False
    assert report.blocking_findings == (finding,)


def test_warning_does_not_hide_blocking_error() -> None:
    warning = PreflightFinding(
        code=PreflightRuleCode.FRICTION_ENVELOPE_SUPPORTED,
        severity=PreflightSeverity.WARNING,
        message="Friction value is outside the certified envelope.",
    )
    error = PreflightFinding(
        code=PreflightRuleCode.PRODUCT_TOPOLOGY_SUPPORTED,
        severity=PreflightSeverity.ERROR,
        message="Requested topology is unsupported.",
    )

    report = PreflightReport(
        case_hash="abc123",
        target=PreflightTarget.FEM,
        support_status=CaseSupportStatus.UNSUPPORTED,
        findings=(warning, error),
    )

    assert report.blocking_findings == (error,)
    assert report.warnings == (warning,)
    assert report.disposition is PreflightDisposition.BLOCKED


def test_empty_finding_message_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="Preflight finding message must not be empty",
    ):
        PreflightFinding(
            code=PreflightRuleCode.MATERIAL_DATA_AVAILABLE,
            severity=PreflightSeverity.ERROR,
            message="   ",
        )


def test_empty_case_hash_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="Preflight case hash must not be empty",
    ):
        PreflightReport(
            case_hash="",
            target=PreflightTarget.RESOLUTION,
            support_status=CaseSupportStatus.EXPERIMENTAL,
        )
