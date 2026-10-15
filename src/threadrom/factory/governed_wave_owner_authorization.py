"""Generic owner-authorization validation for governed DOE waves.

Historical owner-authorizations are immutable evidence and are not rewritten.

Two equivalent historical duplicate-execution declarations exist:

- duplicate_solver_execution_forbidden
- duplicate_trial_1_execution_forbidden_if_valid_result_exists

The generic factory accepts either pinned historical declaration while runtime
execution remains stricter: existing valid solved evidence must always be
reused rather than duplicated.
"""

from __future__ import annotations

import hashlib
import json

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from threadrom.factory.governed_wave_contract import (
    GovernedWaveExecutionContract,
)


class GovernedWaveAuthorizationError(
    RuntimeError
):
    """Fail-closed governed owner-authorization error."""


@dataclass(frozen=True, slots=True)
class VerifiedWaveOwnerAuthorization:
    campaign_id: str
    wave_id: str
    authorization_sha256: str
    preparation_binding_field: str

    authorized_case_count: int
    maximum_trial_index: int
    maximum_concurrent_solver_slots: int

    duplicate_execution_guard_field: str

    raw_payload: dict[str, Any]


_DUPLICATE_GUARD_FIELDS = (
    "duplicate_solver_execution_forbidden",
    (
        "duplicate_trial_1_execution_"
        "forbidden_if_valid_result_exists"
    ),
)


def _require(
    condition: bool,
    message: str,
) -> None:
    if not condition:
        raise GovernedWaveAuthorizationError(
            message
        )


def _sha256(
    path: Path,
) -> str:
    _require(
        path.is_file(),
        f"Owner authorization missing: {path}",
    )

    digest = hashlib.sha256()

    with path.open("rb") as stream:
        for chunk in iter(
            lambda: stream.read(
                1024 * 1024
            ),
            b"",
        ):
            digest.update(
                chunk
            )

    return digest.hexdigest()




def _resolve_named_preparation_binding(
    *,
    payload: dict[str, Any],
    contract: GovernedWaveExecutionContract,
) -> str:
    """Verify preparation provenance through an explicit named field."""

    bound_artifacts = payload.get(
        "bound_artifacts"
    )

    _require(
        isinstance(
            bound_artifacts,
            dict,
        ),
        (
            "Owner authorization bound_artifacts "
            "must be an object."
        ),
    )

    canonical_field = (
        "trial1_preparation_sha256"
    )

    wave_token = (
        contract.wave_id.rsplit(
            "-",
            1,
        )[-1]
        .lower()
    )

    compatibility_field = (
        f"{wave_token}_"
        "trial1_preparation_sha256"
    )

    named_fields = [
        field
        for field in (
            canonical_field,
            compatibility_field,
        )
        if field in bound_artifacts
    ]

    _require(
        bool(
            named_fields
        ),
        (
            "Owner authorization is missing an explicitly "
            "named Trial-1 preparation SHA binding."
        ),
    )

    expected = (
        contract.expected_preparation_index_sha256
    )

    for field in named_fields:

        value = bound_artifacts[
            field
        ]

        _require(
            isinstance(
                value,
                str,
            ),
            (
                "Owner authorization preparation SHA "
                f"binding {field!r} must be a string."
            ),
        )

        _require(
            value == expected,
            (
                "Owner authorization preparation SHA "
                f"binding drift: {field}."
            ),
        )

    if len(
        named_fields
    ) == 2:

        _require(
            bound_artifacts[
                canonical_field
            ]
            == bound_artifacts[
                compatibility_field
            ],
            (
                "Canonical and compatibility preparation "
                "SHA bindings disagree."
            ),
        )

    if canonical_field in named_fields:
        return canonical_field

    return compatibility_field


