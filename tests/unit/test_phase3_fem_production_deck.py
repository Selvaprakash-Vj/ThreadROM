from __future__ import annotations

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
from threadrom.factory.fem_production_deck import (
    write_fem_production_deck,
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
    read_grouped_complete_joint_mesh,
)
from threadrom.solver.complete_joint_contact import (
    load_complete_joint_contact_definition,
)
from threadrom.solver.complete_joint_preload import (
    load_complete_joint_preload_definition,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_real_production_deck_uses_resolved_guidance(
    tmp_path: Path,
) -> None:
    transfer = load_complete_joint_calculix_transfer_definition(
        PROJECT_ROOT
        / "config"
        / "complete_joint_calculix_transfer.toml"
    )
    contact = load_complete_joint_contact_definition(
        PROJECT_ROOT
        / "config"
        / "complete_joint_contact.toml"
    )
    boundary = load_complete_joint_boundary_region_definition(
        PROJECT_ROOT
        / "config"
        / "complete_joint_boundary_regions.toml"
    )

    resolved = resolve_case(
        phase2_certification_case()
    )

    bundle = build_generic_fem_definition_bundle(
        resolved,
        mesh_id=transfer.mesh_id,
        geometry_id=transfer.geometry_id,
        classification_id="phase3-production-regression",
        source_mesh_name=transfer.source_mesh_name,
        transfer_template=transfer,
        contact_template=contact,
        boundary_template=boundary,
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

    mesh = read_grouped_complete_joint_mesh(
        mesh_path,
        bundle.transfer,
    )

    preload_template = load_complete_joint_preload_definition(
        PROJECT_ROOT
        / "config"
        / "complete_joint_preload.toml"
    )

    trial = derive_initial_preload_calibration_trial(
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
        current_trial=trial,
        measurement=ClampForceMeasurement(
            under_head_force_n=20_040.0,
            nut_bearing_force_n=20_050.0,
            member_interface_force_n=20_045.0,
        ),
    )

    assert evaluation.accepted

    preload = build_accepted_complete_joint_preload_definition(
        bundle=bundle,
        evaluation=evaluation,
        preload_template=preload_template,
    )

    input_path = tmp_path / "production.inp"

    write_fem_production_deck(
        mesh_data=mesh,
        transfer=bundle.transfer,
        boundary=bundle.boundary,
        contact=bundle.contact,
        preload=preload,
        backend=PHASE2_CERTIFIED_FEM_PROFILE.backend,
        guidance_geometry=bundle.guidance_geometry,
        input_path=input_path,
    )

    assert input_path.is_file()
    assert input_path.stat().st_size > 0

    text = input_path.read_text(
        encoding="utf-8",
    )

    assert "BOLT_HEAD_GUIDANCE_REFERENCE" in text
    assert "NUT_TRANSLATION_GUIDANCE_REFERENCE" in text
    assert "NUT_MEMBER_GUIDANCE_REFERENCE" in text
    assert "NUT_ROTATION_GUIDANCE_REFERENCE" in text
