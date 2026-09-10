"""Tests for governed exceptional FEM-run adjudication."""

from __future__ import annotations

import json
import struct
from hashlib import sha256
from pathlib import Path

import pytest

from threadrom.factory.fem_run_adjudication import (
    FemRunAdjudicationDisposition,
    adjudicate_completed_solver_reported_error_run,
    verify_fem_run_adjudication,
    write_fem_run_adjudication,
)
from threadrom.factory.fem_run_manifest import (
    FemRunArtifact,
    FemRunArtifactRole,
    FemRunDisposition,
    FemRunFailureCategory,
    FemRunManifest,
    write_fem_run_manifest,
)


_CASE_HASH = "a" * 64
_RUN_ID = "trm_fem_test_cal_02"


def _digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _write_sta(
    path: Path,
    *,
    completed_steps: int = 20,
) -> None:
    """Write synthetic CalculiX STA checkpoint records."""

    lines = []

    for step in range(1, completed_steps + 1):
        total_time = step * 0.05

        lines.append(
            f"{step:5d} "
            f"{1:5d} "
            f"{1:5d} "
            f"{3:5d} "
            f"{total_time:.8E} "
            f"{0.05:.8E} "
            f"{0.05:.8E}"
        )

    path.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
        newline="\n",
    )



def _write_rout(
    path: Path,
    *,
    stored_step: int = 20,
) -> None:
    """Write a tiny CalculiX-like Fortran ROUT header."""

    version = b"Version 2.23"

    payload = (
        struct.pack("<I", len(version))
        + version
        + struct.pack("<I", len(version))
        + struct.pack("<I", 4)
        + struct.pack("<i", stored_step)
        + struct.pack("<I", 4)
    )

    path.write_bytes(payload)


def _write_manifest(
    root: Path,
    *,
    disposition: FemRunDisposition = FemRunDisposition.FAILED,
    failure_category: FemRunFailureCategory | None = (
        FemRunFailureCategory.SOLVER_REPORTED_ERROR
    ),
    failure_message: str | None = "Synthetic solver-reported error.",
    return_code: int = 0,
    job_finished: bool = True,
    accepted_increment_count: int = 20,
    final_step: int = 20,
) -> tuple[Path, Path]:
    run_dir = root / "simulations" / "run"
    run_dir.mkdir(parents=True)

    sta = run_dir / f"{_RUN_ID}.sta"
    _write_sta(
        sta,
        completed_steps=20,
    )

    rout = run_dir / f"{_RUN_ID}.rout"
    _write_rout(
        rout,
        stored_step=20,
    )

    sta_artifact = FemRunArtifact(
        role=FemRunArtifactRole.STA,
        relative_path=sta.relative_to(root).as_posix(),
        size_bytes=sta.stat().st_size,
        sha256=_digest(sta),
    )

    rout_artifact = FemRunArtifact(
        role=FemRunArtifactRole.ROUT,
        relative_path=rout.relative_to(root).as_posix(),
        size_bytes=rout.stat().st_size,
        sha256=_digest(rout),
    )

    manifest = FemRunManifest(
        run_id=_RUN_ID,
        case_hash=_CASE_HASH,
        job_name=_RUN_ID,
        backend_policy_id="test-backend",
        solver_name="CalculiX",
        solver_version="2.23",
        executable_relative_path="vendor/ccx.exe",
        solver_timeout_seconds=None,
        started_at_utc="2026-09-09T12:00:00+00:00",
        finished_at_utc="2026-09-09T12:01:00+00:00",
        duration_seconds=60.0,
        return_code=return_code,
        artifacts=(sta_artifact, rout_artifact),
        disposition=disposition,
        failure_category=failure_category,
        failure_message=failure_message,
        accepted_increment_count=accepted_increment_count,
        final_step=final_step,
        final_increment=1,
        final_attempt=1,
        final_iterations=3,
        job_finished=job_finished,
    )

    manifest_path = run_dir / "fem_run_manifest.json"
    write_fem_run_manifest(
        manifest_path,
        manifest,
    )

    return manifest_path, rout


