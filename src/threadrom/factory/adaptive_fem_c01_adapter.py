from __future__ import annotations

from pathlib import Path

from threadrom.factory.adaptive_fem_lifecycle import (
    FEMLifecycleDecision,
    FEMLifecycleSnapshot,
    LifecycleAction,
    PhysicsDisposition,
    RunPhase,
    decide_fem_lifecycle,
)


C01_CORRECTIVE_RULE = "c01_governed_preload_delta_t_calibration"


def decide_c01_lifecycle(
    *,
    history_plan,
    case_run_id: str,
    campaign_root: Path,
    maximum_trials: int,
) -> FEMLifecycleDecision:
    """Translate verified C01 history into universal lifecycle decisions.

    This adapter cannot authorize a solve, certify full physics or
    delete solver artifacts.
    """

    if (
        not case_run_id.startswith("trm_fem_")
        or type(maximum_trials) is not int
        or not 2 <= maximum_trials <= 6
    ):
        raise RuntimeError("Invalid governed C01 lifecycle bounds.")

    completed_count = history_plan.completed_trial_count

    if (
        type(completed_count) is not int
        or not 1 <= completed_count <= maximum_trials
        or not history_plan.last_completed_run_id
    ):
        raise RuntimeError(
            "C01 lifecycle requires verified completed predecessor."
        )

    state = history_plan.state

    if state == "CALIBRATION_ACCEPTED_PENDING_FULL_PHYSICS":
        if history_plan.next_trial_run_id is not None:
            raise RuntimeError(
                "Accepted calibration unexpectedly requests another trial."
            )

        # Preload acceptance is NOT full-physics acceptance.
        return decide_fem_lifecycle(
            FEMLifecycleSnapshot(
                run_id=history_plan.last_completed_run_id,
                trial_index=completed_count,
                maximum_trials=maximum_trials,
                phase=RunPhase.COMPLETED,
                completed_evidence_verified=True,
                physics=PhysicsDisposition.NOT_ASSESSED,
                full_physics_acceptance_verified=False,
            )
        )

    next_index = completed_count + 1
    next_run_id = f"{case_run_id}_cal_{next_index:02d}"

    if (
        history_plan.next_trial_run_id != next_run_id
        or history_plan.next_delta_temperature_c is None
    ):
        raise RuntimeError(
            "C01 next-trial identity or temperature is missing."
        )

    if state == "NEXT_TRIAL_NOT_PREPARED":
        return decide_fem_lifecycle(
            FEMLifecycleSnapshot(
                run_id=history_plan.last_completed_run_id,
                trial_index=completed_count,
                maximum_trials=maximum_trials,
                phase=RunPhase.COMPLETED,
                completed_evidence_verified=True,
                physics=PhysicsDisposition.ADAPT,
                corrective_rule_id=C01_CORRECTIVE_RULE,
            )
        )

    if state != "PREPARED_NEXT_TRIAL_REQUIRES_AUTHORIZATION":
        raise RuntimeError(
            f"Unsupported C01 lifecycle state: {state}"
        )

    run_dir = (
        campaign_root
        / "solver_preparation"
        / case_run_id
        / next_run_id
    )

    if not run_dir.is_dir():
        raise RuntimeError(
            "Verified prepared trial directory is missing."
        )

    # A completed manifest, durable claim or solver output may mean
    # the history changed during preflight. Never call it PREPARED
    # and accidentally request another launch.
    uncertain = any(
        path.exists()
        for path in (
            run_dir / "fem_run_manifest.json",
            run_dir / "adaptive_launch_claim.json",
            *(
                run_dir / f"{next_run_id}.{extension}"
                for extension in (
                    "sta",
                    "dat",
                    "frd",
                    "rout",
                    "cvg",
                    "stdout.log",
                    "stderr.log",
                )
            ),
        )
    )

    return decide_fem_lifecycle(
        FEMLifecycleSnapshot(
            run_id=next_run_id,
            trial_index=next_index,
            maximum_trials=maximum_trials,
            phase=(
                RunPhase.UNCERTAIN
                if uncertain
                else RunPhase.PREPARED
            ),
        )
    )
