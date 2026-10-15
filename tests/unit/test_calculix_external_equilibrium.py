"""Tests for preload-only external equilibrium."""

from __future__ import annotations

import pytest

from threadrom.postprocessing.calculix_external_equilibrium import (
    validate_external_equilibrium,
)


def _progress() -> dict[str, object]:
    return {
        "accepted_increments": [
            {
                "step": 1,
                "increment": 1,
                "step_time": 0.05,
            },
            {
                "step": 1,
                "increment": 2,
                "step_time": 0.10,
            },
        ]
    }


def test_external_equilibrium_passes() -> None:
    total_force = {
        "records": [
            {
                "step": None,
                "increment": 1,
                "set_name": "SUPPORT",
                "time": 0.05,
                "force_components_n": [
                    1.0e-8,
                    -2.0e-8,
                    3.0e-8,
                ],
            },
            {
                "step": None,
                "increment": 2,
                "set_name": "SUPPORT",
                "time": 0.10,
                "force_components_n": [
                    -1.0e-7,
                    2.0e-7,
                    -3.0e-7,
                ],
            },
        ]
    }

    payload = validate_external_equilibrium(
        _progress(),
        total_force,
        support_set_name="SUPPORT",
        force_absolute_tolerance_n=1.0e-3,
    )

    assert payload["overall_status"] == "pass"
    assert payload["passed_count"] == 2
    assert payload["failed_count"] == 0
    assert payload["pending_count"] == 0


def test_external_equilibrium_pending_record() -> None:
    total_force = {
        "records": [
            {
                "step": None,
                "increment": 1,
                "set_name": "SUPPORT",
                "time": 0.05,
                "force_components_n": [
                    1.0e-8,
                    2.0e-8,
                    3.0e-8,
                ],
            }
        ]
    }

    payload = validate_external_equilibrium(
        _progress(),
        total_force,
        support_set_name="SUPPORT",
    )

    assert payload["overall_status"] == "pending"
    assert payload["passed_count"] == 1
    assert payload["pending_count"] == 1


def test_external_equilibrium_fails_large_reaction() -> None:
    total_force = {
        "records": [
            {
                "step": None,
                "increment": 1,
                "set_name": "SUPPORT",
                "time": 0.05,
                "force_components_n": [
                    0.0,
                    0.0,
                    0.25,
                ],
            },
            {
                "step": None,
                "increment": 2,
                "set_name": "SUPPORT",
                "time": 0.10,
                "force_components_n": [
                    0.0,
                    0.0,
                    0.0,
                ],
            },
        ]
    }

    payload = validate_external_equilibrium(
        _progress(),
        total_force,
        support_set_name="SUPPORT",
        force_absolute_tolerance_n=0.1,
    )

    assert payload["overall_status"] == "fail"
    assert payload["failed_count"] == 1

    validations = payload["validations"]

    assert isinstance(validations, list)

    assert validations[0]["maximum_absolute_component_n"] == pytest.approx(0.25)


def test_multistep_external_equilibrium_uses_total_time() -> None:
    progress = {
        "accepted_increments": [
            {
                "step": 1,
                "increment": 1,
                "step_time": 1.0,
                "total_time": 1.0,
            },
            {
                "step": 2,
                "increment": 1,
                "step_time": 1.0,
                "total_time": 2.0,
            },
            {
                "step": 3,
                "increment": 1,
                "step_time": 1.0,
                "total_time": 3.0,
            },
        ]
    }

    total_force = {
        "records": [
            {
                "step": None,
                "increment": 1,
                "set_name": "SUPPORT",
                "time": 1.0,
                "force_components_n": [0.0, 0.0, 0.0],
            },
            {
                "step": None,
                "increment": 1,
                "set_name": "SUPPORT",
                "time": 2.0,
                "force_components_n": [0.0, 0.0, 0.0],
            },
            {
                "step": None,
                "increment": 1,
                "set_name": "SUPPORT",
                "time": 3.0,
                "force_components_n": [0.0, 0.0, 0.0],
            },
        ]
    }

    payload = validate_external_equilibrium(
        progress,
        total_force,
        support_set_name="SUPPORT",
    )

    assert payload["overall_status"] == "pass"
    assert payload["passed_count"] == 3
    assert payload["failed_count"] == 0
    assert payload["pending_count"] == 0



