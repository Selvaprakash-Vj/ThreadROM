"""Regression for real Phase-3 aluminium pilot catalog propagation."""

from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
import json
import math
import tomllib

import pytest

from threadrom.case.reference_cases import phase2_certification_case
from threadrom.case.resolver import resolve_case
from threadrom.case.serialization import case_sha256
from threadrom.factory.diversified_doe_design import _build_case
from threadrom.factory.fem_case_definition_bundle import (
    build_generic_fem_definition_bundle,
)
from threadrom.factory.preload_calibration_seed import (
    derive_analytical_thermal_preload_seed_v2,
)
from threadrom.materials.baseline_catalog import (
    BASELINE_MATERIAL_CATALOG,
)
from threadrom.materials.diversified_candidate_catalog import (
    DIVERSIFIED_CANDIDATE_MATERIAL_CATALOG,
)
from threadrom.solver.complete_joint_boundary_regions import (
    load_complete_joint_boundary_region_definition,
)
from threadrom.solver.complete_joint_calculix_transfer import (
    load_complete_joint_calculix_transfer_definition,
    read_grouped_complete_joint_mesh,
    render_complete_joint_calculix_model,
)
from threadrom.solver.complete_joint_contact import (
    load_complete_joint_contact_definition,
)


ROOT = Path(__file__).resolve().parents[1]

PILOT_HASH = (
    "db4f5abb0986d0527a06fd72849bfc948041448f6a8a320a4aad0a0858028d53"
)


def _pilot():
    policy = tomllib.loads(
        (ROOT / "config/phase3_diversified_doe.toml")
        .read_text(encoding="utf-8-sig")
    )

    manifest = json.loads(
        (ROOT / "docs/phase3_diversified_doe/design_proposal.json")
        .read_text(encoding="utf-8-sig")
    )

    assert len(manifest["cases"]) == 72
    assert manifest["fem_execution_authorized"] is False
    assert policy["governance"]["solver_launch_authorized"] is False

    pilot = next(
        item for item in manifest["cases"]
        if item["proposal_id"] == manifest["first_pilot_proposal_id"]
    )

    size = next(
        item for item in policy["size_candidates"]
        if item["designation"] == pilot["thread_designation"]
    )

    case, _ = _build_case(
        policy,
        size,
        pilot["member_material_id"],
        tuple(pilot["normalized_coordinates"]),
    )

    assert pilot["case_hash"] == case_sha256(case) == PILOT_HASH
    assert pilot["historical_case_id"] is None
    assert pilot["fem_execution_authorized"] is False

    assert json.loads(
        json.dumps(asdict(case), sort_keys=True)
    ) == pilot["product_case"]

    return resolve_case(
        case,
        material_catalog=DIVERSIFIED_CANDIDATE_MATERIAL_CATALOG,
    )


def _bundle(resolved, *, catalog=None):
    transfer = load_complete_joint_calculix_transfer_definition(
        ROOT / "config/complete_joint_calculix_transfer.toml"
    )
    contact = load_complete_joint_contact_definition(
        ROOT / "config/complete_joint_contact.toml"
    )
    boundary = load_complete_joint_boundary_region_definition(
        ROOT / "config/complete_joint_boundary_regions.toml"
    )

    kwargs = {
        "mesh_id": transfer.mesh_id,
        "geometry_id": transfer.geometry_id,
        "classification_id": "diversified-pilot-preflight-only",
        "source_mesh_name": transfer.source_mesh_name,
        "transfer_template": transfer,
        "contact_template": contact,
        "boundary_template": boundary,
    }

    if catalog is not None:
        kwargs["material_catalog"] = catalog

    return build_generic_fem_definition_bundle(
        resolved, **kwargs
    )


def test_baseline_preload_seed_behavior_unchanged():
    resolved = resolve_case(phase2_certification_case())

    implicit = derive_analytical_thermal_preload_seed_v2(
        resolved
    )
    explicit = derive_analytical_thermal_preload_seed_v2(
        resolved,
        material_catalog=BASELINE_MATERIAL_CATALOG,
    )

    assert implicit == explicit


def test_real_aluminium_pilot_uses_candidate_catalog():
    resolved = _pilot()

    with pytest.raises(
        ValueError,
        match="Unknown ThreadROM material family",
    ):
        _bundle(resolved)

    bundle = _bundle(
        resolved,
        catalog=DIVERSIFIED_CANDIDATE_MATERIAL_CATALOG,
    )

    physics = bundle.preparation.physics

    assert bundle.preparation.identity.case_hash == PILOT_HASH
    assert physics.target_preload_n == 15000.0
    assert physics.youngs_modulus_mpa == 210000.0
    assert physics.member_youngs_modulus_mpa == 70000.0
    assert physics.member_poissons_ratio == 0.33

    assert bundle.transfer.member_youngs_modulus_mpa == 70000.0
    assert bundle.transfer.member_poissons_ratio == 0.33

    seed = derive_analytical_thermal_preload_seed_v2(
        resolved,
        material_catalog=DIVERSIFIED_CANDIDATE_MATERIAL_CATALOG,
    )

    assert bundle.calibration_seed == seed
    assert seed.target_force_n == 15000.0
    assert seed.member_compliance_mm_per_n > 0.0
    assert math.isfinite(seed.predicted_delta_temperature_c)
    assert seed.predicted_delta_temperature_c < 0.0

    print(
        "PASS: real aluminium pilot bundle and preload seed.",
        "Predicted thermal delta:",
        seed.predicted_delta_temperature_c,
    )


def test_verified_reference_mesh_renders_pilot_model_in_memory():
    resolved = _pilot()

    atlas = json.loads(
        (ROOT / "docs/phase3_fem_atlas/atlas.json")
        .read_text(encoding="utf-8-sig")
    )

    reference = next(
        item for item in atlas["cases"]
        if item["case_id"] == "D-BND-001"
    )

    record_path = (
        ROOT
        / reference["primary_run_directory"]
        / "production_doe_calibration_solver_preparation_record.json"
    )

    if not record_path.is_file():
        pytest.skip("Historical reference metadata is unavailable.")

    record = json.loads(
        record_path.read_text(encoding="utf-8-sig")
    )

    artifacts = record["prepared_artifacts"]

    mesh_path = (
        ROOT / artifacts["mesh_relative_path"]
    ).resolve()

    expected_parent = (
        ROOT
        / "simulations/staging/phase3_cp8_production_doe/"
          "TRM-PDOE-C01/prepared_cases/"
          "trm_fem_a5e86e9150fb/mesh"
    ).resolve()

    assert mesh_path.parent == expected_parent

    if not mesh_path.is_file():
        pytest.skip("Historical case-specific mesh is unavailable.")

    assert sha256(mesh_path.read_bytes()).hexdigest() == (
        artifacts["mesh_sha256"].lower()
    )

    bundle = _bundle(
        resolved,
        catalog=DIVERSIFIED_CANDIDATE_MATERIAL_CATALOG,
    )

    grouped_mesh = read_grouped_complete_joint_mesh(
        mesh_path,
        bundle.transfer,
    )

    model = render_complete_joint_calculix_model(
        grouped_mesh,
        bundle.transfer,
    )

    assert model is not None

    print(
        "PASS: actual aluminium pilot rendered on the "
        "checksum-verified historical mesh."
    )
    print(
        "Mesh provenance binding and case-specific calibration: "
        "NOT YET CERTIFIED."
    )
