from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True, slots=True)
class AuthorizedAdaptiveTrial:
    certificate_sha256: str
    campaign_id: str
    case_id: str
    case_run_id: str
    trial_index: int
    trial_run_id: str
    delta_temperature_c: float
    corrective_rule_id: str
    maximum_trials: int
    maximum_concurrent_solvers: int


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(
            "BLOCKED_CAMPAIGN_AUTHORIZATION: " + message
        )


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, "duplicate certificate key")
        result[key] = value
    return result


def verify_adaptive_campaign_authorization(
    *,
    certificate_path: Path,
    independently_pinned_sha256: str,
    expected_campaign_id: str,
    expected_gate0_sha256: str,
    expected_policy_sha256: str,
    governed_cases: Mapping[str, tuple[str, str]],
    case_id: str,
    trial_index: int,
    trial_run_id: str,
    delta_temperature_c: float,
    required_corrective_rule_id: str,
    certified_solver_limit: int,
) -> AuthorizedAdaptiveTrial:
    """Verify permission for one trial within a preapproved campaign.

    governed_cases maps independently verified case IDs to
    (canonical case run ID, case hash). The certificate must match
    that entire approved cohort. This function does not launch FEM.
    """

    _require(
        len(independently_pinned_sha256) == 64
        and all(
            character in "0123456789abcdef"
            for character in independently_pinned_sha256
        ),
        "missing independently pinned certificate SHA-256",
    )

    data = certificate_path.read_bytes()
    actual_sha = hashlib.sha256(data).hexdigest()

    _require(
        actual_sha == independently_pinned_sha256,
        "certificate SHA-256 drift",
    )

    record = json.loads(
        data.decode("utf-8"),
        object_pairs_hook=_unique_pairs,
    )

    _require(
        type(record) is dict
        and set(record) == {
            "schema_version",
            "record_status",
            "campaign_id",
            "gate0_sha256",
            "policy_sha256",
            "cases",
            "adaptive_policy",
            "permissions",
            "authorized_trial",
        },
        "unexpected certificate schema",
    )

    _require(
        type(record["schema_version"]) is int
        and record["schema_version"] == 1
        and record["record_status"] == "FINAL"
        and record["campaign_id"] == expected_campaign_id
        and record["gate0_sha256"] == expected_gate0_sha256
        and record["policy_sha256"] == expected_policy_sha256,
        "campaign identity or frozen evidence mismatch",
    )

    cases = record["cases"]

    _require(
        type(cases) is dict
        and set(cases) == set(governed_cases),
        "case cohort differs from independently governed scope",
    )

    for governed_id, (run_id, case_hash) in governed_cases.items():
        entry = cases[governed_id]
        _require(
            type(entry) is dict
            and set(entry) == {"case_run_id", "case_hash"}
            and entry["case_run_id"] == run_id
            and entry["case_hash"] == case_hash,
            f"{governed_id}: case binding mismatch",
        )

    _require(
        case_id in governed_cases,
        "requested case is outside the governed cohort",
    )


    authorized_trial = record["authorized_trial"]

    if authorized_trial is not None:
        _require(
            type(authorized_trial) is dict
            and set(authorized_trial) == {
                "case_id",
                "trial_index",
                "trial_run_id",
            },
            "unexpected authorized-trial scope",
        )

        _require(
            authorized_trial["case_id"] == case_id
            and type(authorized_trial["trial_index"]) is int
            and authorized_trial["trial_index"] == trial_index
            and authorized_trial["trial_run_id"] == trial_run_id,
            "requested trial is outside independent authorization scope",
        )

    policy = record["adaptive_policy"]

    _require(
        type(policy) is dict
        and set(policy) == {
            "corrective_rule_id",
            "maximum_trials",
            "minimum_delta_temperature_c",
            "maximum_delta_temperature_c",
            "maximum_concurrent_solvers",
        },
        "unexpected adaptive-policy schema",
    )

    _require(
        policy["corrective_rule_id"]
        == required_corrective_rule_id,
        "corrective rule is not the independently governed rule",
    )

    maximum_trials = policy["maximum_trials"]
    solver_limit = policy["maximum_concurrent_solvers"]

    _require(
        type(maximum_trials) is int
        and 2 <= maximum_trials <= 6
        and type(trial_index) is int
        and 2 <= trial_index <= maximum_trials,
        "adaptive trial is outside the authorized trial budget",
    )

    _require(
        type(solver_limit) is int
        and type(certified_solver_limit) is int
        and 1 <= solver_limit <= certified_solver_limit <= 4,
        "solver capacity exceeds the independently certified limit",
    )

    lower = policy["minimum_delta_temperature_c"]
    upper = policy["maximum_delta_temperature_c"]

    _require(
        all(
            type(value) in (int, float)
            and math.isfinite(value)
            for value in (
                lower,
                upper,
                delta_temperature_c,
            )
        )
        and lower < upper
        and lower <= delta_temperature_c <= upper,
        "candidate delta T is outside the approved finite envelope",
    )

    case_run_id = governed_cases[case_id][0]

    _require(
        trial_run_id
        == f"{case_run_id}_cal_{trial_index:02d}",
        "candidate trial run identity mismatch",
    )

    _require(
        record["permissions"] == {
            "automatic_governed_adaptation": True,
            "execute_adaptive_trials": True,
            "certify_full_physics": False,
            "retire_solver_artifacts": False,
            "access_holdouts": False,
        },
        "unexpected or excessive permissions",
    )

    return AuthorizedAdaptiveTrial(
        certificate_sha256=actual_sha,
        campaign_id=expected_campaign_id,
        case_id=case_id,
        case_run_id=case_run_id,
        trial_index=trial_index,
        trial_run_id=trial_run_id,
        delta_temperature_c=float(delta_temperature_c),
        corrective_rule_id=required_corrective_rule_id,
        maximum_trials=maximum_trials,
        maximum_concurrent_solvers=solver_limit,
    )

