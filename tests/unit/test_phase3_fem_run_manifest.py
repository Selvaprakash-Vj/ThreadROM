"""Tests for governed Phase-3 FEM run provenance manifests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from threadrom.factory.fem_run_manifest import (
    FemRunArtifact,
    FemRunArtifactRole,
    FemRunManifest,
    write_fem_run_manifest,
)


_CASE_HASH = "a" * 64
_DECK_HASH = "b" * 64
_STDERR_HASH = "c" * 64


def _manifest() -> FemRunManifest:
    return FemRunManifest(
        run_id="run_001",
        case_hash=_CASE_HASH,
        job_name="run_001",
        backend_policy_id="calculix_c3d4_v1",
        solver_name="CalculiX",
        solver_version="2.23",
        executable_relative_path=(
            "tools/calculix/2.23/bin/ccx.exe"
        ),
        solver_timeout_seconds=57_600,
        started_at_utc="2026-08-28T08:47:19+00:00",
        finished_at_utc="2026-08-28T13:57:18+00:00",
        duration_seconds=18_599.0,
        return_code=0,
        artifacts=(
            FemRunArtifact(
                role=FemRunArtifactRole.STDERR,
                relative_path="runs/run_001.stderr.log",
                size_bytes=0,
                sha256=_STDERR_HASH,
            ),
            FemRunArtifact(
                role=FemRunArtifactRole.INPUT_DECK,
                relative_path="runs/run_001.inp",
                size_bytes=123,
                sha256=_DECK_HASH,
            ),
        ),
    )


def test_manifest_payload_is_stable_and_semantic() -> None:
    payload = _manifest().to_payload()

    assert payload["schema_version"] == 1
    assert payload["run_id"] == "run_001"
    assert payload["case_hash"] == _CASE_HASH
    assert payload["return_code"] == 0

    assert [
        artifact["role"]
        for artifact in payload["artifacts"]
    ] == [
        "input_deck",
        "stderr",
    ]


def test_manifest_writer_is_deterministic(
    tmp_path: Path,
) -> None:
    path = (
        tmp_path
        / "run_manifest.json"
    )

    write_fem_run_manifest(
        path,
        _manifest(),
    )

    first = path.read_bytes()

    write_fem_run_manifest(
        path,
        _manifest(),
    )

    second = path.read_bytes()

    assert first == second
    assert first.endswith(b"\n")

    payload = json.loads(
        first.decode("utf-8")
    )

    assert payload == _manifest().to_payload()


def test_manifest_rejects_duplicate_artifact_roles() -> None:
    artifact = FemRunArtifact(
        role=FemRunArtifactRole.DAT,
        relative_path="runs/result.dat",
        size_bytes=1,
        sha256="d" * 64,
    )

    with pytest.raises(
        ValueError,
        match="duplicate artifact roles",
    ):
        FemRunManifest(
            run_id="run_001",
            case_hash=_CASE_HASH,
            job_name="run_001",
            backend_policy_id="backend",
            solver_name="CalculiX",
            solver_version="2.23",
            executable_relative_path="tools/ccx.exe",
            solver_timeout_seconds=60,
            started_at_utc="2026-08-28T10:00:00Z",
            finished_at_utc="2026-08-28T10:01:00Z",
            duration_seconds=60.0,
            return_code=0,
            artifacts=(
                artifact,
                artifact,
            ),
        )


@pytest.mark.parametrize(
    "relative_path",
    (
        "../outside.dat",
        "runs\\result.dat",
        "/absolute/result.dat",
    ),
)
def test_artifact_requires_normalized_project_relative_path(
    relative_path: str,
) -> None:
    with pytest.raises(ValueError):
        FemRunArtifact(
            role=FemRunArtifactRole.DAT,
            relative_path=relative_path,
            size_bytes=1,
            sha256="e" * 64,
        )


def test_manifest_requires_utc_timestamps() -> None:
    manifest = _manifest()

    with pytest.raises(
        ValueError,
        match="timezone-aware UTC",
    ):
        FemRunManifest(
            run_id=manifest.run_id,
            case_hash=manifest.case_hash,
            job_name=manifest.job_name,
            backend_policy_id=manifest.backend_policy_id,
            solver_name=manifest.solver_name,
            solver_version=manifest.solver_version,
            executable_relative_path=(
                manifest.executable_relative_path
            ),
            solver_timeout_seconds=(
                manifest.solver_timeout_seconds
            ),
            started_at_utc="2026-08-28T10:00:00",
            finished_at_utc=manifest.finished_at_utc,
            duration_seconds=manifest.duration_seconds,
            return_code=manifest.return_code,
            artifacts=manifest.artifacts,
        )
