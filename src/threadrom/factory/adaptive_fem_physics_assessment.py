from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping

from threadrom.factory.fem_physics_acceptance import (
    evaluate_fem_physics_acceptance,
)


import hashlib
import json
import math
from pathlib import Path

from threadrom.factory.production_doe_completed_trial import (
    verify_completed_trial,
)
from threadrom.factory.fem_result_extraction import (
    extract_fem_physics_result_evidence,
)

class AssessmentDisposition(str, Enum):
    CHECKS_PASSED_PENDING_CERTIFICATION = (
        "checks_passed_pending_certification"
    )
    ENGINEERING_REVIEW_REQUIRED = (
        "engineering_review_required"
    )


@dataclass(frozen=True, slots=True)
class AdaptiveFEMPhysicsAssessment:
    disposition: AssessmentDisposition
    policy_id: str
    failed_governed_checks: tuple[str, ...]
    acceptance_result: object

    @property
    def full_physics_certified(self) -> bool:
        # Evaluation is not an independently issued certificate.
        return False


def assess_extracted_fem_physics(
    *,
    policy,
    preload_decision,
    evidence,
    external_equilibrium_payload: Mapping[str, object] | None,
    require_external_support_equilibrium: bool = True,
) -> AdaptiveFEMPhysicsAssessment:
    """Evaluate existing ThreadROM physics gates without certifying a run.

    The caller must first verify the completed solver manifest, input
    identity, source artifact hashes and calibration lineage.
    This function neither adapts model parameters nor executes FEM.
    """

    if require_external_support_equilibrium:
        if (
            getattr(
                policy,
                "require_external_support_equilibrium",
                None,
            ) is not True
        ):
            raise RuntimeError(
                "BLOCKED_PHYSICS_POLICY: external-support "
                "equilibrium gate was disabled."
            )

        # The governed evaluator records absent/failed equilibrium as
        # a failed HARD_GATE. Continue assessing the other physics gates
        # to provide an actionable report; never manufacture PASS.

    if (
        getattr(evidence, "return_code", None) != 0
        or not getattr(evidence, "accepted_increments", ())
    ):
        raise RuntimeError(
            "BLOCKED_SOLVER_EVIDENCE: successful solver completion "
            "and accepted increments are required."
        )

    result = evaluate_fem_physics_acceptance(
        policy=policy,
        preload_decision=preload_decision,
        thread_normal_force_n=evidence.thread_normal_force_n,
        axial_state=evidence.axial_state,
        deformation_state=evidence.deformation_state,
        thread_flank_state=evidence.thread_flank_state,
        accepted_increments=evidence.accepted_increments,
        external_equilibrium_payload=external_equilibrium_payload,
        return_code=evidence.return_code,
        stdout=evidence.stdout,
        require_process_return_code=True,
    )

    failed = tuple(
        check.name for check in result.failed_checks
    )
    # Defense in depth: even a future evaluator regression must not
    # promote absent/failed complete equilibrium to provisional PASS.
    if require_external_support_equilibrium and (
        external_equilibrium_payload is None
        or external_equilibrium_payload.get("overall_status") != "pass"
    ):
        if "external support equilibrium" not in failed:
            failed += ("external support equilibrium",)

    return AdaptiveFEMPhysicsAssessment(
        disposition=(
            AssessmentDisposition.CHECKS_PASSED_PENDING_CERTIFICATION
            if result.passed and not failed
            else AssessmentDisposition.ENGINEERING_REVIEW_REQUIRED
        ),
        policy_id=result.policy_id,
        failed_governed_checks=failed,
        acceptance_result=result,
    )

