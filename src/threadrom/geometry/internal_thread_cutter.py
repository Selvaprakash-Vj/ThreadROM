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
from threadrom.geometry.thread_flank_geometry import (
    boolean_overlap_axial_extension_mm,
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
        """Return the internal-thread path start at the lower nut face."""

        return 0.0

    @property
    def sweep_height_mm(self) -> float:
        """Return the internal-thread path height through the nut."""

        return self.thread_length_mm

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

    if definition.radial_thread_depth_mm <= 0.0:
        raise ValueError(
            "Internal radial thread depth must be positive."
        )

    return definition


def internal_cutter_profile_points(
    definition: InternalThreadCutterDefinition,
    radial_overlap_mm: float,
) -> tuple[tuple[float, float], ...]:
    """Return the complementary female-thread groove cutter profile.

    The physical internal ISO thread is open at the minor-radius bore
    and narrows toward its major-radius root.  Construction overlap is
    extended along the existing 60-degree flank so that the nominal
    physical flank itself remains unchanged.
    """

    if radial_overlap_mm <= 0.0:
        raise ValueError(
            "Thread Boolean radial overlap must be positive."
        )

    pitch_mm = definition.pitch_mm

    axial_overlap_mm = (
        boolean_overlap_axial_extension_mm(
            radial_overlap_mm
        )
    )

    bore_opening_half_width_mm = (
        7.0 * pitch_mm / 16.0
        + axial_overlap_mm
    )

    deep_root_half_width_mm = (
        pitch_mm / 8.0
        - axial_overlap_mm
    )

    if deep_root_half_width_mm <= 0.0:
        raise ValueError(
            "Thread Boolean overlap collapses the "
            "internal-thread root width."
        )

    inward_coordinate_mm = -radial_overlap_mm

    outward_coordinate_mm = (
        definition.radial_thread_depth_mm
        + radial_overlap_mm
    )

    return (
        (
            inward_coordinate_mm,
            -bore_opening_half_width_mm,
        ),
        (
            outward_coordinate_mm,
            -deep_root_half_width_mm,
        ),
        (
            outward_coordinate_mm,
            deep_root_half_width_mm,
        ),
        (
            inward_coordinate_mm,
            bore_opening_half_width_mm,
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
    radial_overlap_mm: float,
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
                    definition,
                    radial_overlap_mm,
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
