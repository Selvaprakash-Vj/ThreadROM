from __future__ import annotations

from pathlib import Path

import pytest

from threadrom.meshing.complete_joint_local_refinement import (
    load_complete_joint_local_refinement_policy,
    resolve_complete_joint_local_refinement,
)


ROOT = Path(__file__).resolve().parents[2]


def test_medium_plus_policy_loads() -> None:
    policy = load_complete_joint_local_refinement_policy(
        ROOT
        / "config"
        / "complete_joint_local_refinement.toml"
    )

    assert policy.policy_id == "TRM-LRP-000001"
    assert policy.policy_name == "medium_plus_v1"

    assert policy.base_mesh_level == "medium"

    assert (
        policy.refinement_kind
        == "surface_distance_threshold"
    )

    assert policy.local_size_relative_to_global_max == 0.50

    assert (
        policy.transition_distance_relative_to_global_max
        == 0.15
    )

    assert policy.distance_sampling == 30

    assert policy.bolt_regions == (
        "under_head_bearing",
    )

    assert policy.nut_regions == (
        "lower_bearing",
    )

    assert policy.member_regions == (
        "head_member_head_bearing",
        "nut_member_nut_bearing",
        "head_member_interface",
        "nut_member_interface",
    )

    assert policy.requires_p04_vv06_sentinel is True


def test_medium_plus_resolves_from_global_medium_size() -> None:
    policy = load_complete_joint_local_refinement_policy(
        ROOT
        / "config"
        / "complete_joint_local_refinement.toml"
    )

    resolved = resolve_complete_joint_local_refinement(
        policy=policy,
        base_mesh_level="medium",
        global_max_size_mm=1.005,
    )

    assert resolved.local_size_mm == pytest.approx(
        0.5025
    )

    assert resolved.transition_distance_mm == pytest.approx(
        0.15075
    )

    assert resolved.distance_sampling == 30


def test_medium_plus_rejects_wrong_base_level() -> None:
    policy = load_complete_joint_local_refinement_policy(
        ROOT
        / "config"
        / "complete_joint_local_refinement.toml"
    )

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        resolve_complete_joint_local_refinement(
            policy=policy,
            base_mesh_level="fine",
            global_max_size_mm=1.005,
        )


@pytest.mark.parametrize(
    "global_max_size_mm",
    (
        0.0,
        -1.0,
        float("nan"),
    ),
)
def test_medium_plus_rejects_invalid_global_size(
    global_max_size_mm: float,
) -> None:
    policy = load_complete_joint_local_refinement_policy(
        ROOT
        / "config"
        / "complete_joint_local_refinement.toml"
    )

    with pytest.raises(
        ValueError,
        match="finite and positive",
    ):
        resolve_complete_joint_local_refinement(
            policy=policy,
            base_mesh_level="medium",
            global_max_size_mm=global_max_size_mm,
        )



def test_medium_plus_semantic_surface_resolution() -> None:
    from dataclasses import dataclass
    from types import SimpleNamespace

    from threadrom.meshing.complete_joint_local_refinement import (
        load_complete_joint_local_refinement_policy,
        resolve_complete_joint_local_refinement,
        resolve_complete_joint_local_refinement_surface_tags,
    )

    @dataclass(frozen=True)
    class Family:
        mapping: dict[str, tuple[int, ...]]

        def tags_for(
            self,
            region: str,
        ) -> tuple[int, ...]:
            return self.mapping.get(region, ())

    @dataclass(frozen=True)
    class Member:
        tag: int
        region: str

    policy = load_complete_joint_local_refinement_policy(
        ROOT
        / "config"
        / "complete_joint_local_refinement.toml"
    )

    refinement = resolve_complete_joint_local_refinement(
        policy=policy,
        base_mesh_level="medium",
        global_max_size_mm=1.005,
    )

    classification = SimpleNamespace(
        bolt=Family(
            {
                "under_head_bearing": (101,),
            }
        ),
        nut=Family(
            {
                "lower_bearing": (201,),
            }
        ),
        member_surfaces=(
            Member(
                301,
                "head_member_head_bearing",
            ),
            Member(
                302,
                "nut_member_nut_bearing",
            ),
            Member(
                303,
                "head_member_interface",
            ),
            Member(
                304,
                "nut_member_interface",
            ),
        ),
    )

    resolved = (
        resolve_complete_joint_local_refinement_surface_tags(
            refinement=refinement,
            classification=classification,
        )
    )

    assert resolved.bolt_surface_tags == (
        101,
    )

    assert resolved.nut_surface_tags == (
        201,
    )

    assert resolved.member_surface_tags == (
        301,
        302,
        303,
        304,
    )

    assert resolved.all_surface_tags == (
        101,
        201,
        301,
        302,
        303,
        304,
    )


