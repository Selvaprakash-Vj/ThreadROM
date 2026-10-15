"""Immutable governed physics certificates for diversified FEM cases.

This module freezes already-completed, already-accepted FEM evidence.
It never launches FEM, grants execution authority, accesses holdouts,
or claims independent human review.
"""

from __future__ import annotations

import hashlib
import json
import os

from pathlib import Path
from typing import Mapping, Sequence


CERTIFICATE_FILENAME = (
    "diversified_governed_physics_certificate.json"
)

CERTIFICATE_SCHEMA = (
    "threadrom.diversified_governed_physics_certificate.v1"
)

CERTIFICATE_DISPOSITION = (
    "GOVERNED_FULL_PHYSICS_ACCEPTED"
)

DEFAULT_SOURCE_PATHS = (
    "src/threadrom/factory/diversified_fem_physics_certificate.py",
    "src/threadrom/factory/fem_physics_acceptance.py",
    "src/threadrom/factory/fem_acceptance_policy.py",
    "src/threadrom/factory/fem_result_extraction.py",
    "src/threadrom/factory/fem_preload_calibration_measurement.py",
    "src/threadrom/factory/preload_calibration_campaign.py",
    "src/threadrom/postprocessing/calculix_external_equilibrium.py",
    "src/threadrom/solver/complete_joint_physical_pretension.py",
    "scripts/run_phase3_diversified_pilot_adaptive_factory.py",
    "config/fem_result_extraction.toml",
    "config/complete_joint_contact.toml",
    "config/complete_joint_preload.toml",
    "config/complete_joint_calculix_transfer.toml",
    "config/complete_joint_boundary_regions.toml",
    "docs/phase3_diversified_doe/design_proposal.json",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as stream:
        for chunk in iter(
            lambda: stream.read(8 * 1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def _canonical(
    payload: Mapping[str, object],
) -> bytes:
    return (
        json.dumps(
            payload,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _artifact_paths(
    run_dir: Path,
    run_id: str,
) -> dict[str, Path]:
    return {
        "manifest": (
            run_dir / "fem_run_manifest.json"
        ),
        "input_deck": (
            run_dir / f"{run_id}.inp"
        ),
        "dat": (
            run_dir / f"{run_id}.dat"
        ),
        "frd": (
            run_dir / f"{run_id}.frd"
        ),
        "sta": (
            run_dir / f"{run_id}.sta"
        ),
        "cvg": (
            run_dir / f"{run_id}.cvg"
        ),
        "stdout": (
            run_dir / f"{run_id}.stdout.log"
        ),
    }


def artifact_fingerprints(
    run_dir: Path,
    run_id: str,
) -> dict[str, str]:
    paths = _artifact_paths(
        run_dir,
        run_id,
    )

    missing = [
        str(path)
        for path in paths.values()
        if (
            not path.is_file()
            or path.stat().st_size <= 0
        )
    ]

    if missing:
        raise RuntimeError(
            "Governed certificate evidence is "
            "missing or empty: "
            + ", ".join(missing)
        )

    return {
        name: sha256_file(path)
        for name, path in paths.items()
    }


def source_fingerprints(
    repo_root: Path,
    source_paths: Sequence[str] = (
        DEFAULT_SOURCE_PATHS
    ),
) -> dict[str, str]:
    result: dict[str, str] = {}

    for relative in source_paths:
        if (
            not isinstance(relative, str)
            or not relative.strip()
        ):
            raise ValueError(
                "Certificate source paths "
                "must be non-blank strings."
            )

        path = repo_root / relative

        if not path.is_file():
            raise RuntimeError(
                "Certificate source is missing: "
                f"{relative}"
            )

        result[relative] = sha256_file(path)

    return result


def _validate_assessment(
    assessment: Mapping[str, object],
) -> None:
    if (
        assessment.get(
            "calibration_disposition"
        )
        != "accept"
    ):
        raise RuntimeError(
            "Governed calibration is not ACCEPT."
        )

    if (
        assessment.get(
            "next_trial_run_id"
        )
        is not None
    ):
        raise RuntimeError(
            "Accepted calibration still requests "
            "another trial."
        )

    if (
        assessment.get(
            "equilibrium_status"
        )
        != "pass"
    ):
        raise RuntimeError(
            "Translational equilibrium did not PASS."
        )

    if (
        assessment.get(
            "full_physics_passed"
        )
        is not True
    ):
        raise RuntimeError(
            "Full governed physics did not PASS."
        )

    increments = assessment.get(
        "accepted_increment_count"
    )

    if (
        type(increments) is not int
        or increments < 1
    ):
        raise RuntimeError(
            "Invalid accepted-increment count."
        )

    checks = assessment.get(
        "physics_checks"
    )

    if (
        not isinstance(checks, list)
        or not checks
    ):
        raise RuntimeError(
            "Missing governed physics checks."
        )

    names: list[str] = []
    hard_gate_count = 0

    for check in checks:
        if not isinstance(check, dict):
            raise RuntimeError(
                "Physics check must be a mapping."
            )

        name = check.get("name")
        kind = check.get("kind")
        passed = check.get("passed")

        if (
            not isinstance(name, str)
            or not name.strip()
        ):
            raise RuntimeError(
                "Physics check has invalid name."
            )

        if kind not in {
            "hard_gate",
            "diagnostic",
        }:
            raise RuntimeError(
                "Physics check has invalid kind."
            )

        if passed is not True:
            raise RuntimeError(
                "Certificate cannot freeze a "
                f"failed physics check: {name}"
            )

        if kind == "hard_gate":
            hard_gate_count += 1

        names.append(name)

    if len(set(names)) != len(names):
        raise RuntimeError(
            "Governed physics-check names "
            "must be unique."
        )

    if hard_gate_count < 1:
        raise RuntimeError(
            "Certificate requires at least "
            "one governed hard gate."
        )

    if assessment.get(
        "failed_governed_checks"
    ) != []:
        raise RuntimeError(
            "Certificate assessment reports "
            "failed governed checks."
        )

    maximum_residual = assessment.get(
        "maximum_translational_resultant_n"
    )

    tolerance = assessment.get(
        "translational_force_tolerance_n"
    )

    if (
        isinstance(maximum_residual, bool)
        or not isinstance(
            maximum_residual,
            (int, float),
        )
        or isinstance(tolerance, bool)
        or not isinstance(
            tolerance,
            (int, float),
        )
        or float(maximum_residual) < 0.0
        or float(tolerance) < 0.0
        or float(maximum_residual)
        > float(tolerance)
    ):
        raise RuntimeError(
            "Translational equilibrium evidence "
            "is outside its governed tolerance."
        )

    if (
        assessment.get(
            "rotational_moment_equilibrium_status"
        )
        != "not_assessed"
    ):
        raise RuntimeError(
            "Unexpected rotational-moment "
            "certification claim."
        )


def build_governed_physics_certificate(
    *,
    repo_root: Path,
    run_dir: Path,
    case_id: str,
    case_hash: str,
    case_run_id: str,
    run_id: str,
    trial_index: int,
    assessment: Mapping[str, object],
    source_paths: Sequence[str] = (
        DEFAULT_SOURCE_PATHS
    ),
) -> dict[str, object]:
    root = repo_root.resolve(strict=True)
    solved = run_dir.resolve(strict=True)

    if (
        not case_id.strip()
        or not case_run_id.strip()
        or not run_id.strip()
    ):
        raise RuntimeError(
            "Governed certificate identity "
            "cannot be blank."
        )

    if (
        len(case_hash) != 64
        or any(
            ch not in "0123456789abcdef"
            for ch in case_hash
        )
    ):
        raise RuntimeError(
            "Invalid governed case hash."
        )

    if (
        type(trial_index) is not int
        or trial_index < 1
    ):
        raise RuntimeError(
            "Invalid governed trial index."
        )

    expected_run = (
        f"{case_run_id}_cal_"
        f"{trial_index:02d}"
    )

    if run_id != expected_run:
        raise RuntimeError(
            "Governed trial/run identity mismatch."
        )

    try:
        solved.relative_to(root)
    except ValueError as exc:
        raise RuntimeError(
            "Governed run directory is outside "
            "the project root."
        ) from exc

    _validate_assessment(
        assessment
    )

    return {
        "schema": CERTIFICATE_SCHEMA,
        "record_status": "FINAL",
        "disposition": (
            CERTIFICATE_DISPOSITION
        ),
        "case_id": case_id,
        "case_hash": case_hash,
        "case_run_id": case_run_id,
        "run_id": run_id,
        "trial_index": trial_index,
        "artifact_sha256": (
            artifact_fingerprints(
                solved,
                run_id,
            )
        ),
        "source_sha256": (
            source_fingerprints(
                root,
                source_paths,
            )
        ),
        "assessment": dict(
            assessment
        ),
        "independent_human_review": False,
        "independent_human_review_claimed": False,
        "additional_fem_authorized": False,
        "solver_launch_authorized": False,
        "artifact_retirement_authorized": False,
        "holdout_access_authorized": False,
        "scope_limitation": (
            "Governed computational certification "
            "of the completed diversified FEM case. "
            "Rotational MPC/generalized-moment "
            "equilibrium is not independently "
            "assessed by this certificate."
        ),
    }


def persist_governed_physics_certificate(
    *,
    repo_root: Path,
    run_dir: Path,
    case_id: str,
    case_hash: str,
    case_run_id: str,
    run_id: str,
    trial_index: int,
    assessment: Mapping[str, object],
    source_paths: Sequence[str] = (
        DEFAULT_SOURCE_PATHS
    ),
) -> Path:
    record = (
        build_governed_physics_certificate(
            repo_root=repo_root,
            run_dir=run_dir,
            case_id=case_id,
            case_hash=case_hash,
            case_run_id=case_run_id,
            run_id=run_id,
            trial_index=trial_index,
            assessment=assessment,
            source_paths=source_paths,
        )
    )

    path = (
        run_dir.resolve(strict=True)
        / CERTIFICATE_FILENAME
    )

    content = _canonical(record)

    try:
        with path.open("xb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())

    except FileExistsError:
        if path.read_bytes() != content:
            raise RuntimeError(
                "Existing immutable diversified "
                "physics certificate differs; "
                "engineering review required."
            ) from None

    return path


def recover_governed_physics_certificate(
    *,
    repo_root: Path,
    run_dir: Path,
    case_id: str,
    case_hash: str,
    case_run_id: str,
    run_id: str,
    trial_index: int,
    source_paths: Sequence[str] = (
        DEFAULT_SOURCE_PATHS
    ),
) -> dict[str, object] | None:
    root = repo_root.resolve(strict=True)
    solved = run_dir.resolve(strict=True)

    path = (
        solved
        / CERTIFICATE_FILENAME
    )

    if not path.exists():
        return None

    raw = path.read_bytes()
    record = json.loads(raw)

    if raw != _canonical(record):
        raise RuntimeError(
            "Diversified physics certificate "
            "is not canonical or changed."
        )

    expected = {
        "schema": CERTIFICATE_SCHEMA,
        "record_status": "FINAL",
        "disposition": (
            CERTIFICATE_DISPOSITION
        ),
        "case_id": case_id,
        "case_hash": case_hash,
        "case_run_id": case_run_id,
        "run_id": run_id,
        "trial_index": trial_index,
        "independent_human_review": False,
        "independent_human_review_claimed": False,
        "additional_fem_authorized": False,
        "solver_launch_authorized": False,
        "artifact_retirement_authorized": False,
        "holdout_access_authorized": False,
    }

    for name, value in expected.items():
        if record.get(name) != value:
            raise RuntimeError(
                "Diversified certificate identity "
                f"or scope drift: {name}"
            )

    if (
        record.get("artifact_sha256")
        != artifact_fingerprints(
            solved,
            run_id,
        )
    ):
        raise RuntimeError(
            "Certified solver artifact changed."
        )

    if (
        record.get("source_sha256")
        != source_fingerprints(
            root,
            source_paths,
        )
    ):
        raise RuntimeError(
            "Certified assessment source changed."
        )

    assessment = record.get(
        "assessment"
    )

    if not isinstance(
        assessment,
        dict,
    ):
        raise RuntimeError(
            "Certificate lacks governed "
            "assessment."
        )

    _validate_assessment(
        assessment
    )

    return record
