"""Governed provenance contract for one FEM solver execution."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path, PurePosixPath


_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class FemRunArtifactRole(str, Enum):
    """Semantic role of one solver-run artifact."""

    INPUT_DECK = "input_deck"
    DAT = "dat"
    FRD = "frd"
    STA = "sta"
    CVG = "cvg"
    STDOUT = "stdout"
    STDERR = "stderr"


class FemRunDisposition(str, Enum):
    """Top-level execution disposition."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"


class FemRunFailureCategory(str, Enum):
    """Governed solver/orchestration failure classification."""

    TIMEOUT = "timeout"
    NONZERO_EXIT = "nonzero_exit"
    SOLVER_REPORTED_ERROR = "solver_reported_error"
    MISSING_REQUIRED_OUTPUT = "missing_required_output"
    INCOMPLETE_COMPLETION_EVIDENCE = (
        "incomplete_completion_evidence"
    )
    ORCHESTRATION_ERROR = "orchestration_error"


@dataclass(frozen=True, slots=True)
class FemRunArtifact:
    """Immutable identity of one persisted solver artifact."""

    role: FemRunArtifactRole
    relative_path: str
    size_bytes: int
    sha256: str

    def __post_init__(self) -> None:
        path = PurePosixPath(self.relative_path)

        if not self.relative_path:
            raise ValueError(
                "FEM run artifact path must not be empty."
            )

        if "\\" in self.relative_path:
            raise ValueError(
                "FEM run artifact paths must use POSIX separators."
            )

        if path.is_absolute() or ".." in path.parts:
            raise ValueError(
                "FEM run artifact path must be project-relative."
            )

        if self.size_bytes < 0:
            raise ValueError(
                "FEM run artifact size must be non-negative."
            )

        if not _SHA256_PATTERN.fullmatch(self.sha256):
            raise ValueError(
                "FEM run artifact SHA-256 must be "
                "64 lowercase hexadecimal characters."
            )

    def to_payload(self) -> dict[str, object]:
        """Return deterministic JSON-compatible artifact data."""

        return {
            "relative_path": self.relative_path,
            "role": self.role.value,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
        }


