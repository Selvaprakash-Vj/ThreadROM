"""Governed CalculiX execution adapter for diversified factory workers.

This module is the narrow seam between:
- an already-owned FemFactoryClaim,
- an explicitly governed CalculiX execution specification,
- the generic solver orchestrator, and
- WorkerExecutionResult consumed by the lease-fenced factory worker.

It creates no admission authority and performs no retry/recovery decision.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from threadrom.factory.diversified_factory_worker import (
    WorkerExecutionResult,
)
from threadrom.factory.fem_factory_registry import (
    FemFactoryClaim,
)
from threadrom.factory.fem_run_manifest import (
    FemRunDisposition,
)
from threadrom.factory.fem_solver_orchestrator import (
    orchestrate_calculix_run,
)
from threadrom.solver.calculix_job import (
    CalculixJobDefinition,
)


@dataclass(frozen=True, slots=True)
class GovernedCalculixExecutionSpec:
    """Pinned solver inputs for one already-prepared governed trial."""

    project_root: Path
    input_path: Path
    definition: CalculixJobDefinition
    backend_policy_id: str
    solver_name: str
    solver_version: str
    manifest_path: Path | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("backend_policy_id", self.backend_policy_id),
            ("solver_name", self.solver_name),
            ("solver_version", self.solver_version),
        ):
            if not value.strip():
                raise ValueError(
                    f"{name} must not be blank."
                )


def _resolved(path: Path) -> Path:
    return path.resolve()


def execute_claimed_calculix_run(
    claim: FemFactoryClaim,
    *,
    spec: GovernedCalculixExecutionSpec,
) -> WorkerExecutionResult:
    """Run one claimed trial through the generic governed orchestrator.

    The factory claim supplies durable run/case identity.
    The execution spec supplies solver/backend configuration.

    No identity is inferred from preparation filenames or mutable registry
    metadata. Any disagreement between claim, spec and resulting manifest
    fails closed.
    """

    if claim.run_id != spec.definition.job_name:
        raise RuntimeError(
            "Claimed run identity differs from governed "
            "CalculiX job definition."
        )

    project_root = _resolved(
        spec.project_root
    )

    input_path = _resolved(
        spec.input_path
    )

    try:
        input_path.relative_to(
            project_root
        )
    except ValueError as exc:
        raise RuntimeError(
            "Governed CalculiX input is outside "
            "the project root."
        ) from exc

    if (
        not input_path.is_file()
        or input_path.stat().st_size <= 0
    ):
        raise RuntimeError(
            "Governed CalculiX input deck is "
            "missing or empty."
        )

    requested_manifest = (
        _resolved(spec.manifest_path)
        if spec.manifest_path is not None
        else None
    )

    if requested_manifest is not None:
        try:
            requested_manifest.relative_to(
                project_root
            )
        except ValueError as exc:
            raise RuntimeError(
                "Governed manifest path is outside "
                "the project root."
            ) from exc

    orchestrated = orchestrate_calculix_run(
        project_root=project_root,
        input_path=input_path,
        definition=spec.definition,
        run_id=claim.run_id,
        case_hash=claim.case_hash,
        backend_policy_id=(
            spec.backend_policy_id
        ),
        solver_name=spec.solver_name,
        solver_version=spec.solver_version,
        manifest_path=requested_manifest,
    )

    manifest = orchestrated.manifest
    actual_manifest_path = _resolved(
        orchestrated.manifest_path
    )

    try:
        actual_manifest_path.relative_to(
            project_root
        )
    except ValueError as exc:
        raise RuntimeError(
            "Orchestrator returned a manifest "
            "outside the project root."
        ) from exc

    if (
        requested_manifest is not None
        and actual_manifest_path
        != requested_manifest
    ):
        raise RuntimeError(
            "Orchestrator returned an unexpected "
            "manifest path."
        )

    expected_identity = {
        "run_id": claim.run_id,
        "job_name": claim.run_id,
        "case_hash": claim.case_hash,
        "backend_policy_id": (
            spec.backend_policy_id
        ),
        "solver_name": spec.solver_name,
        "solver_version": spec.solver_version,
    }

    actual_identity = {
        "run_id": manifest.run_id,
        "job_name": manifest.job_name,
        "case_hash": manifest.case_hash,
        "backend_policy_id": (
            manifest.backend_policy_id
        ),
        "solver_name": manifest.solver_name,
        "solver_version": (
            manifest.solver_version
        ),
    }

    if actual_identity != expected_identity:
        raise RuntimeError(
            "Governed solver manifest identity "
            "differs from the claimed execution."
        )

    if (
        manifest.disposition
        is FemRunDisposition.SUCCEEDED
    ):
        if (
            manifest.failure_category
            is not None
            or manifest.failure_message
            is not None
        ):
            raise RuntimeError(
                "Successful governed manifest "
                "carries failure classification."
            )

        return WorkerExecutionResult(
            succeeded=True,
            manifest_path=(
                actual_manifest_path
            ),
        )

    if (
        manifest.disposition
        is not FemRunDisposition.FAILED
    ):
        raise RuntimeError(
            "Unsupported governed solver "
            "manifest disposition."
        )

    if (
        manifest.failure_category
        is None
        or not manifest.failure_message
    ):
        raise RuntimeError(
            "Failed governed solver manifest "
            "lacks failure classification."
        )

    return WorkerExecutionResult(
        succeeded=False,
        manifest_path=(
            actual_manifest_path
        ),
        failure_category=(
            manifest.failure_category.value
        ),
        failure_message=(
            manifest.failure_message
        ),
    )


def make_claimed_calculix_executor(
    spec: GovernedCalculixExecutionSpec,
) -> Callable[
    [FemFactoryClaim],
    WorkerExecutionResult,
]:
    """Create the callback consumed by execute_claimed_factory_job."""

    def execute(
        claim: FemFactoryClaim,
    ) -> WorkerExecutionResult:
        return execute_claimed_calculix_run(
            claim,
            spec=spec,
        )

    return execute
