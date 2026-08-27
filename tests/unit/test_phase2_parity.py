"""Regression tests for the certified Phase-2 factory parity gate."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from threadrom.case.reference_cases import (
    phase2_certification_case,
)
from threadrom.case.resolver import resolve_case
from threadrom.factory.phase2_parity import (
    evaluate_phase2_parity,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

EXPECTED_PHASE2_PARITY_SHA256 = (
    "8ee3688c189098d35f7747b1c4f5a03feacb3deee562943809b92d46c0a6b048"
)


def test_certified_phase2_case_passes_factory_parity() -> None:
    case = phase2_certification_case()
    resolved = resolve_case(case)

    report = evaluate_phase2_parity(
        resolved,
        PROJECT_ROOT,
    )

    assert report.passed
    assert report.mismatches == ()

    assert (
        report.phase2_snapshot_sha256
        == EXPECTED_PHASE2_PARITY_SHA256
    )

    assert (
        report.phase3_snapshot_sha256
        == EXPECTED_PHASE2_PARITY_SHA256
    )


def test_phase2_parity_report_is_deterministic() -> None:
    resolved = resolve_case(
        phase2_certification_case()
    )

    first = evaluate_phase2_parity(
        resolved,
        PROJECT_ROOT,
    )

    second = evaluate_phase2_parity(
        resolved,
        PROJECT_ROOT,
    )

    assert first == second


def test_changed_bolt_length_fails_phase2_parity() -> None:
    case = phase2_certification_case()

    changed = replace(
        case,
        fastener=replace(
            case.fastener,
            bolt_length_mm=35.0,
        ),
    )

    resolved = resolve_case(changed)

    report = evaluate_phase2_parity(
        resolved,
        PROJECT_ROOT,
    )

    assert not report.passed
    assert report.phase3_snapshot_sha256 != (
        report.phase2_snapshot_sha256
    )
    assert report.mismatches

    assert any(
        mismatch.startswith(
            "analytical.bolt.nominal_length_mm:"
        )
        for mismatch in report.mismatches
    )

    assert any(
        mismatch.startswith(
            "geometry.bolt_blank.underhead_length_mm:"
        )
        for mismatch in report.mismatches
    )
