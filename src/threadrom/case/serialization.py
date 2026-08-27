"""Deterministic serialization and fingerprinting of ThreadROM cases."""

from __future__ import annotations

import hashlib
import json

from threadrom.case.contract import ThreadROMCase


def canonical_case_payload(case: ThreadROMCase) -> dict[str, object]:
    """Return the canonical engineering payload for one case.

    Human-facing metadata is intentionally excluded from engineering
    identity. Member order is preserved because stack order may matter.
    """

    return {
        "schema_version": int(case.schema_version),
        "fastener": {
            "bolt_standard": case.fastener.bolt_standard,
            "thread_designation": case.fastener.thread_designation,
            "bolt_length_mm": float(case.fastener.bolt_length_mm),
            "bolt_material_id": case.fastener.bolt_material_id,
            "bolt_property_class": case.fastener.bolt_property_class,
            "nut_standard": case.fastener.nut_standard,
            "nut_material_id": case.fastener.nut_material_id,
            "nut_property_class": case.fastener.nut_property_class,
            "handedness": case.fastener.handedness.value,
            "starts": int(case.fastener.starts),
        },
        "members": {
            "layers": [
                {
                    "layer_id": layer.layer_id,
                    "thickness_mm": float(layer.thickness_mm),
                    "material_id": layer.material_id,
                    "outer_diameter_mm": float(
                        layer.outer_diameter_mm
                    ),
                    "clearance_hole_diameter_mm": float(
                        layer.clearance_hole_diameter_mm
                    ),
                }
                for layer in case.members.layers
            ]
        },
        "interfaces": {
            "thread_friction_coefficient": float(
                case.interfaces.thread_friction_coefficient
            ),
            "head_bearing_friction_coefficient": float(
                case.interfaces.head_bearing_friction_coefficient
            ),
            "nut_bearing_friction_coefficient": float(
                case.interfaces.nut_bearing_friction_coefficient
            ),
            "member_interface_friction_coefficient": float(
                case.interfaces.member_interface_friction_coefficient
            ),
        },
        "loading": {
            "target_preload_n": float(
                case.loading.target_preload_n
            ),
            "external_axial_load_n": float(
                case.loading.external_axial_load_n
            ),
        },
        "analysis": {
            "calculation_mode": case.analysis.calculation_mode.value,
            "fidelity": case.analysis.fidelity.value,
        },
    }


def canonical_case_json(case: ThreadROMCase) -> str:
    """Serialize one case into stable canonical JSON."""

    return json.dumps(
        canonical_case_payload(case),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def case_sha256(case: ThreadROMCase) -> str:
    """Return the SHA-256 engineering fingerprint of one case."""

    payload = canonical_case_json(case).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
