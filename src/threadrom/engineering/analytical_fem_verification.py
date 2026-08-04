"""Governed analytical-to-FEM verification matrix definitions."""

from __future__ import annotations

import math
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import cast


class EvidenceStatus(StrEnum):
    """Current evidence state for one verification target."""

    PASS = "pass"
    FAIL = "fail"
    INCONCLUSIVE_SOLVER = "inconclusive_solver"
    PENDING_SOLVER = "pending_solver"
    PENDING_EXTRACTOR = "pending_extractor"
    DEDICATED_SIMULATION_REQUIRED = "dedicated_simulation_required"


class AcceptanceMetric(StrEnum):
    """Supported verification acceptance metrics."""

    EXACT_RAMP = "exact_ramp"
    ABSOLUTE = "absolute"
    RELATIVE = "relative"
    RELATIVE_OR_ABSOLUTE = "relative_or_absolute"
    QUALITATIVE = "qualitative"


@dataclass(frozen=True)
class VerificationTargetDefinition:
    """One governed analytical-to-FEM verification target."""

    target_id: str
    quantity: str
    analytical_value: float | None
    unit: str | None
    fem_observable: str
    extraction_source: str
    evidence_status: EvidenceStatus
    acceptance_metric: AcceptanceMetric
    relative_tolerance: float | None
    absolute_tolerance: float | None
    evidence_artifact: Path | None
    notes: str

    def __post_init__(self) -> None:
        """Validate one target definition."""

        for label, value in (
            ("target ID", self.target_id),
            ("quantity", self.quantity),
            ("FEM observable", self.fem_observable),
            ("extraction source", self.extraction_source),
            ("notes", self.notes),
        ):
            if not value.strip():
                raise ValueError(f"Verification target {label} must not be empty.")

        if self.analytical_value is not None:
            if not math.isfinite(self.analytical_value):
                raise ValueError("Analytical verification values must be finite.")

            if self.unit is None or not self.unit.strip():
                raise ValueError("An analytical value requires a nonempty unit.")

        for label, tolerance in (
            ("relative", self.relative_tolerance),
            ("absolute", self.absolute_tolerance),
        ):
            if tolerance is None:
                continue

            if not math.isfinite(tolerance) or tolerance <= 0.0:
                raise ValueError(f"{label.capitalize()} tolerance must be finite and positive.")

        if self.acceptance_metric is AcceptanceMetric.EXACT_RAMP:
            if self.relative_tolerance is None or self.absolute_tolerance is None:
                raise ValueError("Exact-ramp acceptance requires relative and absolute tolerances.")

        elif self.acceptance_metric is AcceptanceMetric.ABSOLUTE:
            if self.absolute_tolerance is None:
                raise ValueError("Absolute acceptance requires an absolute tolerance.")

        elif self.acceptance_metric is AcceptanceMetric.RELATIVE:
            if self.relative_tolerance is None:
                raise ValueError("Relative acceptance requires a relative tolerance.")

        elif self.acceptance_metric is AcceptanceMetric.RELATIVE_OR_ABSOLUTE:
            if self.relative_tolerance is None and self.absolute_tolerance is None:
                raise ValueError("Relative-or-absolute acceptance requires at least one tolerance.")

        elif self.acceptance_metric is AcceptanceMetric.QUALITATIVE and (
            self.relative_tolerance is not None or self.absolute_tolerance is not None
        ):
            raise ValueError("Qualitative acceptance must not define numerical tolerances.")

        if (
            self.evidence_status
            in {
                EvidenceStatus.PASS,
                EvidenceStatus.FAIL,
                EvidenceStatus.INCONCLUSIVE_SOLVER,
            }
            and self.evidence_artifact is None
        ):
            raise ValueError(
                "Pass, fail or inconclusive solver evidence "
                "requires an evidence artifact."
            )


@dataclass(frozen=True)
class AnalyticalFemVerificationDefinition:
    """Governed Phase 1 analytical-to-FEM verification matrix."""

    verification_id: str
    analytical_joint_id: str
    simulation_id: str
    mesh_level: str
    element_type: str
    json_relative_path: Path
    report_relative_path: Path
    targets: tuple[VerificationTargetDefinition, ...]

    def __post_init__(self) -> None:
        """Validate matrix-level identity and target uniqueness."""

        for label, value in (
            ("verification ID", self.verification_id),
            ("analytical joint ID", self.analytical_joint_id),
            ("simulation ID", self.simulation_id),
            ("mesh level", self.mesh_level),
            ("element type", self.element_type),
        ):
            if not value.strip():
                raise ValueError(f"Verification {label} must not be empty.")

        if not self.targets:
            raise ValueError("At least one verification target is required.")

        target_ids = [target.target_id for target in self.targets]

        if len(target_ids) != len(set(target_ids)):
            raise ValueError("Verification target IDs must be unique.")

    @property
    def status_counts(self) -> dict[EvidenceStatus, int]:
        """Return target counts for every evidence status."""

        return {
            status: sum(target.evidence_status is status for target in self.targets)
            for status in EvidenceStatus
        }

    def target_by_id(
        self,
        target_id: str,
    ) -> VerificationTargetDefinition:
        """Return one target by governed identifier."""

        for target in self.targets:
            if target.target_id == target_id:
                return target

        raise KeyError(f"Unknown verification target: {target_id}")