def _adjudicate(
    root: Path,
    manifest_path: Path,
    *,
    expected_final_step: int = 20,
):
    return adjudicate_completed_solver_reported_error_run(
        project_root=root,
        manifest_path=manifest_path,
        expected_run_id=_RUN_ID,
        expected_case_hash=_CASE_HASH,
        expected_final_step=expected_final_step,
        expected_checkpoint_step_time=0.05,
        adjudication_reason=(
            "Restart-write portability defect occurred after "
            "the governed final solution state was reached."
        ),
    )


def test_valid_failed_manifest_is_adjudicated_without_mutation(
    tmp_path: Path,
) -> None:
    manifest_path, rout = _write_manifest(
        tmp_path,
    )

    before = manifest_path.read_bytes()

    result = _adjudicate(
        tmp_path,
        manifest_path,
    )

    after = manifest_path.read_bytes()

    assert before == after
    assert result.run_id == _RUN_ID
    assert result.case_hash == _CASE_HASH
    assert result.original_disposition == "failed"
    assert (
        result.original_failure_category
        == "solver_reported_error"
    )
    assert result.return_code == 0
    assert result.job_finished is True
    assert result.accepted_increment_count == 20
    assert result.final_step == 20
    assert result.rout_stored_step == 20
    assert result.rout_size_bytes == rout.stat().st_size
    assert result.rout_sha256 == _digest(rout)
    assert (
        result.disposition
        is FemRunAdjudicationDisposition
        .COMPLETED_SOLUTION_EVIDENCE_ACCEPTED
    )


def test_succeeded_manifest_cannot_use_exception_path(
    tmp_path: Path,
) -> None:
    manifest_path, _ = _write_manifest(
        tmp_path,
        disposition=FemRunDisposition.SUCCEEDED,
        failure_category=None,
        failure_message=None,
    )

    with pytest.raises(
        ValueError,
        match="originally failed",
    ):
        _adjudicate(
            tmp_path,
            manifest_path,
        )


def test_wrong_failure_category_is_refused(
    tmp_path: Path,
) -> None:
    manifest_path, _ = _write_manifest(
        tmp_path,
        failure_category=(
            FemRunFailureCategory.NONZERO_EXIT
        ),
    )

    with pytest.raises(
        ValueError,
        match="solver_reported_error",
    ):
        _adjudicate(
            tmp_path,
            manifest_path,
        )


def test_nonzero_return_code_is_refused(
    tmp_path: Path,
) -> None:
    manifest_path, _ = _write_manifest(
        tmp_path,
        return_code=7,
    )

    with pytest.raises(
        ValueError,
        match="return code 0",
    ):
        _adjudicate(
            tmp_path,
            manifest_path,
        )


def test_missing_job_finished_is_refused(
    tmp_path: Path,
) -> None:
    manifest_path, _ = _write_manifest(
        tmp_path,
        job_finished=False,
    )

    with pytest.raises(
        ValueError,
        match="Job finished",
    ):
        _adjudicate(
            tmp_path,
            manifest_path,
        )


def test_final_step_mismatch_is_refused(
    tmp_path: Path,
) -> None:
    manifest_path, _ = _write_manifest(
        tmp_path,
        final_step=19,
    )

    with pytest.raises(
        ValueError,
        match="final step",
    ):
        _adjudicate(
            tmp_path,
            manifest_path,
        )


def test_rout_artifact_drift_is_refused(
    tmp_path: Path,
) -> None:
    manifest_path, rout = _write_manifest(
        tmp_path,
    )

    rout.write_bytes(
        b"mutated-restart-state"
    )

    with pytest.raises(
        ValueError,
        match="ROUT artifact",
    ):
        _adjudicate(
            tmp_path,
            manifest_path,
        )


