"""Deterministic static feasibility rules for ThreadROM preflight."""

from __future__ import annotations

from threadrom.case.contract import ThreadROMCase
from threadrom.case.preflight import (
    PreflightFinding,
    PreflightRuleCode,
    PreflightSeverity,
)


def check_product_topology(
    case: ThreadROMCase,
) -> tuple[PreflightFinding, ...]:
    """Check compatibility with the current complete-joint geometry path.

    These are capability restrictions of the current geometry machinery,
    not universal physical restrictions of ThreadROMCase.
    """

    findings: list[PreflightFinding] = []
    layers = case.members.layers

    if len(layers) != 2:
        findings.append(
            PreflightFinding(
                code=PreflightRuleCode.PRODUCT_TOPOLOGY_SUPPORTED,
                severity=PreflightSeverity.ERROR,
                message=(
                    "The current complete-joint geometry path requires "
                    "exactly two clamped-member layers."
                ),
            )
        )
        return tuple(findings)

    upper_layer, lower_layer = layers

    if (
        upper_layer.clearance_hole_diameter_mm
        != lower_layer.clearance_hole_diameter_mm
    ):
        findings.append(
            PreflightFinding(
                code=PreflightRuleCode.PRODUCT_TOPOLOGY_SUPPORTED,
                severity=PreflightSeverity.ERROR,
                message=(
                    "The current complete-joint geometry path requires "
                    "equal clearance-hole diameters in both member layers."
                ),
            )
        )

    if (
        upper_layer.outer_diameter_mm
        != lower_layer.outer_diameter_mm
    ):
        findings.append(
            PreflightFinding(
                code=PreflightRuleCode.PRODUCT_TOPOLOGY_SUPPORTED,
                severity=PreflightSeverity.ERROR,
                message=(
                    "The current complete-joint geometry path requires "
                    "equal outer diameters in both member layers."
                ),
            )
        )

    return tuple(findings)



def check_standard_dimensions(
    case: ThreadROMCase,
) -> tuple[PreflightFinding, ...]:
    """Check that all required governed dimensional records exist."""

    from threadrom.case.standards import (
        resolve_bolt_standard,
        resolve_metric_thread_standard,
        resolve_nut_standard,
    )

    findings: list[PreflightFinding] = []
    fastener = case.fastener

    lookups = (
        (
            "thread",
            lambda: resolve_metric_thread_standard(
                fastener.thread_designation
            ),
        ),
        (
            "bolt",
            lambda: resolve_bolt_standard(
                fastener.bolt_standard,
                fastener.thread_designation,
            ),
        ),
        (
            "nut",
            lambda: resolve_nut_standard(
                fastener.nut_standard,
                fastener.thread_designation,
            ),
        ),
    )

    for label, lookup in lookups:
        try:
            lookup()
        except ValueError as exc:
            findings.append(
                PreflightFinding(
                    code=(
                        PreflightRuleCode
                        .STANDARD_DIMENSIONS_AVAILABLE
                    ),
                    severity=PreflightSeverity.ERROR,
                    message=(
                        f"Governed {label} dimensional data are "
                        f"unavailable: {exc}"
                    ),
                )
            )

    return tuple(findings)


def check_material_data(
    case: ThreadROMCase,
    *,
    material_catalog=None,
) -> tuple[PreflightFinding, ...]:
    """Check that every referenced material family is governed."""

    from threadrom.materials.baseline_catalog import (
        BASELINE_MATERIAL_CATALOG,
    )

    if material_catalog is None:
        material_catalog = BASELINE_MATERIAL_CATALOG

    findings: list[PreflightFinding] = []

    material_references = [
        ("bolt", case.fastener.bolt_material_id),
        ("nut", case.fastener.nut_material_id),
    ]
    material_references.extend(
        (f"member {layer.layer_id}", layer.material_id)
        for layer in case.members.layers
    )

    for label, material_id in material_references:
        try:
            material_catalog.get_material(material_id)
        except ValueError as exc:
            findings.append(
                PreflightFinding(
                    code=PreflightRuleCode.MATERIAL_DATA_AVAILABLE,
                    severity=PreflightSeverity.ERROR,
                    message=(
                        f"Governed material data are unavailable "
                        f"for {label}: {exc}"
                    ),
                )
            )

    return tuple(findings)


