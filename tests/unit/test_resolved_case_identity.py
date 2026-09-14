"""Tests exposing resolved-engineering identity on ResolvedCase."""

from threadrom.case.resolution_serialization import resolution_sha256
from threadrom.case.resolver import resolve_case
from threadrom.case.serialization import case_sha256
from tests.unit.test_case_resolver import _baseline_case


def test_resolved_case_exposes_resolution_hash() -> None:
    case = _baseline_case()
    resolved = resolve_case(case)

    assert resolved.resolution_hash == resolution_sha256(resolved)


def test_product_case_hash_semantics_remain_unchanged() -> None:
    case = _baseline_case()
    resolved = resolve_case(case)

    assert resolved.case_hash == case_sha256(case)
    assert resolved.resolution_hash != resolved.case_hash


def test_resolution_hash_is_stable_for_repeated_resolution() -> None:
    case = _baseline_case()

    first = resolve_case(case)
    second = resolve_case(case)

    assert first.case_hash == second.case_hash
    assert first.resolution_hash == second.resolution_hash
