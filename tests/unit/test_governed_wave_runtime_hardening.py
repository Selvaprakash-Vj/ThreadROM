from __future__ import annotations

import io
import json

from dataclasses import replace

from pathlib import Path
from types import SimpleNamespace

import pytest

import threadrom.factory.governed_wave_runtime as runtime

from threadrom.factory.governed_wave_closure import (
    GovernedCaseAcceptanceEvidence,
    GovernedWaveAcceptanceEvidence,
    build_governed_wave_closure_record,
    persist_governed_wave_closure,
    recover_governed_wave_closure,
)


def test_cp1252_stream_is_reconfigured_before_unicode_output():
    raw = io.BytesIO()

    stream = io.TextIOWrapper(
        raw,
        encoding="cp1252",
        errors="strict",
    )

    runtime.configure_utf8_stream(
        stream
    )

    # Exact class of characters that killed the historical W02
    # campaign logger under cp1252.
    stream.write(
        "physics accepted: \U0001f525 \u2014 PASS \u2713"
    )
    stream.flush()

    value = raw.getvalue().decode(
        "utf-8"
    )

    assert "\U0001f525" in value
    assert "\u2014" in value
    assert "\u2713" in value


class NonReconfigurableCP1252:
    encoding = "cp1252"


def test_nonreconfigurable_non_utf8_stream_fails_closed():
    with pytest.raises(
        RuntimeError,
        match="cannot be proven UTF-8 safe",
    ):
        runtime.configure_utf8_stream(
            NonReconfigurableCP1252()
        )


class NonReconfigurableUTF8:
    encoding = "utf-8"


def test_already_utf8_nonreconfigurable_stream_is_accepted():
    runtime.configure_utf8_stream(
        NonReconfigurableUTF8()
    )


class FakeStream:
    def __init__(self):
        self.calls = []

    def reconfigure(
        self,
        **kwargs,
    ):
        self.calls.append(
            kwargs
        )


def test_process_stdio_hardens_both_streams():
    stdout = FakeStream()
    stderr = FakeStream()

    runtime.configure_process_stdio(
        stdout=stdout,
        stderr=stderr,
    )

    assert stdout.calls == [
        {
            "encoding": "utf-8",
            "errors": "backslashreplace",
        }
    ]

    assert stderr.calls == [
        {
            "encoding": "utf-8",
            "errors": "backslashreplace",
        }
    ]


class FakeRunner:
    def __init__(
        self,
        *,
        preflight_result=None,
        execute_result=0,
    ):
        self.preflight_result = (
            preflight_result
        )
        self.execute_result = (
            execute_result
        )
        self.preflight_calls = 0
        self.execute_calls = 0

    def preflight(self):
        self.preflight_calls += 1
        return self.preflight_result

    def execute(self):
        self.execute_calls += 1
        return self.execute_result


def test_entrypoint_defaults_to_preflight_and_never_executes(
    tmp_path,
    monkeypatch,
):
    runner = FakeRunner()

    monkeypatch.setattr(
        runtime,
        "build_governed_wave_runner",
        lambda **kwargs: runner,
    )

    result = (
        runtime.run_governed_wave_entrypoint(
            repository_root=tmp_path,
            contract=object(),
            stdout=FakeStream(),
            stderr=FakeStream(),
        )
    )

    assert result == 0
    assert runner.preflight_calls == 1
    assert runner.execute_calls == 0


def test_entrypoint_executes_exactly_once_only_when_explicit(
    tmp_path,
    monkeypatch,
):
    runner = FakeRunner(
        execute_result=0
    )

    monkeypatch.setattr(
        runtime,
        "build_governed_wave_runner",
        lambda **kwargs: runner,
    )

    result = (
        runtime.run_governed_wave_entrypoint(
            repository_root=tmp_path,
            contract=object(),
            execute=True,
            stdout=FakeStream(),
            stderr=FakeStream(),
        )
    )

    assert result == 0
    assert runner.preflight_calls == 0
    assert runner.execute_calls == 1


def test_invalid_runner_status_fails_closed():
    with pytest.raises(
        RuntimeError,
        match="invalid process status",
    ):
        runtime.normalize_runner_status(
            "SUCCESS"
        )


def evidence(
    *,
    certificate_sha="a" * 64,
):
    case = (
        GovernedCaseAcceptanceEvidence(
            case_id="CASE-01",
            case_hash="b" * 64,
            case_run_id=(
                "trm_fem_aaaaaaaaaaaa"
            ),
            run_id=(
                "trm_fem_aaaaaaaaaaaa_cal_02"
            ),
            trial_index=2,
            acceptance_record=(
                "run/"
                "governed_physics_certificate.json"
            ),
            certificate_sha256=(
                certificate_sha
            ),
            hard_gate_count=13,
            accepted_increment_count=20,
            rotational_moment_equilibrium_status=(
                "not_assessed"
            ),
        )
    )

    return GovernedWaveAcceptanceEvidence(
        wave_id="TEST-WAVE",
        authorized_case_count=1,
        cases=(
            case,
        ),
    )


def closure_record(
    expected,
):
    return (
        build_governed_wave_closure_record(
            evidence=expected,
            execution_contract_sha256=(
                "1" * 64
            ),
            owner_authorization_sha256=(
                "2" * 64
            ),
            preparation_index_sha256=(
                "3" * 64
            ),
        )
    )


def test_noncanonical_closure_tamper_fails_closed(
    tmp_path,
):
    expected = evidence()

    record = closure_record(
        expected
    )

    path = (
        tmp_path
        / "closure.json"
    )

    persist_governed_wave_closure(
        path=path,
        record=record,
    )

    # Semantically identical JSON, but immutable canonical bytes
    # have been changed.
    path.write_text(
        json.dumps(
            record,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        RuntimeError,
        match="not canonical",
    ):
        recover_governed_wave_closure(
            path=path,
            expected_wave_id="TEST-WAVE",
            expected_evidence=expected,
        )


def test_certificate_fingerprint_tamper_fails_closed(
    tmp_path,
):
    original = evidence(
        certificate_sha=(
            "a" * 64
        )
    )

    path = (
        tmp_path
        / "closure.json"
    )

    persist_governed_wave_closure(
        path=path,
        record=closure_record(
            original
        ),
    )

    changed = evidence(
        certificate_sha=(
            "c" * 64
        )
    )

    with pytest.raises(
        RuntimeError,
        match="certificate set drift",
    ):
        recover_governed_wave_closure(
            path=path,
            expected_wave_id="TEST-WAVE",
            expected_evidence=changed,
        )