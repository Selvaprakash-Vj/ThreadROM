"""Tests for resolved-identity-safe FEM calibration reuse."""

from dataclasses import replace

from threadrom.case.resolver import resolve_case
from threadrom.factory.fem_calibration_knowledge import (
    FemWarmStartSource,
    build_fem_calibration_knowledge_record,
    predict_fem_warm_start,
)
from threadrom.factory.pilot_doe import (
    PilotDoeCaseId,
    build_phase3_cp7_pilot_doe,
)
from threadrom.factory.preload_calibration_seed import (
    derive_analytical_thermal_preload_seed,
)
from tests.unit.test_phase3_fem_calibration_knowledge import (
    _TEST_EXECUTION_GENERATION_ID,
    _geometry_identity,
    _policy,
)


def _pilot(case_id: PilotDoeCaseId):
    campaign = build_phase3_cp7_pilot_doe()

    item = next(
        item
        for item in campaign.cases
        if item.case_id is case_id
    )

    resolved = resolve_case(item.case)
    seed = derive_analytical_thermal_preload_seed(resolved)

    return resolved, seed


def test_new_calibration_record_preserves_both_identities() -> None:
    resolved, seed = _pilot(
        PilotDoeCaseId.ASYMMETRIC_GRIP
    )

    record = build_fem_calibration_knowledge_record(
        resolved=resolved,
        seed=seed,
        geometry_identity=_geometry_identity(resolved),
        execution_generation_id=_TEST_EXECUTION_GENERATION_ID,
        accepted_run_id="accepted-p03",
        accepted_delta_temperature_c=-263.562942251128,
        measured_mean_clamp_force_n=19820.576667,
    )

    assert record.case_hash == resolved.case_hash
    assert record.resolution_hash == resolved.resolution_hash


def test_exact_reuse_requires_matching_resolution_hash() -> None:
    resolved, seed = _pilot(
        PilotDoeCaseId.ASYMMETRIC_GRIP
    )

    record = build_fem_calibration_knowledge_record(
        resolved=resolved,
        seed=seed,
        geometry_identity=_geometry_identity(resolved),
        execution_generation_id=_TEST_EXECUTION_GENERATION_ID,
        accepted_run_id="accepted-p03",
        accepted_delta_temperature_c=-263.562942251128,
        measured_mean_clamp_force_n=19820.576667,
    )

    changed_evidence = replace(
        resolved.nut_standard.thickness_evidence,
        evidence_id="TRM-DIM-M10-ALT001",
    )
    changed_nut = replace(
        resolved.nut_standard,
        thickness_evidence=changed_evidence,
    )
    changed = replace(
        resolved,
        nut_standard=changed_nut,
    )

    assert changed.case_hash == resolved.case_hash
    assert changed.resolution_hash != resolved.resolution_hash

    changed_seed = derive_analytical_thermal_preload_seed(
        changed
    )

    prediction = predict_fem_warm_start(
        resolved=changed,
        seed=changed_seed,
        geometry_identity=_geometry_identity(changed),
        execution_generation_id=_TEST_EXECUTION_GENERATION_ID,
        knowledge=(record,),
        policy=_policy(),
    )

    assert prediction.source is not FemWarmStartSource.EXACT_CASE


def test_matching_resolution_hash_remains_exact_reuse() -> None:
    resolved, seed = _pilot(
        PilotDoeCaseId.ASYMMETRIC_GRIP
    )

    record = build_fem_calibration_knowledge_record(
        resolved=resolved,
        seed=seed,
        geometry_identity=_geometry_identity(resolved),
        execution_generation_id=_TEST_EXECUTION_GENERATION_ID,
        accepted_run_id="accepted-p03",
        accepted_delta_temperature_c=-263.562942251128,
        measured_mean_clamp_force_n=19820.576667,
    )

    prediction = predict_fem_warm_start(
        resolved=resolved,
        seed=seed,
        geometry_identity=_geometry_identity(resolved),
        execution_generation_id=_TEST_EXECUTION_GENERATION_ID,
        knowledge=(record,),
        policy=_policy(),
    )

    assert prediction.source is FemWarmStartSource.EXACT_CASE
