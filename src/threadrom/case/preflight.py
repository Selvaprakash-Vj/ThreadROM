"""Backend-neutral result model for governed ThreadROM preflight checks."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from threadrom.case import CaseSupportStatus


class PreflightTarget(StrEnum):
    """Pipeline stage for which a case is being preflighted."""

    RESOLUTION = "resolution"
    ANALYTICAL = "analytical"
    GEOMETRY = "geometry"
    FEM = "fem"
    ROM = "rom"


class PreflightSeverity(StrEnum):
    """Severity of one governed preflight finding."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class PreflightDisposition(StrEnum):
    """Whether the requested pipeline stage may proceed."""

    PASS = "pass"
    BLOCKED = "blocked"


class PreflightRuleCode(StrEnum):
    """Stable machine-readable identifiers for governed preflight rules."""

    STANDARD_DIMENSIONS_AVAILABLE = "standard_dimensions_available"
    MATERIAL_DATA_AVAILABLE = "material_data_available"
    PROPERTY_CLASS_AVAILABLE = "property_class_available"
    PRODUCT_TOPOLOGY_SUPPORTED = "product_topology_supported"
    BOLT_LENGTH_FEASIBLE = "bolt_length_feasible"
    THREAD_ENGAGEMENT_FEASIBLE = "thread_engagement_feasible"
    PROPERTY_CLASS_COMPATIBLE = "property_class_compatible"
    FRICTION_ENVELOPE_SUPPORTED = "friction_envelope_supported"
    SERVICE_TEMPERATURE_SUPPORTED = "service_temperature_supported"
    ANALYSIS_CAPABILITY_SUPPORTED = "analysis_capability_supported"


@dataclass(frozen=True)
class PreflightFinding:
    """One deterministic preflight observation."""

    code: PreflightRuleCode
    severity: PreflightSeverity
    message: str

    def __post_init__(self) -> None:
        if not self.message.strip():
            raise ValueError("Preflight finding message must not be empty.")


@dataclass(frozen=True)
class PreflightReport:
    """Governed preflight result for one case and requested target."""

    case_hash: str
    target: PreflightTarget
    support_status: CaseSupportStatus
    findings: tuple[PreflightFinding, ...] = ()

    def __post_init__(self) -> None:
        if not self.case_hash.strip():
            raise ValueError("Preflight case hash must not be empty.")

    @property
    def blocking_findings(self) -> tuple[PreflightFinding, ...]:
        """Return findings that prevent the requested stage from running."""

        return tuple(
            finding
            for finding in self.findings
            if finding.severity is PreflightSeverity.ERROR
        )

    @property
    def warnings(self) -> tuple[PreflightFinding, ...]:
        """Return non-blocking warning findings."""

        return tuple(
            finding
            for finding in self.findings
            if finding.severity is PreflightSeverity.WARNING
        )

    @property
    def disposition(self) -> PreflightDisposition:
        """Return whether the requested pipeline stage may proceed."""

        if self.blocking_findings:
            return PreflightDisposition.BLOCKED
        return PreflightDisposition.PASS

    @property
    def can_proceed(self) -> bool:
        """Return True only when no blocking preflight finding exists."""

        return self.disposition is PreflightDisposition.PASS
