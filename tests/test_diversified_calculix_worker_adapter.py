from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import threadrom.factory.diversified_calculix_worker_adapter as adapter

from threadrom.factory.diversified_calculix_worker_adapter import (
    GovernedCalculixExecutionSpec,
    execute_claimed_calculix_run,
    make_claimed_calculix_executor,
)
from threadrom.factory.fem_factory_registry import (
    FemFactoryClaim,
)
from threadrom.factory.fem_run_manifest import (
    FemRunDisposition,
    FemRunFailureCategory,
)
from threadrom.solver.calculix_job import (
    CalculixJobDefinition,
)


CASE_HASH = "a" * 64
RUN_ID = "trm_fem_123456789abc_cal_02"


def _claim() -> FemFactoryClaim:
    return FemFactoryClaim(
        job_id=7,
        case_hash=CASE_HASH,
        trial_index=2,
        run_id=RUN_ID,
        worker_id="worker-a",
        lease_generation=3,
        lease_expires_at_utc=(
            "2099-01-01T00:00:00+00:00"
        ),
        recovered=False,
    )


def _spec(
    tmp_path: Path,
) -> GovernedCalculixExecutionSpec:
    root = tmp_path / "repo"
    run_dir = root / "run"

    run_dir.mkdir(
        parents=True
    )

    input_path = (
        run_dir / f"{RUN_ID}.inp"
    )

    input_path.write_text(
        "*HEADING\n",
        encoding="utf-8",
    )

    return GovernedCalculixExecutionSpec(
        project_root=root,
        input_path=input_path,
        definition=CalculixJobDefinition(
            executable_relative_path=Path(
                "tools/calculix/2.23.0/"
                "ccx.exe"
            ),
            job_name=RUN_ID,
            timeout_seconds=None,
        ),
        backend_policy_id=(
            "phase2_complete_joint_c3d4_v1"
        ),
        solver_name="calculix",
        solver_version="2.23.0",
        manifest_path=(
            run_dir / "fem_run_manifest.json"
        ),
    )


def _manifest(
    *,
    spec,
    disposition,
    failure_category=None,
    failure_message=None,
    run_id=RUN_ID,
    case_hash=CASE_HASH,
    backend_policy_id=(
        "phase2_complete_joint_c3d4_v1"
    ),
):
    return SimpleNamespace(
        run_id=run_id,
        job_name=run_id,
        case_hash=case_hash,
        backend_policy_id=(
            backend_policy_id
        ),
        solver_name="calculix",
        solver_version="2.23.0",
        disposition=disposition,
        failure_category=(
            failure_category
        ),
        failure_message=(
            failure_message
        ),
    )


def test_success_maps_to_worker_result(
    tmp_path,
    monkeypatch,
):
    spec = _spec(tmp_path)
    calls = []

    def fake_orchestrate(**kwargs):
        calls.append(kwargs)

        return SimpleNamespace(
            manifest=_manifest(
                spec=spec,
                disposition=(
                    FemRunDisposition.SUCCEEDED
                ),
            ),
            manifest_path=(
                spec.manifest_path
            ),
        )

    monkeypatch.setattr(
        adapter,
        "orchestrate_calculix_run",
        fake_orchestrate,
    )

    result = execute_claimed_calculix_run(
        _claim(),
        spec=spec,
    )

    assert result.succeeded is True
    assert (
        result.manifest_path
        == spec.manifest_path.resolve()
    )
    assert result.failure_category is None
    assert result.failure_message is None

    assert len(calls) == 1

    call = calls[0]

    assert call["run_id"] == RUN_ID
    assert call["case_hash"] == CASE_HASH
    assert (
        call["definition"]
        is spec.definition
    )
    assert (
        call["backend_policy_id"]
        == spec.backend_policy_id
    )


