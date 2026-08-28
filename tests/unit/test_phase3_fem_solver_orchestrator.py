"""Tests for the Phase-3 FEM solver orchestrator."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

import threadrom.factory.fem_solver_orchestrator as orchestrator
from threadrom.factory.fem_run_manifest import (
    FemRunArtifactRole,
)
from threadrom.solver.calculix_job import (
    CalculixJobDefinition,
    CalculixRunResult,
)


_CASE_HASH = "a" * 64


def _definition() -> CalculixJobDefinition:
    return CalculixJobDefinition(
        executable_relative_path=Path(
            "tools/calculix/2.23/bin/ccx.exe"
        ),
        job_name="run_001",
        timeout_seconds=600,
    )


def _fake_successful_solver(
    *,
    project_root: Path,
    input_path: Path,
    definition: CalculixJobDefinition,
) -> CalculixRunResult:
    del project_root

    directory = input_path.parent
    job = definition.job_name

    dat = directory / f"{job}.dat"
    frd = directory / f"{job}.frd"
    sta = directory / f"{job}.sta"
    cvg = directory / f"{job}.cvg"
    stdout = directory / f"{job}.stdout.log"
    stderr = directory / f"{job}.stderr.log"

    dat.write_bytes(b"dat-result")
    frd.write_bytes(b"frd-result")
    sta.write_bytes(b"sta-result")
    cvg.write_bytes(b"cvg-result")
    stdout.write_text(
        "Job finished\n",
        encoding="utf-8",
    )
    stderr.write_bytes(b"")

    return CalculixRunResult(
        return_code=0,
        stdout="Job finished\n",
        stderr="",
        input_path=input_path,
        dat_path=dat,
        frd_path=frd,
        sta_path=sta,
        stdout_log_path=stdout,
        stderr_log_path=stderr,
    )


def test_successful_orchestration_persists_complete_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path
    run_dir = project_root / "runs"
    run_dir.mkdir()

    input_path = run_dir / "run_001.inp"
    input_path.write_bytes(b"input-deck")

    monkeypatch.setattr(
        orchestrator,
        "run_calculix_job",
        _fake_successful_solver,
    )

    times = iter(
        (
            datetime(
                2026,
                8,
                28,
                8,
                0,
                tzinfo=timezone.utc,
            ),
            datetime(
                2026,
                8,
                28,
                8,
                5,
                tzinfo=timezone.utc,
            ),
        )
    )

    ticks = iter(
        (
            100.0,
            400.0,
        )
    )

    monkeypatch.setattr(
        orchestrator,
        "_utc_now",
        lambda: next(times),
    )

    monkeypatch.setattr(
        orchestrator,
        "_monotonic",
        lambda: next(ticks),
    )

    result = orchestrator.orchestrate_successful_calculix_run(
        project_root=project_root,
        input_path=input_path,
        definition=_definition(),
        run_id="run_001",
        case_hash=_CASE_HASH,
        backend_policy_id="backend_v1",
        solver_name="CalculiX",
        solver_version="2.23",
    )

    assert result.run_result.return_code == 0
    assert result.manifest.duration_seconds == 300.0

    assert result.manifest.started_at_utc == (
        "2026-08-28T08:00:00+00:00"
    )

    assert result.manifest.finished_at_utc == (
        "2026-08-28T08:05:00+00:00"
    )

    assert result.manifest_path == (
        run_dir
        / "run_001.run_manifest.json"
    )

    roles = {
        artifact.role
        for artifact in result.manifest.artifacts
    }

    assert roles == set(FemRunArtifactRole)

    payload = json.loads(
        result.manifest_path.read_text(
            encoding="utf-8",
        )
    )

    assert payload == result.manifest.to_payload()

    input_artifact = next(
        artifact
        for artifact in result.manifest.artifacts
        if artifact.role is FemRunArtifactRole.INPUT_DECK
    )

    assert input_artifact.relative_path == (
        "runs/run_001.inp"
    )

    assert input_artifact.sha256 == hashlib.sha256(
        b"input-deck"
    ).hexdigest()


def test_cvg_is_optional_for_generic_successful_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = tmp_path / "runs"
    run_dir.mkdir()

    input_path = run_dir / "run_001.inp"
    input_path.write_bytes(b"input")

    def fake_without_cvg(
        *,
        project_root: Path,
        input_path: Path,
        definition: CalculixJobDefinition,
    ) -> CalculixRunResult:
        result = _fake_successful_solver(
            project_root=project_root,
            input_path=input_path,
            definition=definition,
        )

        (
            input_path.parent
            / "run_001.cvg"
        ).unlink()

        return result

    monkeypatch.setattr(
        orchestrator,
        "run_calculix_job",
        fake_without_cvg,
    )

    result = orchestrator.orchestrate_successful_calculix_run(
        project_root=tmp_path,
        input_path=input_path,
        definition=_definition(),
        run_id="run_001",
        case_hash=_CASE_HASH,
        backend_policy_id="backend_v1",
        solver_name="CalculiX",
        solver_version="2.23",
    )

    roles = {
        artifact.role
        for artifact in result.manifest.artifacts
    }

    assert FemRunArtifactRole.CVG not in roles


def test_run_identity_must_match_job_name(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_path = tmp_path / "run_001.inp"
    input_path.write_bytes(b"input")

    called = False

    def fake_solver(**kwargs: object) -> CalculixRunResult:
        nonlocal called
        called = True
        raise AssertionError(
            f"Unexpected solver call: {kwargs}"
        )

    monkeypatch.setattr(
        orchestrator,
        "run_calculix_job",
        fake_solver,
    )

    with pytest.raises(
        ValueError,
        match="Run identity",
    ):
        orchestrator.orchestrate_successful_calculix_run(
            project_root=tmp_path,
            input_path=input_path,
            definition=_definition(),
            run_id="wrong_run",
            case_hash=_CASE_HASH,
            backend_policy_id="backend_v1",
            solver_name="CalculiX",
            solver_version="2.23",
        )

    assert not called


def test_provenance_rejects_artifact_outside_project(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()

    run_dir = project_root / "runs"
    run_dir.mkdir()

    input_path = run_dir / "run_001.inp"
    input_path.write_bytes(b"input")

    outside = tmp_path / "outside.dat"
    outside.write_bytes(b"outside")

    def fake_external_artifact(
        *,
        project_root: Path,
        input_path: Path,
        definition: CalculixJobDefinition,
    ) -> CalculixRunResult:
        del project_root

        result = _fake_successful_solver(
            project_root=tmp_path,
            input_path=input_path,
            definition=definition,
        )

        return CalculixRunResult(
            return_code=result.return_code,
            stdout=result.stdout,
            stderr=result.stderr,
            input_path=result.input_path,
            dat_path=outside,
            frd_path=result.frd_path,
            sta_path=result.sta_path,
            stdout_log_path=result.stdout_log_path,
            stderr_log_path=result.stderr_log_path,
        )

    monkeypatch.setattr(
        orchestrator,
        "run_calculix_job",
        fake_external_artifact,
    )

    with pytest.raises(
        ValueError,
        match="escapes the project root",
    ):
        orchestrator.orchestrate_successful_calculix_run(
            project_root=project_root,
            input_path=input_path,
            definition=_definition(),
            run_id="run_001",
            case_hash=_CASE_HASH,
            backend_policy_id="backend_v1",
            solver_name="CalculiX",
            solver_version="2.23",
        )
