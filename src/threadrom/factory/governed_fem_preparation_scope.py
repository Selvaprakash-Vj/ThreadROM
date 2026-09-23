"""Pinned, repository-contained preparation scope for a FEM campaign.

Verifying a scope establishes file identity and path containment only.
The caller must separately establish campaign approval, design-case
eligibility, physical preflight and authorization for any FEM work.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path


@dataclass(frozen=True, slots=True)
class VerifiedPreparationScope:
    repo_root: Path
    campaign_root: Path
    artifact_root: Path
    policy_path: Path
    manifest_path: Path
    anchor_binding_path: Path | None
    policy_sha256: str
    campaign_manifest_sha256: str
    anchor_binding_sha256: str | None


def _inside(path: Path, parent: Path, label: str) -> Path:
    resolved = Path(path).resolve()

    if not resolved.is_relative_to(parent):
        raise RuntimeError(
            f"{label} escapes its governed parent directory."
        )

    return resolved


def _verify_pinned_file(
    *,
    path: Path,
    expected_sha256: str,
    label: str,
) -> str:
    if (
        not isinstance(expected_sha256, str)
        or len(expected_sha256) != 64
        or any(
            character not in "0123456789abcdef"
            for character in expected_sha256
        )
    ):
        raise RuntimeError(
            f"{label}: invalid independently pinned SHA256."
        )

    if not path.is_file() or path.stat().st_size <= 0:
        raise RuntimeError(
            f"{label}: pinned evidence file is missing or empty."
        )

    digest = hashlib.sha256()

    with path.open("rb") as stream:
        for chunk in iter(
            lambda: stream.read(8 * 1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    actual_sha256 = digest.hexdigest()

    if actual_sha256 != expected_sha256:
        raise RuntimeError(
            f"{label}: pinned SHA256 mismatch."
        )

    return actual_sha256


def verify_governed_preparation_scope(
    *,
    repo_root: Path,
    campaign_root: Path,
    artifact_root: Path,
    policy_path: Path,
    manifest_path: Path,
    expected_policy_sha256: str,
    expected_manifest_sha256: str,
    anchor_binding_path: Path | None = None,
    expected_anchor_binding_sha256: str | None = None,
) -> VerifiedPreparationScope:
    """Verify externally pinned campaign files and contained paths.

    Expected hashes must come from independent campaign governance;
    this function does not generate pins, approve campaigns, resolve
    design cases, or authorize preparation or solver execution.
    """

    root = Path(repo_root).resolve(strict=True)

    if not root.is_dir():
        raise RuntimeError(
            "Governed repository root is not a directory."
        )

    campaign = _inside(
        campaign_root,
        root,
        "Campaign root",
    )

    if campaign == root or not campaign.is_dir():
        raise RuntimeError(
            "Campaign root must be an existing repository subdirectory."
        )

    artifacts = _inside(
        artifact_root,
        campaign,
        "Preparation artifact root",
    )

    if artifacts == campaign:
        raise RuntimeError(
            "Preparation artifacts must use a campaign subdirectory."
        )

    policy = _inside(
        policy_path,
        root,
        "DOE policy",
    )

    manifest = _inside(
        manifest_path,
        campaign,
        "Campaign manifest",
    )

    policy_hash = _verify_pinned_file(
        path=policy,
        expected_sha256=expected_policy_sha256,
        label="DOE policy",
    )

    manifest_hash = _verify_pinned_file(
        path=manifest,
        expected_sha256=expected_manifest_sha256,
        label="Campaign manifest",
    )

    if (
        (anchor_binding_path is None)
        != (expected_anchor_binding_sha256 is None)
    ):
        raise RuntimeError(
            "Anchor-binding path and independent SHA256 pin "
            "must either both be supplied or both be omitted."
        )

    anchor = None
    anchor_hash = None

    if anchor_binding_path is not None:
        anchor = _inside(
            anchor_binding_path,
            campaign,
            "Anchor-binding record",
        )

        anchor_hash = _verify_pinned_file(
            path=anchor,
            expected_sha256=expected_anchor_binding_sha256,
            label="Anchor-binding record",
        )

    return VerifiedPreparationScope(
        repo_root=root,
        campaign_root=campaign,
        artifact_root=artifacts,
        policy_path=policy,
        manifest_path=manifest,
        anchor_binding_path=anchor,
        policy_sha256=policy_hash,
        campaign_manifest_sha256=manifest_hash,
        anchor_binding_sha256=anchor_hash,
    )