def check_property_class_data(
    case: ThreadROMCase,
    *,
    material_catalog=None,
) -> tuple[PreflightFinding, ...]:
    """Check that requested bolt and nut property classes are governed."""

    from threadrom.materials.baseline_catalog import (
        BASELINE_MATERIAL_CATALOG,
    )
    from threadrom.materials.fastener_classes import (
        FastenerComponentKind,
    )

    if material_catalog is None:
        material_catalog = BASELINE_MATERIAL_CATALOG

    findings: list[PreflightFinding] = []

    requests = (
        (
            FastenerComponentKind.BOLT,
            case.fastener.bolt_property_class,
        ),
        (
            FastenerComponentKind.NUT,
            case.fastener.nut_property_class,
        ),
    )

    for component_kind, property_class in requests:
        try:
            material_catalog.get_fastener_property_class(
                component_kind,
                property_class,
            )
        except ValueError as exc:
            findings.append(
                PreflightFinding(
                    code=PreflightRuleCode.PROPERTY_CLASS_AVAILABLE,
                    severity=PreflightSeverity.ERROR,
                    message=(
                        "Governed fastener property-class data are "
                        f"unavailable: {exc}"
                    ),
                )
            )

    return tuple(findings)


def check_bolt_length_feasible(
    case: ThreadROMCase,
) -> tuple[PreflightFinding, ...]:
    """Check bolt length against resolved grip and nut thickness."""

    from threadrom.case.standards import resolve_nut_standard

    fastener = case.fastener

    try:
        nut_standard = resolve_nut_standard(
            fastener.nut_standard,
            fastener.thread_designation,
        )
    except ValueError:
        # Missing dimensional data are reported by
        # check_standard_dimensions(); avoid cascading findings here.
        return ()

    required_length_mm = (
        case.members.total_grip_length_mm
        + nut_standard.thickness_mm
    )

    if fastener.bolt_length_mm < required_length_mm:
        return (
            PreflightFinding(
                code=PreflightRuleCode.BOLT_LENGTH_FEASIBLE,
                severity=PreflightSeverity.ERROR,
                message=(
                    f"Bolt length {fastener.bolt_length_mm:g} mm is "
                    f"insufficient for grip "
                    f"{case.members.total_grip_length_mm:g} mm plus "
                    f"nut thickness {nut_standard.thickness_mm:g} mm; "
                    f"minimum geometric length is "
                    f"{required_length_mm:g} mm."
                ),
            ),
        )

    return ()



def check_analysis_capability(
    case: ThreadROMCase,
    target,
) -> tuple[PreflightFinding, ...]:
    """Check whether the requested pipeline target may execute now.

    Support maturity and execution permission are intentionally separate.
    Experimental analytical or geometry work may proceed when its concrete
    prerequisites pass, while FEM and ROM remain blocked until their
    respective governed pipelines are demonstrated.
    """

    from threadrom.case.preflight import PreflightTarget

    if target is PreflightTarget.RESOLUTION:
        return ()

    if target is PreflightTarget.ANALYTICAL:
        if case.loading.external_axial_load_n < 0.0:
            return (
                PreflightFinding(
                    code=(
                        PreflightRuleCode
                        .ANALYSIS_CAPABILITY_SUPPORTED
                    ),
                    severity=PreflightSeverity.ERROR,
                    message=(
                        "The current analytical backend supports only "
                        "non-negative separating external axial load."
                    ),
                ),
            )

        return ()

    if target is PreflightTarget.GEOMETRY:
        # Current case-dependent geometry restrictions are handled by
        # check_product_topology(). The certified geometry profile itself
        # uses the only nut-bore basis supported by the adapter.
        return ()

    if target is PreflightTarget.FEM:
        # Automated FEM execution is authorized after successful
        # certification of the Phase-3 FEM pipeline. Concrete case
        # feasibility remains governed by the topology, material,
        # property-class, bolt-length and resolver checks above.
        return ()

    if target is PreflightTarget.ROM:
        return (
            PreflightFinding(
                code=PreflightRuleCode.ANALYSIS_CAPABILITY_SUPPORTED,
                severity=PreflightSeverity.ERROR,
                message=(
                    "ROM execution is not yet available. A governed ROM "
                    "pipeline is reserved for Phase 4."
                ),
            ),
        )

    raise ValueError(f"Unsupported preflight target: {target!r}.")

