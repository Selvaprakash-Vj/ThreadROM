"""Tests for request identity versus resolved FEM execution identity."""

from dataclasses import replace

from threadrom.case.resolver import resolve_case
from threadrom.factory.fem_case_preparation import (
    derive_fem_case_preparation,
)
from tests.unit.test_case_resolver import _baseline_case


def test_fem_identity_preserves_request_and_resolution_hashes() -> None:
    resolved = resolve_case(_baseline_case())

    preparation = derive_fem_case_preparation(resolved)

    assert preparation.identity.case_hash == resolved.case_hash
    assert (
        preparation.identity.resolution_hash
        == resolved.resolution_hash
    )


def test_fem_run_identity_is_derived_from_resolution_hash() -> None:
    resolved = resolve_case(_baseline_case())

    preparation = derive_fem_case_preparation(resolved)

    assert preparation.identity.run_id == (
        f"trm_fem_{resolved.resolution_hash[:12]}"
    )
    assert preparation.identity.job_name == preparation.identity.run_id


def test_same_request_different_resolution_gets_different_run_id() -> None:
    resolved = resolve_case(_baseline_case())

    changed_evidence = replace(
        resolved.nut_standard.thickness_evidence,
        evidence_id="TRM-DIM-M10-ALT000",
    )
    changed_nut = replace(
        resolved.nut_standard,
        thickness_evidence=changed_evidence,
    )
    changed = replace(
        resolved,
        nut_standard=changed_nut,
    )

    assert changed.case_hash == resolved.case_hash
    assert changed.resolution_hash != resolved.resolution_hash

    original_preparation = derive_fem_case_preparation(resolved)
    changed_preparation = derive_fem_case_preparation(changed)

    assert (
        original_preparation.identity.case_hash
        == changed_preparation.identity.case_hash
    )
    assert (
        original_preparation.identity.resolution_hash
        != changed_preparation.identity.resolution_hash
    )
    assert (
        original_preparation.identity.run_id
        != changed_preparation.identity.run_id
    )
