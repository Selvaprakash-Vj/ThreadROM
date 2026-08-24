"""Construction and verification of the complete parametric bolt."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import cadquery as cq

from threadrom.geometry.bolt_blank import BoltBlankDefinition
from threadrom.geometry.geometry_quality import GeometryQualityPolicy
from threadrom.geometry.helical_thread_cutter import (
    HelicalThreadCutterDefinition,
)
from threadrom.geometry.threaded_shank import build_threaded_shank


@dataclass(frozen=True)
class CompleteBoltBuild:
    """Shapes produced during complete-bolt construction."""

    head: cq.Shape
    threaded_shank: cq.Shape
    fusion_bridge: cq.Shape
    complete_bolt: cq.Shape


@dataclass(frozen=True)
class CompleteBoltMeasurements:
    """Measured properties of the complete bolt."""

    solid_count: int
    is_valid: bool
    head_volume_mm3: float
    threaded_shank_volume_mm3: float
    fusion_bridge_volume_mm3: float
    complete_volume_mm3: float
    union_overlap_volume_mm3: float
    x_length_mm: float
    y_length_mm: float
    z_min_mm: float
    z_max_mm: float
    face_count: int
    edge_count: int


@dataclass(frozen=True)
class StepRoundTripMeasurements:
    """Measurements after STEP export and re-import."""

    file_size_bytes: int
    solid_count: int
    is_valid: bool
    volume_mm3: float
    relative_volume_error: float
    maximum_bounds_error_mm: float


def build_parametric_hex_head(
    definition: BoltBlankDefinition,
) -> cq.Shape:
    """Build a regular hex head using the configured width across flats."""

    model = (
        cq.Workplane("XY")
        .polygon(
            6,
            definition.head_across_flats_mm,
            circumscribed=True,
        )
        .extrude(-definition.head_height_mm)
    )

    head = cast(cq.Shape, model.val()).clean()

    if head.isNull() or head.Volume() <= 0.0:
        raise RuntimeError("Hex-head construction failed.")

    if len(head.Solids()) != 1 or not head.isValid():
        raise RuntimeError("Hex-head construction did not produce one valid solid.")

    return head


def build_fusion_bridge(
    blank_definition: BoltBlankDefinition,
    thread_definition: HelicalThreadCutterDefinition,
    quality_policy: GeometryQualityPolicy,
) -> cq.Shape:
    """Build an internal bridge crossing the head-shank interface."""

    bridge_radius_mm = (
        thread_definition.minor_radius_mm * quality_policy.fusion_bridge_radius_fraction
    )

    maximum_permitted_radius_mm = min(
        blank_definition.nominal_diameter_mm / 2.0,
        blank_definition.head_across_flats_mm / 2.0,
    )

    if not 0.0 < bridge_radius_mm < maximum_permitted_radius_mm:
        raise ValueError("Fusion bridge radius is invalid.")

    half_height_mm = quality_policy.fusion_bridge_half_height_mm

    model = (
        cq.Workplane(
            "XY",
            origin=(0.0, 0.0, -half_height_mm),
        )
        .circle(bridge_radius_mm)
        .extrude(2.0 * half_height_mm)
    )

    bridge = cast(cq.Shape, model.val())

    if bridge.isNull() or bridge.Volume() <= 0.0:
        raise RuntimeError("Head-shank fusion bridge construction failed.")

    return bridge


def build_complete_bolt(
    blank_definition: BoltBlankDefinition,
    thread_definition: HelicalThreadCutterDefinition,
    quality_policy: GeometryQualityPolicy,
    mating_clearance_mm: float = 0.0,
) -> CompleteBoltBuild:
    """Fuse the parametric head and threaded shank into one bolt."""

    head = build_parametric_hex_head(blank_definition)

    threaded_build = build_threaded_shank(
        blank_definition,
        thread_definition,
        quality_policy,
        mating_clearance_mm,
    )

    threaded_shank = threaded_build.threaded_shank

    fusion_bridge = build_fusion_bridge(
        blank_definition,
        thread_definition,
        quality_policy,
    )

    complete_bolt = head.fuse(
        threaded_shank,
        fusion_bridge,
        tol=quality_policy.boolean_tolerance_mm,
    ).clean()

    if complete_bolt.isNull() or complete_bolt.Volume() <= 0.0:
        raise RuntimeError("Complete-bolt fusion produced a null or zero-volume shape.")

    if len(complete_bolt.Solids()) != 1:
        raise RuntimeError("Complete-bolt fusion did not produce exactly one solid.")

    if not complete_bolt.isValid():
        raise RuntimeError("Complete-bolt fusion produced an invalid solid.")

    return CompleteBoltBuild(
        head=head,
        threaded_shank=threaded_shank,
        fusion_bridge=fusion_bridge,
        complete_bolt=complete_bolt,
    )


def measure_complete_bolt(
    build: CompleteBoltBuild,
) -> CompleteBoltMeasurements:
    """Measure the complete fused bolt."""

    bounding_box = build.complete_bolt.BoundingBox()

    head_volume_mm3 = build.head.Volume()
    threaded_shank_volume_mm3 = build.threaded_shank.Volume()
    fusion_bridge_volume_mm3 = build.fusion_bridge.Volume()
    complete_volume_mm3 = build.complete_bolt.Volume()

    component_volume_sum_mm3 = (
        head_volume_mm3 + threaded_shank_volume_mm3 + fusion_bridge_volume_mm3
    )

    return CompleteBoltMeasurements(
        solid_count=len(build.complete_bolt.Solids()),
        is_valid=build.complete_bolt.isValid(),
        head_volume_mm3=head_volume_mm3,
        threaded_shank_volume_mm3=threaded_shank_volume_mm3,
        fusion_bridge_volume_mm3=fusion_bridge_volume_mm3,
        complete_volume_mm3=complete_volume_mm3,
        union_overlap_volume_mm3=(component_volume_sum_mm3 - complete_volume_mm3),
        x_length_mm=bounding_box.xlen,
        y_length_mm=bounding_box.ylen,
        z_min_mm=bounding_box.zmin,
        z_max_mm=bounding_box.zmax,
        face_count=len(build.complete_bolt.Faces()),
        edge_count=len(build.complete_bolt.Edges()),
    )


def expected_hex_across_corners_mm(
    across_flats_mm: float,
) -> float:
    """Return the across-corners size of a regular hexagon."""

    return across_flats_mm / math.cos(math.radians(30.0))


def export_and_reimport_step(
    shape: cq.Shape,
    step_path: Path,
) -> tuple[cq.Shape, StepRoundTripMeasurements]:
    """Export a shape to STEP, re-import it, and compare geometry."""

    step_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    cq.exporters.export(
        shape,
        str(step_path),
    )

    if not step_path.exists() or step_path.stat().st_size <= 0:
        raise RuntimeError("STEP export did not produce a valid file.")

    imported_workplane = cq.importers.importStep(str(step_path))

    imported_shape = cast(
        cq.Shape,
        imported_workplane.val(),
    )

    if imported_shape.isNull():
        raise RuntimeError("STEP re-import produced a null shape.")

    original_box = shape.BoundingBox()
    imported_box = imported_shape.BoundingBox()

    original_volume_mm3 = shape.Volume()
    imported_volume_mm3 = imported_shape.Volume()

    relative_volume_error = abs(imported_volume_mm3 - original_volume_mm3) / original_volume_mm3

    bounds_errors_mm = (
        abs(imported_box.xmin - original_box.xmin),
        abs(imported_box.xmax - original_box.xmax),
        abs(imported_box.ymin - original_box.ymin),
        abs(imported_box.ymax - original_box.ymax),
        abs(imported_box.zmin - original_box.zmin),
        abs(imported_box.zmax - original_box.zmax),
    )

    measurements = StepRoundTripMeasurements(
        file_size_bytes=step_path.stat().st_size,
        solid_count=len(imported_shape.Solids()),
        is_valid=imported_shape.isValid(),
        volume_mm3=imported_volume_mm3,
        relative_volume_error=relative_volume_error,
        maximum_bounds_error_mm=max(bounds_errors_mm),
    )

    return imported_shape, measurements
