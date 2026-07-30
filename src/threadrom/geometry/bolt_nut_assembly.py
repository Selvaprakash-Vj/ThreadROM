"""Governed construction of the baseline bolt-nut assembly."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cadquery as cq

from threadrom.engineering.baseline_assembly import (
    BaselineAssembly,
)
from threadrom.geometry.geometry_quality import (
    GeometryQualityPolicy,
)


@dataclass(frozen=True)
class BoltNutAssemblyBuild:
    """Native CAD shapes forming the positioned assembly."""

    bolt: cq.Shape
    positioned_nut: cq.Shape
    assembly: cq.Compound


@dataclass(frozen=True)
class BoltNutAssemblyMeasurements:
    """Native measurements of the positioned assembly."""

    bolt_solid_count: int
    nut_solid_count: int
    assembly_solid_count: int
    bolt_volume_mm3: float
    nut_volume_mm3: float
    component_volume_sum_mm3: float
    x_min_mm: float
    x_max_mm: float
    y_min_mm: float
    y_max_mm: float
    z_min_mm: float
    z_max_mm: float


@dataclass(frozen=True)
class BoltNutAssemblyStepMeasurements:
    """Measurements comparing native and reimported STEP geometry."""

    native_solid_count: int
    reimported_solid_count: int
    native_component_volume_mm3: float
    reimported_component_volume_mm3: float
    relative_volume_error: float
    maximum_bounds_error_mm: float


def build_bolt_nut_assembly(
    bolt: cq.Shape,
    nut: cq.Shape,
    definition: BaselineAssembly,
) -> BoltNutAssemblyBuild:
    """Position the nut and create a two-solid assembly compound."""

    bolt_solids = bolt.Solids()
    nut_solids = nut.Solids()

    if len(bolt_solids) != 1:
        raise ValueError(
            "Bolt-nut assembly requires exactly one bolt solid."
        )

    if len(nut_solids) != 1:
        raise ValueError(
            "Bolt-nut assembly requires exactly one nut solid."
        )

    positioned_nut = (
        nut.rotate(
            (0.0, 0.0, 0.0),
            (0.0, 0.0, 1.0),
            definition.nut_rotation_deg,
        )
        .translate(
            (
                0.0,
                0.0,
                definition.nut_translation_z_mm,
            )
        )
    )

    assembly = cq.Compound.makeCompound(
        [
            bolt,
            positioned_nut,
        ]
    )

    if len(assembly.Solids()) != 2:
        raise RuntimeError(
            "Positioned bolt-nut assembly must contain "
            "exactly two solids."
        )

    if not bolt.isValid():
        raise RuntimeError(
            "Bolt geometry is invalid."
        )

    if not positioned_nut.isValid():
        raise RuntimeError(
            "Positioned nut geometry is invalid."
        )

    if not assembly.isValid():
        raise RuntimeError(
            "Bolt-nut assembly compound is invalid."
        )

    return BoltNutAssemblyBuild(
        bolt=bolt,
        positioned_nut=positioned_nut,
        assembly=assembly,
    )


def measure_bolt_nut_assembly(
    build: BoltNutAssemblyBuild,
) -> BoltNutAssemblyMeasurements:
    """Measure native assembly topology, volume and bounds."""

    bounds = build.assembly.BoundingBox()

    bolt_volume_mm3 = build.bolt.Volume()
    nut_volume_mm3 = build.positioned_nut.Volume()

    return BoltNutAssemblyMeasurements(
        bolt_solid_count=len(build.bolt.Solids()),
        nut_solid_count=len(
            build.positioned_nut.Solids()
        ),
        assembly_solid_count=len(
            build.assembly.Solids()
        ),
        bolt_volume_mm3=bolt_volume_mm3,
        nut_volume_mm3=nut_volume_mm3,
        component_volume_sum_mm3=(
            bolt_volume_mm3 + nut_volume_mm3
        ),
        x_min_mm=bounds.xmin,
        x_max_mm=bounds.xmax,
        y_min_mm=bounds.ymin,
        y_max_mm=bounds.ymax,
        z_min_mm=bounds.zmin,
        z_max_mm=bounds.zmax,
    )


def export_and_reimport_bolt_nut_assembly(
    build: BoltNutAssemblyBuild,
    step_path: Path,
) -> tuple[cq.Shape, BoltNutAssemblyStepMeasurements]:
    """Export and reimport the assembly through STEP."""

    step_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    cq.exporters.export(
        build.assembly,
        str(step_path),
    )

    if not step_path.exists() or step_path.stat().st_size <= 0:
        raise RuntimeError(
            "Bolt-nut assembly STEP export is empty."
        )

    reimported_value = cq.importers.importStep(
        str(step_path)
    ).val()

    if not isinstance(reimported_value, cq.Shape):
        raise TypeError(
            "STEP reimport did not return a CAD shape."
        )

    reimported = reimported_value

    native_solids = build.assembly.Solids()
    reimported_solids = reimported.Solids()

    native_volume = sum(
        solid.Volume()
        for solid in native_solids
    )

    reimported_volume = sum(
        solid.Volume()
        for solid in reimported_solids
    )

    if native_volume <= 0.0:
        raise RuntimeError(
            "Native assembly volume must be positive."
        )

    native_bounds = build.assembly.BoundingBox()
    reimported_bounds = reimported.BoundingBox()

    bounds_errors = (
        abs(native_bounds.xmin - reimported_bounds.xmin),
        abs(native_bounds.xmax - reimported_bounds.xmax),
        abs(native_bounds.ymin - reimported_bounds.ymin),
        abs(native_bounds.ymax - reimported_bounds.ymax),
        abs(native_bounds.zmin - reimported_bounds.zmin),
        abs(native_bounds.zmax - reimported_bounds.zmax),
    )

    measurements = BoltNutAssemblyStepMeasurements(
        native_solid_count=len(native_solids),
        reimported_solid_count=len(reimported_solids),
        native_component_volume_mm3=native_volume,
        reimported_component_volume_mm3=(
            reimported_volume
        ),
        relative_volume_error=abs(
            reimported_volume - native_volume
        )
        / native_volume,
        maximum_bounds_error_mm=max(bounds_errors),
    )

    return reimported, measurements


def validate_bolt_nut_step_round_trip(
    measurements: BoltNutAssemblyStepMeasurements,
    quality_policy: GeometryQualityPolicy,
) -> None:
    """Apply governed assembly STEP acceptance gates."""

    if measurements.native_solid_count != 2:
        raise RuntimeError(
            "Native bolt-nut assembly must contain two solids."
        )

    if measurements.reimported_solid_count != 2:
        raise RuntimeError(
            "STEP-reimported assembly must contain two solids."
        )

    if (
        measurements.relative_volume_error
        > quality_policy.step_volume_relative_tolerance
    ):
        raise RuntimeError(
            "Assembly STEP relative volume error exceeds "
            "the governed tolerance."
        )

    if (
        measurements.maximum_bounds_error_mm
        > quality_policy.step_bounds_tolerance_mm
    ):
        raise RuntimeError(
            "Assembly STEP bounds error exceeds "
            "the governed tolerance."
        )
