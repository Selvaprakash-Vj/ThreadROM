from __future__ import annotations

import hashlib
import json
import re

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class VerifiedCompletedTrial:
    run_id: str
    case_hash: str
    manifest_path: Path
    dat_path: Path
    deck_path: Path
    dat_sha256: str
    deck_sha256: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_completed_trial(
    *,
    repo_root: Path,
    manifest_path: Path,
    expected_run_id: str,
    expected_case_hash: str,
    expected_deck_sha256: str,
) -> VerifiedCompletedTrial:
    """Verify completed-run identity and calibration inputs. Never runs FEM."""

    root = repo_root.resolve()
    manifest_path = manifest_path.resolve()

    try:
        manifest_path.relative_to(root)
    except ValueError as exc:
        raise RuntimeError("Manifest is outside the project root.") from exc

    if (
        manifest_path.name != "fem_run_manifest.json"
        or manifest_path.parent.name != expected_run_id
        or not re.fullmatch(r"[0-9a-f]{64}", expected_case_hash)
        or not re.fullmatch(r"[0-9a-f]{64}", expected_deck_sha256)
    ):
        raise RuntimeError("Expected completed-trial identity is invalid.")

    if not manifest_path.is_file():
        raise RuntimeError("Completed-trial manifest is missing.")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if (
        manifest.get("run_id") != expected_run_id
        or manifest.get("job_name") != expected_run_id
        or manifest.get("case_hash") != expected_case_hash
        or manifest.get("disposition") != "succeeded"
        or manifest.get("job_finished") is not True
        or manifest.get("return_code") != 0
        or manifest.get("failure_category") is not None
        or manifest.get("failure_message") is not None
        or type(manifest.get("accepted_increment_count")) is not int
        or manifest["accepted_increment_count"] < 1
        or type(manifest.get("final_step")) is not int
        or manifest["final_step"] < 1
    ):
        raise RuntimeError(
            "Completed-trial identity, completion or solver status failed."
        )

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        raise RuntimeError("Completed-run artifact list is missing.")

    def verified_artifact(role: str, extension: str) -> tuple[Path, str]:
        matches = [
            item for item in artifacts
            if isinstance(item, dict) and item.get("role") == role
        ]
        if len(matches) != 1:
            raise RuntimeError(f"Expected exactly one {role} artifact.")

        item = matches[0]
        expected_path = (
            manifest_path.parent / f"{expected_run_id}.{extension}"
        )
        expected_relative = expected_path.relative_to(root).as_posix()

        if item.get("relative_path") != expected_relative:
            raise RuntimeError(f"{role} artifact path/identity mismatch.")

        if (
            not expected_path.is_file()
            or type(item.get("size_bytes")) is not int
            or item["size_bytes"] <= 0
            or expected_path.stat().st_size != item["size_bytes"]
        ):
            raise RuntimeError(f"{role} artifact missing or size mismatch.")

        recorded_hash = item.get("sha256")
        if (
            not isinstance(recorded_hash, str)
            or not re.fullmatch(r"[0-9a-f]{64}", recorded_hash)
        ):
            raise RuntimeError(f"{role} artifact hash is invalid.")

        actual_hash = _sha256(expected_path)
        if actual_hash != recorded_hash:
            raise RuntimeError(f"{role} artifact SHA-256 mismatch.")

        return expected_path, actual_hash

    dat_path, dat_hash = verified_artifact("dat", "dat")
    deck_path, deck_hash = verified_artifact("input_deck", "inp")

    if deck_hash != expected_deck_sha256:
        raise RuntimeError(
            "Completed-run deck differs from certified trial preparation."
        )

    return VerifiedCompletedTrial(
        run_id=expected_run_id,
        case_hash=expected_case_hash,
        manifest_path=manifest_path,
        dat_path=dat_path,
        deck_path=deck_path,
        dat_sha256=dat_hash,
        deck_sha256=deck_hash,
    )
