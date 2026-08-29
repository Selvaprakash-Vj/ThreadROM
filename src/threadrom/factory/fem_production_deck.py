"""Generic case-specific Phase-3 FEM production deck assembly."""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from pathlib import Path

from threadrom.factory.fem_profile import (
    FemBackendPolicy,
)
from threadrom.solver.complete_joint_boundary_regions import (
    CompleteJointBoundaryRegionDefinition,
    derive_complete_joint_boundary_regions,
    render_complete_joint_boundary_region_nsets,
)
from threadrom.solver.complete_joint_calculix_transfer import (
    CompleteJointCalculixMeshData,
    CompleteJointCalculixTransferDefinition,
    render_complete_joint_calculix_model,
)
from threadrom.solver.complete_joint_contact import (
    CompleteJointContactDefinition,
    render_complete_joint_contact_keywords,
)
from threadrom.solver.complete_joint_continuous_preload import (
    derive_component_calculix_node_ids,
    render_calculix_node_set,
)
from threadrom.solver.complete_joint_guidance import (
    BOLT_HEAD_GUIDANCE_REFERENCE,
    BOLT_HEAD_ROTATION_X_REFERENCE,
    BOLT_HEAD_ROTATION_Y_REFERENCE,
    NUT_MEMBER_GUIDANCE_REFERENCE,
    NUT_ROTATION_GUIDANCE_REFERENCE,
    NUT_ROTATION_X_REFERENCE,
    NUT_ROTATION_Y_REFERENCE,
    NUT_TRANSLATION_GUIDANCE_REFERENCE,
    DistributedGuidancePolicy,
    render_distributed_guidance_keywords,
)
from threadrom.solver.complete_joint_preload import (
    CompleteJointPreloadDefinition,
)
from threadrom.solver.complete_joint_thermal_preload import (
    derive_thermal_preload_state,
    render_bolt_temperature_keywords,
    render_initial_temperature_keywords,
    render_thermal_expansion_keywords,
)


BOLT_THERMAL_SET = "BOLT_THERMAL"
THERMAL_INITIAL_ALL_NODES_SET = (
    "THERMAL_INITIAL_ALL_NODES"
)


@dataclass(frozen=True, slots=True)
class FemProductionDeckResult:
    """Identity and derived counts of one generic FEM production deck."""

    input_path: Path
    sha256: str
    size_bytes: int
    node_count: int
    element_count: int
    guidance_reference_node_count: int
    bolt_thermal_node_count: int
    thermal_initial_node_count: int
    head_support_node_count: int
    nut_load_node_count: int


def _node_set_lines(
    *,
    name: str,
    node_ids: tuple[int, ...],
) -> tuple[str, ...]:
    return tuple(
        render_calculix_node_set(
            name=name,
            node_ids=node_ids,
        )
        .rstrip("\n")
        .splitlines()
    )


def _ordered_contact_pairs(
    *,
    contact: CompleteJointContactDefinition,
    backend: FemBackendPolicy,
):
    by_name = {
        pair.name: pair
        for pair in contact.contact_pairs
    }

    missing = [
        name
        for name in backend.required_contact_pairs
        if name not in by_name
    ]

    if missing:
        raise ValueError(
            "Required governed contact pairs are missing: "
            + ", ".join(missing)
        )

    return tuple(
        by_name[name]
        for name in backend.required_contact_pairs
    )


def _validate_accepted_preload(
    preload: CompleteJointPreloadDefinition,
) -> None:
    target = preload.target_force_n
    measured = (
        preload.thermal.calibration_measured_clamp_force_n
    )

    if not math.isfinite(target) or target <= 0.0:
        raise ValueError(
            "Production preload target must be finite and positive."
        )

    if not math.isfinite(measured) or measured <= 0.0:
        raise ValueError(
            "Production preload requires finite positive "
            "FEM calibration evidence."
        )

    relative_error = abs(
        measured - target
    ) / target

    if relative_error > preload.target_relative_tolerance:
        raise ValueError(
            "Production preload calibration evidence lies outside "
            "the governed target-force tolerance."
        )

    if not preload.thermal.calibration_run_id.strip():
        raise ValueError(
            "Production preload requires calibration provenance."
        )

    if not math.isclose(
        preload.thermal.equivalent_delta_temperature_c,
        preload.thermal.calibration_delta_temperature_c,
        rel_tol=0.0,
        abs_tol=1.0e-12,
    ):
        raise ValueError(
            "Production thermal actuator does not match its "
            "accepted calibration temperature."
        )


