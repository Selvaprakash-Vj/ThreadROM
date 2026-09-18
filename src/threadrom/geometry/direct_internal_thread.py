"""Compact Boolean-free canonical internal-thread construction."""

from __future__ import annotations

import math
from dataclasses import dataclass

import cadquery as cq

from threadrom.geometry.canonical_screw_geometry import (
    canonical_internal_radius_from_phase_mm,
    normalized_handedness,
    validate_basic_internal_minor_diameter,
)
from threadrom.geometry.internal_thread_cutter import (
    InternalThreadCutterDefinition,
)

_PROFILE_SPLINE_SAMPLES = 25
_PROFILE_SPLINE_TOLERANCE_MM = 1.0e-8
_SEGMENT_FUSION_TOLERANCE_MM = 1.0e-7
_LENGTH_EPSILON_MM = 1.0e-12

# Cross-size Gate-2C qualification established two full pitches as
# the smallest seam-reducing span that preserves the canonical
# internal-thread oracle for M8x1.25, M10x1.5 and M12x1.75.
_MAX_SEGMENT_FULL_TURNS = 2


@dataclass(frozen=True)
class DirectInternalThreadMeasurements:
    """Measured properties of the compact direct internal thread."""

    solid_count: int
    is_valid: bool
    volume_mm3: float
    profile_edge_count: int
    thread_segment_count: int
    shell_join_radius_mm: float
    sleeve_outer_radius_mm: float
    total_twist_angle_deg: float
    z_min_mm: float
    z_max_mm: float
    face_count: int
    edge_count: int


def direct_internal_thread_join_radii_mm(
    definition: InternalThreadCutterDefinition,
    radial_overlap_mm: float,
) -> tuple[float, float]:
    """Return the governed shell/sleeve joining radii."""

    if radial_overlap_mm <= 0.0:
        raise ValueError(
            "Thread construction overlap must be positive."
        )

    shell_join_radius_mm = (
        definition.major_radius_mm
        + radial_overlap_mm
    )

    sleeve_outer_radius_mm = (
        definition.major_radius_mm
        + 2.0 * radial_overlap_mm
    )

    return (
        shell_join_radius_mm,
        sleeve_outer_radius_mm,
    )


def _hand_sign(
    definition: InternalThreadCutterDefinition,
) -> float:
    """Return the rigid screw-motion handedness sign."""

    handedness = normalized_handedness(
        definition.handedness
    )

    return (
        -1.0
        if handedness == "left"
        else 1.0
    )


def direct_internal_thread_twist_angle_deg(
    definition: InternalThreadCutterDefinition,
) -> float:
    """Return total screw rotation through the governed thread length."""

    return (
        _hand_sign(definition)
        * 360.0
        * definition.thread_length_mm
        / definition.pitch_mm
    )


def _polar_point(
    radius_mm: float,
    theta_rad: float,
    z_mm: float,
) -> cq.Vector:
    """Return one cylindrical point."""

    return cq.Vector(
        radius_mm * math.cos(theta_rad),
        radius_mm * math.sin(theta_rad),
        z_mm,
    )


def _canonical_radius_at_theta_mm(
    definition: InternalThreadCutterDefinition,
    theta_rad: float,
) -> float:
    """Return the canonical z=0 internal boundary radius."""

    axial_phase_mm = (
        -_hand_sign(definition)
        * definition.pitch_mm
        * theta_rad
        / (2.0 * math.pi)
    )

    return canonical_internal_radius_from_phase_mm(
        axial_phase_mm,
        definition.nominal_diameter_mm,
        definition.pitch_mm,
    )


def _flank_spline(
    definition: InternalThreadCutterDefinition,
    theta_start_rad: float,
    theta_end_rad: float,
    z_mm: float,
) -> cq.Edge:
    """Build one compact canonical flank as a B-spline edge."""

    points: list[cq.Vector] = []

    for index in range(
        _PROFILE_SPLINE_SAMPLES
    ):
        fraction = (
            index
            / (_PROFILE_SPLINE_SAMPLES - 1)
        )

        theta_rad = (
            theta_start_rad
            + fraction
            * (
                theta_end_rad
                - theta_start_rad
            )
        )

        radius_mm = (
            _canonical_radius_at_theta_mm(
                definition,
                theta_rad,
            )
        )

        points.append(
            _polar_point(
                radius_mm,
                theta_rad,
                z_mm,
            )
        )

    return cq.Edge.makeSpline(
        points,
        tol=_PROFILE_SPLINE_TOLERANCE_MM,
    )


