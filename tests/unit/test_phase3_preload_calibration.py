from pathlib import Path

import pytest

from threadrom.factory.preload_calibration import (
    PreloadCalibrationPoint,
    derive_secant_delta_temperature,
)
from threadrom.factory.preload_calibration_controller import (
    ClampForceMeasurement,
    PreloadCalibrationDisposition,
    evaluate_preload_calibration,
)
from threadrom.postprocessing.calculix_contact_statistics import (
    parse_contact_statistics_records,
)


def test_phase2_secant_calibration_reproduces_certified_delta_t():
    first = PreloadCalibrationPoint(
        delta_temperature_c=-145.0,
        measured_force_n=12146.47,
    )
    second = PreloadCalibrationPoint(
        delta_temperature_c=-250.0,
        measured_force_n=20537.463333333333,
    )

    result = derive_secant_delta_temperature(
        target_force_n=20000.0,
        first=first,
        second=second,
    )

    assert result.predicted_delta_temperature_c == pytest.approx(
        -243.2744971,
        abs=1.0e-8,
    )


def test_phase2_run_a_requests_certified_a2_temperature():
    measurement = ClampForceMeasurement(
        under_head_force_n=20534.080,
        nut_bearing_force_n=20540.110,
        member_interface_force_n=20538.200,
    )

    decision = evaluate_preload_calibration(
        target_force_n=20000.0,
        target_relative_tolerance=0.01,
        spread_relative_tolerance=0.005,
        measurement=measurement,
        previous_point=PreloadCalibrationPoint(
            delta_temperature_c=-145.0,
            measured_force_n=12146.47,
        ),
        current_delta_temperature_c=-250.0,
    )

    assert decision.disposition is (
        PreloadCalibrationDisposition.CONTINUE
    )
    assert decision.next_delta_temperature_c == pytest.approx(
        -243.2744971,
        abs=1.0e-8,
    )


def test_phase2_a2_measurement_is_accepted():
    measurement = ClampForceMeasurement(
        under_head_force_n=20060.270,
        nut_bearing_force_n=20066.050,
        member_interface_force_n=20064.180,
    )

    decision = evaluate_preload_calibration(
        target_force_n=20000.0,
        target_relative_tolerance=0.01,
        spread_relative_tolerance=0.005,
        measurement=measurement,
        previous_point=PreloadCalibrationPoint(
            delta_temperature_c=-250.0,
            measured_force_n=20537.463333333333,
        ),
        current_delta_temperature_c=-243.2744971,
    )

    assert decision.disposition is (
        PreloadCalibrationDisposition.ACCEPT
    )
    assert decision.measurement.mean_force_n == pytest.approx(
        20063.5,
    )
    assert decision.target_relative_error == pytest.approx(
        0.003175,
    )
    assert decision.next_delta_temperature_c is None


def test_contact_statistics_parser_reads_certified_a2_dat():
    path = Path(
        ".tmp/cp6_run_a2_corrected_20kn/"
        "trm_sim_000004_run_a2_thermal_20kn.dat"
    )

    if not path.exists():
        pytest.skip("Certified Phase-2 A2 DAT is not available.")

    records = parse_contact_statistics_records(
        path.read_text(
            encoding="utf-8",
            errors="replace",
        )
    )

    assert len(records) == 80

    expected = {
        (
            "SURF_HEAD_MEMBER_HEAD_BEARING",
            "SURF_BOLT_UNDER_HEAD_BEARING",
        ): 20060.270,
        (
            "SURF_NUT_MEMBER_NUT_BEARING",
            "SURF_NUT_LOWER_BEARING",
        ): 20066.050,
        (
            "SURF_HEAD_MEMBER_INTERFACE",
            "SURF_NUT_MEMBER_INTERFACE",
        ): 20064.180,
    }

    for pair, expected_force in expected.items():
        matching = [
            record
            for record in records
            if (
                record.slave_surface,
                record.master_surface,
            ) == pair
        ]

        assert matching
        assert abs(matching[-1].normal_force_n) == pytest.approx(
            expected_force,
            abs=1.0e-3,
        )
