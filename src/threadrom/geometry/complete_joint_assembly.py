"""Construction and validation of the complete joint assembly."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import cadquery as cq

from threadrom.engineering.baseline_assembly import (
    BaselineAssembly,
)
from threadrom.geometry.bolt_nut_assembly import (
    BoltNutAssemblyBuild,
)
from threadrom.geometry.geometry_quality import (
    GeometryQualityPolicy,
)


@dataclass(frozen=True)
class AssemblyGeometryValidationPolicy:
    """Governed acceptance criteria for assembly geometry."""

    validation_id: str
    assembly_id: str
    expected_component_count: int
    expected_solids_per_component: int
    coordinate_tolerance_mm: float
    maximum_pairwise_volume_mm3: float
    maximum_mating_pair_volume_mm3: float


@dataclass(frozen=True)
class CompleteJointAssemblyBuild:
    """Four independent solids forming the baseline joint."""

    bolt: cq.Shape
    positioned_nut: cq.Shape
    head_side_member: cq.Shape
    nut_side_member: cq.Shape
    assembly: cq.Compound


@dataclass(frozen=True)
class ComponentInterferenceMeasurement:
    """Material intersection between two assembly components."""

    first_component: str
    second_component: str
    intersection_volume_mm3: float


@dataclass(frozen=True)
class CompleteJointAssemblyMeasurements:
    """Measured topology, placement and interference results."""

    component_solid_counts: tuple[
        tuple[str, int],
        ...,
    ]
    assembly_solid_count: int
    head_side_member_z_min_mm: float
    head_side_member_z_max_mm: float
    nut_side_member_z_min_mm: float
    nut_side_member_z_max_mm: float
    interferences: tuple[
        ComponentInterferenceMeasurement,
        ...,
    ]

    @property
    def maximum_interference_volume_mm3(self) -> float:
        """Return the largest measured pairwise intersection."""

        return max(
            (
                item.intersection_volume_mm3
                for item in self.interferences
            ),
            default=0.0,
        )


def _section(
    data: Mapping[str, object],
    key: str,
) -> Mapping[str, object]:
    """Return one required TOML section."""

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
    """Return one required non-empty string."""

    value = data.get(key)

    if not isinstance(value, str) or not value.strip():
        raise TypeError(
            f"Missing or invalid string value: {key}"
        )

    return value


def _integer(
    data: Mapping[str, object],
    key: str,
) -> int:
    """Return one required positive integer."""

    value = data.get(key)

    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(
            f"Missing or invalid integer value: {key}"
        )

    if value <= 0:
        raise ValueError(
            f"Integer value must be positive: {key}"
        )

    return value


def _number(
    data: Mapping[str, object],
    key: str,
) -> float:
    """Return one required non-negative numerical value."""

    value = data.get(key)

    if (
        isinstance(value, bool)
        or not isinstance(value, int | float)
    ):
        raise TypeError(
            f"Missing or invalid numerical value: {key}"
        )

    result = float(value)

    if result < 0.0:
        raise ValueError(
            f"Numerical value cannot be negative: {key}"
        )

    return result


def load_assembly_geometry_validation_policy(
    path: Path,
) -> AssemblyGeometryValidationPolicy:
    """Load governed complete-assembly acceptance criteria."""

    with path.open("rb") as config_file:
        data: dict[str, object] = tomllib.load(
            config_file
        )

    identity = _section(data, "identity")
    topology = _section(data, "topology")
    placement = _section(data, "placement")
    interference = _section(data, "interference")

    return AssemblyGeometryValidationPolicy(
        validation_id=_string(
            identity,
            "validation_id",
        ),
        assembly_id=_string(
            identity,
            "assembly_id",
        ),
        expected_component_count=_integer(
            topology,
            "expected_component_count",
        ),
        expected_solids_per_component=_integer(
            topology,
            "expected_solids_per_component",
        ),
        coordinate_tolerance_mm=_number(
            placement,
            "coordinate_tolerance_mm",
        ),
        maximum_pairwise_volume_mm3=_number(
            interference,
            "maximum_pairwise_volume_mm3",
        ),
        maximum_mating_pair_volume_mm3=_number(
            interference,
            "maximum_mating_pair_volume_mm3",
        ),
    )


def _require_shape(
    value: object,
    component_name: str,
) -> cq.Shape:
    """Return a CadQuery shape or raise a controlled error."""

    if not isinstance(value, cq.Shape):
        raise TypeError(
            f"{component_name} creation did not return "
            "a CAD shape."
        )

    return value


def build_complete_joint_assembly(
    bolt_nut: BoltNutAssemblyBuild,
    definition: BaselineAssembly,
) -> CompleteJointAssemblyBuild:
    """Build the two annular members and four-solid joint."""

    outer_radius_mm = (
        definition.outer_diameter_mm / 2.0
    )

    hole_radius_mm = (
        definition.clearance_hole_diameter_mm / 2.0
    )

    head_side_member = _require_shape(
        (
            cq.Workplane("XY")
            .circle(outer_radius_mm)
            .circle(hole_radius_mm)
            .extrude(
                definition.upper_member_thickness_mm
            )
            .val()
        ),
        "Head-side member",
    )

    nut_side_member = _require_shape(
        (
            cq.Workplane("XY")
            .workplane(
                offset=(
                    definition
                    .upper_member_thickness_mm
                )
            )
            .circle(outer_radius_mm)
            .circle(hole_radius_mm)
            .extrude(
                definition.lower_member_thickness_mm
            )
            .val()
        ),
        "Nut-side member",
    )

    components = (
        bolt_nut.bolt,
        bolt_nut.positioned_nut,
        head_side_member,
        nut_side_member,
    )

    for component in components:
        if not component.isValid():
            raise RuntimeError(
                "Complete joint contains an invalid "
                "component shape."
            )

    assembly = cq.Compound.makeCompound(
        list(components)
    )

    if not assembly.isValid():
        raise RuntimeError(
            "Complete joint assembly compound is invalid."
        )

    return CompleteJointAssemblyBuild(
        bolt=bolt_nut.bolt,
        positioned_nut=bolt_nut.positioned_nut,
        head_side_member=head_side_member,
        nut_side_member=nut_side_member,
        assembly=assembly,
    )


def measure_complete_joint_assembly(
    build: CompleteJointAssemblyBuild,
) -> CompleteJointAssemblyMeasurements:
    """Measure component topology, placement and interference."""

    components = (
        ("bolt", build.bolt),
        ("nut", build.positioned_nut),
        ("head_side_member", build.head_side_member),
        ("nut_side_member", build.nut_side_member),
    )

    component_solid_counts = tuple(
        (
            name,
            len(shape.Solids()),
        )
        for name, shape in components
    )

    interference_results: list[
        ComponentInterferenceMeasurement
    ] = []

    for first_index, (
        first_name,
        first_shape,
    ) in enumerate(components):
        for (
            second_name,
            second_shape,
        ) in components[first_index + 1 :]:
            intersection = first_shape.intersect(
                second_shape
            )

            interference_results.append(
                ComponentInterferenceMeasurement(
                    first_component=first_name,
                    second_component=second_name,
                    intersection_volume_mm3=(
                        intersection.Volume()
                    ),
                )
            )

    head_bounds = build.head_side_member.BoundingBox()
    nut_side_bounds = (
        build.nut_side_member.BoundingBox()
    )

    return CompleteJointAssemblyMeasurements(
        component_solid_counts=component_solid_counts,
        assembly_solid_count=len(
            build.assembly.Solids()
        ),
        head_side_member_z_min_mm=head_bounds.zmin,
        head_side_member_z_max_mm=head_bounds.zmax,
        nut_side_member_z_min_mm=nut_side_bounds.zmin,
        nut_side_member_z_max_mm=nut_side_bounds.zmax,
        interferences=tuple(interference_results),
    )


def validate_complete_joint_assembly(
    measurements: CompleteJointAssemblyMeasurements,
    definition: BaselineAssembly,
    policy: AssemblyGeometryValidationPolicy,
) -> None:
    """Apply governed four-component geometry gates."""

    if policy.assembly_id != definition.assembly_id:
        raise ValueError(
            "Assembly validation and baseline IDs differ."
        )

    if (
        len(measurements.component_solid_counts)
        != policy.expected_component_count
    ):
        raise RuntimeError(
            "Unexpected number of joint components."
        )

    for (
        component_name,
        solid_count,
    ) in measurements.component_solid_counts:
        if (
            solid_count
            != policy.expected_solids_per_component
        ):
            raise RuntimeError(
                f"Unexpected solid count for "
                f"{component_name}: {solid_count}."
            )

    if (
        measurements.assembly_solid_count
        != policy.expected_component_count
    ):
        raise RuntimeError(
            "Complete assembly does not contain the "
            "expected number of solids."
        )

    expected_head_z_min = 0.0
    expected_head_z_max = (
        definition.upper_member_thickness_mm
    )

    expected_nut_side_z_min = (
        definition.upper_member_thickness_mm
    )
    expected_nut_side_z_max = (
        definition.total_grip_length_mm
    )

    placement_checks = (
        (
            "head-side member minimum Z",
            measurements.head_side_member_z_min_mm,
            expected_head_z_min,
        ),
        (
            "head-side member maximum Z",
            measurements.head_side_member_z_max_mm,
            expected_head_z_max,
        ),
        (
            "nut-side member minimum Z",
            measurements.nut_side_member_z_min_mm,
            expected_nut_side_z_min,
        ),
        (
            "nut-side member maximum Z",
            measurements.nut_side_member_z_max_mm,
            expected_nut_side_z_max,
        ),
    )

    for name, measured, expected in placement_checks:
        if (
            abs(measured - expected)
            > policy.coordinate_tolerance_mm
        ):
            raise RuntimeError(
                f"Invalid {name}: measured {measured}, "
                f"expected {expected}."
            )

    for result in measurements.interferences:
        component_pair = frozenset(
            (
                result.first_component,
                result.second_component,
            )
        )

        if component_pair == frozenset(
            ("bolt", "nut")
        ):
            maximum_volume_mm3 = (
                policy.maximum_mating_pair_volume_mm3
            )
        else:
            maximum_volume_mm3 = (
                policy.maximum_pairwise_volume_mm3
            )

        if (
            result.intersection_volume_mm3
            > maximum_volume_mm3
        ):
            raise RuntimeError(
                "Material interference exceeds policy: "
                f"{result.first_component} vs "
                f"{result.second_component} = "
                f"{result.intersection_volume_mm3} mm^3 "
                f"(limit {maximum_volume_mm3} mm^3)."
            )


@dataclass(frozen=True)
class CompleteJointAssemblyStepMeasurements:
    """Measurements comparing native and STEP joint geometry."""

    native_solid_count: int
    reimported_solid_count: int
    native_component_volume_mm3: float
    reimported_component_volume_mm3: float
    relative_volume_error: float
    maximum_bounds_error_mm: float


def export_and_reimport_complete_joint_assembly(
    build: CompleteJointAssemblyBuild,
    step_path: Path,
) -> tuple[cq.Shape, CompleteJointAssemblyStepMeasurements]:
    """Export and reimport the four-solid joint through STEP."""

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
            "Complete joint STEP export is empty."
        )

    reimported_value = cq.importers.importStep(
        str(step_path)
    ).val()

    if not isinstance(reimported_value, cq.Shape):
        raise TypeError(
            "Complete joint STEP reimport did not "
            "return a CAD shape."
        )

    reimported = reimported_value

    if not reimported.isValid():
        raise RuntimeError(
            "Reimported complete joint geometry is invalid."
        )

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
            "Native complete-joint volume must be positive."
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

    measurements = CompleteJointAssemblyStepMeasurements(
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


def validate_complete_joint_step_round_trip(
    measurements: CompleteJointAssemblyStepMeasurements,
    quality_policy: GeometryQualityPolicy,
    expected_solid_count: int,
) -> None:
    """Apply governed complete-joint STEP acceptance gates."""

    if measurements.native_solid_count != expected_solid_count:
        raise RuntimeError(
            "Native complete joint has an unexpected "
            "solid count."
        )

    if (
        measurements.reimported_solid_count
        != expected_solid_count
    ):
        raise RuntimeError(
            "STEP-reimported complete joint has an "
            "unexpected solid count."
        )

    if (
        measurements.relative_volume_error
        > quality_policy.step_volume_relative_tolerance
    ):
        raise RuntimeError(
            "Complete-joint STEP relative volume error "
            "exceeds policy."
        )

    if (
        measurements.maximum_bounds_error_mm
        > quality_policy.step_bounds_tolerance_mm
    ):
        raise RuntimeError(
            "Complete-joint STEP bounds error exceeds policy."
        )
