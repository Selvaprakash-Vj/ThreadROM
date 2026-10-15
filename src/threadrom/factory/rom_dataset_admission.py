"""Target-specific ROM dataset-admission governance primitives.

This module deliberately separates:

1. pre-target admission readiness,
2. sealed-holdout protection,
3. target extraction,
4. target-specific numerical certification,
5. final sample admission,
6. partition assignment.

The first implementation is intentionally fail closed.

It MUST NOT:
- open FEM result artifacts,
- inspect sealed holdout identities,
- infer missing governance,
- assign dataset partitions,
- promote accepted FEM evidence directly into ROM data.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Sequence


MEMBER_SHORTENING_GATE_IDS = (
    "DA01_TARGET_BINDING",
    "DA02_CASE_IDENTITY",
    "DA03_EXECUTION_IDENTITY",
    "DA04_ENGINEERING_INPUTS",
    "DA05_PHYSICS_ACCEPTANCE",
    "DA06_TARGET_EXTRACTION",
    "DA07_TARGET_VALUE",
    "DA08_NUMERICAL_CERTIFICATION",
    "DA09_PROVENANCE",
    "DA10_APPLICABILITY",
    "DA11_HOLDOUT_PROTECTION",
    "DA12_PARTITION_BOUNDARY",
)


class AdmissionGateState(str, Enum):
    PASS = "PASS"
    DEFERRED = "DEFERRED"
    REJECTED = "REJECTED"
    NOT_EVALUATED = "NOT_EVALUATED"


class AdmissionDecision(str, Enum):
    ADMITTED = "ADMITTED"
    DEFERRED = "DEFERRED"
    REJECTED = "REJECTED"
    NOT_EVALUATED = "NOT_EVALUATED"


@dataclass(frozen=True, slots=True)
class AdmissionGateResult:
    gate_id: str
    state: AdmissionGateState
    reason_code: str | None
    detail: str


@dataclass(frozen=True, slots=True)
class AdmissionReadinessResult:
    case_id: str
    decision: AdmissionDecision
    gates: tuple[AdmissionGateResult, ...]

    def gate(
        self,
        gate_id: str,
    ) -> AdmissionGateResult:
        matches = tuple(
            gate
            for gate in self.gates
            if gate.gate_id == gate_id
        )

        if len(matches) != 1:
            raise RuntimeError(
                f"{self.case_id}: expected exactly one result "
                f"for gate {gate_id!r}; found {len(matches)}."
            )

        return matches[0]


def _gate(
    gate_id: str,
    state: AdmissionGateState,
    *,
    reason_code: str | None = None,
    detail: str,
) -> AdmissionGateResult:
    if gate_id not in MEMBER_SHORTENING_GATE_IDS:
        raise ValueError(
            f"Unsupported dataset-admission gate: {gate_id}"
        )

    if state is AdmissionGateState.PASS and reason_code is not None:
        raise ValueError(
            f"{gate_id}: PASS gate may not carry a failure reason code."
        )

    return AdmissionGateResult(
        gate_id=gate_id,
        state=state,
        reason_code=reason_code,
        detail=detail,
    )


def _inputs_complete(
    engineering_inputs: Mapping[str, Any],
    required_fields: Sequence[str],
) -> tuple[bool, tuple[str, ...]]:
    missing: list[str] = []

    for field in required_fields:
        if field not in engineering_inputs:
            missing.append(field)
            continue

        value = engineering_inputs[field]

        if value is None:
            missing.append(field)
            continue

        if isinstance(value, str) and not value.strip():
            missing.append(field)

    return (
        not missing,
        tuple(sorted(missing)),
    )


def _decision(
    gates: Sequence[AdmissionGateResult],
) -> AdmissionDecision:
    states = {
        gate.state
        for gate in gates
    }

    if AdmissionGateState.REJECTED in states:
        return AdmissionDecision.REJECTED

    if AdmissionGateState.DEFERRED in states:
        return AdmissionDecision.DEFERRED

    if all(
        state is AdmissionGateState.PASS
        for state in states
    ):
        return AdmissionDecision.ADMITTED

    return AdmissionDecision.NOT_EVALUATED


def evaluate_member_shortening_pre_target_readiness(
    *,
    atlas_case: Mapping[str, Any],
    required_engineering_input_fields: Sequence[str],
    target_binding_valid: bool,
    numerical_certification_authority_available: bool,
    case_applicability_resolver_available: bool,
    opaque_holdout_oracle_available: bool,
    opaque_holdout_membership_cleared: bool = False,
) -> AdmissionReadinessResult:
    """Evaluate only gates safe before target-bearing FEM evidence is opened.

    Important sequencing rule
    -------------------------
    DA11 must be resolved by an opaque membership authority before the
    training-candidate workflow is allowed to open target-bearing FEM evidence.

    Therefore DA02/03/05/06/07/09 remain NOT_EVALUATED in this pre-target
    stage. DA08/10 are DEFERRED while their governed authorities are absent.
    DA11 is DEFERRED without an oracle, NOT_EVALUATED when an oracle exists but
    this candidate has not yet been checked, and PASS only after the caller
    proves that this exact candidate cleared the opaque membership check.
    """

    case_id = atlas_case.get("case_id")

    if not isinstance(case_id, str) or not case_id:
        raise ValueError(
            "Atlas candidate lacks a valid case_id."
        )

    engineering_inputs = atlas_case.get(
        "engineering_inputs"
    )

    if not isinstance(
        engineering_inputs,
        Mapping,
    ):
        engineering_inputs = {}

    configuration_status = engineering_inputs.get(
        "configuration_status"
    )

    complete, missing_fields = _inputs_complete(
        engineering_inputs,
        required_engineering_input_fields,
    )

    if (
        configuration_status
        == "NEW_CAMPAIGN_INPUT_ADAPTER_REQUIRED"
        or not complete
    ):
        da04 = _gate(
            "DA04_ENGINEERING_INPUTS",
            AdmissionGateState.DEFERRED,
            reason_code="ENGINEERING_INPUTS_UNRESOLVED",
            detail=(
                "Canonical engineering-input resolution is incomplete. "
                f"configuration_status={configuration_status!r}; "
                f"missing_fields={list(missing_fields)!r}"
            ),
        )
    else:
        da04 = _gate(
            "DA04_ENGINEERING_INPUTS",
            AdmissionGateState.PASS,
            detail=(
                "Canonical engineering inputs are present and no "
                "unresolved campaign-adapter status is recorded."
            ),
        )

    if target_binding_valid:
        da01 = _gate(
            "DA01_TARGET_BINDING",
            AdmissionGateState.PASS,
            detail=(
                "Frozen member-shortening target identity and SHA "
                "are bound by the calling governed transaction."
            ),
        )
    else:
        da01 = _gate(
            "DA01_TARGET_BINDING",
            AdmissionGateState.REJECTED,
            reason_code="TARGET_CONTRACT_MISMATCH",
            detail="Frozen target-contract identity or SHA does not match.",
        )

    if numerical_certification_authority_available:
        da08 = _gate(
            "DA08_NUMERICAL_CERTIFICATION",
            AdmissionGateState.NOT_EVALUATED,
            detail=(
                "Certification authority exists, but target-specific "
                "certification is evaluated only after safe target extraction."
            ),
        )
    else:
        da08 = _gate(
            "DA08_NUMERICAL_CERTIFICATION",
            AdmissionGateState.DEFERRED,
            reason_code="PROVENANCE_INCOMPLETE",
            detail=(
                "The 0.02 limit is frozen, but no governed executable "
                "member-shortening numerical-certification procedure "
                "is currently bound."
            ),
        )

    if case_applicability_resolver_available:
        da10 = _gate(
            "DA10_APPLICABILITY",
            AdmissionGateState.NOT_EVALUATED,
            detail=(
                "Applicability authority exists; case-level evaluation "
                "is reserved for the governed applicability resolver."
            ),
        )
    else:
        da10 = _gate(
            "DA10_APPLICABILITY",
            AdmissionGateState.DEFERRED,
            reason_code="PROVENANCE_INCOMPLETE",
            detail=(
                "A governed applicability envelope exists, but no "
                "case-level admission resolver is yet bound."
            ),
        )

    if (
        opaque_holdout_membership_cleared
        and not opaque_holdout_oracle_available
    ):
        raise ValueError(
            "DA11 candidate clearance cannot be asserted "
            "without an opaque holdout oracle."
        )

    if opaque_holdout_membership_cleared:
        da11 = _gate(
            "DA11_HOLDOUT_PROTECTION",
            AdmissionGateState.PASS,
            detail=(
                "This exact candidate cleared the opaque sealed-holdout "
                "membership check before target-bearing FEM evidence access."
            ),
        )
    elif opaque_holdout_oracle_available:
        da11 = _gate(
            "DA11_HOLDOUT_PROTECTION",
            AdmissionGateState.NOT_EVALUATED,
            detail=(
                "Opaque holdout oracle exists, but this exact candidate "
                "has not yet been proven clear for target-source inspection."
            ),
        )
    else:
        da11 = _gate(
            "DA11_HOLDOUT_PROTECTION",
            AdmissionGateState.DEFERRED,
            reason_code="PROVENANCE_INCOMPLETE",
            detail=(
                "No opaque sealed-holdout membership authority exists. "
                "Target-bearing FEM evidence must remain unopened."
            ),
        )

    gates = (
        da01,

        _gate(
            "DA02_CASE_IDENTITY",
            AdmissionGateState.NOT_EVALUATED,
            detail=(
                "Exact source-certificate identity verification occurs "
                "only after DA11 safely permits candidate inspection."
            ),
        ),

        _gate(
            "DA03_EXECUTION_IDENTITY",
            AdmissionGateState.NOT_EVALUATED,
            detail=(
                "Accepted run_id/trial_index verification occurs only "
                "after DA11 safely permits candidate inspection."
            ),
        ),

        da04,

        _gate(
            "DA05_PHYSICS_ACCEPTANCE",
            AdmissionGateState.NOT_EVALUATED,
            detail=(
                "Full physics certificate is deliberately not opened "
                "during pre-target readiness."
            ),
        ),

        _gate(
            "DA06_TARGET_EXTRACTION",
            AdmissionGateState.NOT_EVALUATED,
            detail=(
                "member_shortening_mm is deliberately not extracted "
                "before holdout protection is resolved."
            ),
        ),

        _gate(
            "DA07_TARGET_VALUE",
            AdmissionGateState.NOT_EVALUATED,
            detail=(
                "Target finiteness/nonzero validation requires safe "
                "target extraction first."
            ),
        ),

        da08,

        _gate(
            "DA09_PROVENANCE",
            AdmissionGateState.NOT_EVALUATED,
            detail=(
                "Final source-artifact/extractor provenance verification "
                "occurs after safe source inspection."
            ),
        ),

        da10,

        da11,

        _gate(
            "DA12_PARTITION_BOUNDARY",
            AdmissionGateState.PASS,
            detail=(
                "Admission readiness does not assign training, validation "
                "or independent-evaluation membership."
            ),
        ),
    )

    if tuple(
        gate.gate_id
        for gate in gates
    ) != MEMBER_SHORTENING_GATE_IDS:
        raise RuntimeError(
            "Dataset-admission gate ordering/coverage drift."
        )

    result = AdmissionReadinessResult(
        case_id=case_id,
        decision=_decision(gates),
        gates=gates,
    )

    # With the current pre-target API, ADMITTED is impossible because
    # target-bearing gates deliberately remain NOT_EVALUATED.
    if result.decision is AdmissionDecision.ADMITTED:
        raise RuntimeError(
            "Pre-target readiness may not produce ADMITTED."
        )

    return result


def evaluate_member_shortening_post_target_admission(
    *,
    atlas_case: Mapping[str, Any],
    required_engineering_input_fields: Sequence[str],
    target_binding_valid: bool,
    case_identity_valid: bool,
    execution_identity_valid: bool,
    physics_acceptance_valid: bool,
    target_extraction_valid: bool,
    target_value_mm: float | int | None,
    numerical_certification_passed: bool | None,
    provenance_valid: bool,
    applicability_passed: bool | None,
    opaque_holdout_oracle_available: bool,
    opaque_holdout_membership_cleared: bool,
    partition_unassigned: bool,
) -> AdmissionReadinessResult:
    """Evaluate the complete target-specific admission state after safe extraction.

    This function is intentionally campaign- and wave-agnostic.

    Inputs supplied by the caller are already-governed facts produced by
    upstream authorities:

    * FEM Atlas / accepted source identity,
    * engineering-input resolution,
    * physics acceptance,
    * deterministic target extraction,
    * numerical-certification authority when available,
    * provenance verification,
    * applicability authority when available,
    * opaque holdout protection, and
    * the no-partition-before-admission boundary.

    ``None`` for numerical certification or applicability means that the
    corresponding governed authority is not yet available. The gate is then
    DEFERRED rather than guessed, weakened, or retroactively passed.
    """

    import math

    case_id = atlas_case.get(
        "case_id"
    )

    if (
        not isinstance(
            case_id,
            str,
        )
        or not case_id
    ):
        raise ValueError(
            "Atlas candidate lacks a valid case_id."
        )

    engineering_inputs = atlas_case.get(
        "engineering_inputs"
    )

    if not isinstance(
        engineering_inputs,
        Mapping,
    ):
        engineering_inputs = {}

    configuration_status = engineering_inputs.get(
        "configuration_status"
    )

    complete, missing_fields = _inputs_complete(
        engineering_inputs,
        required_engineering_input_fields,
    )

    if (
        configuration_status
        == "NEW_CAMPAIGN_INPUT_ADAPTER_REQUIRED"
        or not complete
    ):
        da04 = _gate(
            "DA04_ENGINEERING_INPUTS",
            AdmissionGateState.DEFERRED,
            reason_code="ENGINEERING_INPUTS_UNRESOLVED",
            detail=(
                "Canonical engineering-input resolution is incomplete. "
                f"configuration_status={configuration_status!r}; "
                f"missing_fields={list(missing_fields)!r}"
            ),
        )
    else:
        da04 = _gate(
            "DA04_ENGINEERING_INPUTS",
            AdmissionGateState.PASS,
            detail=(
                "Canonical engineering inputs are complete and no "
                "unresolved campaign-adapter status is recorded."
            ),
        )

    da01 = (
        _gate(
            "DA01_TARGET_BINDING",
            AdmissionGateState.PASS,
            detail=(
                "Frozen member-shortening target identity and SHA "
                "match the governed transaction."
            ),
        )
        if target_binding_valid
        else _gate(
            "DA01_TARGET_BINDING",
            AdmissionGateState.REJECTED,
            reason_code="TARGET_CONTRACT_MISMATCH",
            detail=(
                "Frozen member-shortening target identity or SHA "
                "does not match."
            ),
        )
    )

    da02 = (
        _gate(
            "DA02_CASE_IDENTITY",
            AdmissionGateState.PASS,
            detail=(
                "case_id and case_hash exactly match the governing "
                "accepted FEM evidence."
            ),
        )
        if case_identity_valid
        else _gate(
            "DA02_CASE_IDENTITY",
            AdmissionGateState.REJECTED,
            reason_code="CASE_IDENTITY_MISMATCH",
            detail=(
                "Candidate case identity does not exactly match "
                "the governing accepted FEM evidence."
            ),
        )
    )

    da03 = (
        _gate(
            "DA03_EXECUTION_IDENTITY",
            AdmissionGateState.PASS,
            detail=(
                "case_run_id, accepted run identity and governed "
                "execution identity are consistent."
            ),
        )
        if execution_identity_valid
        else _gate(
            "DA03_EXECUTION_IDENTITY",
            AdmissionGateState.REJECTED,
            reason_code="EXECUTION_IDENTITY_MISMATCH",
            detail=(
                "Accepted FEM execution identity is inconsistent "
                "with the candidate source."
            ),
        )
    )

    da05 = (
        _gate(
            "DA05_PHYSICS_ACCEPTANCE",
            AdmissionGateState.PASS,
            detail=(
                "The governing FEM state is final and physically accepted."
            ),
        )
        if physics_acceptance_valid
        else _gate(
            "DA05_PHYSICS_ACCEPTANCE",
            AdmissionGateState.REJECTED,
            reason_code="PHYSICS_ACCEPTANCE_FAILED",
            detail=(
                "The governing FEM state is not proven final and "
                "full-physics accepted."
            ),
        )
    )

    if target_extraction_valid:
        da06 = _gate(
            "DA06_TARGET_EXTRACTION",
            AdmissionGateState.PASS,
            detail=(
                "member_shortening_mm was deterministically obtained "
                "under the frozen target-extraction contract."
            ),
        )
    else:
        da06 = _gate(
            "DA06_TARGET_EXTRACTION",
            AdmissionGateState.REJECTED,
            reason_code="TARGET_EXTRACTION_FAILED",
            detail=(
                "member_shortening_mm was not deterministically "
                "established from the accepted FEM state."
            ),
        )

    if target_extraction_valid:

        target_numeric = (
            isinstance(
                target_value_mm,
                (int, float),
            )
            and not isinstance(
                target_value_mm,
                bool,
            )
        )

        target_valid = (
            target_numeric
            and math.isfinite(
                float(
                    target_value_mm
                )
            )
            and float(
                target_value_mm
            )
            != 0.0
        )

        da07 = (
            _gate(
                "DA07_TARGET_VALUE",
                AdmissionGateState.PASS,
                detail=(
                    "Extracted member_shortening_mm is finite and nonzero."
                ),
            )
            if target_valid
            else _gate(
                "DA07_TARGET_VALUE",
                AdmissionGateState.REJECTED,
                reason_code="TARGET_VALUE_INVALID",
                detail=(
                    "Extracted member_shortening_mm is absent, non-finite "
                    "or zero."
                ),
            )
        )

    else:

        da07 = _gate(
            "DA07_TARGET_VALUE",
            AdmissionGateState.NOT_EVALUATED,
            detail=(
                "Target-value validation cannot occur because deterministic "
                "target extraction did not pass."
            ),
        )

    if numerical_certification_passed is None:

        da08 = _gate(
            "DA08_NUMERICAL_CERTIFICATION",
            AdmissionGateState.DEFERRED,
            reason_code="PROVENANCE_INCOMPLETE",
            detail=(
                "The frozen 0.02 relative limit remains binding, but a "
                "governed target-specific numerical-certification decision "
                "is not yet available for this candidate."
            ),
        )

    elif numerical_certification_passed:

        da08 = _gate(
            "DA08_NUMERICAL_CERTIFICATION",
            AdmissionGateState.PASS,
            detail=(
                "Target-specific numerical certification passes the "
                "predeclared 0.02 relative limit."
            ),
        )

    else:

        da08 = _gate(
            "DA08_NUMERICAL_CERTIFICATION",
            AdmissionGateState.REJECTED,
            reason_code="NUMERICAL_CERTIFICATION_FAILED",
            detail=(
                "Target-specific numerical certification failed the "
                "predeclared 0.02 relative limit."
            ),
        )

    da09 = (
        _gate(
            "DA09_PROVENANCE",
            AdmissionGateState.PASS,
            detail=(
                "Required source artifacts, extraction implementation "
                "and governing identities are reproducibly bound."
            ),
        )
        if provenance_valid
        else _gate(
            "DA09_PROVENANCE",
            AdmissionGateState.REJECTED,
            reason_code="PROVENANCE_MISMATCH",
            detail=(
                "Required target-source or extraction provenance is "
                "missing or inconsistent."
            ),
        )
    )

    if applicability_passed is None:

        da10 = _gate(
            "DA10_APPLICABILITY",
            AdmissionGateState.DEFERRED,
            reason_code="PROVENANCE_INCOMPLETE",
            detail=(
                "A governed engineering applicability envelope exists, "
                "but no completed case-level applicability decision is "
                "bound to this candidate yet."
            ),
        )

    elif applicability_passed:

        da10 = _gate(
            "DA10_APPLICABILITY",
            AdmissionGateState.PASS,
            detail=(
                "The candidate lies inside the governed engineering "
                "applicability envelope."
            ),
        )

    else:

        da10 = _gate(
            "DA10_APPLICABILITY",
            AdmissionGateState.REJECTED,
            reason_code="OUTSIDE_APPLICABILITY",
            detail=(
                "The candidate is outside the governed engineering "
                "applicability envelope."
            ),
        )

    if (
        opaque_holdout_membership_cleared
        and not opaque_holdout_oracle_available
    ):
        raise ValueError(
            "DA11 candidate clearance cannot be asserted "
            "without an opaque holdout oracle."
        )

    if opaque_holdout_membership_cleared:

        da11 = _gate(
            "DA11_HOLDOUT_PROTECTION",
            AdmissionGateState.PASS,
            detail=(
                "This exact candidate cleared the opaque sealed-holdout "
                "membership check before target-bearing source access."
            ),
        )

    elif opaque_holdout_oracle_available:

        da11 = _gate(
            "DA11_HOLDOUT_PROTECTION",
            AdmissionGateState.NOT_EVALUATED,
            detail=(
                "An opaque holdout oracle exists, but this exact candidate "
                "has not yet been cleared."
            ),
        )

    else:

        da11 = _gate(
            "DA11_HOLDOUT_PROTECTION",
            AdmissionGateState.DEFERRED,
            reason_code="PROVENANCE_INCOMPLETE",
            detail=(
                "No opaque sealed-holdout membership authority is available."
            ),
        )

    da12 = (
        _gate(
            "DA12_PARTITION_BOUNDARY",
            AdmissionGateState.PASS,
            detail=(
                "No training, validation or independent-evaluation "
                "partition is assigned by dataset admission."
            ),
        )
        if partition_unassigned
        else _gate(
            "DA12_PARTITION_BOUNDARY",
            AdmissionGateState.REJECTED,
            reason_code="PARTITION_PREASSIGNED",
            detail=(
                "The candidate already carries a dataset partition before "
                "target-specific admission."
            ),
        )
    )

    gates = (
        da01,
        da02,
        da03,
        da04,
        da05,
        da06,
        da07,
        da08,
        da09,
        da10,
        da11,
        da12,
    )

    if tuple(
        gate.gate_id
        for gate in gates
    ) != MEMBER_SHORTENING_GATE_IDS:
        raise RuntimeError(
            "Dataset-admission gate ordering/coverage drift."
        )

    return AdmissionReadinessResult(
        case_id=case_id,
        decision=_decision(
            gates
        ),
        gates=gates,
    )

