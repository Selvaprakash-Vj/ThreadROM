"""Tests for automatic Phase-3 preload calibration campaign."""

from __future__ import annotations

import pytest

from threadrom.factory.preload_calibration_campaign import (
    PreloadCalibrationCampaignPolicy,
    PreloadCalibrationTrialSource,
    derive_initial_preload_calibration_trial,
    evaluate_preload_calibration_trial,
)
from threadrom.factory.preload_calibration_controller import (
    ClampForceMeasurement,
)
from threadrom.factory.preload_calibration_seed import (
    ThermalPreloadCalibrationSeed,
)


def _seed() -> ThermalPreloadCalibrationSeed:
    return ThermalPreloadCalibrationSeed(
        target_force_n=20_000.0,
        bolt_compliance_mm_per_n=1.0e-6,
        member_compliance_mm_per_n=5.0e-7,
        total_compliance_mm_per_n=1.5e-6,
        effective_bolt_length_mm=30.0,
        expansion_coefficient_per_c=1.2e-5,
        predicted_delta_temperature_c=-83.33333333333333,
    )


def _measurement(
    mean_force_n: float,
    *,
    spread_n: float = 6.0,
) -> ClampForceMeasurement:
    half = spread_n / 2.0

    return ClampForceMeasurement(
        under_head_force_n=mean_force_n - half,
        nut_bearing_force_n=mean_force_n,
        member_interface_force_n=mean_force_n + half,
    )


def test_initial_trial_comes_from_analytical_seed() -> None:
    trial = derive_initial_preload_calibration_trial(
        seed=_seed(),
        case_run_id="trm_fem_abc123",
    )

    assert trial.trial_index == 1
    assert trial.run_id == "trm_fem_abc123_cal_01"
    assert trial.delta_temperature_c == pytest.approx(
        _seed().predicted_delta_temperature_c
    )
    assert (
        trial.source
        is PreloadCalibrationTrialSource.ANALYTICAL_SEED
    )


def test_first_trial_can_be_accepted_without_second_solve() -> None:
    first = derive_initial_preload_calibration_trial(
        seed=_seed(),
        case_run_id="trm_fem_abc123",
    )

    result = evaluate_preload_calibration_trial(
        case_run_id="trm_fem_abc123",
        target_force_n=20_000.0,
        target_relative_tolerance=0.01,
        spread_relative_tolerance=0.005,
        current_trial=first,
        measurement=_measurement(20_050.0),
    )

    assert result.accepted
    assert result.next_trial is None


def test_first_failed_trial_derives_proportional_second_trial() -> None:
    first = derive_initial_preload_calibration_trial(
        seed=_seed(),
        case_run_id="trm_fem_abc123",
    )

    result = evaluate_preload_calibration_trial(
        case_run_id="trm_fem_abc123",
        target_force_n=20_000.0,
        target_relative_tolerance=0.01,
        spread_relative_tolerance=0.005,
        current_trial=first,
        measurement=_measurement(10_000.0),
    )

    assert not result.accepted
    assert result.next_trial is not None
    assert result.next_trial.trial_index == 2
    assert result.next_trial.run_id == (
        "trm_fem_abc123_cal_02"
    )
    assert result.next_trial.delta_temperature_c == pytest.approx(
        2.0 * first.delta_temperature_c
    )
    assert (
        result.next_trial.source
        is PreloadCalibrationTrialSource.PROPORTIONAL
    )


def test_near_duplicate_second_point_uses_governed_perturbation() -> None:
    first = derive_initial_preload_calibration_trial(
        seed=_seed(),
        case_run_id="trm_fem_abc123",
    )

    policy = PreloadCalibrationCampaignPolicy(
        minimum_second_trial_relative_separation=0.05,
        fallback_second_trial_scale=0.80,
    )

    result = evaluate_preload_calibration_trial(
        case_run_id="trm_fem_abc123",
        target_force_n=20_000.0,
        target_relative_tolerance=0.01,
        spread_relative_tolerance=0.0001,
        current_trial=first,
        measurement=_measurement(
            20_000.0,
            spread_n=100.0,
        ),
        policy=policy,
    )

    assert result.next_trial is not None
    assert result.next_trial.delta_temperature_c == pytest.approx(
        0.80 * first.delta_temperature_c
    )
    assert (
        result.next_trial.source
        is PreloadCalibrationTrialSource.FALLBACK_PERTURBATION
    )


def test_second_failed_trial_uses_existing_secant_controller() -> None:
    first = derive_initial_preload_calibration_trial(
        seed=_seed(),
        case_run_id="trm_fem_abc123",
    )

    first_measurement = _measurement(10_000.0)

    first_result = evaluate_preload_calibration_trial(
        case_run_id="trm_fem_abc123",
        target_force_n=20_000.0,
        target_relative_tolerance=0.01,
        spread_relative_tolerance=0.005,
        current_trial=first,
        measurement=first_measurement,
    )

    second = first_result.next_trial
    assert second is not None

    second_result = evaluate_preload_calibration_trial(
        case_run_id="trm_fem_abc123",
        target_force_n=20_000.0,
        target_relative_tolerance=0.01,
        spread_relative_tolerance=0.005,
        previous_trial=first,
        previous_measurement=first_measurement,
        current_trial=second,
        measurement=_measurement(18_000.0),
    )

    assert not second_result.accepted
    assert second_result.next_trial is not None
    assert (
        second_result.next_trial.source
        is PreloadCalibrationTrialSource.SECANT
    )
    assert second_result.next_trial.trial_index == 3
    assert second_result.next_trial.run_id == (
        "trm_fem_abc123_cal_03"
    )


def test_previous_trial_and_measurement_are_atomic_inputs() -> None:
    first = derive_initial_preload_calibration_trial(
        seed=_seed(),
        case_run_id="trm_fem_abc123",
    )

    with pytest.raises(
        ValueError,
        match="must be provided together",
    ):
        evaluate_preload_calibration_trial(
            case_run_id="trm_fem_abc123",
            target_force_n=20_000.0,
            target_relative_tolerance=0.01,
            spread_relative_tolerance=0.005,
            current_trial=first,
            measurement=_measurement(10_000.0),
            previous_trial=first,
            previous_measurement=None,
        )
