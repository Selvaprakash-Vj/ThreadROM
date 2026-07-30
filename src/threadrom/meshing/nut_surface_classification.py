"""Geometry-driven classification of nut CAD surfaces."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import gmsh  # type: ignore[import-untyped]

from threadrom.geometry.nut_blank import NutBlankDefinition

LOWER_BEARING = "lower_bearing"
UPPER_BEARING = "upper_bearing"
OUTER_HEX = "outer_hex"
INTERNAL_THREAD = "internal_thread"
TRANSITION_SURFACES = "transition_surfaces"

REGION_ORDER = (
    LOWER_BEARING,
    UPPER_BEARING,
    OUTER_HEX,
    INTERNAL_THREAD,
    TRANSITION_SURFACES,
)


@dataclass(frozen=True)
class NutSurfaceClassificationDefinition:
    """Controlled rules and names for nut-surface classification."""

    mesh_id: str
    geometry_id: str
    plane_tolerance_mm: float
    radial_tolerance_mm: float
    lower_bearing_name: str
    upper_bearing_name: str
    outer_hex_name: str
    internal_thread_name: str
    transition_surfaces_name: str
    minimum_lower_bearing_surface_count: int
    minimum_upper_bearing_surface_count: int
    minimum_outer_hex_surface_count: int
    minimum_internal_thread_surface_count: int

    def physical_name(self, region: str) -> str:
        """Return the configured physical name for one region."""

        names = {
            LOWER_BEARING: self.lower_bearing_name,
            UPPER_BEARING: self.upper_bearing_name,
            OUTER_HEX: self.outer_hex_name,
            INTERNAL_THREAD: self.internal_thread_name,
            TRANSITION_SURFACES: self.transition_surfaces_name,
        }

        try:
            return names[region]
        except KeyError as error:
            raise ValueError(
                f"Unknown nut-surface region: {region}"
            ) from error


@dataclass(frozen=True)
class ClassifiedNutSurface:
    """Measured CAD surface and its assigned nut region."""

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
    sampled_radial_min_mm: float
    sampled_radial_max_mm: float

    @property
    def radial_envelope_mm(self) -> float:
        """Return the largest absolute X or Y bound."""

        return max(
            abs(self.x_min_mm),
            abs(self.x_max_mm),
            abs(self.y_min_mm),
            abs(self.y_max_mm),
        )


@dataclass(frozen=True)
class NutPhysicalGroupRegistration:
    """Registered Gmsh physical group for the nut."""

    region: str
    physical_name: str
    physical_tag: int
    entity_count: int


@dataclass(frozen=True)
class NutSurfaceClassificationResult:
    """Complete classified nut-surface topology."""

    imported_volume_count: int
    surfaces: tuple[ClassifiedNutSurface, ...]
    physical_groups: tuple[
        NutPhysicalGroupRegistration,
        ...,
    ]

    @property
    def surface_count(self) -> int:
        """Return the number of classified surfaces."""

        return len(self.surfaces)

    def tags_for(self, region: str) -> tuple[int, ...]:
        """Return all surface tags assigned to a region."""

        return tuple(
            surface.tag
            for surface in self.surfaces
            if surface.region == region
        )

    def count_for(self, region: str) -> int:
        """Return the surface count for one region."""

        return len(self.tags_for(region))


def _section(
    data: Mapping[str, object],
    key: str,
) -> Mapping[str, object]:
    """Return a required TOML section."""

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
    """Return a required non-empty string."""

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
    """Return a required numerical value."""

    value = data.get(key)

    if isinstance(value, bool) or not isinstance(
        value,
        int | float,
    ):
        raise TypeError(
            f"Missing or invalid numerical value: {key}"
        )

    return float(value)


def _integer(
    data: Mapping[str, object],
    key: str,
) -> int:
    """Return a required integer value."""

    value = data.get(key)

    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(
            f"Missing or invalid integer value: {key}"
        )

    return value


def load_nut_surface_classification_definition(
    config_path: Path,
) -> NutSurfaceClassificationDefinition:
    """Load and validate the nut classification policy."""

    with config_path.open("rb") as config_file:
        data: dict[str, object] = tomllib.load(config_file)

    identity = _section(data, "identity")
    classification = _section(data, "classification")
    physical_groups = _section(data, "physical_groups")
    verification = _section(data, "verification")

    definition = NutSurfaceClassificationDefinition(
        mesh_id=_string(identity, "mesh_id"),
        geometry_id=_string(identity, "geometry_id"),
        plane_tolerance_mm=_number(
            classification,
            "plane_tolerance_mm",
        ),
        radial_tolerance_mm=_number(
            classification,
            "radial_tolerance_mm",
        ),
        lower_bearing_name=_string(
            physical_groups,
            "lower_bearing",
        ),
        upper_bearing_name=_string(
            physical_groups,
            "upper_bearing",
        ),
        outer_hex_name=_string(
            physical_groups,
            "outer_hex",
        ),
        internal_thread_name=_string(
            physical_groups,
            "internal_thread",
        ),
        transition_surfaces_name=_string(
            physical_groups,
            "transition_surfaces",
        ),
        minimum_lower_bearing_surface_count=_integer(
            verification,
            "minimum_lower_bearing_surface_count",
        ),
        minimum_upper_bearing_surface_count=_integer(
            verification,
            "minimum_upper_bearing_surface_count",
        ),
        minimum_outer_hex_surface_count=_integer(
            verification,
            "minimum_outer_hex_surface_count",
        ),
        minimum_internal_thread_surface_count=_integer(
            verification,
            "minimum_internal_thread_surface_count",
        ),
    )

    if definition.plane_tolerance_mm <= 0.0:
        raise ValueError(
            "Nut plane tolerance must be positive."
        )

    if definition.radial_tolerance_mm <= 0.0:
        raise ValueError(
            "Nut radial tolerance must be positive."
        )

    minimum_counts = (
        definition.minimum_lower_bearing_surface_count,
        definition.minimum_upper_bearing_surface_count,
        definition.minimum_outer_hex_surface_count,
        definition.minimum_internal_thread_surface_count,
    )

    if any(count <= 0 for count in minimum_counts):
        raise ValueError(
            "Required nut-surface counts must be positive."
        )

    return definition


def _lies_on_z_plane(
    z_min_mm: float,
    z_max_mm: float,
    plane_z_mm: float,
    tolerance_mm: float,
) -> bool:
    """Return whether a surface lies on one axial plane."""

    return (
        abs(z_min_mm - plane_z_mm) <= tolerance_mm
        and abs(z_max_mm - plane_z_mm) <= tolerance_mm
    )


def classify_nut_surface_region(
    *,
    x_min_mm: float,
    x_max_mm: float,
    y_min_mm: float,
    y_max_mm: float,
    z_min_mm: float,
    z_max_mm: float,
    sampled_radial_max_mm: float | None = None,
    nut_definition: NutBlankDefinition,
    definition: NutSurfaceClassificationDefinition,
) -> str:
    """Classify one nut surface from axial and radial bounds."""

    plane_tolerance = definition.plane_tolerance_mm

    if _lies_on_z_plane(
        z_min_mm,
        z_max_mm,
        0.0,
        plane_tolerance,
    ):
        return LOWER_BEARING

    if _lies_on_z_plane(
        z_min_mm,
        z_max_mm,
        nut_definition.thickness_mm,
        plane_tolerance,
    ):
        return UPPER_BEARING

    bounding_radial_envelope = max(
        abs(x_min_mm),
        abs(x_max_mm),
        abs(y_min_mm),
        abs(y_max_mm),
    )

    radial_envelope = (
        sampled_radial_max_mm
        if sampled_radial_max_mm is not None
        else bounding_radial_envelope
    )

    internal_limit = (
        nut_definition.nominal_diameter_mm / 2.0
        + definition.radial_tolerance_mm
    )

    within_nut_height = (
        z_min_mm >= -plane_tolerance
        and z_max_mm
        <= nut_definition.thickness_mm + plane_tolerance
    )

    if radial_envelope <= internal_limit:
        return INTERNAL_THREAD

    if within_nut_height:
        return OUTER_HEX

    return TRANSITION_SURFACES


def _sample_surface_radial_bounds(
    tag: int,
) -> tuple[float, float]:
    """Sample interior surface points and return radial bounds."""

    parameter_minimum, parameter_maximum = (
        gmsh.model.getParametrizationBounds(
            2,
            tag,
        )
    )

    fractions = (
        0.05,
        0.20,
        0.35,
        0.50,
        0.65,
        0.80,
        0.95,
    )

    u_minimum = float(parameter_minimum[0])
    u_maximum = float(parameter_maximum[0])
    v_minimum = float(parameter_minimum[1])
    v_maximum = float(parameter_maximum[1])

    parameters: list[float] = []

    for u_fraction in fractions:
        u_value = (
            u_minimum
            + u_fraction * (u_maximum - u_minimum)
        )

        for v_fraction in fractions:
            v_value = (
                v_minimum
                + v_fraction * (v_maximum - v_minimum)
            )

            parameters.extend(
                (
                    u_value,
                    v_value,
                )
            )

    coordinates = gmsh.model.getValue(
        2,
        tag,
        parameters,
    )

    radii = tuple(
        (
            coordinates[index] ** 2
            + coordinates[index + 1] ** 2
        )
        ** 0.5
        for index in range(
            0,
            len(coordinates),
            3,
        )
    )

    if not radii:
        raise RuntimeError(
            f"No radial samples were obtained for surface {tag}."
        )

    return min(radii), max(radii)


def _measure_and_classify_nut_surfaces(
    nut_definition: NutBlankDefinition,
    definition: NutSurfaceClassificationDefinition,
) -> tuple[ClassifiedNutSurface, ...]:
    """Measure and classify all active Gmsh surfaces."""

    surfaces: list[ClassifiedNutSurface] = []

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
        ) = gmsh.model.getBoundingBox(2, tag)

        area_mm2 = gmsh.model.occ.getMass(2, tag)

        (
            center_x_mm,
            center_y_mm,
            center_z_mm,
        ) = gmsh.model.occ.getCenterOfMass(2, tag)

        (
            sampled_radial_min_mm,
            sampled_radial_max_mm,
        ) = _sample_surface_radial_bounds(
            int(tag)
        )

        region = classify_nut_surface_region(
            x_min_mm=float(x_min_mm),
            x_max_mm=float(x_max_mm),
            y_min_mm=float(y_min_mm),
            y_max_mm=float(y_max_mm),
            z_min_mm=float(z_min_mm),
            z_max_mm=float(z_max_mm),
            sampled_radial_max_mm=(
                sampled_radial_max_mm
            ),
            nut_definition=nut_definition,
            definition=definition,
        )

        surfaces.append(
            ClassifiedNutSurface(
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
                sampled_radial_min_mm=(
                    sampled_radial_min_mm
                ),
                sampled_radial_max_mm=(
                    sampled_radial_max_mm
                ),
            )
        )

    return tuple(
        sorted(
            surfaces,
            key=lambda surface: surface.tag,
        )
    )


def _register_nut_physical_groups(
    surfaces: tuple[ClassifiedNutSurface, ...],
    definition: NutSurfaceClassificationDefinition,
) -> tuple[NutPhysicalGroupRegistration, ...]:
    """Register classified surfaces as physical groups."""

    registrations: list[
        NutPhysicalGroupRegistration
    ] = []

    for region in REGION_ORDER:
        tags = [
            surface.tag
            for surface in surfaces
            if surface.region == region
        ]

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

        registered_tags = (
            gmsh.model.getEntitiesForPhysicalGroup(
                2,
                physical_tag,
            )
        )

        registrations.append(
            NutPhysicalGroupRegistration(
                region=region,
                physical_name=physical_name,
                physical_tag=int(physical_tag),
                entity_count=len(registered_tags),
            )
        )

    return tuple(registrations)


def validate_nut_surface_classification(
    result: NutSurfaceClassificationResult,
    definition: NutSurfaceClassificationDefinition,
) -> None:
    """Apply controlled nut-topology acceptance gates."""

    if result.imported_volume_count != 1:
        raise RuntimeError(
            "Nut classification requires exactly one CAD volume."
        )

    if result.surface_count <= 0:
        raise RuntimeError(
            "No nut CAD surfaces were available."
        )

    tags = tuple(
        surface.tag
        for surface in result.surfaces
    )

    if len(tags) != len(set(tags)):
        raise RuntimeError(
            "A nut CAD surface was classified more than once."
        )

    if any(
        surface.area_mm2 <= 0.0
        for surface in result.surfaces
    ):
        raise RuntimeError(
            "A classified nut surface has non-positive area."
        )

    required_counts = {
        LOWER_BEARING: (
            definition.minimum_lower_bearing_surface_count
        ),
        UPPER_BEARING: (
            definition.minimum_upper_bearing_surface_count
        ),
        OUTER_HEX: (
            definition.minimum_outer_hex_surface_count
        ),
        INTERNAL_THREAD: (
            definition.minimum_internal_thread_surface_count
        ),
    }

    for region, required_count in required_counts.items():
        actual_count = result.count_for(region)

        if actual_count < required_count:
            raise RuntimeError(
                f"Nut region {region!r} contains "
                f"{actual_count} surfaces; at least "
                f"{required_count} are required."
            )

    registered_regions = {
        group.region
        for group in result.physical_groups
    }

    nonempty_regions = {
        region
        for region in REGION_ORDER
        if result.count_for(region) > 0
    }

    if registered_regions != nonempty_regions:
        raise RuntimeError(
            "Registered nut groups do not match regions."
        )


def classify_current_model_nut_surfaces(
    nut_definition: NutBlankDefinition,
    definition: NutSurfaceClassificationDefinition,
) -> NutSurfaceClassificationResult:
    """Classify and register surfaces in the active model."""

    volume_entities = gmsh.model.getEntities(3)

    surfaces = _measure_and_classify_nut_surfaces(
        nut_definition,
        definition,
    )

    physical_groups = _register_nut_physical_groups(
        surfaces,
        definition,
    )

    result = NutSurfaceClassificationResult(
        imported_volume_count=len(volume_entities),
        surfaces=surfaces,
        physical_groups=physical_groups,
    )

    validate_nut_surface_classification(
        result,
        definition,
    )

    return result


def classify_step_nut_surfaces(
    step_path: Path,
    nut_definition: NutBlankDefinition,
    definition: NutSurfaceClassificationDefinition,
) -> NutSurfaceClassificationResult:
    """Import a STEP nut and classify its surfaces."""

    if not step_path.exists():
        raise FileNotFoundError(
            f"Nut STEP geometry does not exist: {step_path}"
        )

    if step_path.stat().st_size <= 0:
        raise RuntimeError(
            f"Nut STEP geometry is empty: {step_path}"
        )

    initialized = False

    try:
        gmsh.initialize()
        initialized = True

        gmsh.option.setNumber(
            "General.Terminal",
            0,
        )

        gmsh.model.add(
            f"{definition.mesh_id}-nut-classification"
        )

        gmsh.model.occ.importShapes(
            str(step_path),
            True,
        )
        gmsh.model.occ.synchronize()

        return classify_current_model_nut_surfaces(
            nut_definition,
            definition,
        )

    finally:
        if initialized:
            gmsh.finalize()
