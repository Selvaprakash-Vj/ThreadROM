import hashlib
import json

import pytest

from threadrom.factory.adaptive_fem_campaign_authorization import (
    verify_adaptive_campaign_authorization,
)


CASE_ID = "SYNTHETIC-001"
RUN_ID = "trm_fem_synthetic"
CASE_HASH = "a" * 64
GATE0_SHA = "b" * 64
POLICY_SHA = "c" * 64
RULE = "approved_synthetic_delta_t_rule"


def certificate():
    return {
        "schema_version": 1,
        "record_status": "FINAL",
        "campaign_id": "SYNTHETIC-CAMPAIGN",
        "gate0_sha256": GATE0_SHA,
        "policy_sha256": POLICY_SHA,
        "cases": {
            CASE_ID: {
                "case_run_id": RUN_ID,
                "case_hash": CASE_HASH,
            }
        },
        "adaptive_policy": {
            "corrective_rule_id": RULE,
            "maximum_trials": 6,
            "minimum_delta_temperature_c": -350.0,
            "maximum_delta_temperature_c": -200.0,
            "maximum_concurrent_solvers": 4,
        },
        "permissions": {
            "automatic_governed_adaptation": True,
            "execute_adaptive_trials": True,
            "certify_full_physics": False,
            "retire_solver_artifacts": False,
            "access_holdouts": False,
        },
    }


def verify(tmp_path, record, *, trial=2, delta_t=-273.0,
           pin=None, governed=None):
    path = tmp_path / "synthetic_authorization.json"
    data = json.dumps(
        record, sort_keys=True
    ).encode("utf-8")
    path.write_bytes(data)

    return verify_adaptive_campaign_authorization(
        certificate_path=path,
        independently_pinned_sha256=(
            hashlib.sha256(data).hexdigest()
            if pin is None
            else pin
        ),
        expected_campaign_id="SYNTHETIC-CAMPAIGN",
        expected_gate0_sha256=GATE0_SHA,
        expected_policy_sha256=POLICY_SHA,
        governed_cases=(
            {CASE_ID: (RUN_ID, CASE_HASH)}
            if governed is None
            else governed
        ),
        case_id=CASE_ID,
        trial_index=trial,
        trial_run_id=f"{RUN_ID}_cal_{trial:02d}",
        delta_temperature_c=delta_t,
        required_corrective_rule_id=RULE,
        certified_solver_limit=4,
    )


@pytest.mark.parametrize("trial", [2, 3, 4, 5, 6])
def test_one_campaign_authorizes_multiple_bounded_trials(
    tmp_path, trial
):
    result = verify(
        tmp_path, certificate(), trial=trial
    )
    assert result.trial_index == trial
    assert result.maximum_trials == 6


def test_trial_seven_is_blocked(tmp_path):
    with pytest.raises(RuntimeError, match="trial budget"):
        verify(tmp_path, certificate(), trial=7)


def test_delta_t_outside_envelope_is_blocked(tmp_path):
    with pytest.raises(RuntimeError, match="delta T"):
        verify(
            tmp_path, certificate(), delta_t=-351.0
        )


def test_unpinned_certificate_change_is_blocked(tmp_path):
    with pytest.raises(RuntimeError, match="SHA-256 drift"):
        verify(
            tmp_path, certificate(), pin="0" * 64
        )


def test_unauthorized_case_is_blocked(tmp_path):
    record = certificate()
    record["cases"]["UNKNOWN"] = {
        "case_run_id": "trm_fem_other",
        "case_hash": "d" * 64,
    }
    with pytest.raises(RuntimeError, match="case cohort"):
        verify(tmp_path, record)


def test_unapproved_retirement_permission_is_blocked(tmp_path):
    record = certificate()
    record["permissions"]["retire_solver_artifacts"] = True
    with pytest.raises(RuntimeError, match="permissions"):
        verify(tmp_path, record)


def test_solver_capacity_escalation_is_blocked(tmp_path):
    record = certificate()
    record["adaptive_policy"]["maximum_concurrent_solvers"] = 5
    with pytest.raises(RuntimeError, match="solver capacity"):
        verify(tmp_path, record)


def test_corrective_rule_substitution_is_blocked(tmp_path):
    record = certificate()
    record["adaptive_policy"]["corrective_rule_id"] = "other_rule"
    with pytest.raises(RuntimeError, match="corrective rule"):
        verify(tmp_path, record)


def test_unapproved_holdout_access_is_blocked(tmp_path):
    record = certificate()
    record["permissions"]["access_holdouts"] = True
    with pytest.raises(RuntimeError, match="permissions"):
        verify(tmp_path, record)
