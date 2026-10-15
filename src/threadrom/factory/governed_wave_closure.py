"""Governed wave-level acceptance evidence and immutable closure.

The case-level governed physics certificate remains the source of truth.
This module only closes a wave after every authorized case has exactly
one durable ACCEPTED registry row backed by a recoverable certificate.

This module does not:
- launch FEM,
- create execution authority,
- infer physics acceptance without a certificate,
- access holdouts,
- admit ROM data,
- certify rotational-moment equilibrium.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

from threadrom.factory.diversified_fem_physics_certificate import (
    recover_governed_physics_certificate,
)


_SHA256 = re.compile(
    r"^[0-9a-f]{64}$"
)

_CASE_RUN_ID = re.compile(
    r"^trm_fem_[0-9a-f]{12}$"
)

_CERTIFICATE_SCHEMA = (
    "threadrom.diversified_governed_physics_certificate.v1"
)

_ACCEPTED_DISPOSITION = (
    "GOVERNED_FULL_PHYSICS_ACCEPTED"
)

_ROTATIONAL_STATUS = (
    "not_assessed"
)


def _require(
    condition: bool,
    message: str,
) -> None:
    if not condition:
        raise RuntimeError(
            message
        )


def sha256_file(
    path: Path,
) -> str:
    digest = hashlib.sha256()

    with Path(
        path
    ).open(
        "rb"
    ) as stream:
        for chunk in iter(
            lambda: stream.read(
                8 * 1024 * 1024
            ),
            b"",
        ):
            digest.update(
                chunk
            )

    return digest.hexdigest()


def canonical_json_bytes(
    payload: Mapping[
        str,
        object,
    ],
) -> bytes:
    return (
        json.dumps(
            payload,
            sort_keys=True,
            separators=(
                ",",
                ":",
            ),
            ensure_ascii=True,
            allow_nan=False,
        )
        + "\n"
    ).encode(
        "utf-8"
    )


@dataclass(
    frozen=True,
    slots=True,
)
class GovernedWaveExpectedCase:
    case_id: str
    case_hash: str
    case_run_id: str

    def __post_init__(
        self,
    ) -> None:
        if (
            not isinstance(
                self.case_id,
                str,
            )
            or not self.case_id.strip()
            or self.case_id
            != self.case_id.strip()
        ):
            raise ValueError(
                "Invalid governed case identity."
            )

        if (
            not isinstance(
                self.case_hash,
                str,
            )
            or _SHA256.fullmatch(
                self.case_hash
            )
            is None
        ):
            raise ValueError(
                "Invalid governed case hash."
            )

        if (
            not isinstance(
                self.case_run_id,
                str,
            )
            or _CASE_RUN_ID.fullmatch(
                self.case_run_id
            )
            is None
        ):
            raise ValueError(
                "Invalid governed case-run identity."
            )



@dataclass(
    frozen=True,
    slots=True,
)
class GovernedCaseAcceptanceEvidence:
    case_id: str
    case_hash: str
    case_run_id: str
    run_id: str
    trial_index: int
    acceptance_record: str
    certificate_sha256: str
    hard_gate_count: int
    accepted_increment_count: int
    rotational_moment_equilibrium_status: str


@dataclass(
    frozen=True,
    slots=True,
)
class GovernedWaveAcceptanceEvidence:
    wave_id: str
    authorized_case_count: int
    cases: tuple[
        GovernedCaseAcceptanceEvidence,
        ...,
    ]

    def __post_init__(
        self,
    ) -> None:
        if (
            not isinstance(
                self.wave_id,
                str,
            )
            or not self.wave_id.strip()
        ):
            raise ValueError(
                "Invalid governed wave identity."
            )

        if (
            type(
                self.authorized_case_count
            )
            is not int
            or self.authorized_case_count < 1
        ):
            raise ValueError(
                "Invalid authorized case count."
            )

        if (
            len(
                self.cases
            )
            != self.authorized_case_count
        ):
            raise RuntimeError(
                "Wave acceptance evidence count drift."
            )

        ids = tuple(
            case.case_id
            for case in self.cases
        )

        if len(
            ids
        ) != len(
            set(
                ids
            )
        ):
            raise RuntimeError(
                "Duplicate accepted case identity."
            )


def _resolve_repo_path(
    *,
    repo_root: Path,
    value: str,
) -> Path:
    candidate = Path(
        value
    )

    if not candidate.is_absolute():
        candidate = (
            repo_root
            / candidate
        )

    resolved = candidate.resolve()

    try:
        resolved.relative_to(
            repo_root
        )
    except ValueError as exc:
        raise RuntimeError(
            "Governed acceptance record escapes repository root."
        ) from exc

    return resolved


def _load_certificate(
    path: Path,
) -> dict:
    _require(
        path.is_file(),
        (
            "Governed acceptance certificate missing: "
            f"{path}"
        ),
    )

    try:
        value = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
    ) as exc:
        raise RuntimeError(
            "Governed acceptance certificate is unreadable."
        ) from exc

    _require(
        isinstance(
            value,
            dict,
        ),
        "Governed acceptance certificate root must be a mapping.",
    )

    return value


def _validate_recovered_certificate(
    *,
    certificate: Mapping[
        str,
        object,
    ],
    expected: GovernedWaveExpectedCase,
    run_id: str,
    trial_index: int,
) -> tuple[
    int,
    int,
]:
    _require(
        certificate.get(
            "schema"
        )
        == _CERTIFICATE_SCHEMA,
        "Unexpected governed physics certificate schema.",
    )

    _require(
        certificate.get(
            "record_status"
        )
        == "FINAL",
        "Governed physics certificate is not FINAL.",
    )

    _require(
        certificate.get(
            "disposition"
        )
        == _ACCEPTED_DISPOSITION,
        "Governed physics certificate is not accepted.",
    )

    identity = {
        "case_id": expected.case_id,
        "case_hash": expected.case_hash,
        "case_run_id": expected.case_run_id,
        "run_id": run_id,
        "trial_index": trial_index,
    }

    for key, value in identity.items():
        _require(
            certificate.get(
                key
            )
            == value,
            (
                "Governed certificate identity drift: "
                f"{key}"
            ),
        )

    for key in (
        "additional_fem_authorized",
        "artifact_retirement_authorized",
        "holdout_access_authorized",
        "solver_launch_authorized",
        "independent_human_review",
        "independent_human_review_claimed",
    ):
        _require(
            certificate.get(
                key
            )
            is False,
            (
                "Governed certificate unexpectedly broadens "
                f"authority: {key}"
            ),
        )

    artifacts = certificate.get(
        "artifact_sha256"
    )

    sources = certificate.get(
        "source_sha256"
    )

    _require(
        isinstance(
            artifacts,
            dict,
        )
        and bool(
            artifacts
        ),
        "Governed certificate lacks artifact fingerprints.",
    )

    _require(
        isinstance(
            sources,
            dict,
        )
        and bool(
            sources
        ),
        "Governed certificate lacks source fingerprints.",
    )

    assessment = certificate.get(
        "assessment"
    )

    _require(
        isinstance(
            assessment,
            dict,
        ),
        "Governed certificate lacks assessment payload.",
    )

    for key, value in identity.items():
        _require(
            assessment.get(
                key
            )
            == value,
            (
                "Embedded assessment identity drift: "
                f"{key}"
            ),
        )

    _require(
        assessment.get(
            "calibration_disposition"
        )
        == "accept",
        "Wave closure requires governed calibration ACCEPT.",
    )

    _require(
        assessment.get(
            "next_trial_run_id"
        )
        is None,
        "Accepted case still requests another trial.",
    )

    _require(
        assessment.get(
            "equilibrium_status"
        )
        == "pass",
        "Translational equilibrium is not PASS.",
    )

    _require(
        assessment.get(
            "full_physics_passed"
        )
        is True
        and assessment.get(
            "full_physics_accepted"
        )
        is True,
        "Full governed physics is not accepted.",
    )

    _require(
        assessment.get(
            "all_hard_gates_passed"
        )
        is True,
        "Not all governed physics hard gates passed.",
    )

    _require(
        assessment.get(
            "failed_governed_checks"
        )
        == [],
        "Governed certificate contains failed checks.",
    )

    _require(
        assessment.get(
            "rotational_moment_equilibrium_status"
        )
        == _ROTATIONAL_STATUS,
        (
            "Unexpected rotational-moment equilibrium "
            "certification claim."
        ),
    )

    hard_gate_count = assessment.get(
        "hard_gate_count"
    )

    hard_gates_passed = assessment.get(
        "hard_gates_passed"
    )

    accepted_increments = assessment.get(
        "accepted_increment_count"
    )

    _require(
        type(
            hard_gate_count
        )
        is int
        and hard_gate_count >= 1,
        "Invalid governed hard-gate count.",
    )

    _require(
        hard_gates_passed
        == hard_gate_count,
        "Governed hard-gate pass count drift.",
    )

    _require(
        type(
            accepted_increments
        )
        is int
        and accepted_increments >= 1,
        "Invalid accepted-increment count.",
    )

    return (
        hard_gate_count,
        accepted_increments,
    )


def recover_governed_wave_acceptance_evidence(
    *,
    repo_root: Path,
    wave_id: str,
    factory_database_path: Path,
    expected_cases: tuple[
        GovernedWaveExpectedCase,
        ...,
    ],
    certificate_recoverer: Callable = (
        recover_governed_physics_certificate
    ),
) -> GovernedWaveAcceptanceEvidence:
    root = Path(
        repo_root
    ).resolve(
        strict=True
    )

    database = Path(
        str(
            factory_database_path
        )
    )

    if not database.is_absolute():
        database = (
            root
            / database
        )

    database = database.resolve(
        strict=True
    )

    try:
        database.relative_to(
            root
        )
    except ValueError as exc:
        raise RuntimeError(
            "Factory database escapes repository root."
        ) from exc

    _require(
        expected_cases,
        "No governed cases supplied for wave closure.",
    )

    expected_by_id = {
        case.case_id: case
        for case in expected_cases
    }

    _require(
        len(
            expected_by_id
        )
        == len(
            expected_cases
        ),
        "Duplicate expected governed case identity.",
    )

    uri = (
        "file:"
        + database.as_posix()
        + "?mode=ro"
    )

    connection = sqlite3.connect(
        uri,
        uri=True,
    )

    connection.row_factory = sqlite3.Row

    try:
        rows = connection.execute(
            """
            SELECT
                case_id,
                case_hash,
                trial_index,
                run_id,
                state,
                acceptance_record
            FROM fem_jobs
            WHERE lower(state) = 'accepted'
            ORDER BY
                case_id,
                trial_index
            """
        ).fetchall()
    finally:
        connection.close()

    actual_ids = tuple(
        row[
            "case_id"
        ]
        for row in rows
    )

    _require(
        len(
            actual_ids
        )
        == len(
            expected_cases
        ),
        (
            "Accepted registry row count differs from "
            "authorized wave case count."
        ),
    )

    _require(
        set(
            actual_ids
        )
        == set(
            expected_by_id
        ),
        (
            "Accepted registry cohort differs from "
            "authorized wave cohort."
        ),
    )

    _require(
        len(
            actual_ids
        )
        == len(
            set(
                actual_ids
            )
        ),
        "A governed case has multiple ACCEPTED registry rows.",
    )

    evidence = []

    for row in rows:
        expected = expected_by_id[
            row[
                "case_id"
            ]
        ]

        _require(
            row[
                "case_hash"
            ]
            == expected.case_hash,
            "Accepted registry case hash drift.",
        )

        trial_index = row[
            "trial_index"
        ]

        _require(
            type(
                trial_index
            )
            is int
            and trial_index >= 1,
            "Invalid accepted registry trial index.",
        )

        run_id = row[
            "run_id"
        ]

        _require(
            isinstance(
                run_id,
                str,
            )
            and run_id
            == (
                f"{expected.case_run_id}"
                f"_cal_{trial_index:02d}"
            ),
            "Accepted registry run identity drift.",
        )

        record = row[
            "acceptance_record"
        ]

        _require(
            isinstance(
                record,
                str,
            )
            and bool(
                record.strip()
            ),
            "ACCEPTED registry row lacks acceptance record.",
        )

        certificate_path = _resolve_repo_path(
            repo_root=root,
            value=record,
        )

        certificate = _load_certificate(
            certificate_path
        )

        sources = certificate.get(
            "source_sha256"
        )

        _require(
            isinstance(
                sources,
                dict,
            )
            and all(
                isinstance(
                    key,
                    str,
                )
                and bool(
                    key.strip()
                )
                for key in sources
            ),
            "Governed certificate source fingerprint map is invalid.",
        )

        recovered = certificate_recoverer(
            repo_root=root,
            run_dir=certificate_path.parent,
            case_id=expected.case_id,
            case_hash=expected.case_hash,
            case_run_id=expected.case_run_id,
            run_id=run_id,
            trial_index=trial_index,
            source_paths=tuple(
                sources.keys()
            ),
        )

        _require(
            recovered is not None,
            (
                f"{run_id}: governed physics "
                "certificate could not be recovered."
            ),
        )

        hard_gate_count, accepted_increments = (
            _validate_recovered_certificate(
                certificate=recovered,
                expected=expected,
                run_id=run_id,
                trial_index=trial_index,
            )
        )

        evidence.append(
            GovernedCaseAcceptanceEvidence(
                case_id=expected.case_id,
                case_hash=expected.case_hash,
                case_run_id=expected.case_run_id,
                run_id=run_id,
                trial_index=trial_index,
                acceptance_record=record,
                certificate_sha256=(
                    sha256_file(
                        certificate_path
                    )
                ),
                hard_gate_count=hard_gate_count,
                accepted_increment_count=(
                    accepted_increments
                ),
                rotational_moment_equilibrium_status=(
                    _ROTATIONAL_STATUS
                ),
            )
        )

    return GovernedWaveAcceptanceEvidence(
        wave_id=wave_id,
        authorized_case_count=len(
            expected_cases
        ),
        cases=tuple(
            sorted(
                evidence,
                key=lambda item: item.case_id,
            )
        ),
    )


def build_governed_wave_closure_record(
    *,
    evidence: GovernedWaveAcceptanceEvidence,
    execution_contract_sha256: str,
    owner_authorization_sha256: str,
    preparation_index_sha256: str,
) -> dict:
    for name, value in (
        (
            "execution contract",
            execution_contract_sha256,
        ),
        (
            "owner authorization",
            owner_authorization_sha256,
        ),
        (
            "preparation index",
            preparation_index_sha256,
        ),
    ):
        _require(
            isinstance(
                value,
                str,
            )
            and _SHA256.fullmatch(
                value
            )
            is not None,
            f"Invalid {name} SHA-256.",
        )

    return {
        "schema": (
            "threadrom.governed_wave_closure.v1"
        ),
        "record_status": "FINAL",
        "disposition": (
            "GOVERNED_WAVE_FULL_PHYSICS_CLOSED"
        ),
        "wave_id": evidence.wave_id,
        "authorized_case_count": (
            evidence.authorized_case_count
        ),
        "accepted_case_count": len(
            evidence.cases
        ),
        "execution_contract_sha256": (
            execution_contract_sha256
        ),
        "owner_authorization_sha256": (
            owner_authorization_sha256
        ),
        "preparation_index_sha256": (
            preparation_index_sha256
        ),
        "cases": [
            {
                "case_id": case.case_id,
                "case_hash": case.case_hash,
                "case_run_id": case.case_run_id,
                "run_id": case.run_id,
                "trial_index": (
                    case.trial_index
                ),
                "acceptance_record": (
                    case.acceptance_record
                ),
                "certificate_sha256": (
                    case.certificate_sha256
                ),
                "hard_gate_count": (
                    case.hard_gate_count
                ),
                "accepted_increment_count": (
                    case.accepted_increment_count
                ),
                "rotational_moment_equilibrium_status": (
                    case.rotational_moment_equilibrium_status
                ),
            }
            for case in evidence.cases
        ],
        "governance": {
            "new_fem_authorized": False,
            "additional_wave_authorized": False,
            "dataset_admission_authorized": False,
            "holdout_access_authorized": False,
            "artifact_retirement_authorized": False,
            "rotational_moment_equilibrium_certified": False,
        },
    }


def persist_governed_wave_closure(
    *,
    path: Path,
    record: Mapping[
        str,
        object,
    ],
) -> str:
    target = Path(
        path
    )

    encoded = canonical_json_bytes(
        record
    )

    digest = hashlib.sha256(
        encoded
    ).hexdigest()

    target.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if target.exists():
        _require(
            target.read_bytes()
            == encoded,
            (
                "Immutable governed wave closure "
                "conflict."
            ),
        )

        return digest

    target.write_bytes(
        encoded
    )

    return digest


def recover_governed_wave_closure(
    *,
    path: Path,
    expected_wave_id: str,
    expected_evidence: GovernedWaveAcceptanceEvidence,
) -> dict | None:
    target = Path(
        path
    )

    if not target.exists():
        return None

    raw = target.read_bytes()

    try:
        record = json.loads(
            raw
        )
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Governed wave closure JSON is invalid."
        ) from exc

    _require(
        isinstance(
            record,
            dict,
        ),
        "Governed wave closure root must be a mapping.",
    )

    _require(
        raw
        == canonical_json_bytes(
            record
        ),
        "Governed wave closure is not canonical.",
    )

    _require(
        record.get(
            "schema"
        )
        == "threadrom.governed_wave_closure.v1",
        "Unexpected governed wave closure schema.",
    )

    _require(
        record.get(
            "record_status"
        )
        == "FINAL",
        "Governed wave closure is not FINAL.",
    )

    _require(
        record.get(
            "disposition"
        )
        == "GOVERNED_WAVE_FULL_PHYSICS_CLOSED",
        "Governed wave closure disposition drift.",
    )

    _require(
        record.get(
            "wave_id"
        )
        == expected_wave_id,
        "Governed wave closure identity drift.",
    )

    _require(
        record.get(
            "authorized_case_count"
        )
        == expected_evidence.authorized_case_count
        and record.get(
            "accepted_case_count"
        )
        == expected_evidence.authorized_case_count,
        "Governed wave closure case-count drift.",
    )

    cases = record.get(
        "cases"
    )

    _require(
        isinstance(
            cases,
            list,
        ),
        "Governed wave closure lacks case evidence.",
    )

    expected_certificates = {
        case.case_id: (
            case.certificate_sha256
        )
        for case in expected_evidence.cases
    }

    actual_certificates = {
        row.get(
            "case_id"
        ): row.get(
            "certificate_sha256"
        )
        for row in cases
        if isinstance(
            row,
            dict,
        )
    }

    _require(
        actual_certificates
        == expected_certificates,
        "Governed wave closure certificate set drift.",
    )

    governance = record.get(
        "governance"
    )

    _require(
        governance
        == {
            "additional_wave_authorized": False,
            "artifact_retirement_authorized": False,
            "dataset_admission_authorized": False,
            "holdout_access_authorized": False,
            "new_fem_authorized": False,
            "rotational_moment_equilibrium_certified": False,
        },
        "Governed wave closure authority scope drift.",
    )

    return record