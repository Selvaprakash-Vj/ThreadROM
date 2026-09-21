"""Isolated, no-solver regression of reusable preliminary FEM evidence ledger."""
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from threadrom.factory import adaptive_fem_physics_records as ledger

CASE = "D-INT-013"
RUN_BASE = "trm_fem_synthetic"
RUN = RUN_BASE + "_cal_01_wsv21_rfobs1"



@pytest.fixture
def tmp_path():
    """Use a short, isolated test root to avoid Windows MAX_PATH."""
    parent = (
        Path.cwd().anchor
        if sys.platform == "win32"
        else None
    )
    with tempfile.TemporaryDirectory(
        prefix="trm-physics-",
        dir=parent,
    ) as directory:
        yield Path(directory)


def setup(tmp_path: Path, monkeypatch):
    run_dir = (tmp_path / "simulations/staging/phase3_cp8_production_doe"
               / "TRM-PDOE-C01/solver_preparation" / RUN_BASE / RUN)
    run_dir.mkdir(parents=True)
    (run_dir / "fem_run_manifest.json").write_text(
        json.dumps({"run_id": RUN, "job_name": RUN, "disposition": "succeeded",
                    "job_finished": True, "return_code": 0}), encoding="utf-8")
    monkeypatch.setattr(ledger, "source_fingerprints", lambda root: {"policy": "frozen"})
    return tmp_path, run_dir


def result(*, passed=True):
    return {
        "case_id": CASE, "run_id": RUN, "calibration": "ACCEPTED_TRIAL_1",
        "final_physics_certified": False, "new_fem_authorized": False,
        "rout_retirement_authorized": False,
        "equilibrium_status": "pass" if passed else "fail",
        "rotational_moment_equilibrium_status": "not_assessed",
        "physics_gates": "PASS_PENDING_INDEPENDENT_CERTIFICATION"
                         if passed else "REVIEW_REQUIRED",
        "failed_governed_checks": [] if passed else ["equilibrium"],
        "physics_checks": [
            {"name": "equilibrium", "kind": "hard_gate", "passed": passed,
             "measured": "pass" if passed else "fail",
             "expected": "pass", "tolerance": 0.001}
        ],
    }


def persist(root, record):
    return ledger.persist_preliminary_c01_assessment(
        repo_root=root, case_id=CASE, case_run_id=RUN_BASE, run_id=RUN,
        trial_index=1, result=record,
    )


def recover(root):
    return ledger.recover_preliminary_c01_assessment(
        repo_root=root, case_id=CASE, case_run_id=RUN_BASE, run_id=RUN,
        trial_index=1,
    )


def test_unassessed_then_persist_and_restart(tmp_path, monkeypatch):
    root, _ = setup(tmp_path, monkeypatch)
    assert recover(root) is None
    path = persist(root, result())
    assert path.is_file()
    assert recover(root)["physics_gates"] == "PASS_PENDING_INDEPENDENT_CERTIFICATION"
    assert persist(root, result()) == path  # safe idempotent replay
    assert json.loads(path.read_text())["independent_full_physics_certificate_issued"] is False


def test_conflicting_replay_refuses_overwrite(tmp_path, monkeypatch):
    root, _ = setup(tmp_path, monkeypatch)
    path = persist(root, result())
    before = path.read_bytes()
    with pytest.raises(RuntimeError, match="immutable preliminary"):
        persist(root, result(passed=False))
    assert path.read_bytes() == before


def test_manifest_drift_blocks_recovery(tmp_path, monkeypatch):
    root, run_dir = setup(tmp_path, monkeypatch)
    persist(root, result())
    with (run_dir / "fem_run_manifest.json").open("a") as stream:
        stream.write(" ")
    with pytest.raises(RuntimeError, match="source drift"):
        recover(root)


def test_source_drift_blocks_recovery(tmp_path, monkeypatch):
    root, _ = setup(tmp_path, monkeypatch)
    persist(root, result())
    monkeypatch.setattr(ledger, "source_fingerprints", lambda root: {"policy": "changed"})
    with pytest.raises(RuntimeError, match="source drift"):
        recover(root)


def test_false_pass_and_retirement_claims_fail_closed(tmp_path, monkeypatch):
    root, _ = setup(tmp_path, monkeypatch)
    invalid = result(passed=False)
    invalid["physics_gates"] = "PASS_PENDING_INDEPENDENT_CERTIFICATION"
    with pytest.raises(RuntimeError, match="Physics PASS"):
        persist(root, invalid)
    invalid = result()
    invalid["rout_retirement_authorized"] = True
    with pytest.raises(RuntimeError, match="must not authorize"):
        persist(root, invalid)


def test_record_cannot_claim_independent_certificate(tmp_path, monkeypatch):
    root, _ = setup(tmp_path, monkeypatch)
    path = persist(root, result())
    recorded = json.loads(path.read_text())
    recorded["independent_full_physics_certificate_issued"] = True
    path.write_text(json.dumps(recorded, sort_keys=True, indent=2) + "\n")
    with pytest.raises(RuntimeError, match="not canonical"):
        recover(root)
