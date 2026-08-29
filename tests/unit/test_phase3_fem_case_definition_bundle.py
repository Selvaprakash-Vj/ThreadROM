"""Tests for generic Phase-3 FEM solver-definition bundle."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from threadrom.case.reference_cases import (
    phase2_certification_case,
)
from threadrom.case.resolver import resolve_case
from threadrom.factory.fem_case_definition_bundle import (
    build_accepted_complete_joint_preload_definition,
    build_generic_fem_definition_bundle,
)
from threadrom.factory.fem_profile import (
    PHASE2_CERTIFIED_FEM_PROFILE,
)
from threadrom.factory.preload_calibration_campaign import (
    derive_initial_preload_calibration_trial,
    evaluate_preload_calibration_trial,
)
from threadrom.factory.preload_calibration_controller import (
    ClampForceMeasurement,
)
from threadrom.solver.complete_joint_boundary_regions import (
    load_complete_joint_boundary_region_definition,
)
from threadrom.solver.complete_joint_calculix_transfer import (
    load_complete_joint_calculix_transfer_definition,
)
from threadrom.solver.complete_joint_contact import (
    load_complete_joint_contact_definition,
)
from threadrom.solver.complete_joint_preload import (
    load_complete_joint_preload_definition,
)
from threadrom.solver.complete_joint_thermal_preload import (
    derive_thermal_preload_state,
)


def _templates():
    transfer = (
        load_complete_joint_calculix_transfer_definition(
            Path(
                "config/"
                "complete_joint_calculix_transfer.toml"
            )
        )
    )

    contact = (
        load_complete_joint_contact_definition(
            Path(
                "config/"
                "complete_joint_contact.toml"
            )
        )
    )

    boundary = (
        load_complete_joint_boundary_region_definition(
            Path(
                "config/"
                "complete_joint_boundary_regions.toml"
            )
        )
    )

    return transfer, contact, boundary


def _bundle():
    transfer, contact, boundary = _templates()

    resolved = resolve_case(
        phase2_certification_case()
    )

    return build_generic_fem_definition_bundle(
        resolved,
        mesh_id="mesh-case-001",
        geometry_id="geometry-case-001",
        classification_id="classification-case-001",
        source_mesh_name="case-001.msh",
        transfer_template=transfer,
        contact_template=contact,
        boundary_template=boundary,
    )


def test_bundle_uses_case_identity_not_certification_run_identity() -> None:
    bundle = _bundle()

    oracle = PHASE2_CERTIFIED_FEM_PROFILE.oracle

    assert (
        bundle.preparation.identity.run_id
        != oracle.run_id
    )

    assert (
        bundle.transfer.simulation_id
        == bundle.preparation.identity.run_id
    )

    assert (
        bundle.transfer.job_name
        == bundle.preparation.identity.job_name
    )

    assert bundle.transfer.mesh_id == "mesh-case-001"
    assert (
        bundle.transfer.geometry_id
        == "geometry-case-001"
    )
    assert (
        bundle.transfer.classification_id
        == "classification-case-001"
    )

    assert (
        bundle.transfer.source_mesh_name
        == "case-001.msh"
    )


def test_bundle_uses_reusable_backend_policy_without_oracle_scalars() -> None:
    bundle = _bundle()

    backend = PHASE2_CERTIFIED_FEM_PROFILE.backend

    assert bundle.transfer.element_type == backend.element_type
    assert bundle.transfer.mesh_level == backend.mesh_level
    assert bundle.transfer.timeout_seconds == 57_600

    assert (
        bundle.contact.contact_type
        == backend.contact_type
    )
    assert (
        bundle.contact.pressure_overclosure
        == backend.pressure_overclosure
    )
    assert (
        bundle.contact.normal_stiffness_scale_per_mm
        == backend.normal_stiffness_scale_per_mm
    )
    assert (
        bundle.contact.friction_stick_slope_ratio
        == backend.friction_stick_slope_ratio
    )


def test_bundle_physics_are_case_derived() -> None:
    bundle = _bundle()

    assert bundle.transfer.youngs_modulus_mpa == 210_000.0
    assert bundle.transfer.poissons_ratio == 0.3
    assert bundle.contact.friction_coefficient == 0.15

    assert (
        bundle.calibration_seed.target_force_n
        == 20_000.0
    )
    assert (
        bundle.calibration_seed.predicted_delta_temperature_c
        < 0.0
    )


def test_bundle_boundary_is_geometry_and_mesh_independent() -> None:
    bundle = _bundle()

    assert bundle.boundary.member_outer_radius_mm == 15.0

    assert (
        bundle.boundary.outer_band_inner_radius_mm
        is None
    )
    assert (
        bundle.boundary.outer_band_free_annulus_fraction
        == 0.5
    )

    assert (
        bundle.boundary.expected_head_support_node_count
        is None
    )
    assert (
        bundle.boundary.expected_nut_load_node_count
        is None
    )

    assert not bundle.boundary.require_equal_region_node_counts
    assert bundle.boundary.require_zero_bearing_overlap


def test_changed_preload_changes_case_identity_and_calibration_seed() -> None:
    transfer, contact, boundary = _templates()

    baseline = phase2_certification_case()

    changed = replace(
        baseline,
        loading=replace(
            baseline.loading,
            target_preload_n=10_000.0,
        ),
    )

    baseline_bundle = build_generic_fem_definition_bundle(
        resolve_case(baseline),
        mesh_id="mesh-base",
        geometry_id="geo-base",
        classification_id="class-base",
        source_mesh_name="base.msh",
        transfer_template=transfer,
        contact_template=contact,
        boundary_template=boundary,
    )

    changed_bundle = build_generic_fem_definition_bundle(
        resolve_case(changed),
        mesh_id="mesh-changed",
        geometry_id="geo-changed",
        classification_id="class-changed",
        source_mesh_name="changed.msh",
        transfer_template=transfer,
        contact_template=contact,
        boundary_template=boundary,
    )

    assert (
        baseline_bundle.preparation.identity.case_hash
        != changed_bundle.preparation.identity.case_hash
    )

    assert (
        changed_bundle.calibration_seed.target_force_n
        == 10_000.0
    )

    assert (
        changed_bundle.calibration_seed
        .predicted_delta_temperature_c
        == pytest.approx(
            0.5
            * baseline_bundle.calibration_seed
            .predicted_delta_temperature_c,
            rel=1.0e-12,
        )
    )


def test_contact_template_must_match_backend_topology() -> None:
    transfer, contact, boundary = _templates()

    bad_contact = replace(
        contact,
        contact_pairs=tuple(
            reversed(
                contact.contact_pairs
            )
        ),
    )

    with pytest.raises(
        ValueError,
        match="pair order",
    ):
        build_generic_fem_definition_bundle(
            resolve_case(
                phase2_certification_case()
            ),
            mesh_id="mesh-case",
            geometry_id="geo-case",
            classification_id="class-case",
            source_mesh_name="case.msh",
            transfer_template=transfer,
            contact_template=bad_contact,
            boundary_template=boundary,
        )


def _accepted_evaluation(bundle):
    preload_template = load_complete_joint_preload_definition(
        Path("config/complete_joint_preload.toml")
    )

    first = derive_initial_preload_calibration_trial(
        seed=bundle.calibration_seed,
        case_run_id=bundle.preparation.identity.run_id,
    )

    measurement = ClampForceMeasurement(
        under_head_force_n=20_040.0,
        nut_bearing_force_n=20_050.0,
        member_interface_force_n=20_045.0,
    )

    evaluation = evaluate_preload_calibration_trial(
        case_run_id=bundle.preparation.identity.run_id,
        target_force_n=20_000.0,
        target_relative_tolerance=(
            preload_template.target_relative_tolerance
        ),
        spread_relative_tolerance=(
            preload_template.interface_spread_relative_tolerance
        ),
        current_trial=first,
        measurement=measurement,
    )

    assert evaluation.accepted

    return preload_template, evaluation


def test_accepted_trial_builds_final_preload_without_phase2_calibration_leakage() -> None:
    bundle = _bundle()

    preload_template, evaluation = _accepted_evaluation(
        bundle
    )

    preload = (
        build_accepted_complete_joint_preload_definition(
            bundle=bundle,
            evaluation=evaluation,
            preload_template=preload_template,
        )
    )

    trial = evaluation.completed_trial

    assert preload.target_force_n == 20_000.0
    assert (
        preload.preload_id
        == "preload-"
        + bundle.preparation.identity.case_hash[:16]
    )

    assert (
        preload.thermal.equivalent_delta_temperature_c
        == trial.delta_temperature_c
    )
    assert (
        preload.thermal.calibration_delta_temperature_c
        == trial.delta_temperature_c
    )
    assert (
        preload.thermal.calibration_measured_clamp_force_n
        == pytest.approx(
            evaluation.decision.measurement.mean_force_n
        )
    )
    assert (
        preload.thermal.calibration_run_id
        == trial.run_id
    )

    assert (
        preload.thermal.expansion_coefficient_per_c
        == bundle.preparation.physics
        .bolt_thermal_expansion_per_c
    )

    assert (
        preload.thermal.calibration_method
        == "automatic_case_specific_fem_campaign"
    )

    # Historical Phase-2 calibration scalars must not leak.
    assert (
        preload.thermal.equivalent_delta_temperature_c
        != preload_template.thermal.equivalent_delta_temperature_c
    )
    assert (
        preload.thermal.calibration_delta_temperature_c
        != preload_template.thermal.calibration_delta_temperature_c
    )
    assert (
        preload.thermal.calibration_run_id
        != preload_template.thermal.calibration_run_id
    )


def test_final_preload_remains_compatible_with_certified_thermal_state_derivation() -> None:
    bundle = _bundle()

    preload_template, evaluation = _accepted_evaluation(
        bundle
    )

    preload = (
        build_accepted_complete_joint_preload_definition(
            bundle=bundle,
            evaluation=evaluation,
            preload_template=preload_template,
        )
    )

    state = derive_thermal_preload_state(
        preload
    )

    assert (
        state.delta_temperature_c
        == evaluation.completed_trial.delta_temperature_c
    )
    assert (
        state.calibration_force_n
        == pytest.approx(
            evaluation.decision.measurement.mean_force_n
        )
    )


def test_unaccepted_trial_cannot_be_promoted_to_final_preload() -> None:
    bundle = _bundle()

    preload_template = load_complete_joint_preload_definition(
        Path("config/complete_joint_preload.toml")
    )

    first = derive_initial_preload_calibration_trial(
        seed=bundle.calibration_seed,
        case_run_id=bundle.preparation.identity.run_id,
    )

    evaluation = evaluate_preload_calibration_trial(
        case_run_id=bundle.preparation.identity.run_id,
        target_force_n=20_000.0,
        target_relative_tolerance=(
            preload_template.target_relative_tolerance
        ),
        spread_relative_tolerance=(
            preload_template.interface_spread_relative_tolerance
        ),
        current_trial=first,
        measurement=ClampForceMeasurement(
            under_head_force_n=9_990.0,
            nut_bearing_force_n=10_000.0,
            member_interface_force_n=10_010.0,
        ),
    )

    assert not evaluation.accepted

    with pytest.raises(
        ValueError,
        match="requires an accepted calibration trial",
    ):
        build_accepted_complete_joint_preload_definition(
            bundle=bundle,
            evaluation=evaluation,
            preload_template=preload_template,
        )
