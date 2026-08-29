"""Generic governed FEM solver-definition bundle."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from threadrom.case.resolved_case import ResolvedCase
from threadrom.factory.fem_case_preparation import (
    FemCasePreparation,
    derive_fem_case_preparation,
)
from threadrom.factory.fem_profile import (
    FemBackendPolicy,
    FemPreloadActuator,
    PHASE2_CERTIFIED_FEM_PROFILE,
)
from threadrom.factory.preload_calibration_campaign import (
    PreloadCalibrationCampaignPolicy,
    PreloadCalibrationTrialEvaluation,
)
from threadrom.factory.preload_calibration_seed import (
    ThermalPreloadCalibrationSeed,
    derive_analytical_thermal_preload_seed,
)
from threadrom.solver.complete_joint_boundary_regions import (
    CompleteJointBoundaryRegionDefinition,
)
from threadrom.solver.complete_joint_calculix_transfer import (
    CompleteJointCalculixTransferDefinition,
)
from threadrom.solver.complete_joint_contact import (
    CompleteJointContactDefinition,
)
from threadrom.solver.complete_joint_preload import (
    CompleteJointPreloadDefinition,
    ThermalPreloadDefinition,
)


@dataclass(frozen=True, slots=True)
class FemCaseDefinitionBundle:
    """Non-reference FEM definitions derived for one resolved case."""

    preparation: FemCasePreparation
    transfer: CompleteJointCalculixTransferDefinition
    contact: CompleteJointContactDefinition
    boundary: CompleteJointBoundaryRegionDefinition
    calibration_seed: ThermalPreloadCalibrationSeed
    calibration_policy: PreloadCalibrationCampaignPolicy


def _require_text(
    value: str,
    name: str,
) -> str:
    if not value.strip():
        raise ValueError(
            f"{name} must not be blank."
        )

    return value


def build_generic_fem_definition_bundle(
    resolved: ResolvedCase,
    *,
    mesh_id: str,
    geometry_id: str,
    classification_id: str,
    source_mesh_name: str,
    transfer_template: CompleteJointCalculixTransferDefinition,
    contact_template: CompleteJointContactDefinition,
    boundary_template: CompleteJointBoundaryRegionDefinition,
    backend: FemBackendPolicy = (
        PHASE2_CERTIFIED_FEM_PROFILE.backend
    ),
    boundary_outer_free_annulus_fraction: float = 0.5,
    calibration_policy: PreloadCalibrationCampaignPolicy = (
        PreloadCalibrationCampaignPolicy()
    ),
) -> FemCaseDefinitionBundle:
    """Build generic FEM definitions without certification-oracle coupling.

    The template definitions provide stable semantic names and executable
    configuration. Case/run identity and physical inputs are replaced by
    resolved case data and the reusable FEM backend policy.
    """

    mesh_id = _require_text(
        mesh_id,
        "Mesh identity",
    )
    geometry_id = _require_text(
        geometry_id,
        "Geometry identity",
    )
    classification_id = _require_text(
        classification_id,
        "Classification identity",
    )
    source_mesh_name = _require_text(
        source_mesh_name,
        "Source mesh name",
    )

    if not 0.0 < boundary_outer_free_annulus_fraction < 1.0:
        raise ValueError(
            "Boundary free-annulus fraction must lie in (0, 1)."
        )

    if (
        backend.preload_actuator
        is not FemPreloadActuator.BOLT_ONLY_THERMAL_EIGENSTRAIN
    ):
        raise ValueError(
            "Generic complete-joint FEM currently requires the "
            "bolt-only thermal eigenstrain preload actuator."
        )

    if not backend.require_case_specific_preload_calibration:
        raise ValueError(
            "Generic FEM cases require case-specific preload "
            "calibration."
        )

    preparation = derive_fem_case_preparation(
        resolved
    )

    calibration_seed = (
        derive_analytical_thermal_preload_seed(
            resolved
        )
    )

    timeout_seconds = (
        backend.solver_timeout_seconds
        if backend.solver_timeout_seconds is not None
        else transfer_template.timeout_seconds
    )

    transfer = replace(
        transfer_template,
        simulation_id=preparation.identity.run_id,
        mesh_id=mesh_id,
        assembly_id=resolved.assembly.assembly_id,
        geometry_id=geometry_id,
        classification_id=classification_id,
        mesh_level=backend.mesh_level,
        source_mesh_name=source_mesh_name,
        job_name=preparation.identity.job_name,
        timeout_seconds=timeout_seconds,
        element_type=backend.element_type,
        youngs_modulus_mpa=(
            preparation.physics.youngs_modulus_mpa
        ),
        poissons_ratio=(
            preparation.physics.poissons_ratio
        ),
    )

    template_pair_names = tuple(
        pair.name
        for pair in contact_template.contact_pairs
    )

    if template_pair_names != backend.required_contact_pairs:
        raise ValueError(
            "Contact template pair order does not match the "
            "governed FEM backend policy."
        )

    contact_model_id = (
        f"contact-{resolved.case_hash[:16]}"
    )

    contact = replace(
        contact_template,
        contact_model_id=contact_model_id,
        simulation_id=preparation.identity.run_id,
        mesh_id=mesh_id,
        assembly_id=resolved.assembly.assembly_id,
        geometry_id=geometry_id,
        classification_id=classification_id,
        solver_job_name=preparation.identity.job_name,
        contact_type=backend.contact_type,
        pressure_overclosure=(
            backend.pressure_overclosure
        ),
        normal_stiffness_scale_per_mm=(
            backend.normal_stiffness_scale_per_mm
        ),
        friction_coefficient=(
            preparation.physics.common_friction_coefficient
        ),
        friction_stick_slope_ratio=(
            backend.friction_stick_slope_ratio
        ),
    )

    member_outer_radius_mm = (
        resolved.assembly.outer_diameter_mm
        / 2.0
    )

    boundary = replace(
        boundary_template,
        boundary_region_id=(
            f"boundary-{resolved.case_hash[:16]}"
        ),
        simulation_id=preparation.identity.run_id,
        mesh_id=mesh_id,
        assembly_id=resolved.assembly.assembly_id,
        contact_model_id=contact_model_id,
        status="generated",
        outer_band_inner_radius_mm=None,
        member_outer_radius_mm=(
            member_outer_radius_mm
        ),
        expected_head_support_node_count=None,
        expected_nut_load_node_count=None,
        require_equal_region_node_counts=False,
        outer_band_free_annulus_fraction=(
            boundary_outer_free_annulus_fraction
        ),
    )

    return FemCaseDefinitionBundle(
        preparation=preparation,
        transfer=transfer,
        contact=contact,
        boundary=boundary,
        calibration_seed=calibration_seed,
        calibration_policy=calibration_policy,
    )


def build_accepted_complete_joint_preload_definition(
    *,
    bundle: FemCaseDefinitionBundle,
    evaluation: PreloadCalibrationTrialEvaluation,
    preload_template: CompleteJointPreloadDefinition,
) -> CompleteJointPreloadDefinition:
    """Create the final preload definition from solved acceptance evidence.

    The template contributes reusable preload policy only: tolerances,
    semantic model roles, initial-stress rules, validation requirements
    and numerical reference temperature. Historical target/calibration
    scalars are deliberately replaced.
    """

    if not evaluation.accepted:
        raise ValueError(
            "A final FEM preload definition requires an accepted "
            "calibration trial."
        )

    target_force_n = (
        bundle.preparation.physics.target_preload_n
    )

    decision = evaluation.decision

    if not math.isclose(
        decision.target_force_n,
        target_force_n,
        rel_tol=0.0,
        abs_tol=1.0e-9,
    ):
        raise ValueError(
            "Accepted calibration target does not match the "
            "prepared FEM case."
        )

    if not math.isclose(
        decision.target_relative_tolerance,
        preload_template.target_relative_tolerance,
        rel_tol=0.0,
        abs_tol=1.0e-15,
    ):
        raise ValueError(
            "Accepted calibration target tolerance does not match "
            "the governed preload policy."
        )

    if not math.isclose(
        decision.spread_relative_tolerance,
        preload_template.interface_spread_relative_tolerance,
        rel_tol=0.0,
        abs_tol=1.0e-15,
    ):
        raise ValueError(
            "Accepted calibration spread tolerance does not match "
            "the governed preload policy."
        )

    trial = evaluation.completed_trial
    measurement = decision.measurement

    thermal = ThermalPreloadDefinition(
        enabled=True,
        reference_temperature_c=(
            preload_template.thermal.reference_temperature_c
        ),
        expansion_coefficient_per_c=(
            bundle.preparation.physics
            .bolt_thermal_expansion_per_c
        ),
        equivalent_delta_temperature_c=(
            trial.delta_temperature_c
        ),
        calibration_method=(
            "automatic_case_specific_fem_campaign"
        ),
        calibration_delta_temperature_c=(
            trial.delta_temperature_c
        ),
        calibration_measured_clamp_force_n=(
            measurement.mean_force_n
        ),
        calibration_run_id=trial.run_id,
    )

    return CompleteJointPreloadDefinition(
        schema_version=preload_template.schema_version,
        preload_id=(
            f"preload-{bundle.preparation.identity.case_hash[:16]}"
        ),
        target_force_n=target_force_n,
        target_relative_tolerance=(
            preload_template.target_relative_tolerance
        ),
        interface_spread_relative_tolerance=(
            preload_template.interface_spread_relative_tolerance
        ),
        model=preload_template.model,
        thermal=thermal,
        initial_stress=preload_template.initial_stress,
        validation=preload_template.validation,
    )
