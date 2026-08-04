"""Governed results for analytical thread-load distribution."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from threadrom.engineering.analytical_joint_input import (
    AnalyticalJointInput,
)
from threadrom.engineering.analytical_thread_distribution import (
    AnalyticalThreadLoadDistribution,
    calculate_thread_load_distribution,
)
from threadrom.engineering.analytical_thread_distribution_validation import (
    AnalyticalThreadDistributionValidation,
    validate_thread_load_distribution,
)


@dataclass(frozen=True)
class AnalyticalThreadDistributionResult:
    """Governed thread-load distribution and validation evidence."""

    joint_id: str
    distribution: AnalyticalThreadLoadDistribution
    validation: AnalyticalThreadDistributionValidation

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


def evaluate_analytical_thread_distribution(
    joint: AnalyticalJointInput,
    *,
    total_transferred_load_n: float | None = None,
) -> AnalyticalThreadDistributionResult:
    """Evaluate and validate one engaged-thread load distribution."""

    distribution = calculate_thread_load_distribution(
        joint,
        total_transferred_load_n=(total_transferred_load_n),
    )

    validation = validate_thread_load_distribution(distribution)

    validation.require_valid()

    return AnalyticalThreadDistributionResult(
        joint_id=joint.joint_id,
        distribution=distribution,
        validation=validation,
    )


def render_analytical_thread_distribution_report(
    result: AnalyticalThreadDistributionResult,
) -> str:
    """Render a governed thread-load distribution report."""

    distribution = result.distribution
    engagement = distribution.engagement
    stiffness = distribution.stiffness
    validation = result.validation

    validation_status = "PASS" if validation.passed else "FAIL"

    lines = [
        "# ThreadROM Analytical Thread-Load Distribution Report",
        "",
        "## Record information",
        "",
        f"- Analytical joint: {result.joint_id}",
        f"- Distribution method: {distribution.method}",
        (f"- Thread-stiffness method: {stiffness.method}"),
        (f"- Engagement discretization: {engagement.method}"),
        (f"- Boundary condition: {distribution.boundary_condition}"),
        f"- Physics validation: {validation_status}",
        "",
        "## Engagement convention",
        "",
        (f"- Axial origin: {engagement.axial_origin}"),
        (f"- Numbering direction: {engagement.numbering_direction}"),
        ("- Turn 1 is the engaged turn nearest the nut bearing face."),
        "",
        "| Quantity | Value |",
        "|---|---:|",
        (f"| Pitch | {engagement.pitch_mm:.9f} mm |"),
        (f"| Engagement length | {engagement.total_engagement_length_mm:.9f} mm |"),
        (f"| Nominal engaged pitches | {engagement.nominal_engaged_pitch_count:.12f} |"),
        (f"| Active discrete turns | {engagement.active_turn_count} |"),
        (f"| Complete turns | {engagement.complete_turn_count} |"),
        (f"| Final partial-turn fraction | {engagement.partial_turn_fraction:.12f} |"),
        "",
        "## Elastic transfer properties",
        "",
        "| Quantity | Value |",
        "|---|---:|",
        (f"| Bolt axial area | {stiffness.bolt_axial_area_mm2:.9f} mm2 |"),
        (f"| Nut axial area | {stiffness.nut_axial_area_mm2:.9f} mm2 |"),
        (
            "| Combined distributed thread stiffness | "
            f"{stiffness.combined_distributed_thread_stiffness_n_per_mm2:.9f} "
            "N/mm2 |"
        ),
        (f"| Transfer parameter | {stiffness.transfer_parameter_per_mm:.12f} 1/mm |"),
        (
            "| Characteristic transfer length | "
            f"{stiffness.characteristic_transfer_length_mm:.9f} mm |"
        ),
        (f"| Helix angle | {stiffness.helix_angle_deg:.9f} deg |"),
        (f"| Projection convention | {stiffness.projection_convention} |"),
        "",
        "## Per-turn load distribution",
        "",
        (
            "| Turn | Axial centroid | Engagement fraction | "
            "Spring stiffness | Turn load | Load share | "
            "Cumulative share | Remaining bolt force |"
        ),
        ("|---:|---:|---:|---:|---:|---:|---:|---:|"),
    ]

    for turn in distribution.turn_loads:
        lines.append(
            "| "
            f"{turn.turn_number} | "
            f"{turn.axial_centroid_mm:.9f} mm | "
            f"{turn.engagement_fraction:.12f} | "
            f"{turn.spring_stiffness_n_per_mm:.9f} N/mm | "
            f"{turn.load_n:.9f} N | "
            f"{100.0 * turn.load_share:.6f}% | "
            f"{100.0 * turn.cumulative_load_share:.6f}% | "
            f"{turn.remaining_bolt_force_n:.9f} N |"
        )

    lines.extend(
        [
            "",
            "## Governing distribution quantities",
            "",
            "| Quantity | Value |",
            "|---|---:|",
            (f"| Total transferred load | {distribution.total_transferred_load_n:.9f} N |"),
            (f"| First-turn load | {distribution.first_turn_load_n:.9f} N |"),
            (f"| First-turn load share | {100.0 * distribution.first_turn_load_share:.6f}% |"),
            (f"| Maximum-loaded turn | {distribution.maximum_loaded_turn_number} |"),
            (f"| Maximum turn load | {distribution.maximum_turn_load_n:.9f} N |"),
            (f"| Maximum turn load share | {100.0 * distribution.maximum_turn_load_share:.6f}% |"),
            (
                "| Final remaining bolt force | "
                f"{distribution.final_remaining_bolt_force_n:.12e} N |"
            ),
            (f"| Load-conservation error | {distribution.load_conservation_error_n:.12e} N |"),
            (f"| Nut-bearing reaction | {distribution.nut_bearing_reaction_n:.9f} N |"),
            (f"| Global-equilibrium error | {distribution.global_equilibrium_error_n:.12e} N |"),
            "",
            "## Physics-consistency validation",
            "",
            f"- Validation method: {validation.method}",
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
            (
                "- Compare the analytical load share of each turn "
                "against integrated normal contact force on matching "
                "bolt-nut flank pairs."
            ),
            (
                "- Compare the analytical first-turn share only after "
                "the FEM thread numbering and bearing-face origin have "
                "been confirmed."
            ),
            (
                "- Verify convergence of the first-turn share across "
                "coarse, medium and fine contact meshes."
            ),
            (
                "- Check whether the partial final turn exists in the "
                "FEM geometry before including it in the comparison."
            ),
            (
                "- Evaluate the selected helix projection convention "
                "against FEM and literature evidence during Checkpoint 8."
            ),
            "",
            "## Current limitations",
            "",
            (
                "- The model uses linear-elastic one-dimensional bolt "
                "and nut bars coupled by discrete axial springs."
            ),
            (
                "- Thread springs are concentrated at pitch-cell "
                "centroids rather than distributed continuously."
            ),
            (
                "- Local flank contact pressure, root bending stress, "
                "plasticity and contact opening are not resolved."
            ),
            (
                "- Manufacturing tolerances, pitch error, flank error "
                "and incomplete first-thread geometry are excluded."
            ),
            (
                "- Friction, tightening torsion and helical circumferential "
                "load variation are excluded."
            ),
            (
                "- The final partial turn is scaled by engaged axial "
                "length using the same local stiffness law."
            ),
            (
                "- The reported first-turn share is a provisional "
                "analytical prediction pending Checkpoint 8 verification."
            ),
            "",
        ]
    )

    return "\n".join(lines)
