"""Tests for the persistent calibration-observation store."""

from __future__ import annotations

from dataclasses import replace

import pytest

from threadrom.factory.fem_calibration_knowledge import (
    FemCalibrationCompatibilityKey,
    FemCalibrationFeatureVector,
    FemGeometryRealizationIdentity,
)
from threadrom.factory.fem_calibration_observation_store import (
    FemCalibrationObservation,
    FemCalibrationObservationStoreError,
    calibration_observations,
    load_calibration_observation_store,
    new_calibration_observation_store,
    observation_from_dict,
    observation_id,
    observation_to_dict,
    persist_calibration_observation_store,
    register_calibration_observation,
)


def _feature() -> FemCalibrationFeatureVector:
    return FemCalibrationFeatureVector(
        compatibility=(
            FemCalibrationCompatibilityKey(
                bolt_standard="iso4014",
                thread_designation="M10x1.5",
                bolt_material_id="steel",
                bolt_property_class="8.8",
                nut_standard="iso4032",
                nut_material_id="steel",
                nut_property_class="8",
                handedness="right",
                starts=1,
                member_material_ids=(
                    "aluminium",
                    "aluminium",
                ),
                geometry_generation_id=(
                    "geometry-v1"
                ),
                execution_generation_id=(
                    "execution-v1"
                ),
            )
        ),
        target_preload_n=20_000.0,
        analytical_delta_temperature_abs_c=190.0,
        bolt_length_mm=60.0,
        total_grip_length_mm=30.0,
        upper_grip_fraction=0.5,
        engagement_to_pitch=5.0,
        protrusion_to_pitch=1.0,
        clearance_to_outer_diameter=1.1,
        outer_diameter_to_bolt_length=0.17,
        external_axial_to_preload=0.0,
        thread_friction=0.12,
        head_bearing_friction=0.12,
        nut_bearing_friction=0.12,
        member_interface_friction=0.15,
    )


def _observation(
    *,
    disposition: str = "continue",
) -> FemCalibrationObservation:
    return FemCalibrationObservation(
        case_id="CASE-A",
        case_hash="a" * 64,
        resolution_hash="b" * 64,
        geometry_identity=(
            FemGeometryRealizationIdentity(
                generation_id="geometry-v1",
                realization_id=(
                    "joint-geometry-1234567890abcdef"
                ),
            )
        ),
        execution_generation_id=(
            "execution-v1"
        ),
        run_id="run-cal-01",
        trial_index=1,
        trial_source="analytical_seed",
        delta_temperature_c=-190.0,
        analytical_delta_temperature_c=-190.0,
        target_force_n=20_000.0,
        under_head_force_n=11_000.0,
        nut_bearing_force_n=11_020.0,
        member_interface_force_n=10_980.0,
        extraction_time=1.0,
        thread_normal_force_n=8_000.0,
        decision_disposition=disposition,
        feature=_feature(),
        dat_relative_path=(
            "simulations/example/run-cal-01.dat"
        ),
        dat_sha256="c" * 64,
        preparation_relative_path=(
            "simulations/example/preparation.json"
        ),
        preparation_sha256="d" * 64,
    )


def test_calibration_miss_is_first_class_reusable_observation() -> None:
    observation = _observation(
        disposition="continue"
    )

    assert observation.reusable_for_prediction

    assert observation.target_relative_error == pytest.approx(
        -0.45
    )

    assert (
        observation.proportional_target_delta_temperature_c
        == pytest.approx(
            -345.45454545454544
        )
    )


def test_accepted_observation_is_also_reusable() -> None:
    observation = _observation(
        disposition="accept"
    )

    assert observation.reusable_for_prediction


def test_registration_is_duplicate_safe() -> None:
    store = (
        new_calibration_observation_store()
    )

    observation = _observation()

    first_id, first = (
        register_calibration_observation(
            store,
            observation,
        )
    )

    second_id, second = (
        register_calibration_observation(
            store,
            observation,
        )
    )

    assert first_id == second_id
    assert first == "REGISTERED"
    assert second == "REUSED"

    assert len(
        store[
            "observations"
        ]
    ) == 1


def test_same_governed_run_with_changed_evidence_fails_closed() -> None:
    store = (
        new_calibration_observation_store()
    )

    original = _observation()

    register_calibration_observation(
        store,
        original,
    )

    changed = replace(
        original,
        under_head_force_n=12_000.0,
    )

    assert (
        observation_id(
            changed
        )
        == observation_id(
            original
        )
    )

    with pytest.raises(
        FemCalibrationObservationStoreError,
        match="conflicting evidence",
    ):
        register_calibration_observation(
            store,
            changed,
        )


def test_observation_round_trip_preserves_typed_feature() -> None:
    observation = _observation()

    replay = observation_from_dict(
        observation_to_dict(
            observation
        )
    )

    assert replay == observation
    assert (
        replay.feature.compatibility.member_material_ids
        == (
            "aluminium",
            "aluminium",
        )
    )


def test_persistent_store_round_trip_is_deterministic(
    tmp_path,
) -> None:
    store = (
        new_calibration_observation_store()
    )

    observation = _observation()

    register_calibration_observation(
        store,
        observation,
    )

    path = (
        tmp_path
        / "calibration_observations.json"
    )

    persist_calibration_observation_store(
        path,
        store,
    )

    first = path.read_bytes()

    loaded = (
        load_calibration_observation_store(
            path
        )
    )

    persist_calibration_observation_store(
        path,
        loaded,
    )

    assert path.read_bytes() == first

    assert (
        calibration_observations(
            loaded
        )
        == (
            observation,
        )
    )


def test_zero_byte_or_unsolved_evidence_cannot_be_smuggled_as_zero_force() -> None:
    invalid = replace(
        _observation(),
        under_head_force_n=0.0,
    )

    store = (
        new_calibration_observation_store()
    )

    with pytest.raises(
        FemCalibrationObservationStoreError,
        match="under_head_force_n",
    ):
        register_calibration_observation(
            store,
            invalid,
        )