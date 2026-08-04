"""Result serialization for the analytical-to-FEM verification matrix."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from threadrom.engineering.analytical_fem_verification import (
    AnalyticalFemVerificationDefinition,
    EvidenceStatus,
)


@dataclass(frozen=True)
class AnalyticalFemVerificationResult:
    """Serialized state of one governed verification matrix."""

    definition: AnalyticalFemVerificationDefinition
    overall_status: str
    status_counts: dict[str, int]

    @property
    def resolved_target_count(self) -> int:
        """Return the number of pass-or-fail targets."""

        return (
            self.status_counts[EvidenceStatus.PASS.value]
            + self.status_counts[EvidenceStatus.FAIL.value]
        )

    @property
    def unresolved_target_count(self) -> int:
        """Return the number of targets still awaiting evidence."""

        return len(self.definition.targets) - self.resolved_target_count

    def to_payload(self) -> dict[str, object]:
        """Return a stable JSON-compatible result payload."""

        target_payloads: list[dict[str, object]] = []

        for target in self.definition.targets:
            target_payloads.append(
                {
                    "target_id": target.target_id,
                    "quantity": target.quantity,
                    "analytical_value": target.analytical_value,
                    "unit": target.unit,
                    "fem_observable": target.fem_observable,
                    "extraction_source": target.extraction_source,
                    "evidence_status": target.evidence_status.value,
                    "acceptance_metric": (target.acceptance_metric.value),
                    "relative_tolerance": (target.relative_tolerance),
                    "absolute_tolerance": (target.absolute_tolerance),
                    "evidence_artifact": (
                        target.evidence_artifact.as_posix()
                        if target.evidence_artifact is not None
                        else None
                    ),
                    "notes": target.notes,
                }
            )

        return {
            "schema_version": 1,
            "verification_id": (self.definition.verification_id),
            "analytical_joint_id": (self.definition.analytical_joint_id),
            "simulation_id": (self.definition.simulation_id),
            "mesh_level": self.definition.mesh_level,
            "element_type": self.definition.element_type,
            "overall_status": self.overall_status,
            "target_count": len(self.definition.targets),
            "resolved_target_count": (self.resolved_target_count),
            "unresolved_target_count": (self.unresolved_target_count),
            "status_counts": self.status_counts,
            "targets": target_payloads,
        }


def build_analytical_fem_verification_result(
    definition: AnalyticalFemVerificationDefinition,
) -> AnalyticalFemVerificationResult:
    """Build the current governed verification result."""

    counter = Counter(target.evidence_status.value for target in definition.targets)

    status_counts = {
        status.value: counter.get(
            status.value,
            0,
        )
        for status in EvidenceStatus
    }

    if status_counts[EvidenceStatus.FAIL.value] > 0:
        overall_status = "fail"
    elif status_counts[EvidenceStatus.INCONCLUSIVE_SOLVER.value] > 0:
        overall_status = "inconclusive"
    elif status_counts[EvidenceStatus.PASS.value] == len(definition.targets):
        overall_status = "pass"
    else:
        overall_status = "pending"

    return AnalyticalFemVerificationResult(
        definition=definition,
        overall_status=overall_status,
        status_counts=status_counts,
    )


def render_analytical_fem_verification_markdown(
    result: AnalyticalFemVerificationResult,
) -> str:
    """Render the governed verification matrix as Markdown."""

    definition = result.definition

    table_rows = []

    for target in definition.targets:
        value = (
            "not applicable"
            if target.analytical_value is None
            else f"{target.analytical_value:.12g}"
        )

        unit = target.unit or "—"

        relative_tolerance = (
            "—"
            if target.relative_tolerance is None
            else f"{100.0 * target.relative_tolerance:.6g}%"
        )

        absolute_tolerance = (
            "—" if target.absolute_tolerance is None else f"{target.absolute_tolerance:.12g} {unit}"
        )

        table_rows.append(
            "| "
            f"{target.target_id} | "
            f"{target.quantity} | "
            f"{value} | "
            f"{unit} | "
            f"{target.evidence_status.value} | "
            f"{target.acceptance_metric.value} | "
            f"{relative_tolerance} | "
            f"{absolute_tolerance} |"
        )

    matrix_table = "\n".join(table_rows)

    evidence_sections = []

    for target in definition.targets:
        evidence_artifact = (
            target.evidence_artifact.as_posix()
            if target.evidence_artifact is not None
            else "not yet available"
        )

        evidence_sections.append(
            "\n".join(
                (
                    f"### `{target.target_id}`",
                    "",
                    f"- Quantity: {target.quantity}",
                    (f"- Current status: `{target.evidence_status.value}`"),
                    (f"- FEM observable: {target.fem_observable}"),
                    (f"- Extraction source: {target.extraction_source}"),
                    (f"- Evidence artifact: `{evidence_artifact}`"),
                    f"- Notes: {target.notes}",
                )
            )
        )

    evidence_text = "\n\n".join(evidence_sections)

    return f"""# {definition.verification_id} Analytical-to-FEM Verification Matrix

## Purpose

This artifact defines the governed Phase 1 verification relationship between
the `{definition.analytical_joint_id}` analytical model and
`{definition.simulation_id}`.

A `pending` result is not a failed engineering check. It means that the
required accepted solver state, extractor or dedicated simulation is not yet
available.

An `inconclusive_solver` result means that a governed solver attempt was made,
but it produced no accepted equilibrium state suitable for analytical-to-FEM
comparison. It is neither a PASS nor a FAIL of the analytical prediction.

## Controlled model identity

| Field | Value |
|---|---|
| Verification ID | {definition.verification_id} |
| Analytical joint | {definition.analytical_joint_id} |
| FEM simulation | {definition.simulation_id} |
| Mesh level | {definition.mesh_level} |
| Element type | {definition.element_type} |
| Overall status | {result.overall_status.upper()} |
| Resolved targets | {result.resolved_target_count} |
| Unresolved targets | {result.unresolved_target_count} |

## Status summary

| Evidence status | Target count |
|---|---:|
| pass | {result.status_counts["pass"]} |
| fail | {result.status_counts["fail"]} |
| inconclusive solver | {result.status_counts["inconclusive_solver"]} |
| pending solver | {result.status_counts["pending_solver"]} |
| pending extractor | {result.status_counts["pending_extractor"]} |
| dedicated simulation required | {result.status_counts["dedicated_simulation_required"]} |

## Verification matrix

| Target | Quantity | Analytical value | Unit | Evidence status | Acceptance metric | Relative tolerance | Absolute tolerance |
|---|---|---:|---|---|---|---:|---:|
{matrix_table}

## Target evidence contracts

{evidence_text}

## Current fidelity statement

The analytical model is internally validated, but full analytical-to-FEM
verification is not yet established.

An `inconclusive_solver` classification records an attempted governed
simulation that produced no accepted equilibrium state suitable for
comparison. It does not validate or invalidate the analytical prediction.

PASS or FAIL classifications require matching FEM observables extracted from
accepted solver states. Targets without such evidence remain pending or
require dedicated simulations.
"""


def write_analytical_fem_verification_artifacts(
    root: Path,
    result: AnalyticalFemVerificationResult,
) -> tuple[Path, Path]:
    """Write governed JSON and Markdown artifacts."""

    json_path = root / result.definition.json_relative_path

    report_path = root / result.definition.report_relative_path

    json_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    report_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    json_path.write_text(
        json.dumps(
            result.to_payload(),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )

    report_path.write_text(
        render_analytical_fem_verification_markdown(result),
        encoding="utf-8",
        newline="\n",
    )

    return json_path, report_path
