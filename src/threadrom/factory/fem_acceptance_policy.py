"""Governed general FEM physics-acceptance policy."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from threadrom.case.resolved import ResolvedAssembly


class FemThreadFlankNormalFamily(str, Enum):
    """Semantic axial-normal family of the intended loaded flank."""

    POSITIVE_Z = "+Z-normal flank"
    NEGATIVE_Z = "-Z-normal flank"


class FemNonlinearRetryPolicy(str, Enum):
    """Governed treatment of nonlinear cutbacks/retries."""

    ALLOW = "allow"
    REQUIRE_FIRST_ATTEMPT = "require_first_attempt"


@dataclass(frozen=True, slots=True)
class FemPhysicsAcceptancePolicy:
    """General physics/numerical acceptance policy for one FEM case.

    This contract intentionally contains no certified Phase-2 result
    magnitudes. Exact reproduction values belong to the separate
    certification oracle.
    """

    policy_id: str
    intended_thread_flank_normal_family: (
        FemThreadFlankNormalFamily
    )
    nonlinear_retry_policy: FemNonlinearRetryPolicy
    require_native_thread_contact_force: bool = True

    def __post_init__(self) -> None:
        if not self.policy_id.strip():
            raise ValueError(
                "FEM physics acceptance policy_id must not be blank."
            )

    @property
    def require_first_attempt_only(self) -> bool:
        """Return whether every accepted increment must be ATT1."""

        return (
            self.nonlinear_retry_policy
            is FemNonlinearRetryPolicy.REQUIRE_FIRST_ATTEMPT
        )

    def to_payload(self) -> dict[str, object]:
        """Return deterministic JSON-compatible policy data."""

        return {
            "intended_thread_flank_normal_family": (
                self.intended_thread_flank_normal_family.value
            ),
            "nonlinear_retry_policy": (
                self.nonlinear_retry_policy.value
            ),
            "policy_id": self.policy_id,
            "require_native_thread_contact_force": (
                self.require_native_thread_contact_force
            ),
        }

def derive_complete_joint_thread_flank_normal_family(
    assembly: ResolvedAssembly,
) -> FemThreadFlankNormalFamily:
    """Derive the loaded bolt-thread flank from assembly orientation.

    The complete-joint coordinate convention places the bolt-head
    datum at Z=0 and the nut at ``nut_translation_z_mm``.

    For the currently supported positive-grip assembly, the nut lies
    in +Z relative to the bolt head. Positive clamp preload therefore
    places the bolt in axial tension, requiring the nut to exert a
    +Z axial reaction on the bolt. Compressive contact traction acts
    opposite the bolt's outward surface normal, so the loaded bolt
    flank must have a -Z normal.

    The derivation is geometric/mechanical and intentionally does not
    depend on thread handedness.
    """

    nut_offset_z_mm = assembly.nut_translation_z_mm

    if nut_offset_z_mm > 0.0:
        return FemThreadFlankNormalFamily.NEGATIVE_Z

    if nut_offset_z_mm < 0.0:
        return FemThreadFlankNormalFamily.POSITIVE_Z

    raise ValueError(
        "The nut must not coincide axially with the bolt-head datum."
    )


def derive_complete_joint_physics_acceptance_policy(
    assembly: ResolvedAssembly,
    *,
    policy_id: str = "complete_joint_general_v1",
    nonlinear_retry_policy: FemNonlinearRetryPolicy = (
        FemNonlinearRetryPolicy.ALLOW
    ),
) -> FemPhysicsAcceptancePolicy:
    """Build the governed general acceptance policy from the assembly."""

    return FemPhysicsAcceptancePolicy(
        policy_id=policy_id,
        intended_thread_flank_normal_family=(
            derive_complete_joint_thread_flank_normal_family(
                assembly
            )
        ),
        nonlinear_retry_policy=nonlinear_retry_policy,
        require_native_thread_contact_force=True,
    )

