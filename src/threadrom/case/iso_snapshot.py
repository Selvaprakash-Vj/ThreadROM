"""Canonical governed snapshots of ThreadROM ISO Open Data."""

from __future__ import annotations

from collections import Counter
from datetime import date
import hashlib
import json
from pathlib import Path

from threadrom.case.iso_open_data import ISOOpenDataRecord


def _record_payload(
    record: ISOOpenDataRecord,
) -> dict[str, object]:
    """Serialize one normalized ISO record deterministically."""

    return {
        "iso_deliverable_id": record.iso_deliverable_id,
        "reference": record.reference,
        "title_en": record.title_en,
        "deliverable_type": record.deliverable_type,
        "edition": record.edition,
        "ics_codes": list(record.ics_codes),
        "current_stage": record.current_stage,
        "lifecycle": record.lifecycle.value,
        "publication_date": (
            record.publication_date.isoformat()
            if record.publication_date is not None
            else None
        ),
        "owner_committee": record.owner_committee,
        "replaces": list(record.replaces),
        "replaced_by": list(record.replaced_by),
    }


def write_iso_fastener_snapshot(
    *,
    records: tuple[ISOOpenDataRecord, ...],
    source_path: str | Path,
    output_path: str | Path,
    snapshot_date: date,
    source_url: str,
) -> str:
    """Write a canonical governed ISO fastener metadata snapshot.

    Returns the SHA256 digest of the generated snapshot.
    """

    source = Path(source_path)
    output = Path(output_path)

    source_bytes = source.read_bytes()
    source_sha256 = hashlib.sha256(
        source_bytes
    ).hexdigest()

    lifecycle_counts = Counter(
        record.lifecycle.value
        for record in records
    )

    ics_counts = Counter(
        code
        for record in records
        for code in record.ics_codes
    )

    payload = {
        "schema_version": 1,
        "snapshot_id": (
            "THREADROM-ISO-FASTENERS-"
            f"{snapshot_date.isoformat()}"
        ),
        "snapshot_date": snapshot_date.isoformat(),
        "source": {
            "provider": "ISO Open Data",
            "url": source_url,
            "sha256": source_sha256,
        },
        "scope": {
            "ics_codes": [
                "21.040.10",
                "21.060.10",
                "21.060.20",
            ],
            "record_count": len(records),
            "lifecycle_counts": dict(
                sorted(lifecycle_counts.items())
            ),
            "ics_record_counts": dict(
                sorted(ics_counts.items())
            ),
        },
        "records": [
            _record_payload(record)
            for record in records
        ],
    }

    encoded = (
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    output.write_bytes(encoded)

    return hashlib.sha256(encoded).hexdigest()
