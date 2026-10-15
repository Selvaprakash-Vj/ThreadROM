from __future__ import annotations

import hashlib
import json
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

CONTRACT = (
    ROOT
    / "docs"
    / "phase3_rom_dataset_admission"
    / "member_shortening_v1.admission_contract.json"
)

SIDECAR = Path(
    str(CONTRACT) + ".sha256"
)

TARGET = (
    ROOT
    / "docs"
    / "phase3_rom_targets"
    / "member_shortening_v1.target_contract.json"
)

SUFFICIENCY = (
    ROOT
    / "config"
    / "phase3_dataset_sufficiency.toml"
)

ATLAS = (
    ROOT
    / "docs"
    / "phase3_fem_atlas"
    / "atlas.json"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def _contract() -> dict:
    return json.loads(
        CONTRACT.read_text(
            encoding="utf-8"
        )
    )


def test_admission_contract_is_frozen_before_any_row_admission() -> None:
    payload = _contract()

    assert (
        payload["schema"]
        == "threadrom.rom_dataset_admission_contract.v1"
    )

    assert payload["record_status"] == "FINAL"

    assert (
        payload["contract_status"]
        == "FROZEN_PRE_ADMISSION"
    )

    assert (
        payload["target_binding"]["sha256"]
        == _sha256(TARGET)
    )

    assert (
        payload["current_state_boundary"]
        ["currently_admitted_rows"]
        == 0
    )

    assert (
        payload["current_state_boundary"]
        ["currently_partitioned_rows"]
        == 0
    )

    assert (
        payload["governance"]
        ["dataset_admission_performed"]
        is False
    )

    assert (
        payload["governance"]
        ["partition_assignment_performed"]
        is False
    )

    assert (
        payload["governance"]
        ["rom_training_performed"]
        is False
    )

    assert (
        payload["governance"]
        ["w04_execution_authorized"]
        is False
    )

    assert (
        SIDECAR
        .read_text(
            encoding="ascii"
        )
        .split()[0]
        == _sha256(CONTRACT)
    )


def test_canonical_sample_schema_has_required_boundaries() -> None:
    payload = _contract()

    schema = payload[
        "canonical_sample_schema"
    ]

    assert (
        schema["schema"]
        == "threadrom.rom_dataset_sample.v1"
    )

    assert schema[
        "engineering_inputs"
    ][
        "unresolved_or_placeholder_inputs_forbidden"
    ] is True

    assert (
        schema["target"]["field"]
        == "member_shortening_mm"
    )

    assert schema[
        "validation"
    ][
        "full_physics_acceptance_required"
    ] is True

    assert schema[
        "validation"
    ][
        "target_specific_numerical_certification_required"
    ] is True

    assert (
        schema["validation"]
        ["numerical_certification_relative_limit"]
        == 0.02
    )

    assert (
        schema["partition"]
        ["value_at_admission"]
        is None
    )

    assert schema[
        "partition"
    ][
        "assignment_is_separate_governed_action"
    ] is True


def test_admission_contract_preserves_holdout_and_partition_independence() -> None:
    payload = _contract()

    assert (
        len(
            payload["admission_gates"]
        )
        == 12
    )

    gate_ids = {
        gate["gate_id"]
        for gate in payload[
            "admission_gates"
        ]
    }

    assert "DA11_HOLDOUT_PROTECTION" in gate_ids
    assert "DA12_PARTITION_BOUNDARY" in gate_ids

    assert (
        payload["holdout_governance"]
        ["sealed_holdouts"]
        == 6
    )

    assert (
        payload["holdout_governance"]
        ["access_authorized"]
        is False
    )

    assert (
        payload["partition_boundary"]
        ["admission_assigns_partition"]
        is False
    )


def test_admission_accuracy_and_dataset_population_match_predeclared_policy() -> None:
    with SUFFICIENCY.open("rb") as stream:
        policy = tomllib.load(stream)

    payload = _contract()

    response = next(
        row
        for row in policy["responses"]
        if row["response_id"]
        == "member_shortening"
    )

    assert (
        payload["canonical_sample_schema"]
        ["validation"]
        ["numerical_certification_relative_limit"]
        == response[
            "numerical_certification_relative_limit"
        ]
        == 0.02
    )

    assert (
        payload["dataset_population_requirements"]
        ["required_training_rows"]
        == policy["dataset"]["required_training_rows"]
        == 24
    )

    assert (
        payload["dataset_population_requirements"]
        ["required_blind_holdout_rows"]
        == policy["dataset"]["required_blind_holdout_rows"]
        == 6
    )


def test_contract_creation_did_not_retroactively_admit_live_atlas() -> None:
    atlas = json.loads(
        ATLAS.read_text(
            encoding="utf-8-sig"
        )
    )

    # The live FEM Atlas may grow after this contract was created.
    # The invariant here is admission/partition non-mutation, not a
    # permanently frozen live-Atlas row count.
    assert atlas["cases"]

    assert all(
        row["rom_admission_status"]
        == "NOT_EVALUATED"
        for row in atlas["cases"]
    )

    assert all(
        row["dataset_partition"] is None
        for row in atlas["cases"]
    )