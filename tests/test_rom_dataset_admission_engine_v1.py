from threadrom.factory.rom_dataset_admission import (
    AdmissionDecision,
    AdmissionGateState,
    MEMBER_SHORTENING_GATE_IDS,
    evaluate_member_shortening_pre_target_readiness,
)


REQUIRED = (
    "thread_designation",
    "bolt_material_id",
    "nut_material_id",
    "head_member_material_id",
    "nut_member_material_id",
    "head_member_thickness_mm",
    "nut_member_thickness_mm",
    "member_outer_diameter_mm",
    "member_clearance_hole_diameter_mm",
    "thread_friction_coefficient",
    "head_bearing_friction_coefficient",
    "nut_bearing_friction_coefficient",
    "member_interface_friction_coefficient",
    "target_preload_n",
    "external_axial_load_n",
)


def resolved_case():
    values = {
        field: 1.0
        for field in REQUIRED
    }

    values.update(
        {
            "thread_designation": "M10x1.5",
            "bolt_material_id": "bolt",
            "nut_material_id": "nut",
            "head_member_material_id": "member",
            "nut_member_material_id": "member",
            "configuration_status": "RESOLVED",
        }
    )

    return {
        "case_id": "UNIT-RESOLVED",
        "engineering_inputs": values,
    }


def test_pre_target_gate_coverage_and_order():
    result = evaluate_member_shortening_pre_target_readiness(
        atlas_case=resolved_case(),
        required_engineering_input_fields=REQUIRED,
        target_binding_valid=True,
        numerical_certification_authority_available=False,
        case_applicability_resolver_available=False,
        opaque_holdout_oracle_available=False,
    )

    assert tuple(
        gate.gate_id
        for gate in result.gates
    ) == MEMBER_SHORTENING_GATE_IDS


def test_resolved_case_still_fails_closed_without_missing_authorities():
    result = evaluate_member_shortening_pre_target_readiness(
        atlas_case=resolved_case(),
        required_engineering_input_fields=REQUIRED,
        target_binding_valid=True,
        numerical_certification_authority_available=False,
        case_applicability_resolver_available=False,
        opaque_holdout_oracle_available=False,
    )

    assert result.decision is AdmissionDecision.DEFERRED

    assert (
        result.gate(
            "DA04_ENGINEERING_INPUTS"
        ).state
        is AdmissionGateState.PASS
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

    assert (
        result.gate(
            "DA11_HOLDOUT_PROTECTION"
        ).state
        is AdmissionGateState.DEFERRED
    )

    assert (
        result.gate(
            "DA12_PARTITION_BOUNDARY"
        ).state
        is AdmissionGateState.PASS
    )

    assert (
        result.gate(
            "DA06_TARGET_EXTRACTION"
        ).state
        is AdmissionGateState.NOT_EVALUATED
    )


def test_unresolved_input_adapter_is_deferred_not_rejected():
    case = resolved_case()

    case[
        "engineering_inputs"
    ][
        "configuration_status"
    ] = "NEW_CAMPAIGN_INPUT_ADAPTER_REQUIRED"

    result = evaluate_member_shortening_pre_target_readiness(
        atlas_case=case,
        required_engineering_input_fields=REQUIRED,
        target_binding_valid=True,
        numerical_certification_authority_available=False,
        case_applicability_resolver_available=False,
        opaque_holdout_oracle_available=False,
    )

    gate = result.gate(
        "DA04_ENGINEERING_INPUTS"
    )

    assert gate.state is AdmissionGateState.DEFERRED
    assert gate.reason_code == "ENGINEERING_INPUTS_UNRESOLVED"
    assert result.decision is AdmissionDecision.DEFERRED


def test_target_binding_mismatch_is_definitive_rejection():
    result = evaluate_member_shortening_pre_target_readiness(
        atlas_case=resolved_case(),
        required_engineering_input_fields=REQUIRED,
        target_binding_valid=False,
        numerical_certification_authority_available=False,
        case_applicability_resolver_available=False,
        opaque_holdout_oracle_available=False,
    )

    gate = result.gate(
        "DA01_TARGET_BINDING"
    )

    assert gate.state is AdmissionGateState.REJECTED
    assert gate.reason_code == "TARGET_CONTRACT_MISMATCH"
    assert result.decision is AdmissionDecision.REJECTED


def test_pre_target_api_cannot_admit_even_when_authorities_exist():
    result = evaluate_member_shortening_pre_target_readiness(
        atlas_case=resolved_case(),
        required_engineering_input_fields=REQUIRED,
        target_binding_valid=True,
        numerical_certification_authority_available=True,
        case_applicability_resolver_available=True,
        opaque_holdout_oracle_available=True,
    )

    assert result.decision is AdmissionDecision.NOT_EVALUATED

    assert (
        result.gate(
            "DA06_TARGET_EXTRACTION"
        ).state
        is AdmissionGateState.NOT_EVALUATED
    )

    assert (
        result.gate(
            "DA12_PARTITION_BOUNDARY"
        ).state
        is AdmissionGateState.PASS
    )
