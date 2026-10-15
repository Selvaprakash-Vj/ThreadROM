from __future__ import annotations

import pytest

from threadrom.factory.rom_dataset_admission import (
    AdmissionDecision,
    AdmissionGateState,
    evaluate_member_shortening_pre_target_readiness,
)


def _case():
    return {
        "case_id": "TEST-DA11-CASE",
        "engineering_inputs": {},
    }


def _evaluate(
    *,
    oracle_available: bool,
    membership_cleared: bool = False,
):
    return evaluate_member_shortening_pre_target_readiness(
        atlas_case=_case(),
        required_engineering_input_fields=(),
        target_binding_valid=True,
        numerical_certification_authority_available=False,
        case_applicability_resolver_available=False,
        opaque_holdout_oracle_available=oracle_available,
        opaque_holdout_membership_cleared=membership_cleared,
    )


def test_da11_without_oracle_is_deferred():
    result = _evaluate(
        oracle_available=False,
    )

    gate = result.gate(
        "DA11_HOLDOUT_PROTECTION"
    )

    assert gate.state is AdmissionGateState.DEFERRED
    assert result.decision is AdmissionDecision.DEFERRED


def test_da11_oracle_without_candidate_clearance_is_not_evaluated():
    result = _evaluate(
        oracle_available=True,
    )

    gate = result.gate(
        "DA11_HOLDOUT_PROTECTION"
    )

    assert gate.state is AdmissionGateState.NOT_EVALUATED


def test_da11_exact_candidate_clearance_passes():
    result = _evaluate(
        oracle_available=True,
        membership_cleared=True,
    )

    gate = result.gate(
        "DA11_HOLDOUT_PROTECTION"
    )

    assert gate.state is AdmissionGateState.PASS

    # DA08 + DA10 remain deliberately deferred at this stage.
    assert result.decision is AdmissionDecision.DEFERRED


def test_da11_clearance_without_oracle_is_invalid():
    with pytest.raises(
        ValueError,
        match=(
            "candidate clearance cannot be asserted "
            "without an opaque holdout oracle"
        ),
    ):
        _evaluate(
            oracle_available=False,
            membership_cleared=True,
        )