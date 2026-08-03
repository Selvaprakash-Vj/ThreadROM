"""Governed results for parametric analytical bolt mechanics."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from threadrom.engineering.analytical_bolt_mechanics import (
    AnalyticalBoltMechanics,
    calculate_analytical_bolt_mechanics,
)
from threadrom.engineering.analytical_bolt_validation import (
    AnalyticalBoltMechanicsValidation,
    validate_analytical_bolt_mechanics,
)
from threadrom.engineering.analytical_joint_input import (
    AnalyticalJointInput,
)


@dataclass(frozen=True)
class AnalyticalBoltResult:
    """Governed bolt-mechanics result for one analytical joint."""

    joint_id: str
    bolt_id: str
    mechanics: AnalyticalBoltMechanics
    validation: AnalyticalBoltMechanicsValidation

    def to_json(self) -> str:
        """Render deterministic machine-readable JSON."""

        payload = asdict(self)

        validation_payload = payload.get("validation")

        if not isinstance(validation_payload, dict):
            raise TypeError("Serialized validation payload must be a dictionary.")

        validation_payload["passed"] = self.validation.passed
        validation_payload["failed_check_ids"] = list(self.validation.failed_check_ids)

        return (
            json.dumps(
                payload,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )


def evaluate_analytical_bolt(
    joint: AnalyticalJointInput,
) -> AnalyticalBoltResult:
    """Evaluate and validate bolt axial mechanics."""

    mechanics = calculate_analytical_bolt_mechanics(joint)

    validation = validate_analytical_bolt_mechanics(mechanics)

    validation.require_valid()

    return AnalyticalBoltResult(
        joint_id=joint.joint_id,
        bolt_id=joint.bolt.bolt_id,
        mechanics=mechanics,
        validation=validation,
    )


def render_analytical_bolt_report(
    result: AnalyticalBoltResult,
) -> str:
    """Render one analytical bolt-mechanics report."""

    mechanics = result.mechanics
    validation = result.validation

    validation_status = "PASS" if validation.passed else "FAIL"

    lines = [
        "# ThreadROM Analytical Bolt-Mechanics Report",
        "",
        "## Record information",
        "",
        f"- Analytical joint: {result.joint_id}",
        f"- Bolt: {result.bolt_id}",
        f"- Compliance method: {mechanics.method}",
        "- Material behaviour: Linear elastic",
        f"- Physics validation: {validation_status}",
        "",
        "## Loading and effective geometry",
        "",
        "| Quantity | Value |",
        "|---|---:|",
        f"| Preload | {mechanics.preload_n:.9f} N |",
        (f"| Tensile-stress area | {mechanics.tensile_stress_area_mm2:.9f} mm2 |"),
        (f"| External-root area | {mechanics.external_root_area_mm2:.9f} mm2 |"),
        (f"| Head participation length | {mechanics.head_participation_length_mm:.9f} mm |"),
        (f"| Nut participation length | {mechanics.nut_participation_length_mm:.9f} mm |"),
        (f"| Total effective bolt length | {mechanics.effective_length_mm:.9f} mm |"),
        "",
        "## Effective axial segments",
        "",
        (
            "| Segment | Kind | Material | Length | Area | "
            "Stress | Strain | Elongation | Compliance | Energy |"
        ),
        ("|---|---|---|---:|---:|---:|---:|---:|---:|---:|"),
    ]

    for segment in mechanics.segments:
        lines.append(
            "| "
            f"{segment.segment_id} | "
            f"{segment.segment_kind} | "
            f"{segment.material_id} | "
            f"{segment.length_mm:.9f} mm | "
            f"{segment.area_mm2:.9f} mm2 | "
            f"{segment.axial_stress_mpa:.9f} MPa | "
            f"{segment.axial_strain:.12e} | "
            f"{segment.elongation_mm:.12e} mm | "
            f"{segment.compliance_mm_per_n:.12e} mm/N | "
            f"{segment.strain_energy_n_mm:.12e} N mm |"
        )

    lines.extend(
        [
            "",
            "## Combined axial response",
            "",
            "| Quantity | Value |",
            "|---|---:|",
            (f"| Total compliance | {mechanics.total_compliance_mm_per_n:.12e} mm/N |"),
            (f"| Axial stiffness | {mechanics.axial_stiffness_n_per_mm:.9f} N/mm |"),
            (f"| Total elongation | {mechanics.total_elongation_mm:.12e} mm |"),
            (f"| Elastic strain energy | {mechanics.total_strain_energy_n_mm:.12e} N mm |"),
            "",
            "## Stress and strength references",
            "",
            "| Quantity | Value |",
            "|---|---:|",
            (f"| Nominal tensile-area stress | {mechanics.nominal_tensile_stress_mpa:.9f} MPa |"),
            (
                "| Root-section reference stress | "
                f"{mechanics.root_section_reference_stress_mpa:.9f} MPa |"
            ),
            (
                "| Maximum effective-segment stress | "
                f"{mechanics.maximum_segment_stress_mpa:.9f} MPa |"
            ),
            (f"| Proof utilisation | {_optional_value(mechanics.proof_utilisation)} |"),
            (f"| Yield utilisation | {_optional_value(mechanics.yield_utilisation)} |"),
            (f"| Ultimate utilisation | {_optional_value(mechanics.ultimate_utilisation)} |"),
            "",
            "## Physics-consistency validation",
            "",
            f"- Method: {validation.method}",
            f"- Overall status: {validation_status}",
            "",
            "| Check | Status | Description |",
            "|---|---|---|",
        ]
    )

    for check in validation.checks:
        status = "PASS" if check.passed else "FAIL"

        lines.append(f"| {check.check_id} | {status} | {check.description} |")

    lines.extend(
        [
            "",
            "## FEM comparison targets",
            "",
            "- Bolt elongation must be compared with relative axial",
            "  displacement between governed bolt gauge planes.",
            "- Bolt stiffness must use the same force and displacement",
            "  definitions as the analytical result.",
            "- Nominal tensile-area stress must be compared with a",
            "  section-averaged axial FEM stress.",
            "- The root-section reference stress is not a prediction",
            "  of the local thread-root von Mises stress.",
            "",
            "## Current limitations",
            "",
            "- Head and nut participation are effective assumptions.",
            "- Thread bending and local contact compliance are excluded.",
            "- Tightening torsion is excluded.",
            "- Thread-root stress concentration is excluded.",
            "- Plasticity, fatigue and preload scatter are excluded.",
            "",
        ]
    )

    return "\n".join(lines)


def _optional_value(
    value: float | None,
) -> str:
    """Format one optional dimensionless result."""

    if value is None:
        return "not available"

    return f"{value:.9f}"
