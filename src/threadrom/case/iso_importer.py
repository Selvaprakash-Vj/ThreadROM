"""Deterministic importer for ThreadROM-relevant ISO Open Data."""

from __future__ import annotations

from datetime import date
import json
from pathlib import Path
from typing import Any

from threadrom.case.iso_open_data import ISOOpenDataRecord
from threadrom.case.standard_catalog import resolve_standard_lifecycle


FASTENER_ICS_CODES = frozenset(
    {
        "21.040.10",
        "21.060.10",
        "21.060.20",
    }
)


def _required_int(
    payload: dict[str, Any],
    key: str,
) -> int:
    value = payload.get(key)

    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(
            f"ISO field {key!r} must be an integer."
        )

    return value


def _optional_int(
    payload: dict[str, Any],
    key: str,
) -> int | None:
    value = payload.get(key)

    if value is None:
        return None

    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(
            f"ISO field {key!r} must be an integer or null."
        )

    return value


def _required_string(
    payload: dict[str, Any],
    key: str,
) -> str:
    value = payload.get(key)

    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"ISO field {key!r} must be a non-blank string."
        )

    return value


def _optional_string(
    payload: dict[str, Any],
    key: str,
) -> str | None:
    value = payload.get(key)

    if value is None:
        return None

    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"ISO field {key!r} must be a non-blank string or null."
        )

    return value


def _english_title(
    payload: dict[str, Any],
) -> str:
    title = payload.get("title")

    if not isinstance(title, dict):
        raise ValueError(
            "ISO field 'title' must be an object."
        )

    value = title.get("en")

    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            "ISO English title must be present and non-blank."
        )

    return value


def _ics_codes(
    payload: dict[str, Any],
) -> tuple[str, ...]:
    value = payload.get("icsCode")

    if value is None:
        return ()

    if not isinstance(value, list):
        raise ValueError(
            "ISO field 'icsCode' must be a list or null."
        )

    codes: list[str] = []

    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(
                "ISO ICS entries must be non-blank strings."
            )

        codes.append(item)

    return tuple(sorted(set(codes)))


def _relationship_ids(
    payload: dict[str, Any],
    key: str,
) -> tuple[int, ...]:
    value = payload.get(key)

    if value is None:
        return ()

    if not isinstance(value, list):
        raise ValueError(
            f"ISO field {key!r} must be a list or null."
        )

    ids: list[int] = []

    for item in value:
        if (
            not isinstance(item, int)
            or isinstance(item, bool)
            or item <= 0
        ):
            raise ValueError(
                f"ISO field {key!r} must contain positive integer IDs."
            )

        ids.append(item)

    return tuple(sorted(set(ids)))


def _publication_date(
    payload: dict[str, Any],
) -> date | None:
    value = payload.get("publicationDate")

    if value is None:
        return None

    if not isinstance(value, str):
        raise ValueError(
            "ISO publicationDate must be a string or null."
        )

    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(
            f"Invalid ISO publication date {value!r}."
        ) from exc


def normalize_iso_open_data_payload(
    payload: dict[str, Any],
) -> ISOOpenDataRecord | None:
    """Normalize one relevant ISO payload, or ignore unrelated ICS data."""

    codes = _ics_codes(payload)
    matching_codes = tuple(
        code
        for code in codes
        if code in FASTENER_ICS_CODES
    )

    if not matching_codes:
        return None

    current_stage = _optional_int(
        payload,
        "currentStage",
    )

    return ISOOpenDataRecord(
        iso_deliverable_id=_required_int(payload, "id"),
        reference=_required_string(payload, "reference"),
        title_en=_english_title(payload),
        deliverable_type=_required_string(
            payload,
            "deliverableType",
        ),
        edition=_optional_int(payload, "edition"),
        ics_codes=matching_codes,
        current_stage=current_stage,
        lifecycle=resolve_standard_lifecycle(
            current_stage
        ),
        publication_date=_publication_date(payload),
        owner_committee=_optional_string(
            payload,
            "ownerCommittee",
        ),
        replaces=_relationship_ids(
            payload,
            "replaces",
        ),
        replaced_by=_relationship_ids(
            payload,
            "replacedBy",
        ),
    )


def load_iso_fastener_records(
    path: str | Path,
) -> tuple[ISOOpenDataRecord, ...]:
    """Load and deterministically order the ThreadROM ISO fastener universe."""

    source = Path(path)

    records: list[ISOOpenDataRecord] = []

    with source.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(
            handle,
            start=1,
        ):
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    "Invalid ISO JSONL at "
                    f"line {line_number}."
                ) from exc

            if not isinstance(payload, dict):
                raise ValueError(
                    "Each ISO JSONL row must contain an object."
                )

            normalized = normalize_iso_open_data_payload(
                payload
            )

            if normalized is not None:
                records.append(normalized)

    ids = tuple(
        record.iso_deliverable_id
        for record in records
    )

    if len(ids) != len(set(ids)):
        raise ValueError(
            "ISO fastener snapshot contains duplicate deliverable IDs."
        )

    return tuple(
        sorted(
            records,
            key=lambda record: (
                record.reference,
                record.iso_deliverable_id,
            ),
        )
    )
