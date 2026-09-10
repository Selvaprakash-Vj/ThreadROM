"""Governed adjudication of completed FEM evidence from a failed run."""

from __future__ import annotations

import json
import re
import struct
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Any

from threadrom.solver.complete_joint_pretension_restart import (
    find_last_completed_checkpoint,
    parse_calculix_sta_records,
)


_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class FemRunAdjudicationDisposition(str, Enum):
    """Permitted outcome of one exceptional run adjudication."""

    COMPLETED_SOLUTION_EVIDENCE_ACCEPTED = (
        "completed_solution_evidence_accepted"
    )


@dataclass(frozen=True, slots=True)
class FemRunAdjudication:
    """Immutable evidence that one failed run retained usable final state."""

    run_id: str
    case_hash: str

    original_manifest_relative_path: str
    original_manifest_sha256: str

    original_disposition: str
    original_failure_category: str

    return_code: int
    job_finished: bool
    accepted_increment_count: int

    final_step: int
    final_increment: int
    final_attempt: int
    final_iterations: int

    sta_relative_path: str
    sta_size_bytes: int
    sta_sha256: str
    sta_completed_checkpoint: int

    rout_relative_path: str
    rout_size_bytes: int
    rout_sha256: str
    rout_stored_step: int

    adjudication_reason: str

    disposition: FemRunAdjudicationDisposition = (
        FemRunAdjudicationDisposition
        .COMPLETED_SOLUTION_EVIDENCE_ACCEPTED
    )
    schema_version: int = 1

    def __post_init__(self) -> None:
        if not self.run_id.strip():
            raise ValueError(
                "Adjudicated FEM run ID must not be empty."
            )

        if not _SHA256_PATTERN.fullmatch(self.case_hash):
            raise ValueError(
                "Adjudicated FEM case hash must be SHA-256."
            )

        for value, name in (
            (
                self.original_manifest_sha256,
                "Original manifest SHA-256",
            ),
            (
                self.sta_sha256,
                "STA SHA-256",
            ),
            (
                self.rout_sha256,
                "ROUT SHA-256",
            ),
        ):
            if not _SHA256_PATTERN.fullmatch(value):
                raise ValueError(
                    f"{name} must be 64 lowercase hexadecimal characters."
                )

        for value, name in (
            (
                self.original_manifest_relative_path,
                "Original manifest path",
            ),
            (
                self.sta_relative_path,
                "STA path",
            ),
            (
                self.rout_relative_path,
                "ROUT path",
            ),
        ):
            path = PurePosixPath(value)

            if (
                not value
                or "\\" in value
                or path.is_absolute()
                or ".." in path.parts
            ):
                raise ValueError(
                    f"{name} must be a project-relative POSIX path."
                )

        if self.original_disposition != "failed":
            raise ValueError(
                "Adjudication is only valid for an originally failed run."
            )

        if self.original_failure_category != "solver_reported_error":
            raise ValueError(
                "Only solver_reported_error may use this adjudication path."
            )

        if self.return_code != 0:
            raise ValueError(
                "Adjudicated completed evidence requires return code 0."
            )

        if self.job_finished is not True:
            raise ValueError(
                "Adjudicated completed evidence requires Job finished."
            )

        if self.accepted_increment_count <= 0:
            raise ValueError(
                "Adjudicated evidence requires accepted increments."
            )

        for value, name in (
            (self.final_step, "final_step"),
            (self.final_increment, "final_increment"),
            (self.final_attempt, "final_attempt"),
            (self.final_iterations, "final_iterations"),
        ):
            if value <= 0:
                raise ValueError(
                    f"{name} must be positive."
                )

        if self.sta_size_bytes <= 0:
            raise ValueError(
                "Adjudicated STA artifact must be non-empty."
            )

        if self.sta_completed_checkpoint != self.final_step:
            raise ValueError(
                "STA completed checkpoint does not match "
                "the final FEM step."
            )

        if self.rout_size_bytes <= 0:
            raise ValueError(
                "Adjudicated ROUT artifact must be non-empty."
            )

        if self.rout_stored_step != self.final_step:
            raise ValueError(
                "ROUT stored step does not match the final FEM step."
            )

        if not self.adjudication_reason.strip():
            raise ValueError(
                "Adjudication reason must not be empty."
            )

        if self.schema_version != 1:
            raise ValueError(
                "Unsupported FEM adjudication schema version."
            )

    def to_payload(self) -> dict[str, object]:
        """Return deterministic JSON-compatible adjudication data."""

        return {
            "accepted_increment_count": (
                self.accepted_increment_count
            ),
            "adjudication_reason": self.adjudication_reason,
            "case_hash": self.case_hash,
            "disposition": self.disposition.value,
            "final_attempt": self.final_attempt,
            "final_increment": self.final_increment,
            "final_iterations": self.final_iterations,
            "final_step": self.final_step,
            "job_finished": self.job_finished,
            "original_disposition": self.original_disposition,
            "original_failure_category": (
                self.original_failure_category
            ),
            "original_manifest_relative_path": (
                self.original_manifest_relative_path
            ),
            "original_manifest_sha256": (
                self.original_manifest_sha256
            ),
            "return_code": self.return_code,
            "sta_completed_checkpoint": (
                self.sta_completed_checkpoint
            ),
            "sta_relative_path": self.sta_relative_path,
            "sta_sha256": self.sta_sha256,
            "sta_size_bytes": self.sta_size_bytes,
            "rout_relative_path": self.rout_relative_path,
            "rout_sha256": self.rout_sha256,
            "rout_size_bytes": self.rout_size_bytes,
            "rout_stored_step": self.rout_stored_step,
            "run_id": self.run_id,
            "schema_version": self.schema_version,
        }


