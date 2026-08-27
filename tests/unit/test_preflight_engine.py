from __future__ import annotations

from dataclasses import replace

import pytest

from threadrom.case import CaseSupportStatus
from threadrom.case.preflight import (
    PreflightDisposition,
    PreflightRuleCode,
    PreflightTarget,
)
from threadrom.case.preflight_engine import preflight_case
from threadrom.case.reference_cases import phase2_certification_case


def test_reference_resolution_preflight_passes() -> None:
    report = preflight_case(
        phase2_certification_case(),
        PreflightTarget.RESOLUTION,
    )

    assert report.disposition is PreflightDisposition.PASS
    assert report.can_proceed is True
    assert report.findings == ()
    assert report.support_status is CaseSupportStatus.EXPERIMENTAL


def test_reference_geometry_preflight_passes() -> None:
    report = preflight_case(
        phase2_certification_case(),
        PreflightTarget.GEOMETRY,
    )

    assert report.disposition is PreflightDisposition.PASS
    assert report.can_proceed is True


def test_reference_fem_preflight_is_explicitly_blocked_until_cp4() -> None:
    report = preflight_case(
        phase2_certification_case(),
        PreflightTarget.FEM,
    )

    assert report.disposition is PreflightDisposition.BLOCKED
    assert report.can_proceed is False
    assert len(report.blocking_findings) == 1
    assert (
        report.blocking_findings[0].code
        is PreflightRuleCode.ANALYSIS_CAPABILITY_SUPPORTED
    )
    assert "CP4" in report.blocking_findings[0].message


def test_dimensionally_unsupported_standard_is_reported_not_crashed() -> None:
    case = phase2_certification_case()

    modified = replace(
        case,
        fastener=replace(
            case.fastener,
            bolt_standard="ISO 4014:2022",
        ),
    )

    report = preflight_case(
        modified,
        PreflightTarget.RESOLUTION,
    )

    assert report.disposition is PreflightDisposition.BLOCKED
    assert any(
        finding.code
        is PreflightRuleCode.STANDARD_DIMENSIONS_AVAILABLE
        for finding in report.blocking_findings
    )


def test_multiple_static_failures_are_collected_in_stable_order() -> None:
    case = phase2_certification_case()
    upper, lower = case.members.layers

    modified = replace(
        case,
        fastener=replace(
            case.fastener,
            bolt_length_mm=27.0,
            bolt_material_id="unknown_material",
        ),
        members=replace(
            case.members,
            layers=(
                upper,
                replace(
                    lower,
                    clearance_hole_diameter_mm=12.0,
                ),
            ),
        ),
    )

    report = preflight_case(
        modified,
        PreflightTarget.GEOMETRY,
    )

    assert report.disposition is PreflightDisposition.BLOCKED

    assert tuple(
        finding.code
        for finding in report.blocking_findings
    ) == (
        PreflightRuleCode.MATERIAL_DATA_AVAILABLE,
        PreflightRuleCode.PRODUCT_TOPOLOGY_SUPPORTED,
        PreflightRuleCode.BOLT_LENGTH_FEASIBLE,
    )


def test_negative_external_load_blocks_analytical_target() -> None:
    case = phase2_certification_case()

    modified = replace(
        case,
        loading=replace(
            case.loading,
            external_axial_load_n=-1000.0,
        ),
    )

    report = preflight_case(
        modified,
        PreflightTarget.ANALYTICAL,
    )

    assert report.disposition is PreflightDisposition.BLOCKED
    assert (
        report.blocking_findings[-1].code
        is PreflightRuleCode.ANALYSIS_CAPABILITY_SUPPORTED
    )


def test_preflight_is_deterministic() -> None:
    case = phase2_certification_case()

    first = preflight_case(
        case,
        PreflightTarget.FEM,
    )
    second = preflight_case(
        case,
        PreflightTarget.FEM,
    )

    assert first == second
