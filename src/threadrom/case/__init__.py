"""ThreadROM governed case-contract package."""

from __future__ import annotations

from enum import StrEnum


class CaseSupportStatus(StrEnum):
    """End-to-end validation maturity of a ThreadROM capability."""

    SUPPORTED = "supported"
    EXPERIMENTAL = "experimental"
    UNSUPPORTED = "unsupported"


class CalculationMode(StrEnum):
    """Requested ThreadROM calculation backend."""

    AUTO = "auto"
    ANALYTICAL = "analytical"
    FEM = "fem"
    ROM = "rom"


class AnalysisFidelity(StrEnum):
    """Requested analysis fidelity / validation level."""

    CERTIFICATION = "certification"
    PRODUCTION = "production"
    SCREENING = "screening"
