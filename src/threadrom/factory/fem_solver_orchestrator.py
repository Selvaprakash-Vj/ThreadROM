"""Reusable governed orchestration for successful FEM solver runs."""

from __future__ import annotations

import hashlib
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from threadrom.factory.fem_run_manifest import (
    FemRunArtifact,
    FemRunArtifactRole,
    FemRunDisposition,
    FemRunFailureCategory,
    FemRunManifest,
    write_fem_run_manifest,
)
from threadrom.postprocessing.calculix_nonlinear_progress import (
    parse_status_increments,
)
from threadrom.solver.calculix_job import (
    CalculixJobDefinition,
    CalculixJobError,
    CalculixRunResult,
    run_calculix_job,
)


_HASH_CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True, slots=True)
class FemOrchestratedRun:
    """One successful solver run plus persisted provenance."""

    run_result: CalculixRunResult | None
    manifest: FemRunManifest
    manifest_path: Path


def orchestrate_successful_calculix_run(
    *,
    project_root: Path,
    input_path: Path,
    definition: CalculixJobDefinition,
    run_id: str,
    case_hash: str,
    backend_policy_id: str,
    solver_name: str,
    solver_version: str,
    manifest_path: Path | None = None,
) -> FemOrchestratedRun:
    """Execute one CalculiX job and persist successful-run provenance.

    Solver failure handling and failure classification intentionally
    remain outside this successful-run primitive.
    """

    if run_id != definition.job_name:
        raise ValueError(
            "Run identity must match the governed solver job name."
        )

    project_root_resolved = project_root.resolve()

    _require_within_project(
        project_root_resolved,
        input_path,
    )

    if manifest_path is None:
        manifest_path = (
            input_path.parent
            / f"{definition.job_name}.run_manifest.json"
        )

    _require_within_project(
        project_root_resolved,
        manifest_path,
    )

    started_at = _utc_now()
    started_tick = _monotonic()

    run_result = run_calculix_job(
        project_root=project_root,
        input_path=input_path,
        definition=definition,
    )

    finished_tick = _monotonic()
    finished_at = _utc_now()

    duration_seconds = max(
        0.0,
        finished_tick - started_tick,
    )

    artifacts = _collect_run_artifacts(
        project_root=project_root_resolved,
        run_result=run_result,
        job_name=definition.job_name,
    )

    manifest = FemRunManifest(
        run_id=run_id,
        case_hash=case_hash,
        job_name=definition.job_name,
        backend_policy_id=backend_policy_id,
        solver_name=solver_name,
        solver_version=solver_version,
        executable_relative_path=(
            definition.executable_relative_path.as_posix()
        ),
        solver_timeout_seconds=definition.timeout_seconds,
        started_at_utc=_format_utc(started_at),
        finished_at_utc=_format_utc(finished_at),
        duration_seconds=duration_seconds,
        return_code=run_result.return_code,
        artifacts=artifacts,
    )

    write_fem_run_manifest(
        manifest_path,
        manifest,
    )

    return FemOrchestratedRun(
        run_result=run_result,
        manifest=manifest,
        manifest_path=manifest_path,
    )


