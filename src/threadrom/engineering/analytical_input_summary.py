"""Human-readable summaries of canonical analytical inputs."""

from __future__ import annotations

from threadrom.engineering.analytical_joint_input import (
    AnalyticalJointInput,
)


def render_analytical_input_summary(
    joint: AnalyticalJointInput,
) -> str:
    """Render one canonical analytical joint definition as Markdown."""

    lines = [
        "# ThreadROM Analytical Joint Input Summary",
        "",
        "## Identity",
        "",
        f"- Analytical joint: {joint.joint_id}",
        "- Status: Governed analytical input",
        "",
        "## Thread definition",
        "",
        "| Quantity | Value |",
        "|---|---:|",
        (f"| Nominal diameter | {joint.thread.nominal_diameter_mm:.6f} mm |"),
        f"| Pitch | {joint.thread.pitch_mm:.6f} mm |",
        f"| Handedness | {joint.thread.handedness.value} |",
        f"| Starts | {joint.thread.starts} |",
        (f"| Included angle | {joint.thread.included_angle_deg:.6f} deg |"),
        (
            "| External tolerance class | "
            f"{joint.thread.external_tolerance_class or 'not specified'} |"
        ),
        (
            "| Internal tolerance class | "
            f"{joint.thread.internal_tolerance_class or 'not specified'} |"
        ),
        "",
        "## Bolt definition",
        "",
        f"- Bolt identity: {joint.bolt.bolt_id}",
        f"- Material identity: {joint.bolt.material_id}",
        (f"- Nominal length: {joint.bolt.nominal_length_mm:.6f} mm"),
        (f"- Explicit segment length: {joint.bolt.axial_segment_length_mm:.6f} mm"),
        (
            "- Head bearing ring: "
            f"{joint.bolt.head_bearing_inner_diameter_mm:.6f} to "
            f"{joint.bolt.head_bearing_outer_diameter_mm:.6f} mm"
        ),
        "",
        "### Bolt axial segments",
        "",
        "| Segment | Kind | Length | Diameter | Area | Material override |",
        "|---|---|---:|---:|---:|---|",
    ]

    for segment in joint.bolt.axial_segments:
        diameter = f"{segment.diameter_mm:.6f} mm" if segment.diameter_mm is not None else "derived"

        area = f"{segment.area_mm2:.6f} mm2" if segment.area_mm2 is not None else "derived"

        lines.append(
            "| "
            f"{segment.segment_id} | "
            f"{segment.kind.value} | "
            f"{segment.length_mm:.6f} mm | "
            f"{diameter} | "
            f"{area} | "
            f"{segment.material_id or 'bolt material'} |"
        )

    lines.extend(
        [
            "",
            "## Nut definition",
            "",
            f"- Nut identity: {joint.nut.nut_id}",
            f"- Material identity: {joint.nut.material_id}",
            f"- Thickness: {joint.nut.thickness_mm:.6f} mm",
            (f"- Thread engagement: {joint.nut.thread_engagement_length_mm:.6f} mm"),
            (f"- Nominal engaged pitches: {joint.engaged_thread_count:.6f}"),
            (
                "- Bearing ring: "
                f"{joint.nut.bearing_inner_diameter_mm:.6f} to "
                f"{joint.nut.bearing_outer_diameter_mm:.6f} mm"
            ),
            "",
            "## Clamped-member stack",
            "",
            f"- Total grip length: {joint.grip_length_mm:.6f} mm",
            f"- Number of layers: {len(joint.member_layers)}",
            "",
            "| Layer | Thickness | Material | Hole diameter | Outer diameter |",
            "|---|---:|---|---:|---:|",
        ]
    )

    for layer in joint.member_layers:
        lines.append(
            "| "
            f"{layer.layer_id} | "
            f"{layer.thickness_mm:.6f} mm | "
            f"{layer.material_id} | "
            f"{layer.clearance_hole_diameter_mm:.6f} mm | "
            f"{layer.outer_diameter_mm:.6f} mm |"
        )

    lines.extend(
        [
            "",
            "## Materials",
            "",
            "| Material | E | Poisson ratio | Proof | Yield | Ultimate |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )

    for material in joint.materials:
        proof = (
            f"{material.proof_stress_mpa:.6f} MPa"
            if material.proof_stress_mpa is not None
            else "not specified"
        )

        yield_strength = (
            f"{material.yield_strength_mpa:.6f} MPa"
            if material.yield_strength_mpa is not None
            else "not specified"
        )

        ultimate = (
            f"{material.ultimate_strength_mpa:.6f} MPa"
            if material.ultimate_strength_mpa is not None
            else "not specified"
        )

        lines.append(
            "| "
            f"{material.material_id} | "
            f"{material.youngs_modulus_mpa:.6f} MPa | "
            f"{material.poissons_ratio:.6f} | "
            f"{proof} | "
            f"{yield_strength} | "
            f"{ultimate} |"
        )

    lines.extend(
        [
            "",
            "## Loading",
            "",
            f"- Preload: {joint.loading.preload_n:.6f} N",
            (f"- External separating load: {joint.loading.external_axial_load_n:.6f} N"),
            (f"- Preload scatter fraction: {joint.loading.preload_scatter_fraction:.6f}"),
            "",
            "## Selected analytical methods",
            "",
            (f"- Bolt compliance: {joint.methods.bolt_compliance.value}"),
            (f"- Member compression: {joint.methods.member_compression.value}"),
            (f"- External-load treatment: {joint.methods.external_load.value}"),
            (f"- Thread-load distribution: {joint.methods.thread_load_distribution.value}"),
            (f"- Head participation factor: {joint.methods.head_participation_factor:.6f}"),
            (f"- Nut participation factor: {joint.methods.nut_participation_factor:.6f}"),
            (f"- Load-introduction factor: {joint.methods.load_introduction_factor:.6f}"),
            "",
            "## Scope",
            "",
            "This record contains canonical inputs and selected assumptions.",
            "It does not yet contain calculated analytical mechanics results.",
            "",
        ]
    )

    return "\n".join(lines)