def assess_verified_completed_fem(
    *,
    repo_root: Path,
    manifest_path: Path,
    expected_run_id: str,
    expected_case_hash: str,
    expected_deck_sha256: str,
    frd_path: Path,
    sta_path: Path,
    stdout_path: Path,
    mesh_data,
    extraction_policy,
    contact_pairs,
    thermal_expansion_coefficient_per_c: float,
    equivalent_delta_temperature_c: float,
    physics_policy,
    preload_decision,
    external_equilibrium_payload: Mapping[str, object] | None,
) -> AdaptiveFEMPhysicsAssessment:
    """Assess a completed, hash-verified run using existing FEM checks.

    This is preliminary physics assessment, NOT certification.
    The model adapter supplies independently governed model definitions
    and complete-system equilibrium evidence. Missing evidence fails
    closed; no solver is launched and no output is retired.
    """

    root = repo_root.resolve()
    manifest = manifest_path.resolve()
    run_dir = manifest.parent

    if (
        not expected_run_id.strip()
        or not all(
            math.isfinite(float(value))
            for value in (
                thermal_expansion_coefficient_per_c,
                equivalent_delta_temperature_c,
            )
        )
    ):
        raise RuntimeError(
            "BLOCKED_PHYSICS_INPUT: invalid run or thermal definition."
        )

    # This existing verifier checks successful completion, canonical
    # run/case/deck identity, and actual DAT/INP artifact hashes.
    completed = verify_completed_trial(
        repo_root=root,
        manifest_path=manifest,
        expected_run_id=expected_run_id,
        expected_case_hash=expected_case_hash,
        expected_deck_sha256=expected_deck_sha256,
    )

    dat_path = run_dir / f"{expected_run_id}.dat"

    if completed.dat_path.resolve() != dat_path.resolve():
        raise RuntimeError(
            "BLOCKED_PHYSICS_INPUT: verified DAT identity drift."
        )

    record = json.loads(
        manifest.read_text(encoding="utf-8")
    )
    artifacts = record["artifacts"]

    if not isinstance(artifacts, list):
        raise RuntimeError(
            "BLOCKED_PHYSICS_INPUT: invalid manifest artifacts."
        )

    # Check the remaining files actually consumed by semantic
    # extraction against the immutable solver manifest.
    for role, path in (
        ("frd", frd_path),
        ("sta", sta_path),
        ("stdout", stdout_path),
    ):
        actual_path = path.resolve()

        if (
            actual_path.parent != run_dir
            or not actual_path.is_file()
            or actual_path.stat().st_size == 0
        ):
            raise RuntimeError(
                f"BLOCKED_PHYSICS_INPUT: {role} is missing "
                "or outside the verified run directory."
            )

        relative = actual_path.relative_to(root).as_posix()
        matching = [
            artifact
            for artifact in artifacts
            if artifact.get("role") == role
            and Path(
                artifact.get("relative_path", "")
            ).as_posix() == relative
        ]

        if len(matching) != 1:
            raise RuntimeError(
                f"BLOCKED_PHYSICS_INPUT: {role} is not uniquely "
                "bound to the solver manifest."
            )

        digest = hashlib.sha256()
        with actual_path.open("rb") as stream:
            for chunk in iter(
                lambda: stream.read(1024 * 1024),
                b"",
            ):
                digest.update(chunk)

        if digest.hexdigest() != matching[0]["sha256"]:
            raise RuntimeError(
                f"BLOCKED_PHYSICS_INPUT: {role} hash drift."
            )

    evidence = extract_fem_physics_result_evidence(
        mesh_data=mesh_data,
        policy=extraction_policy,
        frd_path=frd_path,
        sta_path=sta_path,
        dat_path=dat_path,
        stdout_path=stdout_path,
        manifest_path=manifest,
        contact_pairs=contact_pairs,
        thermal_expansion_coefficient_per_c=(
            thermal_expansion_coefficient_per_c
        ),
        equivalent_delta_temperature_c=(
            equivalent_delta_temperature_c
        ),
    )

    return assess_extracted_fem_physics(
        policy=physics_policy,
        preload_decision=preload_decision,
        evidence=evidence,
        external_equilibrium_payload=(
            external_equilibrium_payload
        ),
        require_external_support_equilibrium=True,
    )
