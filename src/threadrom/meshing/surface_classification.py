"""Geometry-driven classification of bolt CAD surfaces."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import gmsh  # type: ignore[import-untyped]

from threadrom.geometry.bolt_blank import BoltBlankDefinition

HEAD_TOP = "head_top"
UNDER_HEAD_BEARING = "under_head_bearing"
HEAD_SIDES = "head_sides"
THREAD_SURFACES = "thread_surfaces"
BOLT_TIP = "bolt_tip"
TRANSITION_SURFACES = "transition_surfaces"

REGION_ORDER = (
    HEAD_TOP,
    UNDER_HEAD_BEARING,
    HEAD_SIDES,
    THREAD_SURFACES,
    BOLT_TIP,
    TRANSITION_SURFACES,
)


@dataclass(frozen=True)
class SurfaceClassificationDefinition:
    """Controlled rules and names for bolt-surface classification."""

    mesh_id: str
    geometry_id: str
    plane_tolerance_mm: float
    head_top_name: str
    under_head_bearing_name: str
    head_sides_name: str
    thread_surfaces_name: str
    bolt_tip_name: str
    transition_surfaces_name: str
    minimum_head_top_surface_count: int
    minimum_under_head_surface_count: int
    minimum_head_side_surface_count: int
    minimum_thread_surface_count: int
    minimum_tip_surface_count: int

    def physical_name(self, region: str) -> str:
        """Return the configured physical-group name for a region."""

        names = {
            HEAD_TOP: self.head_top_name,
            UNDER_HEAD_BEARING: self.under_head_bearing_name,
            HEAD_SIDES: self.head_sides_name,
            THREAD_SURFACES: self.thread_surfaces_name,
            BOLT_TIP: self.bolt_tip_name,
            TRANSITION_SURFACES: self.transition_surfaces_name,
        }

        try:
            return names[region]
        except KeyError as error:
            raise ValueError(f"Unknown surface region: {region}") from error


@dataclass(frozen=True)
class ClassifiedSurface:
    """Measured CAD surface and its assigned engineering region."""

    tag: int
    region: str
    area_mm2: float
    center_x_mm: float
    center_y_mm: float
    center_z_mm: float
    x_min_mm: float
    x_max_mm: float
    y_min_mm: float
    y_max_mm: float
    z_min_mm: float
    z_max_mm: float

    @property
    def z_span_mm(self) -> float:
        """Return the axial surface bounding-box span."""

        return self.z_max_mm - self.z_min_mm


@dataclass(frozen=True)
class PhysicalGroupRegistration:
    """Registered Gmsh physical group."""

    region: str
    physical_name: str
    physical_tag: int
    entity_count: int


@dataclass(frozen=True)
class SurfaceClassificationResult:
    """Complete classified surface topology."""

    imported_volume_count: int
    surfaces: tuple[ClassifiedSurface, ...]
    physical_groups: tuple[PhysicalGroupRegistration, ...]

    @property
    def surface_count(self) -> int:
        """Return the total classified surface count."""

        return len(self.surfaces)

    def tags_for(self, region: str) -> tuple[int, ...]:
        """Return all surface tags assigned to a region."""

        return tuple(surface.tag for surface in self.surfaces if surface.region == region)

    def count_for(self, region: str) -> int:
        """Return the number of surfaces assigned to a region."""

        return len(self.tags_for(region))


def _section(
    data: Mapping[str, object],
    key: str,
) -> Mapping[str, object]:
    """Return a required TOML section."""

    value = data.get(key)

    if not isinstance(value, dict):
        raise TypeError(f"Missing or invalid configuration section: {key}")

    return cast(Mapping[str, object], value)


def _string(
    data: Mapping[str, object],
    key: str,
) -> str:
    """Return a required non-empty string."""

    value = data.get(key)

    if not isinstance(value, str) or not value.strip():
        raise TypeError(f"Missing or invalid string value: {key}")

    return value


def _number(
    data: Mapping[str, object],
    key: str,
) -> float:
    """Return a required numerical value."""

    value = data.get(key)

    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"Missing or invalid numerical value: {key}")

    return float(value)


def _integer(
    data: Mapping[str, object],
    key: str,
) -> int:
    """Return a required integer value."""

    value = data.get(key)

    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"Missing or invalid integer value: {key}")

    return value


def load_surface_classification_definition(
    config_path: Path,
) -> SurfaceClassificationDefinition:
    """Load and validate the surface-classification policy."""

    with config_path.open("rb") as config_file:
        data: dict[str, object] = tomllib.load(config_file)

    identity = _section(data, "identity")
    classification = _section(data, "classification")
    physical_groups = _section(data, "physical_groups")
    verification = _section(data, "verification")

    definition = SurfaceClassificationDefinition(
        mesh_id=_string(identity, "mesh_id"),
        geometry_id=_string(identity, "geometry_id"),
        plane_tolerance_mm=_number(
            classification,
            "plane_tolerance_mm",
        ),
        head_top_name=_string(
            physical_groups,
            "head_top",
        ),
        under_head_bearing_name=_string(
            physical_groups,
            "under_head_bearing",
        ),
        head_sides_name=_string(
            physical_groups,
            "head_sides",
        ),
        thread_surfaces_name=_string(
            physical_groups,
            "thread_surfaces",
        ),
        bolt_tip_name=_string(
            physical_groups,
            "bolt_tip",
        ),
        transition_surfaces_name=_string(
            physical_groups,
            "transition_surfaces",
        ),
        minimum_head_top_surface_count=_integer(
            verification,
            "minimum_head_top_surface_count",
        ),
        minimum_under_head_surface_count=_integer(
            verification,
            "minimum_under_head_surface_count",
        ),
        minimum_head_side_surface_count=_integer(
            verification,
            "minimum_head_side_surface_count",
        ),
        minimum_thread_surface_count=_integer(
            verification,
            "minimum_thread_surface_count",
        ),
        minimum_tip_surface_count=_integer(
            verification,
            "minimum_tip_surface_count",
        ),
    )

    if definition.plane_tolerance_mm <= 0.0:
        raise ValueError("Surface-classification tolerance must be positive.")

    minimum_counts = (
        definition.minimum_head_top_surface_count,
        definition.minimum_under_head_surface_count,
        definition.minimum_head_side_surface_count,
        definition.minimum_thread_surface_count,
        definition.minimum_tip_surface_count,
    )

    if any(count <= 0 for count in minimum_counts):
        raise ValueError("Required surface counts must all be positive.")

    return definition


def _lies_on_z_plane(
    z_min_mm: float,
    z_max_mm: float,
    plane_z_mm: float,
    tolerance_mm: float,
) -> bool:
    """Return whether a surface lies on a controlled axial plane."""

    return abs(z_min_mm - plane_z_mm) <= tolerance_mm and abs(z_max_mm - plane_z_mm) <= tolerance_mm


def classify_surface_region(
    *,
    z_min_mm: float,
    z_max_mm: float,
    blank_definition: BoltBlankDefinition,
    definition: SurfaceClassificationDefinition,
) -> str:
    """Classify one surface from its axial bounding limits."""

    tolerance_mm = definition.plane_tolerance_mm

    head_top_z_mm = -blank_definition.head_height_mm
    interface_z_mm = 0.0
    tip_z_mm = blank_definition.underhead_length_mm

    if _lies_on_z_plane(
        z_min_mm,
        z_max_mm,
        head_top_z_mm,
        tolerance_mm,
    ):
        return HEAD_TOP

    if _lies_on_z_plane(
        z_min_mm,
        z_max_mm,
        interface_z_mm,
        tolerance_mm,
    ):
        return UNDER_HEAD_BEARING

    if _lies_on_z_plane(
        z_min_mm,
        z_max_mm,
        tip_z_mm,
        tolerance_mm,
    ):
        return BOLT_TIP

    if z_min_mm >= head_top_z_mm - tolerance_mm and z_max_mm <= interface_z_mm + tolerance_mm:
        return HEAD_SIDES

    if z_min_mm >= interface_z_mm - tolerance_mm and z_max_mm <= tip_z_mm + tolerance_mm:
        return THREAD_SURFACES

    return TRANSITION_SURFACES


def _measure_and_classify_surfaces(
    blank_definition: BoltBlankDefinition,
    definition: SurfaceClassificationDefinition,
) -> tuple[ClassifiedSurface, ...]:
    """Measure and classify all current Gmsh model surfaces."""

    classified_surfaces: list[ClassifiedSurface] = []

    for dimension, tag in gmsh.model.getEntities(2):
        if dimension != 2:
            continue

        (
            x_min_mm,
            y_min_mm,
            z_min_mm,
            x_max_mm,
            y_max_mm,
            z_max_mm,
        ) = gmsh.model.getBoundingBox(
            2,
            tag,
        )

        area_mm2 = gmsh.model.occ.getMass(
            2,
            tag,
        )

        (
            center_x_mm,
            center_y_mm,
            center_z_mm,
        ) = gmsh.model.occ.getCenterOfMass(
            2,
            tag,
        )

        region = classify_surface_region(
            z_min_mm=float(z_min_mm),
            z_max_mm=float(z_max_mm),
            blank_definition=blank_definition,
            definition=definition,
        )

        classified_surfaces.append(
            ClassifiedSurface(
                tag=int(tag),
                region=region,
                area_mm2=float(area_mm2),
                center_x_mm=float(center_x_mm),
                center_y_mm=float(center_y_mm),
                center_z_mm=float(center_z_mm),
                x_min_mm=float(x_min_mm),
                x_max_mm=float(x_max_mm),
                y_min_mm=float(y_min_mm),
                y_max_mm=float(y_max_mm),
                z_min_mm=float(z_min_mm),
                z_max_mm=float(z_max_mm),
            )
        )

    return tuple(
        sorted(
            classified_surfaces,
            key=lambda surface: surface.tag,
        )
    )


def validate_surface_classification(
    result: SurfaceClassificationResult,
    definition: SurfaceClassificationDefinition,
) -> None:
    """Apply controlled topology-classification gates."""

    if result.imported_volume_count != 1:
        raise RuntimeError("Surface classification requires exactly one CAD volume.")

    if result.surface_count <= 0:
        raise RuntimeError("No CAD surfaces were available for classification.")

    all_tags = tuple(surface.tag for surface in result.surfaces)

    if len(all_tags) != len(set(all_tags)):
        raise RuntimeError("A CAD surface was classified more than once.")

    if any(surface.area_mm2 <= 0.0 for surface in result.surfaces):
        raise RuntimeError("A classified CAD surface has non-positive area.")

    required_counts = {
        HEAD_TOP: definition.minimum_head_top_surface_count,
        UNDER_HEAD_BEARING: (definition.minimum_under_head_surface_count),
        HEAD_SIDES: definition.minimum_head_side_surface_count,
        THREAD_SURFACES: definition.minimum_thread_surface_count,
        BOLT_TIP: definition.minimum_tip_surface_count,
    }

    for region, required_count in required_counts.items():
        actual_count = result.count_for(region)

        if actual_count < required_count:
            raise RuntimeError(
                f"Region {region!r} contains {actual_count} surfaces; "
                f"at least {required_count} are required."
            )

    registered_regions = {group.region for group in result.physical_groups}

    nonempty_regions = {region for region in REGION_ORDER if result.count_for(region) > 0}

    if registered_regions != nonempty_regions:
        raise RuntimeError("Registered physical groups do not match classified regions.")

    for group in result.physical_groups:
        expected_count = result.count_for(group.region)

        if group.entity_count != expected_count:
            raise RuntimeError(
                f"Physical group {group.physical_name!r} contains "
                f"{group.entity_count} entities; expected "
                f"{expected_count}."
            )


def _register_physical_groups(
    surfaces: tuple[ClassifiedSurface, ...],
    definition: SurfaceClassificationDefinition,
) -> tuple[PhysicalGroupRegistration, ...]:
    """Register classified surfaces as Gmsh physical groups."""

    registrations: list[PhysicalGroupRegistration] = []

    for region in REGION_ORDER:
        tags = [surface.tag for surface in surfaces if surface.region == region]

        if not tags:
            continue

        physical_tag = gmsh.model.addPhysicalGroup(
            2,
            tags,
        )

        physical_name = definition.physical_name(region)

        gmsh.model.setPhysicalName(
            2,
            physical_tag,
            physical_name,
        )

        registered_tags = gmsh.model.getEntitiesForPhysicalGroup(
            2,
            physical_tag,
        )

        registrations.append(
            PhysicalGroupRegistration(
                region=region,
                physical_name=physical_name,
                physical_tag=int(physical_tag),
                entity_count=len(registered_tags),
            )
        )

    return tuple(registrations)


def classify_step_surfaces(
    step_path: Path,
    blank_definition: BoltBlankDefinition,
    definition: SurfaceClassificationDefinition,
) -> SurfaceClassificationResult:
    """Import a STEP bolt and classify all of its surfaces."""

    if not step_path.exists():
        raise FileNotFoundError(f"STEP geometry does not exist: {step_path}")

    if step_path.stat().st_size <= 0:
        raise RuntimeError(f"STEP geometry is empty: {step_path}")

    initialized = False

    try:
        gmsh.initialize()
        initialized = True

        gmsh.option.setNumber(
            "General.Terminal",
            0,
        )

        gmsh.model.add(f"{definition.mesh_id}-surface-classification")

        gmsh.model.occ.importShapes(
            str(step_path),
            True,
        )

        gmsh.model.occ.synchronize()

        volume_entities = gmsh.model.getEntities(3)

        surfaces = _measure_and_classify_surfaces(
            blank_definition,
            definition,
        )

        physical_groups = _register_physical_groups(
            surfaces,
            definition,
        )

        result = SurfaceClassificationResult(
            imported_volume_count=len(volume_entities),
            surfaces=surfaces,
            physical_groups=physical_groups,
        )

        validate_surface_classification(
            result,
            definition,
        )

        return result

    finally:
        if initialized:
            gmsh.finalize()
