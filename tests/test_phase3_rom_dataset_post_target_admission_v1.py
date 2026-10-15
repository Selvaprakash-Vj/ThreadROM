from __future__ import annotations

import pytest

from threadrom.factory.rom_dataset_admission import (
    AdmissionDecision,
    AdmissionGateState,
    evaluate_member_shortening_post_target_admission,
)


REQUIRED = (
    "thread_designation",
    "target_preload_n",
)


def candidate():
    return {
        "case_id": "GENERIC-CASE-001",
        "dataset_partition": None,
        "engineering_inputs": {
            "configuration_status": "RESOLVED",
            "thread_designation": "M10x1.5",
            "target_preload_n": 15000.0,
        },
    }


def evaluate(
    **overrides,
):
    values = {
        "atlas_case": candidate(),
        "required_engineering_input_fields": REQUIRED,
        "target_binding_valid": True,
        "case_identity_valid": True,
        "execution_identity_valid": True,
        "physics_acceptance_valid": True,
        "target_extraction_valid": True,
        "target_value_mm": 0.0025,
        "numerical_certification_passed": True,
        "provenance_valid": True,
        "applicability_passed": True,
        "opaque_holdout_oracle_available": True,
        "opaque_holdout_membership_cleared": True,
        "partition_unassigned": True,
    }

    values.update(
        overrides
    )

    return (
        evaluate_member_shortening_post_target_admission(
            **values
        )
    )


def test_all_complete_gates_admit() -> None:
    result = evaluate()

    assert (
        result.decision
        is AdmissionDecision.ADMITTED
    )

    assert all(
        gate.state
        is AdmissionGateState.PASS
        for gate in result.gates
    )


def test_missing_da08_and_da10_authorities_defer_without_guessing() -> None:
    result = evaluate(
        numerical_certification_passed=None,
        applicability_passed=None,
    )

    assert (
        result.decision
        is AdmissionDecision.DEFERRED
    )

    assert (
        result.gate(
            "DA08_NUMERICAL_CERTIFICATION"
        ).state
        is AdmissionGateState.DEFERRED
    )

    assert (
        result.gate(
            "DA10_APPLICABILITY"
        ).state
        is AdmissionGateState.DEFERRED
    )

    for gate_id in (
        "DA01_TARGET_BINDING",
        "DA02_CASE_IDENTITY",
        "DA03_EXECUTION_IDENTITY",
        "DA04_ENGINEERING_INPUTS",
        "DA05_PHYSICS_ACCEPTANCE",
        "DA06_TARGET_EXTRACTION",
        "DA07_TARGET_VALUE",
        "DA09_PROVENANCE",
        "DA11_HOLDOUT_PROTECTION",
        "DA12_PARTITION_BOUNDARY",
    ):
        assert (
            result.gate(
                gate_id
            ).state
            is AdmissionGateState.PASS
        )


@pytest.mark.parametrize(
    "value",
    (
        0.0,
        float("nan"),
        float("inf"),
        None,
    ),
)
def test_invalid_target_is_rejected(
    value,
) -> None:
    result = evaluate(
        target_value_mm=value
    )

    gate = result.gate(
        "DA07_TARGET_VALUE"
    )

    assert (
        result.decision
        is AdmissionDecision.REJECTED
    )

    assert (
        gate.state
        is AdmissionGateState.REJECTED
    )

    assert (
        gate.reason_code
        == "TARGET_VALUE_INVALID"
    )


def test_uncleared_holdout_candidate_cannot_be_admitted() -> None:
    result = evaluate(
        opaque_holdout_membership_cleared=False
    )

    assert (
        result.decision
        is AdmissionDecision.NOT_EVALUATED
    )

    assert (
        result.gate(
            "DA11_HOLDOUT_PROTECTION"
        ).state
        is AdmissionGateState.NOT_EVALUATED
    )


def test_partition_must_still_be_unassigned() -> None:
    result = evaluate(
        partition_unassigned=False
    )

    assert (
        result.decision
        is AdmissionDecision.REJECTED
    )

    assert (
        result.gate(
            "DA12_PARTITION_BOUNDARY"
        ).reason_code
        == "PARTITION_PREASSIGNED"
    )


def test_holdout_clearance_requires_oracle() -> None:
    with pytest.raises(
        ValueError,
        match="without an opaque holdout oracle",
    ):
        evaluate(
            opaque_holdout_oracle_available=False,
            opaque_holdout_membership_cleared=True,
        )


def test_engineering_input_gap_defers() -> None:
    broken = candidate()

    del broken[
        "engineering_inputs"
    ][
        "target_preload_n"
    ]

    result = evaluate(
        atlas_case=broken
    )

    assert (
        result.decision
        is AdmissionDecision.DEFERRED
    )

    assert (
        result.gate(
            "DA04_ENGINEERING_INPUTS"
        ).state
        is AdmissionGateState.DEFERRED
    )


def test_numerical_certification_failure_rejects() -> None:
    result = evaluate(
        numerical_certification_passed=False
    )

    assert (
        result.decision
        is AdmissionDecision.REJECTED
    )

    assert (
        result.gate(
            "DA08_NUMERICAL_CERTIFICATION"
        ).reason_code
        == "NUMERICAL_CERTIFICATION_FAILED"
    )


def test_outside_applicability_rejects() -> None:
    result = evaluate(
        applicability_passed=False
    )

    assert (
        result.decision
        is AdmissionDecision.REJECTED
    )

    assert (
        result.gate(
            "DA10_APPLICABILITY"
        ).reason_code
        == "OUTSIDE_APPLICABILITY"
    )
