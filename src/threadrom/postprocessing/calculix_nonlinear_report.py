"""Generate Markdown reports for nonlinear CalculiX progress."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class NonlinearReportContext:
    """Governed metadata for one nonlinear simulation report."""

    simulation_id: str
    mesh_id: str
    element_type: str
    mesh_level: str
    node_count: int
    element_count: int
    preload_force_n: float
    contact_pair_count: int
    guidance_sample_count: int
    boundary_region_node_count: int
    solver_description: str
    analysis_complete: bool = False


def _require_mapping(
    value: object,
    label: str,
) -> dict[str, object]:
    if not isinstance(value, dict):
        raise TypeError(f"{label} must be a JSON object.")

    result: dict[str, object] = {}

    for key, item in value.items():
        if not isinstance(key, str):
            raise TypeError(f"{label} contains a non-string key.")

        result[key] = item

    return result


def _require_list(
    value: object,
    label: str,
) -> list[object]:
    if not isinstance(value, list):
        raise TypeError(f"{label} must be a JSON array.")

    return value


def _require_int(
    mapping: dict[str, object],
    key: str,
) -> int:
    value = mapping.get(key)

    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{key} must be an integer.")

    return value


def _require_float(
    mapping: dict[str, object],
    key: str,
) -> float:
    value = mapping.get(key)

    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise TypeError(f"{key} must be numeric.")

    return float(value)


def _optional_mapping(
    value: object,
    label: str,
) -> dict[str, object] | None:
    if value is None:
        return None

    return _require_mapping(
        value,
        label,
    )


def _markdown_relative_path(
    report_path: Path,
    artifact_path: Path,
) -> str:
    relative = os.path.relpath(
        artifact_path.resolve(),
        report_path.parent.resolve(),
    )

    return relative.replace("\\", "/")


def _accepted_increment_rows(
    raw_increments: list[object],
    preload_force_n: float,
) -> list[str]:
    rows: list[str] = []

    for index, raw_increment in enumerate(
        raw_increments,
        start=1,
    ):
        increment = _require_mapping(
            raw_increment,
            f"Accepted increment {index}",
        )

        step = _require_int(
            increment,
            "step",
        )

        increment_number = _require_int(
            increment,
            "increment",
        )

        attempt = _require_int(
            increment,
            "attempt",
        )

        iterations = _require_int(
            increment,
            "iterations",
        )

        step_time = _require_float(
            increment,
            "step_time",
        )

        increment_time = _require_float(
            increment,
            "increment_time",
        )

        nominal_load_n = preload_force_n * step_time

        rows.append(
            "| "
            f"{step} | "
            f"{increment_number} | "
            f"{attempt} | "
            f"{iterations} | "
            f"{step_time:.6f} | "
            f"{increment_time:.6f} | "
            f"{nominal_load_n:.3f} N |"
        )

    return rows


def write_nonlinear_progress_report(
    progress_json_path: Path,
    convergence_figure_path: Path,
    output_path: Path,
    context: NonlinearReportContext,
) -> Path:
    """Write a governed nonlinear-progress Markdown report."""

    if not progress_json_path.exists():
        raise FileNotFoundError(progress_json_path)

    if not convergence_figure_path.exists():
        raise FileNotFoundError(convergence_figure_path)

    raw_payload: object = json.loads(progress_json_path.read_text(encoding="utf-8"))

    payload = _require_mapping(
        raw_payload,
        "Progress payload",
    )

    accepted_count = _require_int(
        payload,
        "accepted_increment_count",
    )

    iteration_count = _require_int(
        payload,
        "iteration_record_count",
    )

    accepted_increments = _require_list(
        payload.get("accepted_increments"),
        "accepted_increments",
    )

    latest_accepted = _optional_mapping(
        payload.get("latest_accepted_increment"),
        "latest_accepted_increment",
    )

    latest_iteration = _optional_mapping(
        payload.get("latest_iteration"),
        "latest_iteration",
    )

    status = "Completed" if context.analysis_complete else "In progress"

    progress_percent = 0.0
    nominal_load_n = 0.0

    if latest_accepted is not None:
        latest_step_time = _require_float(
            latest_accepted,
            "step_time",
        )

        progress_percent = 100.0 * latest_step_time

        nominal_load_n = context.preload_force_n * latest_step_time

    figure_reference = _markdown_relative_path(
        output_path,
        convergence_figure_path,
    )

    accepted_rows = _accepted_increment_rows(
        accepted_increments,
        context.preload_force_n,
    )

    if not accepted_rows:
        accepted_rows = ["| ? | ? | ? | ? | ? | ? | ? |"]

    latest_iteration_lines = [
        "| Quantity | Value |",
        "|---|---:|",
    ]

    if latest_iteration is None:
        latest_iteration_lines.append("| Current nonlinear iteration | Not available |")
    else:
        latest_iteration_lines.extend(
            [
                (f"| Step | {_require_int(latest_iteration, 'step')} |"),
                (f"| Increment | {_require_int(latest_iteration, 'increment')} |"),
                (f"| Attempt | {_require_int(latest_iteration, 'attempt')} |"),
                (f"| Iteration | {_require_int(latest_iteration, 'iteration')} |"),
                (f"| Contact elements | {_require_int(latest_iteration, 'contact_elements')} |"),
                (
                    "| Residual force | "
                    f"{_require_float(latest_iteration, 'residual_force_percent'):.6g}% |"
                ),
                (
                    "| Displacement correction | "
                    f"{_require_float(latest_iteration, 'correction_displacement_percent'):.6g}% |"
                ),
            ]
        )

    lines = [
        (f"# {context.simulation_id} Nonlinear Pretension Progress Report"),
        "",
        "## Status",
        "",
        (
            "This report is generated automatically from the "
            "CalculiX `.sta` and `.cvg` progress files."
        ),
        "",
        "| Quantity | Value |",
        "|---|---:|",
        f"| Status | {status} |",
        (f"| Accepted increments | {accepted_count} |"),
        (f"| Nonlinear iteration records | {iteration_count} |"),
        (f"| Accepted step progress | {progress_percent:.2f}% |"),
        (f"| Nominal ramped preload | {nominal_load_n:.3f} N |"),
        "",
        (
            "The nominal ramped preload is derived from the "
            "accepted step time and configured target preload. "
            "It is not an equilibrium verification."
        ),
        "",
        "## Model summary",
        "",
        "| Quantity | Value |",
        "|---|---:|",
        (f"| Simulation ID | {context.simulation_id} |"),
        f"| Mesh ID | {context.mesh_id} |",
        (f"| Element formulation | {context.element_type} |"),
        (f"| Mesh level | {context.mesh_level} |"),
        f"| Nodes | {context.node_count} |",
        (f"| Elements | {context.element_count} |"),
        (f"| Target preload | {context.preload_force_n:.3f} N |"),
        (f"| Contact pairs | {context.contact_pair_count} |"),
        (f"| Guidance samples | {context.guidance_sample_count} |"),
        (f"| Boundary-region nodes | {context.boundary_region_node_count} |"),
        (f"| Solver | {context.solver_description} |"),
        "",
        "## Accepted increments",
        "",
        ("| Step | Increment | Attempt | Iterations | Step time | Increment time | Nominal load |"),
        "|---:|---:|---:|---:|---:|---:|---:|",
        *accepted_rows,
        "",
        "## Latest nonlinear state",
        "",
        *latest_iteration_lines,
        "",
        "## Convergence evidence",
        "",
        (f"![Nonlinear convergence history]({figure_reference})"),
        "",
        (
            "The figure uses a symmetric logarithmic scale so that "
            "large initial residuals and small converged values can "
            "be shown in the same chart."
        ),
        "",
        "## Current interpretation",
        "",
    ]

    if accepted_count > 0:
        lines.extend(
            [
                (f"- CalculiX has accepted {accepted_count} nonlinear increment(s)."),
                (
                    "- The model has progressed beyond solver "
                    "initialization into a converged nonlinear "
                    "contact solution."
                ),
            ]
        )
    else:
        lines.append("- No nonlinear increment has yet been accepted.")

    lines.extend(
        [
            (
                "- The current report tracks numerical progress; "
                "it does not yet establish final structural "
                "equilibrium or physical validation."
            ),
            "",
            "## Current limitations",
            "",
            (
                "- Final conclusions require successful solver "
                "completion and a CalculiX return code of zero."
            ),
            (
                "- Reaction-force equilibrium has not yet been "
                "evaluated from the completed result output."
            ),
            (
                "- The current deck does not contain independent "
                "thread-turn result sets or per-turn contact-force "
                "print requests."
            ),
            (
                "- Final stress, strain, displacement and contact "
                "pressure interpretation must wait for completed "
                "result files."
            ),
            "",
            "## Artifacts",
            "",
            "| Artifact | Path |",
            "|---|---|",
            (f"| Progress JSON | `{progress_json_path.resolve()}` |"),
            (f"| Convergence figure | `{convergence_figure_path.resolve()}` |"),
            "",
            "## Next gate",
            "",
            (
                "Complete the nonlinear solve, verify solver exit "
                "status, extract the final reaction and displacement "
                "results, and perform the equilibrium check."
            ),
            "",
        ]
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        "\n".join(lines),
        encoding="utf-8",
        newline="\n",
    )

    return output_path
