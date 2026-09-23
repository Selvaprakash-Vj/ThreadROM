"""Independent initial-trial authorization contract tests."""

import hashlib
import json

import pytest

from threadrom.factory.governed_fem_initial_launch_authorization import (
    require_initial_trial_authorization,
)


CASE_HASH = "a" * 64
RUN_ID = "trm_fem_" + CASE_HASH[:12]


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _fixture(tmp_path):
    campaign = tmp_path / "campaign"
    approval_dir = campaign / "authorization_review"
    approval_dir.mkdir(parents=True)

    identity = {
        "campaign_id": "TEST-CAMPAIGN",
        "case_id": "TEST-CASE",
        "case_hash": CASE_HASH,
        "case_run_id": RUN_ID,
        "trial_run_id": RUN_ID + "_cal_01",
        "trial_index": 1,
        "deck_sha256": "b" * 64,
    }

    owner = {
        "schema_version": 1,
        "approval_type": "INITIAL_TRIAL_OWNER_APPROVAL",
        "decision": "APPROVED",
        "holdout_access_authorized": False,
        **identity,
    }

    owner_path = approval_dir / "owner.json"
    owner_raw = json.dumps(owner).encode()
    owner_path.write_bytes(owner_raw)
    owner_hash = _sha(owner_raw)

    authorization = {
        "schema_version": 1,
        "authorization_type": "INITIAL_TRIAL_FEM_LAUNCH",
        "authorized": True,
        "holdout_access_authorized": False,
        **identity,
        "policy_sha256": "c" * 64,
        "manifest_sha256": "d" * 64,
        "owner_sha256": owner_hash,
    }

    auth_path = approval_dir / "authorization.json"
    auth_raw = json.dumps(authorization).encode()
    auth_path.write_bytes(auth_raw)

    pins = {
        "TEST-CASE": {
            "owner_path": owner_path.relative_to(tmp_path).as_posix(),
            "owner_sha256": owner_hash,
            "authorization_path": auth_path.relative_to(tmp_path).as_posix(),
            "authorization_sha256": _sha(auth_raw),
        }
    }

    args = {
        "repo_root": tmp_path,
        "campaign_root": campaign,
        "pins": pins,
        **{
            key: value
            for key, value in identity.items()
            if key != "trial_index"
        },
        "policy_sha256": "c" * 64,
        "manifest_sha256": "d" * 64,
    }

    return args, owner_path, auth_path


def test_matching_pinned_approval_pair(tmp_path):
    args, _, _ = _fixture(tmp_path)
    require_initial_trial_authorization(**args)


def test_missing_independent_pin_fails(tmp_path):
    args, _, _ = _fixture(tmp_path)
    args["pins"] = {}

    with pytest.raises(RuntimeError, match="BLOCKED_UNAUTHORIZED"):
        require_initial_trial_authorization(**args)


def test_different_deck_fails(tmp_path):
    args, _, _ = _fixture(tmp_path)
    args["deck_sha256"] = "e" * 64

    with pytest.raises(RuntimeError, match="BLOCKED_UNAUTHORIZED"):
        require_initial_trial_authorization(**args)


def test_trial_two_cannot_use_trial_one_approval(tmp_path):
    args, _, _ = _fixture(tmp_path)
    args["trial_run_id"] = RUN_ID + "_cal_02"

    with pytest.raises(RuntimeError, match="identity mismatch"):
        require_initial_trial_authorization(**args)


def test_modified_owner_record_fails(tmp_path):
    args, owner, _ = _fixture(tmp_path)
    owner.write_bytes(b"modified")

    with pytest.raises(RuntimeError, match="SHA256 mismatch"):
        require_initial_trial_authorization(**args)


def test_modified_launch_record_fails(tmp_path):
    args, _, authorization = _fixture(tmp_path)
    authorization.write_bytes(b"modified")

    with pytest.raises(RuntimeError, match="SHA256 mismatch"):
        require_initial_trial_authorization(**args)


def test_owner_rejection_fails_even_when_re_pinned(tmp_path):
    args, owner, authorization = _fixture(tmp_path)

    owner_record = json.loads(owner.read_text())
    owner_record["decision"] = "REJECTED"
    owner_raw = json.dumps(owner_record).encode()
    owner.write_bytes(owner_raw)

    pins = args["pins"]["TEST-CASE"]
    pins["owner_sha256"] = _sha(owner_raw)

    auth_record = json.loads(authorization.read_text())
    auth_record["owner_sha256"] = pins["owner_sha256"]
    auth_raw = json.dumps(auth_record).encode()
    authorization.write_bytes(auth_raw)
    pins["authorization_sha256"] = _sha(auth_raw)

    with pytest.raises(RuntimeError, match="owner approval"):
        require_initial_trial_authorization(**args)