def load_analytical_fem_verification_definition(
    config_path: Path,
) -> AnalyticalFemVerificationDefinition:
    """Load the governed analytical-to-FEM verification matrix."""

    with config_path.open("rb") as config_file:
        raw_data: dict[str, object] = tomllib.load(config_file)

    identity = _section(
        raw_data,
        "identity",
    )

    output = _section(
        raw_data,
        "output",
    )

    raw_targets = raw_data.get("targets")

    if not isinstance(raw_targets, list) or not raw_targets:
        raise TypeError("Verification config requires at least one [[targets]] table.")

    targets: list[VerificationTargetDefinition] = []

    for raw_target in raw_targets:
        if not isinstance(raw_target, dict):
            raise TypeError("Every verification target must be a TOML table.")

        target = cast(
            Mapping[str, object],
            raw_target,
        )

        targets.append(
            VerificationTargetDefinition(
                target_id=_string(
                    target,
                    "target_id",
                ),
                quantity=_string(
                    target,
                    "quantity",
                ),
                analytical_value=_optional_number(
                    target,
                    "analytical_value",
                ),
                unit=_optional_string(
                    target,
                    "unit",
                ),
                fem_observable=_string(
                    target,
                    "fem_observable",
                ),
                extraction_source=_string(
                    target,
                    "extraction_source",
                ),
                evidence_status=_enum_value(
                    EvidenceStatus,
                    target,
                    "evidence_status",
                ),
                acceptance_metric=_enum_value(
                    AcceptanceMetric,
                    target,
                    "acceptance_metric",
                ),
                relative_tolerance=_optional_number(
                    target,
                    "relative_tolerance",
                ),
                absolute_tolerance=_optional_number(
                    target,
                    "absolute_tolerance",
                ),
                evidence_artifact=_optional_path(
                    target,
                    "evidence_artifact",
                ),
                notes=_string(
                    target,
                    "notes",
                ),
            )
        )

    return AnalyticalFemVerificationDefinition(
        verification_id=_string(
            identity,
            "verification_id",
        ),
        analytical_joint_id=_string(
            identity,
            "analytical_joint_id",
        ),
        simulation_id=_string(
            identity,
            "simulation_id",
        ),
        mesh_level=_string(
            identity,
            "mesh_level",
        ).lower(),
        element_type=_string(
            identity,
            "element_type",
        ).upper(),
        json_relative_path=Path(
            _string(
                output,
                "json_relative_path",
            )
        ),
        report_relative_path=Path(
            _string(
                output,
                "report_relative_path",
            )
        ),
        targets=tuple(targets),
    )


def _section(
    data: Mapping[str, object],
    key: str,
) -> Mapping[str, object]:
    """Return one required TOML section."""

    raw_value = data.get(key)

    if not isinstance(raw_value, dict):
        raise TypeError(f"Required TOML section [{key}] is missing.")

    return cast(
        Mapping[str, object],
        raw_value,
    )


def _string(
    data: Mapping[str, object],
    key: str,
) -> str:
    """Return one required nonempty string."""

    raw_value = data.get(key)

    if not isinstance(raw_value, str):
        raise TypeError(f"Required TOML value '{key}' must be a string.")

    value = raw_value.strip()

    if not value:
        raise ValueError(f"Required TOML value '{key}' must not be empty.")

    return value


def _optional_string(
    data: Mapping[str, object],
    key: str,
) -> str | None:
    """Return one optional nonempty string."""

    if key not in data:
        return None

    return _string(
        data,
        key,
    )


def _optional_number(
    data: Mapping[str, object],
    key: str,
) -> float | None:
    """Return one optional finite number."""

    if key not in data:
        return None

    raw_value = data[key]

    if isinstance(raw_value, bool) or not isinstance(raw_value, int | float):
        raise TypeError(f"TOML value '{key}' must be numerical.")

    value = float(raw_value)

    if not math.isfinite(value):
        raise ValueError(f"TOML value '{key}' must be finite.")

    return value


def _optional_path(
    data: Mapping[str, object],
    key: str,
) -> Path | None:
    """Return one optional relative path."""

    value = _optional_string(
        data,
        key,
    )

    if value is None:
        return None

    path = Path(value)

    if path.is_absolute():
        raise ValueError(f"TOML path '{key}' must be repository-relative.")

    return path


def _enum_value[EnumType: StrEnum](
    enum_type: type[EnumType],
    data: Mapping[str, object],
    key: str,
) -> EnumType:
    """Return one governed string-enum value."""

    value = _string(
        data,
        key,
    ).lower()

    try:
        return enum_type(value)
    except ValueError as error:
        supported = ", ".join(member.value for member in enum_type)

        raise ValueError(
            f"Unsupported value '{value}' for '{key}'. Supported values: {supported}."
        ) from error