def test_medium_plus_semantic_resolution_rejects_missing_region() -> None:
    from dataclasses import dataclass
    from types import SimpleNamespace

    from threadrom.meshing.complete_joint_local_refinement import (
        load_complete_joint_local_refinement_policy,
        resolve_complete_joint_local_refinement,
        resolve_complete_joint_local_refinement_surface_tags,
    )

    @dataclass(frozen=True)
    class Family:
        mapping: dict[str, tuple[int, ...]]

        def tags_for(
            self,
            region: str,
        ) -> tuple[int, ...]:
            return self.mapping.get(region, ())

    @dataclass(frozen=True)
    class Member:
        tag: int
        region: str

    policy = load_complete_joint_local_refinement_policy(
        ROOT
        / "config"
        / "complete_joint_local_refinement.toml"
    )

    refinement = resolve_complete_joint_local_refinement(
        policy=policy,
        base_mesh_level="medium",
        global_max_size_mm=1.005,
    )

    classification = SimpleNamespace(
        bolt=Family(
            {
                "under_head_bearing": (101,),
            }
        ),
        nut=Family(
            {
                "lower_bearing": (201,),
            }
        ),
        member_surfaces=(
            Member(
                301,
                "head_member_head_bearing",
            ),
            Member(
                302,
                "nut_member_nut_bearing",
            ),
            Member(
                303,
                "head_member_interface",
            ),
            # nut_member_interface deliberately absent
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="nut_member_interface",
    ):
        resolve_complete_joint_local_refinement_surface_tags(
            refinement=refinement,
            classification=classification,
        )


def test_medium_plus_semantic_resolution_rejects_overlap() -> None:
    from dataclasses import dataclass
    from types import SimpleNamespace

    from threadrom.meshing.complete_joint_local_refinement import (
        load_complete_joint_local_refinement_policy,
        resolve_complete_joint_local_refinement,
        resolve_complete_joint_local_refinement_surface_tags,
    )

    @dataclass(frozen=True)
    class Family:
        mapping: dict[str, tuple[int, ...]]

        def tags_for(
            self,
            region: str,
        ) -> tuple[int, ...]:
            return self.mapping.get(region, ())

    @dataclass(frozen=True)
    class Member:
        tag: int
        region: str

    policy = load_complete_joint_local_refinement_policy(
        ROOT
        / "config"
        / "complete_joint_local_refinement.toml"
    )

    refinement = resolve_complete_joint_local_refinement(
        policy=policy,
        base_mesh_level="medium",
        global_max_size_mm=1.005,
    )

    classification = SimpleNamespace(
        bolt=Family(
            {
                "under_head_bearing": (101,),
            }
        ),
        nut=Family(
            {
                "lower_bearing": (201,),
            }
        ),
        member_surfaces=(
            # Deliberate duplicate CAD tag with bolt.
            Member(
                101,
                "head_member_head_bearing",
            ),
            Member(
                302,
                "nut_member_nut_bearing",
            ),
            Member(
                303,
                "head_member_interface",
            ),
            Member(
                304,
                "nut_member_interface",
            ),
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="overlapping",
    ):
        resolve_complete_joint_local_refinement_surface_tags(
            refinement=refinement,
            classification=classification,
        )
