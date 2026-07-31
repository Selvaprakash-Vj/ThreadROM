"""Create a conforming pretension section inside the bolt volume."""

from __future__ import annotations

from dataclasses import dataclass

import gmsh  # type: ignore[import-untyped]


@dataclass(frozen=True)
class CompleteJointPretensionFragmentResult:
    """Verified entities created by the bolt fragmentation."""

    original_bolt_tag: int
    lower_fragment_tag: int
    upper_fragment_tag: int
    section_surface_tag: int
    section_area_mm2: float
    section_center_z_mm: float

    @property
    def fragment_tags(self) -> tuple[int, int]:
        """Return both bolt fragments in axial order."""

        return (
            self.lower_fragment_tag,
            self.upper_fragment_tag,
        )


def _volume_surface_tags(
    volume_tag: int,
) -> set[int]:
    """Return direct surfaces bounding one volume."""

    return {
        int(tag)
        for dimension, tag in gmsh.model.getBoundary(
            [(3, volume_tag)],
            combined=False,
            oriented=False,
            recursive=False,
        )
        if dimension == 2
    }


def fragment_bolt_for_pretension(
    *,
    bolt_tag: int,
    axial_position_mm: float,
    expected_fragment_count: int = 2,
    cutter_margin_mm: float = 1.0,
    plane_tolerance_mm: float = 1.0e-4,
) -> CompleteJointPretensionFragmentResult:
    """Split one bolt volume with a conforming transverse surface."""

    if bolt_tag <= 0:
        raise ValueError("Bolt tag must be positive.")

    if expected_fragment_count != 2:
        raise ValueError(
            "The baseline pretension model requires two fragments."
        )

    if cutter_margin_mm <= 0.0:
        raise ValueError("Cutter margin must be positive.")

    if plane_tolerance_mm <= 0.0:
        raise ValueError("Plane tolerance must be positive.")

    (
        x_min,
        y_min,
        z_min,
        x_max,
        y_max,
        z_max,
    ) = gmsh.model.getBoundingBox(3, bolt_tag)

    if not (
        z_min + plane_tolerance_mm
        < axial_position_mm
        < z_max - plane_tolerance_mm
    ):
        raise ValueError(
            "Pretension section must lie inside the bolt volume."
        )

    cutter_tag = gmsh.model.occ.addRectangle(
        x_min - cutter_margin_mm,
        y_min - cutter_margin_mm,
        axial_position_mm,
        (x_max - x_min) + 2.0 * cutter_margin_mm,
        (y_max - y_min) + 2.0 * cutter_margin_mm,
    )

    _, mapping = gmsh.model.occ.fragment(
        [(3, bolt_tag)],
        [(2, cutter_tag)],
    )

    gmsh.model.occ.synchronize()

    if not mapping:
        raise RuntimeError(
            "Gmsh returned no fragment mapping for the bolt."
        )

    fragment_tags = tuple(
        sorted(
            int(tag)
            for dimension, tag in mapping[0]
            if dimension == 3
        )
    )

    if len(fragment_tags) != expected_fragment_count:
        raise RuntimeError(
            "Unexpected bolt-fragment count: "
            f"{len(fragment_tags)}."
        )

    first_surfaces = _volume_surface_tags(fragment_tags[0])
    second_surfaces = _volume_surface_tags(fragment_tags[1])

    shared_surfaces = tuple(
        sorted(first_surfaces & second_surfaces)
    )

    if len(shared_surfaces) != 1:
        raise RuntimeError(
            "Expected one shared pretension interface; found "
            f"{len(shared_surfaces)}."
        )

    section_surface_tag = shared_surfaces[0]

    section_bounds = gmsh.model.getBoundingBox(
        2,
        section_surface_tag,
    )

    if (
        abs(section_bounds[2] - axial_position_mm)
        > plane_tolerance_mm
        or abs(section_bounds[5] - axial_position_mm)
        > plane_tolerance_mm
    ):
        raise RuntimeError(
            "Shared pretension interface is not planar at the "
            "governed axial position."
        )

    section_center = gmsh.model.occ.getCenterOfMass(
        2,
        section_surface_tag,
    )

    section_area_mm2 = float(
        gmsh.model.occ.getMass(
            2,
            section_surface_tag,
        )
    )

    if section_area_mm2 <= 0.0:
        raise RuntimeError(
            "Pretension interface has non-positive area."
        )

    adjacent_volumes, _ = gmsh.model.getAdjacencies(
        2,
        section_surface_tag,
    )

    if {
        int(tag)
        for tag in adjacent_volumes
    } != set(fragment_tags):
        raise RuntimeError(
            "Pretension interface is not shared by both fragments."
        )

    ordered_fragments = tuple(
        sorted(
            fragment_tags,
            key=lambda tag: float(
                gmsh.model.occ.getCenterOfMass(3, tag)[2]
            ),
        )
    )

    return CompleteJointPretensionFragmentResult(
        original_bolt_tag=bolt_tag,
        lower_fragment_tag=ordered_fragments[0],
        upper_fragment_tag=ordered_fragments[1],
        section_surface_tag=section_surface_tag,
        section_area_mm2=section_area_mm2,
        section_center_z_mm=float(section_center[2]),
    )
