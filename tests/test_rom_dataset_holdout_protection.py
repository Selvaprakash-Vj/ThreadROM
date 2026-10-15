from __future__ import annotations

import hashlib
import json

from pathlib import Path

import pytest

from threadrom.factory.rom_dataset_holdout_protection import (
    HoldoutProtectionDecision,
    RomDatasetHoldoutProtectionError,
    evaluate_member_shortening_holdout_protection,
)


def _sha256(
    path: Path,
) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def _secret_ids() -> tuple[str, ...]:
    return (
        "TEST-SEALED-01",
        "TEST-SEALED-02",
        "TEST-SEALED-03",
        "TEST-SEALED-04",
        "TEST-SEALED-05",
        "TEST-SEALED-06",
    )


def _write_fixture(
    root: Path,
    *,
    atlas_case_id: str,
    atlas_case_hash: str,
    holdout_ids: tuple[str, ...],
    dataset_partition=None,
) -> tuple[
    Path,
    Path,
]:
    atlas_path = (
        root
        / "docs"
        / "phase3_fem_atlas"
        / "atlas.json"
    )

    policy_path = (
        root
        / "config"
        / "phase3_production_doe.toml"
    )

    atlas_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    policy_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    atlas = {
        "cases": [
            {
                "case_id":
                    atlas_case_id,

                "case_hash":
                    atlas_case_hash,

                "dataset_partition":
                    dataset_partition,
            }
        ]
    }

    atlas_path.write_text(
        json.dumps(
            atlas
        ),
        encoding="utf-8",
    )

    lines = [
        "[holdouts]",
        (
            "minimum_design_to_holdout_"
            "normalized_euclidean_distance = 0.1"
        ),
        "",
    ]

    for index, private_id in enumerate(
        holdout_ids,
        start=1,
    ):
        lines.extend(
            [
                "[[holdouts.points]]",
                f'case_id = "{private_id}"',
                (
                    "normalized_coordinates = "
                    f"[0.{index}, 0.5, 0.5]"
                ),
                "",
            ]
        )

    policy_path.write_text(
        "\n".join(
            lines
        ),
        encoding="utf-8",
    )

    return (
        atlas_path,
        policy_path,
    )


def test_registered_non_holdout_allows_source_inspection(
    tmp_path: Path,
) -> None:
    case_hash = (
        "1" * 64
    )

    atlas_path, policy_path = (
        _write_fixture(
            tmp_path,
            atlas_case_id=(
                "TEST-ACCEPTED-01"
            ),
            atlas_case_hash=(
                case_hash
            ),
            holdout_ids=(
                _secret_ids()
            ),
        )
    )

    result = (
        evaluate_member_shortening_holdout_protection(
            repo_root=tmp_path,
            expected_atlas_sha256=(
                _sha256(
                    atlas_path
                )
            ),
            expected_policy_sha256=(
                _sha256(
                    policy_path
                )
            ),
            case_id="TEST-ACCEPTED-01",
            case_hash=case_hash,
        )
    )

    assert result is (
        HoldoutProtectionDecision
        .SOURCE_INSPECTION_ALLOWED
    )


def test_registered_holdout_is_protected(
    tmp_path: Path,
) -> None:
    case_hash = (
        "2" * 64
    )

    protected_id = (
        _secret_ids()[
            2
        ]
    )

    atlas_path, policy_path = (
        _write_fixture(
            tmp_path,
            atlas_case_id=(
                protected_id
            ),
            atlas_case_hash=(
                case_hash
            ),
            holdout_ids=(
                _secret_ids()
            ),
        )
    )

    result = (
        evaluate_member_shortening_holdout_protection(
            repo_root=tmp_path,
            expected_atlas_sha256=(
                _sha256(
                    atlas_path
                )
            ),
            expected_policy_sha256=(
                _sha256(
                    policy_path
                )
            ),
            case_id=protected_id,
            case_hash=case_hash,
        )
    )

    assert result is (
        HoldoutProtectionDecision
        .SEALED_HOLDOUT_PROTECTED
    )


