"""Governed results for complete analytical joint behaviour."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from threadrom.engineering.analytical_joint_envelope import (
    AnalyticalJointEnvelope,
    ExternalLoadCase,
    JointEnvelopePoint,
    PreloadCase,
    calculate_analytical_joint_envelope,
)
from threadrom.engineering.analytical_joint_input import (
    AnalyticalJointInput,
)
from threadrom.engineering.analytical_joint_strength import (
    AnalyticalJointStrengthEnvelope,
    calculate_analytical_joint_strength,
)
from threadrom.engineering.analytical_joint_validation import (
    AnalyticalJointBehaviourValidation,
    validate_analytical_joint_behaviour,
)


@dataclass(frozen=True)
class AnalyticalJointResult:
    """Governed complete-joint result for one analytical joint."""

    joint_id: str
    envelope: AnalyticalJointEnvelope
    strength: AnalyticalJointStrengthEnvelope
    validation: AnalyticalJointBehaviourValidation

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


def evaluate_analytical_joint(
    joint: AnalyticalJointInput,
) -> AnalyticalJointResult:
    """Evaluate and validate complete axial joint behaviour."""

    envelope = calculate_analytical_joint_envelope(joint)

    strength = calculate_analytical_joint_strength(
        joint,
        envelope=envelope,
    )

    validation = validate_analytical_joint_behaviour(
        envelope,
        strength,
    )

    validation.require_valid()

    return AnalyticalJointResult(
        joint_id=joint.joint_id,
        envelope=envelope,
        strength=strength,
        validation=validation,
    )


def render_analytical_joint_report(
    result: AnalyticalJointResult,
) -> str:
    """Render one governed complete-joint report."""

    envelope = result.envelope
    strength = result.strength
    validation = result.validation

    nominal_static_point = _nominal_static_point(envelope)

    nominal_state = nominal_static_point.state

    validation_status = "PASS" if validation.passed else "FAIL"

    separation_status = "YES" if envelope.any_separation else "NO"

    lines = [
        "# ThreadROM Analytical Joint-Behaviour Report",
        "",
        "## Record information",
        "",
        f"- Analytical joint: {result.joint_id}",
        (f"- External-load method: {nominal_state.method}"),
        "- Joint model: Piecewise linear two-spring model",
        "- Material behaviour: Linear elastic",
        f"- Physics validation: {validation_status}",
        "",
        "## Stiffness and load sharing",
        "",
        "| Quantity | Value |",
        "|---|---:|",
        (f"| Bolt stiffness | {nominal_state.bolt_stiffness_n_per_mm:.9f} N/mm |"),
        (f"| Member stiffness | {nominal_state.member_stiffness_n_per_mm:.9f} N/mm |"),
        (f"| Basic bolt-load fraction | {nominal_state.basic_load_fraction:.12f} |"),
        (f"| Load-introduction factor | {nominal_state.load_introduction_factor:.12f} |"),
        (f"| Effective bolt-load fraction | {nominal_state.effective_load_fraction:.12f} |"),
        (f"| Nominal separation load | {nominal_state.separation_load_n:.9f} N |"),
        "",
        "## Preload envelope",
        "",
        "| Quantity | Value |",
        "|---|---:|",
        (f"| Preload scatter fraction | {envelope.preload_scatter_fraction:.12f} |"),
        (f"| Minimum preload | {envelope.minimum_preload_n:.9f} N |"),
        (f"| Nominal preload | {envelope.nominal_preload_n:.9f} N |"),
        (f"| Maximum preload | {envelope.maximum_preload_n:.9f} N |"),
        "",
        "## Evaluated joint states",
        "",
        (
            "| Point | Preload case | External-load case | "
            "Preload | External load | Regime | Bolt force | "
            "Member compression | Separation margin | Opening |"
        ),
        ("|---|---|---|---:|---:|---|---:|---:|---:|---:|"),
    ]

    for point in envelope.points:
        state = point.state

        lines.append(
            "| "
            f"{point.point_id} | "
            f"{point.preload_case.value} | "
            f"{point.external_load_case.value} | "
            f"{state.preload_n:.9f} N | "
            f"{state.external_axial_load_n:.9f} N | "
            f"{state.regime.value} | "
            f"{state.bolt_force_n:.9f} N | "
            f"{state.member_compression_force_n:.9f} N | "
            f"{state.separation_margin_n:.9f} N | "
            f"{state.joint_opening_mm:.12e} mm |"
        )

    lines.extend(
        [
            "",
            "## Envelope extrema",
            "",
            "| Quantity | Value |",
            "|---|---:|",
            (f"| Highest bolt force | {envelope.highest_bolt_force_n:.9f} N |"),
            (f"| Lowest member compression | {envelope.lowest_member_compression_force_n:.9f} N |"),
            (f"| Minimum separation margin | {envelope.minimum_separation_margin_n:.9f} N |"),
            (f"| Maximum joint opening | {envelope.maximum_joint_opening_mm:.12e} mm |"),
            (f"| Separation in configured envelope | {separation_status} |"),
            "",
            "## Cyclic response",
            "",
        ]
    )

    if envelope.cyclic_responses:
        lines.extend(
            [
                (
                    "| Preload case | Bolt minimum | Bolt maximum | "
                    "Bolt mean | Bolt amplitude | Bolt range | "
                    "Member minimum | Separation | Maximum opening |"
                ),
                ("|---|---:|---:|---:|---:|---:|---:|---|---:|"),
            ]
        )

        for response in envelope.cyclic_responses:
            separated = "YES" if response.separated_during_cycle else "NO"

            lines.append(
                "| "
                f"{response.preload_case.value} | "
                f"{response.bolt_force_minimum_n:.9f} N | "
                f"{response.bolt_force_maximum_n:.9f} N | "
                f"{response.bolt_force_mean_n:.9f} N | "
                f"{response.bolt_force_amplitude_n:.9f} N | "
                f"{response.bolt_force_range_n:.9f} N | "
                f"{response.member_compression_minimum_n:.9f} N | "
                f"{separated} | "
                f"{response.maximum_joint_opening_mm:.12e} mm |"
            )
    else:
        lines.append("No cyclic external-load range is configured.")

    lines.extend(
        [
            "",
            "## Governing bolt-strength references",
            "",
            "| Quantity | Value |",
            "|---|---:|",
            (f"| Governing envelope point | {strength.governing_point_id} |"),
            (f"| Highest bolt force | {strength.highest_bolt_force_n:.9f} N |"),
            (f"| Tensile-stress area | {strength.tensile_stress_area_mm2:.9f} mm2 |"),
            (f"| External-root area | {strength.external_root_area_mm2:.9f} mm2 |"),
            (
                "| Highest nominal tensile stress | "
                f"{strength.highest_nominal_tensile_stress_mpa:.9f} MPa |"
            ),
            (
                "| Highest root-section reference stress | "
                f"{strength.highest_root_section_reference_stress_mpa:.9f} MPa |"
            ),
            (f"| Proof utilisation | {_optional_value(strength.proof_utilisation)} |"),
            (f"| Yield utilisation | {_optional_value(strength.yield_utilisation)} |"),
            (f"| Ultimate utilisation | {_optional_value(strength.ultimate_utilisation)} |"),
            (
                "| Maximum nominal cyclic-stress amplitude | "
                f"{_optional_value(strength.maximum_nominal_stress_amplitude_mpa)} |"
            ),
            (
                "| Maximum root-reference stress amplitude | "
                f"{_optional_value(strength.maximum_root_reference_stress_amplitude_mpa)} |"
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
                "- Bolt and member stiffnesses must be compared "
                "using matching force and displacement definitions."
            ),
            (
                "- The pre-separation bolt-force slope must be "
                "compared with the FEM bolt-force response."
            ),
            (
                "- The analytical separation load must be compared "
                "with the first governed loss of interface compression."
            ),
            (
                "- Post-separation opening must use governed member "
                "reference planes rather than a single nodal displacement."
            ),
            ("- Section stresses must be compared with section-averaged axial FEM stresses."),
            "",
            "## Current limitations",
            "",
            ("- The model is axial, linear elastic and quasi-static."),
            (
                "- Before separation, external load is shared through "
                "the selected two-spring load fraction."
            ),
            (
                "- After separation, the bolt is assumed to carry "
                "the full separating load and member compression is zero."
            ),
            (
                "- Bending, shear, prying, transverse slip and "
                "frictional load transfer are excluded."
            ),
            (
                "- The root-section value is a reference stress, "
                "not a local thread-root notch stress."
            ),
            ("- Cyclic stress amplitudes are reference quantities; fatigue life is not evaluated."),
            ("- Preload scatter is represented as symmetric bounds around the nominal preload."),
            "",
        ]
    )

    return "\n".join(lines)


def _nominal_static_point(
    envelope: AnalyticalJointEnvelope,
) -> JointEnvelopePoint:
    """Return the nominal-preload static-load point."""

    for point in envelope.points:
        if (
            point.preload_case is PreloadCase.NOMINAL
            and point.external_load_case is ExternalLoadCase.STATIC
        ):
            return point

    raise ValueError("Joint envelope lacks a nominal static point.")


def _optional_value(
    value: float | None,
) -> str:
    """Render one optional numerical result."""

    if value is None:
        return "not available"

    return f"{value:.12f}"
