"""Governed thread-mechanics results for analytical joints."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from threadrom.engineering.analytical_joint_input import (
    AnalyticalJointInput,
)
from threadrom.engineering.metric_thread_mechanics import (
    MetricThreadMechanics,
    calculate_metric_thread_mechanics,
)
from threadrom.engineering.metric_thread_validation import (
    MetricThreadMechanicsValidation,
    validate_metric_thread_mechanics,
)


@dataclass(frozen=True)
class AnalyticalThreadResult:
    """Resolved thread-mechanics result for one analytical joint."""

    joint_id: str
    bolt_id: str
    nut_id: str
    external_tolerance_class: str | None
    internal_tolerance_class: str | None
    mechanics: MetricThreadMechanics
    validation: MetricThreadMechanicsValidation

    def to_json(self) -> str:
        """Render the result as deterministic JSON."""

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


def evaluate_analytical_thread(
    joint: AnalyticalJointInput,
) -> AnalyticalThreadResult:
    """Evaluate and validate parametric thread mechanics."""

    mechanics = calculate_metric_thread_mechanics(
        joint.thread,
        engagement_length_mm=(joint.nut.thread_engagement_length_mm),
    )

    validation = validate_metric_thread_mechanics(mechanics)

    validation.require_valid()

    return AnalyticalThreadResult(
        joint_id=joint.joint_id,
        bolt_id=joint.bolt.bolt_id,
        nut_id=joint.nut.nut_id,
        external_tolerance_class=(joint.thread.external_tolerance_class),
        internal_tolerance_class=(joint.thread.internal_tolerance_class),
        mechanics=mechanics,
        validation=validation,
    )


def render_analytical_thread_report(
    result: AnalyticalThreadResult,
) -> str:
    """Render one thread-mechanics result as Markdown."""

    mechanics = result.mechanics
    validation = result.validation

    validation_status = "PASS" if validation.passed else "FAIL"

    lines = [
        "# ThreadROM Analytical Thread-Mechanics Report",
        "",
        "## Record information",
        "",
        f"- Analytical joint: {result.joint_id}",
        f"- Bolt: {result.bolt_id}",
        f"- Nut: {result.nut_id}",
        f"- Method: {mechanics.method}",
        "- Status: Governed analytical result",
        f"- Physics validation: {validation_status}",
        "",
        "## Thread definition",
        "",
        "| Quantity | Value |",
        "|---|---:|",
        (f"| Nominal diameter | {mechanics.nominal_diameter_mm:.9f} mm |"),
        f"| Pitch | {mechanics.pitch_mm:.9f} mm |",
        f"| Starts | {mechanics.starts} |",
        f"| Lead | {mechanics.lead_mm:.9f} mm |",
        (f"| Included angle | {mechanics.included_angle_deg:.9f} deg |"),
        (f"| Flank half-angle | {mechanics.flank_half_angle_deg:.9f} deg |"),
        (f"| External tolerance class | {result.external_tolerance_class or 'not specified'} |"),
        (f"| Internal tolerance class | {result.internal_tolerance_class or 'not specified'} |"),
        "",
        "## Basic ISO metric dimensions",
        "",
        "| Quantity | Value |",
        "|---|---:|",
        (f"| Fundamental triangle height | {mechanics.fundamental_triangle_height_mm:.9f} mm |"),
        (f"| Basic pitch diameter | {mechanics.basic_pitch_diameter_mm:.9f} mm |"),
        (
            "| Basic internal minor diameter | "
            f"{mechanics.basic_internal_minor_diameter_mm:.9f} mm |"
        ),
        (
            "| Basic external minor diameter | "
            f"{mechanics.basic_external_minor_diameter_mm:.9f} mm |"
        ),
        (f"| External radial thread depth | {mechanics.external_thread_radial_depth_mm:.9f} mm |"),
        (f"| Internal radial thread depth | {mechanics.internal_thread_radial_depth_mm:.9f} mm |"),
        "",
        "## Cross-sectional properties",
        "",
        "| Quantity | Value |",
        "|---|---:|",
        (f"| Nominal shank area | {mechanics.nominal_area_mm2:.9f} mm2 |"),
        (f"| Pitch-diameter area | {mechanics.pitch_diameter_area_mm2:.9f} mm2 |"),
        (f"| Tensile-stress area | {mechanics.tensile_stress_area_mm2:.9f} mm2 |"),
        (f"| External-root area | {mechanics.external_root_area_mm2:.9f} mm2 |"),
        (f"| Tensile-to-nominal area ratio | {mechanics.tensile_to_nominal_area_ratio:.9f} |"),
        (f"| Root-to-nominal area ratio | {mechanics.root_to_nominal_area_ratio:.9f} |"),
        "",
        "## Engagement and helix",
        "",
        "| Quantity | Value |",
        "|---|---:|",
        (f"| Engagement length | {mechanics.engagement_length_mm:.9f} mm |"),
        (f"| Engaged pitch count | {mechanics.engaged_pitch_count:.9f} |"),
        (f"| Engaged lead-turn count | {mechanics.engaged_lead_turn_count:.9f} |"),
        (
            "| Helix angle at pitch diameter | "
            f"{mechanics.helix_angle_at_pitch_diameter_deg:.9f} deg |"
        ),
        "",
        "## Physics-consistency validation",
        "",
        f"- Method: {validation.method}",
        f"- Overall status: {validation_status}",
        "",
        "| Check | Status | Description |",
        "|---|---|---|",
    ]

    for check in validation.checks:
        status = "PASS" if check.passed else "FAIL"

        lines.append(f"| {check.check_id} | {status} | {check.description} |")

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "The reported dimensions use the ideal 60-degree ISO metric",
            "basic profile. Tolerance classes are retained as governed",
            "metadata but are not yet applied as dimensional deviations.",
            "",
            "The tensile-stress area is intended for nominal axial stress",
            "and threaded-segment compliance calculations.",
            "",
            "The external-root area is a geometric root-section reference.",
            "It is not a substitute for a thread-root stress-concentration",
            "or local notch-stress calculation.",
            "",
            "The engaged pitch count can be non-integer because the input",
            "engagement length is treated as a continuous geometric value.",
            "",
            "## Current limitations",
            "",
            "- Tolerance deviations are not yet resolved.",
            "- Manufacturing truncation variation is not included.",
            "- Root radius and thread runout are not included.",
            "- Thread shear and stripping areas are not yet calculated.",
            "- Per-thread load distribution is handled in Checkpoint 7.",
            "",
        ]
    )

    return "\n".join(lines)
