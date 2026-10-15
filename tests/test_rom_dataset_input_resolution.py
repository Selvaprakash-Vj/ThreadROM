from __future__ import annotations

import json

from pathlib import Path

import pytest

from threadrom.factory.rom_dataset_input_resolution import (
    CANONICAL_DA04_FIELDS,
    PILOT_CASE_ID,
    RomDatasetInputResolutionError,
    resolve_rom_engineering_inputs,
)


ROOT = Path(
    __file__
).resolve().parents[1]


ATLAS_PATH = (
    ROOT
    / "docs"
    / "phase3_fem_atlas"
    / "atlas.json"
)


ADMISSION_CONTRACT_PATH = (
    ROOT
    / "docs"
    / "phase3_rom_dataset_admission"
    / "member_shortening_v1.admission_contract.json"
)


def read_json(
    path: Path,
) -> dict:
    return json.loads(
        path.read_text(
            encoding="utf-8-sig"
        )
    )


def adapter_pending_rows() -> list[dict]:
    atlas = read_json(
        ATLAS_PATH
    )

    return [
        row
        for row in atlas[
            "cases"
        ]
        if (
            row[
                "engineering_inputs"
            ].get(
                "configuration_status"
            )
            == "NEW_CAMPAIGN_INPUT_ADAPTER_REQUIRED"
        )
    ]


def test_canonical_da04_fields_match_frozen_admission_contract():
    contract = read_json(
        ADMISSION_CONTRACT_PATH
    )

    required = tuple(
        contract[
            "canonical_sample_schema"
        ][
            "engineering_inputs"
        ][
            "minimum_semantic_fields"
        ]
    )

    assert (
        CANONICAL_DA04_FIELDS
        == required
    )


def test_all_17_adapter_pending_cases_resolve_hash_exactly():
    rows = adapter_pending_rows()

    assert len(rows) == 17

    seen = set()

    for row in rows:
        case_id = row[
            "case_id"
        ]

        case_hash = row[
            "case_hash"
        ]

        result = (
            resolve_rom_engineering_inputs(
                repo_root=ROOT,
                case_id=case_id,
                expected_case_hash=(
                    case_hash
                ),
            )
        )

        assert result.case_id == case_id
        assert result.case_hash == case_hash

        assert (
            tuple(
                result.engineering_inputs
            )
            == CANONICAL_DA04_FIELDS
        )

        assert all(
            value is not None
            for value
            in result.engineering_inputs.values()
        )

        assert (
            len(
                result.normalized_coordinates
            )
            == 3
        )

        seen.add(
            result.source_kind
        )

    assert seen == {
        "GOVERNED_WAVE_PLAN",
        "HISTORICAL_DIVERSIFIED_PILOT_HASH_RECOVERY",
    }


def test_historical_pilot_recovers_expected_point_and_inputs():
    row = next(
        item
        for item in adapter_pending_rows()
        if item[
            "case_id"
        ]
        == PILOT_CASE_ID
    )

    result = (
        resolve_rom_engineering_inputs(
            repo_root=ROOT,
            case_id=row[
                "case_id"
            ],
            expected_case_hash=row[
                "case_hash"
            ],
        )
    )

    assert (
        result.normalized_coordinates
        == (
            0.0,
            0.0,
            0.0,
        )
    )

    inputs = result.engineering_inputs

    assert (
        inputs[
            "thread_designation"
        ]
        == "M10x1.5"
    )

    assert (
        inputs[
            "head_member_material_id"
        ]
        == "member_aluminium_en_aw_6082_t6"
    )

    assert (
        inputs[
            "nut_member_material_id"
        ]
        == "member_aluminium_en_aw_6082_t6"
    )

    assert (
        inputs[
            "target_preload_n"
        ]
        == pytest.approx(
            15000.0
        )
    )


def test_wrong_frozen_hash_fails_closed():
    row = next(
        item
        for item in adapter_pending_rows()
        if item[
            "case_id"
        ]
        != PILOT_CASE_ID
    )

    with pytest.raises(
        RomDatasetInputResolutionError
    ):
        resolve_rom_engineering_inputs(
            repo_root=ROOT,
            case_id=row[
                "case_id"
            ],
            expected_case_hash=(
                "0" * 64
            ),
        )


def test_unknown_case_has_no_implicit_inference_path():
    with pytest.raises(
        RomDatasetInputResolutionError,
        match="no governed ROM engineering-input authority",
    ):
        resolve_rom_engineering_inputs(
            repo_root=ROOT,
            case_id="TRM-DDOE-NOT-A-REAL-CASE",
            expected_case_hash=(
                "1" * 64
            ),
        )