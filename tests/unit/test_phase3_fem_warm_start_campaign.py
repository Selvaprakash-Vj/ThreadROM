"""CP8 governed FEM warm-start campaign integration."""

from __future__ import annotations

import pytest

from threadrom.factory.preload_calibration_campaign import (
    PreloadCalibrationTrialSource,
    derive_fem_warm_start_preload_calibration_trial,
)


def test_fem_warm_start_builds_governed_first_trial() -> None:
    trial = (
        derive_fem_warm_start_preload_calibration_trial(
            predicted_delta_temperature_c=-189.840955076120,
            case_run_id="trm_fem_example",
        )
    )

    assert trial.trial_index == 1
    assert trial.run_id == "trm_fem_example_cal_01"

    assert trial.delta_temperature_c == pytest.approx(
        -189.840955076120
    )

    assert (
        trial.source
        is PreloadCalibrationTrialSource.FEM_WARM_START
    )


@pytest.mark.parametrize(
    "value",
    (
        0.0,
        10.0,
        float("inf"),
        float("-inf"),
        float("nan"),
    ),
)
def test_fem_warm_start_rejects_invalid_temperature(
    value: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="thermal contraction",
    ):
        derive_fem_warm_start_preload_calibration_trial(
            predicted_delta_temperature_c=value,
            case_run_id="trm_fem_example",
        )


def test_fem_warm_start_requires_case_run_identity() -> None:
    with pytest.raises(
        ValueError,
        match="non-blank case run ID",
    ):
        derive_fem_warm_start_preload_calibration_trial(
            predicted_delta_temperature_c=-200.0,
            case_run_id="   ",
        )
