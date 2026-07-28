"""Configuration-driven analytical reference generation."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from threadrom.engineering.metric_thread import (
    MetricThreadBasicDimensions,
    calculate_metric_thread_basic_dimensions,
)


@dataclass(frozen=True)
class BaselineThreadReference:
    """Analytical reference for the configured baseline thread."""

    geometry_id: str
    simulation_id: str
    designation: str
    dimensions: MetricThreadBasicDimensions


def _section(
    data: dict[str, object],
    key: str,
) -> dict[str, object]:
    """Return a required TOML section."""

    value = data.get(key)

    if not isinstance(value, dict):
        raise TypeError(f"Missing or invalid configuration section: {key}")

    return cast(dict[str, object], value)


def _string(
    data: dict[str, object],
    key: str,
) -> str:
    """Return a required string."""

    value = data.get(key)

    if not isinstance(value, str) or not value.strip():
        raise TypeError(f"Missing or invalid string value: {key}")

    return value


def _number(
    data: dict[str, object],
    key: str,
) -> float:
    """Return a required numerical value."""

    value = data.get(key)

    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"Missing or invalid numerical value: {key}")

    return float(value)


def load_baseline_thread_reference(
    config_path: Path,
) -> BaselineThreadReference:
    """Load the baseline configuration and calculate thread dimensions."""

    with config_path.open("rb") as config_file:
        raw_data: dict[str, object] = tomllib.load(config_file)

    identity = _section(raw_data, "identity")
    thread = _section(raw_data, "thread")

    nominal_diameter_mm = _number(
        thread,
        "nominal_diameter_mm",
    )

    pitch_mm = _number(
        thread,
        "pitch_mm",
    )

    dimensions = calculate_metric_thread_basic_dimensions(
        nominal_diameter_mm=nominal_diameter_mm,
        pitch_mm=pitch_mm,
    )

    return BaselineThreadReference(
        geometry_id=_string(identity, "geometry_id"),
        simulation_id=_string(identity, "simulation_id"),
        designation=_string(thread, "designation"),
        dimensions=dimensions,
    )


def render_baseline_thread_report(
    reference: BaselineThreadReference,
) -> str:
    """Render the analytical reference as Markdown."""

    dimensions = reference.dimensions

    return f"""# ThreadROM Basic Thread Analytical Check

## Record information

- Geometry identity: {reference.geometry_id}
- Planned simulation identity: {reference.simulation_id}
- Thread designation: {reference.designation}
- Status: Verified analytical reference
- Scope: Ideal ISO metric basic profile

## Input parameters

| Quantity | Value |
|---|---:|
| Nominal diameter | {dimensions.nominal_diameter_mm:.6f} mm |
| Thread pitch | {dimensions.pitch_mm:.6f} mm |

## Calculated basic dimensions

| Quantity | Value |
|---|---:|
| Fundamental triangle height | {dimensions.fundamental_triangle_height_mm:.9f} mm |
| Basic pitch diameter | {dimensions.basic_pitch_diameter_mm:.9f} mm |
| Basic internal minor diameter | {dimensions.basic_internal_minor_diameter_mm:.9f} mm |
| Basic external minor diameter | {dimensions.basic_external_minor_diameter_mm:.9f} mm |
| Tensile stress area | {dimensions.tensile_stress_area_mm2:.9f} mm² |

## Interpretation

These values define the ideal analytical reference profile for the configured
M10 × 1.5 thread.

They do not yet include:

- External-thread tolerance class 6g
- Internal-thread tolerance class 6H
- Manufacturing variation
- Thread runout
- Root-radius implementation details
- CAD-kernel approximation
- Mesh discretisation effects

## Verification use

The future parametric CAD geometry must be checked against these values before
TRM-GEO-000001 can be approved.

The future finite-element model must not use manually copied thread dimensions
that conflict with this configuration-driven analytical reference.
"""