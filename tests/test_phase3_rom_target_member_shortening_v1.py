from __future__ import annotations

import hashlib
import json
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

CONTRACT = (
    ROOT
    / "docs"
    / "phase3_rom_targets"
    / "member_shortening_v1.target_contract.json"
)

SIDECAR = Path(
    str(CONTRACT) + ".sha256"
)

SUFFICIENCY = (
    ROOT
    / "config"
    / "phase3_dataset_sufficiency.toml"
)

EXTRACTOR = (
    ROOT
    / "src"
    / "threadrom"
    / "factory"
    / "fem_result_extraction.py"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def test_member_shortening_target_contract_is_frozen_and_pretraining() -> None:
    payload = json.loads(
        CONTRACT.read_text(
            encoding="utf-8"
        )
    )

    assert (
        payload["schema"]
        == "threadrom.rom_target_contract.v1"
    )

    assert (
        payload["contract_id"]
        == "TRM-ROM-TARGET-MEMBER-SHORTENING-V1"
    )

    assert (
        payload["target_status"]
        == "FROZEN_PRE_TRAINING"
    )

    target = payload["target"]

    assert target["response_id"] == "member_shortening"
    assert target["dataset_field"] == "member_shortening_mm"
    assert target["unit"] == "mm"

    assert (
        target["formula"]
        == (
            "mean_uz(head_bearing_nodes) "
            "- mean_uz(nut_bearing_nodes)"
        )
    )

    assert (
        payload["phase_boundary"]
        ["rom_training_authorized"]
        is False
    )

    assert (
        payload["phase_boundary"]
        ["dataset_admission_authorized"]
        is False
    )

    assert (
        payload["phase_boundary"]
        ["holdout_access_authorized"]
        is False
    )

    assert (
        payload["phase_boundary"]
        ["w04_execution_authorized"]
        is False
    )

    assert (
        payload["governance"]
        ["target_defined_before_model_training"]
        is True
    )

    assert (
        payload["governance"]
        ["sealed_holdouts_accessed"]
        is False
    )

    assert len(
        payload[
            "reference_proof"
        ][
            "realizations"
        ]
    ) == 4

    assert all(
        row[
            "member_shortening_mm"
        ]
        > 0.0
        for row in payload[
            "reference_proof"
        ][
            "realizations"
        ]
    )

    assert (
        SIDECAR
        .read_text(
            encoding="ascii"
        )
        .split()[0]
        == _sha256(CONTRACT)
    )


def test_member_shortening_accuracy_contract_matches_predeclared_policy() -> None:
    with SUFFICIENCY.open("rb") as stream:
        policy = tomllib.load(stream)

    response = next(
        item
        for item in policy["responses"]
        if item["response_id"]
        == "member_shortening"
    )

    payload = json.loads(
        CONTRACT.read_text(
            encoding="utf-8"
        )
    )

    accuracy = payload[
        "predeclared_accuracy"
    ]

    assert response[
        "dataset_field"
    ] == "member_shortening_mm"

    assert response["unit"] == "mm"

    assert (
        response[
            "numerical_certification_relative_limit"
        ]
        == accuracy[
            "numerical_certification"
        ][
            "relative_limit"
        ]
        == 0.02
    )

    assert (
        response[
            "cross_validation_rrmse_max"
        ]
        == accuracy[
            "cross_validation"
        ][
            "rrmse_max"
        ]
        == 0.01
    )

    assert (
        response[
            "cross_validation_max_absolute_relative_error"
        ]
        == accuracy[
            "cross_validation"
        ][
            "max_absolute_relative_error"
        ]
        == 0.02
    )

    assert (
        response[
            "blind_holdout_rrmse_max"
        ]
        == accuracy[
            "blind_holdout"
        ][
            "rrmse_max"
        ]
        == 0.015
    )

    assert (
        response[
            "blind_holdout_max_absolute_relative_error"
        ]
        == accuracy[
            "blind_holdout"
        ][
            "max_absolute_relative_error"
        ]
        == 0.02
    )


def test_member_shortening_extractor_semantics_remain_bound() -> None:
    payload = json.loads(
        CONTRACT.read_text(
            encoding="utf-8"
        )
    )

    assert (
        payload[
            "extraction"
        ][
            "implementation"
        ][
            "sha256"
        ]
        == _sha256(EXTRACTOR)
    )

    source = EXTRACTOR.read_text(
        encoding="utf-8"
    )

    assert "member_shortening_mm = (" in source
    assert "mean_uz(head_bearing_nodes)" in source
    assert "- mean_uz(nut_bearing_nodes)" in source