"""Independent governed certificate recovery: cannot promote a stale PASS."""
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

import threadrom.factory.adaptive_fem_independent_certificate as cert


@pytest.fixture
def synthetic(tmp_path_factory, monkeypatch):
    # Avoid the large Windows pytest temp prefix + deep C01 solver path.
    with tempfile.TemporaryDirectory(
        prefix="trm-cert-", dir=Path.cwd().anchor if sys.platform == "win32" else None
    ) as directory:
        root = Path(directory)
        case_run_id = "trm_fem_synthetic"
        run_id = case_run_id + "_cal_01_wsv21_rfobs1"
        run_dir = (
            root / "simulations/staging/phase3_cp8_production_doe"
            / "TRM-PDOE-C01/solver_preparation" / case_run_id / run_id
        )
        run_dir.mkdir(parents=True)
        prelim = {"physics_gates": "PASS_PENDING_INDEPENDENT_CERTIFICATION",
                  "calibration": "ACCEPTED_TRIAL_1", "equilibrium_status": "pass",
                  "rotational_moment_equilibrium_status": "not_assessed",
                  "final_physics_certified": False,
                  "physics_checks": [{"kind": "hard_gate", "passed": True} for _ in range(13)],
                  "failed_governed_checks": [],
                  "equilibrium_max_resultant_n": 0.00001,
                  "equilibrium_tolerance_n": 0.001}
        monkeypatch.setattr(cert, "recover_preliminary_c01_assessment", lambda **kwargs: prelim)
        preliminary_path = run_dir / cert.RECORD_FILENAME
        preliminary_path.write_text("synthetic preliminary", encoding="ascii")
        files = {}
        artifacts = []
        for role, suffix in cert._ARTIFACT_SUFFIXES.items():
            path = run_dir / (run_id + suffix)
            path.write_bytes((role + " synthetic evidence").encode())
            sha = hashlib.sha256(path.read_bytes()).hexdigest()
            files[role] = path
            artifacts.append({"role": role, "relative_path": path.relative_to(root).as_posix(),
                              "sha256": sha, "size_bytes": path.stat().st_size})
        manifest = {"case_hash": "a" * 64, "run_id": run_id,
                    "job_name": run_id, "disposition": "succeeded",
                    "job_finished": True, "return_code": 0,
                    "accepted_increment_count": 20, "artifacts": artifacts}
        manifest_path = run_dir / "fem_run_manifest.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        certificate = {"schema": cert.CERTIFICATE_SCHEMA, "record_status": "FINAL",
                       "disposition": "GOVERNED_13_HARD_GATES_CERTIFIED",
                       "case_id": "D-INT-013", "case_hash": "a" * 64,
                       "case_run_id": case_run_id, "run_id": run_id, "trial_index": 1,
                       "governed_hard_gates_passed": 13, "accepted_reaction_states": 20,
                       "peak_translational_force_residual_n": 0.00001,
                       "translational_force_tolerance_n": 0.001,
                       "rotational_moment_equilibrium": "NOT_ASSESSED",
                       "scope_limitation": cert._SCOPE,
                       "preliminary_record_sha256": cert.sha256_file(preliminary_path),
                       "solver_manifest_sha256": cert.sha256_file(manifest_path),
                       "artifact_sha256": {role: hashlib.sha256(path.read_bytes()).hexdigest()
                                           for role, path in files.items()},
                       "new_fem_authorized": False,
                       "rout_retirement_authorized": False}
        certificate_path = run_dir / cert.CERTIFICATE_FILENAME
        certificate_path.write_bytes(cert._canonical(certificate))
        args = {"repo_root": root, "case_id": "D-INT-013",
                "case_run_id": case_run_id, "case_hash": "a" * 64,
                "run_id": run_id, "trial_index": 1,
                "preliminary_result": prelim}
        yield args, certificate, certificate_path, files, preliminary_path


def test_valid_governed_certificate_recovered(synthetic):
    args, *_ = synthetic
    assert cert.recover_c01_independent_certificate(**args) is True


def test_missing_certificate_waits_without_claim(synthetic):
    args, _, path, *_ = synthetic
    path.unlink()
    assert cert.recover_c01_independent_certificate(**args) is False


def test_tampered_certificate_cannot_promote(synthetic):
    args, record, path, *_ = synthetic
    record["rotational_moment_equilibrium"] = "PASS"
    path.write_bytes(cert._canonical(record))
    with pytest.raises(RuntimeError, match="identity or scope drift"):
        cert.recover_c01_independent_certificate(**args)


def test_changed_solver_artifact_cannot_promote(synthetic):
    args, _, _, files, _ = synthetic
    files["dat"].write_bytes(b"changed dat evidence")
    with pytest.raises(RuntimeError, match="artifact (?:size|hash/metadata) drift"):
        cert.recover_c01_independent_certificate(**args)


def test_changed_preliminary_record_cannot_promote(synthetic):
    args, _, _, _, prelim_path = synthetic
    prelim_path.write_text("changed preliminary evidence", encoding="ascii")
    with pytest.raises(RuntimeError, match="preliminary_record_sha256|identity or scope drift"):
        cert.recover_c01_independent_certificate(**args)


def test_stale_case_or_trial_cannot_promote(synthetic):
    args, *_ = synthetic
    assert cert.recover_c01_independent_certificate(**(args | {"trial_index": 2})) is False
    assert cert.recover_c01_independent_certificate(**(args | {"case_id": "D-INT-012"})) is False
