"""Tests for deterministic resolved-engineering identity."""

from dataclasses import replace

from threadrom.case.resolution_serialization import resolution_sha256
from threadrom.case.resolver import resolve_case
from tests.unit.test_case_resolver import _baseline_case


def test_resolution_hash_is_deterministic() -> None:
    resolved = resolve_case(_baseline_case())

    first = resolution_sha256(resolved)
    second = resolution_sha256(resolved)

    assert first == second
    assert len(first) == 64
    int(first, 16)


def test_resolution_hash_is_distinct_from_product_case_hash() -> None:
    resolved = resolve_case(_baseline_case())

    assert resolution_sha256(resolved) != resolved.case_hash


def test_changed_resolved_dimension_changes_resolution_hash() -> None:
    resolved = resolve_case(_baseline_case())

    changed_nut = replace(
        resolved.nut_standard,
        thickness_mm=8.1,
    )
    changed = replace(
        resolved,
        nut_standard=changed_nut,
    )

    assert resolution_sha256(changed) != resolution_sha256(resolved)


def test_changed_dimension_evidence_changes_resolution_hash() -> None:
    resolved = resolve_case(_baseline_case())

    changed_evidence = replace(
        resolved.nut_standard.thickness_evidence,
        evidence_id="TRM-DIM-M10-999999",
    )
    changed_nut = replace(
        resolved.nut_standard,
        thickness_evidence=changed_evidence,
    )
    changed = replace(
        resolved,
        nut_standard=changed_nut,
    )

    assert resolution_sha256(changed) != resolution_sha256(resolved)


def test_changed_material_properties_change_resolution_hash() -> None:
    resolved = resolve_case(_baseline_case())

    changed_material = replace(
        resolved.bolt_material,
        youngs_modulus_mpa=205000.0,
    )
    changed = replace(
        resolved,
        bolt_material=changed_material,
    )

    assert resolution_sha256(changed) != resolution_sha256(resolved)


def test_changed_property_class_data_changes_resolution_hash() -> None:
    resolved = resolve_case(_baseline_case())

    changed_class = replace(
        resolved.bolt_property_class,
        proof_stress_mpa=575.0,
    )
    changed = replace(
        resolved,
        bolt_property_class=changed_class,
    )

    assert resolution_sha256(changed) != resolution_sha256(resolved)
