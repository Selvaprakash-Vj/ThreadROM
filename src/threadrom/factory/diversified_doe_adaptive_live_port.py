from __future__ import annotations

import json
import re

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from threadrom.factory.adaptive_fem_lifecycle import (
    FEMLifecycleDecision,
    FEMLifecycleSnapshot,
    PhysicsDisposition,
    RunPhase,
)
from threadrom.factory.governed_calibration_history import (
    GovernedCalibrationReplay,
)
from threadrom.factory.governed_trial_history import (
    PreparedTrialVerifier,
    recover_governed_trial_history,
)
from threadrom.factory.production_doe_adaptive_controller import (
    AdaptiveCalibrationAction,
)
from threadrom.factory.windows_process_adjudication import (
    FemProcessStatus,
    adjudicate_live_fem_processes,
)


_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_CASE_RUN_ID_PATTERN = re.compile(r"^trm_fem_[0-9a-f]{12}$")


@dataclass(frozen=True, slots=True)
class DiversifiedGovernedCase:
    """Frozen identity of one diversified design proposal."""

    case_id: str
    case_hash: str
    case_run_id: str
    thread_designation: str
    member_material_id: str


def _require(
    condition: bool,
    message: str,
) -> None:
    if not condition:
        raise RuntimeError(
            "DIVERSIFIED_LIVE_PORT_INVALID: "
            + message
        )


