"""Classification of the fragmented pretension-capable joint."""

from __future__ import annotations

from dataclasses import dataclass

from threadrom.engineering.baseline_assembly import (
    BaselineAssembly,
)
from threadrom.geometry.bolt_blank import BoltBlankDefinition
from threadrom.geometry.nut_blank import NutBlankDefinition
from threadrom.meshing.complete_joint_pretension_fragment import (
    CompleteJointPretensionFragmentResult,
)
from threadrom.meshing.complete_joint_surface_classification import (
    HEAD_SIDE_MEMBER,
    MEMBER_REGION_ORDER,
    NUT_SIDE_MEMBER,
    ClassifiedMemberSurface,
    CompleteJointSurfaceClassificationDefinition,
    JointPhysicalGroupRegistration,
    _classify_member_surface,
    _register_group,
    _surface_tags_for_volume,
)
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
from threadrom.solver.complete_joint_pretension import (
    CompleteJointPretensionDefinition,
)


@dataclass(frozen=True)
class PretensionJointVolumeIdentification:
    """Five CAD volumes grouped into four physical components."""

    bolt_fragment_tags: tuple[int, int]
    nut_tag: int
    head_side_member_tag: int
    nut_side_member_tag: int

    @property
    def total_volume_count(self) -> int:
        """Return the total fragmented CAD-volume count."""

        return len(self.bolt_fragment_tags) + 3


@dataclass(frozen=True)
class CompleteJointPretensionClassificationResult:
    """Verified classification of the fragmented joint."""

    volumes: PretensionJointVolumeIdentification
    bolt: SurfaceClassificationResult
    nut: NutSurfaceClassificationResult
    member_surfaces: tuple[ClassifiedMemberSurface, ...]
    section_surface_tag: int
    physical_groups: tuple[
        JointPhysicalGroupRegistration,
        ...,
    ]

    def member_count_for(
        self,
        region: str,
    ) -> int:
        """Return the classified member-surface count."""

        return sum(
            surface.region == region
            for surface in self.member_surfaces
        )


def classify_fragmented_complete_joint(
    *,
    assembly: BaselineAssembly,
    bolt_blank: BoltBlankDefinition,
    nut_blank: NutBlankDefinition,
    fragment: CompleteJointPretensionFragmentResult,
    nut_tag: int,
    head_side_member_tag: int,
    nut_side_member_tag: int,
    bolt_definition: SurfaceClassificationDefinition,
    nut_definition: NutSurfaceClassificationDefinition,
    joint_definition: CompleteJointSurfaceClassificationDefinition,
    pretension_definition: CompleteJointPretensionDefinition,
) -> CompleteJointPretensionClassificationResult:
    """Classify and register the five-volume pretension model."""

    if joint_definition.assembly_id != assembly.assembly_id:
        raise ValueError(
            "Joint classification and assembly IDs differ."
        )

    if pretension_definition.assembly_id != assembly.assembly_id:
        raise ValueError(
            "Pretension and assembly IDs differ."
        )

    if (
        pretension_definition.geometry_id
        != joint_definition.geometry_id
    ):
        raise ValueError(
            "Pretension and classification geometry IDs differ."
        )

    bolt_fragment_tags = fragment.fragment_tags

    if (
        len(bolt_fragment_tags)
        != pretension_definition.bolt_fragment_count
    ):
        raise RuntimeError(
            "Fragmented bolt count differs from configuration."
        )

    external_bolt_surfaces = (
        set(
            _surface_tags_for_volume(
                bolt_fragment_tags[0]
            )
        )
        | set(
            _surface_tags_for_volume(
                bolt_fragment_tags[1]
            )
        )
    )

    external_bolt_surfaces.discard(
        fragment.section_surface_tag
    )

    if not external_bolt_surfaces:
        raise RuntimeError(
            "No external bolt surfaces remain after fragmentation."
        )

    registrations: list[
        JointPhysicalGroupRegistration
    ] = []

    registrations.append(
        _register_group(
            dimension=3,
            tags=list(bolt_fragment_tags),
            physical_name=(
                pretension_definition.physical_bolt_group_name
            ),
        )
    )

    registrations.append(
        _register_group(
            dimension=3,
            tags=[nut_tag],
            physical_name=joint_definition.volume_name(
                "nut"
            ),
        )
    )

    registrations.append(
        _register_group(
            dimension=3,
            tags=[head_side_member_tag],
            physical_name=joint_definition.volume_name(
                HEAD_SIDE_MEMBER
            ),
        )
    )

    registrations.append(
        _register_group(
            dimension=3,
            tags=[nut_side_member_tag],
            physical_name=joint_definition.volume_name(
                NUT_SIDE_MEMBER
            ),
        )
    )

    registrations.append(
        _register_group(
            dimension=2,
            tags=[fragment.section_surface_tag],
            physical_name=pretension_definition.section_name,
        )
    )

    bolt_result = classify_selected_model_surfaces(
        external_bolt_surfaces,
        bolt_blank,
        bolt_definition,
    )

    nut_result = classify_selected_model_nut_surfaces(
        _surface_tags_for_volume(nut_tag),
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
            head_side_member_tag,
        ),
        (
            NUT_SIDE_MEMBER,
            nut_side_member_tag,
        ),
    ):
        for surface_tag in _surface_tags_for_volume(
            volume_tag
        ):
            member_surfaces.append(
                _classify_member_surface(
                    tag=surface_tag,
                    component=component,
                    assembly=assembly,
                    definition=joint_definition,
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
                    joint_definition.member_surface_name(
                        region
                    )
                ),
            )
        )

    result = CompleteJointPretensionClassificationResult(
        volumes=PretensionJointVolumeIdentification(
            bolt_fragment_tags=bolt_fragment_tags,
            nut_tag=nut_tag,
            head_side_member_tag=head_side_member_tag,
            nut_side_member_tag=nut_side_member_tag,
        ),
        bolt=bolt_result,
        nut=nut_result,
        member_surfaces=ordered_member_surfaces,
        section_surface_tag=fragment.section_surface_tag,
        physical_groups=tuple(registrations),
    )

    if (
        result.volumes.total_volume_count
        != pretension_definition.expected_total_cad_volume_count
    ):
        raise RuntimeError(
            "Pretension classification volume count is invalid."
        )

    if result.section_surface_tag in {
        surface.tag
        for surface in result.bolt.surfaces
    }:
        raise RuntimeError(
            "Pretension section was classified as an external "
            "bolt surface."
        )

    for region in MEMBER_REGION_ORDER:
        if result.member_count_for(region) != 1:
            raise RuntimeError(
                f"Invalid member-surface count: {region}."
            )

    return result
