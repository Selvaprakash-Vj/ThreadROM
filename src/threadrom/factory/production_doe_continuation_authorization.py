from __future__ import annotations

import hashlib
import json
import re

from dataclasses import dataclass
from pathlib import Path


AUTHORIZATION_TYPE = "PRODUCTION_DOE_BOUNDED_ADAPTIVE_CONTINUATION"

REQUIRED_CONTROLS = frozenset({
    "verified_completed_predecessor",
    "immutable_prepared_deck",
    "governed_calibration_decision",
    "atomic_solver_slot_reservation",
    "duplicate_solve_prevention",
    "separate_full_physics_acceptance",
})

EXPECTED_FIELDS = frozenset({
    "schema_version",
    "authorization_type",
    "authorized",
    "doe_id",
    "case_id",
    "case_run_id",
    "gate0_certificate_sha256",
    "minimum_trial_index",
    "maximum_trial_index",
    "maximum_concurrent_ccx",
    "holdout_access_authorized",
    "required_controls",
})


@dataclass(frozen=True, slots=True)
class VerifiedContinuationAuthorization:
    certificate_sha256: str
    case_id: str
    case_run_id: str
    maximum_trial_index: int
    maximum_concurrent_ccx: int


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate authorization key: {key}")
        result[key] = value
    return result


def verify_continuation_authorization(
    *,
    certificate_path: Path,
    expected_certificate_sha256: str,
    expected_gate0_certificate_sha256: str,
    expected_case_id: str,
    expected_case_run_id: str,
    requested_trial_index: int,
) -> VerifiedContinuationAuthorization:
    """Verify a separately pinned authorization. Never authorizes by itself.

    The expected certificate hash must come from an independently reviewed
    and frozen authorization register, never from this certificate or its
    adjacent sidecar. Recheck under the launch lock before any solver start.
    """

    for name, value in (
        ("authorization", expected_certificate_sha256),
        ("Gate0", expected_gate0_certificate_sha256),
    ):
        if not isinstance(value, str) or not re.fullmatch(
            r"[0-9a-f]{64}", value
        ):
            raise RuntimeError(f"Invalid pinned {name} SHA-256.")

    if (
        type(requested_trial_index) is not int
        or not 2 <= requested_trial_index <= 6
    ):
        raise RuntimeError("Requested trial exceeds governed continuation bounds.")

    raw = certificate_path.read_bytes()
    actual_sha256 = hashlib.sha256(raw).hexdigest()

    if actual_sha256 != expected_certificate_sha256:
        raise RuntimeError("Continuation authorization SHA-256 mismatch.")

    certificate = json.loads(
        raw.decode("utf-8"),
        object_pairs_hook=_reject_duplicate_keys,
    )

    if not isinstance(certificate, dict):
        raise RuntimeError("Authorization must be a JSON object.")

    if frozenset(certificate) != EXPECTED_FIELDS:
        raise RuntimeError("Authorization schema/fields mismatch.")

    if (
        type(certificate["schema_version"]) is not int
        or certificate["schema_version"] != 1
        or certificate["authorization_type"] != AUTHORIZATION_TYPE
        or certificate["authorized"] is not True
        or certificate["doe_id"] != "TRM-PDOE-C01"
        or certificate["case_id"] != expected_case_id
        or certificate["case_run_id"] != expected_case_run_id
        or certificate["gate0_certificate_sha256"]
        != expected_gate0_certificate_sha256
        or type(certificate["minimum_trial_index"]) is not int
        or certificate["minimum_trial_index"] != 2
        or type(certificate["maximum_trial_index"]) is not int
        or not 2 <= certificate["maximum_trial_index"] <= 6
        or requested_trial_index > certificate["maximum_trial_index"]
        or type(certificate["maximum_concurrent_ccx"]) is not int
        or certificate["maximum_concurrent_ccx"] != 4
        or certificate["holdout_access_authorized"] is not False
        or not isinstance(certificate["required_controls"], list)
        or len(certificate["required_controls"]) != len(REQUIRED_CONTROLS)
        or not all(
            isinstance(item, str)
            for item in certificate["required_controls"]
        )
        or frozenset(certificate["required_controls"]) != REQUIRED_CONTROLS
    ):
        raise RuntimeError(
            "Authorization scope, policy or required controls mismatch."
        )

    return VerifiedContinuationAuthorization(
        certificate_sha256=actual_sha256,
        case_id=expected_case_id,
        case_run_id=expected_case_run_id,
        maximum_trial_index=certificate["maximum_trial_index"],
        maximum_concurrent_ccx=4,
    )