def _translational_progress():
    return {
        "accepted_increments": [
            {
                "step": 1,
                "increment": 1,
                "total_time": 1.0,
            },
        ],
    }


def _translational_record(
    set_name,
    components,
):
    return {
        "step": None,
        "increment": 1,
        "set_name": set_name,
        "time": 1.0,
        "force_components_n": list(
            components
        ),
    }


def test_translational_constraint_equilibrium_sums_explicit_sets():
    from threadrom.postprocessing.calculix_external_equilibrium import (
        validate_translational_constraint_equilibrium,
    )

    payload = (
        validate_translational_constraint_equilibrium(
            _translational_progress(),
            {
                "records": [
                    _translational_record(
                        "SUPPORT",
                        (100.0, 25.0, 0.0),
                    ),
                    _translational_record(
                        "GUIDANCE",
                        (-100.0, -25.0, 0.0),
                    ),
                    _translational_record(
                        "ROTATION_REFERENCE",
                        (5000.0, 0.0, 0.0),
                    ),
                ],
            },
            force_set_names=(
                "SUPPORT",
                "GUIDANCE",
            ),
        )
    )

    assert payload["overall_status"] == "pass"
    assert payload["passed_count"] == 1
    assert payload["failed_count"] == 0
    assert payload["pending_count"] == 0

    validation = payload["validations"][0]

    assert validation["resultant_force_n"] == 0.0
    assert validation[
        "summed_force_components_n"
    ] == [0.0, 0.0, 0.0]

    assert (
        payload["requested_force_record_count"]
        == 2
    )


def test_translational_constraint_equilibrium_pending_when_set_missing():
    from threadrom.postprocessing.calculix_external_equilibrium import (
        validate_translational_constraint_equilibrium,
    )

    payload = (
        validate_translational_constraint_equilibrium(
            _translational_progress(),
            {
                "records": [
                    _translational_record(
                        "SUPPORT",
                        (10.0, 0.0, 0.0),
                    ),
                ],
            },
            force_set_names=(
                "SUPPORT",
                "GUIDANCE",
            ),
        )
    )

    assert payload["overall_status"] == "pending"
    assert payload["pending_count"] == 1
    assert payload["validations"][0][
        "missing_force_set_names"
    ] == ["GUIDANCE"]


def test_translational_constraint_equilibrium_fails_nonzero_sum():
    from threadrom.postprocessing.calculix_external_equilibrium import (
        validate_translational_constraint_equilibrium,
    )

    payload = (
        validate_translational_constraint_equilibrium(
            _translational_progress(),
            {
                "records": [
                    _translational_record(
                        "SUPPORT",
                        (1.0, 0.0, 0.0),
                    ),
                    _translational_record(
                        "GUIDANCE",
                        (-0.5, 0.0, 0.0),
                    ),
                ],
            },
            force_set_names=(
                "SUPPORT",
                "GUIDANCE",
            ),
            force_absolute_tolerance_n=0.1,
        )
    )

    assert payload["overall_status"] == "fail"
    assert payload["failed_count"] == 1

    validation = payload["validations"][0]

    assert (
        validation["resultant_force_n"]
        == 0.5
    )


def test_translational_constraint_equilibrium_rejects_duplicate_sets():
    import pytest

    from threadrom.postprocessing.calculix_external_equilibrium import (
        validate_translational_constraint_equilibrium,
    )

    with pytest.raises(
        ValueError,
        match="must be unique",
    ):
        validate_translational_constraint_equilibrium(
            _translational_progress(),
            {"records": []},
            force_set_names=(
                "SUPPORT",
                "support",
            ),
        )
