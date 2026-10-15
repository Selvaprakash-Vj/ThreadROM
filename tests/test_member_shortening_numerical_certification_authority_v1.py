from __future__ import annotations

import hashlib
import json

from pathlib import Path

from threadrom.factory.rom_dataset_numerical_certification import (
    NumericalCertificationDecision,
    evaluate_rom_numerical_certification,
)


ROOT = Path(__file__).resolve().parents[1]

AUTHORITY = (
    ROOT
    / "docs"
    / "phase3_rom_dataset_admission"
    / "member_shortening_v1.numerical_certification_authority.json"
)

QUALITY = (
    ROOT
    / "simulations"
    / "staging"
    / "phase3_cp8_p04"
    / "trm_fem_ae87c6fcba11"
    / "mesh"
    / "complete_joint_grouped_medium_plus_v1_quality.json"
)


def load_authority() -> dict:
    return json.loads(
        AUTHORITY.read_text(
            encoding="utf-8"
        )
    )


def load_quality() -> dict:
    return json.loads(
        QUALITY.read_text(
            encoding="utf-8"
        )
    )


def test_real_authority_is_final_narrow_and_nonextrapolating() -> None:
    authority = load_authority()

    assert (
        authority["record_status"]
        == "FINAL"
    )

    assert (
        authority["target_field"]
        == "member_shortening_mm"
    )

    assert (
        authority["relative_limit"]
        == 0.02
    )

    assert (
        authority[
            "governance"
        ][
            "extrapolation_forbidden"
        ]
        is True
    )

    assert (
        authority[
            "governance"
        ][
            "absence_of_authority_defers"
        ]
        is True
    )


def test_real_p04_medium_plus_exact_identity_passes() -> None:
    authority = load_authority()
    quality = load_quality()

    result = evaluate_rom_numerical_certification(
        case_id=quality[
            "case_id"
        ],
        case_hash=quality[
            "case_hash"
        ],
        mesh_policy_name="medium_plus_v1",
        target_field="member_shortening_mm",
        authority=authority,
    )

    assert (
        result.decision
        is NumericalCertificationDecision.PASS
    )


def test_real_p04_base_medium_exact_identity_rejects() -> None:
    authority = load_authority()
    quality = load_quality()

    result = evaluate_rom_numerical_certification(
        case_id=quality[
            "case_id"
        ],
        case_hash=quality[
            "case_hash"
        ],
        mesh_policy_name="medium",
        target_field="member_shortening_mm",
        authority=authority,
    )

    assert (
        result.decision
        is NumericalCertificationDecision.REJECTED
    )


def test_real_authority_does_not_generalize_to_other_case() -> None:
    authority = load_authority()

    result = evaluate_rom_numerical_certification(
        case_id="TRM-DDOE-SYNTHETIC",
        case_hash="f" * 64,
        mesh_policy_name="medium_plus_v1",
        target_field="member_shortening_mm",
        authority=authority,
    )

    assert (
        result.decision
        is NumericalCertificationDecision.DEFERRED
    )


def test_authority_sidecar_matches() -> None:
    expected = Path(
        str(AUTHORITY)
        + ".sha256"
    ).read_text(
        encoding="ascii"
    ).strip()

    actual = hashlib.sha256(
        AUTHORITY.read_bytes()
    ).hexdigest()

    assert expected == actual