def check_fem_backend_restrictions(
    case: ThreadROMCase,
    target,
    *,
    material_catalog=None,
) -> tuple[PreflightFinding, ...]:
    """Check restrictions of the current complete-joint FEM backend.

    These restrictions belong to the current solver-transfer implementation,
    not to the ThreadROM case model. Resolution, analytical work, and geometry
    therefore remain free to represent configurations that the present FEM
    backend cannot yet execute.
    """

    from math import isclose

    from threadrom.case.preflight import PreflightTarget
    from threadrom.materials.baseline_catalog import (
        BASELINE_MATERIAL_CATALOG,
    )

    if target is not PreflightTarget.FEM:
        return ()

    if material_catalog is None:
        material_catalog = BASELINE_MATERIAL_CATALOG

    findings: list[PreflightFinding] = []

    friction_values = (
        case.interfaces.thread_friction_coefficient,
        case.interfaces.head_bearing_friction_coefficient,
        case.interfaces.nut_bearing_friction_coefficient,
        case.interfaces.member_interface_friction_coefficient,
    )

    reference_friction = friction_values[0]

    if not all(
        isclose(
            value,
            reference_friction,
            rel_tol=0.0,
            abs_tol=1.0e-12,
        )
        for value in friction_values[1:]
    ):
        findings.append(
            PreflightFinding(
                code=PreflightRuleCode.FRICTION_ENVELOPE_SUPPORTED,
                severity=PreflightSeverity.ERROR,
                message=(
                    "The current complete-joint FEM backend requires one "
                    "common friction coefficient across thread, head-bearing, "
                    "nut-bearing and member interfaces."
                ),
            )
        )

    material_ids = (
        case.fastener.bolt_material_id,
        case.fastener.nut_material_id,
        *(
            layer.material_id
            for layer in case.members.layers
        ),
    )

    materials = []

    for material_id in material_ids:
        try:
            materials.append(
                material_catalog.get_material(material_id)
            )
        except ValueError:
            # Missing material records are already reported by
            # check_material_data(); avoid duplicate cascading findings.
            return tuple(findings)

    reference_material = materials[0]

    same_elastic_model = all(
        isclose(
            material.youngs_modulus_mpa,
            reference_material.youngs_modulus_mpa,
            rel_tol=1.0e-12,
            abs_tol=1.0e-12,
        )
        and isclose(
            material.poissons_ratio,
            reference_material.poissons_ratio,
            rel_tol=1.0e-12,
            abs_tol=1.0e-12,
        )
        for material in materials[1:]
    )

    if not same_elastic_model:
        findings.append(
            PreflightFinding(
                code=PreflightRuleCode.FEM_ELASTIC_MODEL_SUPPORTED,
                severity=PreflightSeverity.ERROR,
                message=(
                    "The current complete-joint FEM backend requires common "
                    "isotropic elastic properties across bolt, nut and "
                    "clamped-member materials."
                ),
            )
        )

    return tuple(findings)
