"""Generate a nonlinear CalculiX progress report."""

from __future__ import annotations

import argparse
from pathlib import Path

from threadrom.postprocessing.calculix_nonlinear_report import (
    NonlinearReportContext,
    write_nonlinear_progress_report,
)


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a governed Markdown report from CalculiX nonlinear-progress artifacts."
        )
    )

    parser.add_argument(
        "--progress-json",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--figure",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--pretension-validation-json",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--output",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--simulation-id",
        required=True,
    )

    parser.add_argument(
        "--mesh-id",
        required=True,
    )

    parser.add_argument(
        "--element-type",
        required=True,
    )

    parser.add_argument(
        "--mesh-level",
        required=True,
    )

    parser.add_argument(
        "--nodes",
        type=int,
        required=True,
    )

    parser.add_argument(
        "--elements",
        type=int,
        required=True,
    )

    parser.add_argument(
        "--preload-force-n",
        type=float,
        required=True,
    )

    parser.add_argument(
        "--contact-pairs",
        type=int,
        required=True,
    )

    parser.add_argument(
        "--guidance-samples",
        type=int,
        required=True,
    )

    parser.add_argument(
        "--boundary-region-nodes",
        type=int,
        required=True,
    )

    parser.add_argument(
        "--solver-description",
        required=True,
    )

    parser.add_argument(
        "--analysis-complete",
        action="store_true",
    )

    return parser.parse_args()


def main() -> None:
    """Generate the requested Markdown report."""

    arguments = _parse_arguments()

    context = NonlinearReportContext(
        simulation_id=arguments.simulation_id,
        mesh_id=arguments.mesh_id,
        element_type=arguments.element_type,
        mesh_level=arguments.mesh_level,
        node_count=arguments.nodes,
        element_count=arguments.elements,
        preload_force_n=arguments.preload_force_n,
        contact_pair_count=arguments.contact_pairs,
        guidance_sample_count=(arguments.guidance_samples),
        boundary_region_node_count=(arguments.boundary_region_nodes),
        solver_description=(arguments.solver_description),
        analysis_complete=(arguments.analysis_complete),
    )

    output_path = write_nonlinear_progress_report(
        arguments.progress_json,
        arguments.figure,
        arguments.output,
        context,
        pretension_validation_json_path=(arguments.pretension_validation_json),
    )

    print("NONLINEAR PROGRESS REPORT: GENERATED")
    print(f"Simulation: {context.simulation_id}")
    print(f"Status: {'completed' if context.analysis_complete else 'in progress'}")
    print(f"Output: {output_path}")


if __name__ == "__main__":
    main()