def orchestrate_calculix_run(
    *,
    project_root: Path,
    input_path: Path,
    definition: CalculixJobDefinition,
    run_id: str,
    case_hash: str,
    backend_policy_id: str,
    solver_name: str,
    solver_version: str,
    manifest_path: Path | None = None,
) -> FemOrchestratedRun:
    """Execute one governed job and always classify solver outcome."""

    if run_id != definition.job_name:
        raise ValueError(
            "Run identity must match the governed solver job name."
        )

    project_root_resolved = project_root.resolve()

    _require_within_project(
        project_root_resolved,
        input_path,
    )

    if manifest_path is None:
        manifest_path = (
            input_path.parent
            / f"{definition.job_name}.run_manifest.json"
        )

    _require_within_project(
        project_root_resolved,
        manifest_path,
    )

    started_at = _utc_now()
    started_tick = _monotonic()

    run_result: CalculixRunResult | None = None
    disposition = FemRunDisposition.SUCCEEDED
    failure_category = None
    failure_message = None
    return_code: int | None = None
    stdout_text = ""

    try:
        run_result = run_calculix_job(
            project_root=project_root,
            input_path=input_path,
            definition=definition,
        )

        return_code = run_result.return_code
        stdout_text = run_result.stdout

    except subprocess.TimeoutExpired as exc:
        disposition = FemRunDisposition.FAILED
        failure_category = FemRunFailureCategory.TIMEOUT
        failure_message = (
            f"CalculiX exceeded governed timeout "
            f"of {definition.timeout_seconds} seconds."
        )

        stdout_text = _timeout_stream_text(
            exc.stdout
        )

        _write_timeout_logs(
            input_path=input_path,
            job_name=definition.job_name,
            stdout=stdout_text,
            stderr=_timeout_stream_text(
                exc.stderr
            ),
        )

    except CalculixJobError as exc:
        disposition = FemRunDisposition.FAILED
        failure_category = FemRunFailureCategory(
            exc.category
        )
        failure_message = str(exc)
        return_code = exc.return_code

        stdout_text = _read_text_if_present(
            input_path.parent
            / f"{definition.job_name}.stdout.log"
        )

    except FileNotFoundError as exc:
        disposition = FemRunDisposition.FAILED
        failure_category = (
            FemRunFailureCategory.ORCHESTRATION_ERROR
        )
        failure_message = str(exc)

    finished_tick = _monotonic()
    finished_at = _utc_now()

    (
        accepted_increment_count,
        final_step,
        final_increment,
        final_attempt,
        final_iterations,
    ) = _read_nonlinear_completion(
        input_path.parent
        / f"{definition.job_name}.sta"
    )

    job_finished = (
        "job finished"
        in stdout_text.casefold()
    )

    if (
        disposition is FemRunDisposition.SUCCEEDED
        and (
            not job_finished
            or accepted_increment_count == 0
        )
    ):
        disposition = FemRunDisposition.FAILED
        failure_category = (
            FemRunFailureCategory.INCOMPLETE_COMPLETION_EVIDENCE
        )
        failure_message = (
            "CalculiX returned successfully but governed completion "
            "evidence is incomplete: at least one accepted increment "
            "and the 'Job finished' marker are required."
        )

    artifacts = _collect_workspace_artifacts(
        project_root=project_root_resolved,
        input_path=input_path,
        job_name=definition.job_name,
    )

    manifest = FemRunManifest(
        run_id=run_id,
        case_hash=case_hash,
        job_name=definition.job_name,
        backend_policy_id=backend_policy_id,
        solver_name=solver_name,
        solver_version=solver_version,
        executable_relative_path=(
            definition.executable_relative_path.as_posix()
        ),
        solver_timeout_seconds=definition.timeout_seconds,
        started_at_utc=_format_utc(started_at),
        finished_at_utc=_format_utc(finished_at),
        duration_seconds=max(
            0.0,
            finished_tick - started_tick,
        ),
        return_code=return_code,
        artifacts=artifacts,
        disposition=disposition,
        failure_category=failure_category,
        failure_message=failure_message,
        accepted_increment_count=accepted_increment_count,
        final_step=final_step,
        final_increment=final_increment,
        final_attempt=final_attempt,
        final_iterations=final_iterations,
        job_finished=job_finished,
    )

    write_fem_run_manifest(
        manifest_path,
        manifest,
    )

    return FemOrchestratedRun(
        run_result=run_result,
        manifest=manifest,
        manifest_path=manifest_path,
    )


def _read_nonlinear_completion(
    sta_path: Path,
) -> tuple[
    int,
    int | None,
    int | None,
    int | None,
    int | None,
]:
    """Extract accepted-increment completion evidence when available."""

    if (
        not sta_path.exists()
        or sta_path.stat().st_size <= 0
    ):
        return (
            0,
            None,
            None,
            None,
            None,
        )

    increments = parse_status_increments(
        sta_path.read_text(
            encoding="utf-8",
            errors="replace",
        )
    )

    if not increments:
        return (
            0,
            None,
            None,
            None,
            None,
        )

    final = increments[-1]

    return (
        len(increments),
        final.step,
        final.increment,
        final.attempt,
        final.iterations,
    )


def _collect_workspace_artifacts(
    *,
    project_root: Path,
    input_path: Path,
    job_name: str,
) -> tuple[FemRunArtifact, ...]:
    """Preserve every available canonical artifact, including partial runs."""

    directory = input_path.parent

    candidates = (
        (
            FemRunArtifactRole.INPUT_DECK,
            input_path,
        ),
        (
            FemRunArtifactRole.DAT,
            directory / f"{job_name}.dat",
        ),
        (
            FemRunArtifactRole.FRD,
            directory / f"{job_name}.frd",
        ),
        (
            FemRunArtifactRole.STA,
            directory / f"{job_name}.sta",
        ),
        (
            FemRunArtifactRole.CVG,
            directory / f"{job_name}.cvg",
        ),
        (
            FemRunArtifactRole.STDOUT,
            directory / f"{job_name}.stdout.log",
        ),
        (
            FemRunArtifactRole.STDERR,
            directory / f"{job_name}.stderr.log",
        ),
    )

    return tuple(
        _build_artifact(
            project_root=project_root,
            role=role,
            path=path,
        )
        for role, path in candidates
        if path.exists() and path.is_file()
    )


