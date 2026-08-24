"""Construction and verification of the complete canonical threaded nut."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import cast

import cadquery as cq

from threadrom.geometry.direct_internal_thread import (
    build_direct_internal_thread_segments,
    direct_internal_thread_join_radii_mm,
)
from threadrom.geometry.geometry_quality import GeometryQualityPolicy
from threadrom.geometry.internal_thread_cutter import (
    InternalThreadCutterDefinition,
    load_internal_thread_cutter_definition,
)
from threadrom.geometry.nut_blank import (
    NutBlankDefinition,
    build_nut_blank,
    load_nut_blank_definition,
)

_NUT_FUSION_TOLERANCE_MM = 1.0e-7


@dataclass(frozen=True)
class CompleteNutBuild:
    """Shapes produced during canonical threaded-nut construction."""

    nut_blank: cq.Shape
    construction_shell: cq.Shape
    thread_segments: tuple[cq.Shape, ...]
    complete_nut: cq.Shape


@dataclass(frozen=True)
class CompleteNutMeasurements:
    """Measured properties of the completed canonical threaded nut."""

    solid_count: int
    is_valid: bool
    blank_volume_mm3: float
    construction_shell_volume_mm3: float
    thread_construction_volume_mm3: float
    complete_volume_mm3: float
    added_thread_material_mm3: float
    removed_thread_volume_mm3: float
    thread_segment_count: int
    x_length_mm: float
    y_length_mm: float
    z_min_mm: float
    z_max_mm: float
    face_count: int
    edge_count: int


def load_complete_nut_definitions(
    project_root: Path,
) -> tuple[
    NutBlankDefinition,
    InternalThreadCutterDefinition,
]:
    """Load and cross-check the governed nut definitions."""

    nut_definition = load_nut_blank_definition(
        project_root / "config" / "nut_geometry.toml",
        project_root / "config" / "baseline_fastener.toml",
        project_root / "config" / "baseline_assembly.toml",
    )

    thread_definition = (
        load_internal_thread_cutter_definition(
            project_root
            / "config"
            / "internal_thread_geometry.toml",
            project_root / "config" / "nut_geometry.toml",
            project_root / "config" / "baseline_fastener.toml",
            project_root / "config" / "baseline_assembly.toml",
        )
    )

    if (
        nut_definition.geometry_id
        != thread_definition.geometry_id
    ):
        raise ValueError(
            "Nut blank and internal thread use different "
            "geometry identities."
        )

    if (
        nut_definition.assembly_id
        != thread_definition.assembly_id
    ):
        raise ValueError(
            "Nut blank and internal thread use different "
            "assembly identities."
        )

    if (
        abs(
            nut_definition.nominal_diameter_mm
            - thread_definition.nominal_diameter_mm
        )
        > 1.0e-9
    ):
        raise ValueError(
            "Nut blank and internal thread use different "
            "nominal diameters."
        )

    if (
        abs(
            nut_definition.pitch_mm
            - thread_definition.pitch_mm
        )
        > 1.0e-9
    ):
        raise ValueError(
            "Nut blank and internal thread use different pitches."
        )

    if (
        abs(
            nut_definition.bore_diameter_mm
            - thread_definition.minor_diameter_mm
        )
        > 1.0e-9
    ):
        raise ValueError(
            "Nut bore and internal-thread minor diameter differ."
        )

    if (
        abs(
            nut_definition.thickness_mm
            - thread_definition.thread_length_mm
        )
        > 1.0e-9
    ):
        raise ValueError(
            "Nut thickness and internal-thread length differ."
        )

    return nut_definition, thread_definition


def _build_construction_shell(
    nut_blank: cq.Shape,
    nut_definition: NutBlankDefinition,
    thread_definition: InternalThreadCutterDefinition,
    radial_overlap_mm: float,
) -> cq.Shape:
    """Enlarge the pilot bore only enough to receive the thread cells."""

    (
        shell_join_radius_mm,
        _,
    ) = direct_internal_thread_join_radii_mm(
        thread_definition,
        radial_overlap_mm,
    )

    if (
        shell_join_radius_mm
        >= nut_definition.across_flats_mm / 2.0
    ):
        raise ValueError(
            "Thread construction bore reaches the nut flats."
        )

    construction_bore_model = (
        cq.Workplane("XY")
        .circle(
            shell_join_radius_mm
        )
        .extrude(
            nut_definition.thickness_mm
        )
    )

    construction_bore = cast(
        cq.Shape,
        construction_bore_model.val(),
    )

    shell = (
        nut_blank.cut(
            construction_bore,
            tol=_NUT_FUSION_TOLERANCE_MM,
        )
        .clean()
    )

    if shell.isNull():
        raise RuntimeError(
            "Nut construction shell is null."
        )

    if shell.Volume() <= 0.0:
        raise RuntimeError(
            "Nut construction shell has zero volume."
        )

    if len(shell.Solids()) != 1:
        raise RuntimeError(
            "Nut construction shell did not produce one solid."
        )

    if not shell.isValid():
        raise RuntimeError(
            "Nut construction shell is invalid."
        )

    return shell


def build_complete_nut(
    nut_definition: NutBlankDefinition,
    thread_definition: InternalThreadCutterDefinition,
    quality_policy: GeometryQualityPolicy,
) -> CompleteNutBuild:
    """Build the nut without a helical thread-cutting Boolean.

    The external hexagonal envelope remains untwisted. A temporary
    cylindrical construction bore is opened outside the physical
    thread major radius, then compact canonical screw cells are fused
    into the shell using the validated normal OCC Boolean operation.
    """

    radial_overlap_mm = (
        quality_policy.thread_boolean_overlap_mm
    )

    nut_blank = build_nut_blank(
        nut_definition
    )

    construction_shell = (
        _build_construction_shell(
            nut_blank,
            nut_definition,
            thread_definition,
            radial_overlap_mm,
        )
    )

    thread_segments = (
        build_direct_internal_thread_segments(
            thread_definition,
            radial_overlap_mm,
        )
    )

    complete_nut = (
        construction_shell.fuse(
            *thread_segments,
            tol=_NUT_FUSION_TOLERANCE_MM,
        )
        .clean()
    )

    if complete_nut.isNull():
        raise RuntimeError(
            "Canonical threaded-nut fusion produced a null shape."
        )

    if complete_nut.Volume() <= 0.0:
        raise RuntimeError(
            "Canonical threaded-nut fusion produced zero volume."
        )

    if len(complete_nut.Solids()) != 1:
        raise RuntimeError(
            "Canonical threaded-nut fusion did not "
            "produce exactly one solid."
        )

    if not complete_nut.isValid():
        raise RuntimeError(
            "Canonical threaded-nut fusion produced "
            "an invalid solid."
        )

    if (
        complete_nut.Volume()
        >= nut_blank.Volume()
    ):
        raise RuntimeError(
            "Completed thread removed no material from "
            "the pilot-bore nut blank."
        )

    if (
        complete_nut.Volume()
        <= construction_shell.Volume()
    ):
        raise RuntimeError(
            "Canonical thread cells added no material "
            "to the construction shell."
        )

    return CompleteNutBuild(
        nut_blank=nut_blank,
        construction_shell=construction_shell,
        thread_segments=thread_segments,
        complete_nut=complete_nut,
    )


def measure_complete_nut(
    build: CompleteNutBuild,
) -> CompleteNutMeasurements:
    """Measure the completed canonical threaded nut."""

    complete_nut = build.complete_nut

    if complete_nut.isNull():
        raise RuntimeError(
            "Cannot measure a null complete nut."
        )

    bounding_box = complete_nut.BoundingBox()

    blank_volume_mm3 = (
        build.nut_blank.Volume()
    )

    construction_shell_volume_mm3 = (
        build.construction_shell.Volume()
    )

    complete_volume_mm3 = (
        complete_nut.Volume()
    )

    thread_construction_volume_mm3 = sum(
        segment.Volume()
        for segment in build.thread_segments
    )

    return CompleteNutMeasurements(
        solid_count=len(complete_nut.Solids()),
        is_valid=complete_nut.isValid(),
        blank_volume_mm3=blank_volume_mm3,
        construction_shell_volume_mm3=(
            construction_shell_volume_mm3
        ),
        thread_construction_volume_mm3=(
            thread_construction_volume_mm3
        ),
        complete_volume_mm3=complete_volume_mm3,
        added_thread_material_mm3=(
            complete_volume_mm3
            - construction_shell_volume_mm3
        ),
        removed_thread_volume_mm3=(
            blank_volume_mm3
            - complete_volume_mm3
        ),
        thread_segment_count=len(
            build.thread_segments
        ),
        x_length_mm=bounding_box.xlen,
        y_length_mm=bounding_box.ylen,
        z_min_mm=bounding_box.zmin,
        z_max_mm=bounding_box.zmax,
        face_count=len(complete_nut.Faces()),
        edge_count=len(complete_nut.Edges()),
    )