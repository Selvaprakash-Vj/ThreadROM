"""Generic physical deck for one preload-calibration trial."""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from pathlib import Path

from threadrom.factory.fem_case_definition_bundle import (
    FemCaseDefinitionBundle,
)
from threadrom.factory.fem_profile import (
    FemBackendPolicy,
    PHASE2_CERTIFIED_FEM_PROFILE,
)
from threadrom.factory.preload_calibration_campaign import (
    PreloadCalibrationTrial,
)
from threadrom.solver.complete_joint_boundary_regions import (
    derive_complete_joint_boundary_regions,
    render_complete_joint_boundary_region_nsets,
)
from threadrom.solver.complete_joint_calculix_transfer import (
    CompleteJointCalculixMeshData,
    render_complete_joint_calculix_model,
)
from threadrom.solver.complete_joint_contact import (
    render_complete_joint_contact_keywords,
)
from threadrom.solver.complete_joint_continuous_preload import (
    derive_component_calculix_node_ids,
)
from threadrom.solver.complete_joint_guidance import (
    BOLT_HEAD_GUIDANCE_REFERENCE,
    BOLT_HEAD_ROTATION_X_REFERENCE,
    BOLT_HEAD_ROTATION_Y_REFERENCE,
    DistributedGuidancePolicy,
    NUT_MEMBER_GUIDANCE_REFERENCE,
    NUT_ROTATION_GUIDANCE_REFERENCE,
    NUT_ROTATION_X_REFERENCE,
    NUT_ROTATION_Y_REFERENCE,
    NUT_TRANSLATION_GUIDANCE_REFERENCE,
    render_distributed_guidance_keywords,
)
from threadrom.solver.complete_joint_thermal_preload import (
    derive_thermal_preload_actuator_state,
    render_bolt_temperature_keywords,
    render_initial_temperature_keywords,
    render_thermal_expansion_keywords,
)


BOLT_THERMAL_SET = "CASE_BOLT_THERMAL"
THERMAL_INITIAL_ALL_NODES_SET = "CASE_THERMAL_ALL_NODES"


@dataclass(frozen=True, slots=True)
class FemPreloadCalibrationDeckResult:
    """Rendered physical deck for one unsolved calibration trial."""

    input_path: Path
    sha256: str
    size_bytes: int
    trial_run_id: str
    trial_index: int
    delta_temperature_c: float
    applied_bolt_temperature_c: float
    node_count: int
    element_count: int
    bolt_thermal_node_count: int
    head_support_node_count: int
    nut_load_node_count: int
    guidance_reference_node_count: int


def _node_set_lines(
    *,
    name: str,
    node_ids: tuple[int, ...],
) -> tuple[str, ...]:
    if not name.strip():
        raise ValueError(
            "Node-set name must not be blank."
        )

    if not node_ids:
        raise ValueError(
            f"Node set {name} must not be empty."
        )

    unique_ids = tuple(
        sorted(set(node_ids))
    )

    if len(unique_ids) != len(node_ids):
        raise ValueError(
            f"Node set {name} contains duplicate IDs."
        )

    rows = tuple(
        ", ".join(
            str(node_id)
            for node_id in unique_ids[
                start:start + 16
            ]
        )
        for start in range(
            0,
            len(unique_ids),
            16,
        )
    )

    return (
        f"*NSET, NSET={name}",
        *rows,
    )