def _sha256(path: Path) -> str:
    """Hash one immutable evidence artifact."""

    digest = sha256()

    with path.open("rb") as stream:
        for block in iter(
            lambda: stream.read(1024 * 1024),
            b"",
        ):
            digest.update(block)

    return digest.hexdigest()


def _project_relative(
    *,
    project_root: Path,
    path: Path,
) -> str:
    """Return one normalized project-relative POSIX path."""

    root = project_root.resolve()
    resolved = path.resolve()

    try:
        relative = resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            "Adjudication evidence lies outside project root."
        ) from exc

    return relative.as_posix()


def _require_int(
    data: dict[str, Any],
    name: str,
) -> int:
    """Require one integer manifest field."""

    value = data.get(name)

    if (
        not isinstance(value, int)
        or isinstance(value, bool)
    ):
        raise ValueError(
            f"Manifest field {name!r} must be an integer."
        )

    return value


def read_calculix_rout_stored_step(
    path: Path,
) -> int:
    """Read the stored restart step from a CalculiX ROUT header."""

    if not path.is_file() or path.stat().st_size <= 0:
        raise FileNotFoundError(
            f"CalculiX ROUT artifact not found or empty: {path}"
        )

    with path.open("rb") as stream:
        raw = stream.read(512)

    for endian in ("<", ">"):
        for marker_size, marker_format in (
            (4, "I"),
            (8, "Q"),
        ):
            try:
                offset = 0

                first_size = struct.unpack_from(
                    endian + marker_format,
                    raw,
                    offset,
                )[0]
                offset += marker_size

                if not 1 <= first_size <= 256:
                    continue

                version = raw[
                    offset : offset + first_size
                ]
                offset += first_size

                first_close = struct.unpack_from(
                    endian + marker_format,
                    raw,
                    offset,
                )[0]
                offset += marker_size

                if first_close != first_size:
                    continue

                if not version.startswith(b"Version "):
                    continue

                second_size = struct.unpack_from(
                    endian + marker_format,
                    raw,
                    offset,
                )[0]
                offset += marker_size

                if second_size not in (4, 8):
                    continue

                if second_size == 4:
                    stored_step = struct.unpack_from(
                        endian + "i",
                        raw,
                        offset,
                    )[0]
                else:
                    stored_step = struct.unpack_from(
                        endian + "q",
                        raw,
                        offset,
                    )[0]

                offset += second_size

                second_close = struct.unpack_from(
                    endian + marker_format,
                    raw,
                    offset,
                )[0]

                if second_close != second_size:
                    continue

                if stored_step <= 0:
                    raise ValueError(
                        "CalculiX ROUT stored step must be positive."
                    )

                return int(stored_step)

            except struct.error:
                continue

    raise ValueError(
        "Unable to decode CalculiX ROUT restart header."
    )



