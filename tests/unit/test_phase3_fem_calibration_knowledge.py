"""CP8 FEM-informed warm-start knowledge tests."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from threadrom.case.resolver import resolve_case
from threadrom.factory.fem_calibration_knowledge import (
    FemWarmStartApplicability,
    FemWarmStartSource,
    build_fem_calibration_feature_vector,
    build_fem_calibration_knowledge_record,
    fem_calibration_feature_distance,
    load_fem_warm_start_policy,
    predict_fem_warm_start,
)
from threadrom.factory.pilot_doe import (
    PilotDoeCaseId,
    build_phase3_cp7_pilot_doe,
)
from threadrom.factory.preload_calibration_seed import (
    derive_analytical_thermal_preload_seed,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _pilot(case_id: PilotDoeCaseId):
    campaign = build_phase3_cp7_pilot_doe()

    item = next(
        item
        for item in campaign.cases
        if item.case_id is case_id
    )

    resolved = resolve_case(item.case)

    return (
        resolved,
        derive_analytical_thermal_preload_seed(
            resolved
        ),
    )


def _policy():
    return load_fem_warm_start_policy(
        PROJECT_ROOT
        / "config"
        / "fem_calibration_warm_start.toml"
    )


def test_exact_case_reuses_accepted_fem_temperature() -> None:
    resolved, seed = _pilot(
        PilotDoeCaseId.ASYMMETRIC_GRIP
    )

    record = build_fem_calibration_knowledge_record(
        resolved=resolved,
        seed=seed,
        accepted_run_id="accepted-p03",
        accepted_delta_temperature_c=-263.562942251128,
        measured_mean_clamp_force_n=19820.576667,
    )

    prediction = predict_fem_warm_start(
        resolved=resolved,
        seed=seed,
        knowledge=(record,),
        policy=_policy(),
    )

    assert (
        prediction.source
        is FemWarmStartSource.EXACT_CASE
    )

    assert (
        prediction.predicted_delta_temperature_c
        == pytest.approx(
            -263.562942251128
        )
    )

    assert prediction.nearest_distance == 0.0


def test_single_neighbor_falls_back_to_analytical() -> None:
    baseline, baseline_seed = _pilot(
        PilotDoeCaseId.BASELINE_CONTROL
    )

    baseline_record = (
        build_fem_calibration_knowledge_record(
            resolved=baseline,
            seed=baseline_seed,
            accepted_run_id="accepted-baseline",
            accepted_delta_temperature_c=-243.2744971,
            measured_mean_clamp_force_n=20063.5,
        )
    )

    low, low_seed = _pilot(
        PilotDoeCaseId.PRELOAD_LOW
    )

    prediction = predict_fem_warm_start(
        resolved=low,
        seed=low_seed,
        knowledge=(baseline_record,),
        policy=_policy(),
    )

    assert (
        prediction.source
        is FemWarmStartSource.ANALYTICAL_FALLBACK
    )

    assert (
        prediction.applicability
        is FemWarmStartApplicability.INSUFFICIENT_NEIGHBORS
    )

    assert prediction.reused_evidence_count == 0
    assert prediction.nearest_distance is not None

    assert (
        prediction.predicted_delta_temperature_c
        == pytest.approx(
            low_seed.predicted_delta_temperature_c
        )
    )



def test_asymmetric_grip_is_distinct_feature_space() -> None:
    baseline, baseline_seed = _pilot(
        PilotDoeCaseId.BASELINE_CONTROL
    )

    asymmetric, asymmetric_seed = _pilot(
        PilotDoeCaseId.ASYMMETRIC_GRIP
    )

    baseline_feature = (
        build_fem_calibration_feature_vector(
            baseline,
            baseline_seed,
        )
    )

    asymmetric_feature = (
        build_fem_calibration_feature_vector(
            asymmetric,
            asymmetric_seed,
        )
    )

    distance = fem_calibration_feature_distance(
        baseline_feature,
        asymmetric_feature,
    )

    assert distance is not None
    assert distance > 0.0

    assert (
        baseline_feature.upper_grip_fraction
        == pytest.approx(0.5)
    )

    assert (
        asymmetric_feature.upper_grip_fraction
        == pytest.approx(0.4)
    )


def test_radial_geometry_is_distinct_feature_space() -> None:
    baseline, baseline_seed = _pilot(
        PilotDoeCaseId.BASELINE_CONTROL
    )

    radial, radial_seed = _pilot(
        PilotDoeCaseId.RADIAL_GEOMETRY
    )

    distance = fem_calibration_feature_distance(
        build_fem_calibration_feature_vector(
            baseline,
            baseline_seed,
        ),
        build_fem_calibration_feature_vector(
            radial,
            radial_seed,
        ),
    )

    assert distance is not None
    assert distance > 0.0


def test_incompatible_material_family_falls_back_to_analytical() -> None:
    baseline, baseline_seed = _pilot(
        PilotDoeCaseId.BASELINE_CONTROL
    )

    record = build_fem_calibration_knowledge_record(
        resolved=baseline,
        seed=baseline_seed,
        accepted_run_id="accepted-baseline",
        accepted_delta_temperature_c=-243.2744971,
        measured_mean_clamp_force_n=20063.5,
    )

    feature = replace(
        record.feature,
        compatibility=replace(
            record.feature.compatibility,
            bolt_material_id="other-material",
        ),
    )

    incompatible_record = replace(
        record,
        case_hash="other-case",
        feature=feature,
    )

    prediction = predict_fem_warm_start(
        resolved=baseline,
        seed=baseline_seed,
        knowledge=(incompatible_record,),
        policy=_policy(),
    )

    assert (
        prediction.source
        is FemWarmStartSource.ANALYTICAL_FALLBACK
    )

    assert prediction.correction_factor == 1.0

    assert (
        prediction.predicted_delta_temperature_c
        == pytest.approx(
            baseline_seed.predicted_delta_temperature_c
        )
    )


def test_two_fem_neighbors_interpolate_correction_factor() -> None:
    baseline, baseline_seed = _pilot(
        PilotDoeCaseId.BASELINE_CONTROL
    )

    asymmetric, asymmetric_seed = _pilot(
        PilotDoeCaseId.ASYMMETRIC_GRIP
    )

    radial, radial_seed = _pilot(
        PilotDoeCaseId.RADIAL_GEOMETRY
    )

    baseline_record = (
        build_fem_calibration_knowledge_record(
            resolved=baseline,
            seed=baseline_seed,
            accepted_run_id="accepted-baseline",
            accepted_delta_temperature_c=-243.2744971,
            measured_mean_clamp_force_n=20063.5,
        )
    )

    asymmetric_record = (
        build_fem_calibration_knowledge_record(
            resolved=asymmetric,
            seed=asymmetric_seed,
            accepted_run_id="accepted-p03",
            accepted_delta_temperature_c=-263.562942251128,
            measured_mean_clamp_force_n=19820.576667,
        )
    )

    prediction = predict_fem_warm_start(
        resolved=radial,
        seed=radial_seed,
        knowledge=(
            baseline_record,
            asymmetric_record,
        ),
        policy=_policy(),
    )

    factors = (
        baseline_record.correction_factor,
        asymmetric_record.correction_factor,
    )

    assert (
        prediction.source
        is FemWarmStartSource.FEM_NEIGHBORS
    )

    assert prediction.reused_evidence_count == 2

    assert min(factors) < prediction.correction_factor
    assert prediction.correction_factor < max(factors)


def test_high_preload_extrapolation_falls_back_to_analytical() -> None:
    baseline, baseline_seed = _pilot(
        PilotDoeCaseId.BASELINE_CONTROL
    )

    asymmetric, asymmetric_seed = _pilot(
        PilotDoeCaseId.ASYMMETRIC_GRIP
    )

    high, high_seed = _pilot(
        PilotDoeCaseId.PRELOAD_HIGH
    )

    baseline_record = (
        build_fem_calibration_knowledge_record(
            resolved=baseline,
            seed=baseline_seed,
            accepted_run_id="accepted-baseline",
            accepted_delta_temperature_c=-243.2744971,
            measured_mean_clamp_force_n=20063.5,
        )
    )

    asymmetric_record = (
        build_fem_calibration_knowledge_record(
            resolved=asymmetric,
            seed=asymmetric_seed,
            accepted_run_id="accepted-p03",
            accepted_delta_temperature_c=-263.562942251128,
            measured_mean_clamp_force_n=19820.576667,
        )
    )

    prediction = predict_fem_warm_start(
        resolved=high,
        seed=high_seed,
        knowledge=(
            baseline_record,
            asymmetric_record,
        ),
        policy=_policy(),
    )

    assert (
        prediction.source
        is FemWarmStartSource.ANALYTICAL_FALLBACK
    )

    assert (
        prediction.applicability
        is FemWarmStartApplicability.PRELOAD_EXTRAPOLATION
    )

    assert prediction.reused_evidence_count == 0

    assert (
        prediction.predicted_delta_temperature_c
        == pytest.approx(
            high_seed.predicted_delta_temperature_c
        )
    )


def test_warm_start_policy_is_governed_configuration() -> None:
    policy = _policy()

    assert (
        policy.policy_id
        == "complete_joint_fem_warm_start_v1"
    )

    assert policy.maximum_neighbors == 4
    assert policy.maximum_reuse_distance > 0.0

    assert policy.minimum_neighbors_for_reuse == 2
    assert policy.require_target_preload_bracketing

    assert (
        policy.maximum_correction_factor_relative_spread
        == pytest.approx(0.20)
    )
