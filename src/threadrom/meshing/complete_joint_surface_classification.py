"""Classification of complete-joint volumes and surfaces."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import gmsh  # type: ignore[import-untyped]

from threadrom.engineering.baseline_assembly import (
    BaselineAssembly,
)
from threadrom.geometry.bolt_blank import BoltBlankDefinition
from threadrom.geometry.nut_blank import NutBlankDefinition
from threadrom.meshing.nut_surface_classification import (
    NutSurfaceClassificationDefinition,
    NutSurfaceClassificationResult,
    classify_selected_model_nut_surfaces,
)
from threadrom.meshing.surface_classification import (
    SurfaceClassificationDefinition,
    SurfaceClassificationResult,
    classify_selected_model_surfaces,
)

BOLT = "bolt"
NUT = "nut"
HEAD_SIDE_MEMBER = "head_side_member"
NUT_SIDE_MEMBER = "nut_side_member"

HEAD_MEMBER_HEAD_BEARING = "head_member_head_bearing"
HEAD_MEMBER_INTERFACE = "head_member_interface"
HEAD_MEMBER_OUTER = "head_member_outer"
HEAD_MEMBER_CLEARANCE_HOLE = (
    "head_member_clearance_hole"
)

NUT_MEMBER_INTERFACE = "nut_member_interface"
NUT_MEMBER_NUT_BEARING = "nut_member_nut_bearing"
NUT_MEMBER_OUTER = "nut_member_outer"
NUT_MEMBER_CLEARANCE_HOLE = (
    "nut_member_clearance_hole"
)

COMPONENT_ORDER = (
    BOLT,
    NUT,
    HEAD_SIDE_MEMBER,
    NUT_SIDE_MEMBER,
)

MEMBER_REGION_ORDER = (
    HEAD_MEMBER_HEAD_BEARING,
    HEAD_MEMBER_INTERFACE,
    HEAD_MEMBER_OUTER,
    HEAD_MEMBER_CLEARANCE_HOLE,
    NUT_MEMBER_INTERFACE,
    NUT_MEMBER_NUT_BEARING,
    NUT_MEMBER_OUTER,
    NUT_MEMBER_CLEARANCE_HOLE,
)


@dataclass(frozen=True)
class CompleteJointSurfaceClassificationDefinition:
    """Governed complete-joint classification settings."""

    classification_id: str
    assembly_id: str
    geometry_id: str
    plane_tolerance_mm: float
    radial_tolerance_mm: float
    volume_names: tuple[tuple[str, str], ...]
    member_surface_names: tuple[
        tuple[str, str],
        ...,
    ]
    expected_volume_count: int
    expected_member_surface_count: int

    def volume_name(
        self,
        component: str,
    ) -> str:
        """Return the physical name for one volume."""

        lookup = dict(self.volume_names)

        try:
            return lookup[component]
        except KeyError as error:
            raise ValueError(
                f"Unknown joint component: {component}"
            ) from error

    def member_surface_name(
        self,
        region: str,
    ) -> str:
        """Return the physical name for one member region."""

        lookup = dict(self.member_surface_names)

        try:
            return lookup[region]
        except KeyError as error:
            raise ValueError(
                f"Unknown member-surface region: {region}"
            ) from error


@dataclass(frozen=True)
class CompleteJointVolumeIdentification:
    """Component identity recovered from imported CAD."""

    bolt_tag: int
    nut_tag: int
    head_side_member_tag: int
    nut_side_member_tag: int

    def items(self) -> tuple[tuple[str, int], ...]:
        """Return components in governed order."""

        return (
            (BOLT, self.bolt_tag),
            (NUT, self.nut_tag),
            (
                HEAD_SIDE_MEMBER,
                self.head_side_member_tag,
            ),
            (
                NUT_SIDE_MEMBER,
                self.nut_side_member_tag,
            ),
        )


@dataclass(frozen=True)
class ClassifiedMemberSurface:
    """Measured surface belonging to one clamped member."""

    tag: int
    component: str
    region: str
    surface_type: str
    area_mm2: float
    center_z_mm: float
    radial_envelope_mm: float
    z_min_mm: float
    z_max_mm: float


@dataclass(frozen=True)
class JointPhysicalGroupRegistration:
    """One registered joint physical group."""

    physical_name: str
    dimension: int
    physical_tag: int
    entity_count: int


@dataclass(frozen=True)
class CompleteJointSurfaceClassificationResult:
    """Verified complete-joint classification result."""

    volumes: CompleteJointVolumeIdentification
    bolt: SurfaceClassificationResult
    nut: NutSurfaceClassificationResult
    member_surfaces: tuple[
        ClassifiedMemberSurface,
        ...,
    ]
    physical_groups: tuple[
        JointPhysicalGroupRegistration,
        ...,
    ]

    def member_count_for(
        self,
        region: str,
    ) -> int:
        """Return the number of member surfaces in a region."""

        return sum(
            surface.region == region
            for surface in self.member_surfaces
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


def _number(
    data: Mapping[str, object],
    key: str,
) -> float:
    """Return one required non-negative number."""

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


def load_complete_joint_surface_definition(
    path: Path,
) -> CompleteJointSurfaceClassificationDefinition:
    """Load governed complete-joint classification settings."""

    with path.open("rb") as config_file:
        data: dict[str, object] = tomllib.load(
            config_file
        )

    identity = _section(data, "identity")
    classification = _section(
        data,
        "classification",
    )
    volumes = _section(data, "volume_groups")
    members = _section(
        data,
        "member_surface_groups",
    )
    verification = _section(
        data,
        "verification",
    )

    volume_names = tuple(
        (
            component,
            _string(volumes, component),
        )
        for component in COMPONENT_ORDER
    )

    member_surface_names = tuple(
        (
            region,
            _string(members, region),
        )
        for region in MEMBER_REGION_ORDER
    )

    return CompleteJointSurfaceClassificationDefinition(
        classification_id=_string(
            identity,
            "classification_id",
        ),
        assembly_id=_string(
            identity,
            "assembly_id",
        ),
        geometry_id=_string(
            identity,
            "geometry_id",
        ),
        plane_tolerance_mm=_number(
            classification,
            "plane_tolerance_mm",
        ),
        radial_tolerance_mm=_number(
            classification,
            "radial_tolerance_mm",
        ),
        volume_names=volume_names,
        member_surface_names=member_surface_names,
        expected_volume_count=_integer(
            verification,
            "expected_volume_count",
        ),
        expected_member_surface_count=_integer(
            verification,
            "expected_member_surface_count",
        ),
    )


def _surface_tags_for_volume(
    volume_tag: int,
) -> tuple[int, ...]:
    """Return direct boundary surfaces of one volume."""

    return tuple(
        sorted(
            int(tag)
            for dimension, tag in gmsh.model.getBoundary(
                [(3, volume_tag)],
                combined=False,
                oriented=False,
                recursive=False,
            )
            if dimension == 2
        )
    )


def identify_complete_joint_volumes(
    assembly: BaselineAssembly,
    definition: (
        CompleteJointSurfaceClassificationDefinition
    ),
) -> CompleteJointVolumeIdentification:
    """Identify all four components from governed geometry."""

    volume_entities = gmsh.model.getEntities(3)

    if (
        len(volume_entities)
        != definition.expected_volume_count
    ):
        raise RuntimeError(
            "Unexpected complete-joint volume count: "
            f"{len(volume_entities)}."
        )

    bolt_tag: int | None = None
    nut_tag: int | None = None
    head_member_tag: int | None = None
    nut_member_tag: int | None = None

    tolerance = max(
        definition.plane_tolerance_mm,
        definition.radial_tolerance_mm,
    )

    for _, tag in volume_entities:
        bounds = gmsh.model.getBoundingBox(3, tag)
        center = gmsh.model.occ.getCenterOfMass(3, tag)

        (
            x_min,
            y_min,
            z_min,
            x_max,
            y_max,
            z_max,
        ) = bounds

        x_extent = x_max - x_min
        y_extent = y_max - y_min
        axial_extent = z_max - z_min

        is_member_diameter = (
            abs(
                x_extent
                - assembly.outer_diameter_mm
            )
            <= tolerance
            and abs(
                y_extent
                - assembly.outer_diameter_mm
            )
            <= tolerance
        )

        if z_min < -tolerance and axial_extent > 30.0:
            bolt_tag = int(tag)
            continue

        if is_member_diameter:
            head_center_z = (
                assembly.upper_member_thickness_mm
                / 2.0
            )

            nut_member_center_z = (
                assembly.upper_member_thickness_mm
                + (
                    assembly.lower_member_thickness_mm
                    / 2.0
                )
            )

            if (
                abs(center[2] - head_center_z)
                <= tolerance
            ):
                head_member_tag = int(tag)
                continue

            if (
                abs(center[2] - nut_member_center_z)
                <= tolerance
            ):
                nut_member_tag = int(tag)
                continue

        expected_nut_center_z = (
            assembly.total_grip_length_mm
            + assembly.nut_thickness_mm / 2.0
        )

        if (
            abs(center[2] - expected_nut_center_z)
            <= tolerance
        ):
            nut_tag = int(tag)

    identified = (
        bolt_tag,
        nut_tag,
        head_member_tag,
        nut_member_tag,
    )

    if any(tag is None for tag in identified):
        raise RuntimeError(
            "Could not identify every complete-joint volume."
        )

    return CompleteJointVolumeIdentification(
        bolt_tag=cast(int, bolt_tag),
        nut_tag=cast(int, nut_tag),
        head_side_member_tag=cast(
            int,
            head_member_tag,
        ),
        nut_side_member_tag=cast(
            int,
            nut_member_tag,
        ),
    )


def _classify_member_surface(
    *,
    tag: int,
    component: str,
    assembly: BaselineAssembly,
    definition: (
        CompleteJointSurfaceClassificationDefinition
    ),
) -> ClassifiedMemberSurface:
    """Classify one annular-member boundary surface."""

    surface_type = gmsh.model.getType(2, tag)

    (
        x_min,
        y_min,
        z_min,
        x_max,
        y_max,
        z_max,
    ) = gmsh.model.getBoundingBox(2, tag)

    center = gmsh.model.occ.getCenterOfMass(2, tag)
    area = gmsh.model.occ.getMass(2, tag)

    radial_envelope = max(
        abs(x_min),
        abs(x_max),
        abs(y_min),
        abs(y_max),
    )

    plane_tolerance = definition.plane_tolerance_mm
    radial_tolerance = definition.radial_tolerance_mm

    outer_radius = assembly.outer_diameter_mm / 2.0
    hole_radius = (
        assembly.clearance_hole_diameter_mm / 2.0
    )

    if surface_type == "Plane":
        if abs(z_max - z_min) > plane_tolerance:
            raise RuntimeError(
                f"Member plane {tag} has axial thickness."
            )

        if component == HEAD_SIDE_MEMBER:
            if abs(center[2]) <= plane_tolerance:
                region = HEAD_MEMBER_HEAD_BEARING
            elif (
                abs(
                    center[2]
                    - assembly.upper_member_thickness_mm
                )
                <= plane_tolerance
            ):
                region = HEAD_MEMBER_INTERFACE
            else:
                raise RuntimeError(
                    f"Unexpected head-member plane: {tag}."
                )

        elif component == NUT_SIDE_MEMBER:
            if (
                abs(
                    center[2]
                    - assembly.upper_member_thickness_mm
                )
                <= plane_tolerance
            ):
                region = NUT_MEMBER_INTERFACE
            elif (
                abs(
                    center[2]
                    - assembly.total_grip_length_mm
                )
                <= plane_tolerance
            ):
                region = NUT_MEMBER_NUT_BEARING
            else:
                raise RuntimeError(
                    f"Unexpected nut-member plane: {tag}."
                )

        else:
            raise ValueError(
                f"Invalid member component: {component}."
            )

    elif surface_type == "Cylinder":
        if (
            abs(radial_envelope - outer_radius)
            <= radial_tolerance
        ):
            region = (
                HEAD_MEMBER_OUTER
                if component == HEAD_SIDE_MEMBER
                else NUT_MEMBER_OUTER
            )

        elif (
            abs(radial_envelope - hole_radius)
            <= radial_tolerance
        ):
            region = (
                HEAD_MEMBER_CLEARANCE_HOLE
                if component == HEAD_SIDE_MEMBER
                else NUT_MEMBER_CLEARANCE_HOLE
            )

        else:
            raise RuntimeError(
                f"Unexpected member-cylinder radius: {tag}."
            )

    else:
        raise RuntimeError(
            "Unexpected member surface type: "
            f"{surface_type}."
        )

    return ClassifiedMemberSurface(
        tag=tag,
        component=component,
        region=region,
        surface_type=surface_type,
        area_mm2=float(area),
        center_z_mm=float(center[2]),
        radial_envelope_mm=float(radial_envelope),
        z_min_mm=float(z_min),
        z_max_mm=float(z_max),
    )


def _register_group(
    *,
    dimension: int,
    tags: list[int],
    physical_name: str,
) -> JointPhysicalGroupRegistration:
    """Register one physical group in the active model."""

    physical_tag = gmsh.model.addPhysicalGroup(
        dimension,
        tags,
    )

    gmsh.model.setPhysicalName(
        dimension,
        physical_tag,
        physical_name,
    )

    registered = gmsh.model.getEntitiesForPhysicalGroup(
        dimension,
        physical_tag,
    )

    return JointPhysicalGroupRegistration(
        physical_name=physical_name,
        dimension=dimension,
        physical_tag=int(physical_tag),
        entity_count=len(registered),
    )


def classify_current_complete_joint(
    assembly: BaselineAssembly,
    bolt_blank: BoltBlankDefinition,
    nut_blank: NutBlankDefinition,
    bolt_definition: SurfaceClassificationDefinition,
    nut_definition: NutSurfaceClassificationDefinition,
    definition: (
        CompleteJointSurfaceClassificationDefinition
    ),
) -> CompleteJointSurfaceClassificationResult:
    """Classify and register the active four-volume joint."""

    if definition.assembly_id != assembly.assembly_id:
        raise ValueError(
            "Joint classification and assembly IDs differ."
        )

    volumes = identify_complete_joint_volumes(
        assembly,
        definition,
    )

    registrations: list[
        JointPhysicalGroupRegistration
    ] = []

    for component, volume_tag in volumes.items():
        registrations.append(
            _register_group(
                dimension=3,
                tags=[volume_tag],
                physical_name=definition.volume_name(
                    component
                ),
            )
        )

    bolt_surface_tags = _surface_tags_for_volume(
        volumes.bolt_tag
    )

    nut_surface_tags = _surface_tags_for_volume(
        volumes.nut_tag
    )

    bolt_result = classify_selected_model_surfaces(
        bolt_surface_tags,
        bolt_blank,
        bolt_definition,
    )

    nut_result = classify_selected_model_nut_surfaces(
        nut_surface_tags,
        nut_blank,
        nut_definition,
        axial_offset_mm=assembly.nut_translation_z_mm,
    )

    member_surfaces: list[
        ClassifiedMemberSurface
    ] = []

    for component, volume_tag in (
        (
            HEAD_SIDE_MEMBER,
            volumes.head_side_member_tag,
        ),
        (
            NUT_SIDE_MEMBER,
            volumes.nut_side_member_tag,
        ),
    ):
        for tag in _surface_tags_for_volume(volume_tag):
            member_surfaces.append(
                _classify_member_surface(
                    tag=tag,
                    component=component,
                    assembly=assembly,
                    definition=definition,
                )
            )

    ordered_member_surfaces = tuple(
        sorted(
            member_surfaces,
            key=lambda surface: surface.tag,
        )
    )

    for region in MEMBER_REGION_ORDER:
        tags = [
            surface.tag
            for surface in ordered_member_surfaces
            if surface.region == region
        ]

        if len(tags) != 1:
            raise RuntimeError(
                "Expected one member surface for "
                f"{region}; found {len(tags)}."
            )

        registrations.append(
            _register_group(
                dimension=2,
                tags=tags,
                physical_name=(
                    definition.member_surface_name(
                        region
                    )
                ),
            )
        )

    result = CompleteJointSurfaceClassificationResult(
        volumes=volumes,
        bolt=bolt_result,
        nut=nut_result,
        member_surfaces=ordered_member_surfaces,
        physical_groups=tuple(registrations),
    )

    validate_complete_joint_surface_classification(
        result,
        definition,
    )

    return result


def validate_complete_joint_surface_classification(
    result: CompleteJointSurfaceClassificationResult,
    definition: (
        CompleteJointSurfaceClassificationDefinition
    ),
) -> None:
    """Apply complete-joint surface acceptance gates."""

    if (
        len(result.volumes.items())
        != definition.expected_volume_count
    ):
        raise RuntimeError(
            "Complete-joint volume identification failed."
        )

    if (
        len(result.member_surfaces)
        != definition.expected_member_surface_count
    ):
        raise RuntimeError(
            "Unexpected number of member surfaces."
        )

    for region in MEMBER_REGION_ORDER:
        if result.member_count_for(region) != 1:
            raise RuntimeError(
                f"Invalid member-surface count: {region}."
            )

    all_component_surfaces = (
        [surface.tag for surface in result.bolt.surfaces]
        + [surface.tag for surface in result.nut.surfaces]
        + [
            surface.tag
            for surface in result.member_surfaces
        ]
    )

    if len(all_component_surfaces) != len(
        set(all_component_surfaces)
    ):
        raise RuntimeError(
            "A joint surface was assigned to multiple components."
        )


def classify_complete_joint_step(
    step_path: Path,
    assembly: BaselineAssembly,
    bolt_blank: BoltBlankDefinition,
    nut_blank: NutBlankDefinition,
    bolt_definition: SurfaceClassificationDefinition,
    nut_definition: NutSurfaceClassificationDefinition,
    definition: (
        CompleteJointSurfaceClassificationDefinition
    ),
) -> CompleteJointSurfaceClassificationResult:
    """Import and classify one complete-joint STEP file."""

    if not step_path.exists() or step_path.stat().st_size <= 0:
        raise FileNotFoundError(
            f"Valid complete-joint STEP not found: {step_path}"
        )

    initialized = False

    try:
        gmsh.initialize()
        initialized = True

        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.model.add(
            f"{definition.classification_id}-complete-joint"
        )

        gmsh.model.occ.importShapes(
            str(step_path),
            True,
        )
        gmsh.model.occ.synchronize()

        return classify_current_complete_joint(
            assembly,
            bolt_blank,
            nut_blank,
            bolt_definition,
            nut_definition,
            definition,
        )

    finally:
        if initialized:
            gmsh.finalize()