def _inner_profile_wire(
    definition: InternalThreadCutterDefinition,
    z_mm: float = 0.0,
) -> cq.Wire:
    """Build the four-edge canonical internal-thread section."""

    validate_basic_internal_minor_diameter(
        definition.minor_diameter_mm,
        definition.nominal_diameter_mm,
        definition.pitch_mm,
        tolerance_mm=2.0e-12,
    )

    # Canonical metric-profile phase transitions:
    #
    # major crest: |phase| <= P/16
    # minor root : |phase| >= 3P/8
    #
    # Converted to angular position around one screw period.
    crest_half_angle_rad = (
        2.0
        * math.pi
        / 16.0
    )

    root_transition_angle_rad = (
        2.0
        * math.pi
        * 3.0
        / 8.0
    )

    theta_0 = (
        2.0 * math.pi
        - root_transition_angle_rad
    )

    theta_1 = (
        2.0 * math.pi
        - crest_half_angle_rad
    )

    theta_2 = crest_half_angle_rad
    theta_3 = root_transition_angle_rad

    major_radius_mm = (
        definition.major_radius_mm
    )

    minor_radius_mm = (
        definition.minor_radius_mm
    )

    wire = cq.Wire.assembleEdges(
        (
            _flank_spline(
                definition,
                theta_0,
                theta_1,
                z_mm,
            ),
            cq.Edge.makeThreePointArc(
                _polar_point(
                    major_radius_mm,
                    theta_1,
                    z_mm,
                ),
                _polar_point(
                    major_radius_mm,
                    0.0,
                    z_mm,
                ),
                _polar_point(
                    major_radius_mm,
                    theta_2,
                    z_mm,
                ),
            ),
            _flank_spline(
                definition,
                theta_2,
                theta_3,
                z_mm,
            ),
            cq.Edge.makeThreePointArc(
                _polar_point(
                    minor_radius_mm,
                    theta_3,
                    z_mm,
                ),
                _polar_point(
                    minor_radius_mm,
                    math.pi,
                    z_mm,
                ),
                _polar_point(
                    minor_radius_mm,
                    theta_0,
                    z_mm,
                ),
            ),
        )
    )

    if not wire.IsClosed():
        raise RuntimeError(
            "Compact internal-thread profile is not closed."
        )

    if not wire.isValid():
        raise RuntimeError(
            "Compact internal-thread profile is invalid."
        )

    return wire


def _outer_wire(
    radius_mm: float,
    z_mm: float,
) -> cq.Wire:
    """Build the circular construction boundary."""

    return cq.Wire.makeCircle(
        radius_mm,
        cq.Vector(
            0.0,
            0.0,
            z_mm,
        ),
        cq.Vector(
            0.0,
            0.0,
            1.0,
        ),
    )


def _validate_segment(
    segment: cq.Shape,
    segment_index: int,
) -> None:
    """Fail closed if a screw segment is not one valid solid."""

    if segment.isNull():
        raise RuntimeError(
            f"Internal-thread segment {segment_index} is null."
        )

    if segment.Volume() <= 0.0:
        raise RuntimeError(
            f"Internal-thread segment {segment_index} "
            "has zero volume."
        )

    if len(segment.Solids()) != 1:
        raise RuntimeError(
            f"Internal-thread segment {segment_index} "
            "did not produce exactly one solid."
        )

    if not segment.isValid():
        raise RuntimeError(
            f"Internal-thread segment {segment_index} is invalid."
        )


