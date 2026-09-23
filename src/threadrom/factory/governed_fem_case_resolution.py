"""Reusable case selection for a provenance-verified DOE campaign.

Case resolution is not execution authorization.

The caller must independently verify the campaign policy, manifest,
source versions and applicable execution permissions.
"""

from __future__ import annotations

import re

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from threadrom.factory.production_doe import (
        ProductionDoeCampaign,
        ProductionDoeCase,
    )


@dataclass(frozen=True, slots=True)
class GovernedDesignCase:
    case_id: str
    case_hash: str
    case_run_id: str
    policy_id: str
    production_case: ProductionDoeCase


def resolve_governed_design_case(
    *,
    campaign: ProductionDoeCampaign,
    requested_case_id: str,
) -> GovernedDesignCase:
    """Resolve one eligible design case without authorizing execution."""

    if (
        not isinstance(requested_case_id, str)
        or not requested_case_id
        or requested_case_id != requested_case_id.strip()
    ):
        raise RuntimeError(
            "Invalid requested governed case identity."
        )

    if (
        not isinstance(campaign.policy_id, str)
        or not campaign.policy_id.strip()
    ):
        raise RuntimeError(
            "Invalid governed campaign policy identity."
        )

    design_ids = [
        case.case_id
        for case in campaign.design_cases
    ]

    holdout_ids = [
        case.case_id
        for case in campaign.holdout_cases
    ]

    if any(
        not isinstance(case_id, str) or not case_id.strip()
        for case_id in design_ids + holdout_ids
    ):
        raise RuntimeError(
            "Invalid case identity in governed campaign."
        )

    if (
        len(design_ids) != len(set(design_ids))
        or len(holdout_ids) != len(set(holdout_ids))
    ):
        raise RuntimeError(
            "Duplicate case identity in governed campaign."
        )

    if set(design_ids).intersection(holdout_ids):
        raise RuntimeError(
            "Design and holdout case identities overlap."
        )

    # Never expose holdout case configuration to normal execution.

    if requested_case_id in holdout_ids:
        raise RuntimeError(
            "Requested case is not eligible for design execution."
        )

    matches = [
        case
        for case in campaign.design_cases
        if case.case_id == requested_case_id
    ]

    if len(matches) != 1:
        raise RuntimeError(
            "Requested case is absent from the governed design."
        )

    case = matches[0]

    # Existing certified anchors must be reused, not recalculated.

    if case.source_case_id is not None:
        raise RuntimeError(
            "Certified anchor must be reused, not recalculated."
        )

    if (
        not isinstance(case.case_hash, str)
        or re.fullmatch(
            r"[0-9a-f]{64}",
            case.case_hash,
        ) is None
    ):
        raise RuntimeError(
            "Invalid governed case hash."
        )

    return GovernedDesignCase(
        case_id=case.case_id,
        case_hash=case.case_hash,
        case_run_id=f"trm_fem_{case.case_hash[:12]}",
        policy_id=campaign.policy_id,
        production_case=case,
    )
