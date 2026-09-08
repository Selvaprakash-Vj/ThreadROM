"""Governed local-refinement policy for complete-joint FEM meshes."""

from __future__ import annotations

import math
import tomllib

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True, slots=True)
class CompleteJointLocalRefinementPolicy:
    policy_id: str
    policy_name: str
    status: str

    enabled: bool
    base_mesh_level: str
    refinement_kind: str

    bolt_regions: tuple[str, ...]
    nut_regions: tuple[str, ...]
    member_regions: tuple[str, ...]

    local_size_relative_to_global_max: float
    transition_distance_relative_to_global_max: float
    distance_sampling: int

    preserve_base_thread_refinement: bool

    require_all_regions_resolved: bool
    require_local_size_below_global_max: bool
    require_positive_transition_distance: bool
    requires_p04_vv06_sentinel: bool


@dataclass(frozen=True, slots=True)
class ResolvedCompleteJointLocalRefinement:
    policy_id: str
    policy_name: str
    base_mesh_level: str

    local_size_mm: float
    transition_distance_mm: float
    distance_sampling: int

    bolt_regions: tuple[str, ...]
    nut_regions: tuple[str, ...]
    member_regions: tuple[str, ...]


def load_complete_joint_local_refinement_policy(
    path: Path,
) -> CompleteJointLocalRefinementPolicy:
    """Load and validate one governed local-refinement policy."""

    with path.open("rb") as stream:
        data = tomllib.load(stream)

    identity = data["identity"]
    applicability = data["applicability"]
    regions = data["regions"]
    sizing = data["sizing"]
    verification = data["verification"]

    policy = CompleteJointLocalRefinementPolicy(
        policy_id=str(identity["policy_id"]),
        policy_name=str(identity["policy_name"]),
        status=str(identity["status"]),
        enabled=bool(applicability["enabled"]),
        base_mesh_level=str(
            applicability["base_mesh_level"]
        ),
        refinement_kind=str(
            applicability["refinement_kind"]
        ),
        bolt_regions=tuple(
            str(value)
            for value in regions["bolt_regions"]
        ),
        nut_regions=tuple(
            str(value)
            for value in regions["nut_regions"]
        ),
        member_regions=tuple(
            str(value)
            for value in regions["member_regions"]
        ),
        local_size_relative_to_global_max=float(
            sizing["local_size_relative_to_global_max"]
        ),
        transition_distance_relative_to_global_max=float(
            sizing[
                "transition_distance_relative_to_global_max"
            ]
        ),
        distance_sampling=int(
            sizing["distance_sampling"]
        ),
        preserve_base_thread_refinement=bool(
            sizing["preserve_base_thread_refinement"]
        ),
        require_all_regions_resolved=bool(
            verification["require_all_regions_resolved"]
        ),
        require_local_size_below_global_max=bool(
            verification[
                "require_local_size_below_global_max"
            ]
        ),
        require_positive_transition_distance=bool(
            verification[
                "require_positive_transition_distance"
            ]
        ),
        requires_p04_vv06_sentinel=bool(
            verification["requires_p04_vv06_sentinel"]
        ),
    )

    if not policy.policy_id.strip():
        raise ValueError(
            "Local-refinement policy_id must not be blank."
        )

    if not policy.policy_name.strip():
        raise ValueError(
            "Local-refinement policy_name must not be blank."
        )

    if policy.base_mesh_level != "medium":
        raise ValueError(
            "Medium+ v1 must use medium as its base mesh level."
        )

    if (
        policy.refinement_kind
        != "surface_distance_threshold"
    ):
        raise ValueError(
            "Unsupported complete-joint local-refinement kind."
        )

    for label, values in (
        ("bolt_regions", policy.bolt_regions),
        ("nut_regions", policy.nut_regions),
        ("member_regions", policy.member_regions),
    ):
        if not values:
            raise ValueError(
                f"{label} must not be empty."
            )

        if len(set(values)) != len(values):
            raise ValueError(
                f"{label} contains duplicate semantic regions."
            )

        if any(
            not value.strip()
            for value in values
        ):
            raise ValueError(
                f"{label} contains a blank semantic region."
            )

    ratio = policy.local_size_relative_to_global_max

    if (
        not math.isfinite(ratio)
        or ratio <= 0.0
        or ratio >= 1.0
    ):
        raise ValueError(
            "Local size ratio must be finite and strictly "
            "between zero and one."
        )

    transition = (
        policy.transition_distance_relative_to_global_max
    )

    if (
        not math.isfinite(transition)
        or transition <= 0.0
    ):
        raise ValueError(
            "Transition-distance ratio must be finite "
            "and positive."
        )

    if policy.distance_sampling <= 0:
        raise ValueError(
            "Distance sampling must be positive."
        )

    if not policy.preserve_base_thread_refinement:
        raise ValueError(
            "Medium+ v1 must preserve base thread refinement."
        )

    return policy


