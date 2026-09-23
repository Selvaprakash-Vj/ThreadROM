"""Pinned-path and evidence tests for campaign preparation scope."""

import hashlib
from pathlib import Path

import pytest

from threadrom.factory.governed_fem_preparation_scope import (
    verify_governed_preparation_scope,
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _inputs(tmp_path):
    campaign = tmp_path / "campaign"
    campaign.mkdir()

    config = tmp_path / "config"
    config.mkdir()

    policy = config / "policy.toml"
    manifest = campaign / "manifest.json"
    anchor = campaign / "anchor.json"

    policy.write_bytes(b"independently-pinned-policy")
    manifest.write_bytes(b"independently-pinned-manifest")
    anchor.write_bytes(b"independently-pinned-anchor")

    return {
        "repo_root": tmp_path,
        "campaign_root": campaign,
        "artifact_root": campaign / "prepared_cases",
        "policy_path": policy,
        "manifest_path": manifest,
        "expected_policy_sha256": _sha(policy.read_bytes()),
        "expected_manifest_sha256": _sha(manifest.read_bytes()),
        "anchor_binding_path": anchor,
        "expected_anchor_binding_sha256": _sha(
            anchor.read_bytes()
        ),
    }


def test_valid_pinned_scope(tmp_path):
    params = _inputs(tmp_path)

    scope = verify_governed_preparation_scope(**params)

    assert scope.campaign_root == params["campaign_root"]
    assert scope.artifact_root == params["artifact_root"]
    assert (
        scope.policy_sha256
        == params["expected_policy_sha256"]
    )
    assert (
        scope.campaign_manifest_sha256
        == params["expected_manifest_sha256"]
    )
    assert (
        scope.anchor_binding_sha256
        == params["expected_anchor_binding_sha256"]
    )

    # Verification alone must not create preparation directories.
    assert not scope.artifact_root.exists()


def test_policy_drift_fails_closed(tmp_path):
    params = _inputs(tmp_path)
    params["policy_path"].write_bytes(b"changed-policy")

    with pytest.raises(
        RuntimeError,
        match="DOE policy: pinned SHA256 mismatch",
    ):
        verify_governed_preparation_scope(**params)


def test_manifest_drift_fails_closed(tmp_path):
    params = _inputs(tmp_path)
    params["manifest_path"].write_bytes(b"changed-manifest")

    with pytest.raises(
        RuntimeError,
        match="Campaign manifest: pinned SHA256 mismatch",
    ):
        verify_governed_preparation_scope(**params)


def test_anchor_drift_fails_closed(tmp_path):
    params = _inputs(tmp_path)
    params["anchor_binding_path"].write_bytes(b"changed-anchor")

    with pytest.raises(
        RuntimeError,
        match="Anchor-binding record: pinned SHA256 mismatch",
    ):
        verify_governed_preparation_scope(**params)


def test_artifacts_outside_campaign_are_rejected(tmp_path):
    params = _inputs(tmp_path)
    params["artifact_root"] = tmp_path / "other_campaign"

    with pytest.raises(
        RuntimeError,
        match="Preparation artifact root escapes",
    ):
        verify_governed_preparation_scope(**params)


def test_manifest_outside_campaign_is_rejected(tmp_path):
    params = _inputs(tmp_path)
    params["manifest_path"] = params["policy_path"]

    with pytest.raises(
        RuntimeError,
        match="Campaign manifest escapes",
    ):
        verify_governed_preparation_scope(**params)


def test_unpaired_anchor_pin_is_rejected(tmp_path):
    params = _inputs(tmp_path)
    params["expected_anchor_binding_sha256"] = None

    with pytest.raises(
        RuntimeError,
        match="must either both be supplied",
    ):
        verify_governed_preparation_scope(**params)


def test_campaign_without_anchor_binding_is_supported(tmp_path):
    params = _inputs(tmp_path)
    params["anchor_binding_path"] = None
    params["expected_anchor_binding_sha256"] = None

    scope = verify_governed_preparation_scope(**params)

    assert scope.anchor_binding_path is None
    assert scope.anchor_binding_sha256 is None


def test_malformed_pin_is_rejected(tmp_path):
    params = _inputs(tmp_path)
    params["expected_policy_sha256"] = "not-a-sha256"

    with pytest.raises(
        RuntimeError,
        match="invalid independently pinned SHA256",
    ):
        verify_governed_preparation_scope(**params)