def verify_owner_execution_approval(
    *,
    approval_path: Path,
    expected_approval_sha256: str,
    expected_certificate_sha256: str,
    expected_case_id: str,
    expected_trial_index: int,
    expected_trial_run_id: str,
    expected_maximum_concurrent_solvers: int,
) -> None:
    """Verify a separately recorded project-owner execution decision.

    This is owner authorization, not independent human review.
    This function never launches FEM or issues a physics certificate.
    """

    _require(
        isinstance(expected_approval_sha256, str)
        and len(expected_approval_sha256) == 64
        and all(
            char in "0123456789abcdef"
            for char in expected_approval_sha256
        ),
        "invalid owner-approval SHA-256 pin",
    )

    raw = approval_path.read_bytes()
    actual_sha256 = hashlib.sha256(raw).hexdigest()

    _require(
        actual_sha256 == expected_approval_sha256,
        "owner-approval record SHA-256 drift",
    )

    approval = json.loads(
        raw.decode("utf-8"),
        object_pairs_hook=_unique_pairs,
    )

    _require(
        type(approval) is dict
        and set(approval) == {
            "schema_version",
            "authorization_type",
            "approval_status",
            "approved_by",
            "approved_at",
            "independent_human_review",
            "campaign_id",
            "case_id",
            "trial_index",
            "trial_run_id",
            "certificate_sha256",
            "maximum_concurrent_solvers",
            "additional_trials_authorized",
            "artifact_retirement_authorized",
            "full_physics_certification_authorized",
            "holdout_access_authorized",
        },
        "unexpected owner-approval schema",
    )

    _require(
        type(approval["schema_version"]) is int
        and approval["schema_version"] == 1
        and approval["authorization_type"] == "OWNER_AUTHORIZATION"
        and approval["approval_status"]
        == "OWNER_APPROVED_PENDING_TECHNICAL_LAUNCH_GATES"
        and approval["approved_by"]
        == "Selva - ThreadROM project owner"
        and isinstance(approval["approved_at"], str)
        and bool(approval["approved_at"].strip())
        and approval["independent_human_review"] is False
        and approval["campaign_id"] == "TRM-PDOE-C01",
        "owner authorization identity or status mismatch",
    )

    _require(
        approval["certificate_sha256"]
        == expected_certificate_sha256
        and approval["case_id"] == expected_case_id
        and type(approval["trial_index"]) is int
        and approval["trial_index"] == expected_trial_index
        and approval["trial_run_id"] == expected_trial_run_id
        and type(approval["maximum_concurrent_solvers"]) is int
        and approval["maximum_concurrent_solvers"]
        == expected_maximum_concurrent_solvers,
        "owner approval differs from requested execution scope",
    )

    _require(
        approval["additional_trials_authorized"] is False
        and approval["artifact_retirement_authorized"] is False
        and approval["full_physics_certification_authorized"] is False
        and approval["holdout_access_authorized"] is False,
        "owner approval contains prohibited permissions",
    )
