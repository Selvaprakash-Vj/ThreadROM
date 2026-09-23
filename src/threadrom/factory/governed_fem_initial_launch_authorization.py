"""Independently pinned authorization for an initial FEM trial.

Verification is not solver admission. The caller must also enforce
immutable input checks, duplicate-run protection and atomic capacity
reservation immediately before starting CalculiX.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def _deny(reason: str) -> None:
    raise RuntimeError(
        "BLOCKED_UNAUTHORIZED_INITIAL_TRIAL: " + reason
    )


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _deny("duplicate authorization JSON key")
        result[key] = value
    return result


def _verified_record(
    root: Path,
    approval_root: Path,
    location: str,
    expected_hash: str,
) -> dict:
    if (
        not isinstance(location, str)
        or not location.strip()
        or not isinstance(expected_hash, str)
        or len(expected_hash) != 64
        or any(c not in "0123456789abcdef" for c in expected_hash)
    ):
        _deny("missing or invalid independent record pin")

    relative = Path(location)

    if relative.is_absolute() or ".." in relative.parts:
        _deny("unsafe authorization record path")

    path = (root / relative).resolve()

    if not path.is_relative_to(approval_root):
        _deny("authorization record outside approved directory")

    if not path.is_file():
        _deny("pinned authorization record missing")

    raw = path.read_bytes()

    if hashlib.sha256(raw).hexdigest() != expected_hash:
        _deny("authorization record SHA256 mismatch")

    try:
        record = json.loads(
            raw.decode("utf-8-sig"),
            object_pairs_hook=_unique_object,
        )
    except (UnicodeError, json.JSONDecodeError):
        _deny("invalid authorization JSON")

    if not isinstance(record, dict):
        _deny("authorization record must be a JSON object")

    return record


def require_initial_trial_authorization(
    *,
    repo_root: Path,
    campaign_root: Path,
    pins: dict,
    campaign_id: str,
    case_id: str,
    case_hash: str,
    case_run_id: str,
    trial_run_id: str,
    deck_sha256: str,
    policy_sha256: str,
    manifest_sha256: str,
) -> None:
    """Require matching owner approval and independently pinned permission.

    ``pins`` must originate from separately reviewed governance, never
    from the records being verified or an execution-time CLI argument.
    """

    if not isinstance(pins, dict) or case_id not in pins:
        _deny("no independently pinned approval for requested case")

    for value in (
        case_hash,
        deck_sha256,
        policy_sha256,
        manifest_sha256,
    ):
        if (
            not isinstance(value, str)
            or len(value) != 64
            or any(c not in "0123456789abcdef" for c in value)
        ):
            _deny("invalid governed SHA256 identity")

    if (
        not isinstance(campaign_id, str)
        or not campaign_id
        or not isinstance(case_id, str)
        or not case_id
        or case_run_id != "trm_fem_" + case_hash[:12]
        or trial_run_id != case_run_id + "_cal_01"
    ):
        _deny("initial-trial identity mismatch")

    root = Path(repo_root).resolve(strict=True)
    campaign = Path(campaign_root).resolve(strict=True)

    if campaign == root or not campaign.is_relative_to(root):
        _deny("campaign outside governed repository")

    approval_root = campaign / "authorization_review"

    if not approval_root.is_dir():
        _deny("independent authorization directory missing")

    approval_root = approval_root.resolve()

    if not approval_root.is_relative_to(campaign):
        _deny("authorization directory escapes campaign")

    case_pins = pins[case_id]

    if (
        not isinstance(case_pins, dict)
        or set(case_pins) != {
            "owner_path",
            "owner_sha256",
            "authorization_path",
            "authorization_sha256",
        }
    ):
        _deny("incomplete independent approval pins")

    owner = _verified_record(
        root,
        approval_root,
        case_pins["owner_path"],
        case_pins["owner_sha256"],
    )

    identity = {
        "campaign_id": campaign_id,
        "case_id": case_id,
        "case_hash": case_hash,
        "case_run_id": case_run_id,
        "trial_run_id": trial_run_id,
        "trial_index": 1,
        "deck_sha256": deck_sha256,
    }

    expected_owner = {
        "schema_version": 1,
        "approval_type": "INITIAL_TRIAL_OWNER_APPROVAL",
        "decision": "APPROVED",
        "holdout_access_authorized": False,
        **identity,
    }

    if (
        type(owner.get("schema_version")) is not int
        or type(owner.get("trial_index")) is not int
        or type(owner.get("holdout_access_authorized")) is not bool
        or owner != expected_owner
    ):
        _deny("owner approval does not match exact initial trial")

    authorization = _verified_record(
        root,
        approval_root,
        case_pins["authorization_path"],
        case_pins["authorization_sha256"],
    )

    expected_authorization = {
        "schema_version": 1,
        "authorization_type": "INITIAL_TRIAL_FEM_LAUNCH",
        "authorized": True,
        "holdout_access_authorized": False,
        **identity,
        "policy_sha256": policy_sha256,
        "manifest_sha256": manifest_sha256,
        "owner_sha256": case_pins["owner_sha256"],
    }

    if (
        type(authorization.get("schema_version")) is not int
        or type(authorization.get("trial_index")) is not int
        or type(authorization.get("authorized")) is not bool
        or type(authorization.get("holdout_access_authorized")) is not bool
        or authorization != expected_authorization
    ):
        _deny("launch permission does not match case, deck or owner")
