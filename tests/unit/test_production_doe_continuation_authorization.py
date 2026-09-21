import hashlib
import json

import pytest

from threadrom.factory.production_doe_continuation_authorization import (
    AUTHORIZATION_TYPE,
    REQUIRED_CONTROLS,
    verify_continuation_authorization,
)


CASE_ID = "D-INT-012"
RUN_ID = "trm_fem_d667bb1aca27"
GATE0_SHA = "1" * 64


def certificate():
    return {
        "schema_version": 1,
        "authorization_type": AUTHORIZATION_TYPE,
        "authorized": True,
        "doe_id": "TRM-PDOE-C01",
        "case_id": CASE_ID,
        "case_run_id": RUN_ID,
        "gate0_certificate_sha256": GATE0_SHA,
        "minimum_trial_index": 2,
        "maximum_trial_index": 6,
        "maximum_concurrent_ccx": 4,
        "holdout_access_authorized": False,
        "required_controls": sorted(REQUIRED_CONTROLS),
    }


def verify(tmp_path, record=None, *, requested_trial=2, **changes):
    record = certificate() if record is None else record
    path = tmp_path / "synthetic_authorization.json"
    raw = json.dumps(record, sort_keys=True).encode("utf-8")
    path.write_bytes(raw)

    arguments = {
        "certificate_path": path,
        "expected_certificate_sha256": hashlib.sha256(raw).hexdigest(),
        "expected_gate0_certificate_sha256": GATE0_SHA,
        "expected_case_id": CASE_ID,
        "expected_case_run_id": RUN_ID,
        "requested_trial_index": requested_trial,
    }
    arguments.update(changes)
    return verify_continuation_authorization(**arguments)


def test_bounded_trial_two_and_six(tmp_path):
    for index in (2, 6):
        result = verify(tmp_path, requested_trial=index)
        assert result.case_id == CASE_ID
        assert result.maximum_concurrent_ccx == 4


def test_seventh_trial_rejected(tmp_path):
    with pytest.raises(RuntimeError, match="bounds"):
        verify(tmp_path, requested_trial=7)


def test_unapproved_record_rejected(tmp_path):
    record = certificate()
    record["authorized"] = False
    with pytest.raises(RuntimeError, match="scope"):
        verify(tmp_path, record)


def test_wrong_case_rejected(tmp_path):
    with pytest.raises(RuntimeError, match="scope"):
        verify(tmp_path, expected_case_id="D-INT-013")


def test_wrong_gate0_certificate_rejected(tmp_path):
    with pytest.raises(RuntimeError, match="scope"):
        verify(tmp_path, expected_gate0_certificate_sha256="2" * 64)


def test_unpinned_or_modified_certificate_rejected(tmp_path):
    with pytest.raises(RuntimeError, match="SHA-256 mismatch"):
        verify(tmp_path, expected_certificate_sha256="0" * 64)


def test_holdout_access_rejected(tmp_path):
    record = certificate()
    record["holdout_access_authorized"] = True
    with pytest.raises(RuntimeError, match="scope"):
        verify(tmp_path, record)


def test_missing_required_control_rejected(tmp_path):
    record = certificate()
    record["required_controls"].remove("duplicate_solve_prevention")
    with pytest.raises(RuntimeError, match="scope"):
        verify(tmp_path, record)


def test_higher_concurrency_rejected(tmp_path):
    record = certificate()
    record["maximum_concurrent_ccx"] = 5
    with pytest.raises(RuntimeError, match="scope"):
        verify(tmp_path, record)


def test_requested_trial_must_fit_certificate(tmp_path):
    record = certificate()
    record["maximum_trial_index"] = 3
    with pytest.raises(RuntimeError, match="scope"):
        verify(tmp_path, record, requested_trial=4)


def test_duplicate_json_key_rejected(tmp_path):
    path = tmp_path / "duplicate.json"
    raw = b'{"authorized":true,"authorized":false}'
    path.write_bytes(raw)

    with pytest.raises(ValueError, match="Duplicate"):
        verify_continuation_authorization(
            certificate_path=path,
            expected_certificate_sha256=hashlib.sha256(raw).hexdigest(),
            expected_gate0_certificate_sha256=GATE0_SHA,
            expected_case_id=CASE_ID,
            expected_case_run_id=RUN_ID,
            requested_trial_index=2,
        )
