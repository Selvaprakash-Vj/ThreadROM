"""Tests for the Phase-3 general FEM acceptance policy."""

from __future__ import annotations

import pytest

from threadrom.case.resolved import ResolvedAssembly
from threadrom.factory.fem_acceptance_policy import (
    FemNonlinearRetryPolicy,
    FemPhysicsAcceptancePolicy,
    FemThreadFlankNormalFamily,
    derive_complete_joint_physics_acceptance_policy,
    derive_complete_joint_thread_flank_normal_family,
)


def test_general_policy_preserves_semantic_inputs() -> None:
    policy = FemPhysicsAcceptancePolicy(
        policy_id="complete_joint_general_v1",
        intended_thread_flank_normal_family=(
            FemThreadFlankNormalFamily.NEGATIVE_Z
        ),
        nonlinear_retry_policy=(
            FemNonlinearRetryPolicy.ALLOW
        ),
    )

    assert (
        policy.intended_thread_flank_normal_family
        is FemThreadFlankNormalFamily.NEGATIVE_Z
    )
    assert not policy.require_first_attempt_only
    assert policy.require_native_thread_contact_force


def test_certification_policy_can_require_att1() -> None:
    policy = FemPhysicsAcceptancePolicy(
        policy_id="phase2_certification_v1",
        intended_thread_flank_normal_family=(
            FemThreadFlankNormalFamily.NEGATIVE_Z
        ),
        nonlinear_retry_policy=(
            FemNonlinearRetryPolicy.REQUIRE_FIRST_ATTEMPT
        ),
    )

    assert policy.require_first_attempt_only


def test_positive_z_flank_is_first_class_policy_value() -> None:
    policy = FemPhysicsAcceptancePolicy(
        policy_id="reversed_orientation_v1",
        intended_thread_flank_normal_family=(
            FemThreadFlankNormalFamily.POSITIVE_Z
        ),
        nonlinear_retry_policy=(
            FemNonlinearRetryPolicy.ALLOW
        ),
    )

    assert (
        policy.to_payload()[
            "intended_thread_flank_normal_family"
        ]
        == "+Z-normal flank"
    )


def test_policy_payload_contains_no_reference_case_magnitudes() -> None:
    policy = FemPhysicsAcceptancePolicy(
        policy_id="general_v1",
        intended_thread_flank_normal_family=(
            FemThreadFlankNormalFamily.NEGATIVE_Z
        ),
        nonlinear_retry_policy=(
            FemNonlinearRetryPolicy.ALLOW
        ),
    )

    payload = policy.to_payload()

    assert "target_force_n" not in payload
    assert "stress_mpa" not in payload
    assert "temperature" not in payload
    assert "increment_count" not in payload


def test_blank_policy_identity_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="policy_id",
    ):
        FemPhysicsAcceptancePolicy(
            policy_id=" ",
            intended_thread_flank_normal_family=(
                FemThreadFlankNormalFamily.NEGATIVE_Z
            ),
            nonlinear_retry_policy=(
                FemNonlinearRetryPolicy.ALLOW
            ),
        )

def _resolved_assembly() -> ResolvedAssembly:
    return ResolvedAssembly(
        assembly_id="test_joint",
        bolt_length_mm=30.0,
        pitch_mm=1.5,
        upper_member_thickness_mm=10.0,
        lower_member_thickness_mm=10.0,
        total_grip_length_mm=20.0,
        nut_thickness_mm=8.0,
        thread_engagement_length_mm=8.0,
        protrusion_length_mm=2.0,
        clearance_hole_diameter_mm=11.0,
        outer_diameter_mm=30.0,
    )


def test_complete_joint_flank_family_is_derived_from_axis_convention() -> None:
    assembly = _resolved_assembly()

    assert assembly.nut_translation_z_mm == 20.0

    assert (
        derive_complete_joint_thread_flank_normal_family(
            assembly
        )
        is FemThreadFlankNormalFamily.NEGATIVE_Z
    )


def test_complete_joint_policy_derives_flank_without_handedness() -> None:
    policy = derive_complete_joint_physics_acceptance_policy(
        _resolved_assembly()
    )

    assert (
        policy.intended_thread_flank_normal_family
        is FemThreadFlankNormalFamily.NEGATIVE_Z
    )

    assert (
        policy.nonlinear_retry_policy
        is FemNonlinearRetryPolicy.ALLOW
    )


def test_complete_joint_certification_can_derive_strict_retry_policy() -> None:
    policy = derive_complete_joint_physics_acceptance_policy(
        _resolved_assembly(),
        policy_id="phase2_certification_v1",
        nonlinear_retry_policy=(
            FemNonlinearRetryPolicy.REQUIRE_FIRST_ATTEMPT
        ),
    )

    assert policy.require_first_attempt_only

