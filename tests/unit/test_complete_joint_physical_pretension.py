"""Tests for the complete-joint physical pretension deck."""

import math
from collections import defaultdict
from pathlib import Path

from threadrom.solver.complete_joint_boundary_regions import (
    load_complete_joint_boundary_region_definition,
)
from threadrom.solver.complete_joint_calculix_transfer import (
    load_complete_joint_calculix_transfer_definition,
    read_grouped_complete_joint_mesh,
)
from threadrom.solver.complete_joint_contact import (
    load_complete_joint_contact_definition,
)
from threadrom.solver.complete_joint_physical_pretension import (
    write_complete_joint_physical_pretension_deck,
)
from threadrom.solver.complete_joint_pretension import (
    load_complete_joint_pretension_definition,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_write_complete_joint_physical_pretension_deck(
    tmp_path: Path,
) -> None:
    """The governed preload deck contains the physical model."""

    transfer = load_complete_joint_calculix_transfer_definition(
        PROJECT_ROOT / "config" / "complete_joint_pretension_calculix_transfer.toml"
    )

    contact = load_complete_joint_contact_definition(
        PROJECT_ROOT / "config" / "complete_joint_pretension_contact.toml"
    )

    boundary = load_complete_joint_boundary_region_definition(
        PROJECT_ROOT / "config" / "complete_joint_pretension_boundary_regions.toml"
    )

    pretension = load_complete_joint_pretension_definition(
        PROJECT_ROOT / "config" / "complete_joint_pretension.toml"
    )

    mesh_data = read_grouped_complete_joint_mesh(
        PROJECT_ROOT
        / "simulations"
        / "staging"
        / transfer.mesh_id
        / "mesh"
        / transfer.source_mesh_name,
        transfer,
    )

    input_path = tmp_path / "physical_pretension.inp"

    summary = write_complete_joint_physical_pretension_deck(
        mesh_data,
        transfer,
        contact,
        boundary,
        pretension,
        input_path,
    )

    text = input_path.read_text(encoding="utf-8")

    coordinates: dict[
        int,
        tuple[float, float, float],
    ] = {}

    node_sets: dict[str, set[int]] = defaultdict(set)
    active_mode: str | None = None
    active_set: str | None = None
    generate_mode = False

    for raw_line in text.splitlines():
        line = raw_line.strip()

        if not line or line.startswith("**"):
            continue

        if line.startswith("*"):
            active_mode = None
            active_set = None
            generate_mode = False

            fields = [field.strip() for field in line.split(",")]

            keyword = fields[0].upper()

            if keyword == "*NODE":
                active_mode = "node"

            elif keyword == "*NSET":
                active_mode = "nset"

                for field in fields[1:]:
                    upper = field.upper()

                    if upper.startswith("NSET="):
                        active_set = field.split(
                            "=",
                            1,
                        )[1]

                    elif upper == "GENERATE":
                        generate_mode = True

            continue

        values = [value.strip() for value in line.split(",") if value.strip()]

        if active_mode == "node" and len(values) >= 4:
            node_id = int(values[0])

            coordinates[node_id] = (
                float(values[1]),
                float(values[2]),
                float(values[3]),
            )

        elif active_mode == "nset" and active_set:
            node_ids = [int(value) for value in values]

            if generate_mode:
                start, stop, increment = node_ids

                node_sets[active_set].update(
                    range(
                        start,
                        stop + 1,
                        increment,
                    )
                )
            else:
                node_sets[active_set].update(node_ids)

    bolt_guidance_nodes = (
        node_sets["BOLT_HEAD_GUIDANCE_SAMPLE"]
        | node_sets["BOLT_HEAD_ROTATION_X_SAMPLE"]
        | node_sets["BOLT_HEAD_ROTATION_Y_SAMPLE"]
    )

    nut_guidance_nodes = (
        node_sets["NUT_TRANSLATION_GUIDANCE_SAMPLE"]
        | node_sets["NUT_ROTATION_GUIDANCE_SAMPLE"]
        | node_sets["NUT_ROTATION_X_SAMPLE"]
        | node_sets["NUT_ROTATION_Y_SAMPLE"]
    )

    assert not (bolt_guidance_nodes & node_sets["BOLT_HEAD_SIDES"])

    assert not (nut_guidance_nodes & node_sets["NUT_INTERNAL_THREAD"])

    assert not (nut_guidance_nodes & node_sets["NUT_OUTER_HEX"])

    bolt_guidance_radii = [
        math.hypot(
            coordinates[node_id][0],
            coordinates[node_id][1],
        )
        for node_id in bolt_guidance_nodes
    ]

    nut_guidance_radii = [
        math.hypot(
            coordinates[node_id][0],
            coordinates[node_id][1],
        )
        for node_id in nut_guidance_nodes
    ]

    assert max(bolt_guidance_radii) < 7.5

    assert min(nut_guidance_radii) > 5.5
    assert max(nut_guidance_radii) < 8.0

    assert summary.reference_node_id == 76066
    assert summary.boundary_region_count == 2
    assert summary.boundary_region_node_count == 720
    assert summary.contact_pair_count == 4
    assert summary.interaction_count == 1
    assert summary.pretension_section_count == 1
    assert summary.preload_force_n == 20000.0
    assert summary.preload_checkpoint_count == 20
    assert summary.restart_write_count == 1
    assert summary.guidance_reference_node_count == 8
    assert summary.guidance_sample_node_count == 304
    assert summary.distributing_coupling_count == 3
    assert summary.mean_rotation_mpc_count == 5

    assert ("*PRE-TENSION SECTION, SURFACE=SURF_BOLT_PRETENSION_SECTION, NODE=76066") in text

    assert "HEAD_MEMBER_SUPPORT_BAND, 1, 3, 0.0" in text

    assert "76066, 1, 2.000000000000e+04" in text
    assert text.count("*STEP, NLGEOM=YES, INC=100") == 20
    assert text.count("*RESTART,WRITE,FREQUENCY=1,OVERLAY") == 1
    assert text.count("*END STEP") == 20
    assert "76066, 1, 1.000000000000e+03" in text
    assert text.count("*CONTACT PAIR,") == 4
    assert text.count("*ELEMENT, TYPE=DCOUP3D") == 3
    assert text.count("*DISTRIBUTING COUPLING,") == 3
    assert text.count("*MPC") == 5
    assert "MEANROT," in text
    assert text.count("MEANROT,") == 5
    assert "BOLT_HEAD_ROTATION_X_REFERENCE, 1, 1, 0.0" in text
    assert "BOLT_HEAD_ROTATION_Y_REFERENCE, 1, 1, 0.0" in text
    assert "NUT_ROTATION_X_REFERENCE, 1, 1, 0.0" in text
    assert "NUT_ROTATION_Y_REFERENCE, 1, 1, 0.0" in text
    assert "BOLT_HEAD_GUIDANCE_REFERENCE, 1, 2, 0.0" in text
    assert "NUT_TRANSLATION_GUIDANCE_REFERENCE, 1, 2, 0.0" in text
    assert "NUT_MEMBER_GUIDANCE_REFERENCE, 1, 2, 0.0" in text
    assert "NUT_ROTATION_GUIDANCE_REFERENCE, 1, 1, 0.0" in text
    assert "NUT_ANCHOR_XY" not in text
    assert "NUT_ANTI_SPIN_Y" not in text
    assert "ALL_NODES, 1, 3, 0.0" not in text
