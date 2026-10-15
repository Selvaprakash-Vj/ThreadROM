from __future__ import annotations

import hashlib
import math
import re

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence

from threadrom.factory.fem_preload_calibration_measurement import (
    extract_clamp_force_measurement_from_dat,
)
from threadrom.factory.preload_calibration_campaign import (
    PreloadCalibrationTrial,
    evaluate_preload_calibration_trial,
)
from threadrom.factory.production_doe_adaptive_controller import (
    AdaptiveCalibrationAction,
    plan_adaptive_calibration,
)


_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class VerifiedCalibrationTrialEvidence:
    """Verified immutable FEM evidence for one completed calibration trial."""

    trial: PreloadCalibrationTrial
    dat_path: Path
    dat_sha256: str


@dataclass(frozen=True, slots=True)
class GovernedCalibrationReplay:
    """Final governed calibration decision reconstructed from solved history."""

    case_id: str
    completed_trial_count: int
    last_completed_run_id: str
    action: AdaptiveCalibrationAction
    next_trial: PreloadCalibrationTrial | None


class CompletedCalibrationTrialResolver(Protocol):
    """Resolve one completed trial from campaign-specific durable evidence."""

    def __call__(
        self,
        *,
        repo_root: Path,
        case_id: str,
        case_hash: str,
        case_run_id: str,
        run_id: str,
        trial_index: int,
    ) -> VerifiedCalibrationTrialEvidence:
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


