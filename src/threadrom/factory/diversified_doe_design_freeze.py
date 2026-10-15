"""Immutable design-freeze certificate for the Phase-3 diversified DOE.

The source design proposal intentionally remains non-executable and unsealed.
This module freezes its exact bytes and governing provenance in a separate
certificate.

A design-freeze certificate:
- does not authorize FEM,
- does not authorize geometry or mesh execution,
- does not admit data to the ROM dataset,
- does not authorize surrogate training,
- does not authorize sealed-holdout access.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tomllib

from pathlib import Path
from typing import Mapping


CERTIFICATE_SCHEMA = (
    "threadrom.phase3_diversified_doe_design_freeze.v1"
)

CERTIFICATE_FILENAME = (
    "design_freeze_certificate.json"
)

CERTIFICATE_STATUS = "FROZEN_DESIGN"

_SHA256 = re.compile(
    r"^[0-9a-f]{64}$"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as stream:
        for chunk in iter(
            lambda: stream.read(8 * 1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def _canonical(
    payload: Mapping[str, object],
) -> bytes:
    return (
        json.dumps(
            payload,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _count_value(
    value: object,
) -> int:
    if type(value) is int:
        return value

    if isinstance(
        value,
        (list, tuple, dict, set),
    ):
        return len(value)

    if isinstance(value, str):
        match = re.fullmatch(
            (
                r"\s*(\d+)\s+reserved;"
                r"\s*configurations not generated\s*"
            ),
            value,
            flags=re.IGNORECASE,
        )

        if match is not None:
            return int(
                match.group(1)
            )

        raise RuntimeError(
            "DOE manifest count string has "
            "unsupported representation."
        )

    raise RuntimeError(
        "DOE manifest count field has "
        "unsupported representation."
    )


def _validate_policy(
    policy: Mapping[str, object],
) -> None:
    governance = policy.get(
        "governance"
    )

    if not isinstance(
        governance,
        dict,
    ):
        raise RuntimeError(
            "Diversified DOE governance "
            "section is missing."
        )

    required_false = (
        "dataset_admission_authorized",
        "geometry_or_mesh_execution_authorized",
        "sealed_holdout_access_authorized",
        "solver_launch_authorized",
        "surrogate_training_authorized",
    )

    for name in required_false:
        if governance.get(name) is not False:
            raise RuntimeError(
                "DOE design freeze refuses "
                f"governance authority: {name}"
            )

    required_true = (
        "duplicate_accepted_case_rerun_forbidden",
        "no_large_upfront_batch_authorization",
        "no_post_hoc_acceptance_relaxation",
        "preserve_failed_and_rejected_attempt_provenance",
        "preserve_valid_realized_states",
        "requested_and_realized_states_must_be_distinguished",
        "reuse_existing_evidence_before_new_fem",
    )

    for name in required_true:
        if governance.get(name) is not True:
            raise RuntimeError(
                "Required DOE governance invariant "
                f"is not enabled: {name}"
            )

    if (
        governance.get("phase") != 3
        or governance.get(
            "first_rom_phase"
        ) != 4
    ):
        raise RuntimeError(
            "Unexpected Phase-3/Phase-4 "
            "governance boundary."
        )


def _validate_atlas(
    atlas: Mapping[str, object],
) -> None:
    cases = atlas.get("cases")

    if not isinstance(cases, list):
        raise RuntimeError(
            "Accepted-FEM atlas lacks case inventory."
        )

    distinct = atlas.get(
        "distinct_case_count"
    )

    acceptance_sources = atlas.get(
        "acceptance_source_count"
    )

    if (
        type(distinct) is not int
        or distinct != len(cases)
        or distinct < 1
    ):
        raise RuntimeError(
            "Accepted-FEM atlas distinct-case "
            "count is inconsistent."
        )

    if (
        type(acceptance_sources) is not int
        or acceptance_sources < distinct
    ):
        raise RuntimeError(
            "Accepted-FEM atlas acceptance-source "
            "count is invalid."
        )

    case_ids = [
        row.get("case_id")
        for row in cases
        if isinstance(row, dict)
    ]

    case_hashes = [
        row.get("case_hash")
        for row in cases
        if isinstance(row, dict)
    ]

    if (
        len(case_ids) != len(cases)
        or len(set(case_ids)) != len(case_ids)
        or len(case_hashes) != len(cases)
        or len(set(case_hashes)) != len(case_hashes)
    ):
        raise RuntimeError(
            "Accepted-FEM atlas contains "
            "ambiguous case identity."
        )


def _validate_proposal(
    proposal: Mapping[str, object],
    *,
    actual_policy_sha256: str,
    actual_atlas_sha256: str,
) -> dict[str, int]:
    cases = proposal.get("cases")

    if not isinstance(cases, list):
        raise RuntimeError(
            "Diversified DOE proposal lacks case inventory."
        )

    # The proposal remains explicitly non-frozen/non-executable.
    # The separate certificate freezes its exact bytes.
    if proposal.get("design_frozen") is not False:
        raise RuntimeError(
            "Source proposal unexpectedly claims "
            "to be its own design freeze."
        )

    for name in (
        "fem_execution_authorized",
        "geometry_execution_authorized",
        "mesh_execution_authorized",
        "dataset_admission_authorized",
    ):
        if proposal.get(name) is not False:
            raise RuntimeError(
                "Source proposal unexpectedly grants "
                f"authority: {name}"
            )

    embedded_policy = proposal.get(
        "policy_sha256"
    )

    embedded_atlas = proposal.get(
        "atlas_sha256"
    )

    if (
        embedded_policy != actual_policy_sha256
    ):
        raise RuntimeError(
            "DOE proposal policy SHA differs "
            "from governing policy bytes."
        )

    if (
        embedded_atlas != actual_atlas_sha256
    ):
        raise RuntimeError(
            "DOE proposal atlas SHA differs "
            "from accepted-FEM atlas bytes."
        )

    declared_design = proposal.get(
        "design_state_count"
    )

    if (
        type(declared_design) is not int
        or declared_design != len(cases)
        or declared_design != 72
    ):
        raise RuntimeError(
            "Diversified DOE must contain exactly "
            "72 frozen design states."
        )

    proposal_ids = []
    case_hashes = []

    historical_count = 0
    new_count = 0

    for row in cases:
        if not isinstance(row, dict):
            raise RuntimeError(
                "DOE case row is not a mapping."
            )

        proposal_id = row.get(
            "proposal_id"
        )

        case_hash = row.get(
            "case_hash"
        )

        if (
            not isinstance(proposal_id, str)
            or not proposal_id.strip()
        ):
            raise RuntimeError(
                "DOE case lacks proposal identity."
            )

        if (
            not isinstance(case_hash, str)
            or _SHA256.fullmatch(
                case_hash
            ) is None
        ):
            raise RuntimeError(
                "DOE case contains invalid case hash."
            )

        if (
            row.get(
                "fem_execution_authorized"
            )
            is not False
        ):
            raise RuntimeError(
                "DOE case row grants FEM execution "
                f"authority: {proposal_id}"
            )

        if (
            row.get(
                "dataset_admission_status"
            )
            != "NOT_EVALUATED"
        ):
            raise RuntimeError(
                "DOE source proposal already claims "
                f"dataset admission: {proposal_id}"
            )

        proposal_ids.append(
            proposal_id
        )

        case_hashes.append(
            case_hash
        )

        if (
            row.get(
                "historical_case_id"
            )
            is None
        ):
            new_count += 1
        else:
            historical_count += 1

    if (
        len(set(proposal_ids))
        != len(proposal_ids)
        or len(set(case_hashes))
        != len(case_hashes)
    ):
        raise RuntimeError(
            "DOE design contains duplicate "
            "proposal or physical case identity."
        )

    if (
        historical_count != 14
        or new_count != 58
    ):
        raise RuntimeError(
            "DOE historical/new allocation "
            "differs from frozen design intent."
        )

    declared_historical = _count_value(
        proposal.get(
            "historical_reuse_candidates"
        )
    )

    declared_new = _count_value(
        proposal.get(
            "new_design_states_requiring_evidence"
        )
    )

    declared_validation = _count_value(
        proposal.get(
            "validation_states"
        )
    )

    if declared_historical != 14:
        raise RuntimeError(
            "Historical-reuse declaration "
            "must equal 14."
        )

    if declared_new != 58:
        raise RuntimeError(
            "New-evidence declaration "
            "must equal 58."
        )

    if declared_validation != 18:
        raise RuntimeError(
            "Sealed validation allocation "
            "must equal 18."
        )

    return {
        "design_state_count": 72,
        "historical_reuse_candidates": 14,
        "new_design_states_requiring_evidence": 58,
        "sealed_validation_state_count": 18,
    }


def build_design_freeze_certificate(
    *,
    proposal_path: Path,
    policy_path: Path,
    atlas_path: Path,
) -> dict[str, object]:
    for path in (
        proposal_path,
        policy_path,
        atlas_path,
    ):
        if (
            not path.is_file()
            or path.stat().st_size <= 0
        ):
            raise RuntimeError(
                "DOE freeze source is missing "
                f"or empty: {path}"
            )

    proposal_bytes = (
        proposal_path.read_bytes()
    )

    policy_bytes = (
        policy_path.read_bytes()
    )

    atlas_bytes = (
        atlas_path.read_bytes()
    )

    proposal = json.loads(
        proposal_bytes.decode(
            "utf-8-sig"
        )
    )

    policy = tomllib.loads(
        policy_bytes.decode(
            "utf-8-sig"
        )
    )

    atlas = json.loads(
        atlas_bytes.decode(
            "utf-8-sig"
        )
    )

    if not isinstance(
        proposal,
        dict,
    ):
        raise RuntimeError(
            "Invalid diversified DOE proposal."
        )

    if not isinstance(
        policy,
        dict,
    ):
        raise RuntimeError(
            "Invalid diversified DOE policy."
        )

    if not isinstance(
        atlas,
        dict,
    ):
        raise RuntimeError(
            "Invalid accepted-FEM atlas."
        )

    policy_sha = hashlib.sha256(
        policy_bytes
    ).hexdigest()

    atlas_sha = hashlib.sha256(
        atlas_bytes
    ).hexdigest()

    proposal_sha = hashlib.sha256(
        proposal_bytes
    ).hexdigest()

    _validate_policy(
        policy
    )

    _validate_atlas(
        atlas
    )

    counts = _validate_proposal(
        proposal,
        actual_policy_sha256=policy_sha,
        actual_atlas_sha256=atlas_sha,
    )

    return {
        "schema": CERTIFICATE_SCHEMA,
        "record_status": "FINAL",
        "design_status": CERTIFICATE_STATUS,
        "campaign_id": proposal.get(
            "campaign_id"
        ),
        "source_commit": proposal.get(
            "source_commit"
        ),
        "proposal_sha256": proposal_sha,
        "policy_sha256": policy_sha,
        "accepted_fem_atlas_sha256": atlas_sha,
        **counts,
        "source_proposal_remains_non_executable": True,
        "fem_execution_authorized": False,
        "geometry_execution_authorized": False,
        "mesh_execution_authorized": False,
        "dataset_admission_authorized": False,
        "surrogate_training_authorized": False,
        "sealed_holdout_access_authorized": False,
        "large_upfront_batch_authorized": False,
        "meaning": (
            "This certificate freezes the exact "
            "Phase-3 diversified DOE design and "
            "its governing provenance. Execution "
            "authority, dataset admission, holdout "
            "access and ROM training remain separate "
            "governed decisions."
        ),
    }


def persist_design_freeze_certificate(
    *,
    proposal_path: Path,
    policy_path: Path,
    atlas_path: Path,
    certificate_path: Path,
) -> Path:
    record = build_design_freeze_certificate(
        proposal_path=proposal_path,
        policy_path=policy_path,
        atlas_path=atlas_path,
    )

    content = _canonical(
        record
    )

    certificate_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        with certificate_path.open(
            "xb"
        ) as stream:
            stream.write(content)
            stream.flush()
            os.fsync(
                stream.fileno()
            )

    except FileExistsError:
        if (
            certificate_path.read_bytes()
            != content
        ):
            raise RuntimeError(
                "Existing immutable DOE design-freeze "
                "certificate differs; engineering "
                "review required."
            ) from None

    return certificate_path


def recover_design_freeze_certificate(
    *,
    proposal_path: Path,
    policy_path: Path,
    atlas_path: Path,
    certificate_path: Path,
) -> dict[str, object] | None:
    if not certificate_path.exists():
        return None

    raw = certificate_path.read_bytes()
    record = json.loads(raw)

    if raw != _canonical(record):
        raise RuntimeError(
            "DOE design-freeze certificate "
            "is not canonical or changed."
        )

    current = build_design_freeze_certificate(
        proposal_path=proposal_path,
        policy_path=policy_path,
        atlas_path=atlas_path,
    )

    if record != current:
        raise RuntimeError(
            "Frozen DOE design provenance "
            "has changed."
        )

    return record
