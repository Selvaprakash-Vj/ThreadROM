"""Governed Phase-3 Verification & Validation matrix tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from threadrom.factory.phase3_verification_validation import (
    load_phase3_verification_validation_matrix,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _matrix():
    return load_phase3_verification_validation_matrix(
        PROJECT_ROOT
        / "config"
        / "phase3_verification_validation.toml"
    )


def test_phase3_vv_matrix_has_complete_24_check_registry() -> None:
    matrix = _matrix()

    assert matrix.matrix_id == (
        "phase3_complete_joint_vv_v1"
    )

    assert matrix.phase == 3
    assert matrix.checkpoint == "CP8"
    assert matrix.status == "governed"

    assert tuple(
        check.check_id
        for check in matrix.checks
    ) == tuple(
        f"VV-{index:02d}"
        for index in range(
            1,
            25,
        )
    )


def test_phase3_vv_matrix_uses_governed_external_references() -> None:
    matrix = _matrix()

    assert {
        reference.reference_id
        for reference in matrix.references
    } == {
        "ISO-68-1-2023",
        "ISO-724-2023",
        "ISO-965-1-2026",
        "ISO-898-1-2013",
        "VDI-2230-1-2015",
        "NASA-RP-1228",
        "NASA-TM-106943",
    }


def test_core_fem_acceptance_tolerances_are_predeclared() -> None:
    matrix = _matrix()

    assert (
        matrix.check("VV-11")
        .thresholds["target_relative"]
        == pytest.approx(0.01)
    )

    assert (
        matrix.check("VV-12")
        .thresholds["spread_relative"]
        == pytest.approx(0.005)
    )

    for check_id in (
        "VV-07",
        "VV-08",
        "VV-09",
        "VV-10",
    ):
        assert (
            matrix.check(check_id)
            .thresholds["relative"]
            == pytest.approx(0.10)
        )


def test_mesh_and_cross_solver_thresholds_are_predeclared() -> None:
    matrix = _matrix()

    mesh = matrix.check("VV-06")

    assert (
        mesh.thresholds["global_relative"]
        == pytest.approx(0.02)
    )

    assert (
        mesh.thresholds["bolt_stress_relative"]
        == pytest.approx(0.03)
    )

    assert (
        mesh.thresholds["thread_force_relative"]
        == pytest.approx(0.03)
    )

    cross_solver = matrix.check(
        "VV-19"
    )

    assert (
        cross_solver
        .thresholds["global_relative"]
        == pytest.approx(0.05)
    )

    assert (
        cross_solver
        .thresholds["thread_load_relative"]
        == pytest.approx(0.10)
    )


def test_reuse_certificate_and_negative_gate_are_separate() -> None:
    matrix = _matrix()

    reuse = matrix.check("VV-17")
    negative = matrix.check("VV-18")

    assert reuse.criterion_type == "hard"
    assert negative.criterion_type == "hard"

    assert "fresh solve" in reuse.criterion
    assert "invalidate reuse" in negative.criterion


def test_dataset_sufficiency_fails_closed_until_threshold_policy_frozen() -> None:
    matrix = _matrix()

    check = matrix.check("VV-23")

    assert check.criterion_type == "hard"

    assert check.gate_state == (
        "BLOCKED_UNTIL_THRESHOLD_POLICY_FROZEN"
    )

    assert (
        "before the first diagnostic surrogate fit"
        in check.criterion
    )

    assert (
        "may not be relaxed"
        in check.criterion
    )


def test_experimental_validation_is_explicitly_not_claimed() -> None:
    matrix = _matrix()

    check = matrix.check("VV-24")

    assert (
        check.criterion_type
        == "limitation"
    )

    assert (
        "no exact physical-test validation"
        in check.criterion
    )


def test_current_p01_p02_matrix_scope_contains_required_checks() -> None:
    matrix = _matrix()

    applicable = {
        check.check_id
        for check in matrix.checks
        if check.current_run_applicable
    }

    assert {
        "VV-01",
        "VV-02",
        "VV-03",
        "VV-04",
        "VV-05",
        "VV-07",
        "VV-08",
        "VV-09",
        "VV-10",
        "VV-11",
        "VV-12",
        "VV-13",
        "VV-14",
        "VV-15",
        "VV-16",
        "VV-17",
    }.issubset(
        applicable
    )


def test_mesh_convergence_has_mandatory_phase3_sentinels() -> None:
    matrix = _matrix()

    check = matrix.check("VV-06")

    assert check.execution_phase == 3
    assert check.execution_checkpoint == "CP8"

    assert check.required_case_ids == (
        "P02_PRELOAD_HIGH",
        "P04_RADIAL_GEOMETRY",
    )

    assert (
        "mandatory Phase-3 mesh-convergence sentinels"
        in check.criterion
    )


def test_cross_solver_validation_is_explicitly_scheduled() -> None:
    matrix = _matrix()

    check = matrix.check("VV-19")

    assert check.execution_phase == 5

    assert (
        check.execution_checkpoint
        == "validation_generalisation"
    )

    assert check.required_case_ids == (
        "P00_BASELINE_CONTROL",
        "P03_ASYMMETRIC_GRIP",
    )

    assert check.required_case_roles == (
        "PRODUCTION_DOMAIN_BOUNDARY_SENTINEL",
    )

    assert (
        "Before Phase-5 validation/generalisation is closed"
        in check.criterion
    )


def test_required_phase3_case_ids_resolve_to_registered_cases() -> None:
    from threadrom.factory.pilot_doe import (
        build_phase3_cp7_pilot_doe,
    )

    matrix = _matrix()

    registered = {
        item.case_id.value
        for item in build_phase3_cp7_pilot_doe().cases
    }

    required = {
        case_id
        for check in matrix.checks
        for case_id in check.required_case_ids
    }

    assert required <= registered

    assert (
        "P04_RADIAL_GEOMETRY"
        in registered
    )


def test_loader_rejects_misspelled_required_case_id(
    tmp_path: Path,
) -> None:
    source = (
        PROJECT_ROOT
        / "config"
        / "phase3_verification_validation.toml"
    ).read_text(
        encoding="utf-8"
    )

    corrupted = source.replace(
        'required_case_ids = ["P02_PRELOAD_HIGH", "P04_RADIAL_GEOMETRY"]',
        'required_case_ids = ["P02_PRELOAD_HIGH", "P04_RADIAL_GEOM"]',
        1,
    )

    assert corrupted != source

    path = (
        tmp_path
        / "phase3_verification_validation.toml"
    )

    path.write_text(
        corrupted,
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="unregistered required case IDs",
    ):
        load_phase3_verification_validation_matrix(
            path
        )


def test_future_sentinel_role_is_not_misrepresented_as_case_id() -> None:
    matrix = _matrix()

    check = matrix.check("VV-19")

    assert (
        "PRODUCTION_DOMAIN_BOUNDARY_SENTINEL"
        not in check.required_case_ids
    )

    assert check.required_case_roles == (
        "PRODUCTION_DOMAIN_BOUNDARY_SENTINEL",
    )
