from __future__ import annotations

from threadrom.factory.production_doe_equilibrium_applicability import (
    classify_production_doe_equilibrium_applicability,
)
from threadrom.factory.production_doe_prospective_normalization import (
    build_prospective_first_shot_accepted_fem_record,
)


def _validation() -> dict[str, object]:
    measurement = {
        "under_head_force_n": 99.9,
        "nut_bearing_force_n": 100.0,
        "member_interface_force_n": 100.1,
    }

    decision = {
        "disposition": "accept",
        "measurement": measurement,
        "next_delta_temperature_c": None,
        "spread_relative_tolerance": 0.005,
        "target_force_n": 100.0,
        "target_relative_error": 0.0,
        "target_relative_tolerance": 0.01,
    }

    return {
        "record_status": "FINAL",
        "overall_disposition": (
            "V2_1_PROSPECTIVE_PASS_ROLLOUT_AUTHORIZED"
        ),
        "case": {
            "case_id": "D-INT-008",
            "case_hash": "abc123",
            "run_id": "trm_fem_abc123_cal_01_wsv21",
            "target_preload_n": 100.0,
            "frozen_delta_temperature_c": -200.0,
        },
        "prospective_validation": {
            "verdict": "PROSPECTIVE_PASS",
            "prediction_frozen_before_fem": True,
            "actual_first_fem_trial_used": True,
            "posthoc_tolerance_change": False,
            "additional_fem_for_validation": False,
            "blind_holdout_accessed": False,
        },
        "evidence_semantics": {
            "solver_success_verified": True,
            "governed_calibration_accept_verified": True,
            "first_shot_is_accepted_physics_solve": True,
            "additional_calibration_required": False,
            "eligible_for_production_dataset": True,
            "holdout_accessed": False,
        },
        "governed_acceptance": {
            "target_relative_tolerance": 0.01,
            "interface_spread_relative_tolerance": 0.005,
            "decision": decision,
            "accepted": True,
            "next_trial_derived": False,
        },
        "first_shot_measurement": {
            **measurement,
            "mean_clamp_force_n": 100.0,
            "interface_spread_n": 0.2,
            "interface_spread_relative": 0.002,
            "target_relative_error": 0.0,
        },
        "solver_execution": {
            "manifest_relative_path": "manifest.json",
            "manifest_sha256": "manifest-sha",
            "disposition": "succeeded",
            "return_code": 0,
            "job_finished": True,
            "accepted_increment_count": 20,
        },
    }


def _preparation() -> dict[str, object]:
    return {
        "record_status": "FINAL",
        "overall_disposition": (
            "V2_1_PROSPECTIVE_SOLVER_PREPARATION_PASS"
        ),
        "case": {
            "canonical_case_run_id": "trm_fem_abc123",
            "case_hash": "abc123",
            "case_id": "D-INT-008",
            "mesh_policy_name": "medium_plus_v1",
            "prospective_trial_run_id": (
                "trm_fem_abc123_cal_01_wsv21"
            ),
            "target_preload_n": 100.0,
        },
        "execution_selection": {
            "canonical_v1_trial1_executed": False,
            "canonical_v1_trial1_preserved": True,
            "prospective_execution_uses_v2_1_sibling": True,
        },
    }


def _artifacts() -> dict[str, object]:
    names = (
        "campaign_manifest",
        "doe_policy",
        "preparation_certification",
        "warm_start_v1",
        "prospective_validation",
        "prospective_prediction",
        "prospective_preparation",
        "v2_1_policy",
        "dat",
    )

    return {
        name: {
            "relative_path": f"{name}.dat",
            "sha256": f"{name}-sha",
        }
        for name in names
    }


def _applicability():
    return classify_production_doe_equilibrium_applicability(
        constrained_reaction_sets=(
            "HEAD_MEMBER_SUPPORT_BAND",
            "NUT_MEMBER_GUIDANCE_REFERENCE",
        ),
        reaction_observable_sets=(
            "HEAD_MEMBER_SUPPORT_BAND",
        ),
    )


def _build() -> dict[str, object]:
    return build_prospective_first_shot_accepted_fem_record(
        validation=_validation(),
        preparation=_preparation(),
        source_artifacts=_artifacts(),
        support_equilibrium_payload={
            "overall_status": "fail",
        },
        equilibrium_applicability=_applicability(),
    )


def test_normalization_builds_standard_dataset_facing_record() -> None:
    record = _build()

    assert record["record_status"] == "FINAL"
    assert (
        record["overall_disposition"]
        == "PRODUCTION_DOE_FEM_CALIBRATION_ACCEPTED"
    )

    accepted = record["accepted_calibration"]

    assert accepted["accepted_trial_index"] == 1
    assert (
        accepted["accepted_run_id"]
        == "trm_fem_abc123_cal_01_wsv21"
    )

    assert len(record["calibration_history"]) == 1


def test_normalization_preserves_support_fail_without_pass_claim() -> None:
    record = _build()

    semantics = record["evidence_semantics"]

    assert (
        semantics["external_support_equilibrium_raw_status"]
        == "fail"
    )

    assert not semantics["external_support_equilibrium_verified"]
    assert not semantics["full_system_equilibrium_pass_claimed"]
    assert not semantics["equilibrium_tolerance_changed"]


def test_normalization_preserves_prospective_lineage() -> None:
    record = _build()

    semantics = record["evidence_semantics"]

    assert semantics["trial_1_is_accepted_physics_solve"]
    assert not semantics["trial_2_is_accepted_physics_solve"]

    assert not semantics["canonical_v1_trial1_executed"]
    assert semantics["canonical_v1_trial1_preserved"]

    assert not semantics[
        "eligible_for_warm_start_knowledge"
    ]

    assert not semantics[
        "eligible_for_v2_anchor_use"
    ]

    assert not semantics[
        "eligible_for_v2_1_parameter_refit_before_rollout"
    ]


def test_normalization_does_not_authorize_more_fem() -> None:
    record = _build()

    assert not record["evidence_semantics"][
        "additional_fem_authorized_by_normalization"
    ]

    assert not record["governance"][
        "equilibrium_applicability"
    ][
        "additional_fem_authorized_by_classifier"
    ]


def test_normalization_rejects_support_fail_pass_rewrite() -> None:
    try:
        build_prospective_first_shot_accepted_fem_record(
            validation=_validation(),
            preparation=_preparation(),
            source_artifacts=_artifacts(),
            support_equilibrium_payload={
                "overall_status": "pass",
            },
            equilibrium_applicability=_applicability(),
        )
    except ValueError as exc:
        assert (
            str(exc)
            == "Expected raw support-only equilibrium "
            "diagnostic FAIL."
        )
    else:
        raise AssertionError(
            "Normalizer must refuse to rewrite the raw diagnostic."
        )


def test_normalization_rejects_executed_canonical_v1() -> None:
    preparation = _preparation()

    preparation["execution_selection"] = {
        "canonical_v1_trial1_executed": True,
        "canonical_v1_trial1_preserved": True,
        "prospective_execution_uses_v2_1_sibling": True,
    }

    try:
        build_prospective_first_shot_accepted_fem_record(
            validation=_validation(),
            preparation=preparation,
            source_artifacts=_artifacts(),
            support_equilibrium_payload={
                "overall_status": "fail",
            },
            equilibrium_applicability=_applicability(),
        )
    except ValueError as exc:
        assert (
            str(exc)
            == "Canonical V1 Trial 1 must remain unexecuted."
        )
    else:
        raise AssertionError(
            "Executed canonical V1 provenance must fail closed."
        )
