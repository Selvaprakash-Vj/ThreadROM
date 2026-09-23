"""Governed campaign and design-case context for FEM preparation.

A pinned and resolved context is not an execution authorization.
Initial and corrective preparation retain their additional gates.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from threadrom.factory.governed_fem_case_resolution import (
    resolve_governed_design_case,
)
from threadrom.factory.governed_fem_preparation_scope import (
    VerifiedPreparationScope,
    verify_governed_preparation_scope,
)
from threadrom.factory.production_doe import (
    build_phase3_production_doe,
    load_phase3_production_doe_policy,
)


@dataclass(frozen=True, slots=True)
class GovernedFEMCampaignContext:
    scope: VerifiedPreparationScope
    policy: object
    campaign: object
    governed_case: object
    production_case: object
    frozen_row: dict


def _verify_frozen_design_row(
    *,
    manifest: object,
    production_case,
) -> dict:
    if not isinstance(manifest, dict):
        raise RuntimeError(
            "Frozen campaign manifest is not a JSON object."
        )

    rows = manifest.get("design_cases")

    if not isinstance(rows, list):
        raise RuntimeError(
            "Frozen campaign design-case inventory is invalid."
        )

    matches = [
        row
        for row in rows
        if isinstance(row, dict)
        and row.get("case_id") == production_case.case_id
    ]

    if len(matches) != 1:
        raise RuntimeError(
            "Governed case must have exactly one frozen "
            "design-case manifest row."
        )

    row = matches[0]

    if row.get("case_hash") != production_case.case_hash:
        raise RuntimeError(
            "Frozen manifest case-hash mismatch."
        )

    if (
        row.get("mesh_policy_name")
        != production_case.mesh_policy_name
    ):
        raise RuntimeError(
            "Frozen manifest mesh-policy mismatch."
        )

    if row.get("existing_evidence_reuse_planned") is not False:
        raise RuntimeError(
            "New-case preparation cannot rebuild an "
            "existing-evidence anchor."
        )

    if production_case.source_case_id is not None:
        raise RuntimeError(
            "Certified FEM anchors must not enter "
            "new-case preparation."
        )

    return row


def resolve_governed_fem_campaign_context(
    *,
    verified_scope: VerifiedPreparationScope,
    requested_case_id: str,
) -> GovernedFEMCampaignContext:
    """Resolve one frozen new-evidence design case.

    SHA pins must originate from independent campaign governance.
    A successful result does not authorize CAD, meshing or FEM.
    """

    if not isinstance(
        verified_scope,
        VerifiedPreparationScope,
    ):
        raise RuntimeError(
            "A verified preparation scope is required."
        )

    if (
        not isinstance(requested_case_id, str)
        or not requested_case_id
        or requested_case_id != requested_case_id.strip()
    ):
        raise RuntimeError(
            "Invalid requested governed case identity."
        )

    # Recheck the original external pins at the point of case
    # resolution. Never trust a previously verified path alone.
    scope = verify_governed_preparation_scope(
        repo_root=verified_scope.repo_root,
        campaign_root=verified_scope.campaign_root,
        artifact_root=verified_scope.artifact_root,
        policy_path=verified_scope.policy_path,
        manifest_path=verified_scope.manifest_path,
        expected_policy_sha256=verified_scope.policy_sha256,
        expected_manifest_sha256=(
            verified_scope.campaign_manifest_sha256
        ),
        anchor_binding_path=(
            verified_scope.anchor_binding_path
        ),
        expected_anchor_binding_sha256=(
            verified_scope.anchor_binding_sha256
        ),
    )

    policy = load_phase3_production_doe_policy(
        scope.policy_path
    )

    campaign = build_phase3_production_doe(policy)

    governed_case = resolve_governed_design_case(
        campaign=campaign,
        requested_case_id=requested_case_id,
    )

    production_case = governed_case.production_case

    # Check manifest bytes against the pin again before reading.
    # The scope verifier checks the file's actual content.
    manifest = json.loads(
        scope.manifest_path.read_text(
            encoding="utf-8-sig"
        )
    )

    frozen_row = _verify_frozen_design_row(
        manifest=manifest,
        production_case=production_case,
    )

    return GovernedFEMCampaignContext(
        scope=scope,
        policy=policy,
        campaign=campaign,
        governed_case=governed_case,
        production_case=production_case,
        frozen_row=frozen_row,
    )
