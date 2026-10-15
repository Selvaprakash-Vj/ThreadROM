"""Bounded owner authorization for one diversified DOE execution wave.

This contract authorizes only the explicitly frozen Trial-1 runs contained
in one immutable diversified DOE wave plan.

It does not authorize:
- adaptive continuation,
- additional calibration trials,
- later waves,
- dataset admission,
- full-physics certification,
- solver-artifact retirement,
- holdout access.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tomllib

from pathlib import Path
from typing import Mapping


AUTH_SCHEMA = (
    "threadrom.phase3_diversified_doe_wave_trial1_authorization.v1"
)

_SHA256 = re.compile(
    r"^[0-9a-f]{64}$"
)

_DATE = re.compile(
    r"^\d{4}-\d{2}-\d{2}$"
)


def _sha256(
    path: Path,
) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as stream:
        for chunk in iter(
            lambda: stream.read(8 * 1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def _canonical(
    payload: Mapping[str, object],
) -> bytes:
    return (
        json.dumps(
            payload,
            sort_keys=True,
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _load_json(
    path: Path,
) -> dict[str, object]:
    if (
        not path.is_file()
        or path.stat().st_size <= 0
    ):
        raise RuntimeError(
            f"Required governed artifact missing: {path}"
        )

    value = json.loads(
        path.read_text(
            encoding="utf-8-sig"
        )
    )

    if not isinstance(
        value,
        dict,
    ):
        raise RuntimeError(
            f"Governed artifact is not a mapping: {path}"
        )

    return value


def _validate_policy(
    policy_path: Path,
) -> str:
    raw = policy_path.read_bytes()

    policy = tomllib.loads(
        raw.decode(
            "utf-8-sig"
        )
    )

    governance = policy.get(
        "governance"
    )

    if not isinstance(
        governance,
        dict,
    ):
        raise RuntimeError(
            "Diversified DOE governance section missing."
        )

    if (
        governance.get(
            "solver_launch_authorized"
        )
        is not False
        or governance.get(
            "dataset_admission_authorized"
        )
        is not False
        or governance.get(
            "sealed_holdout_access_authorized"
        )
        is not False
        or governance.get(
            "no_large_upfront_batch_authorization"
        )
        is not True
    ):
        raise RuntimeError(
            "Diversified DOE policy no longer "
            "supports bounded-wave authorization."
        )

    return hashlib.sha256(
        raw
    ).hexdigest()


def build_wave_trial1_authorization(
    *,
    wave_plan_path: Path,
    design_freeze_certificate_path: Path,
    policy_path: Path,
    approved_by: str,
    approval_date: str,
) -> dict[str, object]:
    if (
        not isinstance(
            approved_by,
            str,
        )
        or not approved_by.strip()
    ):
        raise RuntimeError(
            "Project-owner identity is required."
        )

    if (
        not isinstance(
            approval_date,
            str,
        )
        or _DATE.fullmatch(
            approval_date
        )
        is None
    ):
        raise RuntimeError(
            "Approval date must be YYYY-MM-DD."
        )

    policy_sha = _validate_policy(
        policy_path
    )

    freeze = _load_json(
        design_freeze_certificate_path
    )

    wave = _load_json(
        wave_plan_path
    )

    freeze_sha = _sha256(
        design_freeze_certificate_path
    )

    wave_sha = _sha256(
        wave_plan_path
    )

    if (
        freeze.get(
            "design_status"
        )
        != "FROZEN_DESIGN"
        or freeze.get(
            "design_state_count"
        )
        != 72
    ):
        raise RuntimeError(
            "Diversified DOE design freeze "
            "is not valid."
        )

    for key in (
        "fem_execution_authorized",
        "dataset_admission_authorized",
        "sealed_holdout_access_authorized",
        "surrogate_training_authorized",
    ):
        if freeze.get(key) is not False:
            raise RuntimeError(
                "Design freeze unexpectedly grants "
                f"authority: {key}"
            )

    if (
        wave.get("record_status")
        != "FINAL"
        or wave.get(
            "selection_status"
        )
        != "FROZEN_SELECTION"
        or wave.get(
            "wave_size"
        )
        != 4
        or wave.get(
            "initial_trial_index"
        )
        != 1
    ):
        raise RuntimeError(
            "Wave plan is not the expected "
            "frozen four-case Trial-1 selection."
        )

    if (
        wave.get(
            "design_freeze_certificate_sha256"
        )
        != freeze_sha
    ):
        raise RuntimeError(
            "Wave plan/design-freeze SHA mismatch."
        )

    if (
        wave.get(
            "policy_sha256"
        )
        != policy_sha
    ):
        raise RuntimeError(
            "Wave plan/policy SHA mismatch."
        )

    for key in (
        "preparation_authorized",
        "fem_execution_authorized",
        "adaptive_continuation_authorized",
        "dataset_admission_authorized",
        "full_physics_certification_authorized",
        "artifact_retirement_authorized",
        "holdout_access_authorized",
        "holdout_configurations_generated",
    ):
        if wave.get(key) is not False:
            raise RuntimeError(
                "Source wave plan unexpectedly "
                f"grants authority: {key}"
            )

    limit = wave.get(
        "maximum_concurrent_solver_slots"
    )

    if (
        type(limit) is not int
        or not 1 <= limit <= 4
    ):
        raise RuntimeError(
            "Wave solver-slot ceiling is invalid."
        )

    selected = wave.get(
        "selected_cases"
    )

    if (
        not isinstance(
            selected,
            list,
        )
        or len(selected) != 4
    ):
        raise RuntimeError(
            "Wave must contain exactly four cases."
        )

    case_ids: set[str] = set()
    case_hashes: set[str] = set()
    trial_run_ids: set[str] = set()

    authorized_cases = []

    for expected_order, row in enumerate(
        selected,
        start=1,
    ):
        if not isinstance(
            row,
            dict,
        ):
            raise RuntimeError(
                "Wave case row is not a mapping."
            )

        case_id = row.get(
            "proposal_id"
        )

        case_hash = row.get(
            "case_hash"
        )

        case_run_id = row.get(
            "preparation_run_id"
        )

        trial_run_id = row.get(
            "trial_1_run_id"
        )

        if (
            row.get(
                "wave_order"
            )
            != expected_order
        ):
            raise RuntimeError(
                "Wave case ordering changed."
            )

        if (
            not isinstance(
                case_id,
                str,
            )
            or not case_id
        ):
            raise RuntimeError(
                "Wave case identity missing."
            )

        if (
            not isinstance(
                case_hash,
                str,
            )
            or _SHA256.fullmatch(
                case_hash
            )
            is None
        ):
            raise RuntimeError(
                f"Invalid case hash: {case_id}"
            )

        if (
            not isinstance(
                case_run_id,
                str,
            )
            or not re.fullmatch(
                r"trm_fem_[0-9a-f]{12}",
                case_run_id,
            )
        ):
            raise RuntimeError(
                f"Invalid case-run identity: {case_id}"
            )

        expected_trial = (
            case_run_id
            + "_cal_01"
        )

        if (
            trial_run_id
            != expected_trial
        ):
            raise RuntimeError(
                "Wave authorization refuses "
                f"non-Trial-1 identity: {case_id}"
            )

        if (
            case_id in case_ids
            or case_hash in case_hashes
            or trial_run_id in trial_run_ids
        ):
            raise RuntimeError(
                "Wave contains duplicate identity."
            )

        case_ids.add(
            case_id
        )

        case_hashes.add(
            case_hash
        )

        trial_run_ids.add(
            trial_run_id
        )

        authorized_cases.append(
            {
                "wave_order":
                    expected_order,
                "case_id":
                    case_id,
                "case_hash":
                    case_hash,
                "case_run_id":
                    case_run_id,
                "trial_index":
                    1,
                "trial_run_id":
                    trial_run_id,
            }
        )

    return {
        "schema":
            AUTH_SCHEMA,
        "record_status":
            "FINAL",
        "authorization_type":
            "OWNER_BOUNDED_WAVE_TRIAL1_AUTHORIZATION",
        "approval_status":
            "OWNER_APPROVED_PENDING_TECHNICAL_LAUNCH_GATES",
        "approved_by":
            approved_by,
        "approval_date":
            approval_date,
        "independent_human_review":
            False,
        "campaign_id":
            wave.get(
                "campaign_id"
            ),
        "wave_id":
            wave.get(
                "wave_id"
            ),
        "wave_plan_sha256":
            wave_sha,
        "design_freeze_certificate_sha256":
            freeze_sha,
        "policy_sha256":
            policy_sha,
        "maximum_concurrent_solvers":
            limit,
        "authorized_cases":
            authorized_cases,
        "permissions": {
            "prepare_trial_1":
                True,
            "execute_trial_1":
                True,
            "adaptive_continuation":
                False,
            "additional_trials":
                False,
            "additional_waves":
                False,
            "dataset_admission":
                False,
            "full_physics_certification":
                False,
            "artifact_retirement":
                False,
            "holdout_access":
                False,
        },
        "meaning": (
            "Project-owner authorization to prepare and execute "
            "only Trial-1 for the four cases frozen in this wave. "
            "All continuation, later-wave, dataset, certification, "
            "retirement and holdout permissions remain prohibited."
        ),
    }


def persist_wave_trial1_authorization(
    *,
    wave_plan_path: Path,
    design_freeze_certificate_path: Path,
    policy_path: Path,
    authorization_path: Path,
    approved_by: str,
    approval_date: str,
) -> Path:
    record = build_wave_trial1_authorization(
        wave_plan_path=wave_plan_path,
        design_freeze_certificate_path=(
            design_freeze_certificate_path
        ),
        policy_path=policy_path,
        approved_by=approved_by,
        approval_date=approval_date,
    )

    content = _canonical(
        record
    )

    authorization_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        with authorization_path.open(
            "xb"
        ) as stream:
            stream.write(
                content
            )
            stream.flush()
            os.fsync(
                stream.fileno()
            )

    except FileExistsError:
        if (
            authorization_path.read_bytes()
            != content
        ):
            raise RuntimeError(
                "Existing immutable Wave authorization "
                "differs; engineering review required."
            ) from None

    return authorization_path


def recover_wave_trial1_authorization(
    *,
    wave_plan_path: Path,
    design_freeze_certificate_path: Path,
    policy_path: Path,
    authorization_path: Path,
    approved_by: str,
    approval_date: str,
) -> dict[str, object] | None:
    if not authorization_path.exists():
        return None

    raw = authorization_path.read_bytes()

    record = json.loads(
        raw.decode(
            "utf-8"
        )
    )

    if raw != _canonical(record):
        raise RuntimeError(
            "Wave authorization is not canonical "
            "or has changed."
        )

    current = build_wave_trial1_authorization(
        wave_plan_path=wave_plan_path,
        design_freeze_certificate_path=(
            design_freeze_certificate_path
        ),
        policy_path=policy_path,
        approved_by=approved_by,
        approval_date=approval_date,
    )

    if record != current:
        raise RuntimeError(
            "Wave authorization provenance changed."
        )

    return record
