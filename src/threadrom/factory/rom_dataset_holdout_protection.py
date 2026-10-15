from __future__ import annotations

import hashlib
import hmac
import json
import re
import tomllib

from enum import Enum
from pathlib import Path
from typing import Mapping


_SHA256_PATTERN = re.compile(
    r"^[0-9a-f]{64}$"
)

_ATLAS_RELATIVE_PATH = (
    Path("docs")
    / "phase3_fem_atlas"
    / "atlas.json"
)

_POLICY_RELATIVE_PATH = (
    Path("config")
    / "phase3_production_doe.toml"
)

_EXPECTED_BLIND_HOLDOUT_ROWS = 6


class RomDatasetHoldoutProtectionError(
    RuntimeError
):
    """Fail-closed DA11 protection error."""


class HoldoutProtectionDecision(
    str,
    Enum,
):
    """
    Public DA11 surface.

    No sealed identity, coordinate, case object,
    case hash or holdout collection is returned.
    """

    SOURCE_INSPECTION_ALLOWED = (
        "SOURCE_INSPECTION_ALLOWED"
    )

    SEALED_HOLDOUT_PROTECTED = (
        "SEALED_HOLDOUT_PROTECTED"
    )


def _require(
    condition: bool,
    message: str,
) -> None:
    if not condition:
        raise RomDatasetHoldoutProtectionError(
            message
        )


def _sha256(
    path: Path,
) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def _validate_sha256(
    value: str,
    *,
    label: str,
) -> None:
    _require(
        isinstance(
            value,
            str,
        )
        and _SHA256_PATTERN.fullmatch(
            value
        )
        is not None,
        f"invalid {label} SHA-256",
    )


def _canonical_file(
    *,
    root: Path,
    relative_path: Path,
) -> Path:
    path = (
        root
        / relative_path
    ).resolve(
        strict=True
    )

    try:
        path.relative_to(
            root
        )
    except ValueError as exc:
        raise RomDatasetHoldoutProtectionError(
            "DA11 authority escapes repository root"
        ) from exc

    _require(
        path.is_file(),
        "DA11 authority is not a regular file",
    )

    return path


def _validate_candidate_identity(
    *,
    case_id: str,
    case_hash: str,
) -> None:
    _require(
        isinstance(
            case_id,
            str,
        )
        and bool(
            case_id
        )
        and case_id
        == case_id.strip(),
        "invalid DA11 candidate identity",
    )

    _require(
        isinstance(
            case_hash,
            str,
        )
        and _SHA256_PATTERN.fullmatch(
            case_hash
        )
        is not None,
        "invalid DA11 candidate case hash",
    )


def _require_exact_registered_atlas_case(
    *,
    atlas_path: Path,
    expected_atlas_sha256: str,
    case_id: str,
    case_hash: str,
) -> None:
    _require(
        _sha256(
            atlas_path
        )
        == expected_atlas_sha256,
        "accepted FEM Atlas SHA-256 drift",
    )

    try:
        atlas = json.loads(
            atlas_path.read_text(
                encoding="utf-8-sig"
            )
        )
    except (
        json.JSONDecodeError,
        UnicodeDecodeError,
    ) as exc:
        raise RomDatasetHoldoutProtectionError(
            "accepted FEM Atlas is unreadable"
        ) from exc

    _require(
        isinstance(
            atlas,
            dict,
        ),
        "accepted FEM Atlas root is invalid",
    )

    cases = atlas.get(
        "cases"
    )

    _require(
        isinstance(
            cases,
            list,
        )
        and bool(
            cases
        ),
        "accepted FEM Atlas case registry is invalid",
    )

    case_ids: list[str] = []
    case_hashes: list[str] = []

    for row in cases:
        _require(
            isinstance(
                row,
                dict,
            ),
            "accepted FEM Atlas contains invalid case record",
        )

        row_case_id = row.get(
            "case_id"
        )

        row_case_hash = row.get(
            "case_hash"
        )

        _require(
            isinstance(
                row_case_id,
                str,
            )
            and bool(
                row_case_id
            ),
            "accepted FEM Atlas contains invalid case identity",
        )

        _require(
            isinstance(
                row_case_hash,
                str,
            )
            and _SHA256_PATTERN.fullmatch(
                row_case_hash
            )
            is not None,
            "accepted FEM Atlas contains invalid case hash",
        )

        case_ids.append(
            row_case_id
        )

        case_hashes.append(
            row_case_hash
        )

    _require(
        len(
            case_ids
        )
        == len(
            set(
                case_ids
            )
        ),
        "accepted FEM Atlas contains duplicate case identity",
    )

    _require(
        len(
            case_hashes
        )
        == len(
            set(
                case_hashes
            )
        ),
        "accepted FEM Atlas contains duplicate case hash",
    )

    matches = [
        row
        for row in cases
        if (
            row.get(
                "case_id"
            )
            == case_id
            and row.get(
                "case_hash"
            )
            == case_hash
        )
    ]

    _require(
        len(
            matches
        )
        == 1,
        (
            "DA11 candidate is not an exact registered "
            "accepted FEM Atlas identity"
        ),
    )

    candidate = matches[
        0
    ]

    _require(
        candidate.get(
            "dataset_partition"
        )
        is None,
        (
            "DA11 candidate already crossed the "
            "pre-admission partition boundary"
        ),
    )