def replay_governed_calibration_history(
    *,
    repo_root: Path,
    case_id: str,
    case_hash: str,
    case_run_id: str,
    completed_run_ids: Sequence[str],
    maximum_trials: int,
    target_force_n: float,
    target_relative_tolerance: float,
    spread_relative_tolerance: float,
    contact_pairs,
    resolve_completed_trial: CompletedCalibrationTrialResolver,
) -> GovernedCalibrationReplay:
    """Replay every solved calibration trial from verified immutable evidence.

    The resolver owns campaign-specific evidence verification.

    This function performs only deterministic calibration reconstruction.
    It never prepares or launches FEM, grants execution authority, accepts
    full physics, admits ROM data, accesses holdouts, or deletes artifacts.
    """

    root = Path(
        repo_root
    ).resolve(strict=True)

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
        or _SHA256_PATTERN.fullmatch(
            case_hash
        ) is None
    ):
        raise RuntimeError(
            "Invalid governed case hash."
        )

    if (
        not isinstance(case_run_id, str)
        or not case_run_id.startswith(
            "trm_fem_"
        )
    ):
        raise RuntimeError(
            "Invalid governed case-run identity."
        )

    if (
        type(maximum_trials) is not int
        or maximum_trials < 2
    ):
        raise RuntimeError(
            "Invalid governed calibration-trial limit."
        )

    completed = tuple(
        completed_run_ids
    )

    if (
        not completed
        or len(completed) > maximum_trials
    ):
        raise RuntimeError(
            "Invalid completed calibration history."
        )

    if (
        not isinstance(target_force_n, (int, float))
        or isinstance(target_force_n, bool)
        or not math.isfinite(float(target_force_n))
        or float(target_force_n) <= 0.0
    ):
        raise RuntimeError(
            "Invalid governed target preload."
        )

    for value, name in (
        (
            target_relative_tolerance,
            "target tolerance",
        ),
        (
            spread_relative_tolerance,
            "spread tolerance",
        ),
    ):
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(float(value))
            or not 0.0 < float(value) < 1.0
        ):
            raise RuntimeError(
                f"Invalid governed {name}."
            )

    if not callable(
        resolve_completed_trial
    ):
        raise RuntimeError(
            "Completed-trial resolver is required."
        )

    previous_trial = None
    previous_measurement = None
    expected_current_trial = None

    final_evaluation = None
    final_plan = None

    for trial_index, run_id in enumerate(
        completed,
        start=1,
    ):
        expected_run_id = (
            f"{case_run_id}"
            f"_cal_{trial_index:02d}"
        )

        if run_id != expected_run_id:
            raise RuntimeError(
                "Completed calibration history has "
                "noncanonical run identity."
            )

        evidence = resolve_completed_trial(
            repo_root=root,
            case_id=case_id,
            case_hash=case_hash,
            case_run_id=case_run_id,
            run_id=run_id,
            trial_index=trial_index,
        )

        if not isinstance(
            evidence,
            VerifiedCalibrationTrialEvidence,
        ):
            raise RuntimeError(
                "Completed-trial resolver returned "
                "unsupported evidence."
            )

        trial = evidence.trial

        if (
            trial.run_id != run_id
            or trial.trial_index != trial_index
        ):
            raise RuntimeError(
                "Completed calibration trial identity drift."
            )

        if (
            trial_index > 1
            and expected_current_trial is None
        ):
            raise RuntimeError(
                "Calibration history continued after "
                "a terminal decision."
            )

        if (
            trial_index > 1
            and (
                trial.run_id
                != expected_current_trial.run_id
                or trial.trial_index
                != expected_current_trial.trial_index
                or trial.source
                != expected_current_trial.source
                or not math.isclose(
                    trial.delta_temperature_c,
                    expected_current_trial.delta_temperature_c,
                    rel_tol=0.0,
                    abs_tol=1.0e-10,
                )
            )
        ):
            raise RuntimeError(
                "Completed trial differs from the preceding "
                "governed calibration decision."
            )

        dat_path = Path(
            evidence.dat_path
        ).resolve(strict=True)

        try:
            dat_path.relative_to(
                root
            )
        except ValueError as exc:
            raise RuntimeError(
                "Calibration DAT is outside repository."
            ) from exc

        if (
            not isinstance(
                evidence.dat_sha256,
                str,
            )
            or _SHA256_PATTERN.fullmatch(
                evidence.dat_sha256
            ) is None
            or _sha256(dat_path)
            != evidence.dat_sha256
        ):
            raise RuntimeError(
                "Completed calibration DAT evidence drift."
            )

        extraction = (
            extract_clamp_force_measurement_from_dat(
                dat_path=dat_path,
                contact_pairs=contact_pairs,
            )
        )

        measurement = extraction.measurement

        # Detect replacement during parsing as well.
        if (
            _sha256(dat_path)
            != evidence.dat_sha256
        ):
            raise RuntimeError(
                "Completed calibration DAT changed "
                "during force extraction."
            )

        evaluation = (
            evaluate_preload_calibration_trial(
                case_run_id=case_run_id,
                target_force_n=float(
                    target_force_n
                ),
                target_relative_tolerance=float(
                    target_relative_tolerance
                ),
                spread_relative_tolerance=float(
                    spread_relative_tolerance
                ),
                current_trial=trial,
                measurement=measurement,
                previous_trial=previous_trial,
                previous_measurement=(
                    previous_measurement
                ),
            )
        )

        plan = plan_adaptive_calibration(
            case_run_id=case_run_id,
            evaluation=evaluation,
            maximum_trials=maximum_trials,
        )

        if (
            trial_index
            < len(completed)
            and plan.action
            is not AdaptiveCalibrationAction
            .NEXT_TRIAL_REQUIRES_AUTHORIZATION
        ):
            raise RuntimeError(
                "Completed FEM trial exists after "
                "calibration termination."
            )

        previous_trial = trial
        previous_measurement = measurement
        expected_current_trial = (
            evaluation.next_trial
        )
        final_evaluation = evaluation
        final_plan = plan

    if (
        final_evaluation is None
        or final_plan is None
    ):
        raise RuntimeError(
            "No verified calibration decision."
        )

    next_trial = (
        final_evaluation.next_trial
    )

    if (
        final_plan.action
        is AdaptiveCalibrationAction
        .CALIBRATION_ACCEPTED_PENDING_FULL_PHYSICS
    ):
        if next_trial is not None:
            raise RuntimeError(
                "Accepted calibration unexpectedly "
                "contains a next trial."
            )

    elif (
        final_plan.action
        is AdaptiveCalibrationAction
        .NEXT_TRIAL_REQUIRES_AUTHORIZATION
    ):
        if (
            next_trial is None
            or final_plan.next_run_id
            != next_trial.run_id
        ):
            raise RuntimeError(
                "Adaptive continuation identity mismatch."
            )

    else:
        raise RuntimeError(
            "Unsupported adaptive calibration action."
        )

    return GovernedCalibrationReplay(
        case_id=case_id,
        completed_trial_count=len(
            completed
        ),
        last_completed_run_id=(
            completed[-1]
        ),
        action=final_plan.action,
        next_trial=next_trial,
    )
