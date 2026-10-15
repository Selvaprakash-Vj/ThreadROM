from __future__ import annotations

import hashlib
import json
import math
import re

from pathlib import Path
from typing import Mapping

from threadrom.factory.governed_trial_history import (
    PreparedTrialVerifier,
    VerifiedPreparedTrialEvidence,
)


_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_CASE_RUN_ID_PATTERN = re.compile(r"^trm_fem_[0-9a-f]{12}$")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as stream:
        for chunk in iter(
            lambda: stream.read(8 * 1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def _require(
    condition: bool,
    message: str,
) -> None:
    if not condition:
        raise RuntimeError(
            "DIVERSIFIED_PREPARATION_INVALID: "
            + message
        )


def make_diversified_prepared_trial_verifier(
    *,
    preparation_records: Mapping[
        str,
        tuple[Path, str],
    ],
    required_scope: str,
) -> PreparedTrialVerifier:
    """Create a verifier backed by independently pinned preparation records.

    ``preparation_records`` maps each adaptive trial run ID to:
        (preparation-record path, independently pinned SHA-256)

    The preparation record is evidence only. It never grants FEM execution,
    dataset admission, holdout access, or physics acceptance.
    """

    _require(
        isinstance(required_scope, str)
        and bool(required_scope.strip()),
        "required scope is missing",
    )

    pinned: dict[
        str,
        tuple[Path, str],
    ] = {}

    for run_id, entry in preparation_records.items():
        _require(
            isinstance(run_id, str)
            and bool(run_id.strip()),
            "invalid pinned run identity",
        )

        _require(
            isinstance(entry, tuple)
            and len(entry) == 2,
            "invalid preparation-record pin",
        )

        record_path, expected_sha256 = entry

        _require(
            isinstance(expected_sha256, str)
            and _SHA256_PATTERN.fullmatch(
                expected_sha256
            ) is not None,
            "invalid preparation-record SHA-256 pin",
        )

        pinned[run_id] = (
            Path(record_path),
            expected_sha256,
        )

    def verify(
        *,
        repo_root: Path,
        case_id: str,
        case_hash: str,
        case_run_id: str,
        trial_index: int,
        run_dir: Path,
    ) -> VerifiedPreparedTrialEvidence:

        root = Path(
            repo_root
        ).resolve(strict=True)

        run_dir_resolved = Path(
            run_dir
        ).resolve(strict=True)

        try:
            run_dir_resolved.relative_to(root)
        except ValueError as exc:
            raise RuntimeError(
                "DIVERSIFIED_PREPARATION_INVALID: "
                "run directory is outside repository"
            ) from exc

        _require(
            isinstance(case_id, str)
            and bool(case_id.strip()),
            "invalid case identity",
        )

        _require(
            isinstance(case_hash, str)
            and _SHA256_PATTERN.fullmatch(
                case_hash
            ) is not None,
            "invalid case hash",
        )

        _require(
            isinstance(case_run_id, str)
            and _CASE_RUN_ID_PATTERN.fullmatch(
                case_run_id
            ) is not None,
            "invalid case-run identity",
        )

        _require(
            type(trial_index) is int
            and trial_index >= 2,
            "adaptive trial index must be >= 2",
        )

        run_id = (
            f"{case_run_id}_cal_{trial_index:02d}"
        )

        _require(
            run_dir_resolved.name == run_id,
            "run-directory identity mismatch",
        )

        _require(
            run_id in pinned,
            "adaptive preparation lacks independent pin",
        )

        record_path_raw, expected_record_sha = (
            pinned[run_id]
        )

        record_path = Path(
            record_path_raw
        ).resolve(strict=True)

        try:
            record_path.relative_to(root)
        except ValueError as exc:
            raise RuntimeError(
                "DIVERSIFIED_PREPARATION_INVALID: "
                "preparation record is outside repository"
            ) from exc

        _require(
            record_path.parent
            == run_dir_resolved,
            "preparation record is outside trial directory",
        )

        actual_record_sha = _sha256(
            record_path
        )

        _require(
            actual_record_sha
            == expected_record_sha,
            "preparation-record SHA-256 drift",
        )

        record = json.loads(
            record_path.read_text(
                encoding="utf-8-sig"
            )
        )

        _require(
            isinstance(record, dict),
            "preparation record is not an object",
        )

        required_keys = {
            "case_hash",
            "case_run_id",
            "scope",
            "sealed_holdouts_accessed",
            "next_trial",
            "deck",
        }

        _require(
            required_keys.issubset(
                record.keys()
            ),
            "required preparation fields are missing",
        )

        _require(
            record["case_hash"]
            == case_hash,
            "case hash mismatch",
        )

        _require(
            record["case_run_id"]
            == case_run_id,
            "case-run mismatch",
        )

        _require(
            record["scope"]
            == required_scope,
            "preparation scope mismatch",
        )

        _require(
            record[
                "sealed_holdouts_accessed"
            ] is False,
            "sealed holdout access was claimed",
        )

        # Preparation evidence must never self-authorize broader actions.
        for key in (
            "dataset_admission_authorized",
            "doe_wide_solver_launch_authorized",
            "production_doe_authorization_claimed",
        ):
            if key in record:
                _require(
                    record[key] is False,
                    f"{key} must remain false",
                )

        next_trial = record[
            "next_trial"
        ]

        _require(
            isinstance(next_trial, dict),
            "next-trial record is invalid",
        )

        _require(
            next_trial.get("run_id")
            == run_id,
            "next-trial run identity mismatch",
        )

        _require(
            type(
                next_trial.get("trial_index")
            ) is int
            and next_trial["trial_index"]
            == trial_index,
            "next-trial index mismatch",
        )

        delta_temperature_c = (
            next_trial.get(
                "delta_temperature_c"
            )
        )

        _require(
            isinstance(
                delta_temperature_c,
                (int, float),
            )
            and not isinstance(
                delta_temperature_c,
                bool,
            )
            and math.isfinite(
                float(
                    delta_temperature_c
                )
            ),
            "next-trial delta-T is invalid",
        )

        source = next_trial.get(
            "source"
        )

        _require(
            isinstance(source, str)
            and bool(source.strip()),
            "next-trial corrective source is missing",
        )

        adaptive_plan = record.get(
            "adaptive_plan"
        )

        if adaptive_plan is not None:
            _require(
                isinstance(
                    adaptive_plan,
                    dict,
                ),
                "adaptive plan is invalid",
            )

            _require(
                adaptive_plan.get(
                    "next_run_id"
                )
                == run_id,
                "adaptive-plan next run mismatch",
            )

        adaptive_evaluation = record.get(
            "adaptive_evaluation"
        )

        if adaptive_evaluation is not None:
            _require(
                isinstance(
                    adaptive_evaluation,
                    dict,
                ),
                "adaptive evaluation is invalid",
            )

            evaluated_next = (
                adaptive_evaluation.get(
                    "next_trial"
                )
            )

            _require(
                isinstance(
                    evaluated_next,
                    dict,
                )
                and evaluated_next.get(
                    "run_id"
                )
                == run_id
                and evaluated_next.get(
                    "trial_index"
                )
                == trial_index,
                "adaptive evaluation next-trial mismatch",
            )

        deck_record = record[
            "deck"
        ]

        _require(
            isinstance(deck_record, dict),
            "deck evidence is invalid",
        )

        relative_path = deck_record.get(
            "relative_path"
        )

        deck_sha256 = deck_record.get(
            "sha256"
        )

        _require(
            isinstance(
                relative_path,
                str,
            )
            and bool(
                relative_path.strip()
            ),
            "deck relative path is missing",
        )

        _require(
            isinstance(
                deck_sha256,
                str,
            )
            and _SHA256_PATTERN.fullmatch(
                deck_sha256
            ) is not None,
            "deck SHA-256 is invalid",
        )

        normalized_relative = (
            relative_path.replace(
                "\\",
                "/",
            )
        )

        deck_path = (
            root
            / Path(
                normalized_relative
            )
        ).resolve()

        try:
            deck_path.relative_to(root)
        except ValueError as exc:
            raise RuntimeError(
                "DIVERSIFIED_PREPARATION_INVALID: "
                "deck path escapes repository"
            ) from exc

        expected_deck = (
            run_dir_resolved
            / f"{run_id}.inp"
        ).resolve()

        _require(
            deck_path
            == expected_deck,
            "deck path/identity mismatch",
        )

        _require(
            deck_path.is_file(),
            "prepared deck is missing",
        )

        _require(
            _sha256(deck_path)
            == deck_sha256,
            "prepared deck SHA-256 drift",
        )

        return VerifiedPreparedTrialEvidence(
            run_id=run_id,
            trial_index=trial_index,
            deck_path=deck_path,
            deck_sha256=deck_sha256,
        )

    return verify
