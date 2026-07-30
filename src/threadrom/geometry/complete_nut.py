"""Construction and verification of the complete threaded nut."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cadquery as cq

from threadrom.geometry.internal_thread_cutter import (
    InternalThreadCutterDefinition,
    build_internal_thread_cutter,
    load_internal_thread_cutter_definition,
)
from threadrom.geometry.nut_blank import (
    NutBlankDefinition,
    build_nut_blank,
    load_nut_blank_definition,
)


@dataclass(frozen=True)
class CompleteNutBuild:
    """Shapes produced during threaded-nut construction."""

    nut_blank: cq.Shape
    thread_cutter: cq.Shape
    complete_nut: cq.Shape


@dataclass(frozen=True)
class CompleteNutMeasurements:
    """Measured properties of the completed threaded nut."""

    solid_count: int
    is_valid: bool
    blank_volume_mm3: float
    cutter_volume_mm3: float
    complete_volume_mm3: float
    removed_thread_volume_mm3: float
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


def build_complete_nut(
    nut_definition: NutBlankDefinition,
    thread_definition: InternalThreadCutterDefinition,
) -> CompleteNutBuild:
    """Subtract the helical cutter from the nut blank."""

    nut_blank = build_nut_blank(nut_definition)

    thread_cutter = build_internal_thread_cutter(
        thread_definition
    )

    complete_nut = nut_blank.cut(
        thread_cutter,
        tol=1.0e-7,
    ).clean()

    if complete_nut.isNull():
        raise RuntimeError(
            "Internal-thread cut produced a null nut."
        )

    if complete_nut.Volume() <= 0.0:
        raise RuntimeError(
            "Internal-thread cut produced zero nut volume."
        )

    if len(complete_nut.Solids()) != 1:
        raise RuntimeError(
            "Internal-thread cut did not produce one nut solid."
        )

    if not complete_nut.isValid():
        raise RuntimeError(
            "Internal-thread cut produced an invalid nut solid."
        )

    removed_volume_mm3 = (
        nut_blank.Volume()
        - complete_nut.Volume()
    )

    if removed_volume_mm3 <= 0.0:
        raise RuntimeError(
            "Internal-thread cutter removed no nut material."
        )

    return CompleteNutBuild(
        nut_blank=nut_blank,
        thread_cutter=thread_cutter,
        complete_nut=complete_nut,
    )


def measure_complete_nut(
    build: CompleteNutBuild,
) -> CompleteNutMeasurements:
    """Measure the completed threaded nut."""

    complete_nut = build.complete_nut

    if complete_nut.isNull():
        raise RuntimeError(
            "Cannot measure a null complete nut."
        )

    bounding_box = complete_nut.BoundingBox()

    blank_volume_mm3 = build.nut_blank.Volume()
    complete_volume_mm3 = complete_nut.Volume()

    return CompleteNutMeasurements(
        solid_count=len(complete_nut.Solids()),
        is_valid=complete_nut.isValid(),
        blank_volume_mm3=blank_volume_mm3,
        cutter_volume_mm3=build.thread_cutter.Volume(),
        complete_volume_mm3=complete_volume_mm3,
        removed_thread_volume_mm3=(
            blank_volume_mm3
            - complete_volume_mm3
        ),
        x_length_mm=bounding_box.xlen,
        y_length_mm=bounding_box.ylen,
        z_min_mm=bounding_box.zmin,
        z_max_mm=bounding_box.zmax,
        face_count=len(complete_nut.Faces()),
        edge_count=len(complete_nut.Edges()),
    )
