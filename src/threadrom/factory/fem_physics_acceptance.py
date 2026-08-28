"""General governed FEM physics acceptance evaluation."""

from __future__ import annotations

from dataclasses import dataclass

from threadrom.factory.fem_acceptance_policy import (
    FemNonlinearRetryPolicy,
    FemPhysicsAcceptancePolicy,
    FemThreadFlankNormalFamily,
)
from threadrom.factory.fem_reproduction_acceptance import (
    FemAcceptanceCheck,
    FemAcceptanceCheckKind,
    FemAcceptanceDisposition,
    build_axial_state_acceptance_checks,
    build_deformation_acceptance_checks,
    build_preload_acceptance_checks,
    build_thread_contact_acceptance_checks,
)
from threadrom.factory.preload_calibration_controller import (
    PreloadCalibrationDecision,
)
from threadrom.postprocessing.calculix_nonlinear_progress import (
    AcceptedIncrement,
)
from threadrom.postprocessing.calculix_semantic_mechanics import (
    CompleteJointAxialStressState,
    CompleteJointDeformationState,
)
from threadrom.postprocessing.calculix_thread_flank import (
    ThreadFlankStressState,
)


@dataclass(frozen=True, slots=True)
class FemPhysicsAcceptanceResult:
    """Structured result of general FEM physics acceptance."""

    policy_id: str
    checks: tuple[FemAcceptanceCheck, ...]

    def __post_init__(self) -> None:
        if not self.policy_id.strip():
            raise ValueError(
                "Physics acceptance policy_id must not be blank."
            )

        if not self.checks:
            raise ValueError(
                "At least one physics acceptance check is required."
            )

        names = tuple(
            check.name
            for check in self.checks
        )

        if len(set(names)) != len(names):
            raise ValueError(
                "Physics acceptance-check names must be unique."
            )

        if not any(
            check.is_gate
            for check in self.checks
        ):
            raise ValueError(
                "At least one governed physics gate is required."
            )

    @property
    def failed_checks(
        self,
    ) -> tuple[FemAcceptanceCheck, ...]:
        """Return failed governed gates."""

        return tuple(
            check
            for check in self.checks
            if check.is_gate
            and not check.passed
        )

    @property
    def disposition(self) -> FemAcceptanceDisposition:
        """Return overall governed PASS/FAIL disposition."""

        if self.failed_checks:
            return FemAcceptanceDisposition.FAIL

        return FemAcceptanceDisposition.PASS

    @property
    def passed(self) -> bool:
        """Return whether all governed gates passed."""

        return (
            self.disposition
            is FemAcceptanceDisposition.PASS
        )

    @property
    def hard_gate_checks(
        self,
    ) -> tuple[FemAcceptanceCheck, ...]:
        return tuple(
            check
            for check in self.checks
            if check.kind
            is FemAcceptanceCheckKind.HARD_GATE
        )

    @property
    def diagnostic_checks(
        self,
    ) -> tuple[FemAcceptanceCheck, ...]:
        return tuple(
            check
            for check in self.checks
            if check.kind
            is FemAcceptanceCheckKind.DIAGNOSTIC
        )


def build_policy_thread_flank_acceptance_checks(
    *,
    state: ThreadFlankStressState,
    policy: FemPhysicsAcceptancePolicy,
) -> tuple[FemAcceptanceCheck, ...]:
    """Evaluate loaded-flank direction using the governed policy."""

    if (
        policy.intended_thread_flank_normal_family
        is FemThreadFlankNormalFamily.NEGATIVE_Z
    ):
        intended = state.negative_z_flank
        opposite = state.positive_z_flank

    elif (
        policy.intended_thread_flank_normal_family
        is FemThreadFlankNormalFamily.POSITIVE_Z
    ):
        intended = state.positive_z_flank
        opposite = state.negative_z_flank

    else:
        raise AssertionError(
            "Unhandled FEM thread-flank normal family."
        )

    passed = (
        state.dominant_flank_name == intended.name
        and intended.mean_compression_mpa
        > opposite.mean_compression_mpa
    )

    return (
        FemAcceptanceCheck(
            name="intended thread flank carries dominant compression",
            kind=FemAcceptanceCheckKind.HARD_GATE,
            passed=passed,
            measured=state.dominance_ratio,
            expected=f"{intended.name} dominant",
            reason=(
                "The loaded bolt-thread flank derived from the "
                "governed assembly orientation must carry greater "
                "projected compressive solid stress than the "
                "opposite flank family. This is a directionality "
                "check, not CPRESS and not a strength criterion."
            ),
        ),
    )


