"""Additive helical ridge for the baseline external metric thread."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import cadquery as cq

from threadrom.geometry.helical_thread_cutter import (
    HelicalThreadCutterDefinition,
)


@dataclass(frozen=True)
class HelicalThreadRidgeMeasurements:
    """Measured properties of the additive helical ridge."""

    solid_count: int
    is_valid: bool
    volume_mm3: float
    x_length_mm: float
    y_length_mm: float
    z_min_mm: float
    z_max_mm: float
    face_count: int
    edge_count: int


def ridge_profile_points(
    definition: HelicalThreadCutterDefinition,
    radial_overlap_mm: float,
) -> tuple[tuple[float, float], ...]:
    """Return the additive ridge profile relative to the helix path."""

    if radial_overlap_mm <= 0.0:
        raise ValueError("Radial overlap must be positive.")

    pitch = definition.pitch_mm

    crest_half_width_mm = pitch / 16.0
    base_half_width_mm = 5.0 * pitch / 12.0

    inward_coordinate_mm = -(
        definition.radial_thread_depth_mm
        + radial_overlap_mm
    )

    return (
        (
            inward_coordinate_mm,
            -base_half_width_mm,
        ),
        (
            0.0,
            -crest_half_width_mm,
        ),
        (
            0.0,
            crest_half_width_mm,
        ),
        (
            inward_coordinate_mm,
            base_half_width_mm,
        ),
    )


def build_helical_thread_ridge(
    definition: HelicalThreadCutterDefinition,
    radial_overlap_mm: float = 0.03,
) -> cq.Shape:
    """Sweep an additive trapezoidal thread ridge along a right-hand helix."""

    pitch = definition.pitch_mm

    base_half_width_mm = 5.0 * pitch / 12.0

    path_start_z_mm = base_half_width_mm

    path_height_mm = (
        definition.thread_length_mm
        - 2.0 * base_half_width_mm
    )

    if path_height_mm <= 0.0:
        raise ValueError(
            "Thread length is insufficient for the ridge profile."
        )

    helix = cq.Wire.makeHelix(
        pitch=definition.pitch_mm,
        height=path_height_mm,
        radius=definition.major_radius_mm,
        center=cq.Vector(
            0.0,
            0.0,
            path_start_z_mm,
        ),
        dir=cq.Vector(0.0, 0.0, 1.0),
        lefthand=definition.is_left_hand,
    )

    helix_workplane = cq.Workplane(obj=helix)

    profile = (
        cq.Workplane("XZ")
        .center(
            definition.major_radius_mm,
            path_start_z_mm,
        )
        .polyline(
            list(
                ridge_profile_points(
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

    ridge = cast(cq.Shape, swept.val())

    if ridge.isNull():
        raise RuntimeError(
            "Helical sweep produced a null thread ridge."
        )

    if ridge.Volume() <= 0.0:
        raise RuntimeError(
            "Helical sweep produced a zero-volume thread ridge."
        )

    if len(ridge.Solids()) != 1:
        raise RuntimeError(
            "Helical sweep did not produce exactly one ridge solid."
        )

    if not ridge.isValid():
        raise RuntimeError(
            "Helical sweep produced an invalid ridge solid."
        )

    return ridge


def measure_helical_thread_ridge(
    ridge: cq.Shape,
) -> HelicalThreadRidgeMeasurements:
    """Measure the generated additive helical ridge."""

    if ridge.isNull():
        raise RuntimeError("Cannot measure a null thread ridge.")

    bounding_box = ridge.BoundingBox()

    return HelicalThreadRidgeMeasurements(
        solid_count=len(ridge.Solids()),
        is_valid=ridge.isValid(),
        volume_mm3=ridge.Volume(),
        x_length_mm=bounding_box.xlen,
        y_length_mm=bounding_box.ylen,
        z_min_mm=bounding_box.zmin,
        z_max_mm=bounding_box.zmax,
        face_count=len(ridge.Faces()),
        edge_count=len(ridge.Edges()),
    )