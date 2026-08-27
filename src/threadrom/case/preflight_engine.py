"""Governed orchestration for ThreadROM case preflight."""

from __future__ import annotations

from threadrom.case.capabilities import assess_case_capability
from threadrom.case.contract import ThreadROMCase
from threadrom.case.preflight import (
    PreflightReport,
    PreflightSeverity,
    PreflightTarget,
)
from threadrom.case.preflight_rules import (
    check_analysis_capability,
    check_bolt_length_feasible,
    check_material_data,
    check_product_topology,
    check_property_class_data,
    check_standard_dimensions,
)
from threadrom.case.resolver import resolve_case
from threadrom.case.serialization import case_sha256
from threadrom.materials.baseline_catalog import (
    BASELINE_MATERIAL_CATALOG,
)
from threadrom.materials.catalog import MaterialCatalog


def preflight_case(
    case: ThreadROMCase,
    target: PreflightTarget,
    *,
    material_catalog: MaterialCatalog = BASELINE_MATERIAL_CATALOG,
) -> PreflightReport:
    """Run deterministic governed preflight for one requested target.

    Normal unsupported-case conditions are collected as findings rather
    than discovered through downstream exceptions.

    If all static pre-resolution rules pass, deterministic resolution is
    executed as an invariant check. A resolver failure at that point means
    the preflight rule set and resolver have drifted apart and is therefore
    treated as an implementation error rather than a normal case rejection.
    """

    findings = []

    # Fixed deterministic order. Do not reorder casually: stable ordering
    # matters for diagnostics, testing, and future machine-readable output.
    findings.extend(check_standard_dimensions(case))
    findings.extend(
        check_material_data(
            case,
            material_catalog=material_catalog,
        )
    )
    findings.extend(
        check_property_class_data(
            case,
            material_catalog=material_catalog,
        )
    )
    findings.extend(check_product_topology(case))
    findings.extend(check_bolt_length_feasible(case))

    static_blocked = any(
        finding.severity is PreflightSeverity.ERROR
        for finding in findings
    )

    if not static_blocked:
        try:
            resolve_case(
                case,
                material_catalog=material_catalog,
            )
        except ValueError as exc:
            raise RuntimeError(
                "Preflight/resolver invariant violation: static "
                "preflight passed, but deterministic case resolution "
                "failed."
            ) from exc

    findings.extend(
        check_analysis_capability(
            case,
            target,
        )
    )

    capability = assess_case_capability(case)

    return PreflightReport(
        case_hash=case_sha256(case),
        target=target,
        support_status=capability.status,
        findings=tuple(findings),
    )
