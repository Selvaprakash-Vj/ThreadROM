"""Additive canonical screw-motion ridge for the external metric thread."""

from __future__ import annotations

import math
from dataclasses import dataclass

import cadquery as cq
import numpy as np
from OCP.BRepOffsetAPI import BRepOffsetAPI_ThruSections  # type: ignore[import-untyped]

from threadrom.geometry.canonical_screw_geometry import (
    canonical_flank_half_width_mm,
    screw_point_xyz,
)
from threadrom.geometry.helical_thread_cutter import (
    HelicalThreadCutterDefinition,
)

_SECTIONS_PER_TURN = 32


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
    mating_clearance_mm: float = 0.0,
) -> tuple[tuple[float, float], ...]:
    """Return canonical ridge points relative to the major cylinder.

    The physical 60-degree flank comes from the shared canonical
    screw-profile contract.

    ``radial_overlap_mm`` extends the additive ridge inward for
    robust fusion with the thread core without moving the physical
    flank datum.

    ``mating_clearance_mm`` shifts the complete external profile
    radially inward while preserving its axial flank coordinates.
    """

    if radial_overlap_mm <= 0.0:
        raise ValueError(
            "Radial overlap must be positive."
        )

    if mating_clearance_mm < 0.0:
        raise ValueError(
            "Mating clearance must be non-negative."
        )

    unshifted_base_radius_mm = (
        definition.minor_radius_mm
        - radial_overlap_mm
    )

    if unshifted_base_radius_mm <= 0.0:
        raise ValueError(
            "Radial overlap collapses the external-thread radius."
        )

    shifted_base_radius_mm = (
        unshifted_base_radius_mm
        - mating_clearance_mm
    )

    shifted_crest_radius_mm = (
        definition.major_radius_mm
        - mating_clearance_mm
    )

    if shifted_base_radius_mm <= 0.0:
        raise ValueError(
            "Mating clearance collapses the external-thread radius."
        )

    if (
        shifted_base_radius_mm
        >= shifted_crest_radius_mm
    ):
        raise ValueError(
            "External ridge base must remain inside the crest radius."
        )

    base_half_width_mm = (
        canonical_flank_half_width_mm(
            unshifted_base_radius_mm,
            definition.nominal_diameter_mm,
            definition.pitch_mm,
        )
    )

    crest_half_width_mm = (
        canonical_flank_half_width_mm(
            definition.major_radius_mm,
            definition.nominal_diameter_mm,
            definition.pitch_mm,
        )
    )

    inward_coordinate_mm = (
        shifted_base_radius_mm
        - definition.major_radius_mm
    )

    crest_coordinate_mm = (
        shifted_crest_radius_mm
        - definition.major_radius_mm
    )

    return (
        (
            inward_coordinate_mm,
            -base_half_width_mm,
        ),
        (
            crest_coordinate_mm,
            -crest_half_width_mm,
        ),
        (
            crest_coordinate_mm,
            crest_half_width_mm,
        ),
        (
            inward_coordinate_mm,
            base_half_width_mm,
        ),
    )


def _screw_section_wire(
    definition: HelicalThreadCutterDefinition,
    profile_points: tuple[tuple[float, float], ...],
    theta_rad: float,
    axial_origin_mm: float,
) -> cq.Wire:
    """Create one rigidly screw-transformed ridge section."""

    points: list[cq.Vector] = []

    for radial_offset_mm, axial_offset_mm in profile_points:
        radius_mm = (
            definition.major_radius_mm
            + radial_offset_mm
        )

        x_mm, y_mm, z_relative_mm = (
            screw_point_xyz(
                radius_mm,
                axial_offset_mm,
                theta_rad,
                definition.pitch_mm,
                definition.handedness,
            )
        )

        points.append(
            cq.Vector(
                x_mm,
                y_mm,
                axial_origin_mm
                + z_relative_mm,
            )
        )

    return cq.Wire.makePolygon(
        points,
        close=True,
    )


def build_helical_thread_ridge(
    definition: HelicalThreadCutterDefinition,
    radial_overlap_mm: float,
    mating_clearance_mm: float = 0.0,
) -> cq.Shape:
    """Build the external ridge using one canonical rigid screw motion.

    Unlike the former pipe sweep, profile orientation is not controlled
    by a radius-dependent Frenet frame. Every profile point follows the
    same screw transformation:

        z = a +/- P*theta/(2*pi)

    with the sign determined solely by thread handedness.
    """

    profile_points = ridge_profile_points(
        definition,
        radial_overlap_mm,
        mating_clearance_mm,
    )

    base_half_width_mm = max(
        abs(point[1])
        for point in profile_points
        if point[0] == profile_points[0][0]
    )

    path_height_mm = (
        definition.thread_length_mm
        - 2.0 * base_half_width_mm
    )

    if path_height_mm <= 0.0:
        raise ValueError(
            "Thread length is insufficient for the ridge profile."
        )

    hand_sign = (
        -1.0
        if definition.is_left_hand
        else 1.0
    )

    # Preserve the canonical rigid-screw datum while keeping the
    # finite ridge inside the governed 0..thread_length envelope.
    #
    # z = a + hand_sign * P*theta/(2*pi)
    #
    # At the first section the lowest profile point a=-base_half
    # must lie at z=0. At the last section the highest profile point
    # a=+base_half must lie at z=thread_length.
    theta_start_rad = (
        hand_sign
        * 2.0
        * math.pi
        * base_half_width_mm
        / definition.pitch_mm
    )

    theta_end_rad = (
        hand_sign
        * 2.0
        * math.pi
        * (
            definition.thread_length_mm
            - base_half_width_mm
        )
        / definition.pitch_mm
    )

    turn_count = (
        path_height_mm
        / definition.pitch_mm
    )

    section_count = max(
        9,
        math.ceil(
            turn_count
            * _SECTIONS_PER_TURN
        )
        + 1,
    )

    builder = BRepOffsetAPI_ThruSections(
        True,
        False,
        1.0e-7,
    )

    builder.CheckCompatibility(
        False
    )

    for theta_rad in np.linspace(
        theta_start_rad,
        theta_end_rad,
        section_count,
    ):
        wire = _screw_section_wire(
            definition,
            profile_points,
            float(theta_rad),
            0.0,
        )

        builder.AddWire(
            wire.wrapped
        )

    builder.Build()

    if not builder.IsDone():
        raise RuntimeError(
            "Canonical screw-motion loft failed to build the ridge."
        )

    shape = cq.Shape.cast(
        builder.Shape()
    )

    solids = list(
        shape.Solids()
    )

    if len(solids) != 1:
        raise RuntimeError(
            "Canonical screw-motion loft did not produce "
            "exactly one ridge solid."
        )

    ridge = solids[0]

    if ridge.isNull():
        raise RuntimeError(
            "Canonical screw-motion loft produced a null ridge."
        )

    if ridge.Volume() <= 0.0:
        raise RuntimeError(
            "Canonical screw-motion loft produced "
            "a zero-volume ridge."
        )

    if not ridge.isValid():
        raise RuntimeError(
            "Canonical screw-motion loft produced "
            "an invalid ridge solid."
        )

    return ridge


def measure_helical_thread_ridge(
    ridge: cq.Shape,
) -> HelicalThreadRidgeMeasurements:
    """Measure the generated additive canonical ridge."""

    if ridge.isNull():
        raise RuntimeError(
            "Cannot measure a null thread ridge."
        )

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