def test_sta_completed_checkpoint_mismatch_is_refused(
    tmp_path: Path,
) -> None:
    manifest_path, _ = _write_manifest(
        tmp_path,
    )

    data = json.loads(
        manifest_path.read_text(
            encoding="utf-8",
        )
    )

    sta_artifact = next(
        item
        for item in data["artifacts"]
        if item["role"] == "sta"
    )

    sta_path = (
        tmp_path
        / Path(
            *Path(
                sta_artifact["relative_path"]
            ).parts
        )
    )

    _write_sta(
        sta_path,
        completed_steps=19,
    )

    sta_artifact["size_bytes"] = (
        sta_path.stat().st_size
    )
    sta_artifact["sha256"] = (
        _digest(sta_path)
    )

    manifest_path.write_text(
        json.dumps(
            data,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )

    with pytest.raises(
        ValueError,
        match="STA completed checkpoint",
    ):
        _adjudicate(
            tmp_path,
            manifest_path,
        )



def test_rout_stored_step_mismatch_is_refused(
    tmp_path: Path,
) -> None:
    manifest_path, rout = _write_manifest(
        tmp_path,
    )

    _write_rout(
        rout,
        stored_step=19,
    )

    data = json.loads(
        manifest_path.read_text(
            encoding="utf-8",
        )
    )

    rout_artifact = next(
        item
        for item in data["artifacts"]
        if item["role"] == "rout"
    )

    rout_artifact["size_bytes"] = rout.stat().st_size
    rout_artifact["sha256"] = _digest(rout)

    manifest_path.write_text(
        json.dumps(
            data,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )

    with pytest.raises(
        ValueError,
        match="stored restart step",
    ):
        _adjudicate(
            tmp_path,
            manifest_path,
        )


def test_adjudication_payload_is_json_serializable(
    tmp_path: Path,
) -> None:
    manifest_path, _ = _write_manifest(
        tmp_path,
    )

    result = _adjudicate(
        tmp_path,
        manifest_path,
    )

    serialized = json.dumps(
        result.to_payload(),
        sort_keys=True,
    )

    assert "completed_solution_evidence_accepted" in serialized
    assert _RUN_ID in serialized


def test_persisted_adjudication_verifies(
    tmp_path: Path,
) -> None:
    manifest_path, _ = _write_manifest(
        tmp_path,
    )

    adjudication = _adjudicate(
        tmp_path,
        manifest_path,
    )

    output = (
        tmp_path
        / "simulations"
        / "run"
        / "fem_run_adjudication.json"
    )

    write_fem_run_adjudication(
        output,
        adjudication,
    )

    verified = verify_fem_run_adjudication(
        project_root=tmp_path,
        adjudication_path=output,
        manifest_path=manifest_path,
        expected_run_id=_RUN_ID,
        expected_case_hash=_CASE_HASH,
        expected_final_step=20,
        expected_checkpoint_step_time=0.05,
        adjudication_reason=(
            "Restart-write portability defect occurred after "
            "the governed final solution state was reached."
        ),
    )

    assert verified == adjudication


def test_tampered_persisted_adjudication_is_refused(
    tmp_path: Path,
) -> None:
    manifest_path, _ = _write_manifest(
        tmp_path,
    )

    adjudication = _adjudicate(
        tmp_path,
        manifest_path,
    )

    output = (
        tmp_path
        / "simulations"
        / "run"
        / "fem_run_adjudication.json"
    )

    write_fem_run_adjudication(
        output,
        adjudication,
    )

    data = json.loads(
        output.read_text(
            encoding="utf-8",
        )
    )

    data["rout_stored_step"] = 19

    output.write_text(
        json.dumps(
            data,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )

    with pytest.raises(
        ValueError,
        match="does not match independently recomputed evidence",
    ):
        verify_fem_run_adjudication(
            project_root=tmp_path,
            adjudication_path=output,
            manifest_path=manifest_path,
            expected_run_id=_RUN_ID,
            expected_case_hash=_CASE_HASH,
            expected_final_step=20,
            expected_checkpoint_step_time=0.05,
            adjudication_reason=(
                "Restart-write portability defect occurred after "
                "the governed final solution state was reached."
            ),
        )
