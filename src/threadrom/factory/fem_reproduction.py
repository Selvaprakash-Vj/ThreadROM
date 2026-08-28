"""Deterministic Phase-2 certified FEM reproduction assembly."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from threadrom.factory.fem_profile import (
    FemReproductionProfile,
)
from threadrom.solver.calculix_job import (
    CalculixJobDefinition,
    run_calculix_job,
)
from threadrom.solver.calculix_mesh_transfer import (
    CalculixRunResult,
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
class FemReproductionDeckResult:
    """Identity and derived counts of one reproduction deck."""

    input_path: Path
    sha256: str
    size_bytes: int
    node_count: int
    element_count: int
    guidance_reference_node_count: int
    bolt_thermal_node_count: int
    thermal_initial_node_count: int


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
    profile: FemReproductionProfile,
):
    by_name = {
        pair.name: pair
        for pair in contact.contact_pairs
    }

    required = (
        profile.backend.required_contact_pairs
    )

    missing = [
        name
        for name in required
        if name not in by_name
    ]

    if missing:
        raise ValueError(
            "Required certified contact pairs are missing: "
            + ", ".join(missing)
        )

    return tuple(
        by_name[name]
        for name in required
    )


def write_phase2_certified_reproduction_deck(
    *,
    mesh_data: CompleteJointCalculixMeshData,
    transfer: CompleteJointCalculixTransferDefinition,
    boundary: CompleteJointBoundaryRegionDefinition,
    contact: CompleteJointContactDefinition,
    preload: CompleteJointPreloadDefinition,
    profile: FemReproductionProfile,
    input_path: Path,
) -> FemReproductionDeckResult:
    """Assemble the certified thermal-preload FEM deck."""

    state = derive_thermal_preload_state(preload)

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
        profile.backend.guidance_policy
    )

    guidance = (
        render_distributed_guidance_keywords(
            mesh_data=mesh_data,
            nut_member_node_ids=(
                boundary_regions
                .region("nut_load")
                .node_ids
            ),
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

    step = profile.backend.step

    if not step.nonlinear_geometry:
        raise ValueError(
            "Certified reproduction requires NLGEOM."
        )

    contact_pairs = _ordered_contact_pairs(
        contact=contact,
        profile=profile,
    )

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
        "HEAD_MEMBER_SUPPORT_BAND, 1, 3, 0.0",
        (
            f"{BOLT_HEAD_GUIDANCE_REFERENCE}, "
            "1, 2, 0.0"
        ),
        (
            f"{NUT_TRANSLATION_GUIDANCE_REFERENCE}, "
            "1, 2, 0.0"
        ),
        (
            f"{NUT_MEMBER_GUIDANCE_REFERENCE}, "
            "1, 2, 0.0"
        ),
        (
            f"{NUT_ROTATION_GUIDANCE_REFERENCE}, "
            "1, 1, 0.0"
        ),
        (
            f"{BOLT_HEAD_ROTATION_X_REFERENCE}, "
            "1, 1, 0.0"
        ),
        (
            f"{BOLT_HEAD_ROTATION_Y_REFERENCE}, "
            "1, 1, 0.0"
        ),
        (
            f"{NUT_ROTATION_X_REFERENCE}, "
            "1, 1, 0.0"
        ),
        (
            f"{NUT_ROTATION_Y_REFERENCE}, "
            "1, 1, 0.0"
        ),
        *bolt_temperature_lines,
        (
            "*NODE PRINT, "
            "NSET=HEAD_MEMBER_SUPPORT_BAND, "
            "TOTALS=ONLY"
        ),
        "RF",
        "*NODE FILE",
        "U, RF",
        "*EL FILE",
        "S, E",
        "** Direct contact-force resultants",
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
            "",
        )
    )

    lines: list[str] = [
        "** ------------------------------------------------------------",
        (
            "** THREADROM RUN A2 ? "
            "CORRECTED GOVERNED THERMAL PRELOAD"
        ),
        f"** Preload ID: {preload.preload_id}",
        (
            "** Target force N: "
            f"{preload.target_force_n:.12e}"
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
        "** ------------------------------------------------------------",
        *model.lines,
        "**",
        "**",
        "** CP6 CONTINUOUS-BOLT THERMAL PRELOAD",
        "** No PRE-TENSION SECTION",
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
        "** Settling diagnostic A0",
        *all_node_set_lines,
        *initial_temperature_lines,
        "**",
        *step_lines,
    ]

    input_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    payload = "\n".join(lines).encode("utf-8")

    input_path.write_bytes(payload)

    return FemReproductionDeckResult(
        input_path=input_path,
        sha256=hashlib.sha256(payload).hexdigest(),
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
    )

def run_phase2_certified_reproduction_job(
    *,
    project_root: Path,
    deck: FemReproductionDeckResult,
    transfer: CompleteJointCalculixTransferDefinition,
    profile: FemReproductionProfile,
) -> CalculixRunResult:
    """Execute only an oracle-identical certified reproduction deck."""

    if not deck.input_path.exists():
        raise FileNotFoundError(
            f"Reproduction deck not found: {deck.input_path}"
        )

    payload = deck.input_path.read_bytes()
    actual_sha256 = hashlib.sha256(payload).hexdigest()

    if actual_sha256 != deck.sha256:
        raise RuntimeError(
            "Reproduction deck changed after assembly."
        )

    if actual_sha256 != profile.oracle.solver_deck_sha256:
        raise RuntimeError(
            "Reproduction deck does not match the certified "
            "solver-deck oracle."
        )

    if deck.input_path.stem != profile.oracle.run_id:
        raise ValueError(
            "Reproduction job name does not match the certified "
            "run identity."
        )

    definition = CalculixJobDefinition(
        executable_relative_path=(
            transfer.executable_relative_path
        ),
        job_name=deck.input_path.stem,
        timeout_seconds=transfer.timeout_seconds,
    )

    return run_calculix_job(
        project_root=project_root,
        input_path=deck.input_path,
        definition=definition,
    )