def adjudicate_completed_solver_reported_error_run(
    *,
    project_root: Path,
    manifest_path: Path,
    expected_run_id: str,
    expected_case_hash: str,
    expected_final_step: int,
    expected_checkpoint_step_time: float,
    adjudication_reason: str,
) -> FemRunAdjudication:
    """Adjudicate one narrowly eligible failed CalculiX execution.

    This does not mutate or reinterpret the original run manifest.
    It establishes a separate evidence layer proving that a
    solver_reported_error run nevertheless reached its governed
    final state and retained the matching CalculiX restart state.
    """

    if expected_final_step <= 0:
        raise ValueError(
            "Expected final step must be positive."
        )

    if expected_checkpoint_step_time <= 0.0:
        raise ValueError(
            "Expected checkpoint step time must be positive."
        )

    if not manifest_path.is_file():
        raise FileNotFoundError(
            f"FEM run manifest not found: {manifest_path}"
        )

    manifest = json.loads(
        manifest_path.read_text(
            encoding="utf-8",
        )
    )

    if not isinstance(manifest, dict):
        raise ValueError(
            "FEM run manifest must contain a JSON object."
        )

    if manifest.get("schema_version") != 1:
        raise ValueError(
            "Unsupported FEM run manifest schema version."
        )

    if manifest.get("run_id") != expected_run_id:
        raise ValueError(
            "FEM adjudication run identity mismatch."
        )

    if manifest.get("case_hash") != expected_case_hash:
        raise ValueError(
            "FEM adjudication case-hash mismatch."
        )

    if manifest.get("disposition") != "failed":
        raise ValueError(
            "Only an originally failed FEM manifest may be adjudicated."
        )

    if (
        manifest.get("failure_category")
        != "solver_reported_error"
    ):
        raise ValueError(
            "Only solver_reported_error is eligible for adjudication."
        )

    return_code = _require_int(
        manifest,
        "return_code",
    )

    if return_code != 0:
        raise ValueError(
            "Adjudication requires solver return code 0."
        )

    if manifest.get("job_finished") is not True:
        raise ValueError(
            "Adjudication requires explicit Job finished evidence."
        )

    accepted_increment_count = _require_int(
        manifest,
        "accepted_increment_count",
    )

    if accepted_increment_count <= 0:
        raise ValueError(
            "Adjudication requires accepted nonlinear increments."
        )

    final_step = _require_int(
        manifest,
        "final_step",
    )
    final_increment = _require_int(
        manifest,
        "final_increment",
    )
    final_attempt = _require_int(
        manifest,
        "final_attempt",
    )
    final_iterations = _require_int(
        manifest,
        "final_iterations",
    )

    if final_step != expected_final_step:
        raise ValueError(
            "Manifest final step does not match the governed "
            "expected final checkpoint."
        )

    artifacts = manifest.get("artifacts")

    if not isinstance(artifacts, list):
        raise ValueError(
            "FEM run manifest artifacts must be a list."
        )

    sta_entries = [
        item
        for item in artifacts
        if (
            isinstance(item, dict)
            and item.get("role") == "sta"
        )
    ]

    if len(sta_entries) != 1:
        raise ValueError(
            "Adjudication requires exactly one manifested STA artifact."
        )

    rout_entries = [
        item
        for item in artifacts
        if (
            isinstance(item, dict)
            and item.get("role") == "rout"
        )
    ]

    if len(rout_entries) != 1:
        raise ValueError(
            "Adjudication requires exactly one manifested ROUT artifact."
        )

    sta_entry = sta_entries[0]
    rout_entry = rout_entries[0]

    sta_relative_path = sta_entry.get(
        "relative_path"
    )
    sta_manifest_sha = sta_entry.get(
        "sha256"
    )
    sta_manifest_size = sta_entry.get(
        "size_bytes"
    )

    if not isinstance(sta_relative_path, str):
        raise ValueError(
            "Manifest STA path is invalid."
        )

    if (
        not isinstance(sta_manifest_sha, str)
        or not _SHA256_PATTERN.fullmatch(
            sta_manifest_sha
        )
    ):
        raise ValueError(
            "Manifest STA SHA-256 is invalid."
        )

    if (
        not isinstance(sta_manifest_size, int)
        or isinstance(sta_manifest_size, bool)
        or sta_manifest_size <= 0
    ):
        raise ValueError(
            "Manifest STA size is invalid."
        )

    sta_pure = PurePosixPath(
        sta_relative_path
    )

    if (
        sta_pure.is_absolute()
        or ".." in sta_pure.parts
        or "\\" in sta_relative_path
    ):
        raise ValueError(
            "Manifest STA path is not project-relative."
        )

    sta_path = (
        project_root
        / Path(*sta_pure.parts)
    )

    if not sta_path.is_file():
        raise FileNotFoundError(
            f"Manifested STA artifact not found: {sta_path}"
        )

    actual_sta_size = sta_path.stat().st_size

    if actual_sta_size != sta_manifest_size:
        raise ValueError(
            "STA artifact size differs from immutable manifest."
        )

    actual_sta_sha = _sha256(
        sta_path
    )

    if actual_sta_sha != sta_manifest_sha:
        raise ValueError(
            "STA artifact SHA-256 differs from immutable manifest."
        )

    sta_records = parse_calculix_sta_records(
        sta_path.read_text(
            encoding="utf-8",
            errors="replace",
        )
    )

    sta_completed_checkpoint = (
        find_last_completed_checkpoint(
            sta_records,
            checkpoint_count=expected_final_step,
            configured_step_time=(
                expected_checkpoint_step_time
            ),
        )
    )

    if sta_completed_checkpoint != expected_final_step:
        raise ValueError(
            "STA completed checkpoint does not match "
            "the governed final checkpoint."
        )

    rout_relative_path = rout_entry.get(
        "relative_path"
    )
    rout_manifest_sha = rout_entry.get(
        "sha256"
    )
    rout_manifest_size = rout_entry.get(
        "size_bytes"
    )

    if not isinstance(rout_relative_path, str):
        raise ValueError(
            "Manifest ROUT path is invalid."
        )

    if (
        not isinstance(rout_manifest_sha, str)
        or not _SHA256_PATTERN.fullmatch(
            rout_manifest_sha
        )
    ):
        raise ValueError(
            "Manifest ROUT SHA-256 is invalid."
        )

    if (
        not isinstance(rout_manifest_size, int)
        or isinstance(rout_manifest_size, bool)
        or rout_manifest_size <= 0
    ):
        raise ValueError(
            "Manifest ROUT size is invalid."
        )

    rout_pure = PurePosixPath(
        rout_relative_path
    )

    if (
        rout_pure.is_absolute()
        or ".." in rout_pure.parts
        or "\\" in rout_relative_path
    ):
        raise ValueError(
            "Manifest ROUT path is not project-relative."
        )

    rout_path = (
        project_root
        / Path(*rout_pure.parts)
    )

    if not rout_path.is_file():
        raise FileNotFoundError(
            f"Manifested ROUT artifact not found: {rout_path}"
        )

    actual_rout_size = (
        rout_path.stat().st_size
    )

    if actual_rout_size != rout_manifest_size:
        raise ValueError(
            "ROUT artifact size differs from immutable manifest."
        )

    actual_rout_sha = _sha256(
        rout_path
    )

    if actual_rout_sha != rout_manifest_sha:
        raise ValueError(
            "ROUT artifact SHA-256 differs from immutable manifest."
        )

    rout_stored_step = (
        read_calculix_rout_stored_step(
            rout_path
        )
    )

    if rout_stored_step != expected_final_step:
        raise ValueError(
            "ROUT stored restart step does not match "
            "the governed final checkpoint."
        )

    return FemRunAdjudication(
        run_id=expected_run_id,
        case_hash=expected_case_hash,
        original_manifest_relative_path=(
            _project_relative(
                project_root=project_root,
                path=manifest_path,
            )
        ),
        original_manifest_sha256=_sha256(
            manifest_path
        ),
        original_disposition=str(
            manifest["disposition"]
        ),
        original_failure_category=str(
            manifest["failure_category"]
        ),
        return_code=return_code,
        job_finished=True,
        accepted_increment_count=(
            accepted_increment_count
        ),
        final_step=final_step,
        final_increment=final_increment,
        final_attempt=final_attempt,
        final_iterations=final_iterations,
        sta_relative_path=(
            _project_relative(
                project_root=project_root,
                path=sta_path,
            )
        ),
        sta_size_bytes=actual_sta_size,
        sta_sha256=actual_sta_sha,
        sta_completed_checkpoint=(
            sta_completed_checkpoint
        ),
        rout_relative_path=(
            _project_relative(
                project_root=project_root,
                path=rout_path,
            )
        ),
        rout_size_bytes=actual_rout_size,
        rout_sha256=actual_rout_sha,
        rout_stored_step=rout_stored_step,
        adjudication_reason=(
            adjudication_reason
        ),
    )


