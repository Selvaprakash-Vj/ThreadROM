"""Generic, fail-closed, crash-recoverable retirement of a certified .rout.

A physics certificate is necessary but *never* sufficient to delete an artifact.
An independently authorized retention permit must explicitly allow retirement.
This module does not issue permits, launch solvers or weaken physics criteria.
"""
from __future__ import annotations

import hashlib
import json
import os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping


RETIREMENT_SCHEMA = "threadrom.fem_rout_retirement.v1"
PERMIT_SCHEMA = "threadrom.fem_rout_retirement_permit.v1"


def _canonical(value: Mapping[str, object]) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@contextmanager
def _locked_run(run_dir: Path):
    """OS-held single-run lock, released automatically on process crash."""
    lock_path = run_dir / ".rout_retirement.lock"
    with lock_path.open("a+b") as lock:
        lock.seek(0)
        lock.write(b"1")
        lock.flush()
        lock.seek(0)
        if os.name == "nt":
            import msvcrt
            try:
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise RuntimeError("RETIREMENT_BLOCKED: another retirement is active") from exc
            try:
                yield
            finally:
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            try:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise RuntimeError("RETIREMENT_BLOCKED: another retirement is active") from exc
            try:
                yield
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


@dataclass(frozen=True)
class RetirementOutcome:
    status: str
    run_id: str
    size_bytes: int
    retired: bool


