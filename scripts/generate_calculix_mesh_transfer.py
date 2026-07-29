"""Generate and solve the first grouped-mesh CalculiX deck."""

from __future__ import annotations

from pathlib import Path

from threadrom.solver.calculix_mesh_transfer import (
    evaluate_calculix_force_balance,
    load_calculix_transfer_definition,
    read_grouped_mesh_for_calculix,
    run_calculix_transfer_job,
    write_calculix_transfer_deck,
)


def main() -> None:
    """Convert the coarse grouped mesh and verify it in CalculiX."""

    project_root = Path(__file__).resolve().parents[1]

    definition = load_calculix_transfer_definition(
        project_root / "config" / "calculix_mesh_transfer.toml"
    )

    source_mesh_path = (
        project_root
        / "simulations"
        / "staging"
        / definition.mesh_id
        / "mesh_levels"
        / f"complete_bolt_{definition.mesh_level}.msh"
    )

    output_directory = (
        project_root
        / "simulations"
        / "staging"
        / definition.simulation_id
        / "mesh_transfer"
        / definition.mesh_level
    )

    input_path = output_directory / f"{definition.job_name}.inp"

    mesh_data = read_grouped_mesh_for_calculix(
        source_mesh_path,
        definition,
    )

    deck_summary = write_calculix_transfer_deck(
        mesh_data,
        definition,
        input_path,
    )

    run_result = run_calculix_transfer_job(
        project_root,
        input_path,
        definition,
    )

    force_balance = evaluate_calculix_force_balance(
        run_result.dat_path,
        definition,
    )

    node_set_rows = "\n".join(
        (f"| {name} | {len(node_ids)} |")
        for name, node_ids in sorted(mesh_data.boundary_node_sets.items())
    )

    report = f"""# TRM-SIM-000001 CalculiX Mesh-Transfer Check

## Status

The parameter-generated {definition.mesh_level} grouped bolt mesh was
converted into a CalculiX C3D4 input deck and solved successfully.

## Purpose

This is a mesh-transfer and solver-read verification model.

It is not the final threaded-joint FEM simulation.

## Transfer summary

| Quantity | Value |
|---|---:|
| Source mesh level | {definition.mesh_level} |
| Nodes | {deck_summary.node_count} |
| C3D4 elements | {deck_summary.element_count} |
| Named node sets | {deck_summary.named_node_set_count} |
| Fixed nodes | {deck_summary.fixed_node_count} |
| Loaded nodes | {deck_summary.loaded_node_count} |
| Load per node | {deck_summary.load_per_node_n:.9f} N |
| Total applied axial force | {deck_summary.total_applied_force_n:.9f} N |
| Reaction force X | {force_balance.reaction_x_n:.9f} N |
| Reaction force Y | {force_balance.reaction_y_n:.9f} N |
| Reaction force Z | {force_balance.reaction_z_n:.9f} N |
| Maximum equilibrium residual | {force_balance.maximum_absolute_residual_n:.9e} N |
| Force-balance tolerance | {definition.force_balance_tolerance_n:.9e} N |
| Input file size | {deck_summary.input_file_size_bytes} bytes |

## Preserved boundary node sets

| CalculiX node set | Node count |
|---|---:|
{node_set_rows}

## Verification model

- Element type: {definition.element_type}
- Material: linear-elastic steel
- Young's modulus: {definition.youngs_modulus_mpa:.3f} MPa
- Poisson's ratio: {definition.poissons_ratio:.6f}
- Fixed set: {definition.fixed_node_group}
- Loaded set: {definition.loaded_node_group}
- Applied force: {definition.total_axial_force_n:.3f} N in global Z
- Solver units: mm, N and MPa

## Solver outputs

| Output | Path |
|---|---|
| Input deck | `{run_result.input_path}` |
| Data file | `{run_result.dat_path}` |
| Results file | `{run_result.frd_path}` |
| Status file | `{run_result.sta_path}` |
| Standard-output log | `{run_result.stdout_log_path}` |
| Error-output log | `{run_result.stderr_log_path}` |

## Acceptance gates

The transfer gate requires:

- All first-order tetrahedra converted to C3D4 elements
- Every required Gmsh boundary group preserved as a CalculiX node set
- Fixed and loaded node sets remain disjoint
- Distributed nodal forces sum to the controlled total force
- CalculiX returns exit code zero
- No CalculiX `*ERROR` diagnostics
- Non-empty DAT, FRD and STA outputs

## Interpretation

The complete parametric bolt mesh can now move from CadQuery through STEP,
Gmsh, Meshio and into a successfully solved CalculiX model.

The medium mesh remains the provisional engineering baseline. It will be
transferred after this coarse development gate is accepted.

## Next gate

Run the same verified deck-generation path using the medium mesh and extract
the resulting displacement and reaction-force balance.
"""

    report_path = (
        project_root / "docs" / "verification" / "TRM-SIM-000001_CALCULIX_MESH_TRANSFER.md"
    )

    report_path.write_text(
        report,
        encoding="utf-8",
    )

    print("CalculiX grouped-mesh transfer: VERIFIED")
    print(f"Mesh level: {definition.mesh_level}")
    print(f"Nodes: {deck_summary.node_count}")
    print(f"C3D4 elements: {deck_summary.element_count}")
    print(f"Named node sets: {deck_summary.named_node_set_count}")
    print(f"Applied force: {deck_summary.total_applied_force_n:.6f} N")
    print(f"CalculiX return code: {run_result.return_code}")
    print(
        "Reaction force: "
        f"({force_balance.reaction_x_n:.9f}, "
        f"{force_balance.reaction_y_n:.9f}, "
        f"{force_balance.reaction_z_n:.9f}) N"
    )
    print(f"Maximum equilibrium residual: {force_balance.maximum_absolute_residual_n:.9e} N")
    print(f"Input deck: {run_result.input_path}")
    print(f"FRD results: {run_result.frd_path}")
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()
