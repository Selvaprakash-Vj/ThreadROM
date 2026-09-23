from __future__ import annotations

import hashlib
import json

from dataclasses import dataclass
from pathlib import Path

from threadrom.factory.production_doe_case_registry import (
    resolve_governed_c01_case,
)
from threadrom.factory.production_doe_completed_trial import (
    verify_completed_trial,
)
from threadrom.factory.production_doe_gate0_evidence import (
    inspect_gate0_trial1,
)


@dataclass(frozen=True, slots=True)
class TrialHistoryState:
    case_id: str
    completed_run_ids: tuple[str, ...]
    next_trial_index: int | None
    state: str


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(
            lambda: stream.read(8 * 1024 * 1024),
            b"",
        ):
            digest.update(chunk)
    return digest.hexdigest()


def recover_trial_history(
    *,
    repo_root: Path,
    case_id: str,
) -> TrialHistoryState:
    """C01 compatibility adapter; never authorize or execute FEM."""

    root = repo_root.resolve(strict=True)

    governed = resolve_governed_c01_case(
        repo_root=root,
        requested_case_id=case_id,
    )

    gate0 = inspect_gate0_trial1(
        repo_root=root,
        requested_case_id=case_id,
    )

    return recover_verified_trial_history(
        repo_root=root,
        case_id=case_id,
        case_hash=governed.case_hash,
        case_run_id=governed.case_run_id,
        solver_preparation_root=(
            root
            / "simulations/staging/phase3_cp8_production_doe"
            / "TRM-PDOE-C01/solver_preparation"
        ),
        verified_initial_trial=gate0,
        maximum_trials=6,
    )


def recover_verified_trial_history(
    *,
    repo_root: Path,
    case_id: str,
    case_hash: str,
    case_run_id: str,
    solver_preparation_root: Path,
    verified_initial_trial,
    maximum_trials: int,
) -> TrialHistoryState:
    """Recover governed trial history from independently verified inputs.

    The caller must establish campaign provenance, case eligibility,
    initial-trial evidence and applicable calibration policy.

    This function neither authorizes execution nor accepts physics.
    """

    root = repo_root.resolve(strict=True)

    if (
        not isinstance(case_id, str)
        or not case_id
        or case_id != case_id.strip()
    ):
        raise RuntimeError("Invalid governed case identity.")

    if (
        not isinstance(case_hash, str)
        or len(case_hash) != 64
        or any(
            character not in "0123456789abcdef"
            for character in case_hash
        )
    ):
        raise RuntimeError("Invalid governed case hash.")

    if case_run_id != f"trm_fem_{case_hash[:12]}":
        raise RuntimeError(
            "Governed FEM run identity differs from the case hash."
        )

    if (
        type(maximum_trials) is not int
        or maximum_trials < 1
    ):
        raise RuntimeError(
            "Invalid governed maximum-trial policy."
        )

    solver_root = Path(
        solver_preparation_root
    ).resolve()

    try:
        solver_root.relative_to(root)
    except ValueError as exc:
        raise RuntimeError(
            "Solver evidence directory is outside the repository."
        ) from exc

    status = verified_initial_trial.completion_status

    if status == "PENDING_COMPLETED_MANIFEST":
        return TrialHistoryState(
            case_id, (), 1, "WAIT_FOR_TRIAL_1_COMPLETION"
        )

    if status != "COMPLETED_INPUT_EVIDENCE_VERIFIED":
        raise RuntimeError(
            "Unverified initial-trial predecessor."
        )

    gate0 = verified_initial_trial

    if (
        not isinstance(gate0.run_id, str)
        or not gate0.run_id
        or "/" in gate0.run_id
        or "\\" in gate0.run_id
        or gate0.run_id in {".", ".."}
    ):
        raise RuntimeError(
            "Invalid verified initial-trial run identity."
        )

    case_dir = solver_root / case_run_id

    completed = [gate0.run_id]

    # A future-trial directory must not be skipped or silently ignored.
    for index in range(2, maximum_trials + 1):
        run_id = f"{case_run_id}_cal_{index:02d}"
        run_dir = case_dir / run_id

        if not run_dir.exists():
            later = [
                case_dir / f"{case_run_id}_cal_{j:02d}"
                for j in range(index + 1, maximum_trials + 1)
            ]
            if any(item.exists() for item in later):
                raise RuntimeError(
                    "Calibration trial-history gap detected."
                )

            return TrialHistoryState(
                case_id,
                tuple(completed),
                index,
                "NEXT_TRIAL_NOT_PREPARED",
            )

        if not run_dir.is_dir():
            raise RuntimeError("Calibration run path is not a directory.")

        prep_path = (
            run_dir
            / "production_doe_calibration_solver_preparation_record.json"
        )
        sidecar_path = prep_path.with_suffix(".sha256")

        if not prep_path.is_file() or not sidecar_path.is_file():
            raise RuntimeError(
                "Existing calibration run lacks immutable preparation."
            )

        prep_hash = sha256(prep_path)

        if sidecar_path.read_text(encoding="ascii") != (
            f"{prep_hash}  {prep_path.name}" + chr(10)
        ):
            raise RuntimeError(
                "Calibration preparation SHA sidecar mismatch."
            )

        prep = json.loads(
            prep_path.read_text(encoding="utf-8-sig")
        )

        if (
            prep["record_status"] != "FINAL"
            or prep["overall_disposition"]
            != "PRODUCTION_DOE_NEXT_CALIBRATION_SOLVER_PREPARATION_PASS"
            or prep["case"]["case_id"] != case_id
            or prep["case"]["case_hash"] != case_hash
            or prep["next_trial"]["run_id"] != run_id
            or type(prep["next_trial"]["trial_index"]) is not int
            or prep["next_trial"]["trial_index"] != index
        ):
            raise RuntimeError(
                "Calibration preparation identity or status mismatch."
            )

        deck = run_dir / f"{run_id}.inp"

        if (
            prep["deck"]["relative_path"]
            != deck.relative_to(root).as_posix()
            or deck.stat().st_size != prep["deck"]["size_bytes"]
            or sha256(deck) != prep["deck"]["sha256"]
        ):
            raise RuntimeError("Calibration preparation deck drift.")

        manifest_path = run_dir / "fem_run_manifest.json"

        if not manifest_path.exists():
            return TrialHistoryState(
                case_id,
                tuple(completed),
                index,
                "PREPARED_TRIAL_NOT_COMPLETED",
            )

        verify_completed_trial(
            repo_root=root,
            manifest_path=manifest_path,
            expected_run_id=run_id,
            expected_case_hash=case_hash,
            expected_deck_sha256=prep["deck"]["sha256"],
        )

        completed.append(run_id)

    return TrialHistoryState(
        case_id,
        tuple(completed),
        None,
        "TRIAL_LIMIT_REACHED_REQUIRES_CALIBRATION_DECISION",
    )
