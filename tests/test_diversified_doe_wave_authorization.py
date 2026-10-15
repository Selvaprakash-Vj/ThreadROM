from __future__ import annotations

import hashlib
import json

from pathlib import Path

import pytest

from threadrom.factory.diversified_doe_wave_authorization import (
    persist_wave_trial1_authorization,
    recover_wave_trial1_authorization,
)


def _write_json(
    path: Path,
    value,
):
    path.write_text(
        json.dumps(
            value,
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _sha(
    path: Path,
):
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def _sources(
    tmp_path: Path,
):
    policy = (
        tmp_path
        / "policy.toml"
    )

    policy.write_text(
        """
[governance]
solver_launch_authorized = false
dataset_admission_authorized = false
sealed_holdout_access_authorized = false
no_large_upfront_batch_authorization = true
""".lstrip(),
        encoding="utf-8",
    )

    freeze = (
        tmp_path
        / "freeze.json"
    )

    _write_json(
        freeze,
        {
            "design_status":
                "FROZEN_DESIGN",
            "design_state_count":
                72,
            "fem_execution_authorized":
                False,
            "dataset_admission_authorized":
                False,
            "sealed_holdout_access_authorized":
                False,
            "surrogate_training_authorized":
                False,
        },
    )

    rows = []

    for index in range(4):
        case_run = (
            "trm_fem_"
            + f"{index + 1:012x}"
        )

        rows.append(
            {
                "wave_order":
                    index + 1,
                "proposal_id":
                    f"CASE-{index + 1}",
                "case_hash":
                    f"{index + 1:064x}",
                "preparation_run_id":
                    case_run,
                "trial_1_run_id":
                    case_run + "_cal_01",
            }
        )

    wave = (
        tmp_path
        / "wave.json"
    )

    _write_json(
        wave,
        {
            "record_status":
                "FINAL",
            "campaign_id":
                "TRM-DDOE-001",
            "wave_id":
                "TRM-DDOE-001-W01",
            "selection_status":
                "FROZEN_SELECTION",
            "wave_size":
                4,
            "initial_trial_index":
                1,
            "maximum_concurrent_solver_slots":
                4,
            "design_freeze_certificate_sha256":
                _sha(freeze),
            "policy_sha256":
                _sha(policy),
            "selected_cases":
                rows,
            "preparation_authorized":
                False,
            "fem_execution_authorized":
                False,
            "adaptive_continuation_authorized":
                False,
            "dataset_admission_authorized":
                False,
            "full_physics_certification_authorized":
                False,
            "artifact_retirement_authorized":
                False,
            "holdout_access_authorized":
                False,
            "holdout_configurations_generated":
                False,
        },
    )

    auth = (
        tmp_path
        / "authorization.json"
    )

    return (
        policy,
        freeze,
        wave,
        auth,
    )


def _kwargs(
    tmp_path,
):
    (
        policy,
        freeze,
        wave,
        auth,
    ) = _sources(
        tmp_path
    )

    return {
        "wave_plan_path":
            wave,
        "design_freeze_certificate_path":
            freeze,
        "policy_path":
            policy,
        "authorization_path":
            auth,
        "approved_by":
            "Selva - ThreadROM project owner",
        "approval_date":
            "2026-09-28",
    }


def test_persist_and_recover(
    tmp_path,
):
    kwargs = _kwargs(
        tmp_path
    )

    persist_wave_trial1_authorization(
        **kwargs
    )

    record = (
        recover_wave_trial1_authorization(
            **kwargs
        )
    )

    assert record is not None

    assert (
        len(
            record[
                "authorized_cases"
            ]
        )
        == 4
    )

    assert (
        record[
            "permissions"
        ][
            "execute_trial_1"
        ]
        is True
    )

    assert (
        record[
            "permissions"
        ][
            "adaptive_continuation"
        ]
        is False
    )

    assert (
        record[
            "permissions"
        ][
            "holdout_access"
        ]
        is False
    )


def test_is_idempotent(
    tmp_path,
):
    kwargs = _kwargs(
        tmp_path
    )

    first = (
        persist_wave_trial1_authorization(
            **kwargs
        )
    )

    second = (
        persist_wave_trial1_authorization(
            **kwargs
        )
    )

    assert first == second


def test_wave_drift_fails_recovery(
    tmp_path,
):
    kwargs = _kwargs(
        tmp_path
    )

    persist_wave_trial1_authorization(
        **kwargs
    )

    wave = kwargs[
        "wave_plan_path"
    ]

    wave.write_text(
        wave.read_text(
            encoding="utf-8"
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "authorization provenance"
            "|SHA mismatch"
        ),
    ):
        recover_wave_trial1_authorization(
            **kwargs
        )


def test_trial2_substitution_refused(
    tmp_path,
):
    kwargs = _kwargs(
        tmp_path
    )

    wave = kwargs[
        "wave_plan_path"
    ]

    payload = json.loads(
        wave.read_text(
            encoding="utf-8"
        )
    )

    payload[
        "selected_cases"
    ][0][
        "trial_1_run_id"
    ] = (
        payload[
            "selected_cases"
        ][0][
            "preparation_run_id"
        ]
        + "_cal_02"
    )

    _write_json(
        wave,
        payload,
    )

    with pytest.raises(
        RuntimeError,
        match="non-Trial-1",
    ):
        persist_wave_trial1_authorization(
            **kwargs
        )


def test_source_wave_authority_refused(
    tmp_path,
):
    kwargs = _kwargs(
        tmp_path
    )

    wave = kwargs[
        "wave_plan_path"
    ]

    payload = json.loads(
        wave.read_text(
            encoding="utf-8"
        )
    )

    payload[
        "fem_execution_authorized"
    ] = True

    _write_json(
        wave,
        payload,
    )

    with pytest.raises(
        RuntimeError,
        match="unexpectedly grants authority",
    ):
        persist_wave_trial1_authorization(
            **kwargs
        )