def _retire_certified_rout_locked(
    *,
    root: Path,
    run_dir: Path,
    run_id: str,
    manifest_path: Path,
    certificate_path: Path,
    permit_path: Path,
    expected_permit_sha256: str | None,
    verify_independent_certificate: Callable[[], bool],
    active_solver_count: Callable[[], int],
    execute: bool = False,
) -> RetirementOutcome:
    """Preflight or retire one .rout; no implicit authorization or broad globs.

    The independently pinned permit must explicitly allow retirement and name
    the exact canonical certificate, original manifest, artifact hash and size.
    Intent is durable before move/unlink. A post-crash retry uses the same intent
    and permit; conflicting state fails closed. The caller supplies an actual
    independent certificate verifier and process/slot check.
    """
    root = root.resolve(strict=True)
    run_dir = run_dir.resolve(strict=True)
    if not run_dir.is_relative_to(root) or not run_id or Path(run_id).name != run_id:
        raise RuntimeError("RETIREMENT_BLOCKED: unsafe run identity or directory")
    expected_manifest = run_dir / "fem_run_manifest.json"
    expected_certificate = run_dir / "independent_governed_physics_certificate.json"
    expected_permit = run_dir / "independent_rout_retirement_permit.json"
    if (manifest_path.resolve() != expected_manifest or
            certificate_path.resolve() != expected_certificate or
            permit_path.resolve() != expected_permit):
        raise RuntimeError("RETIREMENT_BLOCKED: artifact path identity mismatch")

    # No destructive path even begins unless this independently sourced pin is
    # supplied. The four C01 certificates currently do NOT grant retirement.
    if expected_permit_sha256 is None:
        return RetirementOutcome("HOLD_NO_INDEPENDENT_PERMIT_PIN", run_id, 0, False)
    if len(expected_permit_sha256) != 64 or any(c not in "0123456789abcdef" for c in expected_permit_sha256):
        raise RuntimeError("RETIREMENT_BLOCKED: invalid independent permit pin")
    if not expected_permit.is_file() or _hash(expected_permit) != expected_permit_sha256:
        raise RuntimeError("RETIREMENT_BLOCKED: independent retention permit missing or changed")
    raw = expected_permit.read_bytes()
    try:
        permit = json.loads(raw)
        if raw != _canonical(permit):
            raise ValueError("permit not canonical")
    except (TypeError, ValueError) as exc:
        raise RuntimeError("RETIREMENT_BLOCKED: invalid canonical permit") from exc
    if not expected_manifest.is_file() or not expected_certificate.is_file():
        raise RuntimeError("RETIREMENT_BLOCKED: governing evidence missing")
    if verify_independent_certificate() is not True:
        raise RuntimeError("RETIREMENT_BLOCKED: independent physics certificate invalid")
    if (permit.get("schema") != PERMIT_SCHEMA or
            permit.get("authorization") != "ROUT_RETIREMENT_EXPLICITLY_APPROVED" or
            permit.get("run_id") != run_id or
            permit.get("solver_manifest_sha256") != _hash(expected_manifest) or
            permit.get("independent_certificate_sha256") != _hash(expected_certificate) or
            permit.get("rotational_moment_scope_disposition") not in (
                "INDEPENDENTLY_VERIFIED", "INDEPENDENTLY_CERTIFIED_NOT_REQUIRED"
            ) or
            permit.get("retirement_without_additional_fem") is not True):
        raise RuntimeError("RETIREMENT_BLOCKED: permit identity or physics scope invalid")

    manifest = json.loads(expected_manifest.read_text(encoding="utf-8-sig"))
    if (manifest.get("run_id") != run_id or
            manifest.get("disposition") != "succeeded" or
            manifest.get("job_finished") is not True or
            manifest.get("return_code") != 0):
        raise RuntimeError("RETIREMENT_BLOCKED: solver manifest is not a completed success")
    entries = [item for item in manifest.get("artifacts", ()) if item.get("role") == "rout"]
    artifact = run_dir / f"{run_id}.rout"
    if (len(entries) != 1 or
            entries[0].get("relative_path") != artifact.relative_to(root).as_posix() or
            permit.get("rout_sha256") != entries[0].get("sha256") or
            permit.get("rout_size_bytes") != entries[0].get("size_bytes") or
            type(entries[0].get("size_bytes")) is not int or
            entries[0]["size_bytes"] <= 0):
        raise RuntimeError("RETIREMENT_BLOCKED: manifest/permit .rout identity mismatch")
    size = entries[0]["size_bytes"]
    if active_solver_count() != 0:
        return RetirementOutcome("HOLD_SOLVER_ACTIVE", run_id, size, False)

    intent_path = run_dir / "rout_retirement_intent.json"
    quarantine = run_dir / f"{run_id}.rout.retirement-pending"
    expected_intent = {
        "schema": RETIREMENT_SCHEMA,
        "run_id": run_id,
        "solver_manifest_sha256": _hash(expected_manifest),
        "independent_certificate_sha256": _hash(expected_certificate),
        "independent_permit_sha256": expected_permit_sha256,
        "original_rout_relative_path": artifact.relative_to(root).as_posix(),
        "original_rout_sha256": permit["rout_sha256"],
        "original_rout_size_bytes": size,
        "retirement_disposition": "AUTHORIZED_RETIREMENT_INTENT",
    }
    intent_bytes = _canonical(expected_intent)
    if intent_path.exists() and intent_path.read_bytes() != intent_bytes:
        raise RuntimeError("RETIREMENT_BLOCKED: preexisting retirement intent conflict")

    if artifact.is_symlink() or quarantine.is_symlink():
        raise RuntimeError("RETIREMENT_BLOCKED: symlink is not an immutable FEM artifact")
    source_present = artifact.is_file()
    quarantine_present = quarantine.is_file()
    if source_present and quarantine_present:
        raise RuntimeError("RETIREMENT_BLOCKED: both source and quarantine exist")
    if not source_present and not quarantine_present:
        if not intent_path.is_file() or intent_path.read_bytes() != intent_bytes:
            raise RuntimeError("RETIREMENT_BLOCKED: .rout absent without matching retirement intent")
        return RetirementOutcome("ALREADY_RETIRED", run_id, size, True)

    source = artifact if source_present else quarantine
    before = source.stat()
    if (before.st_size != size or _hash(source) != permit["rout_sha256"]):
        raise RuntimeError("RETIREMENT_BLOCKED: .rout hash/size mismatch")
    after = source.stat()
    if (after.st_size != before.st_size or
            after.st_mtime_ns != before.st_mtime_ns or
            after.st_ctime_ns != before.st_ctime_ns):
        raise RuntimeError("RETIREMENT_BLOCKED: .rout changed during audit")
    if not execute:
        return RetirementOutcome("ELIGIBLE_DRY_RUN", run_id, size, False)

    # No silent auto-delete: the independently pinned permit above is mandatory.
    # Exclusive creation is idempotent on clean restart; conflicting intent blocks.
    if not intent_path.exists():
        try:
            with intent_path.open("xb") as stream:
                stream.write(intent_bytes)
                stream.flush()
                os.fsync(stream.fileno())
        except FileExistsError:
            if intent_path.read_bytes() != intent_bytes:
                raise RuntimeError("RETIREMENT_BLOCKED: concurrent intent changed") from None
    if artifact.is_file():
        if quarantine.exists():
            raise RuntimeError("RETIREMENT_BLOCKED: concurrent quarantine created")
        artifact.rename(quarantine)
    if not quarantine.is_file() or quarantine.stat().st_size != size:
        raise RuntimeError("RETIREMENT_BLOCKED: quarantine transition unverified")
    if active_solver_count() != 0:
        raise RuntimeError("RETIREMENT_BLOCKED: solver became active; quarantine retained")
    quarantine.unlink()
    return RetirementOutcome("RETIRED_WITH_IMMUTABLE_INTENT", run_id, size, True)


def retire_certified_rout(
    *,
    root: Path,
    run_dir: Path,
    run_id: str,
    manifest_path: Path,
    certificate_path: Path,
    permit_path: Path,
    expected_permit_sha256: str | None,
    verify_independent_certificate: Callable[[], bool],
    active_solver_count: Callable[[], int],
    execute: bool = False,
) -> RetirementOutcome:
    """Public serialized wrapper. Never infers a permit from local contents."""
    root = root.resolve(strict=True)
    run_dir = run_dir.resolve(strict=True)
    if not run_dir.is_relative_to(root):
        raise RuntimeError("RETIREMENT_BLOCKED: run directory escapes repository")
    # A missing independent pin is the default, non-destructive policy.
    if expected_permit_sha256 is None:
        return RetirementOutcome("HOLD_NO_INDEPENDENT_PERMIT_PIN", run_id, 0, False)
    with _locked_run(run_dir):
        return _retire_certified_rout_locked(
            root=root, run_dir=run_dir, run_id=run_id,
            manifest_path=manifest_path, certificate_path=certificate_path,
            permit_path=permit_path,
            expected_permit_sha256=expected_permit_sha256,
            verify_independent_certificate=verify_independent_certificate,
            active_solver_count=active_solver_count, execute=execute,
        )