def write_fem_preload_calibration_trial_deck(
    *,
    mesh_data: CompleteJointCalculixMeshData,
    bundle: FemCaseDefinitionBundle,
    trial: PreloadCalibrationTrial,
    reference_temperature_c: float,
    input_path: Path,
    backend: FemBackendPolicy = (
        PHASE2_CERTIFIED_FEM_PROFILE.backend
    ),
) -> FemPreloadCalibrationDeckResult:
    """Render one fresh nonlinear thermal-preload calibration trial.

    This function deliberately requires no accepted calibration evidence.
    It uses only the case-derived target/thermal coefficient, the current
    governed trial temperature, reusable FEM backend policy and the
    current case-specific mesh/contact/boundary definitions.
    """

    if not math.isfinite(reference_temperature_c):
        raise ValueError(
            "Reference temperature must be finite."
        )

    if not math.isfinite(trial.delta_temperature_c):
        raise ValueError(
            "Calibration trial delta temperature must be finite."
        )

    if trial.delta_temperature_c >= 0.0:
        raise ValueError(
            "Current bolt-only thermal preload requires "
            "a negative calibration delta temperature."
        )

    case_run_id = bundle.preparation.identity.run_id

    if not trial.run_id.startswith(
        f"{case_run_id}_cal_"
    ):
        raise ValueError(
            "Calibration trial does not belong to the prepared case."
        )

    if not backend.step.nonlinear_geometry:
        raise ValueError(
            "Physical preload calibration requires NLGEOM."
        )

    pair_names = tuple(
        pair.name
        for pair in bundle.contact.contact_pairs
    )

    if pair_names != backend.required_contact_pairs:
        raise ValueError(
            "Calibration contact topology does not match "
            "the governed FEM backend policy."
        )

    state = derive_thermal_preload_actuator_state(
        target_force_n=(
            bundle.preparation.physics.target_preload_n
        ),
        reference_temperature_c=(
            reference_temperature_c
        ),
        delta_temperature_c=(
            trial.delta_temperature_c
        ),
        expansion_coefficient_per_c=(
            bundle.preparation.physics
            .bolt_thermal_expansion_per_c
        ),
    )

    expansion_lines = render_thermal_expansion_keywords(
        state=state
    )

    model = render_complete_joint_calculix_model(
        mesh_data,
        bundle.transfer,
        material_keyword_extensions={
            bundle.transfer.bolt_material_name: (
                expansion_lines
            ),
        },
    )

    boundary_regions = derive_complete_joint_boundary_regions(
        mesh_data,
        bundle.boundary,
        bundle.transfer,
        bundle.contact,
    )

    boundary_lines = (
        render_complete_joint_boundary_region_nsets(
            boundary_regions
        )
    )

    head_support = boundary_regions.region(
        "head_support"
    )
    nut_load = boundary_regions.region(
        "nut_load"
    )

    bolt_node_ids = derive_component_calculix_node_ids(
        mesh_data,
        "bolt",
    )

    bolt_set_lines = _node_set_lines(
        name=BOLT_THERMAL_SET,
        node_ids=bolt_node_ids,
    )

    governed_guidance = backend.guidance_policy

    guidance = render_distributed_guidance_keywords(
        mesh_data=mesh_data,
        nut_member_node_ids=nut_load.node_ids,
        first_reference_node_id=(
            mesh_data.node_count + 1
        ),
        first_element_id=(
            mesh_data.element_count + 1
        ),
        policy=DistributedGuidancePolicy(
            translation_sample_node_count=(
                governed_guidance
                .translation_sample_node_count
            ),
            rotation_sample_node_count=(
                governed_guidance
                .rotation_sample_node_count
            ),
            bolt_head_max_radius_mm=(
                governed_guidance
                .bolt_head_max_radius_mm
            ),
            nut_min_radius_mm=(
                governed_guidance
                .nut_min_radius_mm
            ),
            nut_max_radius_mm=(
                governed_guidance
                .nut_max_radius_mm
            ),
        ),
    )

    contact_lines = (
        render_complete_joint_contact_keywords(
            bundle.contact,
            bundle.transfer,
        )
    )

    thermal_initial_node_ids = tuple(
        range(
            1,
            (
                mesh_data.node_count
                + guidance.reference_node_count
                + 1
            ),
        )
    )

    all_node_set_lines = _node_set_lines(
        name=THERMAL_INITIAL_ALL_NODES_SET,
        node_ids=thermal_initial_node_ids,
    )

    initial_temperature_lines = (
        render_initial_temperature_keywords(
            state=state,
            all_nodes_set_name=(
                THERMAL_INITIAL_ALL_NODES_SET
            ),
        )
    )

    bolt_temperature_lines = (
        render_bolt_temperature_keywords(
            state=state,
            bolt_nodes_set_name=BOLT_THERMAL_SET,
        )
    )

    step = backend.step

    step_lines: list[str] = [
        (
            "*STEP, NLGEOM=YES, "
            f"INC={step.maximum_increments}"
        ),
        "*STATIC",
        (
            f"{step.initial_increment:.12e}, "
            f"{step.total_time:.12e}, "
            f"{step.minimum_increment:.12e}, "
            f"{step.maximum_increment:.12e}"
        ),
        "*BOUNDARY",
        f"{head_support.name}, 1, 3, 0.0",
        f"{BOLT_HEAD_GUIDANCE_REFERENCE}, 1, 2, 0.0",
        f"{NUT_TRANSLATION_GUIDANCE_REFERENCE}, 1, 2, 0.0",
        f"{NUT_MEMBER_GUIDANCE_REFERENCE}, 1, 2, 0.0",
        f"{NUT_ROTATION_GUIDANCE_REFERENCE}, 1, 1, 0.0",
        f"{BOLT_HEAD_ROTATION_X_REFERENCE}, 1, 1, 0.0",
        f"{BOLT_HEAD_ROTATION_Y_REFERENCE}, 1, 1, 0.0",
        f"{NUT_ROTATION_X_REFERENCE}, 1, 1, 0.0",
        f"{NUT_ROTATION_Y_REFERENCE}, 1, 1, 0.0",
        *bolt_temperature_lines,
        (
            "*NODE PRINT, "
            f"NSET={head_support.name}, "
            "TOTALS=ONLY"
        ),
        "RF",
        "*NODE FILE",
        "U, RF",
        "*EL FILE",
        "S, E",
        "** Direct contact-force resultants",
    ]

    for pair in bundle.contact.contact_pairs:
        step_lines.extend(
            (
                (
                    "*CONTACT PRINT, FREQUENCY=1, "
                    f"SLAVE={pair.slave_surface}, "
                    f"MASTER={pair.master_surface}"
                ),
                "CFN",
            )
        )

    step_lines.extend(
        (
            "*END STEP",
            "",
        )
    )

    lines = [
        "** ------------------------------------------------------------",
        "** THREADROM PHASE 3 CASE-SPECIFIC PRELOAD CALIBRATION",
        f"** Case run ID: {case_run_id}",
        f"** Calibration trial ID: {trial.run_id}",
        f"** Calibration trial index: {trial.trial_index}",
        (
            "** Target preload N: "
            f"{state.target_force_n:.12e}"
        ),
        (
            "** Reference temperature C: "
            f"{state.reference_temperature_c:.12e}"
        ),
        (
            "** Trial delta temperature C: "
            f"{state.delta_temperature_c:.12e}"
        ),
        (
            "** Applied bolt temperature C: "
            f"{state.applied_bolt_temperature_c:.12e}"
        ),
        "** No accepted calibration evidence exists at this stage.",
        "** No PRE-TENSION SECTION.",
        "** No direct preload CLOAD.",
        "** ------------------------------------------------------------",
        *model.lines,
        "**",
        *boundary_lines,
        "**",
        *bolt_set_lines,
        "**",
        *guidance.lines,
        "**",
        "** Complete-joint nonlinear contact model",
        *contact_lines,
        "**",
        *all_node_set_lines,
        *initial_temperature_lines,
        "**",
        *step_lines,
    ]

    payload = "\n".join(lines).encode(
        "utf-8"
    )

    input_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    input_path.write_bytes(
        payload
    )

    return FemPreloadCalibrationDeckResult(
        input_path=input_path,
        sha256=hashlib.sha256(
            payload
        ).hexdigest(),
        size_bytes=len(payload),
        trial_run_id=trial.run_id,
        trial_index=trial.trial_index,
        delta_temperature_c=state.delta_temperature_c,
        applied_bolt_temperature_c=(
            state.applied_bolt_temperature_c
        ),
        node_count=model.node_count,
        element_count=model.element_count,
        bolt_thermal_node_count=len(
            bolt_node_ids
        ),
        head_support_node_count=(
            head_support.node_count
        ),
        nut_load_node_count=(
            nut_load.node_count
        ),
        guidance_reference_node_count=(
            guidance.reference_node_count
        ),
    )
