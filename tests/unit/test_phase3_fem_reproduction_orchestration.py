"""Certified Phase-2 reproduction orchestration integration."""

from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

import threadrom.factory.fem_reproduction as reproduction
from threadrom.factory.fem_reproduction import (
    FemReproductionDeckResult,
    orchestrate_phase2_certified_reproduction_job,
)


_CASE_HASH = "a" * 64


def _deck(tmp_path: Path):
    input_path = tmp_path / "certified_run.inp"
    payload = b"certified-deck"
    input_path.write_bytes(payload)
    sha256 = hashlib.sha256(payload).hexdigest()

    return (
        FemReproductionDeckResult(
            input_path=input_path,
            sha256=sha256,
            size_bytes=len(payload),
            node_count=100,
            element_count=200,
            guidance_reference_node_count=8,
            bolt_thermal_node_count=50,
            thermal_initial_node_count=60,
        ),
        sha256,
    )


def _profile(
    sha256: str,
    *,
    timeout: int | None = 57_600,
):
    return SimpleNamespace(
        oracle=SimpleNamespace(
            run_id="certified_run",
            case_hash=_CASE_HASH,
            solver_deck_sha256=sha256,
        ),
        backend=SimpleNamespace(
            policy_id="phase2_complete_joint_c3d4_v1",
            solver_name="CalculiX",
            solver_version="2.23",
            solver_timeout_seconds=timeout,
        ),
    )


def _transfer():
    return SimpleNamespace(
        executable_relative_path=Path(
            "tools/calculix/2.23/bin/ccx.exe"
        ),
        timeout_seconds=1_800,
    )


def test_certified_reproduction_routes_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deck, sha256 = _deck(tmp_path)
    captured = {}

    def fake_orchestrate(**kwargs):
        captured.update(kwargs)
        return "orchestrated"

    monkeypatch.setattr(
        reproduction,
        "orchestrate_calculix_run",
        fake_orchestrate,
    )

    result = orchestrate_phase2_certified_reproduction_job(
        project_root=tmp_path,
        deck=deck,
        transfer=_transfer(),
        profile=_profile(sha256),
    )

    assert result == "orchestrated"
    assert captured["run_id"] == "certified_run"
    assert captured["case_hash"] == _CASE_HASH
    assert (
        captured["backend_policy_id"]
        == "phase2_complete_joint_c3d4_v1"
    )
    assert captured["solver_name"] == "CalculiX"
    assert captured["solver_version"] == "2.23"
    assert captured["definition"].job_name == "certified_run"
    assert captured["definition"].timeout_seconds == 57_600


def test_certified_orchestration_uses_timeout_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deck, sha256 = _deck(tmp_path)
    captured = {}

    def fake_orchestrate(**kwargs):
        captured.update(kwargs)
        return "orchestrated"

    monkeypatch.setattr(
        reproduction,
        "orchestrate_calculix_run",
        fake_orchestrate,
    )

    orchestrate_phase2_certified_reproduction_job(
        project_root=tmp_path,
        deck=deck,
        transfer=_transfer(),
        profile=_profile(
            sha256,
            timeout=None,
        ),
    )

    assert captured["definition"].timeout_seconds == 1_800


def test_certified_orchestration_forwards_manifest_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deck, sha256 = _deck(tmp_path)
    captured = {}

    def fake_orchestrate(**kwargs):
        captured.update(kwargs)
        return "orchestrated"

    monkeypatch.setattr(
        reproduction,
        "orchestrate_calculix_run",
        fake_orchestrate,
    )

    manifest_path = tmp_path / "provenance/run.json"

    orchestrate_phase2_certified_reproduction_job(
        project_root=tmp_path,
        deck=deck,
        transfer=_transfer(),
        profile=_profile(sha256),
        manifest_path=manifest_path,
    )

    assert captured["manifest_path"] == manifest_path


def test_orchestration_blocks_tampered_deck(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deck, sha256 = _deck(tmp_path)
    deck.input_path.write_bytes(b"tampered")

    called = False

    def fake_orchestrate(**kwargs):
        nonlocal called
        called = True
        return kwargs

    monkeypatch.setattr(
        reproduction,
        "orchestrate_calculix_run",
        fake_orchestrate,
    )

    with pytest.raises(
        RuntimeError,
        match="changed after assembly",
    ):
        orchestrate_phase2_certified_reproduction_job(
            project_root=tmp_path,
            deck=deck,
            transfer=_transfer(),
            profile=_profile(sha256),
        )

    assert not called


def test_orchestration_blocks_wrong_oracle_hash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deck, _ = _deck(tmp_path)

    called = False

    def fake_orchestrate(**kwargs):
        nonlocal called
        called = True
        return kwargs

    monkeypatch.setattr(
        reproduction,
        "orchestrate_calculix_run",
        fake_orchestrate,
    )

    with pytest.raises(
        RuntimeError,
        match="certified solver-deck oracle",
    ):
        orchestrate_phase2_certified_reproduction_job(
            project_root=tmp_path,
            deck=deck,
            transfer=_transfer(),
            profile=_profile("f" * 64),
        )

    assert not called


def test_legacy_runner_still_uses_same_guard(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deck, sha256 = _deck(tmp_path)
    deck.input_path.write_bytes(b"tampered")

    called = False

    def fake_solver(**kwargs):
        nonlocal called
        called = True
        return kwargs

    monkeypatch.setattr(
        reproduction,
        "run_calculix_job",
        fake_solver,
    )

    with pytest.raises(
        RuntimeError,
        match="changed after assembly",
    ):
        reproduction.run_phase2_certified_reproduction_job(
            project_root=tmp_path,
            deck=deck,
            transfer=_transfer(),
            profile=_profile(sha256),
        )

    assert not called
