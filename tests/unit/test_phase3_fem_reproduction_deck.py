from __future__ import annotations

from pathlib import Path

import pytest

from threadrom.case.reference_cases import (
    phase2_certification_case,
)
from threadrom.case.resolver import resolve_case
from threadrom.factory.fem_case_definition_bundle import (
    FemGuidanceGeometry,
)
from threadrom.factory.fem_profile import (
    PHASE2_CERTIFIED_FEM_PROFILE,
)
from threadrom.factory.fem_reproduction import (
    write_phase2_certified_reproduction_deck,
)
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
from threadrom.solver.complete_joint_preload import (
    load_complete_joint_preload_definition,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_certified_reproduction_deck_remains_oracle_identical(
    tmp_path: Path,
) -> None:
    profile = PHASE2_CERTIFIED_FEM_PROFILE

    transfer = load_complete_joint_calculix_transfer_definition(
        PROJECT_ROOT
        / "config"
        / "complete_joint_calculix_transfer.toml"
    )

    boundary = load_complete_joint_boundary_region_definition(
        PROJECT_ROOT
        / "config"
        / "complete_joint_boundary_regions.toml"
    )

    contact = load_complete_joint_contact_definition(
        PROJECT_ROOT
        / "config"
        / "complete_joint_contact.toml"
    )

    preload = load_complete_joint_preload_definition(
        PROJECT_ROOT
        / "config"
        / "complete_joint_preload.toml"
    )

    mesh_path = (
        PROJECT_ROOT
        / "simulations"
        / "staging"
        / transfer.mesh_id
        / "mesh"
        / transfer.source_mesh_name
    )

    if not mesh_path.is_file():
        pytest.skip(
            "Certified grouped mesh is not available."
        )

    mesh_data = read_grouped_complete_joint_mesh(
        mesh_path,
        transfer,
    )

    input_path = (
        tmp_path
        / f"{profile.oracle.run_id}.inp"
    )

    resolved_case = resolve_case(
        phase2_certification_case()
    )

    guidance_geometry = FemGuidanceGeometry(
        nominal_thread_diameter_mm=(
            resolved_case.thread_standard.nominal_diameter_mm
        ),
    )

    deck = write_phase2_certified_reproduction_deck(
        mesh_data=mesh_data,
        transfer=transfer,
        boundary=boundary,
        contact=contact,
        preload=preload,
        profile=profile,
        guidance_geometry=guidance_geometry,
        input_path=input_path,
    )

    assert input_path.is_file()
    assert deck.sha256 == profile.oracle.solver_deck_sha256
    assert input_path.stem == profile.oracle.run_id
    assert deck.guidance_reference_node_count == 8
