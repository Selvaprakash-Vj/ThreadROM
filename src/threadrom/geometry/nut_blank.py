"""Parametric blank geometry for the baseline hexagonal nut."""

from __future__ import annotations

import math
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import cadquery as cq

from threadrom.engineering.baseline_assembly import (
    load_baseline_assembly,
)
from threadrom.engineering.baseline_reference import (
    load_baseline_thread_reference,
)


@dataclass(frozen=True)
class NutBlankDefinition:
    """Controlled dimensions for an unthreaded hexagonal nut blank."""

    geometry_id: str
    assembly_id: str
    component_name: str
    nominal_diameter_mm: float
    pitch_mm: float
    across_flats_mm: float
    thickness_mm: float
    bore_diameter_mm: float
    bore_basis: str
    chamfer_included: bool

    @property
    def circumscribed_radius_mm(self) -> float:
        """Return the radius through the hexagon corners."""

        return self.across_flats_mm / math.sqrt(3.0)

    @property
    def across_corners_mm(self) -> float:
        """Return the maximum corner-to-corner hexagon width."""

        return 2.0 * self.circumscribed_radius_mm

    @property
    def gross_hex_area_mm2(self) -> float:
        """Return the cross-sectional area of the regular hexagon."""

        return (
            math.sqrt(3.0)
            / 2.0
            * self.across_flats_mm**2
        )

    @property
    def analytical_volume_mm3(self) -> float:
        """Return the ideal blank volume after subtracting the bore."""

        bore_area_mm2 = (
            math.pi
            / 4.0
            * self.bore_diameter_mm**2
        )

        return (
            self.gross_hex_area_mm2
            - bore_area_mm2
        ) * self.thickness_mm


@dataclass(frozen=True)
class NutBlankMeasurements:
    """Measured properties of the generated nut blank."""

    solid_count: int
    is_valid: bool
    volume_mm3: float
    x_length_mm: float
    y_length_mm: float
    z_min_mm: float
    z_max_mm: float
    face_count: int
    edge_count: int


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
    """Return a required non-empty string."""

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
    """Return a required numerical value."""

    value = data.get(key)

    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(
            f"Missing or invalid numerical value: {key}"
        )

    return float(value)


def _boolean(
    data: Mapping[str, object],
    key: str,
) -> bool:
    """Return a required Boolean value."""

    value = data.get(key)

    if not isinstance(value, bool):
        raise TypeError(
            f"Missing or invalid Boolean value: {key}"
        )

    return value


def load_nut_blank_definition(
    nut_config_path: Path,
    fastener_config_path: Path,
    assembly_config_path: Path,
) -> NutBlankDefinition:
    """Load and validate the governed nut-blank definition."""

    with nut_config_path.open("rb") as config_file:
        raw_data: dict[str, object] = tomllib.load(config_file)

    identity = _section(raw_data, "identity")
    nut = _section(raw_data, "nut")
    construction = _section(raw_data, "construction")

    thread_reference = load_baseline_thread_reference(
        fastener_config_path
    )
    assembly = load_baseline_assembly(
        assembly_config_path
    )

    definition = NutBlankDefinition(
        geometry_id=_string(identity, "geometry_id"),
        assembly_id=_string(identity, "assembly_id"),
        component_name=_string(identity, "component_name"),
        nominal_diameter_mm=(
            thread_reference.dimensions.nominal_diameter_mm
        ),
        pitch_mm=thread_reference.dimensions.pitch_mm,
        across_flats_mm=_number(
            nut,
            "across_flats_mm",
        ),
        thickness_mm=_number(
            nut,
            "thickness_mm",
        ),
        bore_diameter_mm=(
            thread_reference
            .dimensions
            .basic_internal_minor_diameter_mm
        ),
        bore_basis=_string(
            construction,
            "bore_basis",
        ),
        chamfer_included=_boolean(
            construction,
            "chamfer_included",
        ),
    )

    if definition.assembly_id != assembly.assembly_id:
        raise ValueError(
            "Nut geometry and assembly use different identities."
        )

    if definition.across_flats_mm <= definition.nominal_diameter_mm:
        raise ValueError(
            "Nut across-flats width must exceed nominal diameter."
        )

    if definition.thickness_mm <= 0.0:
        raise ValueError("Nut thickness must be positive.")

    if (
        abs(
            definition.thickness_mm
            - assembly.nut_thickness_mm
        )
        > 1.0e-9
    ):
        raise ValueError(
            "Nut geometry thickness disagrees with the assembly."
        )

    if definition.bore_basis != "basic_internal_minor_diameter":
        raise ValueError(
            "Unsupported nut-bore construction basis."
        )

    if definition.chamfer_included:
        raise ValueError(
            "Nut chamfers are outside the current baseline blank."
        )

    return definition


def build_nut_blank(
    definition: NutBlankDefinition,
) -> cq.Shape:
    """Build a regular hexagonal nut with a cylindrical pilot bore."""

    outer_model = (
        cq.Workplane("XY")
        .polygon(
            6,
            definition.across_corners_mm,
        )
        .extrude(definition.thickness_mm)
    )

    bore_model = (
        cq.Workplane("XY")
        .circle(definition.bore_diameter_mm / 2.0)
        .extrude(definition.thickness_mm)
    )

    outer = cast(cq.Shape, outer_model.val())
    bore = cast(cq.Shape, bore_model.val())

    nut_blank = outer.cut(
        bore,
        tol=1.0e-7,
    ).clean()

    if nut_blank.isNull():
        raise RuntimeError(
            "Nut blank construction produced a null shape."
        )

    if nut_blank.Volume() <= 0.0:
        raise RuntimeError(
            "Nut blank construction produced zero volume."
        )

    if len(nut_blank.Solids()) != 1:
        raise RuntimeError(
            "Nut blank construction did not produce one solid."
        )

    if not nut_blank.isValid():
        raise RuntimeError(
            "Nut blank construction produced an invalid solid."
        )

    return nut_blank


def measure_nut_blank(
    nut_blank: cq.Shape,
) -> NutBlankMeasurements:
    """Measure the generated nut blank."""

    if nut_blank.isNull():
        raise RuntimeError("Cannot measure a null nut blank.")

    bounding_box = nut_blank.BoundingBox()

    return NutBlankMeasurements(
        solid_count=len(nut_blank.Solids()),
        is_valid=nut_blank.isValid(),
        volume_mm3=nut_blank.Volume(),
        x_length_mm=bounding_box.xlen,
        y_length_mm=bounding_box.ylen,
        z_min_mm=bounding_box.zmin,
        z_max_mm=bounding_box.zmax,
        face_count=len(nut_blank.Faces()),
        edge_count=len(nut_blank.Edges()),
    )
