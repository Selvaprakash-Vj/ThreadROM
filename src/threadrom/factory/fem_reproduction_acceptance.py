"""Governed acceptance model for certified FEM reproduction."""

from __future__ import annotations

import math

from dataclasses import dataclass
from enum import Enum
from typing import TypeAlias

from threadrom.factory.preload_calibration_controller import (
    ClampForceMeasurement,
    PreloadCalibrationDecision,
    PreloadCalibrationDisposition,
)
from threadrom.postprocessing.calculix_semantic_mechanics import (
    CompleteJointAxialStressState,
    CompleteJointDeformationState,
)
from threadrom.postprocessing.calculix_thread_flank import (
    ThreadFlankStressState,
)
from threadrom.postprocessing.calculix_nonlinear_progress import (
    AcceptedIncrement,
)
from threadrom.factory.fem_result_oracle import (
    FemCertifiedResultOracle,
)


AcceptanceValue: TypeAlias = (
    str
    | float
    | int
    | bool
    | None
)


class FemAcceptanceDisposition(str, Enum):
    """Overall governed FEM reproduction disposition."""

    PASS = "pass"
    FAIL = "fail"


class FemAcceptanceCheckKind(str, Enum):
    """Role of one FEM reproduction evidence check."""

    HARD_GATE = "hard_gate"
    REPRODUCTION_PARITY = "reproduction_parity"
    DIAGNOSTIC = "diagnostic"


@dataclass(frozen=True, slots=True)
class FemAcceptanceCheck:
    """One named, auditable FEM reproduction check."""

    name: str
    kind: FemAcceptanceCheckKind
    passed: bool
    measured: AcceptanceValue = None
    expected: AcceptanceValue = None
    tolerance: AcceptanceValue = None
    reason: str = ""

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError(
                "Acceptance-check name must not be empty."
            )

    @property
    def is_gate(self) -> bool:
        """Return whether this check contributes to PASS/FAIL."""

        return self.kind in (
            FemAcceptanceCheckKind.HARD_GATE,
            FemAcceptanceCheckKind.REPRODUCTION_PARITY,
        )