def test_failure_classification_propagates(
    tmp_path,
    monkeypatch,
):
    spec = _spec(tmp_path)

    def fake_orchestrate(**kwargs):
        return SimpleNamespace(
            manifest=_manifest(
                spec=spec,
                disposition=(
                    FemRunDisposition.FAILED
                ),
                failure_category=(
                    FemRunFailureCategory.TIMEOUT
                ),
                failure_message=(
                    "governed timeout"
                ),
            ),
            manifest_path=(
                spec.manifest_path
            ),
        )

    monkeypatch.setattr(
        adapter,
        "orchestrate_calculix_run",
        fake_orchestrate,
    )

    result = execute_claimed_calculix_run(
        _claim(),
        spec=spec,
    )

    assert result.succeeded is False
    assert (
        result.failure_category
        == "timeout"
    )
    assert (
        result.failure_message
        == "governed timeout"
    )
    assert (
        result.manifest_path
        == spec.manifest_path.resolve()
    )


def test_claim_definition_identity_drift_blocks_before_launch(
    tmp_path,
    monkeypatch,
):
    spec = _spec(tmp_path)

    wrong = GovernedCalculixExecutionSpec(
        project_root=spec.project_root,
        input_path=spec.input_path,
        definition=CalculixJobDefinition(
            executable_relative_path=(
                spec.definition
                .executable_relative_path
            ),
            job_name=(
                "trm_fem_ffffffffffff_cal_02"
            ),
            timeout_seconds=None,
        ),
        backend_policy_id=(
            spec.backend_policy_id
        ),
        solver_name=spec.solver_name,
        solver_version=(
            spec.solver_version
        ),
        manifest_path=(
            spec.manifest_path
        ),
    )

    called = False

    def fake_orchestrate(**kwargs):
        nonlocal called
        called = True
        raise AssertionError

    monkeypatch.setattr(
        adapter,
        "orchestrate_calculix_run",
        fake_orchestrate,
    )

    with pytest.raises(
        RuntimeError,
        match="run identity differs",
    ):
        execute_claimed_calculix_run(
            _claim(),
            spec=wrong,
        )

    assert called is False


def test_manifest_identity_drift_fails_closed(
    tmp_path,
    monkeypatch,
):
    spec = _spec(tmp_path)

    def fake_orchestrate(**kwargs):
        return SimpleNamespace(
            manifest=_manifest(
                spec=spec,
                disposition=(
                    FemRunDisposition.SUCCEEDED
                ),
                case_hash=("b" * 64),
            ),
            manifest_path=(
                spec.manifest_path
            ),
        )

    monkeypatch.setattr(
        adapter,
        "orchestrate_calculix_run",
        fake_orchestrate,
    )

    with pytest.raises(
        RuntimeError,
        match="manifest identity",
    ):
        execute_claimed_calculix_run(
            _claim(),
            spec=spec,
        )


def test_failed_manifest_requires_classification(
    tmp_path,
    monkeypatch,
):
    spec = _spec(tmp_path)

    def fake_orchestrate(**kwargs):
        return SimpleNamespace(
            manifest=_manifest(
                spec=spec,
                disposition=(
                    FemRunDisposition.FAILED
                ),
                failure_category=None,
                failure_message=None,
            ),
            manifest_path=(
                spec.manifest_path
            ),
        )

    monkeypatch.setattr(
        adapter,
        "orchestrate_calculix_run",
        fake_orchestrate,
    )

    with pytest.raises(
        RuntimeError,
        match="lacks failure classification",
    ):
        execute_claimed_calculix_run(
            _claim(),
            spec=spec,
        )


def test_executor_is_worker_callback(
    tmp_path,
    monkeypatch,
):
    spec = _spec(tmp_path)

    def fake_orchestrate(**kwargs):
        return SimpleNamespace(
            manifest=_manifest(
                spec=spec,
                disposition=(
                    FemRunDisposition.SUCCEEDED
                ),
            ),
            manifest_path=(
                spec.manifest_path
            ),
        )

    monkeypatch.setattr(
        adapter,
        "orchestrate_calculix_run",
        fake_orchestrate,
    )

    execute = (
        make_claimed_calculix_executor(
            spec
        )
    )

    result = execute(
        _claim()
    )

    assert result.succeeded is True
    assert (
        result.manifest_path
        == spec.manifest_path.resolve()
    )
