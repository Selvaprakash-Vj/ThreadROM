"""Read-only independent C01 governed-scope certificate recovery.

A certificate is only valid for the already accepted C01 Trial-1 13-gate
policy. Moment equilibrium remains NOT_ASSESSED, and no deletion/launch
permissions follow from this certificate. No state is inferred from filenames.
"""
from __future__ import annotations

import hashlib
import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Mapping

from threadrom.factory.adaptive_fem_physics_records import (
    RECORD_FILENAME,
    recover_preliminary_c01_assessment,
    sha256_file,
)

CERTIFICATE_FILENAME = "independent_governed_physics_certificate.json"
CERTIFICATE_SCHEMA = "threadrom.c01.governed_physics_certificate.v1"
ACCEPTED_TRIAL_CERTIFICATE_SCHEMA = "threadrom.c01.governed_physics_certificate.v2"
_CERTIFIED_CASES = frozenset({
    "D-INT-012", "D-INT-013", "D-INT-014", "D-INT-015", "D-INT-016"
})
_ARTIFACT_SUFFIXES = {
    "input_deck": ".inp",
    "dat": ".dat",
    "sta": ".sta",
    "frd": ".frd",
    "stdout": ".stdout.log",
}
_SCOPE = (
    "Certifies the existing governed 13 hard gates, "
    "including translational force equilibrium; "
    "does not certify rotational-moment equilibrium."
)


def _canonical(record: Mapping[str, object]) -> bytes:
    return (
        json.dumps(record, sort_keys=True, indent=2, allow_nan=False) + "\n"
    ).encode("utf-8")


@lru_cache(maxsize=64)
def _sha256_with_metadata(path: str, size: int, mtime_ns: int, ctime_ns: int) -> str:
    """Stream once per unchanged artifact per process; restart rechecks bytes."""
    return sha256_file(Path(path))


def _verify_artifact(path: Path, *, expected_sha256: str, expected_size: int) -> None:
    if (
        not path.is_file()
        or type(expected_size) is not int
        or expected_size <= 0
    ):
        raise RuntimeError(f"Certified FEM artifact missing/invalid: {path}")
    stat_before = path.stat()
    if stat_before.st_size != expected_size:
        raise RuntimeError(f"Certified FEM artifact size drift: {path}")
    actual = _sha256_with_metadata(
        str(path.resolve(strict=True)), stat_before.st_size,
        stat_before.st_mtime_ns, stat_before.st_ctime_ns,
    )
    stat_after = path.stat()
    if (
        stat_after.st_size != stat_before.st_size
        or stat_after.st_mtime_ns != stat_before.st_mtime_ns
        or stat_after.st_ctime_ns != stat_before.st_ctime_ns
        or actual != expected_sha256
    ):
        raise RuntimeError(f"Certified FEM artifact hash/metadata drift: {path}")