def verify_fem_run_adjudication(
    *,
    project_root: Path,
    adjudication_path: Path,
    manifest_path: Path,
    expected_run_id: str,
    expected_case_hash: str,
    expected_final_step: int,
    expected_checkpoint_step_time: float,
    adjudication_reason: str,
) -> FemRunAdjudication:
    """Recompute and verify one persisted FEM-run adjudication."""

    if not adjudication_path.is_file():
        raise FileNotFoundError(
            f"FEM run adjudication not found: {adjudication_path}"
        )

    persisted = json.loads(
        adjudication_path.read_text(
            encoding="utf-8",
        )
    )

    if not isinstance(persisted, dict):
        raise ValueError(
            "FEM run adjudication must contain a JSON object."
        )

    recomputed = (
        adjudicate_completed_solver_reported_error_run(
            project_root=project_root,
            manifest_path=manifest_path,
            expected_run_id=expected_run_id,
            expected_case_hash=expected_case_hash,
            expected_final_step=expected_final_step,
            expected_checkpoint_step_time=(
                expected_checkpoint_step_time
            ),
            adjudication_reason=adjudication_reason,
        )
    )

    expected_payload = recomputed.to_payload()

    if persisted != expected_payload:
        raise ValueError(
            "Persisted FEM-run adjudication does not match "
            "independently recomputed evidence."
        )

    return recomputed



def write_fem_run_adjudication(
    path: Path,
    adjudication: FemRunAdjudication,
) -> Path:
    """Write deterministic adjudication evidence."""

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            adjudication.to_payload(),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )

    return path
