from __future__ import annotations

import hashlib
import re

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from threadrom.factory.production_doe_completed_trial import (
    verify_completed_trial,
)


_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_CASE_RUN_ID_PATTERN = re.compile(r"^trm_fem_[0-9a-f]{12}$")


@dataclass(frozen=True, slots=True)
class GovernedTrialHistoryState:
    """Recovered calibration history from verified durable evidence."""

    case_id: str
    completed_run_ids: tuple[str, ...]
    next_trial_index: int | None
    state: str


@dataclass(frozen=True, slots=True)
class VerifiedPreparedTrialEvidence:
    """Immutable preparation evidence for one adaptive calibration trial."""

    run_id: str
    trial_index: int
    deck_path: Path
    deck_sha256: str


class PreparedTrialVerifier(Protocol):
    """Campaign-specific verifier for one already-prepared adaptive trial."""

    def __call__(
        self,
        *,
        repo_root: Path,
        case_id: str,
        case_hash: str,
        case_run_id: str,
        trial_index: int,
        run_dir: Path,
    ) -> VerifiedPreparedTrialEvidence:
        ...


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as stream:
        for chunk in iter(
            lambda: stream.read(8 * 1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def recover_governed_trial_history(
    *,
    repo_root: Path,
    case_id: str,
    case_hash: str,
    case_run_id: str,
    solver_preparation_root: Path,
    verified_initial_trial,
    maximum_trials: int,
    verify_prepared_trial: PreparedTrialVerifier,
) -> GovernedTrialHistoryState:
    """Recover adaptive calibration history from independently verified inputs.

    Campaign-specific preparation records are verified by
    ``verify_prepared_trial``. Completed solver evidence is then checked by
    the shared completed-trial verifier.

    The caller remains responsible for establishing campaign provenance,
    case eligibility, initial-trial evidence, calibration policy and any
    execution authorization.

    This function never authorizes or launches FEM, accepts physics, reads
    sealed holdouts, or deletes simulation artifacts.
    """

    root = Path(repo_root).resolve(strict=True)

    if (
        not isinstance(case_id, str)
        or not case_id
        or case_id != case_id.strip()
    ):
        raise RuntimeError(
            "Invalid governed case identity."
        )

    if (
        not isinstance(case_hash, str)
        or _SHA256_PATTERN.fullmatch(case_hash) is None
    ):
        raise RuntimeError(
            "Invalid governed case hash."
        )

    if (
        not isinstance(case_run_id, str)
        or _CASE_RUN_ID_PATTERN.fullmatch(case_run_id) is None
    ):
        raise RuntimeError(
            "Invalid governed FEM case-run identity."
        )

    if (
        type(maximum_trials) is not int
        or maximum_trials < 1
    ):
        raise RuntimeError(
            "Invalid governed maximum-trial policy."
        )

    if not callable(verify_prepared_trial):
        raise RuntimeError(
            "Prepared-trial verifier is required."
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

    status = getattr(
        verified_initial_trial,
        "completion_status",
        None,
    )

    if status == "PENDING_COMPLETED_MANIFEST":
        return GovernedTrialHistoryState(
            case_id=case_id,
            completed_run_ids=(),
            next_trial_index=1,
            state="WAIT_FOR_TRIAL_1_COMPLETION",
        )

    if status != "COMPLETED_INPUT_EVIDENCE_VERIFIED":
        raise RuntimeError(
            "Unverified initial-trial predecessor."
        )

    initial_run_id = getattr(
        verified_initial_trial,
        "run_id",
        None,
    )

    if (
        not isinstance(initial_run_id, str)
        or not initial_run_id
        or "/" in initial_run_id
        or "\\" in initial_run_id
        or initial_run_id in {".", ".."}
    ):
        raise RuntimeError(
            "Invalid verified initial-trial run identity."
        )

    case_dir = solver_root / case_run_id

    completed = [
        initial_run_id
    ]

    for index in range(
        2,
        maximum_trials + 1,
    ):
        run_id = (
            f"{case_run_id}_cal_{index:02d}"
        )

        run_dir = (
            case_dir
            / run_id
        )

        if not run_dir.exists():
            later = [
                case_dir
                / f"{case_run_id}_cal_{future_index:02d}"
                for future_index in range(
                    index + 1,
                    maximum_trials + 1,
                )
            ]

            if any(
                item.exists()
                for item in later
            ):
                raise RuntimeError(
                    "Calibration trial-history gap detected."
                )

            return GovernedTrialHistoryState(
                case_id=case_id,
                completed_run_ids=tuple(completed),
                next_trial_index=index,
                state="NEXT_TRIAL_NOT_PREPARED",
            )

        if not run_dir.is_dir():
            raise RuntimeError(
                "Calibration run path is not a directory."
            )

        prepared = verify_prepared_trial(
            repo_root=root,
            case_id=case_id,
            case_hash=case_hash,
            case_run_id=case_run_id,
            trial_index=index,
            run_dir=run_dir,
        )

        if not isinstance(
            prepared,
            VerifiedPreparedTrialEvidence,
        ):
            raise RuntimeError(
                "Prepared-trial verifier returned unsupported evidence."
            )

        expected_deck = (
            run_dir
            / f"{run_id}.inp"
        ).resolve()

        actual_deck = Path(
            prepared.deck_path
        ).resolve()

        try:
            actual_deck.relative_to(root)
        except ValueError as exc:
            raise RuntimeError(
                "Prepared calibration deck is outside the repository."
            ) from exc

        if (
            prepared.run_id != run_id
            or type(prepared.trial_index) is not int
            or prepared.trial_index != index
            or actual_deck != expected_deck
            or _SHA256_PATTERN.fullmatch(
                prepared.deck_sha256
            ) is None
            or not actual_deck.is_file()
            or _sha256(actual_deck)
            != prepared.deck_sha256
        ):
            raise RuntimeError(
                "Prepared calibration trial evidence is inconsistent."
            )

        manifest_path = (
            run_dir
            / "fem_run_manifest.json"
        )

        if not manifest_path.exists():
            return GovernedTrialHistoryState(
                case_id=case_id,
                completed_run_ids=tuple(completed),
                next_trial_index=index,
                state="PREPARED_TRIAL_NOT_COMPLETED",
            )

        verify_completed_trial(
            repo_root=root,
            manifest_path=manifest_path,
            expected_run_id=run_id,
            expected_case_hash=case_hash,
            expected_deck_sha256=(
                prepared.deck_sha256
            ),
        )

        completed.append(
            run_id
        )

    return GovernedTrialHistoryState(
        case_id=case_id,
        completed_run_ids=tuple(completed),
        next_trial_index=None,
        state=(
            "TRIAL_LIMIT_REACHED_"
            "REQUIRES_CALIBRATION_DECISION"
        ),
    )
