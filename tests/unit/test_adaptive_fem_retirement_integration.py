"""Synthetic evidence only; four real C01 .rout files are never touched."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

import threadrom.factory.adaptive_fem_retirement_integration as integration
from threadrom.factory.adaptive_fem_lifecycle import (
    FEMLifecycleSnapshot,
    PhysicsDisposition,
    RunPhase,
)
from threadrom.factory.adaptive_fem_rout_retirement import (
    PERMIT_SCHEMA,
    _canonical,
)


@pytest.fixture
def short_root():
    # Full C01 directory depth otherwise exceeds Windows default MAX_PATH.
    with tempfile.TemporaryDirectory(
        prefix="trm-g2-",
        dir=Path.cwd().anchor if sys.platform == "win32" else None,
    ) as directory:
        yield Path(directory)


def synthetic_port(short_root, monkeypatch):
    root = short_root
    case_run_id = "trm_fem_synthetic"
    run_id = case_run_id + "_cal_01"
    campaign = root / "simulations/staging/phase3_cp8_production_doe/TRM-PDOE-C01"
    run_dir = campaign / "solver_preparation" / case_run_id / run_id
    run_dir.mkdir(parents=True)
    rout = run_dir / (run_id + ".rout")
    rout.write_bytes(b"synthetic-test-only")
    cert = run_dir / "independent_governed_physics_certificate.json"
    cert.write_text('{"synthetic":true}\n', encoding="utf-8")
    manifest = run_dir / "fem_run_manifest.json"
    manifest.write_bytes(_canonical({
        "run_id": run_id, "job_finished": True,
        "disposition": "succeeded", "return_code": 0,
        "artifacts": [{
            "role": "rout", "sha256": hashlib.sha256(rout.read_bytes()).hexdigest(),
            "size_bytes": rout.stat().st_size,
            "relative_path": rout.relative_to(root).as_posix(),
        }],
    }))
    permit = run_dir / "independent_rout_retirement_permit.json"
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
    snap = FEMLifecycleSnapshot(
        run_id=run_id, trial_index=1, maximum_trials=6,
        phase=RunPhase.COMPLETED, completed_evidence_verified=True,
        physics=PhysicsDisposition.ACCEPTED,
        full_physics_acceptance_verified=True,
    )
    port = SimpleNamespace(
        root=root, case_id="SYNTHETIC-001", campaign_root=campaign,
        case=SimpleNamespace(case_run_id=case_run_id, case_hash="a" * 64),
        snapshot=lambda: snap,
    )
    monkeypatch.setattr(
        integration, "recover_preliminary_c01_assessment",
        lambda **kwargs: {"synthetic": True},
    )
    monkeypatch.setattr(
        integration, "recover_c01_independent_certificate",
        lambda **kwargs: True,
    )
    return port, rout, permit


def test_live_handoff_holds_without_separately_pinned_permit(short_root, monkeypatch):
    port, rout, permit = synthetic_port(short_root, monkeypatch)
    outcome = integration.retire_c01_certified_rout(
        port=port, expected_permit_sha256=None,
        active_solver_count=lambda: 0, execute=True,
    )
    assert outcome.status == "HOLD_NO_INDEPENDENT_PERMIT_PIN"
    assert rout.is_file()
    assert not (rout.parent / "rout_retirement_intent.json").exists()


def test_live_handoff_dry_run_then_explicit_permit_retires_synthetic_only(
    short_root, monkeypatch,
):
    port, rout, permit = synthetic_port(short_root, monkeypatch)
    pin = hashlib.sha256(permit.read_bytes()).hexdigest()  # synthetic independent pin
    kwargs = dict(
        port=port, expected_permit_sha256=pin,
        active_solver_count=lambda: 0,
    )
    assert integration.retire_c01_certified_rout(**kwargs).status == "ELIGIBLE_DRY_RUN"
    assert rout.is_file()
    first = integration.retire_c01_certified_rout(**kwargs, execute=True)
    assert first.status == "RETIRED_WITH_IMMUTABLE_INTENT"
    assert not rout.exists()
    assert integration.retire_c01_certified_rout(**kwargs, execute=True).status == "ALREADY_RETIRED"


def test_not_certified_blocks_before_retirement(short_root, monkeypatch):
    port, rout, _ = synthetic_port(short_root, monkeypatch)
    original = port.snapshot()
    port.snapshot = lambda: FEMLifecycleSnapshot(
        run_id=original.run_id, trial_index=1, maximum_trials=6,
        phase=RunPhase.COMPLETED, completed_evidence_verified=True,
        physics=PhysicsDisposition.NOT_ASSESSED,
    )
    with pytest.raises(RuntimeError, match="not independently certified"):
        integration.retire_c01_certified_rout(
            port=port, expected_permit_sha256=None,
            active_solver_count=lambda: 0, execute=True,
        )
    assert rout.is_file()


def test_certificate_drift_blocks_without_deleting(short_root, monkeypatch):
    port, rout, permit = synthetic_port(short_root, monkeypatch)
    monkeypatch.setattr(
        integration, "recover_c01_independent_certificate",
        lambda **kwargs: False,
    )
    with pytest.raises(RuntimeError, match="certificate invalid"):
        integration.retire_c01_certified_rout(
            port=port,
            expected_permit_sha256=hashlib.sha256(permit.read_bytes()).hexdigest(),
            active_solver_count=lambda: 0,
            execute=True,
        )
    assert rout.is_file()
