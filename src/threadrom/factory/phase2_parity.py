"""Certified Phase-2 parity gate for the Phase-3 case factory."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from threadrom.case.resolved_case import ResolvedCase
from threadrom.engineering.analytical_joint_loader import (
    load_analytical_joint_input,
)
from threadrom.engineering.baseline_assembly import (
    load_baseline_assembly,
)
from threadrom.factory.analytical_adapter import (
    build_analytical_joint_input,
)
from threadrom.factory.geometry_adapter import (
    build_geometry_definitions,
)
from threadrom.geometry.complete_nut import (
    load_complete_nut_definitions,
)
from threadrom.geometry.geometry_quality import (
    load_geometry_quality_policy,
)
from threadrom.geometry.threaded_shank import (
    load_threaded_shank_definitions,
)


@dataclass(frozen=True)
class Phase2ParityReport:
    """Result of comparing one resolved case with Phase-2 baseline."""

    passed: bool
    phase2_snapshot_sha256: str
    phase3_snapshot_sha256: str
    mismatches: tuple[str, ...]


def _material_payload(material: Any) -> dict[str, object]:
    """Return engineering properties while ignoring material identity."""

    return {
        "youngs_modulus_mpa": material.youngs_modulus_mpa,
        "poissons_ratio": material.poissons_ratio,
        "proof_stress_mpa": material.proof_stress_mpa,
        "yield_strength_mpa": material.yield_strength_mpa,
        "ultimate_strength_mpa": material.ultimate_strength_mpa,
    }


def _analytical_payload(definition: Any) -> dict[str, object]:
    """Return identity-neutral analytical engineering data."""

    bolt_material = definition.material_by_id(
        definition.bolt.material_id
    )
    nut_material = definition.material_by_id(
        definition.nut.material_id
    )

    member_layers = []

    for layer in definition.member_layers:
        material = definition.material_by_id(layer.material_id)

        member_layers.append(
            {
                "layer_id": layer.layer_id,
                "thickness_mm": layer.thickness_mm,
                "clearance_hole_diameter_mm": (
                    layer.clearance_hole_diameter_mm
                ),
                "outer_diameter_mm": layer.outer_diameter_mm,
                "material": _material_payload(material),
            }
        )

    return {
        "thread": {
            "nominal_diameter_mm": (
                definition.thread.nominal_diameter_mm
            ),
            "pitch_mm": definition.thread.pitch_mm,
            "handedness": definition.thread.handedness.value,
            "starts": definition.thread.starts,
            "included_angle_deg": (
                definition.thread.included_angle_deg
            ),
            "external_tolerance_class": (
                definition.thread.external_tolerance_class
            ),
            "internal_tolerance_class": (
                definition.thread.internal_tolerance_class
            ),
        },
        "bolt": {
            "nominal_length_mm": (
                definition.bolt.nominal_length_mm
            ),
            "head_bearing_outer_diameter_mm": (
                definition.bolt.head_bearing_outer_diameter_mm
            ),
            "head_bearing_inner_diameter_mm": (
                definition.bolt.head_bearing_inner_diameter_mm
            ),
            "axial_segments": [
                {
                    "segment_id": segment.segment_id,
                    "kind": segment.kind.value,
                    "length_mm": segment.length_mm,
                    "diameter_mm": segment.diameter_mm,
                    "area_mm2": segment.area_mm2,
                }
                for segment in definition.bolt.axial_segments
            ],
            "material": _material_payload(bolt_material),
        },
        "nut": {
            "thickness_mm": definition.nut.thickness_mm,
            "thread_engagement_length_mm": (
                definition.nut.thread_engagement_length_mm
            ),
            "bearing_outer_diameter_mm": (
                definition.nut.bearing_outer_diameter_mm
            ),
            "bearing_inner_diameter_mm": (
                definition.nut.bearing_inner_diameter_mm
            ),
            "material": _material_payload(nut_material),
        },
        "member_layers": member_layers,
        "loading": {
            "preload_n": definition.loading.preload_n,
            "external_axial_load_n": (
                definition.loading.external_axial_load_n
            ),
            "preload_scatter_fraction": (
                definition.loading.preload_scatter_fraction
            ),
        },
        "methods": {
            "bolt_compliance": (
                definition.methods.bolt_compliance.value
            ),
            "member_compression": (
                definition.methods.member_compression.value
            ),
            "external_load": (
                definition.methods.external_load.value
            ),
            "thread_load_distribution": (
                definition.methods.thread_load_distribution.value
            ),
            "head_participation_factor": (
                definition.methods.head_participation_factor
            ),
            "nut_participation_factor": (
                definition.methods.nut_participation_factor
            ),
            "load_introduction_factor": (
                definition.methods.load_introduction_factor
            ),
            "compression_cone_half_angle_deg": (
                definition.methods.compression_cone_half_angle_deg
            ),
        },
    }


def _assembly_payload(definition: Any) -> dict[str, object]:
    """Return complete-joint placement and member dimensions."""

    return {
        "upper_member_thickness_mm": (
            definition.upper_member_thickness_mm
        ),
        "lower_member_thickness_mm": (
            definition.lower_member_thickness_mm
        ),
        "total_grip_length_mm": (
            definition.total_grip_length_mm
        ),
        "clearance_hole_diameter_mm": (
            definition.clearance_hole_diameter_mm
        ),
        "outer_diameter_mm": definition.outer_diameter_mm,
        "nut_translation_z_mm": (
            definition.nut_translation_z_mm
        ),
    }


def _geometry_payload(
    bolt_blank: Any,
    external_thread: Any,
    nut_blank: Any,
    internal_thread: Any,
    quality_policy: Any,
    assembly: Any,
    mating_clearance_mm: float,
    mating_phase_offset_deg: float,
) -> dict[str, object]:
    """Return identity-neutral CAD-definition engineering data."""

    return {
        "assembly": _assembly_payload(assembly),
        "mating": {
            "clearance_mm": mating_clearance_mm,
            "phase_offset_deg": mating_phase_offset_deg,
        },
        "bolt_blank": {
            "nominal_diameter_mm": (
                bolt_blank.nominal_diameter_mm
            ),
            "underhead_length_mm": (
                bolt_blank.underhead_length_mm
            ),
            "head_across_flats_mm": (
                bolt_blank.head_across_flats_mm
            ),
            "head_height_mm": bolt_blank.head_height_mm,
        },
        "external_thread": {
            "nominal_diameter_mm": (
                external_thread.nominal_diameter_mm
            ),
            "pitch_mm": external_thread.pitch_mm,
            "minor_diameter_mm": (
                external_thread.minor_diameter_mm
            ),
            "thread_length_mm": (
                external_thread.thread_length_mm
            ),
            "overshoot_pitches": (
                external_thread.overshoot_pitches
            ),
            "radial_clearance_mm": (
                external_thread.radial_clearance_mm
            ),
            "handedness": external_thread.handedness,
            "use_frenet_frame": (
                external_thread.use_frenet_frame
            ),
        },
        "nut_blank": {
            "nominal_diameter_mm": (
                nut_blank.nominal_diameter_mm
            ),
            "pitch_mm": nut_blank.pitch_mm,
            "across_flats_mm": nut_blank.across_flats_mm,
            "thickness_mm": nut_blank.thickness_mm,
            "bore_diameter_mm": nut_blank.bore_diameter_mm,
            "bore_basis": nut_blank.bore_basis,
            "chamfer_included": nut_blank.chamfer_included,
        },
        "internal_thread": {
            "nominal_diameter_mm": (
                internal_thread.nominal_diameter_mm
            ),
            "pitch_mm": internal_thread.pitch_mm,
            "minor_diameter_mm": (
                internal_thread.minor_diameter_mm
            ),
            "thread_length_mm": (
                internal_thread.thread_length_mm
            ),
            "handedness": internal_thread.handedness,
            "use_frenet_frame": (
                internal_thread.use_frenet_frame
            ),
        },
        "quality_policy": {
            "boolean_tolerance_mm": (
                quality_policy.boolean_tolerance_mm
            ),
            "thread_boolean_overlap_mm": (
                quality_policy.thread_boolean_overlap_mm
            ),
            "fusion_bridge_half_height_mm": (
                quality_policy.fusion_bridge_half_height_mm
            ),
            "fusion_bridge_radius_fraction": (
                quality_policy.fusion_bridge_radius_fraction
            ),
            "cad_envelope_tolerance_mm": (
                quality_policy.cad_envelope_tolerance_mm
            ),
            "step_bounds_tolerance_mm": (
                quality_policy.step_bounds_tolerance_mm
            ),
            "step_volume_relative_tolerance": (
                quality_policy.step_volume_relative_tolerance
            ),
        },
    }


def _snapshot_sha256(payload: dict[str, object]) -> str:
    """Return deterministic SHA-256 for one normalized snapshot."""

    serialized = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")

    return hashlib.sha256(serialized).hexdigest()


def _collect_mismatches(
    expected: Any,
    actual: Any,
    *,
    path: str = "",
) -> list[str]:
    """Collect deterministic human-readable mismatch paths."""

    if isinstance(expected, dict) and isinstance(actual, dict):
        mismatches: list[str] = []

        keys = sorted(set(expected) | set(actual))

        for key in keys:
            child_path = f"{path}.{key}" if path else key

            if key not in expected:
                mismatches.append(
                    f"{child_path}: unexpected Phase-3 value"
                )
                continue

            if key not in actual:
                mismatches.append(
                    f"{child_path}: missing Phase-3 value"
                )
                continue

            mismatches.extend(
                _collect_mismatches(
                    expected[key],
                    actual[key],
                    path=child_path,
                )
            )

        return mismatches

    if isinstance(expected, list) and isinstance(actual, list):
        mismatches = []

        if len(expected) != len(actual):
            mismatches.append(
                f"{path}: expected {len(expected)} items, "
                f"got {len(actual)}"
            )
            return mismatches

        for index, (left, right) in enumerate(
            zip(expected, actual, strict=True)
        ):
            mismatches.extend(
                _collect_mismatches(
                    left,
                    right,
                    path=f"{path}[{index}]",
                )
            )

        return mismatches

    if expected != actual:
        return [
            f"{path}: Phase-2={expected!r}, Phase-3={actual!r}"
        ]

    return []


def evaluate_phase2_parity(
    resolved: ResolvedCase,
    project_root: Path,
) -> Phase2ParityReport:
    """Compare Phase-3 factory output with certified Phase-2 inputs."""

    phase3_analytical = build_analytical_joint_input(resolved)
    phase3_geometry = build_geometry_definitions(resolved)

    phase2_analytical = load_analytical_joint_input(
        project_root / "config" / "analytical_m10_20kn.toml"
    )

    phase2_bolt_blank, phase2_external_thread = (
        load_threaded_shank_definitions(project_root)
    )

    phase2_nut_blank, phase2_internal_thread = (
        load_complete_nut_definitions(project_root)
    )

    phase2_quality = load_geometry_quality_policy(
        project_root / "config" / "geometry_quality.toml"
    )

    phase2_assembly = load_baseline_assembly(
        project_root / "config" / "baseline_assembly.toml"
    )

    phase2_payload = {
        "analytical": _analytical_payload(phase2_analytical),
        "geometry": _geometry_payload(
            phase2_bolt_blank,
            phase2_external_thread,
            phase2_nut_blank,
            phase2_internal_thread,
            phase2_quality,
            phase2_assembly,
            0.0,
            0.0,
        ),
    }

    phase3_payload = {
        "analytical": _analytical_payload(phase3_analytical),
        "geometry": _geometry_payload(
            phase3_geometry.bolt_blank,
            phase3_geometry.external_thread,
            phase3_geometry.nut_blank,
            phase3_geometry.internal_thread,
            phase3_geometry.quality_policy,
            resolved.assembly,
            phase3_geometry.mating_clearance_mm,
            phase3_geometry.mating_phase_offset_deg,
        ),
    }

    mismatches = tuple(
        _collect_mismatches(
            phase2_payload,
            phase3_payload,
        )
    )

    return Phase2ParityReport(
        passed=not mismatches,
        phase2_snapshot_sha256=_snapshot_sha256(
            phase2_payload
        ),
        phase3_snapshot_sha256=_snapshot_sha256(
            phase3_payload
        ),
        mismatches=mismatches,
    )