def build_direct_internal_thread_segments(
    definition: InternalThreadCutterDefinition,
    radial_overlap_mm: float,
) -> tuple[cq.Shape, ...]:
    """Build bounded canonical screw chunks.

    Each ordinary chunk spans at most two complete thread pitches.
    Any fractional terminal remainder is absorbed into the final chunk
    rather than emitted as a separate sliver-length construction cell.

    This reduces artificial pitch-plane topology while retaining the
    canonical metric-thread profile and rigid screw motion.
    """

    if definition.thread_length_mm <= 0.0:
        raise ValueError(
            "Internal thread length must be positive."
        )

    if definition.pitch_mm <= 0.0:
        raise ValueError(
            "Internal thread pitch must be positive."
        )

    (
        _,
        sleeve_outer_radius_mm,
    ) = direct_internal_thread_join_radii_mm(
        definition,
        radial_overlap_mm,
    )

    pitch_mm = definition.pitch_mm
    length_mm = definition.thread_length_mm

    full_turn_count = math.floor(
        length_mm / pitch_mm
        + _LENGTH_EPSILON_MM
    )

    remainder_mm = (
        length_mm
        - full_turn_count * pitch_mm
    )

    if abs(remainder_mm) <= _LENGTH_EPSILON_MM:
        remainder_mm = 0.0

    spans_mm: list[float] = []
    remaining_full_turns = full_turn_count

    while (
        remaining_full_turns
        > _MAX_SEGMENT_FULL_TURNS
    ):
        spans_mm.append(
            _MAX_SEGMENT_FULL_TURNS
            * pitch_mm
        )
        remaining_full_turns -= (
            _MAX_SEGMENT_FULL_TURNS
        )

    final_span_mm = (
        remaining_full_turns
        * pitch_mm
        + remainder_mm
    )

    if final_span_mm > _LENGTH_EPSILON_MM:
        spans_mm.append(
            final_span_mm
        )

    if not spans_mm:
        raise RuntimeError(
            "Internal-thread segmentation produced no chunks."
        )

    hand_sign = _hand_sign(
        definition
    )

    segments: list[cq.Shape] = []
    z_start_mm = 0.0

    for segment_index, span_mm in enumerate(
        spans_mm,
        start=1,
    ):
        segment = (
            cq.Solid.extrudeLinearWithRotation(
                _outer_wire(
                    sleeve_outer_radius_mm,
                    z_start_mm,
                ),
                [
                    _inner_profile_wire(
                        definition,
                        z_start_mm,
                    )
                ],
                cq.Vector(
                    0.0,
                    0.0,
                    z_start_mm,
                ),
                cq.Vector(
                    0.0,
                    0.0,
                    span_mm,
                ),
                (
                    hand_sign
                    * 360.0
                    * span_mm
                    / pitch_mm
                ),
            )
        )

        if segment.isNull():
            raise RuntimeError(
                f"Internal-thread segment "
                f"{segment_index} is null."
            )

        if segment.Volume() <= 0.0:
            raise RuntimeError(
                f"Internal-thread segment "
                f"{segment_index} has zero volume."
            )

        if len(segment.Solids()) != 1:
            raise RuntimeError(
                f"Internal-thread segment "
                f"{segment_index} did not produce "
                "exactly one solid."
            )

        if not segment.isValid():
            raise RuntimeError(
                f"Internal-thread segment "
                f"{segment_index} is invalid."
            )

        segments.append(
            segment
        )

        z_start_mm += span_mm

    if not math.isclose(
        z_start_mm,
        length_mm,
        rel_tol=0.0,
        abs_tol=1.0e-10,
    ):
        raise RuntimeError(
            "Internal-thread chunks do not span the "
            "governed thread length."
        )

    return tuple(
        segments
    )


def build_direct_internal_thread_sleeve(
    definition: InternalThreadCutterDefinition,
    radial_overlap_mm: float,
) -> cq.Shape:
    """Fuse compact canonical screw cells into one threaded sleeve."""

    segments = (
        build_direct_internal_thread_segments(
            definition,
            radial_overlap_mm,
        )
    )

    if len(segments) == 1:
        assembled = segments[0]
    else:
        assembled = (
            segments[0]
            .fuse(
                *segments[1:],
                tol=_SEGMENT_FUSION_TOLERANCE_MM,
            )
            .clean()
        )

    if assembled.isNull():
        raise RuntimeError(
            "Direct internal-thread sleeve is null."
        )

    if assembled.Volume() <= 0.0:
        raise RuntimeError(
            "Direct internal-thread sleeve has zero volume."
        )

    if len(assembled.Solids()) != 1:
        raise RuntimeError(
            "Direct internal-thread sleeve did not "
            "produce exactly one solid."
        )

    if not assembled.isValid():
        raise RuntimeError(
            "Direct internal-thread sleeve is invalid."
        )

    return assembled


def measure_direct_internal_thread_sleeve(
    sleeve: cq.Shape,
    definition: InternalThreadCutterDefinition,
    radial_overlap_mm: float,
) -> DirectInternalThreadMeasurements:
    """Measure the compact direct internal-thread sleeve."""

    if sleeve.isNull():
        raise RuntimeError(
            "Cannot measure a null internal-thread sleeve."
        )

    (
        shell_join_radius_mm,
        sleeve_outer_radius_mm,
    ) = direct_internal_thread_join_radii_mm(
        definition,
        radial_overlap_mm,
    )

    bounding_box = sleeve.BoundingBox()

    full_turn_count = math.floor(
        definition.thread_length_mm
        / definition.pitch_mm
        + _LENGTH_EPSILON_MM
    )

    segment_count = max(
        1,
        math.ceil(
            full_turn_count
            / _MAX_SEGMENT_FULL_TURNS
        ),
    )

    return DirectInternalThreadMeasurements(
        solid_count=len(sleeve.Solids()),
        is_valid=sleeve.isValid(),
        volume_mm3=sleeve.Volume(),
        profile_edge_count=4,
        thread_segment_count=segment_count,
        shell_join_radius_mm=shell_join_radius_mm,
        sleeve_outer_radius_mm=sleeve_outer_radius_mm,
        total_twist_angle_deg=(
            direct_internal_thread_twist_angle_deg(
                definition
            )
        ),
        z_min_mm=bounding_box.zmin,
        z_max_mm=bounding_box.zmax,
        face_count=len(sleeve.Faces()),
        edge_count=len(sleeve.Edges()),
    )