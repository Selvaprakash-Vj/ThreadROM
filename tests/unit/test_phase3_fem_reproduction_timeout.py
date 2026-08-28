"""Tests for governed certified FEM solver timeout policy."""

from dataclasses import replace
import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

import threadrom.factory.fem_reproduction as reproduction_module
from threadrom.factory.fem_profile import (
    FemCertificationOracle,
    FemReproductionProfile,
    PHASE2_CERTIFIED_FEM_PROFILE,
)
from threadrom.factory.fem_reproduction import (
    FemReproductionDeckResult,
    run_phase2_certified_reproduction_job,
)


def _deck(
    tmp_path: Path,
    *,
    run_id: str,
) -> FemReproductionDeckResult:
    path = (
        tmp_path
        / f"{run_id}.inp"
    )

    payload = b"*HEADING\nCP4 timeout policy test\n"

    path.write_bytes(
        payload
    )

    digest = hashlib.sha256(
        payload
    ).hexdigest()

    return FemReproductionDeckResult(
        input_path=path,
        sha256=digest,
        size_bytes=len(payload),
        node_count=1,
        element_count=1,
        guidance_reference_node_count=0,
        bolt_thermal_node_count=1,
        thermal_initial_node_count=1,
    )


def _profile(
    *,
    run_id: str,
    deck_sha256: str,
    solver_timeout_seconds: int | None,
) -> FemReproductionProfile:
    backend = replace(
        PHASE2_CERTIFIED_FEM_PROFILE.backend,
        solver_timeout_seconds=solver_timeout_seconds,
    )

    oracle = FemCertificationOracle(
        run_id=run_id,
        case_hash="0" * 64,
        preload_config_sha256="1" * 64,
        analytical_config_sha256="2" * 64,
        solver_deck_sha256=deck_sha256,
        certification_document="test-certification.md",
    )

    return FemReproductionProfile(
        backend=backend,
        oracle=oracle,
    )


def test_certified_profile_has_long_running_solver_timeout() -> None:
    assert (
        PHASE2_CERTIFIED_FEM_PROFILE
        .backend
        .solver_timeout_seconds
        == 57_600
    )


def test_certified_runner_prefers_backend_solver_timeout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_id = "certified_timeout_test"

    deck = _deck(
        tmp_path,
        run_id=run_id,
    )

    profile = _profile(
        run_id=run_id,
        deck_sha256=deck.sha256,
        solver_timeout_seconds=57_600,
    )

    transfer = SimpleNamespace(
        executable_relative_path=Path(
            "fake-ccx.exe"
        ),
        timeout_seconds=1_800,
    )

    captured = {}

    def fake_run_calculix_job(
        *,
        project_root,
        input_path,
        definition,
    ):
        captured["timeout_seconds"] = (
            definition.timeout_seconds
        )
        captured["job_name"] = (
            definition.job_name
        )
        return "solver-result"

    monkeypatch.setattr(
        reproduction_module,
        "run_calculix_job",
        fake_run_calculix_job,
    )

    result = run_phase2_certified_reproduction_job(
        project_root=tmp_path,
        deck=deck,
        transfer=transfer,
        profile=profile,
    )

    assert result == "solver-result"
    assert captured["timeout_seconds"] == 57_600
    assert captured["job_name"] == run_id


def test_runner_can_intentionally_inherit_transfer_timeout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_id = "inherited_timeout_test"

    deck = _deck(
        tmp_path,
        run_id=run_id,
    )

    profile = _profile(
        run_id=run_id,
        deck_sha256=deck.sha256,
        solver_timeout_seconds=None,
    )

    transfer = SimpleNamespace(
        executable_relative_path=Path(
            "fake-ccx.exe"
        ),
        timeout_seconds=1_800,
    )

    captured = {}

    def fake_run_calculix_job(
        *,
        project_root,
        input_path,
        definition,
    ):
        captured["timeout_seconds"] = (
            definition.timeout_seconds
        )
        return "solver-result"

    monkeypatch.setattr(
        reproduction_module,
        "run_calculix_job",
        fake_run_calculix_job,
    )

    result = run_phase2_certified_reproduction_job(
        project_root=tmp_path,
        deck=deck,
        transfer=transfer,
        profile=profile,
    )

    assert result == "solver-result"
    assert captured["timeout_seconds"] == 1_800


def test_backend_rejects_nonpositive_solver_timeout() -> None:
    with pytest.raises(
        ValueError,
        match="solver_timeout_seconds",
    ):
        replace(
            PHASE2_CERTIFIED_FEM_PROFILE.backend,
            solver_timeout_seconds=0,
        )
