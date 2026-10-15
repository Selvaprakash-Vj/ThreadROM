"""Governed target-specific numerical certification for ROM admission.

The resolver is deliberately narrow and fail-closed.

A frozen target-specific authority may:
- PASS an exact governed case/mesh realization with positive certification,
- REJECT an exact governed case/mesh realization with explicit negative evidence,
- DEFER when no applicable certification authority exists.

Absence of evidence is never converted into PASS or REJECT.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Any, Mapping, Sequence


NUMERICAL_CERTIFICATION_SCHEMA = (
    "threadrom.rom_numerical_certification_authority.v1"
)


class NumericalCertificationDecision(str, Enum):
    PASS = "PASS"
    REJECTED = "REJECTED"
    DEFERRED = "DEFERRED"


@dataclass(frozen=True)
class NumericalCertificationResult:
    decision: NumericalCertificationDecision
    authority_id: str
    reason_code: str | None
    detail: str
    certification_id: str | None

    @property
    def passed(self) -> bool:
        return (
            self.decision
            is NumericalCertificationDecision.PASS
        )


def _mapping(
    value: Any,
    *,
    name: str,
) -> Mapping[str, Any]:

    if not isinstance(
        value,
        Mapping,
    ):
        raise ValueError(
            f"{name} must be a mapping."
        )

    return value


def _sequence(
    value: Any,
    *,
    name: str,
) -> Sequence[Any]:

    if (
        not isinstance(
            value,
            Sequence,
        )
        or isinstance(
            value,
            (str, bytes),
        )
    ):
        raise ValueError(
            f"{name} must be a sequence."
        )

    return value


def evaluate_rom_numerical_certification(
    *,
    case_id: str | None,
    case_hash: str | None,
    mesh_policy_name: str | None,
    target_field: str,
    authority: Mapping[str, Any],
) -> NumericalCertificationResult:

    record = _mapping(
        authority,
        name="authority",
    )

    if (
        record.get(
            "schema"
        )
        != NUMERICAL_CERTIFICATION_SCHEMA
    ):
        raise ValueError(
            "Unsupported numerical-certification authority schema."
        )

    if record.get(
        "record_status"
    ) != "FINAL":
        raise ValueError(
            "Numerical-certification authority must be FINAL."
        )

    authority_id = record.get(
        "authority_id"
    )

    if (
        not isinstance(
            authority_id,
            str,
        )
        or not authority_id
    ):
        raise ValueError(
            "Numerical-certification authority requires authority_id."
        )

    authority_target = record.get(
        "target_field"
    )

    if (
        not isinstance(
            authority_target,
            str,
        )
        or not authority_target
    ):
        raise ValueError(
            "Numerical-certification authority requires target_field."
        )

    if target_field != authority_target:
        raise ValueError(
            "Requested target field does not match numerical-certification authority."
        )

    relative_limit = record.get(
        "relative_limit"
    )

    if (
        isinstance(
            relative_limit,
            bool,
        )
        or not isinstance(
            relative_limit,
            (int, float),
        )
        or not isfinite(
            float(
                relative_limit
            )
        )
        or float(
            relative_limit
        ) <= 0.0
    ):
        raise ValueError(
            "Numerical-certification relative limit must be finite and positive."
        )

    governance = _mapping(
        record.get(
            "governance"
        ),
        name="authority.governance",
    )

    if governance.get(
        "absence_of_authority_defers"
    ) is not True:
        raise ValueError(
            "Numerical-certification authority must defer when evidence is absent."
        )

    if governance.get(
        "extrapolation_forbidden"
    ) is not True:
        raise ValueError(
            "Numerical-certification authority must forbid extrapolation."
        )

    if (
        case_id is None
        or case_hash is None
        or mesh_policy_name is None
    ):
        return NumericalCertificationResult(
            decision=(
                NumericalCertificationDecision.DEFERRED
            ),
            authority_id=authority_id,
            reason_code="CERTIFICATION_INPUTS_INCOMPLETE",
            detail=(
                "Case identity or mesh-policy identity required for "
                "target-specific numerical certification is incomplete."
            ),
            certification_id=None,
        )

    certifications = _sequence(
        record.get(
            "certifications"
        ),
        name="authority.certifications",
    )

    matches: list[
        Mapping[str, Any]
    ] = []

    for raw in certifications:

        certification = _mapping(
            raw,
            name="certification",
        )

        match = _mapping(
            certification.get(
                "match"
            ),
            name="certification.match",
        )

        if (
            match.get(
                "case_id"
            )
            == case_id
            and match.get(
                "case_hash"
            )
            == case_hash
            and match.get(
                "mesh_policy_name"
            )
            == mesh_policy_name
        ):
            matches.append(
                certification
            )

    if len(
        matches
    ) > 1:
        raise ValueError(
            "Ambiguous numerical-certification authority: "
            "multiple exact certifications match one candidate."
        )

    if not matches:
        return NumericalCertificationResult(
            decision=(
                NumericalCertificationDecision.DEFERRED
            ),
            authority_id=authority_id,
            reason_code="NO_APPLICABLE_CERTIFICATION_AUTHORITY",
            detail=(
                "No exact target-specific numerical-certification authority "
                "covers this case and mesh-policy identity."
            ),
            certification_id=None,
        )

    certification = matches[0]

    certification_id = certification.get(
        "certification_id"
    )

    if (
        not isinstance(
            certification_id,
            str,
        )
        or not certification_id
    ):
        raise ValueError(
            "Matching numerical certification requires certification_id."
        )

    disposition = certification.get(
        "decision"
    )

    if disposition == "PASS":

        evidence_limit = certification.get(
            "relative_limit"
        )

        if (
            isinstance(
                evidence_limit,
                bool,
            )
            or not isinstance(
                evidence_limit,
                (int, float),
            )
            or float(
                evidence_limit
            )
            != float(
                relative_limit
            )
        ):
            raise ValueError(
                "PASS certification relative limit does not match authority."
            )

        if certification.get(
            "extrapolation_authorized"
        ) is not False:
            raise ValueError(
                "PASS certification must explicitly forbid extrapolation."
            )

        return NumericalCertificationResult(
            decision=(
                NumericalCertificationDecision.PASS
            ),
            authority_id=authority_id,
            reason_code=None,
            detail=(
                "Exact case and mesh-policy identity are covered by a "
                "FINAL target-specific numerical certification satisfying "
                "the frozen relative limit."
            ),
            certification_id=certification_id,
        )

    if disposition == "REJECTED":

        return NumericalCertificationResult(
            decision=(
                NumericalCertificationDecision.REJECTED
            ),
            authority_id=authority_id,
            reason_code="NUMERICAL_CERTIFICATION_FAILED",
            detail=(
                "Exact case and mesh-policy identity are covered by "
                "explicit negative target-specific numerical evidence."
            ),
            certification_id=certification_id,
        )

    raise ValueError(
        "Unsupported numerical-certification decision."
    )