@dataclass(frozen=True, slots=True)
class FemRunManifest:
    """Governed immutable provenance for one completed execution attempt."""

    run_id: str
    case_hash: str
    job_name: str
    backend_policy_id: str
    solver_name: str
    solver_version: str
    executable_relative_path: str
    solver_timeout_seconds: int
    started_at_utc: str
    finished_at_utc: str
    duration_seconds: float
    return_code: int | None
    artifacts: tuple[FemRunArtifact, ...]
    disposition: FemRunDisposition = FemRunDisposition.SUCCEEDED
    failure_category: FemRunFailureCategory | None = None
    failure_message: str | None = None
    accepted_increment_count: int = 0
    final_step: int | None = None
    final_increment: int | None = None
    final_attempt: int | None = None
    final_iterations: int | None = None
    job_finished: bool = False
    schema_version: int = 1

    def __post_init__(self) -> None:
        for name, value in (
            ("run_id", self.run_id),
            ("job_name", self.job_name),
            ("backend_policy_id", self.backend_policy_id),
            ("solver_name", self.solver_name),
            ("solver_version", self.solver_version),
        ):
            if not value.strip():
                raise ValueError(
                    f"{name} must not be empty."
                )

        if not _SHA256_PATTERN.fullmatch(self.case_hash):
            raise ValueError(
                "case_hash must be "
                "64 lowercase hexadecimal characters."
            )

        executable = PurePosixPath(
            self.executable_relative_path
        )

        if (
            not self.executable_relative_path
            or "\\" in self.executable_relative_path
            or executable.is_absolute()
            or ".." in executable.parts
        ):
            raise ValueError(
                "CalculiX executable path must be a "
                "project-relative POSIX path."
            )

        if self.solver_timeout_seconds <= 0:
            raise ValueError(
                "Solver timeout must be positive."
            )

        if self.duration_seconds < 0.0:
            raise ValueError(
                "Run duration must be non-negative."
            )

        if self.accepted_increment_count < 0:
            raise ValueError(
                "Accepted increment count must be non-negative."
            )

        final_values = (
            self.final_step,
            self.final_increment,
            self.final_attempt,
            self.final_iterations,
        )

        if self.accepted_increment_count == 0:
            if any(value is not None for value in final_values):
                raise ValueError(
                    "Final nonlinear state cannot exist when no "
                    "increments were accepted."
                )
        elif any(value is None for value in final_values):
            raise ValueError(
                "Accepted nonlinear increments require a complete "
                "final step/increment/attempt/iteration signature."
            )

        if self.disposition is FemRunDisposition.SUCCEEDED:
            if self.return_code != 0:
                raise ValueError(
                    "Successful FEM execution requires return code 0."
                )

            if (
                self.failure_category is not None
                or self.failure_message is not None
            ):
                raise ValueError(
                    "Successful FEM execution cannot carry "
                    "failure classification."
                )
        else:
            if self.failure_category is None:
                raise ValueError(
                    "Failed FEM execution requires a failure category."
                )

            if (
                self.failure_message is None
                or not self.failure_message.strip()
            ):
                raise ValueError(
                    "Failed FEM execution requires a failure message."
                )

        if self.schema_version != 1:
            raise ValueError(
                "Unsupported FEM run manifest schema version."
            )

        started = _parse_utc_timestamp(
            "started_at_utc",
            self.started_at_utc,
        )

        finished = _parse_utc_timestamp(
            "finished_at_utc",
            self.finished_at_utc,
        )

        if finished < started:
            raise ValueError(
                "Run finish time precedes start time."
            )

        roles = tuple(
            artifact.role
            for artifact in self.artifacts
        )

        if len(set(roles)) != len(roles):
            raise ValueError(
                "FEM run manifest contains duplicate artifact roles."
            )

    def to_payload(self) -> dict[str, object]:
        """Return deterministic JSON-compatible manifest data."""

        artifacts = sorted(
            self.artifacts,
            key=lambda artifact: artifact.role.value,
        )

        return {
            "accepted_increment_count": (
                self.accepted_increment_count
            ),
            "artifacts": [
                artifact.to_payload()
                for artifact in artifacts
            ],
            "backend_policy_id": self.backend_policy_id,
            "case_hash": self.case_hash,
            "duration_seconds": self.duration_seconds,
            "executable_relative_path": (
                self.executable_relative_path
            ),
            "failure_category": (
                self.failure_category.value
                if self.failure_category is not None
                else None
            ),
            "failure_message": self.failure_message,
            "final_attempt": self.final_attempt,
            "final_increment": self.final_increment,
            "final_iterations": self.final_iterations,
            "final_step": self.final_step,
            "finished_at_utc": self.finished_at_utc,
            "job_finished": self.job_finished,
            "job_name": self.job_name,
            "return_code": self.return_code,
            "run_id": self.run_id,
            "disposition": self.disposition.value,
            "schema_version": self.schema_version,
            "solver_name": self.solver_name,
            "solver_timeout_seconds": (
                self.solver_timeout_seconds
            ),
            "solver_version": self.solver_version,
            "started_at_utc": self.started_at_utc,
        }


def write_fem_run_manifest(
    path: Path,
    manifest: FemRunManifest,
) -> Path:
    """Write one deterministic governed FEM run manifest."""

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            manifest.to_payload(),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )

    return path


def _parse_utc_timestamp(
    name: str,
    value: str,
) -> datetime:
    """Validate and return one timezone-aware UTC timestamp."""

    try:
        parsed = datetime.fromisoformat(
            value.replace(
                "Z",
                "+00:00",
            )
        )
    except ValueError as exc:
        raise ValueError(
            f"{name} must be a valid ISO-8601 timestamp."
        ) from exc

    if (
        parsed.tzinfo is None
        or parsed.utcoffset() != timedelta(0)
    ):
        raise ValueError(
            f"{name} must be timezone-aware UTC."
        )

    return parsed
