"""Helical cutting solid for a parametric internal metric thread."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import cadquery as cq

from threadrom.geometry.nut_blank import (
    load_nut_blank_definition,
)


@dataclass(frozen=True)
class InternalThreadCutterDefinition:
    """Controlled parameters for the internal-thread cutter."""

    geometry_id: str
    assembly_id: str
    component_name: str
    nominal_diameter_mm: float
    pitch_mm: float
    minor_diameter_mm: float
    thread_length_mm: float
    overshoot_pitches: float
    radial_overlap_mm: float
    handedness: str
    use_frenet_frame: bool

    @property
    def major_radius_mm(self) -> float:
        """Return the basic internal-thread major radius."""

        return self.nominal_diameter_mm / 2.0

    @property
    def minor_radius_mm(self) -> float:
        """Return the basic internal-thread minor radius."""

        return self.minor_diameter_mm / 2.0

    @property
    def radial_thread_depth_mm(self) -> float:
        """Return the basic radial internal-thread depth."""

        return self.major_radius_mm - self.minor_radius_mm

    @property
    def start_z_mm(self) -> float:
        """Return the sweep start below the nut."""

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
        """Return whether the thread is left-handed."""

        return self.handedness.lower() == "left"


@dataclass(frozen=True)
class InternalThreadCutterMeasurements:
    """Measured properties of the generated cutter."""

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


def load_internal_thread_cutter_definition(
    thread_config_path: Path,
    nut_config_path: Path,
    fastener_config_path: Path,
    assembly_config_path: Path,
) -> InternalThreadCutterDefinition:
    """Load and validate the governed internal-thread cutter."""

    with thread_config_path.open("rb") as config_file:
        raw_data: dict[str, object] = tomllib.load(config_file)

    identity = _section(raw_data, "identity")
    thread = _section(raw_data, "thread")

    nut_definition = load_nut_blank_definition(
        nut_config_path,
        fastener_config_path,
        assembly_config_path,
    )

    handedness = _string(
        thread,
        "handedness",
    ).lower()

    if handedness not in {"right", "left"}:
        raise ValueError(
            "Thread handedness must be either right or left."
        )

    definition = InternalThreadCutterDefinition(
        geometry_id=_string(identity, "geometry_id"),
        assembly_id=_string(identity, "assembly_id"),
        component_name=_string(
            identity,
            "component_name",
        ),
        nominal_diameter_mm=(
            nut_definition.nominal_diameter_mm
        ),
        pitch_mm=nut_definition.pitch_mm,
        minor_diameter_mm=nut_definition.bore_diameter_mm,
        thread_length_mm=_number(
            thread,
            "thread_length_mm",
        ),
        overshoot_pitches=_number(
            thread,
            "overshoot_pitches",
        ),
        radial_overlap_mm=_number(
            thread,
            "radial_overlap_mm",
        ),
        handedness=handedness,
        use_frenet_frame=_boolean(
            thread,
            "use_frenet_frame",
        ),
    )

    if definition.geometry_id != nut_definition.geometry_id:
        raise ValueError(
            "Nut and internal thread use different geometry identities."
        )

    if definition.assembly_id != nut_definition.assembly_id:
        raise ValueError(
            "Nut and internal thread use different assembly identities."
        )

    if (
        abs(
            definition.thread_length_mm
            - nut_definition.thickness_mm
        )
        > 1.0e-9
    ):
        raise ValueError(
            "Internal thread length must equal the nut thickness."
        )

    if definition.overshoot_pitches <= 0.0:
        raise ValueError(
            "Cutter overshoot must be positive."
        )

    if definition.radial_overlap_mm <= 0.0:
        raise ValueError(
            "Cutter radial overlap must be positive."
        )

    if (
        definition.radial_overlap_mm
        >= definition.minor_radius_mm
    ):
        raise ValueError(
            "Radial overlap must remain below the minor radius."
        )

    if definition.radial_thread_depth_mm <= 0.0:
        raise ValueError(
            "Internal radial thread depth must be positive."
        )

    return definition


def internal_cutter_profile_points(
    definition: InternalThreadCutterDefinition,
) -> tuple[tuple[float, float], ...]:
    """Return the cutter profile relative to the helix path."""

    crest_half_width_mm = definition.pitch_mm / 16.0
    root_half_width_mm = definition.pitch_mm / 8.0

    inward_overlap_mm = -definition.radial_overlap_mm
    outward_depth_mm = definition.radial_thread_depth_mm

    return (
        (
            inward_overlap_mm,
            -crest_half_width_mm,
        ),
        (
            outward_depth_mm,
            -root_half_width_mm,
        ),
        (
            outward_depth_mm,
            root_half_width_mm,
        ),
        (
            inward_overlap_mm,
            crest_half_width_mm,
        ),
    )


def build_internal_thread_path(
    definition: InternalThreadCutterDefinition,
) -> cq.Wire:
    """Build the controlled internal-thread helix."""

    return cq.Wire.makeHelix(
        pitch=definition.pitch_mm,
        height=definition.sweep_height_mm,
        radius=definition.minor_radius_mm,
        center=cq.Vector(
            0.0,
            0.0,
            definition.start_z_mm,
        ),
        dir=cq.Vector(0.0, 0.0, 1.0),
        lefthand=definition.is_left_hand,
    )


def build_internal_thread_cutter(
    definition: InternalThreadCutterDefinition,
) -> cq.Shape:
    """Sweep the internal-thread groove cutter along the helix."""

    path = build_internal_thread_path(definition)
    helix_workplane = cq.Workplane(obj=path)

    profile = (
        cq.Workplane("XZ")
        .center(
            definition.minor_radius_mm,
            definition.start_z_mm,
        )
        .polyline(
            list(
                internal_cutter_profile_points(
                    definition
                )
            )
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
            "Internal-thread sweep produced a null cutter."
        )

    if cutter.Volume() <= 0.0:
        raise RuntimeError(
            "Internal-thread sweep produced zero volume."
        )

    if len(cutter.Solids()) != 1:
        raise RuntimeError(
            "Internal-thread sweep did not produce one solid."
        )

    if not cutter.isValid():
        raise RuntimeError(
            "Internal-thread sweep produced an invalid solid."
        )

    return cutter


def measure_internal_thread_cutter(
    cutter: cq.Shape,
) -> InternalThreadCutterMeasurements:
    """Measure the generated internal-thread cutter."""

    if cutter.isNull():
        raise RuntimeError(
            "Cannot measure a null internal-thread cutter."
        )

    bounding_box = cutter.BoundingBox()

    return InternalThreadCutterMeasurements(
        solid_count=len(cutter.Solids()),
        is_valid=cutter.isValid(),
        volume_mm3=cutter.Volume(),
        x_length_mm=bounding_box.xlen,
        y_length_mm=bounding_box.ylen,
        z_min_mm=bounding_box.zmin,
        z_max_mm=bounding_box.zmax,
        face_count=len(cutter.Faces()),
        edge_count=len(cutter.Edges()),
    )
