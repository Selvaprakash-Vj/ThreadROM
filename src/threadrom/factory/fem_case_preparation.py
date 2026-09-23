"""Generic governed FEM case-preparation contracts."""

from __future__ import annotations

import math
from dataclasses import dataclass

from threadrom.case.contract import ThreadROMCase
from threadrom.case.resolved_case import ResolvedCase


@dataclass(frozen=True, slots=True)
class FemCaseIdentity:
    """Deterministic request and resolved-execution identity of one FEM case."""

    case_hash: str
    resolution_hash: str
    run_id: str
    job_name: str

    def __post_init__(self) -> None:
        for value, label in (
            (self.case_hash, "FEM case hash"),
            (self.resolution_hash, "FEM resolution hash"),
        ):
            if len(value) != 64:
                raise ValueError(
                    f"{label} must contain 64 hexadecimal characters."
                )

            try:
                int(value, 16)
            except ValueError as exc:
                raise ValueError(
                    f"{label} must be hexadecimal."
                ) from exc

        if not self.run_id.strip():
            raise ValueError(
                "FEM run_id must not be blank."
            )

        if not self.job_name.strip():
            raise ValueError(
                "FEM job_name must not be blank."
            )


@dataclass(frozen=True, slots=True)
class FemCasePhysicsInputs:
    """Case-derived physical inputs required by the FEM backend."""

    target_preload_n: float
    common_friction_coefficient: float
    youngs_modulus_mpa: float
    poissons_ratio: float
    bolt_thermal_expansion_per_c: float
    bolt_thermal_source_reference: str
    member_youngs_modulus_mpa: float | None = None
    member_poissons_ratio: float | None = None

    def __post_init__(self) -> None:
        if (
            not math.isfinite(self.target_preload_n)
            or self.target_preload_n <= 0.0
        ):
            raise ValueError(
                "FEM target preload must be finite and positive."
            )

        if (
            not math.isfinite(self.common_friction_coefficient)
            or not 0.0 <= self.common_friction_coefficient <= 1.0
        ):
            raise ValueError(
                "FEM common friction coefficient must lie in [0, 1]."
            )

        if (
            not math.isfinite(self.youngs_modulus_mpa)
            or self.youngs_modulus_mpa <= 0.0
        ):
            raise ValueError(
                "FEM Young's modulus must be finite and positive."
            )

        if (
            not math.isfinite(self.poissons_ratio)
            or not -1.0 < self.poissons_ratio < 0.5
        ):
            raise ValueError(
                "FEM Poisson's ratio must lie between -1 and 0.5."
            )

        member_e = self.member_youngs_modulus_mpa
        member_nu = self.member_poissons_ratio

        if (member_e is None) != (member_nu is None):
            raise ValueError(
                "Member elastic modulus and Poisson ratio must "
                "be supplied together."
            )

        if member_e is not None:
            if (
                not math.isfinite(member_e)
                or member_e <= 0.0
                or not math.isfinite(member_nu)
                or not -1.0 < member_nu < 0.5
            ):
                raise ValueError(
                    "Invalid governed member-group elastic properties."
                )

        if (
            not math.isfinite(self.bolt_thermal_expansion_per_c)
            or self.bolt_thermal_expansion_per_c <= 0.0
        ):
            raise ValueError(
                "Bolt thermal expansion coefficient must be "
                "finite and positive."
            )

        if not self.bolt_thermal_source_reference.strip():
            raise ValueError(
                "Bolt thermal expansion requires a governed "
                "source reference."
            )


@dataclass(frozen=True, slots=True)
class FemCasePreparation:
    """Case-derived inputs ready for generic FEM artifact generation."""

    identity: FemCaseIdentity
    physics: FemCasePhysicsInputs


def derive_common_contact_friction(
    case: ThreadROMCase,
    *,
    tolerance: float = 1.0e-12,
) -> float:
    """Resolve the backend's currently supported common friction value.

    The current CalculiX complete-joint contact contract exposes one
    friction coefficient shared by every contact pair. ThreadROM's
    product case contract is richer and carries four independent
    coefficients. Until the solver contact contract is generalized,
    unequal requested coefficients must be rejected explicitly rather
    than silently collapsed.
    """

    values = (
        case.interfaces.thread_friction_coefficient,
        case.interfaces.head_bearing_friction_coefficient,
        case.interfaces.nut_bearing_friction_coefficient,
        case.interfaces.member_interface_friction_coefficient,
    )

    reference = values[0]

    if not all(
        math.isclose(
            value,
            reference,
            rel_tol=0.0,
            abs_tol=tolerance,
        )
        for value in values[1:]
    ):
        raise ValueError(
            "The current complete-joint FEM backend requires a common "
            "friction coefficient across thread, head-bearing, "
            "nut-bearing and member interfaces."
        )

    return reference


