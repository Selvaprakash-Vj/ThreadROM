"""Helical cutter for the baseline external metric thread."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import cadquery as cq

from threadrom.engineering.baseline_reference import (
    load_baseline_thread_reference,
)


@dataclass(frozen=True)
class HelicalThreadCutterDefinition:
    """Controlled parameters for the external-thread cutter."""

    geometry_id: str
    nominal_diameter_mm: float
    pitch_mm: float
    minor_diameter_mm: float
    thread_length_mm: float
    overshoot_pitches: float
    radial_clearance_mm: float
    handedness: str
    use_frenet_frame: bool

    @property
    def major_radius_mm(self) -> float:
        """Return the external-thread major radius."""

        return self.nominal_diameter_mm / 2.0

    @property
    def minor_radius_mm(self) -> float:
        """Return the external-thread minor radius."""

        return self.minor_diameter_mm / 2.0

    @property
    def radial_thread_depth_mm(self) -> float:
        """Return the basic radial thread depth."""

        return self.major_radius_mm - self.minor_radius_mm

    @property
    def start_z_mm(self) -> float:
        """Return the cutter start position below the threaded region."""

        return -self.overshoot_pitches * self.pitch_mm

    @property
    def sweep_height_mm(self) -> float:
        """Return the complete cutter sweep height."""

        return (
            self.thread_length_mm
            + 2.0 * self.overshoot_pitches * self.pitch_mm
        )

    @property
    def turn_count(self) -> float:
        """Return the number of helical revolutions."""

        return self.sweep_height_mm / self.pitch_mm

    @property
    def is_left_hand(self) -> bool:
        """Return whether the configured helix is left-handed."""

        return self.handedness.lower() == "left"


@dataclass(frozen=True)
class HelicalThreadCutterMeasurements:
    """Measured properties of the generated cutter."""

    solid_count: int
    is_valid: bool
    volume_mm3: float
    x_length_mm: float
    y_length_mm: float
    z_min_mm: float
    z_max_mm: float


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


def load_helical_thread_cutter_definition(
    cutter_config_path: Path,
    fastener_config_path: Path,
) -> HelicalThreadCutterDefinition:
    """Load and validate the helical cutter definition."""

    with cutter_config_path.open("rb") as config_file:
        cutter_data: dict[str, object] = tomllib.load(config_file)

    identity = _section(cutter_data, "identity")
    cutter = _section(cutter_data, "cutter")

    thread_reference = load_baseline_thread_reference(
        fastener_config_path
    )

    handedness = _string(cutter, "handedness").lower()

    if handedness not in {"right", "left"}:
        raise ValueError(
            "Thread handedness must be either right or left."
        )

    definition = HelicalThreadCutterDefinition(
        geometry_id=_string(identity, "geometry_id"),
        nominal_diameter_mm=(
            thread_reference.dimensions.nominal_diameter_mm
        ),
        pitch_mm=thread_reference.dimensions.pitch_mm,
        minor_diameter_mm=(
            thread_reference
            .dimensions
            .basic_external_minor_diameter_mm
        ),
        thread_length_mm=_number(
            cutter,
            "thread_length_mm",
        ),
        overshoot_pitches=_number(
            cutter,
            "overshoot_pitches",
        ),
        radial_clearance_mm=_number(
            cutter,
            "radial_clearance_mm",
        ),
        handedness=handedness,
        use_frenet_frame=_boolean(
            cutter,
            "use_frenet_frame",
        ),
    )

    if definition.thread_length_mm <= 0.0:
        raise ValueError("Thread length must be positive.")

    if definition.overshoot_pitches <= 0.0:
        raise ValueError("Cutter overshoot must be positive.")

    if definition.radial_clearance_mm <= 0.0:
        raise ValueError("Radial clearance must be positive.")

    if definition.radial_thread_depth_mm <= 0.0:
        raise ValueError("Radial thread depth must be positive.")

    return definition


def build_helical_thread_path(
    definition: HelicalThreadCutterDefinition,
) -> cq.Wire:
    """Build the controlled helical sweep path."""

    return cq.Wire.makeHelix(
        pitch=definition.pitch_mm,
        height=definition.sweep_height_mm,
        radius=definition.major_radius_mm,
        center=cq.Vector(
            0.0,
            0.0,
            definition.start_z_mm,
        ),
        dir=cq.Vector(0.0, 0.0, 1.0),
        lefthand=definition.is_left_hand,
    )


def cutter_profile_points(
    definition: HelicalThreadCutterDefinition,
) -> tuple[tuple[float, float], ...]:
    """Return cutter-profile points relative to the helix start point."""

    pitch = definition.pitch_mm

    root_half_width = pitch / 12.0
    outer_half_width = 7.0 * pitch / 16.0

    inward_depth = -definition.radial_thread_depth_mm
    outward_clearance = definition.radial_clearance_mm

    return (
        (
            inward_depth,
            -root_half_width,
        ),
        (
            0.0,
            -outer_half_width,
        ),
        (
            outward_clearance,
            -outer_half_width,
        ),
        (
            outward_clearance,
            outer_half_width,
        ),
        (
            0.0,
            outer_half_width,
        ),
        (
            inward_depth,
            root_half_width,
        ),
    )


def build_helical_thread_cutter(
    definition: HelicalThreadCutterDefinition,
) -> cq.Shape:
    """Sweep a locally positioned groove profile along the helix."""

    path = build_helical_thread_path(definition)
    helix_workplane = cq.Workplane(obj=path)

    profile = (
        cq.Workplane("XZ")
        .center(
            definition.major_radius_mm,
            definition.start_z_mm,
        )
        .polyline(
            list(cutter_profile_points(definition))
        )
        .close()
    )

    swept = profile.sweep(
        helix_workplane,
        isFrenet=definition.use_frenet_frame,
        transition="transformed",
        combine=False,
        clean=True,
    )

    cutter = cast(cq.Shape, swept.val())

    if cutter.isNull():
        raise RuntimeError(
            "Helical sweep produced a null cutter."
        )

    if cutter.Volume() <= 0.0:
        raise RuntimeError(
            "Helical sweep produced a zero-volume cutter."
        )

    if len(cutter.Solids()) != 1:
        raise RuntimeError(
            "Helical sweep did not produce exactly one solid."
        )

    return cutter


def measure_helical_thread_cutter(
    cutter: cq.Shape,
) -> HelicalThreadCutterMeasurements:
    """Measure and validate the generated cutter solid."""

    if cutter.isNull():
        raise RuntimeError("Cannot measure a null cutter.")

    bounding_box = cutter.BoundingBox()

    return HelicalThreadCutterMeasurements(
        solid_count=len(cutter.Solids()),
        is_valid=cutter.isValid(),
        volume_mm3=cutter.Volume(),
        x_length_mm=bounding_box.xlen,
        y_length_mm=bounding_box.ylen,
        z_min_mm=bounding_box.zmin,
        z_max_mm=bounding_box.zmax,
    )