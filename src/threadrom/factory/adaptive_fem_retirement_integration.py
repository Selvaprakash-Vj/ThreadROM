"""C01 adapter for the generic, independently authorized .rout retirement core.

The adaptive supervisor's CERTIFIED_COMPLETE is not deletion authorization.
The approved run-bound permit SHA-256 must come from an independent frozen
registry, never from hashing an arbitrary local permit on the fly.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Protocol

from threadrom.factory.adaptive_fem_independent_certificate import (
    recover_c01_independent_certificate,
)
from threadrom.factory.adaptive_fem_lifecycle import (
    LifecycleAction,
    decide_fem_lifecycle,
)
from threadrom.factory.adaptive_fem_physics_records import (
    recover_preliminary_c01_assessment,
)
from threadrom.factory.adaptive_fem_rout_retirement import (
    RetirementOutcome,
    retire_certified_rout,
)


class CertifiedC01Port(Protocol):
    root: Path
    case_id: str
    campaign_root: Path
    case: object

    def snapshot(self): ...


def retire_c01_certified_rout(
    *,
    port: CertifiedC01Port,
    expected_permit_sha256: str | None,
    active_solver_count: Callable[[], int],
    execute: bool = False,
) -> RetirementOutcome:
    """Use saved evidence; never create a permit or trigger a new FEM solve."""
    snapshot = port.snapshot()
    if decide_fem_lifecycle(snapshot).action is not LifecycleAction.CERTIFIED_COMPLETE:
        raise RuntimeError(
            "RETIREMENT_BLOCKED: C01 run is not independently certified."
        )
    case_run_id = port.case.case_run_id
    case_hash = port.case.case_hash
    run_id = snapshot.run_id
    if not run_id.startswith(case_run_id + "_cal_"):
        raise RuntimeError("RETIREMENT_BLOCKED: C01 run identity drift.")
    run_dir = (
        port.campaign_root / "solver_preparation" / case_run_id / run_id
    )
    if not run_dir.is_dir():
        raise RuntimeError("RETIREMENT_BLOCKED: completed run directory missing.")

    # A real verified certificate binds source artifacts and the saved physics
    # result; the closure re-verifies it immediately before retirement.
    preliminary = recover_preliminary_c01_assessment(
        repo_root=port.root,
        case_id=port.case_id,
        case_run_id=case_run_id,
        run_id=run_id,
        trial_index=snapshot.trial_index,
    )
    if preliminary is None:
        raise RuntimeError("RETIREMENT_BLOCKED: preliminary physics missing.")

    def verify_certificate() -> bool:
        if port.snapshot() != snapshot:
            return False
        return recover_c01_independent_certificate(
            repo_root=port.root,
            case_id=port.case_id,
            case_run_id=case_run_id,
            case_hash=case_hash,
            run_id=run_id,
            trial_index=snapshot.trial_index,
            preliminary_result=preliminary,
        )

    return retire_certified_rout(
        root=port.root,
        run_dir=run_dir,
        run_id=run_id,
        manifest_path=run_dir / "fem_run_manifest.json",
        certificate_path=(
            run_dir / "independent_governed_physics_certificate.json"
        ),
        permit_path=run_dir / "independent_rout_retirement_permit.json",
        expected_permit_sha256=expected_permit_sha256,
        verify_independent_certificate=verify_certificate,
        active_solver_count=active_solver_count,
        execute=execute,
    )
