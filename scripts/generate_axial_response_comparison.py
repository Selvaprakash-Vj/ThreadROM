"""Generate the governed axial-response mesh comparison."""

from __future__ import annotations

from itertools import pairwise
from pathlib import Path

from threadrom.postprocessing.axial_response import (
    finer_relative_change_percent,
    load_axial_comparison_definition,
    summarize_axial_response,
)


def main() -> None:
    """Generate a reproducible coarse-to-medium comparison."""

    root = Path(__file__).resolve().parents[1]

    definition = load_axial_comparison_definition(
        root / "config" / "axial_response_comparison.toml"
    )

    summaries = []

    for case in definition.cases:
        dat_path = root / case.dat_relative_path

        summaries.append(
            summarize_axial_response(
                case=case,
                dat_path=dat_path,
                node_set_name=definition.node_set_name,
                applied_force_n=definition.applied_force_n,
            )
        )

    table_rows = "\n".join(
        (
            f"| {summary.level} | "
            f"{summary.simulation_id} | "
            f"{summary.loaded_node_count} | "
            f"{summary.mean_vz_mm:.12e} | "
            f"{summary.minimum_vz_mm:.12e} | "
            f"{summary.maximum_vz_mm:.12e} | "
            f"{summary.standard_deviation_vz_mm:.12e} | "
            f"{summary.coefficient_of_variation_percent:.6f} | "
            f"{summary.apparent_stiffness_n_per_mm / 1000.0:.6f} |"
        )
        for summary in summaries
    )

    comparison_rows = []

    for previous, current in pairwise(summaries):
        displacement_change = finer_relative_change_percent(
            abs(previous.mean_vz_mm),
            abs(current.mean_vz_mm),
        )

        stiffness_change = finer_relative_change_percent(
            previous.apparent_stiffness_n_per_mm,
            current.apparent_stiffness_n_per_mm,
        )

        comparison_rows.append(
            f"| {previous.level} to {current.level} | "
            f"{displacement_change:.6f}% | "
            f"{stiffness_change:.6f}% | "
            f"{max(abs(displacement_change), abs(stiffness_change)):.6f}% |"
        )

    comparison_table = "\n".join(comparison_rows)

    candidate = summaries[-2]
    reference = summaries[-1]

    candidate_displacement_difference = finer_relative_change_percent(
        abs(candidate.mean_vz_mm),
        abs(reference.mean_vz_mm),
    )

    candidate_stiffness_difference = finer_relative_change_percent(
        candidate.apparent_stiffness_n_per_mm,
        reference.apparent_stiffness_n_per_mm,
    )

    candidate_maximum_difference = max(
        abs(candidate_displacement_difference),
        abs(candidate_stiffness_difference),
    )

    candidate_is_accepted = (
        candidate_maximum_difference
        <= definition.maximum_global_response_difference_percent
    )

    acceptance_status = (
        "ACCEPTED"
        if candidate_is_accepted
        else "REJECTED"
    )

    baseline_statement = (
        f"The {candidate.level} mesh is accepted as the global-response "
        f"engineering baseline."
        if candidate_is_accepted
        else (
            f"The {candidate.level} mesh is not accepted as the "
            f"global-response engineering baseline; the {reference.level} "
            "mesh is retained."
        )
    )

    report = f"""# {definition.mesh_id} Axial Response Comparison

## Purpose

This verification compares the global axial response of the bolt-only
CalculiX transfer model across controlled mesh levels.

The model uses a total axial force of
{definition.applied_force_n:.3f} N applied equally to the nodes in
`{definition.node_set_name}`.

Because every loaded node receives the same nodal force, the arithmetic mean
of the loaded-node axial displacements is also the load-weighted,
work-conjugate displacement for this verification model.

## Results

| Mesh level | Simulation | Loaded nodes | Mean VZ (mm) | Minimum VZ (mm) | Maximum VZ (mm) | VZ standard deviation (mm) | Coefficient of variation | Apparent stiffness (kN/mm) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
{table_rows}

## Mesh-to-mesh change

Changes are calculated relative to the finer result.

| Transition | Mean-displacement change | Stiffness change | Maximum global-response difference |
|---|---:|---:|---:|
{comparison_table}

## Governed baseline decision

The global-response acceptance criterion is a maximum difference of
{definition.maximum_global_response_difference_percent:.3f}% between the
candidate mesh and the next finer reference mesh.

| Candidate | Reference | Maximum global-response difference | Limit | Status |
|---|---|---:|---:|---|
| {candidate.level} | {reference.level} | {candidate_maximum_difference:.6f}% | {definition.maximum_global_response_difference_percent:.6f}% | {acceptance_status} |

{baseline_statement}

The fine mesh is used as the reference for this bolt-only global-response
decision. The accepted baseline is intended for efficient global stiffness
and displacement studies.

This comparison does not establish convergence for:

- Thread-root stress
- Local stress concentration
- Thread-flank contact pressure
- First-thread load share
- Preload loss
- Nonlinear frictional contact
- Full joint stiffness

Those quantities require the complete threaded-joint assembly and dedicated
local mesh-convergence studies.

## Next verification gate

Use the accepted global-response baseline while developing the parametric
internally threaded nut and the first complete bolt-nut assembly. Separate
local convergence studies remain mandatory for thread stress and contact
outputs.
"""

    report_path = root / definition.report_relative_path

    report_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    report_path.write_text(
        report,
        encoding="utf-8",
        newline="\n",
    )

    print("Axial-response comparison: GENERATED")

    for summary in summaries:
        print()
        print(summary.level.upper())
        print(f"Mean axial displacement: {summary.mean_vz_mm:.12e} mm")
        print(f"Apparent axial stiffness: {summary.apparent_stiffness_n_per_mm / 1000.0:.6f} kN/mm")

    print()
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()
