"""Tests for automatic Phase-3 preload calibration campaign."""

from __future__ import annotations

import pytest

from threadrom.factory.preload_calibration_campaign import (
    PreloadCalibrationCampaignPolicy,
    PreloadCalibrationTrialSource,
    derive_initial_preload_calibration_trial,
    evaluate_preload_calibration_trial,
)
from threadrom.factory.preload_calibration_campaign import PreloadCalibrationTrial

from threadrom.factory.preload_calibration_controller import (
    ClampForceMeasurement,
    PreloadCalibrationDisposition,
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


def test_small_underload_miss_uses_proportional_correction() -> None:
    first = PreloadCalibrationTrial(
        trial_index=1,
        run_id="trm_fem_p01_cal_01",
        delta_temperature_c=-189.8409550761197,
        source=PreloadCalibrationTrialSource.FEM_WARM_START,
    )

    result = evaluate_preload_calibration_trial(
        case_run_id="trm_fem_p01",
        target_force_n=15_000.0,
        target_relative_tolerance=0.01,
        spread_relative_tolerance=0.005,
        current_trial=first,
        measurement=_measurement(14_802.58),
    )

    assert result.next_trial is not None
    assert (
        result.next_trial.source
        is PreloadCalibrationTrialSource.PROPORTIONAL
    )
    assert result.next_trial.delta_temperature_c == pytest.approx(
        first.delta_temperature_c
        * 15_000.0
        / 14_802.58
    )


def test_larger_underload_miss_uses_proportional_correction() -> None:
    first = PreloadCalibrationTrial(
        trial_index=1,
        run_id="trm_fem_p02_cal_01",
        delta_temperature_c=-316.1671871266993,
        source=PreloadCalibrationTrialSource.FEM_WARM_START,
    )

    result = evaluate_preload_calibration_trial(
        case_run_id="trm_fem_p02",
        target_force_n=25_000.0,
        target_relative_tolerance=0.01,
        spread_relative_tolerance=0.005,
        current_trial=first,
        measurement=_measurement(24_095.963333333333),
    )

    assert result.next_trial is not None
    assert (
        result.next_trial.source
        is PreloadCalibrationTrialSource.PROPORTIONAL
    )
    assert result.next_trial.delta_temperature_c == pytest.approx(
        first.delta_temperature_c
        * 25_000.0
        / 24_095.963333333333
    )


def test_force_inside_tolerance_with_spread_failure_uses_perturbation() -> None:
    first = derive_initial_preload_calibration_trial(
        seed=_seed(),
        case_run_id="trm_fem_inside_tolerance",
    )

    result = evaluate_preload_calibration_trial(
        case_run_id="trm_fem_inside_tolerance",
        target_force_n=20_000.0,
        target_relative_tolerance=0.01,
        spread_relative_tolerance=0.0001,
        current_trial=first,
        measurement=_measurement(
            19_900.0,
            spread_n=100.0,
        ),
    )

    assert result.next_trial is not None
    assert (
        result.next_trial.source
        is PreloadCalibrationTrialSource.FALLBACK_PERTURBATION
    )
    assert result.next_trial.delta_temperature_c == pytest.approx(
        0.80 * first.delta_temperature_c
    )

def test_p02_reversed_response_terminates_campaign_without_trial_four() -> None:
    """Preserve the governed P02 non-monotonic calibration boundary."""

    second = PreloadCalibrationTrial(
        trial_index=2,
        run_id="trm_fem_p02_cal_02",
        delta_temperature_c=-328.029204262325,
        source=PreloadCalibrationTrialSource.PROPORTIONAL,
    )

    third = PreloadCalibrationTrial(
        trial_index=3,
        run_id="trm_fem_p02_cal_03",
        delta_temperature_c=-333.844390132161,
        source=PreloadCalibrationTrialSource.SECANT,
    )

    result = evaluate_preload_calibration_trial(
        case_run_id="trm_fem_p02",
        target_force_n=25_000.0,
        target_relative_tolerance=0.01,
        spread_relative_tolerance=0.005,
        previous_trial=second,
        previous_measurement=_measurement(
            24_702.603333333333,
            spread_n=9.27,
        ),
        current_trial=third,
        measurement=_measurement(
            23_839.306666666667,
            spread_n=9.63,
        ),
    )

    assert not result.accepted

    assert (
        result.decision.disposition
        is PreloadCalibrationDisposition.NON_MONOTONIC_RESPONSE
    )

    assert result.decision.next_delta_temperature_c is None
    assert result.next_trial is None
