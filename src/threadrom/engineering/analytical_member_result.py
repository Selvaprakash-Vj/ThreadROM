"""Governed results for parametric analytical member mechanics."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from threadrom.engineering.analytical_joint_input import (
    AnalyticalJointInput,
)
from threadrom.engineering.analytical_member_mechanics import (
    AnalyticalMemberMechanics,
    calculate_analytical_member_mechanics,
)
from threadrom.engineering.analytical_member_validation import (
    AnalyticalMemberMechanicsValidation,
    validate_analytical_member_mechanics,
)


@dataclass(frozen=True)
class AnalyticalMemberResult:
    """Governed member-mechanics result for one analytical joint."""

    joint_id: str
    mechanics: AnalyticalMemberMechanics
    validation: AnalyticalMemberMechanicsValidation

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


def evaluate_analytical_member(
    joint: AnalyticalJointInput,
) -> AnalyticalMemberResult:
    """Evaluate and validate member compression mechanics."""

    mechanics = calculate_analytical_member_mechanics(joint)

    validation = validate_analytical_member_mechanics(mechanics)

    validation.require_valid()

    return AnalyticalMemberResult(
        joint_id=joint.joint_id,
        mechanics=mechanics,
        validation=validation,
    )


def render_analytical_member_report(
    result: AnalyticalMemberResult,
) -> str:
    """Render one governed member-mechanics report."""

    mechanics = result.mechanics
    validation = result.validation

    validation_status = "PASS" if validation.passed else "FAIL"

    lines = [
        "# ThreadROM Analytical Member-Mechanics Report",
        "",
        "## Record information",
        "",
        f"- Analytical joint: {result.joint_id}",
        f"- Compression method: {mechanics.method}",
        *_compression_method_metadata(mechanics),
        "- Material behaviour: Linear elastic",
        f"- Physics validation: {validation_status}",
        "",
        "## Loading and stack geometry",
        "",
        "| Quantity | Value |",
        "|---|---:|",
        f"| Preload | {mechanics.preload_n:.9f} N |",
        (f"| Total member thickness | {mechanics.total_thickness_mm:.9f} mm |"),
        (f"| Minimum compression area | {mechanics.minimum_compression_area_mm2:.9f} mm2 |"),
        "",
        "## Member layers",
        "",
        (
            "| Layer | Material | Thickness | Hole diameter | "
            "Outer diameter | Area | Stress | Strain | "
            "Shortening | Compliance | Energy |"
        ),
        ("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"),
    ]

    for layer in mechanics.layers:
        lines.append(
            "| "
            f"{layer.layer_id} | "
            f"{layer.material_id} | "
            f"{layer.thickness_mm:.9f} mm | "
            f"{layer.clearance_hole_diameter_mm:.9f} mm | "
            f"{layer.outer_diameter_mm:.9f} mm | "
            f"{layer.compression_area_mm2:.9f} mm2 | "
            f"{layer.compressive_stress_mpa:.9f} MPa | "
            f"{layer.compressive_strain:.12e} | "
            f"{layer.shortening_mm:.12e} mm | "
            f"{layer.compliance_mm_per_n:.12e} mm/N | "
            f"{layer.strain_energy_n_mm:.12e} N mm |"
        )

    lines.extend(
        [
            "",
            "## Combined member response",
            "",
            "| Quantity | Value |",
            "|---|---:|",
            (f"| Total compliance | {mechanics.total_compliance_mm_per_n:.12e} mm/N |"),
            (f"| Axial stiffness | {mechanics.axial_stiffness_n_per_mm:.9f} N/mm |"),
            (f"| Total shortening | {mechanics.total_shortening_mm:.12e} mm |"),
            (f"| Elastic strain energy | {mechanics.total_strain_energy_n_mm:.12e} N mm |"),
            (
                "| Maximum layer compressive stress | "
                f"{mechanics.maximum_compressive_stress_mpa:.9f} MPa |"
            ),
            "",
            "## Bearing references",
            "",
            "| Quantity | Value |",
            "|---|---:|",
            (f"| Head-side bearing area | {mechanics.head_bearing_area_mm2:.9f} mm2 |"),
            (f"| Nut-side bearing area | {mechanics.nut_bearing_area_mm2:.9f} mm2 |"),
            (
                "| Head-side mean bearing pressure | "
                f"{mechanics.head_mean_bearing_pressure_mpa:.9f} MPa |"
            ),
            (
                "| Nut-side mean bearing pressure | "
                f"{mechanics.nut_mean_bearing_pressure_mpa:.9f} MPa |"
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
                "- Total member shortening must be compared using "
                "governed head-side and nut-side reference planes."
            ),
            (
                "- Member stiffness must use the same compressive force "
                "and relative displacement definitions."
            ),
            (
                "- Layer stress is an analytical area-average value, "
                "not a local FEM contact or notch stress."
            ),
            ("- Mean bearing pressure must be compared with a contact-area-weighted FEM pressure."),
            "",
            "## Current limitations",
            "",
            *_method_specific_limitations(mechanics),
            "- Local bearing deformation is excluded.",
            "- Member-interface contact compliance is excluded.",
            "- Interface opening, slip and friction are excluded.",
            "- Plasticity and manufacturing variation are excluded.",
            "",
        ]
    )

    return "\n".join(lines)


def _compression_method_metadata(
    mechanics: AnalyticalMemberMechanics,
) -> tuple[str, ...]:
    """Render metadata specific to the selected member model."""

    if mechanics.compression_cone_half_angle_deg is None:
        return ()

    return (f"- Compression-cone half-angle: {mechanics.compression_cone_half_angle_deg:.9f} deg",)


def _method_specific_limitations(
    mechanics: AnalyticalMemberMechanics,
) -> tuple[str, ...]:
    """Return limitations appropriate to the selected method."""

    if mechanics.compression_cone_half_angle_deg is not None:
        return (
            (
                "- Compression spreading follows ideal opposed "
                "annular frustums meeting at the stack midpoint."
            ),
            ("- Each cone is capped by the configured outer diameter of its current member layer."),
            (
                "- The cone model remains axisymmetric and "
                "excludes local three-dimensional contact effects."
            ),
        )

    return (
        (
            "- The uniform annular-cylinder method assumes "
            "constant compression area within each layer."
        ),
        ("- Compression spreading and cone interaction are excluded."),
    )