def resolve_complete_joint_local_refinement(
    *,
    policy: CompleteJointLocalRefinementPolicy,
    base_mesh_level: str,
    global_max_size_mm: float,
) -> ResolvedCompleteJointLocalRefinement:
    """Resolve dimensioned Medium+ refinement values from governed ratios."""

    if not policy.enabled:
        raise ValueError(
            "Cannot resolve a disabled local-refinement policy."
        )

    if base_mesh_level != policy.base_mesh_level:
        raise ValueError(
            "Resolved base mesh level does not match "
            "the local-refinement policy."
        )

    if (
        not math.isfinite(global_max_size_mm)
        or global_max_size_mm <= 0.0
    ):
        raise ValueError(
            "Global maximum mesh size must be finite and positive."
        )

    local_size_mm = (
        policy.local_size_relative_to_global_max
        * global_max_size_mm
    )

    transition_distance_mm = (
        policy.transition_distance_relative_to_global_max
        * global_max_size_mm
    )

    if (
        policy.require_local_size_below_global_max
        and local_size_mm >= global_max_size_mm
    ):
        raise ValueError(
            "Resolved local size must be below global maximum."
        )

    if (
        policy.require_positive_transition_distance
        and transition_distance_mm <= 0.0
    ):
        raise ValueError(
            "Resolved transition distance must be positive."
        )

    return ResolvedCompleteJointLocalRefinement(
        policy_id=policy.policy_id,
        policy_name=policy.policy_name,
        base_mesh_level=base_mesh_level,
        local_size_mm=local_size_mm,
        transition_distance_mm=(
            transition_distance_mm
        ),
        distance_sampling=policy.distance_sampling,
        bolt_regions=policy.bolt_regions,
        nut_regions=policy.nut_regions,
        member_regions=policy.member_regions,
    )


# === SEMANTIC LOCAL-REFINEMENT SURFACE RESOLUTION ===


class _TaggedSurfaceFamily(Protocol):
    def tags_for(
        self,
        region: str,
    ) -> tuple[int, ...]:
        ...


class _MemberSurface(Protocol):
    tag: int
    region: str


class _LocalRefinementClassification(Protocol):
    bolt: _TaggedSurfaceFamily
    nut: _TaggedSurfaceFamily
    member_surfaces: tuple[_MemberSurface, ...]


@dataclass(frozen=True, slots=True)
class ResolvedCompleteJointLocalRefinementSurfaceTags:
    """CAD surfaces selected from semantic classification metadata."""

    bolt_surface_tags: tuple[int, ...]
    nut_surface_tags: tuple[int, ...]
    member_surface_tags: tuple[int, ...]
    all_surface_tags: tuple[int, ...]


def resolve_complete_joint_local_refinement_surface_tags(
    *,
    refinement: ResolvedCompleteJointLocalRefinement,
    classification: _LocalRefinementClassification,
) -> ResolvedCompleteJointLocalRefinementSurfaceTags:
    """Resolve Medium+ CAD surfaces without IDs or geometry assumptions."""

    bolt_tags: list[int] = []

    for region in refinement.bolt_regions:
        tags = tuple(
            int(tag)
            for tag in classification.bolt.tags_for(
                region
            )
        )

        if not tags:
            raise RuntimeError(
                "Medium+ could not resolve required bolt region: "
                f"{region}"
            )

        bolt_tags.extend(tags)

    nut_tags: list[int] = []

    for region in refinement.nut_regions:
        tags = tuple(
            int(tag)
            for tag in classification.nut.tags_for(
                region
            )
        )

        if not tags:
            raise RuntimeError(
                "Medium+ could not resolve required nut region: "
                f"{region}"
            )

        nut_tags.extend(tags)

    member_tags: list[int] = []

    for region in refinement.member_regions:
        tags = tuple(
            int(surface.tag)
            for surface in classification.member_surfaces
            if surface.region == region
        )

        if not tags:
            raise RuntimeError(
                "Medium+ could not resolve required member region: "
                f"{region}"
            )

        member_tags.extend(tags)

    bolt_unique = tuple(
        sorted(set(bolt_tags))
    )

    nut_unique = tuple(
        sorted(set(nut_tags))
    )

    member_unique = tuple(
        sorted(set(member_tags))
    )

    all_tags_raw = (
        *bolt_unique,
        *nut_unique,
        *member_unique,
    )

    all_unique = tuple(
        sorted(set(all_tags_raw))
    )

    if len(all_unique) != len(all_tags_raw):
        raise RuntimeError(
            "Medium+ semantic refinement regions resolved "
            "overlapping CAD surface tags."
        )

    if not all_unique:
        raise RuntimeError(
            "Medium+ resolved no CAD surfaces."
        )

    return ResolvedCompleteJointLocalRefinementSurfaceTags(
        bolt_surface_tags=bolt_unique,
        nut_surface_tags=nut_unique,
        member_surface_tags=member_unique,
        all_surface_tags=all_unique,
    )
