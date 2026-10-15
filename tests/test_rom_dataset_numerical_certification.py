from __future__ import annotations

import pytest

from threadrom.factory.rom_dataset_numerical_certification import (
    NumericalCertificationDecision,
    evaluate_rom_numerical_certification,
)


def authority() -> dict:
    return {
        "schema": (
            "threadrom.rom_numerical_certification_authority.v1"
        ),
        "record_status": "FINAL",
        "authority_id": "UNIT-NUMCERT",
        "target_field": "member_shortening_mm",
        "relative_limit": 0.02,
        "governance": {
            "absence_of_authority_defers": True,
            "extrapolation_forbidden": True,
        },
        "certifications": [
            {
                "certification_id": "PASS-1",
                "decision": "PASS",
                "match": {
                    "case_id": "CASE-1",
                    "case_hash": "a" * 64,
                    "mesh_policy_name": "medium_plus_v1",
                },
                "relative_limit": 0.02,
                "extrapolation_authorized": False,
            },
            {
                "certification_id": "REJECT-1",
                "decision": "REJECTED",
                "match": {
                    "case_id": "CASE-1",
                    "case_hash": "a" * 64,
                    "mesh_policy_name": "medium",
                },
            },
        ],
    }


def test_exact_positive_authority_passes() -> None:
    result = evaluate_rom_numerical_certification(
        case_id="CASE-1",
        case_hash="a" * 64,
        mesh_policy_name="medium_plus_v1",
        target_field="member_shortening_mm",
        authority=authority(),
    )

    assert (
        result.decision
        is NumericalCertificationDecision.PASS
    )


def test_exact_negative_authority_rejects() -> None:
    result = evaluate_rom_numerical_certification(
        case_id="CASE-1",
        case_hash="a" * 64,
        mesh_policy_name="medium",
        target_field="member_shortening_mm",
        authority=authority(),
    )

    assert (
        result.decision
        is NumericalCertificationDecision.REJECTED
    )


def test_uncovered_case_defers() -> None:
    result = evaluate_rom_numerical_certification(
        case_id="OTHER",
        case_hash="b" * 64,
        mesh_policy_name="medium_plus_v1",
        target_field="member_shortening_mm",
        authority=authority(),
    )

    assert (
        result.decision
        is NumericalCertificationDecision.DEFERRED
    )

    assert (
        result.reason_code
        == "NO_APPLICABLE_CERTIFICATION_AUTHORITY"
    )


def test_missing_identity_defers() -> None:
    result = evaluate_rom_numerical_certification(
        case_id=None,
        case_hash="a" * 64,
        mesh_policy_name="medium_plus_v1",
        target_field="member_shortening_mm",
        authority=authority(),
    )

    assert (
        result.decision
        is NumericalCertificationDecision.DEFERRED
    )


def test_target_mismatch_fails_closed() -> None:
    with pytest.raises(
        ValueError,
        match="target field",
    ):
        evaluate_rom_numerical_certification(
            case_id="CASE-1",
            case_hash="a" * 64,
            mesh_policy_name="medium_plus_v1",
            target_field="other_target",
            authority=authority(),
        )


def test_nonfinal_authority_fails_closed() -> None:
    record = authority()
    record["record_status"] = "DRAFT"

    with pytest.raises(
        ValueError,
        match="FINAL",
    ):
        evaluate_rom_numerical_certification(
            case_id="CASE-1",
            case_hash="a" * 64,
            mesh_policy_name="medium_plus_v1",
            target_field="member_shortening_mm",
            authority=record,
        )


def test_pass_authority_must_match_relative_limit() -> None:
    record = authority()

    record[
        "certifications"
    ][0][
        "relative_limit"
    ] = 0.03

    with pytest.raises(
        ValueError,
        match="relative limit",
    ):
        evaluate_rom_numerical_certification(
            case_id="CASE-1",
            case_hash="a" * 64,
            mesh_policy_name="medium_plus_v1",
            target_field="member_shortening_mm",
            authority=record,
        )


def test_duplicate_exact_authorities_fail_closed() -> None:
    record = authority()

    duplicate = dict(
        record[
            "certifications"
        ][0]
    )

    duplicate[
        "certification_id"
    ] = "PASS-2"

    record[
        "certifications"
    ].append(
        duplicate
    )

    with pytest.raises(
        ValueError,
        match="Ambiguous",
    ):
        evaluate_rom_numerical_certification(
            case_id="CASE-1",
            case_hash="a" * 64,
            mesh_policy_name="medium_plus_v1",
            target_field="member_shortening_mm",
            authority=record,
        )