def build_policy_numerical_completion_acceptance_checks(
    *,
    return_code: int | None,
    stdout: str,
    accepted_increments: tuple[AcceptedIncrement, ...],
    policy: FemPhysicsAcceptancePolicy,
    require_process_return_code: bool = True,
) -> tuple[FemAcceptanceCheck, ...]:
    """Evaluate completion and policy-controlled nonlinear robustness."""

    increments_present = bool(
        accepted_increments
    )

    first_attempt_only = (
        increments_present
        and all(
            increment.attempt == 1
            for increment in accepted_increments
        )
    )

    maximum_attempt = max(
        (
            increment.attempt
            for increment in accepted_increments
        ),
        default=0,
    )

    job_finished = (
        "job finished"
        in stdout.casefold()
    )

    if return_code is not None:
        return_code_kind = FemAcceptanceCheckKind.HARD_GATE
        return_code_passed = return_code == 0
        return_code_expected: object = 0
        return_code_reason = (
            "An observed solver process return code must be zero."
        )
    elif require_process_return_code:
        return_code_kind = FemAcceptanceCheckKind.HARD_GATE
        return_code_passed = False
        return_code_expected = 0
        return_code_reason = (
            "A live governed solver execution must preserve its "
            "process return code, and that code must be zero."
        )
    else:
        return_code_kind = FemAcceptanceCheckKind.DIAGNOSTIC
        return_code_passed = True
        return_code_expected = (
            "not persisted in historical archive"
        )
        return_code_reason = (
            "Missing historical process-return-code evidence is "
            "retained as a provenance diagnostic rather than "
            "fabricated."
        )

    strict_retry = (
        policy.nonlinear_retry_policy
        is FemNonlinearRetryPolicy.REQUIRE_FIRST_ATTEMPT
    )

    retry_kind = (
        FemAcceptanceCheckKind.HARD_GATE
        if strict_retry
        else FemAcceptanceCheckKind.DIAGNOSTIC
    )

    retry_passed = (
        first_attempt_only
        if strict_retry
        else True
    )

    retry_expected = (
        "all accepted increments on ATT1"
        if strict_retry
        else "cutbacks/retries permitted by policy"
    )

    retry_reason = (
        "The selected acceptance policy requires every accepted "
        "increment to converge on its first attempt."
        if strict_retry
        else
        "Nonlinear cutbacks/retries are permitted for this case; "
        "the maximum observed attempt remains diagnostic evidence."
    )

    return (
        FemAcceptanceCheck(
            name="CalculiX return code = 0",
            kind=return_code_kind,
            passed=return_code_passed,
            measured=return_code,
            expected=return_code_expected,
            reason=return_code_reason,
        ),
        FemAcceptanceCheck(
            name="nonlinear increments accepted",
            kind=FemAcceptanceCheckKind.HARD_GATE,
            passed=increments_present,
            measured=len(
                accepted_increments
            ),
            expected="one or more accepted increments",
            reason=(
                "A successful nonlinear solution must contain "
                "accepted increment history."
            ),
        ),
        FemAcceptanceCheck(
            name="nonlinear retry policy",
            kind=retry_kind,
            passed=retry_passed,
            measured=maximum_attempt,
            expected=retry_expected,
            reason=retry_reason,
        ),
        FemAcceptanceCheck(
            name="CalculiX Job finished",
            kind=FemAcceptanceCheckKind.HARD_GATE,
            passed=job_finished,
            measured=job_finished,
            expected=True,
            reason=(
                "CalculiX stdout must contain its normal "
                "'Job finished' completion marker."
            ),
        ),
    )


def evaluate_fem_physics_acceptance(
    *,
    policy: FemPhysicsAcceptancePolicy,
    preload_decision: PreloadCalibrationDecision,
    thread_normal_force_n: float,
    axial_state: CompleteJointAxialStressState,
    deformation_state: CompleteJointDeformationState,
    thread_flank_state: ThreadFlankStressState,
    accepted_increments: tuple[AcceptedIncrement, ...],
    return_code: int | None,
    stdout: str,
    require_process_return_code: bool = True,
) -> FemPhysicsAcceptanceResult:
    """Evaluate one supported FEM case without reproduction parity."""

    checks: tuple[FemAcceptanceCheck, ...] = (
        *build_preload_acceptance_checks(
            preload_decision
        ),
        *(
            build_thread_contact_acceptance_checks(
                thread_normal_force_n=thread_normal_force_n
            )
            if policy.require_native_thread_contact_force
            else ()
        ),
        *build_axial_state_acceptance_checks(
            axial_state
        ),
        *build_deformation_acceptance_checks(
            deformation_state
        ),
        *build_policy_thread_flank_acceptance_checks(
            state=thread_flank_state,
            policy=policy,
        ),
        *build_policy_numerical_completion_acceptance_checks(
            return_code=return_code,
            stdout=stdout,
            accepted_increments=accepted_increments,
            policy=policy,
            require_process_return_code=(
                require_process_return_code
            ),
        ),
    )

    return FemPhysicsAcceptanceResult(
        policy_id=policy.policy_id,
        checks=checks,
    )
