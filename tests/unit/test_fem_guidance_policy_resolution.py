from __future__ import annotations

import math
from pathlib import Path

from threadrom.factory.fem_guidance import (
    resolve_fem_distributed_guidance_policy,
)
from threadrom.factory.fem_profile import (
    FemDistributedGuidancePolicy,
)
from threadrom.solver.complete_joint_calculix_transfer import (
    load_complete_joint_calculix_transfer_definition,
    read_grouped_complete_joint_mesh,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_resolve_guidance_policy_preserves_certified_m10_safe_zone() -> None:
    transfer = load_complete_joint_calculix_transfer_definition(
        PROJECT_ROOT
        / "config"
        / "complete_joint_pretension_calculix_transfer.toml"
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

    governed = FemDistributedGuidancePolicy(
        translation_sample_node_count=40,
        rotation_sample_node_count=20,
        bolt_head_safe_radius_fraction=0.9375,
        nut_inner_annulus_fraction=1.0 / 6.0,
        nut_outer_inset_fraction=0.0,
    )

    resolved = resolve_fem_distributed_guidance_policy(
        mesh_data=mesh_data,
        policy=governed,
        nominal_thread_diameter_mm=10.0,
    )

    assert resolved.translation_sample_node_count == 40
    assert resolved.rotation_sample_node_count == 20

    assert math.isclose(
        resolved.bolt_head_max_radius_mm,
        7.5,
        rel_tol=0.0,
        abs_tol=1.0e-9,
    )

    assert math.isclose(
        resolved.nut_min_radius_mm,
        5.5,
        rel_tol=0.0,
        abs_tol=1.0e-9,
    )

    assert math.isclose(
        resolved.nut_max_radius_mm,
        8.0,
        rel_tol=0.0,
        abs_tol=1.0e-9,
    )



def test_resolved_guidance_preserves_certified_m10_safe_node_population() -> None:
    transfer = load_complete_joint_calculix_transfer_definition(
        PROJECT_ROOT
        / "config"
        / "complete_joint_pretension_calculix_transfer.toml"
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

    governed = FemDistributedGuidancePolicy(
        translation_sample_node_count=40,
        rotation_sample_node_count=20,
        bolt_head_safe_radius_fraction=0.9375,
        nut_inner_annulus_fraction=1.0 / 6.0,
        nut_outer_inset_fraction=0.0,
    )

    resolved = resolve_fem_distributed_guidance_policy(
        mesh_data=mesh_data,
        policy=governed,
        nominal_thread_diameter_mm=10.0,
    )

    def boundary(name: str) -> set[int]:
        matches = tuple(
            node_ids
            for boundary_name, node_ids
            in mesh_data.boundary_node_sets.items()
            if boundary_name.casefold() == name.casefold()
        )

        assert len(matches) == 1
        return set(matches[0])

    def radius(node_id: int) -> float:
        return math.hypot(
            float(mesh_data.points_mm[node_id - 1, 0]),
            float(mesh_data.points_mm[node_id - 1, 1]),
        )

    bolt_interior = (
        boundary("BOLT_HEAD_TOP")
        - boundary("BOLT_HEAD_SIDES")
    )

    nut_interior = (
        boundary("NUT_UPPER_BEARING")
        - boundary("NUT_INTERNAL_THREAD")
        - boundary("NUT_OUTER_HEX")
    )

    legacy_bolt = {
        node_id
        for node_id in bolt_interior
        if -1.0e-12 < radius(node_id) < 7.5
    }

    resolved_bolt = {
        node_id
        for node_id in bolt_interior
        if (
            -1.0e-12
            < radius(node_id)
            < resolved.bolt_head_max_radius_mm
        )
    }

    legacy_nut = {
        node_id
        for node_id in nut_interior
        if 5.5 < radius(node_id) < 8.0
    }

    resolved_nut = {
        node_id
        for node_id in nut_interior
        if (
            resolved.nut_min_radius_mm
            < radius(node_id)
            < resolved.nut_max_radius_mm
        )
    }

    assert resolved_bolt == legacy_bolt
    assert resolved_nut == legacy_nut

    assert len(resolved_bolt) == 241
    assert len(resolved_nut) == 323



def test_nominal_thread_radius_preserves_m10_guidance_across_governed_meshes() -> None:
    governed = FemDistributedGuidancePolicy(
        translation_sample_node_count=40,
        rotation_sample_node_count=20,
        bolt_head_safe_radius_fraction=0.9375,
        nut_inner_annulus_fraction=1.0 / 6.0,
        nut_outer_inset_fraction=0.0,
    )

    for transfer_name in (
        "complete_joint_calculix_transfer.toml",
        "complete_joint_pretension_calculix_transfer.toml",
    ):
        transfer = load_complete_joint_calculix_transfer_definition(
            PROJECT_ROOT
            / "config"
            / transfer_name
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

        resolved = resolve_fem_distributed_guidance_policy(
            mesh_data=mesh_data,
            policy=governed,
            nominal_thread_diameter_mm=10.0,
        )

        assert math.isclose(
            resolved.bolt_head_max_radius_mm,
            7.5,
            rel_tol=0.0,
            abs_tol=1.0e-9,
        )
        assert math.isclose(
            resolved.nut_min_radius_mm,
            5.5,
            rel_tol=0.0,
            abs_tol=1.0e-9,
        )
        assert math.isclose(
            resolved.nut_max_radius_mm,
            8.0,
            rel_tol=0.0,
            abs_tol=1.0e-9,
        )

        def boundary(name: str) -> set[int]:
            matches = tuple(
                node_ids
                for boundary_name, node_ids
                in mesh_data.boundary_node_sets.items()
                if boundary_name.casefold() == name.casefold()
            )
            assert len(matches) == 1
            return set(matches[0])

        def radius(node_id: int) -> float:
            return math.hypot(
                float(mesh_data.points_mm[node_id - 1, 0]),
                float(mesh_data.points_mm[node_id - 1, 1]),
            )

        nut_interior = (
            boundary("NUT_UPPER_BEARING")
            - boundary("NUT_INTERNAL_THREAD")
            - boundary("NUT_OUTER_HEX")
        )

        legacy_nut = {
            node_id
            for node_id in nut_interior
            if 5.5 < radius(node_id) < 8.0
        }

        resolved_nut = {
            node_id
            for node_id in nut_interior
            if (
                resolved.nut_min_radius_mm
                < radius(node_id)
                < resolved.nut_max_radius_mm
            )
        }

        assert resolved_nut == legacy_nut
        assert len(resolved_nut) == 323
