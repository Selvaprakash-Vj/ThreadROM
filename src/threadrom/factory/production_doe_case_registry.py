from __future__ import annotations

import hashlib
import re

from dataclasses import dataclass
from pathlib import Path

from threadrom.factory.production_doe import (
    build_phase3_production_doe,
    load_phase3_production_doe_policy,
)
from threadrom.factory.governed_fem_case_resolution import (
    resolve_governed_design_case,
)


EXPECTED_POLICY_SHA256 = (
    "43032557cb2abead0118362bcfc6a9b2e"
    "5246a7d363ca83eef5fcf35054befc1"
)
EXPECTED_CAMPAIGN_SHA256 = (
    "84516519bbb188664268936e2d116e133"
    "431d90d037bed407ffb2d1fe92d2a67"
)


@dataclass(frozen=True, slots=True)
class GovernedC01Case:
    case_id: str
    case_hash: str
    case_run_id: str


def _require_sha256(path: Path, expected: str) -> None:
    digest = hashlib.sha256()

    with path.open("rb") as stream:
        for chunk in iter(
            lambda: stream.read(8 * 1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    if digest.hexdigest() != expected:
        raise RuntimeError(
            f"Frozen C01 governance artifact drift: {path}"
        )


def resolve_governed_c01_case(
    *,
    repo_root: Path,
    requested_case_id: str,
) -> GovernedC01Case:
    """Resolve a frozen C01 design case; never authorize a solve."""

    root = repo_root.resolve(strict=True)
    policy_path = root / "config/phase3_production_doe.toml"
    campaign_path = (
        root
        / "simulations/staging/phase3_cp8_production_doe"
        / "TRM-PDOE-C01/production_doe_campaign_manifest.json"
    )

    _require_sha256(policy_path, EXPECTED_POLICY_SHA256)
    _require_sha256(campaign_path, EXPECTED_CAMPAIGN_SHA256)

    policy = load_phase3_production_doe_policy(policy_path)
    campaign = build_phase3_production_doe(policy)

    # The frozen C01 policy and manifest have already been verified.
    # Shared case resolution does not grant solver authorization.
    resolved = resolve_governed_design_case(
        campaign=campaign,
        requested_case_id=requested_case_id,
    )

    return GovernedC01Case(
        case_id=resolved.case_id,
        case_hash=resolved.case_hash,
        case_run_id=resolved.case_run_id,
    )
