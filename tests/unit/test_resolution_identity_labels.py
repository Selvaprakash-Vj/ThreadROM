"""Resolution identity must depend on engineering state, not derived labels."""

from dataclasses import replace

from threadrom.case.resolution_serialization import resolution_sha256
from threadrom.case.resolver import resolve_case
from tests.unit.test_case_resolver import _baseline_case


def test_assembly_label_does_not_change_resolution_hash() -> None:
    resolved = resolve_case(_baseline_case())

    relabelled_assembly = replace(
        resolved.assembly,
        assembly_id="completely-different-derived-label",
    )
    relabelled = replace(
        resolved,
        assembly=relabelled_assembly,
    )

    assert resolution_sha256(relabelled) == resolution_sha256(resolved)


def test_physical_assembly_change_does_change_resolution_hash() -> None:
    resolved = resolve_case(_baseline_case())

    changed_assembly = replace(
        resolved.assembly,
        outer_diameter_mm=31.0,
    )
    changed = replace(
        resolved,
        assembly=changed_assembly,
    )

    assert resolution_sha256(changed) != resolution_sha256(resolved)
