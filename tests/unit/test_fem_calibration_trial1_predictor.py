"""Trial-1 observation predictor V1 tests."""

from __future__ import annotations

from pathlib import Path

from threadrom.factory.fem_calibration_observation_store import (
    calibration_observations,
    load_calibration_observation_store,
)
from threadrom.factory.fem_calibration_trial1_predictor import (
    Trial1PredictionSource,
    load_trial1_observation_predictor_policy,
    predict_trial1_from_observations,
)


ROOT = Path(__file__).resolve().parents[2]

STORE = (
    ROOT
    / "docs"
    / "phase3_calibration_knowledge"
    / "observations_v1.json"
)

POLICY = (
    ROOT
    / "config"
    / "fem_calibration_trial1_predictor.toml"
)


def _observations():
    return calibration_observations(
        load_calibration_observation_store(
            STORE
        )
    )


def _target(case_id):
    rows = tuple(
        item
        for item in _observations()
        if item.case_id == case_id
    )

    assert len(rows) == 2

    return sorted(
        rows,
        key=lambda item: item.trial_index,
    )[0]


def test_w02_m10_aluminium_interpolates_from_neighbor_sizes() -> None:
    target = _target(
        "TRM-DDOE-D-M10x1_5__member_aluminium_en_aw_6082_t6-02"
    )

    expected_neighbor_ids = {
        "TRM-DDOE-D-M8x1_25__member_aluminium_en_aw_6082_t6-02",
        "TRM-DDOE-D-M12x1_75__member_aluminium_en_aw_6082_t6-02",
    }

    training = tuple(
        item
        for item in _observations()
        if item.case_id in expected_neighbor_ids
    )

    assert {
        item.case_id
        for item in training
    } == expected_neighbor_ids

    prediction = predict_trial1_from_observations(
        target_case_hash=target.case_hash,
        target_resolution_hash=target.resolution_hash,
        target_feature=target.feature,
        analytical_delta_temperature_c=(
            target.analytical_delta_temperature_c
        ),
        observations=training,
        policy=(
            load_trial1_observation_predictor_policy(
                POLICY
            )
        ),
    )

    assert (
        prediction.source
        is Trial1PredictionSource.OBSERVATION_NEIGHBORS
    )

    assert prediction.reused_case_count == 2

    assert set(
        prediction.neighbor_case_ids
    ) == expected_neighbor_ids


def test_execution_generation_boundary_blocks_incompatible_neighbors() -> None:
    target = _target(
        "TRM-DDOE-D-M12x1_75__steel_member-02"
    )

    training = tuple(
        item
        for item in _observations()
        if (
            item.case_hash
            != target.case_hash
            and item.execution_generation_id
            != target.execution_generation_id
        )
    )

    assert training

    assert all(
        item.execution_generation_id
        != target.execution_generation_id
        for item in training
    )

    prediction = predict_trial1_from_observations(
        target_case_hash=target.case_hash,
        target_resolution_hash=target.resolution_hash,
        target_feature=target.feature,
        analytical_delta_temperature_c=(
            target.analytical_delta_temperature_c
        ),
        observations=training,
        policy=(
            load_trial1_observation_predictor_policy(
                POLICY
            )
        ),
    )

    assert (
        prediction.source
        is Trial1PredictionSource.ANALYTICAL_FALLBACK
    )


def test_prediction_is_always_thermal_contraction() -> None:
    target = _target(
        "TRM-DDOE-D-M10x1_5__member_aluminium_en_aw_6082_t6-02"
    )

    prediction = predict_trial1_from_observations(
        target_case_hash="f" * 64,
        target_resolution_hash="e" * 64,
        target_feature=target.feature,
        analytical_delta_temperature_c=(
            target.analytical_delta_temperature_c
        ),
        observations=_observations(),
        policy=(
            load_trial1_observation_predictor_policy(
                POLICY
            )
        ),
    )

    assert (
        prediction.predicted_delta_temperature_c
        < 0.0
    )

    assert prediction.correction_factor > 0.0