def derive_common_elastic_properties(
    resolved: ResolvedCase,
    *,
    relative_tolerance: float = 1.0e-12,
    absolute_tolerance: float = 1.0e-12,
) -> tuple[float, float]:
    """Resolve the transfer backend's common isotropic elastic model.

    ResolvedCase correctly preserves component-specific materials.
    The current complete-joint CalculiX transfer contract, however,
    exposes only one Young's modulus and one Poisson's ratio. Mixed
    elastic properties must therefore be rejected until that backend
    contract is generalized.
    """

    materials = (
        resolved.bolt_material,
        resolved.nut_material,
        *resolved.member_materials,
    )

    reference = materials[0]

    for material in materials[1:]:
        same_youngs_modulus = math.isclose(
            material.youngs_modulus_mpa,
            reference.youngs_modulus_mpa,
            rel_tol=relative_tolerance,
            abs_tol=absolute_tolerance,
        )
        same_poissons_ratio = math.isclose(
            material.poissons_ratio,
            reference.poissons_ratio,
            rel_tol=relative_tolerance,
            abs_tol=absolute_tolerance,
        )

        if not (
            same_youngs_modulus
            and same_poissons_ratio
        ):
            raise ValueError(
                "The current complete-joint FEM transfer backend "
                "requires common isotropic elastic properties across "
                "bolt, nut and clamped-member materials."
            )

    return (
        reference.youngs_modulus_mpa,
        reference.poissons_ratio,
    )


def derive_two_group_elastic_properties(
    resolved: ResolvedCase,
    *,
    relative_tolerance: float = 1.0e-12,
    absolute_tolerance: float = 1.0e-12,
) -> tuple[float, float, float, float]:
    """Return (fastener E, fastener nu, member E, member nu).

    Bolt and nut must have the same material identity and elastic
    properties. Both clamped members must likewise match each other.
    The two groups may differ. This is not DOE material certification.
    """
    fastener = resolved.source_case.fastener
    layers = tuple(resolved.source_case.members.layers)
    member_materials = tuple(resolved.member_materials)

    if (
        fastener.bolt_material_id != fastener.nut_material_id
        or len(layers) != 2
        or len(member_materials) != 2
        or layers[0].material_id != layers[1].material_id
    ):
        raise ValueError(
            "Governed FEM requires one bolt/nut material identity "
            "and one common upper/lower member material identity."
        )

    def require_matching(first, second, label):
        for property_name in (
            "youngs_modulus_mpa",
            "poissons_ratio",
        ):
            first_value = getattr(first, property_name)
            second_value = getattr(second, property_name)
            if not (
                math.isfinite(first_value)
                and math.isfinite(second_value)
                and math.isclose(
                    first_value,
                    second_value,
                    rel_tol=relative_tolerance,
                    abs_tol=absolute_tolerance,
                )
            ):
                raise ValueError(
                    f"{label} elastic-property mismatch: "
                    f"{property_name}"
                )

    require_matching(
        resolved.bolt_material,
        resolved.nut_material,
        "Bolt/nut",
    )
    require_matching(
        member_materials[0],
        member_materials[1],
        "Upper/lower member",
    )

    fastener_e = resolved.bolt_material.youngs_modulus_mpa
    fastener_nu = resolved.bolt_material.poissons_ratio
    member_e = member_materials[0].youngs_modulus_mpa
    member_nu = member_materials[0].poissons_ratio

    for modulus, ratio in (
        (fastener_e, fastener_nu),
        (member_e, member_nu),
    ):
        if (
            modulus <= 0.0
            or not -1.0 < ratio < 0.5
        ):
            raise ValueError(
                "Invalid two-group isotropic elastic properties."
            )

    return fastener_e, fastener_nu, member_e, member_nu


def derive_bolt_thermal_expansion(
    resolved: ResolvedCase,
) -> tuple[float, str]:
    """Return governed bolt thermal data for the preload actuator."""

    material = resolved.bolt_material

    coefficient = material.thermal_expansion_per_c
    source_reference = material.thermal_source_reference

    if coefficient is None:
        raise ValueError(
            "The thermal-preload FEM backend requires a governed "
            "bolt thermal expansion coefficient."
        )

    if (
        source_reference is None
        or not source_reference.strip()
    ):
        raise ValueError(
            "The thermal-preload FEM backend requires provenance "
            "for the bolt thermal expansion coefficient."
        )

    return coefficient, source_reference


def derive_fem_case_preparation(
    resolved: ResolvedCase,
    *,
    run_prefix: str = "trm_fem",
) -> FemCasePreparation:
    """Derive deterministic non-reference FEM preparation inputs."""

    if not run_prefix.strip():
        raise ValueError(
            "FEM run prefix must not be blank."
        )

    digest = resolved.resolution_hash
    short_hash = digest[:12]

    run_id = (
        f"{run_prefix}_{short_hash}"
    ).lower()

    friction = derive_common_contact_friction(
        resolved.source_case
    )

    (
        youngs_modulus_mpa,
        poissons_ratio,
        member_youngs_modulus_mpa,
        member_poissons_ratio,
    ) = derive_two_group_elastic_properties(resolved)

    (
        bolt_thermal_expansion_per_c,
        bolt_thermal_source_reference,
    ) = derive_bolt_thermal_expansion(
        resolved
    )

    return FemCasePreparation(
        identity=FemCaseIdentity(
            case_hash=resolved.case_hash,
            resolution_hash=digest,
            run_id=run_id,
            job_name=run_id,
        ),
        physics=FemCasePhysicsInputs(
            target_preload_n=(
                resolved.source_case.loading.target_preload_n
            ),
            common_friction_coefficient=friction,
            youngs_modulus_mpa=youngs_modulus_mpa,
            poissons_ratio=poissons_ratio,
            member_youngs_modulus_mpa=member_youngs_modulus_mpa,
            member_poissons_ratio=member_poissons_ratio,
            bolt_thermal_expansion_per_c=(
                bolt_thermal_expansion_per_c
            ),
            bolt_thermal_source_reference=(
                bolt_thermal_source_reference
            ),
        ),
    )