def write_fem_production_deck(
    *,
    mesh_data: CompleteJointCalculixMeshData,
    transfer: CompleteJointCalculixTransferDefinition,
    boundary: CompleteJointBoundaryRegionDefinition,
    contact: CompleteJointContactDefinition,
    preload: CompleteJointPreloadDefinition,
    backend: FemBackendPolicy,
    input_path: Path,
) -> FemProductionDeckResult:
    """Assemble one generic case-specific nonlinear FEM production deck."""

    _validate_accepted_preload(preload)

    if not backend.step.nonlinear_geometry:
        raise ValueError(
            "Production FEM requires NLGEOM."
        )

    state = derive_thermal_preload_state(
        preload
    )

    expansion_lines = (
        render_thermal_expansion_keywords(
            state=state,
        )
    )

    model = render_complete_joint_calculix_model(
        mesh_data,
        transfer,
        material_keyword_extensions={
            transfer.bolt_material_name: (
                expansion_lines
            ),
        },
    )

    boundary_regions = (
        derive_complete_joint_boundary_regions(
            mesh_data,
            boundary,
            transfer,
            contact,
        )
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

    bolt_node_ids = (
        derive_component_calculix_node_ids(
            mesh_data,
            "bolt",
        )
    )

    bolt_set_lines = _node_set_lines(
        name=BOLT_THERMAL_SET,
        node_ids=bolt_node_ids,
    )

    governed_guidance = (
        backend.guidance_policy
    )

    guidance = (
        render_distributed_guidance_keywords(
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
    )

    contact_lines = (
        render_complete_joint_contact_keywords(
            contact,
            transfer,
        )
    )

    contact_pairs = _ordered_contact_pairs(
        contact=contact,
        backend=backend,
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
        "** Direct governed contact-force resultants",
    ]

    for pair in contact_pairs:
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
        "** THREADROM PHASE 3 GENERIC FEM PRODUCTION RUN",
        f"** Preload ID: {preload.preload_id}",
        (
            "** Calibration run ID: "
            f"{preload.thermal.calibration_run_id}"
        ),
        (
            "** Target force N: "
            f"{preload.target_force_n:.12e}"
        ),
        (
            "** Calibration measured clamp force N: "
            f"{preload.thermal.calibration_measured_clamp_force_n:.12e}"
        ),
        (
            "** Reference temperature C: "
            f"{state.reference_temperature_c:.12e}"
        ),
        (
            "** Delta temperature C: "
            f"{state.delta_temperature_c:.12e}"
        ),
        (
            "** Applied bolt temperature C: "
            f"{state.applied_bolt_temperature_c:.12e}"
        ),
        (
            "** Backend policy ID: "
            f"{backend.policy_id}"
        ),
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

    payload = "\n".join(
        lines
    ).encode("utf-8")

    text = payload.decode("utf-8")

    if (
        backend.forbid_native_pretension_section
        and "*PRE-TENSION SECTION" in text.upper()
    ):
        raise RuntimeError(
            "Production deck contains forbidden native pretension."
        )

    if (
        backend.forbid_direct_preload_cload
        and "*CLOAD" in text.upper()
    ):
        raise RuntimeError(
            "Production deck contains forbidden direct preload CLOAD."
        )

    input_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    input_path.write_bytes(
        payload
    )

    return FemProductionDeckResult(
        input_path=input_path,
        sha256=hashlib.sha256(
            payload
        ).hexdigest(),
        size_bytes=len(payload),
        node_count=model.node_count,
        element_count=model.element_count,
        guidance_reference_node_count=(
            guidance.reference_node_count
        ),
        bolt_thermal_node_count=len(
            bolt_node_ids
        ),
        thermal_initial_node_count=len(
            thermal_initial_node_ids
        ),
        head_support_node_count=(
            head_support.node_count
        ),
        nut_load_node_count=(
            nut_load.node_count
        ),
    )