def _private_policy_holdout_membership(
    *,
    policy_path: Path,
    expected_policy_sha256: str,
    candidate_case_id: str,
) -> bool:
    """
    Private sealed-membership operation.

    The policy is read only after exact Atlas registration
    has already been proven by the public entry point.

    No holdout identity leaves this function.
    """

    raw = policy_path.read_bytes()

    _require(
        hashlib.sha256(
            raw
        ).hexdigest()
        == expected_policy_sha256,
        "frozen Production DOE policy SHA-256 drift",
    )

    try:
        policy = tomllib.loads(
            raw.decode(
                "utf-8-sig"
            )
        )
    except (
        tomllib.TOMLDecodeError,
        UnicodeDecodeError,
    ) as exc:
        raise RomDatasetHoldoutProtectionError(
            "frozen Production DOE policy is unreadable"
        ) from exc

    _require(
        isinstance(
            policy,
            dict,
        ),
        "frozen Production DOE policy root is invalid",
    )

    holdouts = policy.get(
        "holdouts"
    )

    _require(
        isinstance(
            holdouts,
            Mapping,
        ),
        "frozen holdout authority is absent or invalid",
    )

    points = holdouts.get(
        "points"
    )

    _require(
        isinstance(
            points,
            list,
        )
        and len(
            points
        )
        == _EXPECTED_BLIND_HOLDOUT_ROWS,
        "frozen blind-holdout point authority is invalid",
    )

    candidate_bytes = (
        candidate_case_id.encode(
            "utf-8"
        )
    )

    seen_private_ids: set[str] = set()

    matched = False

    for row in points:
        _require(
            isinstance(
                row,
                Mapping,
            ),
            "frozen blind-holdout record is invalid",
        )

        private_id = row.get(
            "case_id"
        )

        _require(
            isinstance(
                private_id,
                str,
            )
            and bool(
                private_id
            )
            and private_id
            == private_id.strip(),
            "frozen blind-holdout identity is invalid",
        )

        _require(
            private_id
            not in seen_private_ids,
            (
                "frozen blind-holdout authority "
                "contains duplicate identity"
            ),
        )

        seen_private_ids.add(
            private_id
        )

        current = hmac.compare_digest(
            candidate_bytes,
            private_id.encode(
                "utf-8"
            ),
        )

        matched = (
            matched
            or current
        )

    _require(
        len(
            seen_private_ids
        )
        == _EXPECTED_BLIND_HOLDOUT_ROWS,
        "frozen blind-holdout authority count drift",
    )

    return matched


def evaluate_member_shortening_holdout_protection(
    *,
    repo_root: Path,
    expected_atlas_sha256: str,
    expected_policy_sha256: str,
    case_id: str,
    case_hash: str,
) -> HoldoutProtectionDecision:
    """
    DA11 opaque membership oracle for one accepted FEM case.

    Caller-visible output is binary governance state only.
    """

    root = Path(
        repo_root
    ).resolve(
        strict=True
    )

    _require(
        root.is_dir(),
        "invalid ThreadROM repository root",
    )

    _validate_sha256(
        expected_atlas_sha256,
        label="accepted FEM Atlas",
    )

    _validate_sha256(
        expected_policy_sha256,
        label="Production DOE policy",
    )

    _validate_candidate_identity(
        case_id=case_id,
        case_hash=case_hash,
    )

    atlas_path = _canonical_file(
        root=root,
        relative_path=(
            _ATLAS_RELATIVE_PATH
        ),
    )

    policy_path = _canonical_file(
        root=root,
        relative_path=(
            _POLICY_RELATIVE_PATH
        ),
    )

    # Critical anti-enumeration property:
    # arbitrary identities cannot query the sealed policy.
    _require_exact_registered_atlas_case(
        atlas_path=atlas_path,
        expected_atlas_sha256=(
            expected_atlas_sha256
        ),
        case_id=case_id,
        case_hash=case_hash,
    )

    protected = (
        _private_policy_holdout_membership(
            policy_path=policy_path,
            expected_policy_sha256=(
                expected_policy_sha256
            ),
            candidate_case_id=case_id,
        )
    )

    if protected:
        return (
            HoldoutProtectionDecision
            .SEALED_HOLDOUT_PROTECTED
        )

    return (
        HoldoutProtectionDecision
        .SOURCE_INSPECTION_ALLOWED
    )