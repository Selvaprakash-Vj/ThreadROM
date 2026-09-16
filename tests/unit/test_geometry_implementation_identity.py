"""CAD implementation revisions must participate in geometry identity."""

from threadrom.case.resolver import resolve_case
from threadrom.factory.geometry_adapter import (
    build_geometry_definitions,
)
from threadrom.factory.geometry_identity import (
    bolt_geometry_payload,
    joint_geometry_bundle_payload,
)
from tests.unit.test_case_resolver import _baseline_case


EXPECTED_EXTERNAL_THREAD_REVISION = (
    "canonical_additive_external_thread_v2_physical_minor_core"
)


def test_bolt_geometry_identity_records_external_thread_implementation() -> None:
    resolved = resolve_case(
        _baseline_case()
    )

    payload = bolt_geometry_payload(
        resolved
    )

    assert payload["implementation"] == {
        "external_thread_construction": (
            EXPECTED_EXTERNAL_THREAD_REVISION
        ),
    }


def test_joint_bundle_identity_records_external_thread_implementation() -> None:
    resolved = resolve_case(
        _baseline_case()
    )

    geometry = build_geometry_definitions(
        resolved
    )

    payload = joint_geometry_bundle_payload(
        resolved,
        geometry,
    )

    assert payload["implementation"] == {
        "external_thread_construction": (
            EXPECTED_EXTERNAL_THREAD_REVISION
        ),
    }