def verify_owner_authorization_payload(
    *,
    payload: dict[str, Any],
    contract: GovernedWaveExecutionContract,
    authorization_sha256: str,
) -> VerifiedWaveOwnerAuthorization:
    """Validate semantic owner-authorization requirements."""

    _require(
        isinstance(
            payload,
            dict,
        ),
        "Owner authorization root must be an object.",
    )

    _require(
        payload.get(
            "approval_status"
        )
        == "OWNER_APPROVED",
        "Owner authorization is not approved.",
    )

    campaign_id = payload.get(
        "campaign_id"
    )

    wave_id = payload.get(
        "wave_id"
    )

    _require(
        campaign_id
        == contract.campaign_id,
        "Owner authorization campaign identity drift.",
    )

    _require(
        wave_id
        == contract.wave_id,
        "Owner authorization wave identity drift.",
    )

    execution = payload.get(
        "execution_contract"
    )

    scope = payload.get(
        "scope"
    )

    _require(
        isinstance(
            execution,
            dict,
        ),
        "Missing adaptive execution contract.",
    )

    _require(
        isinstance(
            scope,
            dict,
        ),
        "Missing adaptive authorization scope.",
    )

    for field, message in (
        (
            "automatic_governed_adaptation",
            "Automatic governed adaptation is not authorized.",
        ),
        (
            "continue_until_physics_acceptance",
            "Continuation through physics acceptance is not authorized.",
        ),
        (
            "preload_calibration_continuation",
            "Calibration continuation is not authorized.",
        ),
        (
            "full_physics_certification",
            "Full physics certification is not authorized.",
        ),
        (
            "reuse_existing_valid_trials",
            "Existing valid trial reuse is required.",
        ),
    ):
        _require(
            execution.get(
                field
            )
            is True,
            message,
        )

    _require(
        execution.get(
            "maximum_trial_index_per_case"
        )
        == contract.maximum_trial_index,
        "Authorized trial ceiling drift.",
    )

    _require(
        execution.get(
            "maximum_concurrent_calculix"
        )
        == contract.maximum_concurrent_solver_slots,
        "Authorized CalculiX concurrency drift.",
    )

    duplicate_guards = tuple(
        field
        for field in _DUPLICATE_GUARD_FIELDS
        if execution.get(
            field
        )
        is True
    )

    _require(
        len(
            duplicate_guards
        )
        >= 1,
        "Duplicate-solve prohibition missing.",
    )

    # Multiple compatible declarations are harmless. Preserve which
    # declaration supplied the historical authority evidence.
    duplicate_guard_field = (
        duplicate_guards[0]
    )

    _require(
        scope.get(
            "authorized_case_count"
        )
        == contract.authorized_case_count,
        "Authorized case count drift.",
    )

    forbidden_scope = (
        "additional_doe_cases_authorized",
        "additional_waves_authorized",
        "holdout_access_authorized",
        "dataset_admission_authorized",
        "surrogate_training_authorized",
        "artifact_retirement_authorized",
    )

    for field in forbidden_scope:
        _require(
            scope.get(
                field
            )
            is False,
            (
                "Owner authorization scope broadened: "
                f"{field} must be false."
            ),
        )

    preparation_binding_field = (
        _resolve_named_preparation_binding(
            payload=payload,
            contract=contract,
        )
    )

    return VerifiedWaveOwnerAuthorization(
        campaign_id=contract.campaign_id,
        wave_id=contract.wave_id,
        authorization_sha256=(
            authorization_sha256
        ),
        preparation_binding_field=(
            preparation_binding_field
        ),
        authorized_case_count=(
            contract.authorized_case_count
        ),
        maximum_trial_index=(
            contract.maximum_trial_index
        ),
        maximum_concurrent_solver_slots=(
            contract.maximum_concurrent_solver_slots
        ),
        duplicate_execution_guard_field=(
            duplicate_guard_field
        ),
        raw_payload=payload,
    )


def load_and_verify_wave_owner_authorization(
    *,
    repository_root: Path,
    contract: GovernedWaveExecutionContract,
) -> VerifiedWaveOwnerAuthorization:
    """Load, SHA-bind and validate one immutable wave authorization."""

    path = (
        repository_root
        / Path(
            contract.owner_authorization_path.as_posix()
        )
    )

    actual_sha256 = _sha256(
        path
    )

    _require(
        actual_sha256
        == contract.expected_owner_authorization_sha256,
        "Adaptive campaign owner authorization SHA-256 drift.",
    )

    payload = json.loads(
        path.read_text(
            encoding="utf-8-sig"
        )
    )

    return verify_owner_authorization_payload(
        payload=payload,
        contract=contract,
        authorization_sha256=actual_sha256,
    )