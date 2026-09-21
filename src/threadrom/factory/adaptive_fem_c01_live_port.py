from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from threadrom.factory.adaptive_fem_c01_adapter import (
    C01_CORRECTIVE_RULE,
    decide_c01_lifecycle,
)
from threadrom.factory.adaptive_fem_lifecycle import (
    FEMLifecycleSnapshot,
    LifecycleAction,
    PhysicsDisposition,
    RunPhase,
)
from threadrom.factory.production_doe_adaptive_history_planner import (
    plan_from_verified_history,
)
from threadrom.factory.production_doe_case_registry import (
    resolve_governed_c01_case,
)
from threadrom.factory.production_doe_gate0_evidence import (
    inspect_gate0_trial1,
)

from threadrom.factory.production_doe_launch_fence import (
    MAXIMUM_CONCURRENT_CCX,
    count_running_ccx,
)
from threadrom.factory.preload_calibration_campaign import (
    PreloadCalibrationCampaignPolicy,
)


class C01PredecessorPending(RuntimeError):
    """The original governed Trial 1 has no verified completion yet."""


class C01LiveFactoryPort:
    """Evidence-backed C01 adapter for the universal FEM supervisor.

    No state is inferred from a previously cached supervisor decision.
    This adapter cannot issue campaign authorization or accept physics.
    """

    def __init__(self, *, repo_root: Path, case_id: str):
        self.root = repo_root.resolve()
        self.case_id = case_id
        self.campaign_root = (
            self.root
            / "simulations/staging/phase3_cp8_production_doe"
            / "TRM-PDOE-C01"
        )
        self.case = resolve_governed_c01_case(
            repo_root=self.root,
            requested_case_id=case_id,
        )
        self.maximum_trials = (
            PreloadCalibrationCampaignPolicy().maximum_trials
        )

    def snapshot(self) -> FEMLifecycleSnapshot:
        gate0 = inspect_gate0_trial1(
            repo_root=self.root,
            requested_case_id=self.case_id,
        )

        if (
            gate0.completion_status
            == "PENDING_COMPLETED_MANIFEST"
        ):
            raise C01PredecessorPending(
                f"{self.case_id}: WAIT_FOR_VERIFIED_TRIAL_1. "
                "Do not relaunch or replace the original solve."
            )

        if (
            gate0.completion_status
            != "COMPLETED_INPUT_EVIDENCE_VERIFIED"
        ):
            raise RuntimeError(
                f"{self.case_id}: Gate-0 evidence requires review: "
                f"{gate0.completion_status}"
            )

        plan = plan_from_verified_history(
            repo_root=self.root,
            case_id=self.case_id,
        )
        decision = decide_c01_lifecycle(
            history_plan=plan,
            case_run_id=self.case.case_run_id,
            campaign_root=self.campaign_root,
            maximum_trials=self.maximum_trials,
        )

        if (
            decision.action
            is LifecycleAction.PREPARE_GOVERNED_ADAPTATION
        ):
            return FEMLifecycleSnapshot(
                run_id=plan.last_completed_run_id,
                trial_index=plan.completed_trial_count,
                maximum_trials=self.maximum_trials,
                phase=RunPhase.COMPLETED,
                completed_evidence_verified=True,
                physics=PhysicsDisposition.ADAPT,
                corrective_rule_id=C01_CORRECTIVE_RULE,
            )

        if (
            decision.action
            is LifecycleAction.REQUEST_GOVERNED_LAUNCH
        ):
            return FEMLifecycleSnapshot(
                run_id=plan.next_trial_run_id,
                trial_index=plan.completed_trial_count + 1,
                maximum_trials=self.maximum_trials,
                phase=RunPhase.PREPARED,
            )

        if (
            decision.action
            is LifecycleAction.ASSESS_VERIFIED_PHYSICS
        ):
            # C01 preload acceptance does not establish acceptance
            # of equilibrium, contact, stress or other full physics.
            return FEMLifecycleSnapshot(
                run_id=plan.last_completed_run_id,
                trial_index=plan.completed_trial_count,
                maximum_trials=self.maximum_trials,
                phase=RunPhase.COMPLETED,
                completed_evidence_verified=True,
                physics=PhysicsDisposition.NOT_ASSESSED,
            )

        if (
            decision.action
            is LifecycleAction.ENGINEERING_REVIEW
        ):
            return FEMLifecycleSnapshot(
                run_id=(
                    plan.next_trial_run_id
                    or plan.last_completed_run_id
                ),
                trial_index=(
                    plan.completed_trial_count + 1
                    if plan.next_trial_run_id is not None
                    else plan.completed_trial_count
                ),
                maximum_trials=self.maximum_trials,
                phase=RunPhase.UNCERTAIN,
            )

        raise RuntimeError(
            f"{self.case_id}: unsupported recovered lifecycle "
            f"action {decision.action.value}; no execution permitted."
        )

    def prepare(self, snapshot: FEMLifecycleSnapshot) -> None:
        raise RuntimeError(
            "Trial-1 preparation belongs to the separately "
            "governed initial campaign, not adaptive continuation."
        )

    def prepare_adaptation(self, snapshot, decision) -> None:
        if (
            self.snapshot() != snapshot
            or decision.action
            is not LifecycleAction.PREPARE_GOVERNED_ADAPTATION
            or decision.next_trial_index
            != snapshot.trial_index + 1
            or decision.corrective_rule_id
            != C01_CORRECTIVE_RULE
        ):
            raise RuntimeError(
                "C01 adaptation state changed before preparation."
            )

        script = (
            self.root
            / "scripts/prepare_phase3_production_doe_next_calibration_trial.py"
        )
        subprocess.run(
            [
                sys.executable,
                str(script),
                "--case-id",
                self.case_id,
            ],
            cwd=self.root,
            check=True,
        )

        after = self.snapshot()
        if (
            after.phase is not RunPhase.PREPARED
            or after.trial_index
            != decision.next_trial_index
        ):
            raise RuntimeError(
                "Preparation did not produce the verified next trial."
            )

    def launch_authorized(
        self,
        snapshot: FEMLifecycleSnapshot,
    ) -> bool:
        if (
            snapshot.phase is not RunPhase.PREPARED
            or self.snapshot() != snapshot
        ):
            raise RuntimeError(
                "C01 launch snapshot changed; refusing execution."
            )

        # Queue saturation is a deferral, not a failed or
        # restartable FEM run. No launch claim is created here.
        # The shared fence MUST check live capacity again after
        # independently verifying campaign authorization.
        if count_running_ccx() >= MAXIMUM_CONCURRENT_CCX:
            return False

        # This is the SAME coordinator that verifies the independently
        # pinned campaign authorization, replays completed history,
        # checks immutable inputs and reserves the shared solver slot.
        script = (
            self.root
            / "scripts/run_phase3_production_doe_adaptive_factory.py"
        )
        result = subprocess.run(
            [
                sys.executable,
                str(script),
                "--case-id",
                self.case_id,
                "--execute",
            ],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
        )

        output = result.stdout + result.stderr

        if (
            result.returncode != 0
            and "BLOCKED_UNAUTHORIZED" in output
        ):
            return False

        if result.returncode != 0:
            raise RuntimeError(
                "C01 governed launcher stopped; inspect its "
                "original output before any retry."
                + chr(10)
                + output[-6000:]
            )

        if "GOVERNED TRIAL COMPLETED:" not in output:
            raise RuntimeError(
                "Launcher returned success without confirming "
                "governed trial completion."
            )

        # Do not trust the subprocess exit code alone. The supervisor
        # will recover and verify the new completed trial on its
        # next snapshot before considering another action.
        return True

    def assess_verified_physics(self, snapshot) -> None:
        raise RuntimeError(
            "FULL_PHYSICS_ASSESSMENT_NOT_YET_CERTIFIED: "
            "preload acceptance alone cannot close the FEM run."
        )

    def verify_full_physics_certificate(self, snapshot) -> bool:
        # Will be implemented only with an independent, verifiable
        # full-physics acceptance certificate.
        return False
