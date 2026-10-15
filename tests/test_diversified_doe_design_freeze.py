from __future__ import annotations

import hashlib
import json

from pathlib import Path

import pytest

from threadrom.factory.diversified_doe_design_freeze import (
    persist_design_freeze_certificate,
    recover_design_freeze_certificate,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def _make_sources(
    tmp_path: Path,
):
    root = tmp_path / "repo"
    root.mkdir()

    policy_path = (
        root / "policy.toml"
    )

    policy_path.write_text(
        """
[governance]
phase = 3
first_rom_phase = 4
dataset_admission_authorized = false
geometry_or_mesh_execution_authorized = false
sealed_holdout_access_authorized = false
solver_launch_authorized = false
surrogate_training_authorized = false
duplicate_accepted_case_rerun_forbidden = true
no_large_upfront_batch_authorization = true
no_post_hoc_acceptance_relaxation = true
preserve_failed_and_rejected_attempt_provenance = true
preserve_valid_realized_states = true
requested_and_realized_states_must_be_distinguished = true
reuse_existing_evidence_before_new_fem = true
""".lstrip(),
        encoding="utf-8",
    )

    atlas_path = (
        root / "atlas.json"
    )

    atlas = {
        "schema_version": 1,
        "distinct_case_count": 1,
        "acceptance_source_count": 1,
        "cases": [
            {
                "case_id": "HIST-1",
                "case_hash": "f" * 64,
            }
        ],
    }

    atlas_path.write_text(
        json.dumps(
            atlas,
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    rows = []

    for index in range(72):
        historical = (
            f"HIST-{index + 1}"
            if index < 14
            else None
        )

        rows.append(
            {
                "proposal_id": (
                    f"DOE-{index + 1:02d}"
                ),
                "case_hash": (
                    f"{index + 1:064x}"
                ),
                "historical_case_id": historical,
                "fem_execution_authorized": False,
                "dataset_admission_status": (
                    "NOT_EVALUATED"
                ),
            }
        )

    proposal_path = (
        root / "proposal.json"
    )

    proposal = {
        "schema_version": 1,
        "campaign_id": "TEST-DDOE",
        "source_commit": "abc123",
        "design_frozen": False,
        "design_state_count": 72,
        "historical_reuse_candidates": 14,
        "new_design_states_requiring_evidence": 58,
        "validation_states": [
            f"sealed-{i}"
            for i in range(18)
        ],
        "fem_execution_authorized": False,
        "geometry_execution_authorized": False,
        "mesh_execution_authorized": False,
        "dataset_admission_authorized": False,
        "policy_sha256": _sha(
            policy_path
        ),
        "atlas_sha256": _sha(
            atlas_path
        ),
        "cases": rows,
    }

    proposal_path.write_text(
        json.dumps(
            proposal,
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    certificate_path = (
        root
        / "design_freeze_certificate.json"
    )

    return (
        proposal_path,
        policy_path,
        atlas_path,
        certificate_path,
    )


def test_freeze_persist_and_recover(
    tmp_path,
):
    (
        proposal,
        policy,
        atlas,
        certificate,
    ) = _make_sources(
        tmp_path
    )

    persist_design_freeze_certificate(
        proposal_path=proposal,
        policy_path=policy,
        atlas_path=atlas,
        certificate_path=certificate,
    )

    recovered = (
        recover_design_freeze_certificate(
            proposal_path=proposal,
            policy_path=policy,
            atlas_path=atlas,
            certificate_path=certificate,
        )
    )

    assert recovered is not None
    assert (
        recovered["design_status"]
        == "FROZEN_DESIGN"
    )
    assert (
        recovered["design_state_count"]
        == 72
    )
    assert (
        recovered[
            "fem_execution_authorized"
        ]
        is False
    )


def test_freeze_is_idempotent(
    tmp_path,
):
    (
        proposal,
        policy,
        atlas,
        certificate,
    ) = _make_sources(
        tmp_path
    )

    kwargs = dict(
        proposal_path=proposal,
        policy_path=policy,
        atlas_path=atlas,
        certificate_path=certificate,
    )

    first = (
        persist_design_freeze_certificate(
            **kwargs
        )
    )

    second = (
        persist_design_freeze_certificate(
            **kwargs
        )
    )

    assert first == second


def test_policy_drift_fails_recovery(
    tmp_path,
):
    (
        proposal,
        policy,
        atlas,
        certificate,
    ) = _make_sources(
        tmp_path
    )

    persist_design_freeze_certificate(
        proposal_path=proposal,
        policy_path=policy,
        atlas_path=atlas,
        certificate_path=certificate,
    )

    policy.write_text(
        policy.read_text(
            encoding="utf-8"
        )
        + "\n# changed\n",
        encoding="utf-8",
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "policy SHA"
            "|provenance"
        ),
    ):
        recover_design_freeze_certificate(
            proposal_path=proposal,
            policy_path=policy,
            atlas_path=atlas,
            certificate_path=certificate,
        )


def test_case_execution_authority_refused(
    tmp_path,
):
    (
        proposal,
        policy,
        atlas,
        certificate,
    ) = _make_sources(
        tmp_path
    )

    payload = json.loads(
        proposal.read_text(
            encoding="utf-8"
        )
    )

    payload["cases"][20][
        "fem_execution_authorized"
    ] = True

    proposal.write_text(
        json.dumps(
            payload,
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        RuntimeError,
        match="grants FEM execution",
    ):
        persist_design_freeze_certificate(
            proposal_path=proposal,
            policy_path=policy,
            atlas_path=atlas,
            certificate_path=certificate,
        )


def test_bulk_solver_authority_refused(
    tmp_path,
):
    (
        proposal,
        policy,
        atlas,
        certificate,
    ) = _make_sources(
        tmp_path
    )

    text = policy.read_text(
        encoding="utf-8"
    ).replace(
        "solver_launch_authorized = false",
        "solver_launch_authorized = true",
    )

    policy.write_text(
        text,
        encoding="utf-8",
    )

    with pytest.raises(
        RuntimeError,
        match="solver_launch_authorized",
    ):
        persist_design_freeze_certificate(
            proposal_path=proposal,
            policy_path=policy,
            atlas_path=atlas,
            certificate_path=certificate,
        )


def test_real_reserved_validation_string_representation(
    tmp_path,
):
    (
        proposal,
        policy,
        atlas,
        certificate,
    ) = _make_sources(
        tmp_path
    )

    payload = json.loads(
        proposal.read_text(
            encoding="utf-8"
        )
    )

    payload["validation_states"] = (
        "18 reserved; configurations not generated"
    )

    proposal.write_text(
        json.dumps(
            payload,
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    persist_design_freeze_certificate(
        proposal_path=proposal,
        policy_path=policy,
        atlas_path=atlas,
        certificate_path=certificate,
    )

    recovered = (
        recover_design_freeze_certificate(
            proposal_path=proposal,
            policy_path=policy,
            atlas_path=atlas,
            certificate_path=certificate,
        )
    )

    assert recovered is not None
    assert (
        recovered[
            "sealed_validation_state_count"
        ]
        == 18
    )
    assert (
        recovered[
            "sealed_holdout_access_authorized"
        ]
        is False
    )

