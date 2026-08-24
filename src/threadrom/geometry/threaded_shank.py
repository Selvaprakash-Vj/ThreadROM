"""Additive construction and verification of the baseline threaded shank."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import cadquery as cq

from threadrom.geometry.bolt_blank import (
    BoltBlankDefinition,
    load_bolt_blank_definition,
)
from threadrom.geometry.external_thread_ridge import (
    build_helical_thread_ridge,
)
from threadrom.geometry.geometry_quality import GeometryQualityPolicy
from threadrom.geometry.helical_thread_cutter import (
    HelicalThreadCutterDefinition,
    load_helical_thread_cutter_definition,
)


@dataclass(frozen=True)
class ThreadedShankBuild:
    """Shapes produced during additive threaded-shank construction."""

    core: cq.Shape
    ridge: cq.Shape
    threaded_shank: cq.Shape


@dataclass(frozen=True)
class ThreadedShankMeasurements:
    """Measured properties of the additive threaded shank."""

    solid_count: int
    is_valid: bool
    core_volume_mm3: float
    ridge_volume_mm3: float
    threaded_volume_mm3: float
    radial_overlap_volume_mm3: float
    major_cylinder_volume_mm3: float
    x_length_mm: float
    y_length_mm: float
    z_min_mm: float
    z_max_mm: float
    face_count: int
    edge_count: int


def load_threaded_shank_definitions(
    project_root: Path,
) -> tuple[BoltBlankDefinition, HelicalThreadCutterDefinition]:
    """Load the controlled blank and external-thread definitions."""

    blank_definition = load_bolt_blank_definition(
        project_root / "config" / "baseline_geometry.toml"
    )

    thread_definition = load_helical_thread_cutter_definition(
        project_root / "config" / "external_thread_geometry.toml",
        project_root / "config" / "baseline_fastener.toml",
    )

    if blank_definition.geometry_id != thread_definition.geometry_id:
        raise ValueError(
            "Bolt blank and thread geometry use different identities."
        )

    if (
        abs(
            blank_definition.nominal_diameter_mm
            - thread_definition.nominal_diameter_mm
        )
        > 1.0e-9
    ):
        raise ValueError(
            "Bolt blank and thread geometry use different diameters."
        )

    if (
        abs(
            blank_definition.underhead_length_mm
            - thread_definition.thread_length_mm
        )
        > 1.0e-9
    ):
        raise ValueError(
            "Bolt length and threaded length are inconsistent."
        )

    return blank_definition, thread_definition


def build_thread_core(
    definition: HelicalThreadCutterDefinition,
    radial_overlap_mm: float,
) -> cq.Shape:
    """Build the minor-diameter core with controlled ridge overlap."""

    if radial_overlap_mm <= 0.0:
        raise ValueError("Radial overlap must be positive.")

    core_radius_mm = (
        definition.minor_radius_mm
        + radial_overlap_mm
    )

    if core_radius_mm >= definition.major_radius_mm:
        raise ValueError(
            "Core radius must remain below the thread major radius."
        )

    core_model = (
        cq.Workplane("XY")
        .circle(core_radius_mm)
        .extrude(definition.thread_length_mm)
    )

    core = cast(cq.Shape, core_model.val())

    if core.isNull() or core.Volume() <= 0.0:
        raise RuntimeError("Thread core construction failed.")

    return core


def build_threaded_shank(
    blank_definition: BoltBlankDefinition,
    thread_definition: HelicalThreadCutterDefinition,
    quality_policy: GeometryQualityPolicy,
    mating_clearance_mm: float = 0.0,
) -> ThreadedShankBuild:
    """Fuse a minor-diameter core with an additive helical ridge."""

    thread_boolean_overlap_mm = (
        quality_policy.thread_boolean_overlap_mm
    )

    core = build_thread_core(
        thread_definition,
        thread_boolean_overlap_mm,
    )

    ridge = build_helical_thread_ridge(
        thread_definition,
        thread_boolean_overlap_mm,
        mating_clearance_mm,
    )

    threaded_shank = core.fuse(
        ridge,
        tol=1.0e-6,
    ).clean()

    if threaded_shank.isNull():
        raise RuntimeError(
            "Core and ridge fusion produced a null shape."
        )

    if threaded_shank.Volume() <= 0.0:
        raise RuntimeError(
            "Core and ridge fusion produced zero volume."
        )

    if len(threaded_shank.Solids()) != 1:
        raise RuntimeError(
            "Core and ridge fusion did not produce one solid."
        )

    if not threaded_shank.isValid():
        raise RuntimeError(
            "Core and ridge fusion produced an invalid solid."
        )

    return ThreadedShankBuild(
        core=core,
        ridge=ridge,
        threaded_shank=threaded_shank,
    )


def measure_threaded_shank(
    build: ThreadedShankBuild,
    thread_definition: HelicalThreadCutterDefinition,
) -> ThreadedShankMeasurements:
    """Measure and verify the additive threaded-shank result."""

    threaded_shank = build.threaded_shank
    bounding_box = threaded_shank.BoundingBox()

    core_volume_mm3 = build.core.Volume()
    ridge_volume_mm3 = build.ridge.Volume()
    threaded_volume_mm3 = threaded_shank.Volume()

    overlap_volume_mm3 = (
        core_volume_mm3
        + ridge_volume_mm3
        - threaded_volume_mm3
    )

    major_cylinder_volume_mm3 = (
        math.pi
        * thread_definition.major_radius_mm**2
        * thread_definition.thread_length_mm
    )

    return ThreadedShankMeasurements(
        solid_count=len(threaded_shank.Solids()),
        is_valid=threaded_shank.isValid(),
        core_volume_mm3=core_volume_mm3,
        ridge_volume_mm3=ridge_volume_mm3,
        threaded_volume_mm3=threaded_volume_mm3,
        radial_overlap_volume_mm3=overlap_volume_mm3,
        major_cylinder_volume_mm3=major_cylinder_volume_mm3,
        x_length_mm=bounding_box.xlen,
        y_length_mm=bounding_box.ylen,
        z_min_mm=bounding_box.zmin,
        z_max_mm=bounding_box.zmax,
        face_count=len(threaded_shank.Faces()),
        edge_count=len(threaded_shank.Edges()),
    )