def recover_c01_independent_certificate(
    *,
    repo_root: Path,
    case_id: str,
    case_run_id: str,
    case_hash: str,
    run_id: str,
    trial_index: int,
    preliminary_result: Mapping[str, object] | None = None,
) -> bool:
    """Return True only for independently audited, intact governed evidence.

    Missing certificate -> False (pending). Present but invalid -> fail closed.
    This verifier never creates certificates, accepts ungoverned moment claims,
    authorizes another FEM run, or deletes/authorizes retiring an artifact.
    """
    if (
        case_id not in _CERTIFIED_CASES
        or type(trial_index) is not int
        or trial_index < 1
        or (trial_index == 1 and case_id == "D-INT-012")
    ):
        return False
    # Reject a stale trial/run pairing before touching the evidence store.
    # Governed run IDs may carry a suffix after their trial number.
    trial_prefix = f"{case_run_id}_cal_{trial_index:02d}"
    if not (
        run_id == trial_prefix
        or run_id.startswith(trial_prefix + "_")
    ):
        return False
    root = repo_root.resolve(strict=True)
    if not run_id.startswith(case_run_id + "_cal_"):
        raise RuntimeError("Certificate run identity is outside governed case.")
    run_dir = (
        root / "simulations/staging/phase3_cp8_production_doe"
        / "TRM-PDOE-C01/solver_preparation" / case_run_id / run_id
    ).resolve(strict=True)
    if not run_dir.is_relative_to(root):
        raise RuntimeError("Certificate run directory escapes repository.")
    path = run_dir / CERTIFICATE_FILENAME
    if not path.exists():
        return False
    if not path.is_file():
        raise RuntimeError("Governed certificate path is not a file.")

    if trial_index > 1:
        # Later-trial certificates must identify the currently accepted
        # completed run. Historical Trial-1 certificates retain their
        # original recovery contract.
        from threadrom.factory.production_doe_c01_physics import (
            resolve_accepted_completed_trial,
        )

        accepted = resolve_accepted_completed_trial(
            repo_root=root, case_id=case_id,
        )
        if (
            accepted["governed"].case_run_id != case_run_id
            or accepted["governed"].case_hash != case_hash
            or accepted["run_id"] != run_id
            or accepted["trial_index"] != trial_index
        ):
            raise RuntimeError(
                "Later-trial certificate does not identify the accepted run."
            )

    # Recover source-pinned preliminary physics on every certification check.
    verified_preliminary = recover_preliminary_c01_assessment(
        repo_root=root, case_id=case_id,
        case_run_id=case_run_id, run_id=run_id, trial_index=trial_index,
    )
    if verified_preliminary is None or (
        preliminary_result is not None and verified_preliminary != preliminary_result
    ):
        raise RuntimeError("Independent certificate lost its preliminary source evidence.")
    hard_gates = [
        check for check in verified_preliminary["physics_checks"]
        if check["kind"] == "hard_gate"
    ]
    if (
        verified_preliminary["physics_gates"]
        != "PASS_PENDING_INDEPENDENT_CERTIFICATION"
        or verified_preliminary["calibration"] != f"ACCEPTED_TRIAL_{trial_index}"
        or verified_preliminary["equilibrium_status"] != "pass"
        or verified_preliminary["rotational_moment_equilibrium_status"] != "not_assessed"
        or verified_preliminary["final_physics_certified"] is not False
        or len(hard_gates) != 13
        or any(check["passed"] is not True for check in hard_gates)
        or verified_preliminary["failed_governed_checks"]
    ):
        raise RuntimeError("Independent certificate has no matching governed 13-gate PASS.")

    raw = path.read_bytes()
    try:
        certificate = json.loads(raw)
        if raw != _canonical(certificate):
            raise RuntimeError("Independent physics certificate is not canonical.")
    except (ValueError, TypeError) as exc:
        raise RuntimeError("Independent physics certificate is malformed.") from exc
    if (
        not isinstance(certificate, dict)
        or certificate.get("schema") != (
            CERTIFICATE_SCHEMA if trial_index == 1
            else ACCEPTED_TRIAL_CERTIFICATE_SCHEMA
        )
        or certificate.get("record_status") != "FINAL"
        or certificate.get("disposition") != "GOVERNED_13_HARD_GATES_CERTIFIED"
        or certificate.get("case_id") != case_id
        or certificate.get("case_run_id") != case_run_id
        or certificate.get("case_hash") != case_hash
        or certificate.get("run_id") != run_id
        or certificate.get("trial_index") != trial_index
        or certificate.get("governed_hard_gates_passed") != 13
        or certificate.get("accepted_reaction_states") != 20
        or certificate.get("translational_force_tolerance_n") != 0.001
        or certificate.get("rotational_moment_equilibrium") != "NOT_ASSESSED"
        or certificate.get("scope_limitation") != _SCOPE
        or certificate.get("new_fem_authorized") is not False
        or certificate.get("rout_retirement_authorized") is not False
        or certificate.get("preliminary_record_sha256")
        != sha256_file(run_dir / RECORD_FILENAME)
    ):
        raise RuntimeError("Independent physics certificate identity or scope drift.")
    peak = certificate.get("peak_translational_force_residual_n")
    reported_peak = verified_preliminary["equilibrium_max_resultant_n"]
    if (
        type(peak) not in (int, float)
        or not math.isfinite(peak)
        or peak < 0.0
        or peak > 0.001
        or not math.isclose(peak, reported_peak, rel_tol=0.0, abs_tol=1e-7)
        or verified_preliminary["equilibrium_tolerance_n"] != 0.001
    ):
        raise RuntimeError("Independent certificate force-equilibrium result drift.")

    manifest_path = run_dir / "fem_run_manifest.json"
    if certificate.get("solver_manifest_sha256") != sha256_file(manifest_path):
        raise RuntimeError("Independent certificate solver manifest hash drift.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if (
        manifest.get("case_hash") != case_hash
        or manifest.get("run_id") != run_id
        or manifest.get("job_name") != run_id
        or manifest.get("disposition") != "succeeded"
        or manifest.get("job_finished") is not True
        or manifest.get("return_code") != 0
        or manifest.get("accepted_increment_count") != 20
    ):
        raise RuntimeError("Independent certificate does not match completed solver.")
    pins = certificate.get("artifact_sha256")
    if not isinstance(pins, dict) or set(pins) != set(_ARTIFACT_SUFFIXES):
        raise RuntimeError("Independent certificate artifact pins incomplete.")
    entries = manifest.get("artifacts")
    if not isinstance(entries, list):
        raise RuntimeError("Independent certificate manifest artifacts malformed.")
    for role, suffix in _ARTIFACT_SUFFIXES.items():
        matches = [item for item in entries if item.get("role") == role]
        artifact = run_dir / (run_id + suffix)
        if (
            len(matches) != 1
            or matches[0].get("relative_path")
            != artifact.relative_to(root).as_posix()
            or pins[role] != matches[0].get("sha256")
        ):
            raise RuntimeError(f"Independent certificate {role} identity drift.")
        _verify_artifact(
            artifact,
            expected_sha256=pins[role],
            expected_size=matches[0].get("size_bytes"),
        )
    return True
