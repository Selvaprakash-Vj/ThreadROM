"""Parametric construction of the ThreadROM bolt control blank."""

from __future__ import annotations

import math
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import cadquery as cq


@dataclass(frozen=True)
class BoltBlankDefinition:
    """Controlled dimensions of the baseline bolt blank."""

    geometry_id: str
    nominal_diameter_mm: float
    underhead_length_mm: float
    head_across_flats_mm: float
    head_height_mm: float

    @property
    def head_across_corners_mm(self) -> float:
        """Return the regular-hexagon dimension across corners."""

        return self.head_across_flats_mm / math.cos(math.pi / 6.0)

    @property
    def analytical_volume_mm3(self) -> float:
        """Return the ideal bolt-blank volume."""

        shank_volume = (
            math.pi
            * (self.nominal_diameter_mm / 2.0) ** 2
            * self.underhead_length_mm
        )

        head_area = (
            math.sqrt(3.0)
            / 2.0
            * self.head_across_flats_mm**2
        )

        head_volume = head_area * self.head_height_mm

        return shank_volume + head_volume


@dataclass(frozen=True)
class BoltBlankMeasurements:
    """Measured properties of the generated CAD solid."""

    solid_count: int
    volume_mm3: float
    x_length_mm: float
    y_length_mm: float
    z_min_mm: float
    z_max_mm: float
    is_valid: bool


def _section(
    data: Mapping[str, object],
    key: str,
) -> Mapping[str, object]:
    """Return a required TOML section."""

    value = data.get(key)

    if not isinstance(value, dict):
        raise TypeError(
            f"Missing or invalid configuration section: {key}"
        )

    return cast(Mapping[str, object], value)


def _string(
    data: Mapping[str, object],
    key: str,
) -> str:
    """Return a required string value."""

    value = data.get(key)

    if not isinstance(value, str) or not value.strip():
        raise TypeError(
            f"Missing or invalid string value: {key}"
        )

    return value


def _number(
    data: Mapping[str, object],
    key: str,
) -> float:
    """Return a required positive numerical value."""

    value = data.get(key)

    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(
            f"Missing or invalid numerical value: {key}"
        )

    numeric_value = float(value)

    if numeric_value <= 0.0:
        raise ValueError(f"{key} must be positive.")

    return numeric_value


def load_bolt_blank_definition(
    config_path: Path,
) -> BoltBlankDefinition:
    """Load the controlled bolt-blank definition."""

    with config_path.open("rb") as config_file:
        raw_data: dict[str, object] = tomllib.load(config_file)

    identity = _section(raw_data, "identity")
    bolt_blank = _section(raw_data, "bolt_blank")

    return BoltBlankDefinition(
        geometry_id=_string(identity, "geometry_id"),
        nominal_diameter_mm=_number(
            bolt_blank,
            "nominal_diameter_mm",
        ),
        underhead_length_mm=_number(
            bolt_blank,
            "underhead_length_mm",
        ),
        head_across_flats_mm=_number(
            bolt_blank,
            "head_across_flats_mm",
        ),
        head_height_mm=_number(
            bolt_blank,
            "head_height_mm",
        ),
    )


def build_bolt_blank(
    definition: BoltBlankDefinition,
) -> cq.Workplane:
    """Build the unthreaded baseline bolt control blank."""

    shank = (
        cq.Workplane("XY")
        .circle(definition.nominal_diameter_mm / 2.0)
        .extrude(definition.underhead_length_mm)
    )

    head = (
        cq.Workplane(
            "XY",
            origin=(0.0, 0.0, -definition.head_height_mm),
        )
        .polygon(
            6,
            definition.head_across_corners_mm,
        )
        .extrude(definition.head_height_mm)
    )

    return shank.union(head).clean()


def measure_bolt_blank(
    model: cq.Workplane,
) -> BoltBlankMeasurements:
    """Measure and validate the generated bolt blank."""

    solid_count = model.solids().size()

    if solid_count != 1:
        raise RuntimeError(
            f"Expected one bolt solid, found {solid_count}."
        )

    shape = cast(cq.Shape, model.val())
    bounding_box = shape.BoundingBox()

    return BoltBlankMeasurements(
        solid_count=solid_count,
        volume_mm3=shape.Volume(),
        x_length_mm=bounding_box.xlen,
        y_length_mm=bounding_box.ylen,
        z_min_mm=bounding_box.zmin,
        z_max_mm=bounding_box.zmax,
        is_valid=shape.isValid(),
    )