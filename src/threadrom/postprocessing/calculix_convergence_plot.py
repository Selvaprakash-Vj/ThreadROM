"""Generate governed CalculiX convergence figures."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure


@dataclass(frozen=True)
class IterationPoint:
    """One plotted nonlinear convergence iteration."""

    global_iteration: int
    step: int
    increment: int
    attempt: int
    iteration: int
    contact_elements: int
    residual_force_percent: float
    correction_displacement_percent: float


def _as_string_mapping(
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


def load_progress_payload(
    input_path: Path,
) -> dict[str, object]:
    """Load and validate a progress JSON payload."""

    raw: object = json.loads(input_path.read_text(encoding="utf-8"))

    return _as_string_mapping(
        raw,
        "Progress payload",
    )


def load_iteration_points(
    input_path: Path,
) -> tuple[IterationPoint, ...]:
    """Load plotting points from a progress artifact."""

    payload = load_progress_payload(input_path)
    raw_iterations = payload.get("iterations")

    if not isinstance(raw_iterations, list):
        raise TypeError("iterations must be a JSON array.")

    points: list[IterationPoint] = []

    for global_iteration, raw_record in enumerate(
        raw_iterations,
        start=1,
    ):
        record = _as_string_mapping(
            raw_record,
            f"Iteration record {global_iteration}",
        )

        points.append(
            IterationPoint(
                global_iteration=global_iteration,
                step=_require_int(record, "step"),
                increment=_require_int(
                    record,
                    "increment",
                ),
                attempt=_require_int(
                    record,
                    "attempt",
                ),
                iteration=_require_int(
                    record,
                    "iteration",
                ),
                contact_elements=_require_int(
                    record,
                    "contact_elements",
                ),
                residual_force_percent=(
                    _require_float(
                        record,
                        "residual_force_percent",
                    )
                ),
                correction_displacement_percent=(
                    _require_float(
                        record,
                        "correction_displacement_percent",
                    )
                ),
            )
        )

    return tuple(points)


def write_convergence_figure(
    input_path: Path,
    output_path: Path,
) -> Path:
    """Write a portfolio-ready convergence figure."""

    payload = load_progress_payload(input_path)
    points = load_iteration_points(input_path)

    if not points:
        raise ValueError("Cannot plot an empty iteration history.")

    accepted_count = _require_int(
        payload,
        "accepted_increment_count",
    )

    global_iterations = [point.global_iteration for point in points]

    residual_force = [point.residual_force_percent for point in points]

    displacement_correction = [point.correction_displacement_percent for point in points]

    figure = Figure(
        figsize=(11.0, 6.5),
        constrained_layout=True,
    )

    FigureCanvasAgg(figure)
    axis = figure.subplots()

    axis.plot(
        global_iterations,
        residual_force,
        marker="o",
        markersize=3.5,
        linewidth=1.5,
        label="Residual force",
    )

    axis.plot(
        global_iterations,
        displacement_correction,
        marker="s",
        markersize=3.0,
        linewidth=1.3,
        label="Displacement correction",
    )

    segment_starts: list[tuple[int, tuple[int, int, int]]] = []

    previous_key: tuple[int, int, int] | None = None

    for point in points:
        key = (
            point.step,
            point.increment,
            point.attempt,
        )

        if key != previous_key:
            segment_starts.append(
                (
                    point.global_iteration,
                    key,
                )
            )

            previous_key = key

    for start, key in segment_starts:
        if start > 1:
            axis.axvline(
                start - 0.5,
                linestyle="--",
                linewidth=0.8,
                alpha=0.7,
            )

        step, increment, attempt = key

        axis.text(
            start,
            0.98,
            (f"S{step} I{increment} A{attempt}"),
            transform=axis.get_xaxis_transform(),
            fontsize=8,
            verticalalignment="top",
        )

    axis.set_title(
        "ThreadROM C3D10 Nonlinear Convergence\n"
        f"Accepted increments: {accepted_count} | "
        f"Iteration records: {len(points)}"
    )

    axis.set_xlabel("Global nonlinear iteration")

    axis.set_ylabel("Convergence metric (%)")

    axis.set_yscale(
        "symlog",
        linthresh=0.1,
    )

    axis.grid(
        True,
        which="both",
        linestyle=":",
        linewidth=0.7,
        alpha=0.7,
    )

    axis.legend()
    axis.margins(x=0.02)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    figure.savefig(
        output_path,
        dpi=220,
        bbox_inches="tight",
    )

    figure.clear()

    return output_path