class DiversifiedDOEAdaptiveLivePort:
    """Recovery-only diversified adapter for the universal FEM supervisor.

    This first implementation deliberately has no mutation authority.

    It may:
      * resolve one explicit diversified design proposal,
      * verify its externally supplied canonical identity,
      * recover generic calibration history,
      * adjudicate the currently prepared trial against the Windows
        process table,
      * expose a model-independent FEMLifecycleSnapshot.

    It may NOT:
      * prepare another trial,
      * authorize or launch FEM,
      * assess or certify physics,
      * admit data to a ROM dataset,
      * access sealed holdouts,
      * delete or retire artifacts.

    Those capabilities require separate governed integration.
    """

    def __init__(
        self,
        *,
        repo_root: Path,
        case_id: str,
        expected_case_hash: str,
        expected_case_run_id: str,
        solver_preparation_root: Path,
        verified_initial_trial,
        prepared_trial_verifier: PreparedTrialVerifier,
        calibration_replay: Callable[
            [tuple[str, ...]],
            GovernedCalibrationReplay,
        ],
        corrective_rule_id: str,
        maximum_trials: int,
    ) -> None:

        self.root = Path(
            repo_root
        ).resolve(strict=True)

        _require(
            isinstance(case_id, str)
            and bool(case_id.strip())
            and case_id == case_id.strip(),
            "invalid proposal identity",
        )

        _require(
            isinstance(expected_case_hash, str)
            and _SHA256_PATTERN.fullmatch(
                expected_case_hash
            ) is not None,
            "invalid expected case hash",
        )

        _require(
            isinstance(expected_case_run_id, str)
            and _CASE_RUN_ID_PATTERN.fullmatch(
                expected_case_run_id
            ) is not None,
            "invalid expected case-run identity",
        )

        _require(
            type(maximum_trials) is int
            and maximum_trials >= 1,
            "invalid maximum-trial policy",
        )

        _require(
            callable(calibration_replay),
            "governed calibration replay is required",
        )

        _require(
            isinstance(corrective_rule_id, str)
            and bool(corrective_rule_id.strip())
            and corrective_rule_id
            == corrective_rule_id.strip(),
            "corrective-rule identity is missing",
        )

        solver_root = Path(
            solver_preparation_root
        ).resolve()

        try:
            solver_root.relative_to(
                self.root
            )
        except ValueError as exc:
            raise RuntimeError(
                "DIVERSIFIED_LIVE_PORT_INVALID: "
                "solver-preparation root escapes repository"
            ) from exc

        manifest_path = (
            self.root
            / "docs"
            / "phase3_diversified_doe"
            / "design_proposal.json"
        )

        _require(
            manifest_path.is_file(),
            "diversified design manifest is missing",
        )

        manifest = json.loads(
            manifest_path.read_text(
                encoding="utf-8-sig"
            )
        )

        _require(
            isinstance(manifest, dict),
            "diversified design manifest is invalid",
        )

        # This adapter is recovery-only. A manifest that claims bulk
        # execution/admission authority is outside this implementation's
        # reviewed contract and therefore fails closed.
        _require(
            manifest.get(
                "fem_execution_authorized"
            ) is False,
            "campaign FEM authorization unexpectedly changed",
        )

        _require(
            manifest.get(
                "dataset_admission_authorized"
            ) is False,
            "campaign dataset-admission authority unexpectedly changed",
        )

        rows = manifest.get(
            "cases"
        )

        _require(
            isinstance(rows, list),
            "diversified case inventory is missing",
        )

        matches = [
            row
            for row in rows
            if (
                isinstance(row, dict)
                and row.get(
                    "proposal_id"
                )
                == case_id
            )
        ]

        _require(
            len(matches) == 1,
            "proposal identity is missing or ambiguous",
        )

        row = matches[0]

        _require(
            row.get("case_hash")
            == expected_case_hash,
            "canonical case hash differs from external pin",
        )

        _require(
            row.get(
                "preparation_run_id"
            )
            == expected_case_run_id,
            "preparation run identity differs from external pin",
        )

        _require(
            row.get(
                "fem_execution_authorized"
            ) is False,
            "proposal unexpectedly claims FEM authorization",
        )

        _require(
            row.get(
                "dataset_admission_status"
            )
            == "NOT_EVALUATED",
            "proposal dataset-admission status changed",
        )

        _require(
            row.get(
                "evidence_status"
            )
            == (
                "NEW_EVIDENCE_REQUIRED_"
                "NO_EXECUTION_AUTHORITY"
            ),
            "proposal evidence status changed",
        )

        # This live port handles new evidence, not exact historical
        # evidence reuse.
        _require(
            row.get(
                "historical_case_id"
            ) is None,
            "historical-reuse proposal entered new-evidence live port",
        )

        thread_designation = row.get(
            "thread_designation"
        )

        member_material_id = row.get(
            "member_material_id"
        )

        _require(
            isinstance(
                thread_designation,
                str,
            )
            and bool(
                thread_designation.strip()
            ),
            "thread designation is missing",
        )

        _require(
            isinstance(
                member_material_id,
                str,
            )
            and bool(
                member_material_id.strip()
            ),
            "member-material identity is missing",
        )

        self.case_id = case_id

        self.case = DiversifiedGovernedCase(
            case_id=case_id,
            case_hash=expected_case_hash,
            case_run_id=expected_case_run_id,
            thread_designation=thread_designation,
            member_material_id=member_material_id,
        )

        self.solver_preparation_root = (
            solver_root
        )

        self.verified_initial_trial = (
            verified_initial_trial
        )

        self.prepared_trial_verifier = (
            prepared_trial_verifier
        )

        self.calibration_replay = (
            calibration_replay
        )

        self.corrective_rule_id = (
            corrective_rule_id
        )

        self.maximum_trials = (
            maximum_trials
        )

    def _history(self):
        return recover_governed_trial_history(
            repo_root=self.root,
            case_id=self.case_id,
            case_hash=self.case.case_hash,
            case_run_id=self.case.case_run_id,
            solver_preparation_root=(
                self.solver_preparation_root
            ),
            verified_initial_trial=(
                self.verified_initial_trial
            ),
            maximum_trials=(
                self.maximum_trials
            ),
            verify_prepared_trial=(
                self.prepared_trial_verifier
            ),
        )

    def snapshot(
        self,
    ) -> FEMLifecycleSnapshot:
        """Recover current lifecycle state without mutating evidence."""

        history = self._history()

        if (
            history.state
            == "WAIT_FOR_TRIAL_1_COMPLETION"
        ):
            initial_run_id = getattr(
                self.verified_initial_trial,
                "run_id",
                self.case.case_run_id
                + "_cal_01",
            )

            return FEMLifecycleSnapshot(
                run_id=initial_run_id,
                trial_index=1,
                maximum_trials=(
                    self.maximum_trials
                ),
                phase=RunPhase.UNCERTAIN,
            )

        if (
            history.state
            == "PREPARED_TRIAL_NOT_COMPLETED"
        ):
            trial_index = (
                history.next_trial_index
            )

            _require(
                type(trial_index) is int
                and 2
                <= trial_index
                <= self.maximum_trials,
                "invalid prepared adaptive-trial index",
            )

            run_id = (
                f"{self.case.case_run_id}"
                f"_cal_{trial_index:02d}"
            )

            replay = self.calibration_replay(
                history.completed_run_ids
            )

            _require(
                isinstance(
                    replay,
                    GovernedCalibrationReplay,
                )
                and replay.case_id
                == self.case_id
                and replay.completed_trial_count
                == len(
                    history.completed_run_ids
                )
                and replay.last_completed_run_id
                == history.completed_run_ids[-1],
                "calibration replay lineage mismatch",
            )

            expected_next = (
                replay.next_trial
            )

            _require(
                replay.action
                is AdaptiveCalibrationAction
                .NEXT_TRIAL_REQUIRES_AUTHORIZATION
                and expected_next is not None
                and expected_next.run_id
                == run_id
                and expected_next.trial_index
                == trial_index,
                "prepared trial differs from governed calibration replay",
            )

            process = (
                adjudicate_live_fem_processes(
                    run_id=run_id,
                    case_id=self.case_id,
                )
            )

            if (
                process.status
                is FemProcessStatus.LIVE_MATCH
            ):
                return FEMLifecycleSnapshot(
                    run_id=run_id,
                    trial_index=trial_index,
                    maximum_trials=(
                        self.maximum_trials
                    ),
                    phase=RunPhase.RUNNING,
                )

            # There is not yet a durable generalized launch claim
            # separating PREPARED_NEVER_LAUNCHED from a disappeared
            # executor. Therefore both NO_MATCH and UNKNOWN fail closed.
            return FEMLifecycleSnapshot(
                run_id=run_id,
                trial_index=trial_index,
                maximum_trials=(
                    self.maximum_trials
                ),
                phase=RunPhase.UNCERTAIN,
            )

        if history.completed_run_ids:
            replay = self.calibration_replay(
                history.completed_run_ids
            )

            run_id = (
                history.completed_run_ids[
                    -1
                ]
            )

            trial_index = len(
                history.completed_run_ids
            )

            _require(
                isinstance(
                    replay,
                    GovernedCalibrationReplay,
                )
                and replay.case_id
                == self.case_id
                and replay.completed_trial_count
                == trial_index
                and replay.last_completed_run_id
                == run_id,
                "completed calibration replay lineage mismatch",
            )

            if (
                replay.action
                is AdaptiveCalibrationAction
                .CALIBRATION_ACCEPTED_PENDING_FULL_PHYSICS
            ):
                _require(
                    replay.next_trial is None,
                    "accepted calibration contains a next trial",
                )

                return FEMLifecycleSnapshot(
                    run_id=run_id,
                    trial_index=trial_index,
                    maximum_trials=(
                        self.maximum_trials
                    ),
                    phase=RunPhase.COMPLETED,
                    completed_evidence_verified=True,
                    physics=(
                        PhysicsDisposition
                        .NOT_ASSESSED
                    ),
                )

            if (
                replay.action
                is AdaptiveCalibrationAction
                .NEXT_TRIAL_REQUIRES_AUTHORIZATION
            ):
                next_trial = (
                    replay.next_trial
                )

                _require(
                    next_trial is not None,
                    "adaptive replay lacks next trial",
                )

                if (
                    trial_index
                    < self.maximum_trials
                ):
                    _require(
                        history.next_trial_index
                        == next_trial.trial_index
                        and next_trial.run_id
                        == (
                            f"{self.case.case_run_id}"
                            f"_cal_{next_trial.trial_index:02d}"
                        ),
                        "next-trial history differs from calibration replay",
                    )

                return FEMLifecycleSnapshot(
                    run_id=run_id,
                    trial_index=trial_index,
                    maximum_trials=(
                        self.maximum_trials
                    ),
                    phase=RunPhase.COMPLETED,
                    completed_evidence_verified=True,
                    physics=(
                        PhysicsDisposition.ADAPT
                    ),
                    corrective_rule_id=(
                        self.corrective_rule_id
                    ),
                )

            raise RuntimeError(
                "DIVERSIFIED_LIVE_PORT_INVALID: "
                "unsupported calibration replay action"
            )

        raise RuntimeError(
            "DIVERSIFIED_LIVE_PORT_INVALID: "
            f"unsupported recovered history state {history.state}"
        )

    def prepare(
        self,
        snapshot: FEMLifecycleSnapshot,
    ) -> None:
        raise RuntimeError(
            "DIVERSIFIED_MUTATION_NOT_WIRED: "
            "initial preparation is not authorized by this live port"
        )

    def prepare_adaptation(
        self,
        snapshot: FEMLifecycleSnapshot,
        decision: FEMLifecycleDecision,
    ) -> None:
        raise RuntimeError(
            "DIVERSIFIED_MUTATION_NOT_WIRED: "
            "adaptive preparation requires separate governance"
        )

    def launch_authorized(
        self,
        snapshot: FEMLifecycleSnapshot,
    ) -> bool:
        raise RuntimeError(
            "DIVERSIFIED_MUTATION_NOT_WIRED: "
            "solver launch requires independent authorization integration"
        )

    def assess_verified_physics(
        self,
        snapshot: FEMLifecycleSnapshot,
    ) -> None:
        raise RuntimeError(
            "DIVERSIFIED_MUTATION_NOT_WIRED: "
            "full-physics assessment is not yet integrated"
        )

    def verify_full_physics_certificate(
        self,
        snapshot: FEMLifecycleSnapshot,
    ) -> bool:
        raise RuntimeError(
            "DIVERSIFIED_MUTATION_NOT_WIRED: "
            "full-physics certification is not yet integrated"
        )
