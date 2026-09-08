"""Governed Phase-3 FEM Verification & Validation matrix."""

from __future__ import annotations

import math
import tomllib

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping


_ALLOWED_CRITERION_TYPES = frozenset(
    {
        "hard",
        "conditional",
        "limitation",
    }
)


@dataclass(frozen=True, slots=True)
class VerificationValidationReference:
    reference_id: str
    authority: str
    identifier: str
    title: str
    reference_type: str
    note: str | None = None


@dataclass(frozen=True, slots=True)
class VerificationValidationCheck:
    check_id: str
    title: str
    category: str
    criterion_type: str
    cadence: str
    evidence: str
    criterion: str
    reference_ids: tuple[str, ...]
    current_run_applicable: bool
    thresholds: Mapping[str, float]
    gate_state: str | None = None
    execution_phase: int | None = None
    execution_checkpoint: str | None = None
    required_case_ids: tuple[str, ...] = ()
    required_case_roles: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Phase3VerificationValidationMatrix:
    matrix_id: str
    phase: int
    checkpoint: str
    status: str
    principle: str
    references: tuple[
        VerificationValidationReference,
        ...,
    ]
    checks: tuple[
        VerificationValidationCheck,
        ...,
    ]

    def check(
        self,
        check_id: str,
    ) -> VerificationValidationCheck:
        matches = tuple(
            check
            for check in self.checks
            if check.check_id == check_id
        )

        if len(matches) != 1:
            raise KeyError(
                f"Expected exactly one V&V check {check_id!r}; "
                f"found {len(matches)}."
            )

        return matches[0]


def _require_text(
    value: object,
    name: str,
) -> str:
    text = str(value).strip()

    if not text:
        raise ValueError(
            f"{name} must not be blank."
        )

    return text


def load_phase3_verification_validation_matrix(
    path: Path,
) -> Phase3VerificationValidationMatrix:
    """Load and fail-closed validate the governed Phase-3 V&V matrix."""

    with path.open("rb") as stream:
        raw = tomllib.load(stream)

    identity = raw["identity"]

    references = tuple(
        VerificationValidationReference(
            reference_id=_require_text(
                item["reference_id"],
                "reference_id",
            ),
            authority=_require_text(
                item["authority"],
                "authority",
            ),
            identifier=_require_text(
                item["identifier"],
                "identifier",
            ),
            title=_require_text(
                item["title"],
                "reference title",
            ),
            reference_type=_require_text(
                item["reference_type"],
                "reference_type",
            ),
            note=(
                _require_text(
                    item["note"],
                    "reference note",
                )
                if "note" in item
                else None
            ),
        )
        for item in raw.get(
            "references",
            (),
        )
    )

    reference_ids = tuple(
        item.reference_id
        for item in references
    )

    if len(reference_ids) != len(
        set(reference_ids)
    ):
        raise ValueError(
            "V&V reference IDs must be unique."
        )

    known_references = frozenset(
        reference_ids
    )

    checks: list[
        VerificationValidationCheck
    ] = []

    for item in raw.get(
        "checks",
        (),
    ):
        criterion_type = _require_text(
            item["criterion_type"],
            "criterion_type",
        )

        if (
            criterion_type
            not in _ALLOWED_CRITERION_TYPES
        ):
            raise ValueError(
                "Unsupported V&V criterion type: "
                f"{criterion_type}"
            )

        check_references = tuple(
            _require_text(
                value,
                "check reference ID",
            )
            for value in item.get(
                "reference_ids",
                (),
            )
        )

        unknown = (
            frozenset(check_references)
            - known_references
        )

        if unknown:
            raise ValueError(
                "V&V check references unknown external IDs: "
                + ", ".join(
                    sorted(unknown)
                )
            )

        threshold_values: dict[
            str,
            float,
        ] = {}

        for key, value in item.get(
            "thresholds",
            {},
        ).items():
            numeric = float(value)

            if (
                not math.isfinite(numeric)
                or numeric <= 0.0
            ):
                raise ValueError(
                    "V&V thresholds must be finite and positive: "
                    f"{key}={value!r}"
                )

            threshold_values[
                str(key)
            ] = numeric

        checks.append(
            VerificationValidationCheck(
                check_id=_require_text(
                    item["check_id"],
                    "check_id",
                ),
                title=_require_text(
                    item["title"],
                    "check title",
                ),
                category=_require_text(
                    item["category"],
                    "check category",
                ),
                criterion_type=(
                    criterion_type
                ),
                cadence=_require_text(
                    item["cadence"],
                    "check cadence",
                ),
                evidence=_require_text(
                    item["evidence"],
                    "check evidence",
                ),
                criterion=_require_text(
                    item["criterion"],
                    "check criterion",
                ),
                reference_ids=(
                    check_references
                ),
                current_run_applicable=bool(
                    item[
                        "current_run_applicable"
                    ]
                ),
                thresholds=MappingProxyType(
                    threshold_values
                ),
                gate_state=(
                    _require_text(
                        item["gate_state"],
                        "gate_state",
                    )
                    if "gate_state" in item
                    else None
                ),
                execution_phase=(
                    int(item["execution_phase"])
                    if "execution_phase" in item
                    else None
                ),
                execution_checkpoint=(
                    _require_text(
                        item["execution_checkpoint"],
                        "execution_checkpoint",
                    )
                    if "execution_checkpoint" in item
                    else None
                ),
                required_case_ids=tuple(
                    _require_text(
                        value,
                        "required_case_id",
                    )
                    for value in item.get(
                        "required_case_ids",
                        (),
                    )
                ),
                required_case_roles=tuple(
                    _require_text(
                        value,
                        "required_case_role",
                    )
                    for value in item.get(
                        "required_case_roles",
                        (),
                    )
                ),
            )
        )

    check_ids = tuple(
        item.check_id
        for item in checks
    )

    if len(check_ids) != len(
        set(check_ids)
    ):
        raise ValueError(
            "V&V check IDs must be unique."
        )

    # Every concrete required case ID must already resolve through
    # the governed Phase-3 pilot case registry. Future selections are
    # represented separately as required_case_roles and therefore cannot
    # hide a misspelled concrete case ID.
    from threadrom.factory.pilot_doe import (
        build_phase3_cp7_pilot_doe,
    )

    known_case_ids = frozenset(
        item.case_id.value
        for item in build_phase3_cp7_pilot_doe().cases
    )

    for check in checks:
        unknown_case_ids = (
            frozenset(check.required_case_ids)
            - known_case_ids
        )

        if unknown_case_ids:
            raise ValueError(
                f"V&V check {check.check_id} references "
                "unregistered required case IDs: "
                + ", ".join(
                    sorted(unknown_case_ids)
                )
            )

    return Phase3VerificationValidationMatrix(
        matrix_id=_require_text(
            identity["matrix_id"],
            "matrix_id",
        ),
        phase=int(
            identity["phase"]
        ),
        checkpoint=_require_text(
            identity["checkpoint"],
            "checkpoint",
        ),
        status=_require_text(
            identity["status"],
            "status",
        ),
        principle=_require_text(
            identity["principle"],
            "principle",
        ),
        references=references,
        checks=tuple(
            checks
        ),
    )
