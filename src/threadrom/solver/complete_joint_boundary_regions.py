"""Governed mesh-derived boundary regions for the complete joint."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import numpy as np
from numpy.typing import NDArray

from threadrom.solver.complete_joint_calculix_transfer import (
    CompleteJointCalculixMeshData,
    CompleteJointCalculixTransferDefinition,
)
from threadrom.solver.complete_joint_contact import (
    CompleteJointContactDefinition,
)

HEAD_SUPPORT = "head_support"
NUT_LOAD = "nut_load"

BOUNDARY_REGION_ORDER = (
    HEAD_SUPPORT,
    NUT_LOAD,
)


@dataclass(frozen=True)
class BoundaryRegionDefinition:
    """One governed mesh-derived boundary region."""

    key: str
    name: str
    source_boundary: str
    excluded_boundary: str


@dataclass(frozen=True)
class CompleteJointBoundaryRegionDefinition:
    """Governed complete-joint boundary-region settings."""

    boundary_region_id: str
    simulation_id: str
    mesh_id: str
    assembly_id: str
    contact_model_id: str
    status: str
    outer_band_inner_radius_mm: float | None
    member_outer_radius_mm: float
    coordinate_tolerance_mm: float
    regions: tuple[BoundaryRegionDefinition, ...]
    expected_region_count: int
    expected_head_support_node_count: int | None
    expected_nut_load_node_count: int | None
    require_zero_bearing_overlap: bool
    require_equal_region_node_counts: bool
    outer_band_free_annulus_fraction: float | None = None

    def region(
        self,
        key: str,
    ) -> BoundaryRegionDefinition:
        """Return one governed boundary-region definition."""

        for region in self.regions:
            if region.key == key:
                return region

        raise ValueError(
            f"Unknown complete-joint boundary region: {key}"
        )


@dataclass(frozen=True)
class DerivedBoundaryRegion:
    """One node set derived from an existing mesh boundary."""

    key: str
    name: str
    source_boundary: str
    excluded_boundary: str
    node_ids: tuple[int, ...]

    @property
    def node_count(self) -> int:
        """Return the number of nodes in the region."""

        return len(self.node_ids)


@dataclass(frozen=True)
class CompleteJointBoundaryRegionResult:
    """Verified complete-joint boundary-region result."""

    regions: tuple[DerivedBoundaryRegion, ...]

    def region(
        self,
        key: str,
    ) -> DerivedBoundaryRegion:
        """Return one derived boundary region."""

        for region in self.regions:
            if region.key == key:
                return region

        raise ValueError(
            f"Unknown derived complete-joint region: {key}"
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
    """Return one required numerical value."""

    value = data.get(key)

    if (
        isinstance(value, bool)
        or not isinstance(value, int | float)
    ):
        raise TypeError(
            f"Missing or invalid numerical value: {key}"
        )

    return float(value)


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


def _boolean(
    data: Mapping[str, object],
    key: str,
) -> bool:
    """Return one required Boolean value."""

    value = data.get(key)

    if not isinstance(value, bool):
        raise TypeError(
            f"Missing or invalid Boolean value: {key}"
        )

    return value


def load_complete_joint_boundary_region_definition(
    config_path: Path,
) -> CompleteJointBoundaryRegionDefinition:
    """Load and validate governed boundary-region settings."""

    with config_path.open("rb") as config_file:
        data: dict[str, object] = tomllib.load(config_file)

    identity = _section(data, "identity")
    geometry = _section(data, "geometry")
    region_sections = _section(data, "regions")
    verification = _section(data, "verification")

    regions: list[BoundaryRegionDefinition] = []

    for region_key in BOUNDARY_REGION_ORDER:
        region_section = _section(
            region_sections,
            region_key,
        )

        regions.append(
            BoundaryRegionDefinition(
                key=region_key,
                name=_string(region_section, "name"),
                source_boundary=_string(
                    region_section,
                    "source_boundary",
                ),
                excluded_boundary=_string(
                    region_section,
                    "excluded_boundary",
                ),
            )
        )

    definition = CompleteJointBoundaryRegionDefinition(
        boundary_region_id=_string(
            identity,
            "boundary_region_id",
        ),
        simulation_id=_string(
            identity,
            "simulation_id",
        ),
        mesh_id=_string(identity, "mesh_id"),
        assembly_id=_string(identity, "assembly_id"),
        contact_model_id=_string(
            identity,
            "contact_model_id",
        ),
        status=_string(identity, "status"),
        outer_band_inner_radius_mm=_number(
            geometry,
            "outer_band_inner_radius_mm",
        ),
        member_outer_radius_mm=_number(
            geometry,
            "member_outer_radius_mm",
        ),
        coordinate_tolerance_mm=_number(
            geometry,
            "coordinate_tolerance_mm",
        ),
        regions=tuple(regions),
        expected_region_count=_integer(
            verification,
            "expected_region_count",
        ),
        expected_head_support_node_count=_integer(
            verification,
            "expected_head_support_node_count",
        ),
        expected_nut_load_node_count=_integer(
            verification,
            "expected_nut_load_node_count",
        ),
        require_zero_bearing_overlap=_boolean(
            verification,
            "require_zero_bearing_overlap",
        ),
        require_equal_region_node_counts=_boolean(
            verification,
            "require_equal_region_node_counts",
        ),
    )

    if definition.outer_band_inner_radius_mm is not None:
        if definition.outer_band_inner_radius_mm <= 0.0:
            raise ValueError(
                "Outer-band inner radius must be positive."
            )

        if (
            definition.member_outer_radius_mm
            <= definition.outer_band_inner_radius_mm
        ):
            raise ValueError(
                "Member outer radius must exceed the "
                "outer-band inner radius."
            )

    if definition.coordinate_tolerance_mm <= 0.0:
        raise ValueError(
            "Coordinate tolerance must be positive."
        )

    if (
        len(definition.regions)
        != definition.expected_region_count
    ):
        raise ValueError(
            "Boundary-region count does not match the "
            "governed expectation."
        )

    region_names = tuple(
        region.name
        for region in definition.regions
    )

    if len(set(region_names)) != len(region_names):
        raise ValueError(
            "Derived boundary-region names must be unique."
        )

    return definition


def _resolve_boundary_name(
    available_names: tuple[str, ...],
    requested_name: str,
) -> str:
    """Resolve a boundary name case-insensitively."""

    matches = tuple(
        available_name
        for available_name in available_names
        if (
            available_name.casefold()
            == requested_name.casefold()
        )
    )

    if len(matches) != 1:
        raise KeyError(
            f"Could not uniquely resolve boundary "
            f"{requested_name!r}; matches={matches}."
        )

    return matches[0]


def validate_boundary_region_identities(
    definition: CompleteJointBoundaryRegionDefinition,
    transfer: CompleteJointCalculixTransferDefinition,
    contact: CompleteJointContactDefinition,
) -> None:
    """Verify identity consistency across governed models."""

    identity_checks = (
        (
            "mesh",
            definition.mesh_id,
            transfer.mesh_id,
        ),
        (
            "assembly",
            definition.assembly_id,
            transfer.assembly_id,
        ),
        (
            "contact mesh",
            definition.mesh_id,
            contact.mesh_id,
        ),
        (
            "contact assembly",
            definition.assembly_id,
            contact.assembly_id,
        ),
        (
            "contact model",
            definition.contact_model_id,
            contact.contact_model_id,
        ),
    )

    for label, boundary_value, model_value in identity_checks:
        if boundary_value != model_value:
            raise ValueError(
                f"Boundary-region and {label} identities differ."
            )


def derive_complete_joint_boundary_regions(
    mesh_data: CompleteJointCalculixMeshData,
    definition: CompleteJointBoundaryRegionDefinition,
    transfer: CompleteJointCalculixTransferDefinition,
    contact: CompleteJointContactDefinition,
) -> CompleteJointBoundaryRegionResult:
    """Derive and verify the two outer annular node sets."""

    validate_boundary_region_identities(
        definition,
        transfer,
        contact,
    )

    available_names = tuple(
        mesh_data.boundary_node_sets
    )

    derived_regions: list[DerivedBoundaryRegion] = []

    for region_definition in definition.regions:
        source_name = _resolve_boundary_name(
            available_names,
            region_definition.source_boundary,
        )

        excluded_name = _resolve_boundary_name(
            available_names,
            region_definition.excluded_boundary,
        )

        source_node_ids = np.asarray(
            mesh_data.boundary_node_sets[source_name],
            dtype=np.int64,
        )

        excluded_node_ids = np.asarray(
            mesh_data.boundary_node_sets[excluded_name],
            dtype=np.int64,
        )

        source_coordinates = mesh_data.points_mm[
            source_node_ids - 1
        ]

        source_radii = np.hypot(
            source_coordinates[:, 0],
            source_coordinates[:, 1],
        )

        maximum_source_radius = float(
            np.max(source_radii)
        )

        if (
            abs(
                maximum_source_radius
                - definition.member_outer_radius_mm
            )
            > definition.coordinate_tolerance_mm
        ):
            raise RuntimeError(
                f"{region_definition.key}: source boundary "
                "has an unexpected outer radius."
            )

        if (
            definition.outer_band_free_annulus_fraction
            is None
        ):
            if definition.outer_band_inner_radius_mm is None:
                raise ValueError(
                    "Legacy boundary-band mode requires an "
                    "absolute inner radius."
                )

            inner_radius_mm = (
                definition.outer_band_inner_radius_mm
            )
        else:
            fraction = (
                definition.outer_band_free_annulus_fraction
            )

            if not 0.0 < fraction < 1.0:
                raise ValueError(
                    "Outer-band free-annulus fraction "
                    "must lie in (0, 1)."
                )

            excluded_coordinates = mesh_data.points_mm[
                excluded_node_ids - 1
            ]

            excluded_radii = np.hypot(
                excluded_coordinates[:, 0],
                excluded_coordinates[:, 1],
            )

            excluded_outer_radius_mm = float(
                np.max(excluded_radii)
            )

            if (
                excluded_outer_radius_mm
                >= definition.member_outer_radius_mm
            ):
                raise RuntimeError(
                    f"{region_definition.key}: excluded boundary "
                    "reaches or exceeds the member outer radius."
                )

            free_annulus_width_mm = (
                definition.member_outer_radius_mm
                - excluded_outer_radius_mm
            )

            inner_radius_mm = (
                excluded_outer_radius_mm
                + fraction * free_annulus_width_mm
            )

        selection_mask: NDArray[np.bool_] = (
            source_radii
            >= (
                inner_radius_mm
                - definition.coordinate_tolerance_mm
            )
        )

        selected_node_ids = tuple(
            int(node_id)
            for node_id in source_node_ids[selection_mask]
        )

        if not selected_node_ids:
            raise RuntimeError(
                f"{region_definition.key}: derived region "
                "contains no nodes."
            )

        overlap = np.intersect1d(
            np.asarray(
                selected_node_ids,
                dtype=np.int64,
            ),
            excluded_node_ids,
        )

        if (
            definition.require_zero_bearing_overlap
            and len(overlap) != 0
        ):
            raise RuntimeError(
                f"{region_definition.key}: derived region "
                "overlaps the excluded bearing boundary."
            )

        derived_regions.append(
            DerivedBoundaryRegion(
                key=region_definition.key,
                name=region_definition.name,
                source_boundary=source_name,
                excluded_boundary=excluded_name,
                node_ids=selected_node_ids,
            )
        )

    result = CompleteJointBoundaryRegionResult(
        regions=tuple(derived_regions),
    )

    head_support = result.region(HEAD_SUPPORT)
    nut_load = result.region(NUT_LOAD)

    if (
        definition.expected_head_support_node_count
        is not None
        and head_support.node_count
        != definition.expected_head_support_node_count
    ):
        raise RuntimeError(
            "Head-support node count does not match the "
            "governed expectation."
        )

    if (
        definition.expected_nut_load_node_count
        is not None
        and nut_load.node_count
        != definition.expected_nut_load_node_count
    ):
        raise RuntimeError(
            "Nut-load node count does not match the "
            "governed expectation."
        )

    if (
        definition.require_equal_region_node_counts
        and head_support.node_count != nut_load.node_count
    ):
        raise RuntimeError(
            "Head-support and nut-load regions must "
            "contain equal node counts."
        )

    return result



def _format_node_identifier_rows(
    node_ids: tuple[int, ...],
    identifiers_per_row: int = 16,
) -> tuple[str, ...]:
    """Format CalculiX node identifiers into deterministic rows."""

    if identifiers_per_row <= 0:
        raise ValueError(
            "Identifiers per row must be positive."
        )

    return tuple(
        ", ".join(
            str(node_id)
            for node_id in node_ids[
                start_index : (
                    start_index + identifiers_per_row
                )
            ]
        )
        for start_index in range(
            0,
            len(node_ids),
            identifiers_per_row,
        )
    )


def render_complete_joint_boundary_region_nsets(
    result: CompleteJointBoundaryRegionResult,
) -> tuple[str, ...]:
    """Render the derived boundary regions as CalculiX NSET cards."""

    lines: list[str] = []

    for region in result.regions:
        if not region.node_ids:
            raise RuntimeError(
                f"Boundary region {region.name} is empty."
            )

        if len(set(region.node_ids)) != len(region.node_ids):
            raise RuntimeError(
                f"Boundary region {region.name} contains "
                "duplicate node identifiers."
            )

        sorted_node_ids = tuple(
            sorted(region.node_ids)
        )

        lines.extend(
            (
                f"** Derived boundary region: {region.key}",
                f"*NSET, NSET={region.name}",
                *_format_node_identifier_rows(
                    sorted_node_ids
                ),
            )
        )

    return tuple(lines)