@dataclass(frozen=True, slots=True)
class FemReproductionAcceptanceResult:
    """Structured result of the governed reproduction oracle."""

    checks: tuple[FemAcceptanceCheck, ...]

    def __post_init__(self) -> None:
        if not self.checks:
            raise ValueError(
                "At least one acceptance check is required."
            )

        names = tuple(
            check.name
            for check in self.checks
        )

        if len(set(names)) != len(names):
            raise ValueError(
                "Acceptance-check names must be unique."
            )

        if not any(
            check.is_gate
            for check in self.checks
        ):
            raise ValueError(
                "At least one governed gate is required."
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
    def failed_checks(
        self,
    ) -> tuple[FemAcceptanceCheck, ...]:
        """Return failed hard/parity gates only."""

        return tuple(
            check
            for check in self.checks
            if check.is_gate
            and not check.passed
        )

    @property
    def hard_gate_checks(
        self,
    ) -> tuple[FemAcceptanceCheck, ...]:
        """Return physical/numerical hard gates."""

        return tuple(
            check
            for check in self.checks
            if check.kind
            is FemAcceptanceCheckKind.HARD_GATE
        )

    @property
    def parity_checks(
        self,
    ) -> tuple[FemAcceptanceCheck, ...]:
        """Return Phase-2 reproduction-parity checks."""

        return tuple(
            check
            for check in self.checks
            if check.kind
            is FemAcceptanceCheckKind.REPRODUCTION_PARITY
        )

    @property
    def diagnostic_checks(
        self,
    ) -> tuple[FemAcceptanceCheck, ...]:
        """Return non-gating diagnostic evidence."""

        return tuple(
            check
            for check in self.checks
            if check.kind
            is FemAcceptanceCheckKind.DIAGNOSTIC
        )

def build_preload_acceptance_checks(
    decision: PreloadCalibrationDecision,
) -> tuple[FemAcceptanceCheck, FemAcceptanceCheck]:
    """Convert the governed preload decision into auditable gates."""

    force_passed = (
        abs(decision.target_relative_error)
        <= decision.target_relative_tolerance
    )

    spread_passed = (
        decision.measurement.spread_relative
        <= decision.spread_relative_tolerance
    )

    accepted = (
        decision.disposition
        is PreloadCalibrationDisposition.ACCEPT
    )

    if accepted != (
        force_passed
        and spread_passed
    ):
        raise RuntimeError(
            "Preload decision is inconsistent with "
            "its governed force/spread tolerances."
        )

    target_check = FemAcceptanceCheck(
        name="preload target force",
        kind=FemAcceptanceCheckKind.HARD_GATE,
        passed=force_passed,
        measured=decision.measurement.mean_force_n,
        expected=decision.target_force_n,
        tolerance=decision.target_relative_tolerance,
        reason=(
            "Three-path mean clamp force must remain within "
            "the governed target-relative tolerance."
        ),
    )

    spread_check = FemAcceptanceCheck(
        name="planar clamp-force consistency",
        kind=FemAcceptanceCheckKind.HARD_GATE,
        passed=spread_passed,
        measured=decision.measurement.spread_relative,
        expected=0.0,
        tolerance=decision.spread_relative_tolerance,
        reason=(
            "Under-head, nut-bearing, and member-interface "
            "clamp-force paths must remain mutually consistent."
        ),
    )

    return (
        target_check,
        spread_check,
    )


def build_thread_contact_acceptance_checks(
    *,
    thread_normal_force_n: float,
) -> tuple[FemAcceptanceCheck, ...]:
    """Require a finite positive native thread-contact normal force."""

    passed = (
        math.isfinite(
            thread_normal_force_n
        )
        and thread_normal_force_n > 0.0
    )

    return (
        FemAcceptanceCheck(
            name="native thread contact carries normal force",
            kind=FemAcceptanceCheckKind.HARD_GATE,
            passed=passed,
            measured=thread_normal_force_n,
            expected="finite positive normal-force magnitude",
            reason=(
                "The governed preload validation requires native "
                "thread-contact CFN evidence in addition to the "
                "solid-STRESS thread-flank directionality diagnostic."
            ),
        ),
    )


def build_axial_state_acceptance_checks(
    state: CompleteJointAxialStressState,
) -> tuple[
    FemAcceptanceCheck,
    FemAcceptanceCheck,
    FemAcceptanceCheck,
]:
    """Build the certified physical axial-state hard gates."""

    return (
        FemAcceptanceCheck(
            name="bolt free-span axial state = tension",
            kind=FemAcceptanceCheckKind.HARD_GATE,
            passed=state.bolt.mean_szz_mpa > 0.0,
            measured=state.bolt.mean_szz_mpa,
            expected="positive mean SZZ",
            reason=(
                "The semantically derived bolt free-span region "
                "must carry net axial tension."
            ),
        ),
        FemAcceptanceCheck(
            name="head-side member axial state = compression",
            kind=FemAcceptanceCheckKind.HARD_GATE,
            passed=(
                state.head_side_member.mean_szz_mpa
                < 0.0
            ),
            measured=(
                state.head_side_member.mean_szz_mpa
            ),
            expected="negative mean SZZ",
            reason=(
                "The complete head-side member must carry "
                "net axial compression."
            ),
        ),
        FemAcceptanceCheck(
            name="nut-side member axial state = compression",
            kind=FemAcceptanceCheckKind.HARD_GATE,
            passed=(
                state.nut_side_member.mean_szz_mpa
                < 0.0
            ),
            measured=(
                state.nut_side_member.mean_szz_mpa
            ),
            expected="negative mean SZZ",
            reason=(
                "The complete nut-side member must carry "
                "net axial compression."
            ),
        ),
    )

def build_deformation_acceptance_checks(
    state: CompleteJointDeformationState,
) -> tuple[
    FemAcceptanceCheck,
    FemAcceptanceCheck,
]:
    """Build the certified physical deformation hard gates."""

    return (
        FemAcceptanceCheck(
            name="member stack physically shortens",
            kind=FemAcceptanceCheckKind.HARD_GATE,
            passed=state.member_shortening_mm > 0.0,
            measured=state.member_shortening_mm,
            expected="positive shortening",
            reason=(
                "The clamped-member bearing surfaces must move "
                "toward one another under preload."
            ),
        ),
        FemAcceptanceCheck(
            name="bolt mechanical extension positive",
            kind=FemAcceptanceCheckKind.HARD_GATE,
            passed=(
                state.bolt_mechanical_extension_mm
                > 0.0
            ),
            measured=(
                state.bolt_mechanical_extension_mm
            ),
            expected="positive mechanical extension",
            reason=(
                "After removal of the imposed thermal eigenstrain, "
                "the bolt free span must exhibit positive "
                "mechanical extension."
            ),
        ),
    )

def build_thread_flank_acceptance_checks(
    state: ThreadFlankStressState,
) -> tuple[FemAcceptanceCheck, ...]:
    """Build the certified thread-flank directionality hard gate.

    This gate verifies loading direction only. The exact Phase-2
    compression magnitudes and dominance ratio belong to reproduction
    parity rather than the general physical acceptance criterion.
    """

    intended_name = "-Z-normal flank"

    intended_mean = (
        state.negative_z_flank.mean_compression_mpa
    )

    opposite_mean = (
        state.positive_z_flank.mean_compression_mpa
    )

    passed = (
        state.dominant_flank_name == intended_name
        and intended_mean > opposite_mean
    )

    return (
        FemAcceptanceCheck(
            name="intended thread flank carries dominant compression",
            kind=FemAcceptanceCheckKind.HARD_GATE,
            passed=passed,
            measured=state.dominance_ratio,
            expected=f"{intended_name} dominant",
            reason=(
                "The certified joint orientation requires the "
                "-Z-normal bolt-thread flank family to carry greater "
                "projected compressive solid stress than the "
                "+Z-normal flank family. This is a directionality "
                "diagnostic, not CPRESS and not a strength criterion."
            ),
        ),
    )

def build_numerical_completion_acceptance_checks(
    *,
    return_code: int | None,
    stdout: str,
    accepted_increments: tuple[AcceptedIncrement, ...],
    require_process_return_code: bool = True,
) -> tuple[
    FemAcceptanceCheck,
    FemAcceptanceCheck,
    FemAcceptanceCheck,
    FemAcceptanceCheck,
]:
    """Build general CalculiX completion/convergence checks.

    Live governed runs require an observed zero process return code.
    Historical archives may explicitly declare that this process-level
    datum was not persisted. Missing archived evidence is then retained
    as a diagnostic provenance gap rather than fabricated.

    An observed nonzero return code is always a hard failure.

    Exact Phase-2 increment count and final iteration count are
    reproduction-parity evidence and are intentionally not encoded
    here as universal acceptance thresholds.
    """

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

    job_finished = (
        "job finished"
        in stdout.casefold()
    )

    if return_code is not None:
        return_code_kind = (
            FemAcceptanceCheckKind.HARD_GATE
        )
        return_code_passed = (
            return_code == 0
        )
        return_code_expected: AcceptanceValue = 0
        return_code_reason = (
            "An observed solver process return code must be zero."
        )
    elif require_process_return_code:
        return_code_kind = (
            FemAcceptanceCheckKind.HARD_GATE
        )
        return_code_passed = False
        return_code_expected = 0
        return_code_reason = (
            "A live governed solver execution must preserve its "
            "process return code, and that code must be zero."
        )
    else:
        return_code_kind = (
            FemAcceptanceCheckKind.DIAGNOSTIC
        )
        return_code_passed = True
        return_code_expected = (
            "not persisted in historical archive"
        )
        return_code_reason = (
            "The certified historical archive predates persisted "
            "process-return-code provenance. No value is fabricated; "
            "solver completion is instead evidenced separately by "
            "accepted nonlinear history and the CalculiX "
            "'Job finished' marker."
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
            name="no nonlinear cutbacks or retries",
            kind=FemAcceptanceCheckKind.HARD_GATE,
            passed=first_attempt_only,
            measured=(
                max(
                    (
                        increment.attempt
                        for increment in accepted_increments
                    ),
                    default=0,
                )
            ),
            expected="all accepted increments on ATT1",
            reason=(
                "Every accepted increment must be accepted on "
                "its first attempt; ATT>1 indicates a prior "
                "cutback or retry."
            ),
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

def build_reproduction_parity_checks(
    *,
    oracle: FemCertifiedResultOracle,
    preload_decision: PreloadCalibrationDecision,
    thread_normal_force_n: float,
    analytical_member_shortening_mm: float,
    axial_state: CompleteJointAxialStressState,
    deformation_state: CompleteJointDeformationState,
    thread_flank_state: ThreadFlankStressState,
    accepted_increments: tuple[AcceptedIncrement, ...],
    force_tolerance_n: float = 0.01,
    stress_tolerance_mpa: float = 0.001,
    displacement_tolerance_mm: float = 1.0e-8,
    geometry_tolerance_mm: float = 1.0e-9,
    flank_mean_tolerance_mpa: float = 0.01,
    flank_area_tolerance_percent: float = 0.01,
    dominance_tolerance: float = 0.001,
    ratio_tolerance: float = 1.0e-6,
    time_tolerance: float = 1.0e-12,
) -> tuple[FemAcceptanceCheck, ...]:
    """Build strict CP4 parity checks against the certified A2 result.

    These checks verify reproduction of one immutable Phase-2
    reference. They are not general Phase-3 physical thresholds.
    """

    if (
        not math.isfinite(
            analytical_member_shortening_mm
        )
        or analytical_member_shortening_mm <= 0.0
    ):
        raise ValueError(
            "analytical_member_shortening_mm must be "
            "finite and positive."
        )

    for name, value in (
        (
            "force_tolerance_n",
            force_tolerance_n,
        ),
        (
            "stress_tolerance_mpa",
            stress_tolerance_mpa,
        ),
        (
            "displacement_tolerance_mm",
            displacement_tolerance_mm,
        ),
        (
            "geometry_tolerance_mm",
            geometry_tolerance_mm,
        ),
        (
            "flank_mean_tolerance_mpa",
            flank_mean_tolerance_mpa,
        ),
        (
            "flank_area_tolerance_percent",
            flank_area_tolerance_percent,
        ),
        (
            "dominance_tolerance",
            dominance_tolerance,
        ),
        (
            "ratio_tolerance",
            ratio_tolerance,
        ),
        (
            "time_tolerance",
            time_tolerance,
        ),
    ):
        if value < 0.0:
            raise ValueError(
                f"{name} must be non-negative."
            )

    axial = oracle.axial_stress
    deformation = oracle.deformation
    flank = oracle.thread_flank
    numerical = oracle.numerical

    checks: list[FemAcceptanceCheck] = []

    def numeric_check(
        *,
        name: str,
        measured: float,
        expected: float,
        tolerance: float,
        reason: str,
    ) -> None:
        checks.append(
            FemAcceptanceCheck(
                name=name,
                kind=(
                    FemAcceptanceCheckKind.REPRODUCTION_PARITY
                ),
                passed=(
                    abs(
                        measured
                        - expected
                    )
                    <= tolerance
                ),
                measured=measured,
                expected=expected,
                tolerance=tolerance,
                reason=reason,
            )
        )

    # --------------------------------------------------------
    # Clamp-force parity.
    # --------------------------------------------------------

    clamp = oracle.clamp_force
    measurement = preload_decision.measurement

    numeric_check(
        name="A2 preload target-force parity",
        measured=preload_decision.target_force_n,
        expected=clamp.target_force_n,
        tolerance=force_tolerance_n,
        reason=(
            "The reproduction target preload must match "
            "the certified Phase-2 target."
        ),
    )

    numeric_check(
        name="A2 under-head clamp-force parity",
        measured=measurement.under_head_force_n,
        expected=clamp.under_head_force_n,
        tolerance=force_tolerance_n,
        reason=(
            "The reproduced under-head clamp-force path "
            "must match the certified Phase-2 reference."
        ),
    )

    numeric_check(
        name="A2 nut-bearing clamp-force parity",
        measured=measurement.nut_bearing_force_n,
        expected=clamp.nut_bearing_force_n,
        tolerance=force_tolerance_n,
        reason=(
            "The reproduced nut-bearing clamp-force path "
            "must match the certified Phase-2 reference."
        ),
    )

    numeric_check(
        name="A2 member-interface clamp-force parity",
        measured=measurement.member_interface_force_n,
        expected=clamp.member_interface_force_n,
        tolerance=force_tolerance_n,
        reason=(
            "The reproduced member-interface clamp-force path "
            "must match the certified Phase-2 reference."
        ),
    )

    numeric_check(
        name="A2 thread contact normal-force parity",
        measured=thread_normal_force_n,
        expected=clamp.thread_normal_force_n,
        tolerance=force_tolerance_n,
        reason=(
            "The reproduced native thread-contact normal-force "
            "magnitude must match the certified Phase-2 reference."
        ),
    )

    # --------------------------------------------------------
    # Axial-state parity.
    # --------------------------------------------------------

    numeric_check(
        name="A2 bolt mean SZZ parity",
        measured=axial_state.bolt.mean_szz_mpa,
        expected=axial.bolt_mean_szz_mpa,
        tolerance=stress_tolerance_mpa,
        reason=(
            "Reproduced bolt free-span mean SZZ must match "
            "the certified Phase-2 reference."
        ),
    )

    numeric_check(
        name="A2 bolt median SZZ parity",
        measured=axial_state.bolt.median_szz_mpa,
        expected=axial.bolt_median_szz_mpa,
        tolerance=stress_tolerance_mpa,
        reason=(
            "Reproduced bolt free-span median SZZ must match "
            "the certified Phase-2 reference."
        ),
    )

    numeric_check(
        name="A2 head-member mean SZZ parity",
        measured=(
            axial_state.head_side_member.mean_szz_mpa
        ),
        expected=axial.head_member_mean_szz_mpa,
        tolerance=stress_tolerance_mpa,
        reason=(
            "Reproduced head-side member mean SZZ must match "
            "the certified Phase-2 reference."
        ),
    )

    numeric_check(
        name="A2 nut-member mean SZZ parity",
        measured=(
            axial_state.nut_side_member.mean_szz_mpa
        ),
        expected=axial.nut_member_mean_szz_mpa,
        tolerance=stress_tolerance_mpa,
        reason=(
            "Reproduced nut-side member mean SZZ must match "
            "the certified Phase-2 reference."
        ),
    )

    checks.append(
        FemAcceptanceCheck(
            name="A2 bolt diagnostic element-count parity",
            kind=FemAcceptanceCheckKind.REPRODUCTION_PARITY,
            passed=(
                axial_state.bolt.element_count
                == axial.bolt_selected_tetrahedra
            ),
            measured=axial_state.bolt.element_count,
            expected=axial.bolt_selected_tetrahedra,
            reason=(
                "The semantically derived bolt diagnostic region "
                "must reproduce the certified tetrahedron count."
            ),
        )
    )

    checks.append(
        FemAcceptanceCheck(
            name="A2 head-member element-count parity",
            kind=FemAcceptanceCheckKind.REPRODUCTION_PARITY,
            passed=(
                axial_state.head_side_member.element_count
                == axial.head_member_tetrahedra
            ),
            measured=(
                axial_state.head_side_member.element_count
            ),
            expected=axial.head_member_tetrahedra,
            reason=(
                "The complete head-side member region must "
                "reproduce the certified tetrahedron count."
            ),
        )
    )

    checks.append(
        FemAcceptanceCheck(
            name="A2 nut-member element-count parity",
            kind=FemAcceptanceCheckKind.REPRODUCTION_PARITY,
            passed=(
                axial_state.nut_side_member.element_count
                == axial.nut_member_tetrahedra
            ),
            measured=(
                axial_state.nut_side_member.element_count
            ),
            expected=axial.nut_member_tetrahedra,
            reason=(
                "The complete nut-side member region must "
                "reproduce the certified tetrahedron count."
            ),
        )
    )

    # --------------------------------------------------------
    # Deformation parity.
    # --------------------------------------------------------

    numeric_check(
        name="A2 member-shortening parity",
        measured=deformation_state.member_shortening_mm,
        expected=deformation.member_shortening_mm,
        tolerance=displacement_tolerance_mm,
        reason=(
            "Reproduced member-stack shortening must match "
            "the certified Phase-2 reference."
        ),
    )

    numeric_check(
        name="A2 bolt mechanical-extension parity",
        measured=(
            deformation_state.bolt_mechanical_extension_mm
        ),
        expected=(
            deformation.bolt_mechanical_extension_mm
        ),
        tolerance=displacement_tolerance_mm,
        reason=(
            "Reproduced bolt mechanical extension must match "
            "the certified Phase-2 reference."
        ),
    )

    numeric_check(
        name="A2 analytical member-shortening parity",
        measured=analytical_member_shortening_mm,
        expected=(
            deformation.analytical_member_shortening_mm
        ),
        tolerance=displacement_tolerance_mm,
        reason=(
            "The analytical joint model used by reproduction "
            "must match the certified Phase-2 analytical "
            "member-shortening reference."
        ),
    )

    reproduced_shortening_ratio = (
        deformation_state.member_shortening_mm
        / analytical_member_shortening_mm
    )

    numeric_check(
        name="A2 FEM-to-analytical shortening-ratio parity",
        measured=reproduced_shortening_ratio,
        expected=deformation.member_shortening_ratio,
        tolerance=ratio_tolerance,
        reason=(
            "The reproduced FEM/analytical member-shortening "
            "relationship must match the certified reference."
        ),
    )

    # --------------------------------------------------------
    # Thread-flank parity.
    # --------------------------------------------------------

    numeric_check(
        name="A2 thread engagement minimum-Z parity",
        measured=thread_flank_state.engagement_min_z_mm,
        expected=flank.engagement_min_z_mm,
        tolerance=geometry_tolerance_mm,
        reason=(
            "The semantic nut-thread engagement start must "
            "match the certified reference geometry."
        ),
    )

    numeric_check(
        name="A2 thread engagement maximum-Z parity",
        measured=thread_flank_state.engagement_max_z_mm,
        expected=flank.engagement_max_z_mm,
        tolerance=geometry_tolerance_mm,
        reason=(
            "The semantic nut-thread engagement end must "
            "match the certified reference geometry."
        ),
    )

    checks.append(
        FemAcceptanceCheck(
            name="A2 +Z flank triangle-count parity",
            kind=FemAcceptanceCheckKind.REPRODUCTION_PARITY,
            passed=(
                thread_flank_state
                .positive_z_flank
                .triangle_count
                == flank.positive_triangle_count
            ),
            measured=(
                thread_flank_state
                .positive_z_flank
                .triangle_count
            ),
            expected=flank.positive_triangle_count,
            reason=(
                "The reproduced +Z flank family must retain "
                "the certified facet population."
            ),
        )
    )

    checks.append(
        FemAcceptanceCheck(
            name="A2 -Z flank triangle-count parity",
            kind=FemAcceptanceCheckKind.REPRODUCTION_PARITY,
            passed=(
                thread_flank_state
                .negative_z_flank
                .triangle_count
                == flank.negative_triangle_count
            ),
            measured=(
                thread_flank_state
                .negative_z_flank
                .triangle_count
            ),
            expected=flank.negative_triangle_count,
            reason=(
                "The reproduced -Z flank family must retain "
                "the certified facet population."
            ),
        )
    )

    checks.append(
        FemAcceptanceCheck(
            name="A2 intended thread-flank parity",
            kind=FemAcceptanceCheckKind.REPRODUCTION_PARITY,
            passed=(
                thread_flank_state.dominant_flank_name
                == flank.intended_flank_name
            ),
            measured=(
                thread_flank_state.dominant_flank_name
            ),
            expected=flank.intended_flank_name,
            reason=(
                "The reproduced dominant thread-flank family "
                "must match the certified reference."
            ),
        )
    )

    checks.append(
        FemAcceptanceCheck(
            name="A2 engaged thread-triangle count parity",
            kind=FemAcceptanceCheckKind.REPRODUCTION_PARITY,
            passed=(
                thread_flank_state.engaged_triangle_count
                == flank.engaged_triangle_count
            ),
            measured=(
                thread_flank_state.engaged_triangle_count
            ),
            expected=flank.engaged_triangle_count,
            reason=(
                "Semantic thread engagement must reproduce "
                "the certified engaged-facet population."
            ),
        )
    )

    numeric_check(
        name="A2 +Z flank mean-compression parity",
        measured=(
            thread_flank_state
            .positive_z_flank
            .mean_compression_mpa
        ),
        expected=flank.positive_mean_compression_mpa,
        tolerance=flank_mean_tolerance_mpa,
        reason=(
            "The reproduced +Z solid-STRESS flank diagnostic "
            "must match the certified reference."
        ),
    )

    numeric_check(
        name="A2 -Z flank mean-compression parity",
        measured=(
            thread_flank_state
            .negative_z_flank
            .mean_compression_mpa
        ),
        expected=flank.negative_mean_compression_mpa,
        tolerance=flank_mean_tolerance_mpa,
        reason=(
            "The reproduced -Z solid-STRESS flank diagnostic "
            "must match the certified reference."
        ),
    )

    numeric_check(
        name="A2 +Z flank median-compression parity",
        measured=(
            thread_flank_state
            .positive_z_flank
            .median_compression_mpa
        ),
        expected=flank.positive_median_compression_mpa,
        tolerance=flank_mean_tolerance_mpa,
        reason=(
            "The reproduced +Z flank median-compression "
            "diagnostic must match the certified reference."
        ),
    )

    numeric_check(
        name="A2 -Z flank median-compression parity",
        measured=(
            thread_flank_state
            .negative_z_flank
            .median_compression_mpa
        ),
        expected=flank.negative_median_compression_mpa,
        tolerance=flank_mean_tolerance_mpa,
        reason=(
            "The reproduced -Z flank median-compression "
            "diagnostic must match the certified reference."
        ),
    )

    numeric_check(
        name="A2 +Z flank compressed-area parity",
        measured=(
            thread_flank_state
            .positive_z_flank
            .compressed_area_percent
        ),
        expected=(
            flank.positive_compressed_area_percent
        ),
        tolerance=flank_area_tolerance_percent,
        reason=(
            "The reproduced +Z compressed-area diagnostic "
            "must match the certified reference."
        ),
    )

    numeric_check(
        name="A2 -Z flank compressed-area parity",
        measured=(
            thread_flank_state
            .negative_z_flank
            .compressed_area_percent
        ),
        expected=(
            flank.negative_compressed_area_percent
        ),
        tolerance=flank_area_tolerance_percent,
        reason=(
            "The reproduced -Z compressed-area diagnostic "
            "must match the certified reference."
        ),
    )

    numeric_check(
        name="A2 thread-flank dominance-ratio parity",
        measured=thread_flank_state.dominance_ratio,
        expected=flank.dominance_ratio,
        tolerance=dominance_tolerance,
        reason=(
            "The reproduced solid-STRESS flank dominance "
            "must match the certified reference."
        ),
    )

    # --------------------------------------------------------
    # Numerical signature parity.
    # --------------------------------------------------------

    checks.append(
        FemAcceptanceCheck(
            name="A2 accepted-increment count parity",
            kind=FemAcceptanceCheckKind.REPRODUCTION_PARITY,
            passed=(
                len(accepted_increments)
                == numerical.accepted_increment_count
            ),
            measured=len(
                accepted_increments
            ),
            expected=numerical.accepted_increment_count,
            reason=(
                "The certified reproduction must retain the "
                "Phase-2 accepted-increment count."
            ),
        )
    )

    final_increment = (
        accepted_increments[-1]
        if accepted_increments
        else None
    )

    checks.append(
        FemAcceptanceCheck(
            name="A2 final nonlinear increment parity",
            kind=FemAcceptanceCheckKind.REPRODUCTION_PARITY,
            passed=(
                final_increment is not None
                and final_increment.step
                == numerical.final_step
                and final_increment.increment
                == numerical.final_increment
                and final_increment.attempt
                == numerical.final_attempt
                and final_increment.iterations
                == numerical.final_iterations
                and abs(
                    final_increment.total_time
                    - numerical.final_time
                )
                <= time_tolerance
            ),
            measured=(
                None
                if final_increment is None
                else (
                    f"step={final_increment.step},"
                    f"inc={final_increment.increment},"
                    f"att={final_increment.attempt},"
                    f"iter={final_increment.iterations},"
                    f"time={final_increment.total_time}"
                )
            ),
            expected=(
                f"step={numerical.final_step},"
                f"inc={numerical.final_increment},"
                f"att={numerical.final_attempt},"
                f"iter={numerical.final_iterations},"
                f"time={numerical.final_time}"
            ),
            tolerance=time_tolerance,
            reason=(
                "The final accepted nonlinear state must reproduce "
                "the certified Phase-2 numerical signature."
            ),
        )
    )

    return tuple(
        checks
    )

def evaluate_certified_reproduction(
    *,
    oracle: FemCertifiedResultOracle,
    preload_decision: PreloadCalibrationDecision,
    thread_normal_force_n: float,
    analytical_member_shortening_mm: float,
    axial_state: CompleteJointAxialStressState,
    deformation_state: CompleteJointDeformationState,
    thread_flank_state: ThreadFlankStressState,
    accepted_increments: tuple[AcceptedIncrement, ...],
    return_code: int | None,
    stdout: str,
    require_process_return_code: bool = True,
) -> FemReproductionAcceptanceResult:
    """Evaluate one certified FEM reproduction end to end.

    General physical/numerical hard gates and strict Phase-2
    reproduction-parity gates remain distinct internally, but their
    combined result is the authoritative CP4 reproduction verdict.
    """

    checks = (
        *build_preload_acceptance_checks(
            preload_decision
        ),
        *build_thread_contact_acceptance_checks(
            thread_normal_force_n=thread_normal_force_n
        ),
        *build_axial_state_acceptance_checks(
            axial_state
        ),
        *build_deformation_acceptance_checks(
            deformation_state
        ),
        *build_thread_flank_acceptance_checks(
            thread_flank_state
        ),
        *build_numerical_completion_acceptance_checks(
            return_code=return_code,
            stdout=stdout,
            accepted_increments=accepted_increments,
            require_process_return_code=(
                require_process_return_code
            ),
        ),
        *build_reproduction_parity_checks(
            oracle=oracle,
            preload_decision=preload_decision,
            thread_normal_force_n=thread_normal_force_n,
            analytical_member_shortening_mm=(
                analytical_member_shortening_mm
            ),
            axial_state=axial_state,
            deformation_state=deformation_state,
            thread_flank_state=thread_flank_state,
            accepted_increments=accepted_increments,
        ),
    )

    return FemReproductionAcceptanceResult(
        checks=checks
    )