def _write_timeout_logs(
    *,
    input_path: Path,
    job_name: str,
    stdout: str,
    stderr: str,
) -> None:
    """Persist timeout streams that the low-level runner could not write."""

    directory = input_path.parent

    (
        directory
        / f"{job_name}.stdout.log"
    ).write_text(
        stdout,
        encoding="utf-8",
        errors="replace",
    )

    (
        directory
        / f"{job_name}.stderr.log"
    ).write_text(
        stderr,
        encoding="utf-8",
        errors="replace",
    )


def _timeout_stream_text(
    value: str | bytes | None,
) -> str:
    """Normalize TimeoutExpired captured streams."""

    if value is None:
        return ""

    if isinstance(value, bytes):
        return value.decode(
            "utf-8",
            errors="replace",
        )

    return value


def _read_text_if_present(
    path: Path,
) -> str:
    """Read one optional text provenance artifact."""

    if not path.exists():
        return ""

    return path.read_text(
        encoding="utf-8",
        errors="replace",
    )



def _collect_run_artifacts(
    *,
    project_root: Path,
    run_result: CalculixRunResult,
    job_name: str,
) -> tuple[FemRunArtifact, ...]:
    """Hash persisted artifacts without loading large results into memory."""

    cvg_path = (
        run_result.input_path.parent
        / f"{job_name}.cvg"
    )

    candidates = (
        (
            FemRunArtifactRole.INPUT_DECK,
            run_result.input_path,
            True,
        ),
        (
            FemRunArtifactRole.DAT,
            run_result.dat_path,
            True,
        ),
        (
            FemRunArtifactRole.FRD,
            run_result.frd_path,
            True,
        ),
        (
            FemRunArtifactRole.STA,
            run_result.sta_path,
            True,
        ),
        (
            FemRunArtifactRole.CVG,
            cvg_path,
            False,
        ),
        (
            FemRunArtifactRole.STDOUT,
            run_result.stdout_log_path,
            True,
        ),
        (
            FemRunArtifactRole.STDERR,
            run_result.stderr_log_path,
            True,
        ),
    )

    artifacts = []

    for role, path, required in candidates:
        if not path.exists():
            if required:
                raise RuntimeError(
                    "Required solver provenance artifact is missing: "
                    f"{path}"
                )

            continue

        if not path.is_file():
            raise RuntimeError(
                "Solver provenance artifact is not a file: "
                f"{path}"
            )

        artifacts.append(
            _build_artifact(
                project_root=project_root,
                role=role,
                path=path,
            )
        )

    return tuple(artifacts)


def _build_artifact(
    *,
    project_root: Path,
    role: FemRunArtifactRole,
    path: Path,
) -> FemRunArtifact:
    """Build immutable provenance for one artifact."""

    resolved = path.resolve()

    relative = _require_within_project(
        project_root,
        resolved,
    )

    return FemRunArtifact(
        role=role,
        relative_path=relative.as_posix(),
        size_bytes=resolved.stat().st_size,
        sha256=_sha256_file(resolved),
    )


def _sha256_file(path: Path) -> str:
    """Hash one file using bounded memory."""

    digest = hashlib.sha256()

    with path.open("rb") as stream:
        while True:
            chunk = stream.read(_HASH_CHUNK_SIZE)

            if not chunk:
                break

            digest.update(chunk)

    return digest.hexdigest()


def _require_within_project(
    project_root: Path,
    path: Path,
) -> Path:
    """Return a project-relative path or reject escaping provenance."""

    root = project_root.resolve()
    resolved = path.resolve()

    try:
        return resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            "Governed FEM run path escapes the project root: "
            f"{resolved}"
        ) from exc


def _utc_now() -> datetime:
    """Return the current timezone-aware UTC time."""

    return datetime.now(timezone.utc)


def _monotonic() -> float:
    """Return a monotonic clock value for duration measurement."""

    return time.perf_counter()


def _format_utc(value: datetime) -> str:
    """Serialize one UTC timestamp deterministically."""

    return value.astimezone(
        timezone.utc
    ).isoformat()
