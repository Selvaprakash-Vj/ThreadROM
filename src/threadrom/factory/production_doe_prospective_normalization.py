"""Build standard dataset-facing evidence from a certified prospective first shot.

This module performs normalization only.  It does not execute FEM, alter
acceptance tolerances, or reinterpret a failed support-only equilibrium
diagnostic as a full-system equilibrium PASS.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from threadrom.factory.production_doe_equilibrium_applicability import (
    ProductionDoeEquilibriumApplicability,
    ProductionDoeEquilibriumApplicabilityResult,
)


def _mapping(
    value: object,
    name: str,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(
            f"{name} must be a mapping."
        )

    return value


def _string(
    value: object,
    name: str,
) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
    ):
        raise ValueError(
            f"{name} must be a non-empty string."
        )

    return value


def _float(
    value: object,
    name: str,
) -> float:
    if isinstance(value, bool):
        raise ValueError(
            f"{name} must be numeric."
        )

    try:
        return float(value)
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise ValueError(
            f"{name} must be numeric."
        ) from exc


def _require(
    condition: bool,
    message: str,
) -> None:
    if not condition:
        raise ValueError(message)


def _artifact(
    artifacts: Mapping[str, object],
    name: str,
) -> dict[str, str]:
    item = _mapping(
        artifacts.get(name),
        f"source_artifacts[{name!r}]",
    )

    return {
        "relative_path": _string(
            item.get("relative_path"),
            f"{name}.relative_path",
        ),
        "sha256": _string(
            item.get("sha256"),
            f"{name}.sha256",
        ),
    }


def build_prospective_first_shot_accepted_fem_record(
    *,
    validation: Mapping[str, object],
    preparation: Mapping[str, object],
    source_artifacts: Mapping[str, object],
    support_equilibrium_payload: Mapping[str, object],
    equilibrium_applicability: (
        ProductionDoeEquilibriumApplicabilityResult
    ),
) -> dict[str, object]:
    """Normalize one independently certified prospective first-shot solve."""

    # ------------------------------------------------------------------
    # Prospective certification must already be immutable governed PASS.
    # ------------------------------------------------------------------

    _require(
        validation.get("record_status") == "FINAL",
        "Prospective validation must be FINAL.",
    )

    _require(
        validation.get("overall_disposition")
        == "V2_1_PROSPECTIVE_PASS_ROLLOUT_AUTHORIZED",
        "Prospective validation disposition is not governed PASS.",
    )

    prospective_validation = _mapping(
        validation.get("prospective_validation"),
        "prospective_validation",
    )

    validation_semantics = _mapping(
        validation.get("evidence_semantics"),
        "validation.evidence_semantics",
    )

    governed_acceptance = _mapping(
        validation.get("governed_acceptance"),
        "governed_acceptance",
    )

    validation_case = _mapping(
        validation.get("case"),
        "validation.case",
    )

    solver_execution = _mapping(
        validation.get("solver_execution"),
        "solver_execution",
    )

    _require(
        prospective_validation.get("verdict")
        == "PROSPECTIVE_PASS",
        "Prospective validation verdict must be PROSPECTIVE_PASS.",
    )

    _require(
        prospective_validation.get("prediction_frozen_before_fem")
        is True,
        "Prospective prediction was not frozen before FEM.",
    )

    _require(
        prospective_validation.get("actual_first_fem_trial_used")
        is True,
        "Prospective validation did not use the actual first FEM trial.",
    )

    _require(
        prospective_validation.get("posthoc_tolerance_change")
        is False,
        "Post-hoc tolerance change is forbidden.",
    )

    _require(
        prospective_validation.get("additional_fem_for_validation")
        is False,
        "Prospective validation unexpectedly used additional FEM.",
    )

    _require(
        prospective_validation.get("blind_holdout_accessed")
        is False,
        "Blind holdout access is forbidden.",
    )

    _require(
        validation_semantics.get("solver_success_verified")
        is True,
        "Solver success is not verified.",
    )

    _require(
        validation_semantics.get(
            "governed_calibration_accept_verified"
        )
        is True,
        "Governed calibration ACCEPT is not verified.",
    )

    _require(
        validation_semantics.get(
            "first_shot_is_accepted_physics_solve"
        )
        is True,
        "First-shot accepted physics semantics are missing.",
    )

    _require(
        validation_semantics.get(
            "additional_calibration_required"
        )
        is False,
        "Additional calibration is still required.",
    )

    _require(
        validation_semantics.get(
            "eligible_for_production_dataset"
        )
        is True,
        "Prospective solve is not production-dataset eligible.",
    )

    _require(
        validation_semantics.get("holdout_accessed")
        is False,
        "Holdout access is forbidden.",
    )

    _require(
        governed_acceptance.get("accepted")
        is True,
        "Governed acceptance is not ACCEPT.",
    )

    _require(
        governed_acceptance.get("next_trial_derived")
        is False,
        "Accepted first shot unexpectedly derived another trial.",
    )

    # ------------------------------------------------------------------
    # Solver completion remains independently explicit.
    # ------------------------------------------------------------------

    _require(
        solver_execution.get("disposition") == "succeeded",
        "Prospective solver disposition is not succeeded.",
    )

    _require(
        solver_execution.get("return_code") == 0,
        "Prospective solver return code is not zero.",
    )

    _require(
        solver_execution.get("job_finished") is True,
        "Prospective solver did not report Job finished.",
    )

    _require(
        solver_execution.get("accepted_increment_count") == 20,
        "Prospective solver did not preserve 20 accepted increments.",
    )

    # ------------------------------------------------------------------
    # Preparation lineage must prove canonical V1 was never executed.
    # ------------------------------------------------------------------

    _require(
        preparation.get("record_status") == "FINAL",
        "Prospective preparation must be FINAL.",
    )

    _require(
        preparation.get("overall_disposition")
        == "V2_1_PROSPECTIVE_SOLVER_PREPARATION_PASS",
        "Prospective preparation disposition drift.",
    )

    preparation_case = _mapping(
        preparation.get("case"),
        "preparation.case",
    )

    execution_selection = _mapping(
        preparation.get("execution_selection"),
        "preparation.execution_selection",
    )

    _require(
        execution_selection.get(
            "canonical_v1_trial1_executed"
        )
        is False,
        "Canonical V1 Trial 1 must remain unexecuted.",
    )

    _require(
        execution_selection.get(
            "canonical_v1_trial1_preserved"
        )
        is True,
        "Canonical V1 Trial 1 provenance was not preserved.",
    )

    _require(
        execution_selection.get(
            "prospective_execution_uses_v2_1_sibling"
        )
        is True,
        "Prospective execution is not the governed V2.1 sibling.",
    )

    # ------------------------------------------------------------------
    # Identity binding.
    # ------------------------------------------------------------------

    case_id = _string(
        validation_case.get("case_id"),
        "validation.case.case_id",
    )

    case_hash = _string(
        validation_case.get("case_hash"),
        "validation.case.case_hash",
    )

    accepted_run_id = _string(
        validation_case.get("run_id"),
        "validation.case.run_id",
    )

    target_preload_n = _float(
        validation_case.get("target_preload_n"),
        "validation.case.target_preload_n",
    )

    accepted_delta_temperature_c = _float(
        validation_case.get(
            "frozen_delta_temperature_c"
        ),
        "validation.case.frozen_delta_temperature_c",
    )

    case_run_id = _string(
        preparation_case.get("canonical_case_run_id"),
        "preparation.case.canonical_case_run_id",
    )

    mesh_policy_name = _string(
        preparation_case.get("mesh_policy_name"),
        "preparation.case.mesh_policy_name",
    )

    _require(
        preparation_case.get("case_id") == case_id,
        "Validation/preparation case ID mismatch.",
    )

    _require(
        preparation_case.get("case_hash") == case_hash,
        "Validation/preparation case hash mismatch.",
    )

    _require(
        preparation_case.get("prospective_trial_run_id")
        == accepted_run_id,
        "Validation/preparation prospective run mismatch.",
    )

    _require(
        preparation_case.get("target_preload_n")
        == target_preload_n,
        "Validation/preparation target preload mismatch.",
    )

    # ------------------------------------------------------------------
    # Existing support-only equilibrium result is retained exactly as
    # diagnostic evidence.  It is NEVER converted into PASS here.
    # ------------------------------------------------------------------

    _require(
        support_equilibrium_payload.get("overall_status") == "fail",
        "Expected raw support-only equilibrium diagnostic FAIL.",
    )

    _require(
        equilibrium_applicability.applicability
        is ProductionDoeEquilibriumApplicability
        .DIAGNOSTIC_ONLY_INCOMPLETE_REACTION_SYSTEM,
        "Prospective normalization requires the governed "
        "diagnostic-only incomplete-reaction-system classification.",
    )

    _require(
        equilibrium_applicability.support_only_result_is_diagnostic,
        "Support-only result is not classified diagnostic-only.",
    )

    _require(
        not equilibrium_applicability.full_system_pass_claimed,
        "Full-system equilibrium PASS must not be claimed.",
    )

    _require(
        not equilibrium_applicability.tolerance_changed,
        "Equilibrium tolerance must not change.",
    )

    _require(
        not equilibrium_applicability
        .additional_fem_authorized_by_classifier,
        "Applicability classifier must not authorize additional FEM.",
    )

    _require(
        bool(equilibrium_applicability.missing_reaction_sets),
        "Diagnostic-only classification must preserve missing reactions.",
    )

    # ------------------------------------------------------------------
    # Measurement / governed decision.
    # ------------------------------------------------------------------

    first_shot = _mapping(
        validation.get("first_shot_measurement"),
        "first_shot_measurement",
    )

    decision = _mapping(
        governed_acceptance.get("decision"),
        "governed_acceptance.decision",
    )

    measurement = {
        "under_head_force_n": _float(
            first_shot.get("under_head_force_n"),
            "under_head_force_n",
        ),
        "nut_bearing_force_n": _float(
            first_shot.get("nut_bearing_force_n"),
            "nut_bearing_force_n",
        ),
        "member_interface_force_n": _float(
            first_shot.get("member_interface_force_n"),
            "member_interface_force_n",
        ),
    }

    mean_force_n = _float(
        first_shot.get("mean_clamp_force_n"),
        "mean_clamp_force_n",
    )

    spread_force_n = _float(
        first_shot.get("interface_spread_n"),
        "interface_spread_n",
    )

    spread_relative = _float(
        first_shot.get("interface_spread_relative"),
        "interface_spread_relative",
    )

    target_relative_error = _float(
        first_shot.get("target_relative_error"),
        "target_relative_error",
    )

    target_relative_tolerance = _float(
        governed_acceptance.get(
            "target_relative_tolerance"
        ),
        "target_relative_tolerance",
    )

    spread_relative_tolerance = _float(
        governed_acceptance.get(
            "interface_spread_relative_tolerance"
        ),
        "interface_spread_relative_tolerance",
    )

    _require(
        decision.get("disposition") == "accept",
        "Serialized governed decision is not ACCEPT.",
    )

    _require(
        decision.get("next_delta_temperature_c") is None,
        "Accepted first shot unexpectedly contains next delta-T.",
    )

    # ------------------------------------------------------------------
    # Immutable source references.
    # ------------------------------------------------------------------

    campaign_manifest = _artifact(
        source_artifacts,
        "campaign_manifest",
    )

    doe_policy = _artifact(
        source_artifacts,
        "doe_policy",
    )

    preparation_certification = _artifact(
        source_artifacts,
        "preparation_certification",
    )

    warm_start_v1 = _artifact(
        source_artifacts,
        "warm_start_v1",
    )

    prospective_validation_artifact = _artifact(
        source_artifacts,
        "prospective_validation",
    )

    prospective_prediction = _artifact(
        source_artifacts,
        "prospective_prediction",
    )

    prospective_preparation = _artifact(
        source_artifacts,
        "prospective_preparation",
    )

    v2_1_policy = _artifact(
        source_artifacts,
        "v2_1_policy",
    )

    dat_artifact = _artifact(
        source_artifacts,
        "dat",
    )

    manifest_artifact = {
        "relative_path": _string(
            solver_execution.get(
                "manifest_relative_path"
            ),
            "solver_execution.manifest_relative_path",
        ),
        "sha256": _string(
            solver_execution.get("manifest_sha256"),
            "solver_execution.manifest_sha256",
        ),
    }

    trial = {
        "trial_index": 1,
        "run_id": accepted_run_id,
        "delta_temperature_c": (
            accepted_delta_temperature_c
        ),
        "source": "fem_warm_start",
    }

    solver_manifest_summary = {
        "accepted_increment_count": 20,
        "disposition": "succeeded",
        "job_finished": True,
        "return_code": 0,
    }

    solver_evidence = {
        "adjudication_relative_path": None,
        "adjudication_sha256": None,
        "completed_solution_evidence_verified": True,
        "evidence_kind": "CLEAN_SOLVER_SUCCESS",
        "solver_outcome_adjudicated": False,
        "solver_success_verified": True,
    }

    calibration_history = [
        {
            "trial": trial,
            "measurement": measurement,
            "evaluation": {
                "completed_trial": trial,
                "decision": dict(decision),
                "next_trial": None,
            },
            "preparation_record_relative_path": (
                prospective_preparation["relative_path"]
            ),
            "preparation_record_sha256": (
                prospective_preparation["sha256"]
            ),
            "manifest_relative_path": (
                manifest_artifact["relative_path"]
            ),
            "manifest_sha256": (
                manifest_artifact["sha256"]
            ),
            "dat_relative_path": (
                dat_artifact["relative_path"]
            ),
            "dat_sha256": (
                dat_artifact["sha256"]
            ),
            "solver_manifest_summary": (
                solver_manifest_summary
            ),
            "solver_evidence": solver_evidence,
        }
    ]

    record = {
        "schema_version": 1,
        "record_id": (
            "TRM-P3-CP8-PDOE-C01-"
            f"{case_id}-ACCEPTED-FEM-001"
        ),
        "record_status": "FINAL",
        "case": {
            "case_id": case_id,
            "case_hash": case_hash,
            "case_run_id": case_run_id,
            "target_preload_n": target_preload_n,
            "mesh_policy_name": mesh_policy_name,
        },
        "governance": {
            "doe_policy_relative_path": (
                doe_policy["relative_path"]
            ),
            "doe_policy_sha256": doe_policy["sha256"],
            "campaign_manifest_relative_path": (
                campaign_manifest["relative_path"]
            ),
            "campaign_manifest_sha256": (
                campaign_manifest["sha256"]
            ),
            "preparation_certification_relative_path": (
                preparation_certification["relative_path"]
            ),
            "preparation_certification_sha256": (
                preparation_certification["sha256"]
            ),
            "warm_start_v1_relative_path": (
                warm_start_v1["relative_path"]
            ),
            "warm_start_v1_sha256": (
                warm_start_v1["sha256"]
            ),
            "normalization_mode": (
                "certified_v2_1_prospective_first_shot_zero_solve"
            ),
            "prospective_validation": (
                prospective_validation_artifact
            ),
            "prospective_prediction": (
                prospective_prediction
            ),
            "prospective_preparation": (
                prospective_preparation
            ),
            "v2_1_policy": v2_1_policy,
            "equilibrium_applicability": {
                "classification": (
                    equilibrium_applicability
                    .applicability
                    .value
                ),
                "support_only_raw_status": (
                    support_equilibrium_payload[
                        "overall_status"
                    ]
                ),
                "support_only_result_is_diagnostic": True,
                "full_system_pass_claimed": False,
                "tolerance_changed": False,
                "additional_fem_authorized_by_classifier": False,
                "missing_reaction_sets": list(
                    equilibrium_applicability
                    .missing_reaction_sets
                ),
            },
        },
        "accepted_calibration": {
            "accepted_trial_index": 1,
            "accepted_run_id": accepted_run_id,
            "accepted_delta_temperature_c": (
                accepted_delta_temperature_c
            ),
            "measurement": measurement,
            "mean_clamp_force_n": mean_force_n,
            "interface_spread_force_n": (
                spread_force_n
            ),
            "interface_spread_relative": (
                spread_relative
            ),
            "target_relative_error": (
                target_relative_error
            ),
            "target_relative_tolerance": (
                target_relative_tolerance
            ),
            "spread_relative_tolerance": (
                spread_relative_tolerance
            ),
            "decision": dict(decision),
        },
        "calibration_history": calibration_history,
        "evidence_semantics": {
            "solver_success_verified": True,
            "completed_solution_evidence_verified": True,
            "solver_outcome_adjudicated": False,
            "governed_calibration_accept_verified": True,
            "external_support_equilibrium_verified": False,
            "external_support_equilibrium_raw_status": "fail",
            "external_support_equilibrium_applicability": (
                equilibrium_applicability
                .applicability
                .value
            ),
            "full_system_equilibrium_pass_claimed": False,
            "equilibrium_tolerance_changed": False,
            "trial_1_preserved": True,
            "trial_1_is_accepted_physics_solve": True,
            "trial_2_is_accepted_physics_solve": False,
            "additional_calibration_required": False,
            "additional_fem_authorized_by_normalization": False,
            "eligible_for_warm_start_knowledge": False,
            "eligible_for_v2_anchor_use": False,
            "eligible_for_production_dataset": True,
            "eligible_for_v2_1_parameter_refit_before_rollout": False,
            "canonical_v1_trial1_executed": False,
            "canonical_v1_trial1_preserved": True,
            "holdout_accessed": False,
        },
        "overall_disposition": (
            "PRODUCTION_DOE_FEM_CALIBRATION_ACCEPTED"
        ),
    }

    return record