def test_unregistered_identity_cannot_probe_oracle(
    tmp_path: Path,
) -> None:
    atlas_path, policy_path = (
        _write_fixture(
            tmp_path,
            atlas_case_id=(
                "TEST-ACCEPTED-01"
            ),
            atlas_case_hash=(
                "3" * 64
            ),
            holdout_ids=(
                _secret_ids()
            ),
        )
    )

    with pytest.raises(
        RomDatasetHoldoutProtectionError,
        match=(
            "not an exact registered "
            "accepted FEM Atlas identity"
        ),
    ):
        evaluate_member_shortening_holdout_protection(
            repo_root=tmp_path,
            expected_atlas_sha256=(
                _sha256(
                    atlas_path
                )
            ),
            expected_policy_sha256=(
                _sha256(
                    policy_path
                )
            ),
            case_id="ARBITRARY-PROBE",
            case_hash="4" * 64,
        )


def test_atlas_sha_drift_fails_closed(
    tmp_path: Path,
) -> None:
    case_hash = (
        "5" * 64
    )

    _, policy_path = (
        _write_fixture(
            tmp_path,
            atlas_case_id=(
                "TEST-ACCEPTED-01"
            ),
            atlas_case_hash=(
                case_hash
            ),
            holdout_ids=(
                _secret_ids()
            ),
        )
    )

    with pytest.raises(
        RomDatasetHoldoutProtectionError,
        match="Atlas SHA-256 drift",
    ):
        evaluate_member_shortening_holdout_protection(
            repo_root=tmp_path,
            expected_atlas_sha256=(
                "0" * 64
            ),
            expected_policy_sha256=(
                _sha256(
                    policy_path
                )
            ),
            case_id="TEST-ACCEPTED-01",
            case_hash=case_hash,
        )


def test_policy_sha_drift_fails_closed(
    tmp_path: Path,
) -> None:
    case_hash = (
        "6" * 64
    )

    atlas_path, _ = (
        _write_fixture(
            tmp_path,
            atlas_case_id=(
                "TEST-ACCEPTED-01"
            ),
            atlas_case_hash=(
                case_hash
            ),
            holdout_ids=(
                _secret_ids()
            ),
        )
    )

    with pytest.raises(
        RomDatasetHoldoutProtectionError,
        match="policy SHA-256 drift",
    ):
        evaluate_member_shortening_holdout_protection(
            repo_root=tmp_path,
            expected_atlas_sha256=(
                _sha256(
                    atlas_path
                )
            ),
            expected_policy_sha256=(
                "0" * 64
            ),
            case_id="TEST-ACCEPTED-01",
            case_hash=case_hash,
        )


def test_partitioned_candidate_fails_closed(
    tmp_path: Path,
) -> None:
    case_hash = (
        "7" * 64
    )

    atlas_path, policy_path = (
        _write_fixture(
            tmp_path,
            atlas_case_id=(
                "TEST-ACCEPTED-01"
            ),
            atlas_case_hash=(
                case_hash
            ),
            holdout_ids=(
                _secret_ids()
            ),
            dataset_partition=(
                "TRAINING"
            ),
        )
    )

    with pytest.raises(
        RomDatasetHoldoutProtectionError,
        match="partition boundary",
    ):
        evaluate_member_shortening_holdout_protection(
            repo_root=tmp_path,
            expected_atlas_sha256=(
                _sha256(
                    atlas_path
                )
            ),
            expected_policy_sha256=(
                _sha256(
                    policy_path
                )
            ),
            case_id="TEST-ACCEPTED-01",
            case_hash=case_hash,
        )


def test_holdout_count_drift_fails_closed(
    tmp_path: Path,
) -> None:
    case_hash = (
        "8" * 64
    )

    atlas_path, policy_path = (
        _write_fixture(
            tmp_path,
            atlas_case_id=(
                "TEST-ACCEPTED-01"
            ),
            atlas_case_hash=(
                case_hash
            ),
            holdout_ids=(
                _secret_ids()[
                    :-1
                ]
            ),
        )
    )

    with pytest.raises(
        RomDatasetHoldoutProtectionError,
        match=(
            "point authority is invalid"
        ),
    ):
        evaluate_member_shortening_holdout_protection(
            repo_root=tmp_path,
            expected_atlas_sha256=(
                _sha256(
                    atlas_path
                )
            ),
            expected_policy_sha256=(
                _sha256(
                    policy_path
                )
            ),
            case_id="TEST-ACCEPTED-01",
            case_hash=case_hash,
        )


def test_public_decision_surface_is_binary() -> None:
    assert {
        item.value
        for item in HoldoutProtectionDecision
    } == {
        "SOURCE_INSPECTION_ALLOWED",
        "SEALED_HOLDOUT_PROTECTED",
    }