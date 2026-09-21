"""Synthetic-only negative/positive tests: never touch actual FEM evidence."""
import hashlib
import json
from pathlib import Path

import pytest

from threadrom.factory.adaptive_fem_rout_retirement import (
    PERMIT_SCHEMA,
    _canonical,
    retire_certified_rout,
)


def fixtures(tmp_path):
    root = tmp_path
    run = root / "synthetic" / "case"
    run.mkdir(parents=True)
    run_id = "synthetic_cal_01"
    rout = run / f"{run_id}.rout"
    rout.write_bytes(b"synthetic solver output only")
    manifest = run / "fem_run_manifest.json"
    cert = run / "independent_governed_physics_certificate.json"
    permit = run / "independent_rout_retirement_permit.json"
    cert.write_text('{"certified": true}\n', encoding="utf-8")
    manifest.write_bytes(_canonical({
        "run_id": run_id, "job_finished": True, "disposition": "succeeded",
        "return_code": 0,
        "artifacts": [{
            "role": "rout", "size_bytes": rout.stat().st_size,
            "sha256": hashlib.sha256(rout.read_bytes()).hexdigest(),
            "relative_path": rout.relative_to(root).as_posix(),
        }],
    }))
    permit.write_bytes(_canonical({
        "schema": PERMIT_SCHEMA,
        "authorization": "ROUT_RETIREMENT_EXPLICITLY_APPROVED",
        "run_id": run_id,
        "solver_manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "independent_certificate_sha256": hashlib.sha256(cert.read_bytes()).hexdigest(),
        "rotational_moment_scope_disposition": "INDEPENDENTLY_VERIFIED",
        "retirement_without_additional_fem": True,
        "rout_sha256": hashlib.sha256(rout.read_bytes()).hexdigest(),
        "rout_size_bytes": rout.stat().st_size,
    }))
    kwargs = dict(
        root=root, run_dir=run, run_id=run_id,
        manifest_path=manifest, certificate_path=cert, permit_path=permit,
        expected_permit_sha256=hashlib.sha256(permit.read_bytes()).hexdigest(),
        verify_independent_certificate=lambda: True,
        active_solver_count=lambda: 0,
    )
    return kwargs, rout, permit


def test_no_independent_pin_blocks_before_hashing(tmp_path):
    kwargs, rout, _ = fixtures(tmp_path)
    kwargs["expected_permit_sha256"] = None
    result = retire_certified_rout(**kwargs, execute=True)
    assert result.status == "HOLD_NO_INDEPENDENT_PERMIT_PIN"
    assert rout.is_file()


def test_dry_run_preserves_artifact_and_writes_no_intent(tmp_path):
    kwargs, rout, _ = fixtures(tmp_path)
    result = retire_certified_rout(**kwargs)
    assert result.status == "ELIGIBLE_DRY_RUN"
    assert rout.is_file()
    assert not (rout.parent / "rout_retirement_intent.json").exists()


def test_active_solver_holds(tmp_path):
    kwargs, rout, _ = fixtures(tmp_path)
    kwargs["active_solver_count"] = lambda: 1
    assert retire_certified_rout(**kwargs, execute=True).status == "HOLD_SOLVER_ACTIVE"
    assert rout.is_file()


def test_tampered_rout_blocks(tmp_path):
    kwargs, rout, _ = fixtures(tmp_path)
    rout.write_bytes(b"changed")
    with pytest.raises(RuntimeError, match="hash/size mismatch"):
        retire_certified_rout(**kwargs, execute=True)
    assert rout.is_file()


def test_tampered_permit_blocks(tmp_path):
    kwargs, rout, permit = fixtures(tmp_path)
    permit.write_text("{}", encoding="utf-8")
    with pytest.raises(RuntimeError, match="permit missing or changed"):
        retire_certified_rout(**kwargs, execute=True)
    assert rout.is_file()


def test_certificate_failure_blocks(tmp_path):
    kwargs, rout, _ = fixtures(tmp_path)
    kwargs["verify_independent_certificate"] = lambda: False
    with pytest.raises(RuntimeError, match="certificate invalid"):
        retire_certified_rout(**kwargs, execute=True)
    assert rout.is_file()


def test_success_maintains_immutable_intent_and_is_idempotent(tmp_path):
    kwargs, rout, _ = fixtures(tmp_path)
    outcome = retire_certified_rout(**kwargs, execute=True)
    assert outcome.retired is True
    assert not rout.exists()
    intent = rout.parent / "rout_retirement_intent.json"
    before = intent.read_bytes()
    again = retire_certified_rout(**kwargs, execute=True)
    assert again.status == "ALREADY_RETIRED"
    assert intent.read_bytes() == before


def test_restart_from_quarantine(tmp_path):
    kwargs, rout, _ = fixtures(tmp_path)
    assert retire_certified_rout(**kwargs).status == "ELIGIBLE_DRY_RUN"
    # Simulate an interrupted, preapproved retirement just after the rename.
    from threadrom.factory.adaptive_fem_rout_retirement import _hash
    cert = kwargs["certificate_path"]
    manifest = kwargs["manifest_path"]
    intent = {
        "schema": "threadrom.fem_rout_retirement.v1",
        "run_id": kwargs["run_id"],
        "solver_manifest_sha256": _hash(manifest),
        "independent_certificate_sha256": _hash(cert),
        "independent_permit_sha256": kwargs["expected_permit_sha256"],
        "original_rout_relative_path": rout.relative_to(kwargs["root"]).as_posix(),
        "original_rout_sha256": _hash(rout),
        "original_rout_size_bytes": rout.stat().st_size,
        "retirement_disposition": "AUTHORIZED_RETIREMENT_INTENT",
    }
    (rout.parent / "rout_retirement_intent.json").write_bytes(_canonical(intent))
    quarantine = rout.with_name(rout.name + ".retirement-pending")
    rout.rename(quarantine)
    assert retire_certified_rout(**kwargs, execute=True).status == "RETIRED_WITH_IMMUTABLE_INTENT"
    assert not quarantine.exists()


def test_no_file_without_intent_requires_review(tmp_path):
    kwargs, rout, _ = fixtures(tmp_path)
    rout.unlink()
    with pytest.raises(RuntimeError, match="absent without matching retirement intent"):
        retire_certified_rout(**kwargs, execute=True)


def test_permit_must_independently_reconcile_moment_scope(tmp_path):
    kwargs, rout, permit = fixtures(tmp_path)
    record = json.loads(permit.read_text(encoding="utf-8"))
    record["rotational_moment_scope_disposition"] = "NOT_ASSESSED"
    permit.write_bytes(_canonical(record))
    kwargs["expected_permit_sha256"] = hashlib.sha256(permit.read_bytes()).hexdigest()
    with pytest.raises(RuntimeError, match="physics scope invalid"):
        retire_certified_rout(**kwargs, execute=True)
    assert rout.exists()


def test_conflicting_retirement_intent_blocks(tmp_path):
    kwargs, rout, _ = fixtures(tmp_path)
    (rout.parent / "rout_retirement_intent.json").write_text("{}", encoding="utf-8")
    with pytest.raises(RuntimeError, match="intent conflict"):
        retire_certified_rout(**kwargs, execute=True)
    assert rout.exists()


def test_existing_quarantine_and_rout_blocks(tmp_path):
    kwargs, rout, _ = fixtures(tmp_path)
    (rout.parent / (rout.name + ".retirement-pending")).write_bytes(rout.read_bytes())
    with pytest.raises(RuntimeError, match="both source and quarantine"):
        retire_certified_rout(**kwargs, execute=True)
    assert rout.exists()
