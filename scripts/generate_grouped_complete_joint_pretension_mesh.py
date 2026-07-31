"""Generate the grouped complete-joint pretension mesh."""

from __future__ import annotations

from pathlib import Path

from threadrom.engineering.baseline_assembly import (
    load_baseline_assembly,
)
from threadrom.geometry.complete_nut import (
    load_complete_nut_definitions,
)
from threadrom.geometry.threaded_shank import (
    load_threaded_shank_definitions,
)
from threadrom.meshing.complete_joint_mesh_definition import (
    load_complete_joint_mesh_definition,
    resolve_complete_joint_mesh_sizes,
)
from threadrom.meshing.complete_joint_surface_classification import (
    load_complete_joint_surface_definition,
)
from threadrom.meshing.grouped_complete_joint_pretension_mesh import (
    generate_grouped_complete_joint_pretension_mesh,
)
from threadrom.meshing.mesh_levels import (
    load_mesh_level_policy,
    resolve_mesh_levels,
)
from threadrom.meshing.nut_surface_classification import (
    load_nut_surface_classification_definition,
)
from threadrom.meshing.surface_classification import (
    load_surface_classification_definition,
)
from threadrom.solver.complete_joint_pretension import (
    load_complete_joint_pretension_definition,
)


def main() -> None:
    """Generate and verify the pretension-capable mesh."""

    project_root = Path(__file__).resolve().parents[1]

    assembly = load_baseline_assembly(
        project_root
        / "config"
        / "baseline_assembly.toml"
    )

    bolt_blank, bolt_thread = (
        load_threaded_shank_definitions(project_root)
    )

    nut_blank, nut_thread = (
        load_complete_nut_definitions(project_root)
    )

    mesh_definition = (
        load_complete_joint_mesh_definition(
            project_root
            / "config"
            / "complete_joint_pretension_mesh.toml"
        )
    )

    pretension_definition = (
        load_complete_joint_pretension_definition(
            project_root
            / "config"
            / "complete_joint_pretension.toml"
        )
    )

    bolt_levels = resolve_mesh_levels(
        load_mesh_level_policy(
            project_root
            / "config"
            / mesh_definition.bolt_mesh_level_policy
        ),
        bolt_thread,
    )

    nut_levels = resolve_mesh_levels(
        load_mesh_level_policy(
            project_root
            / "config"
            / mesh_definition.nut_mesh_level_policy
        ),
        nut_thread,
    )

    sizes = resolve_complete_joint_mesh_sizes(
        mesh_definition,
        bolt_levels,
        nut_levels,
    )

    joint_definition = (
        load_complete_joint_surface_definition(
            project_root
            / "config"
            / "complete_joint_surface_classification.toml"
        )
    )

    bolt_definition = (
        load_surface_classification_definition(
            project_root
            / "config"
            / "surface_classification.toml"
        )
    )

    nut_definition = (
        load_nut_surface_classification_definition(
            project_root
            / "config"
            / "nut_surface_classification.toml"
        )
    )

    step_path = (
        project_root
        / "simulations"
        / "staging"
        / assembly.assembly_id
        / "geometry"
        / "complete_joint_assembly.step"
    )

    msh_path = (
        project_root
        / "simulations"
        / "staging"
        / mesh_definition.mesh_id
        / "mesh"
        / (
            "complete_joint_pretension_grouped_"
            f"{sizes.level_name}_first_order.msh"
        )
    )

    result = (
        generate_grouped_complete_joint_pretension_mesh(
            step_path=step_path,
            msh_path=msh_path,
            assembly=assembly,
            bolt_blank=bolt_blank,
            nut_blank=nut_blank,
            mesh_definition=mesh_definition,
            sizes=sizes,
            joint_definition=joint_definition,
            bolt_definition=bolt_definition,
            nut_definition=nut_definition,
            pretension_definition=pretension_definition,
        )
    )

    print("PRETENSION-CAPABLE JOINT MESH: VERIFIED")
    print(f"Mesh ID: {mesh_definition.mesh_id}")
    print(f"Mesh level: {sizes.level_name}")
    print(
        "Bolt fragments: "
        f"{result.fragment.fragment_tags}"
    )
    print(
        "Pretension section: "
        f"{result.fragment.section_surface_tag}"
    )
    print(
        "Section position: "
        f"{result.fragment.section_center_z_mm:.9f} mm"
    )
    print(
        "Section area: "
        f"{result.fragment.section_area_mm2:.9f} mm^2"
    )
    print(f"Nodes: {result.meshio_node_count}")
    print(
        "C3D4 tetrahedra: "
        f"{result.meshio_tetrahedron_count}"
    )
    print(
        "Boundary triangles: "
        f"{result.meshio_triangle_count}"
    )
    print(
        "Section nodes: "
        f"{result.section_node_count}"
    )
    print(
        "Shared fragment nodes: "
        f"{result.shared_fragment_node_count}"
    )
    print(f"Output: {msh_path}")


if __name__ == "__main__":
    main()
