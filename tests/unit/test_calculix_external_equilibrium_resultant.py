from __future__ import annotations

from threadrom.postprocessing.calculix_external_equilibrium import (
    validate_external_equilibrium_resultant,
)


def _progress():
    return {
        "accepted_increments": [
            {
                "step": 1,
                "increment": 1,
                "total_time": 0.5,
            },
            {
                "step": 2,
                "increment": 1,
                "total_time": 1.0,
            },
        ]
    }


def test_complete_translational_resultant_passes():
    payload = {
        "records": [
            {
                "set_name": "A",
                "time": 0.5,
                "force_components_n": [
                    10.0,
                    -4.0,
                    2.0,
                ],
            },
            {
                "set_name": "B",
                "time": 0.5,
                "force_components_n": [
                    -9.99995,
                    4.00001,
                    -2.00002,
                ],
            },
            {
                "set_name": "A",
                "time": 1.0,
                "force_components_n": [
                    72.88916,
                    -14.04797,
                    0.0,
                ],
            },
            {
                "set_name": "B",
                "time": 1.0,
                "force_components_n": [
                    -72.88911,
                    14.047974,
                    -0.000039,
                ],
            },
        ]
    }

    result = (
        validate_external_equilibrium_resultant(
            _progress(),
            payload,
            support_set_names=(
                "A",
                "B",
            ),
        )
    )

    assert result["overall_status"] == "pass"
    assert result["passed_count"] == 2
    assert result["failed_count"] == 0
    assert result["pending_count"] == 0

    latest = result["validations"][-1]

    assert latest["status"] == "pass"

    assert (
        latest[
            "maximum_absolute_component_n"
        ]
        <= 1.0e-3
    )


def test_incomplete_resultant_is_pending():
    payload = {
        "records": [
            {
                "set_name": "A",
                "time": 0.5,
                "force_components_n": [
                    1.0,
                    0.0,
                    0.0,
                ],
            },
            {
                "set_name": "B",
                "time": 0.5,
                "force_components_n": [
                    -1.0,
                    0.0,
                    0.0,
                ],
            },
            {
                "set_name": "A",
                "time": 1.0,
                "force_components_n": [
                    1.0,
                    0.0,
                    0.0,
                ],
            },
        ]
    }

    result = (
        validate_external_equilibrium_resultant(
            _progress(),
            payload,
            support_set_names=(
                "A",
                "B",
            ),
        )
    )

    assert result["overall_status"] == "pending"
    assert result["passed_count"] == 1
    assert result["pending_count"] == 1


def test_true_global_imbalance_fails():
    payload = {
        "records": [
            {
                "set_name": "A",
                "time": 0.5,
                "force_components_n": [
                    1.0,
                    0.0,
                    0.0,
                ],
            },
            {
                "set_name": "B",
                "time": 0.5,
                "force_components_n": [
                    -0.5,
                    0.0,
                    0.0,
                ],
            },
            {
                "set_name": "A",
                "time": 1.0,
                "force_components_n": [
                    2.0,
                    0.0,
                    0.0,
                ],
            },
            {
                "set_name": "B",
                "time": 1.0,
                "force_components_n": [
                    -1.0,
                    0.0,
                    0.0,
                ],
            },
        ]
    }

    result = (
        validate_external_equilibrium_resultant(
            _progress(),
            payload,
            support_set_names=(
                "A",
                "B",
            ),
        )
    )

    assert result["overall_status"] == "fail"
    assert result["failed_count"] == 2
