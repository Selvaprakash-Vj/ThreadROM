"""Restart-safe evidence ledger for preliminary FEM physics assessments.

Shared by model-specific factory ports. This module cannot issue an independent
physics certificate, authorize FEM or retire solver files. A stored PASS means
only that the previously verified governed checks passed for pinned evidence.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Mapping


RECORD_FILENAME = "adaptive_fem_physics_assessment.json"
RECORD_SCHEMA = "threadrom.preliminary_fem_physics_assessment.v1"

# Identifies the evaluator/extractor/force witness plus the governed C01
# definitions used for the preliminary assessment. A code/policy change
# invalidates the durable preliminary result instead of silently reusing it.
SOURCE_PATHS = (
    "src/threadrom/factory/production_doe_c01_physics.py",
    "src/threadrom/factory/adaptive_fem_physics_assessment.py",
    "src/threadrom/factory/fem_physics_acceptance.py",
    "src/threadrom/factory/fem_result_extraction.py",
    "src/threadrom/postprocessing/calculix_external_equilibrium.py",
    "config/fem_result_extraction.toml",
    "config/complete_joint_contact.toml",
    "config/complete_joint_preload.toml",
    "config/complete_joint_calculix_transfer.toml",
    "config/complete_joint_boundary_regions.toml",
    "config/phase3_production_doe.toml",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_fingerprints(repo_root: Path) -> dict[str, str]:
    return {
        relative: sha256_file(repo_root / relative)
        for relative in SOURCE_PATHS
    }


def _manifest_fingerprint(repo_root: Path, case_run_id: str,
                          run_id: str) -> tuple[Path, str]:
    if not run_id.startswith(case_run_id + "_cal_"):
        raise RuntimeError("Assessment run is outside governed case identity.")
    run_dir = (repo_root / "simulations/staging/phase3_cp8_production_doe"
               / "TRM-PDOE-C01/solver_preparation" / case_run_id / run_id)
    run_dir = run_dir.resolve(strict=True)
    if not run_dir.is_relative_to(repo_root.resolve(strict=True)):
        raise RuntimeError("Assessment directory escapes repository.")
    path = run_dir / "fem_run_manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8-sig"))
    if (manifest.get("run_id") != run_id
            or manifest.get("job_name") != run_id
            or manifest.get("disposition") != "succeeded"
            or manifest.get("job_finished") is not True
            or manifest.get("return_code") != 0):
        raise RuntimeError("Preliminary assessment requires verified solver success.")
    return run_dir, sha256_file(path)


def _canonical(record: Mapping[str, object]) -> bytes:
    return (json.dumps(record, sort_keys=True, indent=2, allow_nan=False)
            + "\n").encode("utf-8")


def _validate_result(result: Mapping[str, object], *, case_id: str,
                     run_id: str, trial_index: int) -> None:
    if result.get("case_id") != case_id or result.get("run_id") != run_id:
        raise RuntimeError("Physics result differs from recovered run identity.")
    if type(trial_index) is not int or trial_index < 1:
        raise RuntimeError("Invalid governed trial index.")
    if result.get("calibration") != f"ACCEPTED_TRIAL_{trial_index}":
        raise RuntimeError("Calibration does not match the governed trial.")
    if result.get("final_physics_certified") is not False:
        raise RuntimeError("Preliminary result cannot claim final certification.")
    if result.get("new_fem_authorized") is not False or result.get(
            "rout_retirement_authorized") is not False:
        raise RuntimeError("Assessment result must not authorize FEM or retirement.")
    checks = result.get("physics_checks")
    if not isinstance(checks, list) or not checks:
        raise RuntimeError("Missing governed FEM physics checks.")
    names = [check.get("name") for check in checks if isinstance(check, dict)]
    if len(names) != len(checks) or len(set(names)) != len(names):
        raise RuntimeError("Ambiguous governed FEM physics checks.")
    hard_failed = sorted(
        check["name"] for check in checks
        if check.get("kind") == "hard_gate" and check.get("passed") is not True
    )
    failed = result.get("failed_governed_checks")
    if not isinstance(failed, list) or sorted(failed) != hard_failed:
        raise RuntimeError("Result disagrees with its governed hard gates.")
    pass_claimed = result.get("physics_gates") == "PASS_PENDING_INDEPENDENT_CERTIFICATION"
    if pass_claimed != (not hard_failed and result.get("equilibrium_status") == "pass"):
        raise RuntimeError("Physics PASS disagrees with measured hard gates or equilibrium.")
    if result.get("rotational_moment_equilibrium_status") != "not_assessed":
        raise RuntimeError("Uncertified C01 rotational moment status changed unexpectedly.")


def persist_preliminary_c01_assessment(*, repo_root: Path, case_id: str,
                                       case_run_id: str, run_id: str,
                                       trial_index: int,
                                       result: Mapping[str, object]) -> Path:
    """Persist once; identical replays are idempotent, conflict is fatal."""
    root = repo_root.resolve(strict=True)
    if type(trial_index) is not int or trial_index < 1:
        raise RuntimeError("Invalid governed trial index.")
    _validate_result(
        result, case_id=case_id, run_id=run_id,
        trial_index=trial_index,
    )
    run_dir, manifest_sha = _manifest_fingerprint(root, case_run_id, run_id)
    path = run_dir / RECORD_FILENAME
    record = {
        "schema": RECORD_SCHEMA,
        "record_status": "PRELIMINARY_NOT_INDEPENDENTLY_CERTIFIED",
        "case_id": case_id,
        "case_run_id": case_run_id,
        "run_id": run_id,
        "trial_index": trial_index,
        "manifest_sha256": manifest_sha,
        "source_sha256": source_fingerprints(root),
        "result": dict(result),
        "independent_full_physics_certificate_issued": False,
        "rotational_moment_equilibrium_certified": False,
        "solver_launch_authorized": False,
        "rout_retirement_authorized": False,
    }
    content = _canonical(record)
    try:
        with path.open("xb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError:
        if path.read_bytes() != content:
            raise RuntimeError(
                "Existing immutable preliminary FEM assessment differs; engineering review required."
            ) from None
    return path


def recover_preliminary_c01_assessment(*, repo_root: Path, case_id: str,
                                       case_run_id: str, run_id: str,
                                       trial_index: int) -> dict[str, object] | None:
    """Recover a pinned preliminary report, never a final certificate."""
    root = repo_root.resolve(strict=True)
    run_dir, manifest_sha = _manifest_fingerprint(root, case_run_id, run_id)
    path = run_dir / RECORD_FILENAME
    if not path.exists():
        return None
    raw = path.read_bytes()
    record = json.loads(raw)
    if raw != _canonical(record):
        raise RuntimeError("Preliminary physics record changed or is not canonical.")
    if (record.get("schema") != RECORD_SCHEMA
            or record.get("record_status") != "PRELIMINARY_NOT_INDEPENDENTLY_CERTIFIED"
            or record.get("case_id") != case_id
            or record.get("case_run_id") != case_run_id
            or record.get("run_id") != run_id
            or record.get("trial_index") != trial_index
            or record.get("manifest_sha256") != manifest_sha
            or record.get("independent_full_physics_certificate_issued") is not False
            or record.get("rotational_moment_equilibrium_certified") is not False
            or record.get("solver_launch_authorized") is not False
            or record.get("rout_retirement_authorized") is not False):
        raise RuntimeError("Preliminary physics record identity, scope or source drift.")
    result = record.get("result")
    if not isinstance(result, dict):
        raise RuntimeError("Preliminary physics record lacks governed result.")
    _validate_result(
        result, case_id=case_id, run_id=run_id,
        trial_index=trial_index,
    )

    pinned_sources = record.get("source_sha256")
    current_sources = source_fingerprints(root)

    if pinned_sources != current_sources:
        historical_assessor_path = (
            "src/threadrom/factory/production_doe_c01_physics.py"
        )
        historical_assessor_sha256 = (
            "81d336835f12eeee1919b0f33449e048"
            "1164c8978adcc5e716c4cc50afd41b40"
        )

        if not (
            case_id in {
                "D-INT-013", "D-INT-014",
                "D-INT-015", "D-INT-016",
            }
            and trial_index == 1
            and isinstance(pinned_sources, dict)
            and set(pinned_sources) == set(current_sources)
            and pinned_sources.get(historical_assessor_path)
                == historical_assessor_sha256
            and all(
                pinned_sources[name] == current_sources[name]
                for name in current_sources
                if name != historical_assessor_path
            )
        ):
            raise RuntimeError(
                "Preliminary physics record has unrecognized source drift."
            )

        # Reproduce the historical result under the current assessor.
        # Any changed or missing historical field blocks recovery.
        from threadrom.factory.production_doe_c01_physics import (
            assess_c01_saved_trial,
        )

        replayed = assess_c01_saved_trial(
            repo_root=root,
            case_id=case_id,
        )

        if not (
            replayed.get("run_id") == run_id
            and replayed.get("trial_index") == trial_index
            and set(replayed) - set(result) == {"trial_index"}
            and not (set(result) - set(replayed))
            and all(
                replayed[name] == value
                for name, value in result.items()
            )
        ):
            raise RuntimeError(
                "Historical preliminary physics result was not reproduced."
            )

    return result
