"""Tests for governed Phase-3 FEM completion classification."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import threadrom.factory.fem_solver_orchestrator as orchestrator
from threadrom.factory.fem_run_manifest import (
    FemRunDisposition,
    FemRunFailureCategory,
)
from threadrom.solver.calculix_job import (
    CalculixJobDefinition,
    CalculixJobError,
    CalculixRunResult,
)


_CASE_HASH = "a" * 64


def _definition() -> CalculixJobDefinition:
    return CalculixJobDefinition(
        executable_relative_path=Path("tools/ccx.exe"),
        job_name="run_001",
        timeout_seconds=600,
    )


def _input(tmp_path: Path) -> Path:
    run_dir = tmp_path / "runs"
    run_dir.mkdir()

    path = run_dir / "run_001.inp"
    path.write_bytes(b"input")

    return path


def _fake_result(
    input_path: Path,
    *,
    stdout: str = "Job finished\n",
) -> CalculixRunResult:
    directory = input_path.parent

    paths = {
        suffix: directory / f"run_001.{suffix}"
        for suffix in (
            "dat",
            "frd",
            "sta",
            "stdout.log",
            "stderr.log",
        )
    }

    paths["dat"].write_bytes(b"dat")
    paths["frd"].write_bytes(b"frd")
    paths["sta"].write_bytes(b"sta")
    paths["stdout.log"].write_text(
        stdout,
        encoding="utf-8",
    )
    paths["stderr.log"].write_text(
        "",
        encoding="utf-8",
    )

    return CalculixRunResult(
        return_code=0,
        stdout=stdout,
        stderr="",
        input_path=input_path,
        dat_path=paths["dat"],
        frd_path=paths["frd"],
        sta_path=paths["sta"],
        stdout_log_path=paths["stdout.log"],
        stderr_log_path=paths["stderr.log"],
    )


def test_completed_run_is_classified_successfully(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_path = _input(tmp_path)

    monkeypatch.setattr(
        orchestrator,
        "run_calculix_job",
        lambda **kwargs: _fake_result(
            kwargs["input_path"]
        ),
    )

    monkeypatch.setattr(
        orchestrator,
        "_read_nonlinear_completion",
        lambda path: (
            20,
            1,
            20,
            1,
            21,
        ),
    )

    result = orchestrator.orchestrate_calculix_run(
        project_root=tmp_path,
        input_path=input_path,
        definition=_definition(),
        run_id="run_001",
        case_hash=_CASE_HASH,
        backend_policy_id="backend",
        solver_name="CalculiX",
        solver_version="2.23",
    )

    manifest = result.manifest

    assert (
        manifest.disposition
        is FemRunDisposition.SUCCEEDED
    )
    assert manifest.failure_category is None
    assert manifest.return_code == 0
    assert manifest.job_finished
    assert manifest.accepted_increment_count == 20
    assert manifest.final_increment == 20
    assert manifest.final_attempt == 1
    assert manifest.final_iterations == 21


def test_timeout_is_preserved_as_failed_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_path = _input(tmp_path)

    def timeout(**kwargs: object) -> CalculixRunResult:
        raise subprocess.TimeoutExpired(
            cmd="ccx",
            timeout=600,
            output=b"partial stdout",
            stderr=b"partial stderr",
        )

    monkeypatch.setattr(
        orchestrator,
        "run_calculix_job",
        timeout,
    )

    result = orchestrator.orchestrate_calculix_run(
        project_root=tmp_path,
        input_path=input_path,
        definition=_definition(),
        run_id="run_001",
        case_hash=_CASE_HASH,
        backend_policy_id="backend",
        solver_name="CalculiX",
        solver_version="2.23",
    )

    manifest = result.manifest

    assert result.run_result is None
    assert manifest.disposition is FemRunDisposition.FAILED
    assert (
        manifest.failure_category
        is FemRunFailureCategory.TIMEOUT
    )
    assert manifest.return_code is None

    assert (
        input_path.parent
        / "run_001.stdout.log"
    ).read_text(
        encoding="utf-8"
    ) == "partial stdout"

    assert (
        input_path.parent
        / "run_001.stderr.log"
    ).read_text(
        encoding="utf-8"
    ) == "partial stderr"


@pytest.mark.parametrize(
    ("job_category", "manifest_category", "return_code"),
    (
        (
            "nonzero_exit",
            FemRunFailureCategory.NONZERO_EXIT,
            7,
        ),
        (
            "solver_reported_error",
            FemRunFailureCategory.SOLVER_REPORTED_ERROR,
            0,
        ),
        (
            "missing_required_output",
            FemRunFailureCategory.MISSING_REQUIRED_OUTPUT,
            0,
        ),
    ),
)
def test_structured_solver_failures_are_classified(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    job_category: str,
    manifest_category: FemRunFailureCategory,
    return_code: int,
) -> None:
    input_path = _input(tmp_path)

    def fail(**kwargs: object) -> CalculixRunResult:
        raise CalculixJobError(
            "classified solver failure",
            category=job_category,
            return_code=return_code,
        )

    monkeypatch.setattr(
        orchestrator,
        "run_calculix_job",
        fail,
    )

    result = orchestrator.orchestrate_calculix_run(
        project_root=tmp_path,
        input_path=input_path,
        definition=_definition(),
        run_id="run_001",
        case_hash=_CASE_HASH,
        backend_policy_id="backend",
        solver_name="CalculiX",
        solver_version="2.23",
    )

    assert (
        result.manifest.disposition
        is FemRunDisposition.FAILED
    )
    assert (
        result.manifest.failure_category
        is manifest_category
    )
    assert result.manifest.return_code == return_code


def test_successful_process_without_completion_marker_is_failed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_path = _input(tmp_path)

    monkeypatch.setattr(
        orchestrator,
        "run_calculix_job",
        lambda **kwargs: _fake_result(
            kwargs["input_path"],
            stdout="solver ended without marker",
        ),
    )

    monkeypatch.setattr(
        orchestrator,
        "_read_nonlinear_completion",
        lambda path: (
            20,
            1,
            20,
            1,
            21,
        ),
    )

    result = orchestrator.orchestrate_calculix_run(
        project_root=tmp_path,
        input_path=input_path,
        definition=_definition(),
        run_id="run_001",
        case_hash=_CASE_HASH,
        backend_policy_id="backend",
        solver_name="CalculiX",
        solver_version="2.23",
    )

    assert (
        result.manifest.failure_category
        is FemRunFailureCategory.INCOMPLETE_COMPLETION_EVIDENCE
    )
    assert result.manifest.return_code == 0
    assert not result.manifest.job_finished


def test_missing_executable_is_orchestration_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_path = _input(tmp_path)

    def missing(**kwargs: object) -> CalculixRunResult:
        raise FileNotFoundError(
            "CalculiX executable not found"
        )

    monkeypatch.setattr(
        orchestrator,
        "run_calculix_job",
        missing,
    )

    result = orchestrator.orchestrate_calculix_run(
        project_root=tmp_path,
        input_path=input_path,
        definition=_definition(),
        run_id="run_001",
        case_hash=_CASE_HASH,
        backend_policy_id="backend",
        solver_name="CalculiX",
        solver_version="2.23",
    )

    assert (
        result.manifest.failure_category
        is FemRunFailureCategory.ORCHESTRATION_ERROR
    )
