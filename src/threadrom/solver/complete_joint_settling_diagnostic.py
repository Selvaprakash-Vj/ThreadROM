"""Reduced A0-A3 and A0T settling diagnostics for the complete joint."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from threadrom.solver.complete_joint_boundary_regions import (
    CompleteJointBoundaryRegionDefinition,
    derive_complete_joint_boundary_regions,
    render_complete_joint_boundary_region_nsets,
)
from threadrom.solver.complete_joint_calculix_transfer import (
    CompleteJointCalculixDeckSummary,
    CompleteJointCalculixMeshData,
    CompleteJointCalculixTransferDefinition,
    _calculix_surface_name,
    write_complete_joint_calculix_transfer_deck,
)
from threadrom.solver.complete_joint_contact import (
    THREAD,
    CompleteJointContactDefinition,
    render_complete_joint_contact_keywords,
)
from threadrom.solver.complete_joint_physical_pretension import (
    BOLT_HEAD_GUIDANCE_REFERENCE,
    BOLT_HEAD_ROTATION_X_REFERENCE,
    BOLT_HEAD_ROTATION_Y_REFERENCE,
    NUT_MEMBER_GUIDANCE_REFERENCE,
    NUT_ROTATION_GUIDANCE_REFERENCE,
    NUT_ROTATION_X_REFERENCE,
    NUT_ROTATION_Y_REFERENCE,
    NUT_TRANSLATION_GUIDANCE_REFERENCE,
    PRETENSION_REFERENCE_SET,
    _exclude_boundary_faces_touching_protected_nodes,
    _render_distributed_guidance_keywords,
    validate_physical_pretension_identities,
)
from threadrom.solver.complete_joint_pretension import (
    CompleteJointPretensionDefinition,
)

DIAGNOSTIC_MAXIMUM_INCREMENTS = 100
DIAGNOSTIC_GUIDANCE_SAMPLE_NODE_COUNT = 40
DIAGNOSTIC_ROTATION_GUIDANCE_SAMPLE_NODE_COUNT = 20
DIAGNOSTIC_INITIAL_TIME_INCREMENT = 5.0e-2
DIAGNOSTIC_STEP_TIME = 1.0
DIAGNOSTIC_MINIMUM_TIME_INCREMENT = 1.0e-6
DIAGNOSTIC_MAXIMUM_TIME_INCREMENT = 5.0e-2


@dataclass(frozen=True)
class CompleteJointSettlingDiagnosticCase:
    """One governed member of the A0-A3 and A0T diagnostic matrix."""

    case_id: str
    include_pretension_section: bool
    reference_force_n: float
    excluded_contact_pair_names: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        expected = {
            "A0": (False, 0.0, ()),
            "A0T": (False, 0.0, (THREAD,)),
            "A1": (True, 0.0, ()),
            "A2": (True, 1.0, ()),
            "A3": (True, -1.0, ()),
        }

        if self.case_id not in expected:
            raise ValueError(f"Unknown settling diagnostic case: {self.case_id}")

        if not math.isfinite(self.reference_force_n):
            raise ValueError("Diagnostic reference force must be finite.")

        (
            expected_section,
            expected_force,
            expected_excluded_pairs,
        ) = expected[self.case_id]

        if (
            self.include_pretension_section != expected_section
            or self.reference_force_n != expected_force
            or self.excluded_contact_pair_names != expected_excluded_pairs
        ):
            raise ValueError(
                f"Diagnostic case {self.case_id} does not match its governed definition."
            )


SETTLING_DIAGNOSTIC_CASES = (
    CompleteJointSettlingDiagnosticCase(
        case_id="A0",
        include_pretension_section=False,
        reference_force_n=0.0,
    ),
    CompleteJointSettlingDiagnosticCase(
        case_id="A0T",
        include_pretension_section=False,
        reference_force_n=0.0,
        excluded_contact_pair_names=(THREAD,),
    ),
    CompleteJointSettlingDiagnosticCase(
        case_id="A1",
        include_pretension_section=True,
        reference_force_n=0.0,
    ),
    CompleteJointSettlingDiagnosticCase(
        case_id="A2",
        include_pretension_section=True,
        reference_force_n=1.0,
    ),
    CompleteJointSettlingDiagnosticCase(
        case_id="A3",
        include_pretension_section=True,
        reference_force_n=-1.0,
    ),
)


@dataclass(frozen=True)
class CompleteJointSettlingDiagnosticDeckSummary:
    """Summary of one generated A0-A3 diagnostic deck."""

    transfer: CompleteJointCalculixDeckSummary
    case_id: str
    reference_node_id: int | None
    applied_reference_force_n: float
    boundary_region_count: int
    boundary_region_node_count: int
    contact_pair_count: int
    excluded_contact_pair_names: tuple[str, ...]
    interaction_count: int
    pretension_section_count: int
    step_count: int
    cload_count: int
    restart_write_count: int
    excluded_thread_contact_face_count: int
    guidance_reference_node_count: int
    guidance_sample_node_count: int
    distributing_coupling_count: int
    mean_rotation_mpc_count: int
    input_file_size_bytes: int


def settling_diagnostic_case(
    case_id: str,
) -> CompleteJointSettlingDiagnosticCase:
    """Return one governed diagnostic case by identifier."""

    matches = tuple(case for case in SETTLING_DIAGNOSTIC_CASES if case.case_id == case_id.upper())

    if len(matches) != 1:
        raise KeyError(f"Unknown settling diagnostic case: {case_id}")

    return matches[0]


def _render_settling_diagnostic_step(
    case: CompleteJointSettlingDiagnosticCase,
    reference_node_id: int | None,
) -> tuple[str, ...]:
    """Render one short nonlinear settling step."""

    if case.include_pretension_section:
        if reference_node_id is None:
            raise ValueError("Pretension diagnostic requires a reference node.")
    elif reference_node_id is not None:
        raise ValueError(
            "A diagnostic without pretension must not contain a pretension reference node."
        )

    lines: list[str] = [
        f"** Settling diagnostic {case.case_id}",
        (f"*STEP, NLGEOM=YES, INC={DIAGNOSTIC_MAXIMUM_INCREMENTS}"),
        "*STATIC",
        (
            f"{DIAGNOSTIC_INITIAL_TIME_INCREMENT:.12e}, "
            f"{DIAGNOSTIC_STEP_TIME:.12e}, "
            f"{DIAGNOSTIC_MINIMUM_TIME_INCREMENT:.12e}, "
            f"{DIAGNOSTIC_MAXIMUM_TIME_INCREMENT:.12e}"
        ),
        "*BOUNDARY",
        "HEAD_MEMBER_SUPPORT_BAND, 1, 3, 0.0",
        f"{BOLT_HEAD_GUIDANCE_REFERENCE}, 1, 2, 0.0",
        f"{NUT_TRANSLATION_GUIDANCE_REFERENCE}, 1, 2, 0.0",
        f"{NUT_MEMBER_GUIDANCE_REFERENCE}, 1, 2, 0.0",
        f"{NUT_ROTATION_GUIDANCE_REFERENCE}, 1, 1, 0.0",
        f"{BOLT_HEAD_ROTATION_X_REFERENCE}, 1, 1, 0.0",
        f"{BOLT_HEAD_ROTATION_Y_REFERENCE}, 1, 1, 0.0",
        f"{NUT_ROTATION_X_REFERENCE}, 1, 1, 0.0",
        f"{NUT_ROTATION_Y_REFERENCE}, 1, 1, 0.0",
    ]

    if case.reference_force_n != 0.0:
        if reference_node_id is None:
            raise ValueError("Reference force requires a pretension reference node.")

        lines.extend(
            (
                "*CLOAD",
                (f"{reference_node_id}, 1, {case.reference_force_n:.12e}"),
            )
        )

    if reference_node_id is not None:
        lines.extend(
            (
                f"*NODE PRINT, NSET={PRETENSION_REFERENCE_SET}",
                "U",
                "RF",
            )
        )

    lines.extend(
        (
            "*NODE PRINT, NSET=HEAD_MEMBER_SUPPORT_BAND, TOTALS=ONLY",
            "RF",
            "*NODE FILE",
            "U, RF",
            "*EL FILE",
            "S, E",
            "*END STEP",
            "",
        )
    )

    return tuple(lines)


def _exclude_contact_pair_keywords(
    contact_lines: tuple[str, ...],
    *,
    excluded_pair_names: tuple[str, ...],
) -> tuple[str, ...]:
    """Remove explicitly governed contact-pair keyword blocks."""

    if not excluded_pair_names:
        return contact_lines

    excluded_names = frozenset(excluded_pair_names)

    if len(excluded_names) != len(excluded_pair_names):
        raise ValueError("Excluded diagnostic contact-pair names must be unique.")

    result: list[str] = []
    removed_names: set[str] = set()
    line_index = 0

    while line_index < len(contact_lines):
        line = contact_lines[line_index]

        if line.startswith("** Contact pair: "):
            pair_name = line.removeprefix("** Contact pair: ")

            if pair_name in excluded_names:
                block = contact_lines[line_index : line_index + 3]

                if len(block) != 3 or not block[1].startswith("*CONTACT PAIR,"):
                    raise RuntimeError(f"Unexpected rendered contact-pair block for {pair_name!r}.")

                removed_names.add(pair_name)
                line_index += 3
                continue

        result.append(line)
        line_index += 1

    missing_names = excluded_names.difference(removed_names)

    if missing_names:
        raise RuntimeError(
            "Requested diagnostic contact-pair exclusions "
            "were not found: " + ", ".join(sorted(missing_names))
        )

    return tuple(result)


def write_complete_joint_settling_diagnostic_deck(
    mesh_data: CompleteJointCalculixMeshData,
    transfer: CompleteJointCalculixTransferDefinition,
    contact: CompleteJointContactDefinition,
    boundary: CompleteJointBoundaryRegionDefinition,
    pretension: CompleteJointPretensionDefinition,
    case: CompleteJointSettlingDiagnosticCase,
    input_path: Path,
) -> CompleteJointSettlingDiagnosticDeckSummary:
    """Write one governed complete-joint diagnostic deck."""

    validate_physical_pretension_identities(
        transfer,
        contact,
        boundary,
        pretension,
    )

    boundary_regions = derive_complete_joint_boundary_regions(
        mesh_data,
        boundary,
        transfer,
        contact,
    )

    thread_surface_name = contact.pair("thread").master_surface

    if not thread_surface_name.startswith("SURF_"):
        raise ValueError("Thread-contact master surface must use the SURF_ prefix.")

    thread_boundary_name = thread_surface_name[5:]

    transfer_mesh_data, excluded_face_count = _exclude_boundary_faces_touching_protected_nodes(
        mesh_data,
        protected_boundary=pretension.section_name,
        filtered_boundary=thread_boundary_name,
    )

    transfer_summary = write_complete_joint_calculix_transfer_deck(
        transfer_mesh_data,
        transfer,
        input_path,
        internal_surface_normals={
            pretension.section_name: (
                0.0,
                0.0,
                1.0,
            ),
        },
    )

    boundary_lines = render_complete_joint_boundary_region_nsets(boundary_regions)

    contact_lines = _exclude_contact_pair_keywords(
        render_complete_joint_contact_keywords(
            contact,
            transfer,
        ),
        excluded_pair_names=(case.excluded_contact_pair_names),
    )

    reference_node_id = mesh_data.node_count + 1 if case.include_pretension_section else None

    first_guidance_node_id = (
        mesh_data.node_count + 2 if reference_node_id is not None else mesh_data.node_count + 1
    )

    guidance = _render_distributed_guidance_keywords(
        mesh_data,
        boundary_regions.region("nut_load").node_ids,
        first_guidance_node_id,
        mesh_data.element_count + 1,
        translation_sample_node_count=(DIAGNOSTIC_GUIDANCE_SAMPLE_NODE_COUNT),
        rotation_sample_node_count=(DIAGNOSTIC_ROTATION_GUIDANCE_SAMPLE_NODE_COUNT),
    )

    pretension_surface_name = _calculix_surface_name(pretension.section_name)

    text = input_path.read_text(encoding="utf-8")

    text = text.replace(
        (f"{transfer.simulation_id} complete-joint mesh-transfer verification"),
        (f"{transfer.simulation_id} complete-joint settling diagnostic {case.case_id}"),
        1,
    )

    text = text.replace(
        "** Transfer-only deck: no contact or loading",
        ("** Diagnostic deck: nonlinear contact, guidance, and controlled pretension isolation"),
        1,
    )

    smoke_marker = "** Fully constrained zero-load solver-read smoke step"

    if smoke_marker not in text:
        raise RuntimeError("Transfer smoke-step replacement marker was not found.")

    physical_lines: list[str] = [
        (f"** Complete-joint settling diagnostic {case.case_id}"),
        "**",
        *boundary_lines,
        "**",
        *guidance.lines,
        "**",
    ]

    if reference_node_id is not None:
        physical_lines.extend(
            (
                f"*NODE, NSET={PRETENSION_REFERENCE_SET}",
                (
                    f"{reference_node_id}, "
                    "0.000000000000e+00, "
                    "0.000000000000e+00, "
                    f"{pretension.axial_position_mm:.12e}"
                ),
                (
                    "*PRE-TENSION SECTION, "
                    f"SURFACE={pretension_surface_name}, "
                    f"NODE={reference_node_id}"
                ),
                ("0.000000000000e+00, 0.000000000000e+00, 1.000000000000e+00"),
                "**",
            )
        )

    physical_lines.extend(
        (
            "** Complete-joint nonlinear contact model",
            *contact_lines,
            "**",
            *_render_settling_diagnostic_step(
                case,
                reference_node_id,
            ),
        )
    )

    marker_index = text.index(smoke_marker)

    text = text[:marker_index] + "\n".join(physical_lines)

    input_path.write_text(
        text,
        encoding="utf-8",
        newline="\n",
    )

    contact_pair_count = text.count("*CONTACT PAIR,")
    interaction_count = text.count("*SURFACE INTERACTION,")
    pretension_section_count = text.count("*PRE-TENSION SECTION,")
    step_count = text.count("*STEP,")
    cload_count = text.count("*CLOAD")
    restart_write_count = text.count("*RESTART,WRITE")

    expected_pretension_count = int(case.include_pretension_section)
    expected_cload_count = int(case.reference_force_n != 0.0)
    expected_contact_pair_count = contact.expected_contact_pair_count - len(
        case.excluded_contact_pair_names
    )

    if contact_pair_count != expected_contact_pair_count:
        raise RuntimeError("Written contact-pair count does not match the governed expectation.")

    if interaction_count != 1:
        raise RuntimeError("Diagnostic deck must contain exactly one surface interaction.")

    if pretension_section_count != expected_pretension_count:
        raise RuntimeError("Diagnostic pretension-section count is incorrect.")

    if step_count != 1:
        raise RuntimeError("Diagnostic deck must contain exactly one step.")

    if cload_count != expected_cload_count:
        raise RuntimeError("Diagnostic CLOAD count is incorrect.")

    if restart_write_count != 0:
        raise RuntimeError("Settling diagnostics must not write restart data.")

    if "ALL_NODES, 1, 3, 0.0" in text:
        raise RuntimeError("The nonphysical all-node constraint remains in the diagnostic deck.")

    boundary_region_node_count = sum(region.node_count for region in boundary_regions.regions)

    return CompleteJointSettlingDiagnosticDeckSummary(
        transfer=transfer_summary,
        case_id=case.case_id,
        reference_node_id=reference_node_id,
        applied_reference_force_n=case.reference_force_n,
        boundary_region_count=len(boundary_regions.regions),
        boundary_region_node_count=boundary_region_node_count,
        contact_pair_count=contact_pair_count,
        excluded_contact_pair_names=(case.excluded_contact_pair_names),
        interaction_count=interaction_count,
        pretension_section_count=pretension_section_count,
        step_count=step_count,
        cload_count=cload_count,
        restart_write_count=restart_write_count,
        excluded_thread_contact_face_count=excluded_face_count,
        guidance_reference_node_count=guidance.reference_node_count,
        guidance_sample_node_count=guidance.sample_node_count,
        distributing_coupling_count=(guidance.distributing_coupling_count),
        mean_rotation_mpc_count=guidance.mean_rotation_mpc_count,
        input_file_size_bytes=input_path.stat().st_size,
    )
