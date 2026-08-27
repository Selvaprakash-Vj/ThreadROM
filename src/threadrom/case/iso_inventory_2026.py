"""ThreadROM ISO fastener-standard inventory snapshot.

Verified against the public ISO catalogue on 2026-08-27.

This module stores catalogue metadata only. Detailed copyrighted standard
tables are not reproduced here. Capability remains METADATA_ONLY unless
ThreadROM separately owns and verifies the engineering data required for a
higher support level.
"""

from __future__ import annotations

from datetime import date

from threadrom.case.standard_catalog import (
    FastenerProductKind,
    ISOStandardCatalogRecord,
    StandardCapability,
    StandardLifecycle,
    StandardRole,
)
from threadrom.case.standard_inventory import ISOStandardInventory


def _published_thread_standard(
    reference: str,
    title: str,
    role: StandardRole,
) -> ISOStandardCatalogRecord:
    """Create one published metric fastener-thread catalogue record."""

    return ISOStandardCatalogRecord(
        reference=reference,
        title=title,
        lifecycle=StandardLifecycle.PUBLISHED,
        role=role,
        product_kind=FastenerProductKind.THREAD,
        ics_code="21.040.10",
        capability=StandardCapability.METADATA_ONLY,
    )


METRIC_FASTENER_THREAD_RECORDS = (
    _published_thread_standard(
        "ISO 68-1:2023",
        "Metric screw-thread basic and design profiles",
        StandardRole.THREAD_SYSTEM,
    ),
    _published_thread_standard(
        "ISO 261:1998",
        "General-purpose metric screw-thread plan",
        StandardRole.THREAD_SYSTEM,
    ),
    _published_thread_standard(
        "ISO 262:2023",
        "Selected metric thread sizes for fasteners",
        StandardRole.THREAD_SYSTEM,
    ),
    _published_thread_standard(
        "ISO 724:2023",
        "General-purpose metric screw-thread basic dimensions",
        StandardRole.DIMENSIONAL_SUPPORT,
    ),
    _published_thread_standard(
        "ISO 965-1:2026",
        "Metric screw-thread tolerance principles and basic data",
        StandardRole.TOLERANCES,
    ),
    _published_thread_standard(
        "ISO 965-2:2024",
        "Metric internal and external thread size limits",
        StandardRole.TOLERANCES,
    ),
    _published_thread_standard(
        "ISO 965-3:2021",
        "Metric screw-thread limit deviations",
        StandardRole.TOLERANCES,
    ),
    _published_thread_standard(
        "ISO 965-4:2025",
        "Tolerance limits for galvanized external metric threads",
        StandardRole.TOLERANCES,
    ),
    _published_thread_standard(
        "ISO 965-5:2025",
        "Tolerance limits for mating galvanized metric threads",
        StandardRole.TOLERANCES,
    ),
    _published_thread_standard(
        "ISO 965-6:2025",
        "Preferred metric screw-thread tolerance size limits",
        StandardRole.TOLERANCES,
    ),
)


ISO_FASTENER_STANDARD_INVENTORY_2026_08_27 = ISOStandardInventory(
    inventory_id="ISO-FASTENERS-2026-08-27",
    verified_on=date(2026, 8, 27),
    source_urls=(
        "https://www.iso.org/ics/21.040.10/x/",
        "https://www.iso.org/ics/21.060.10/x/",
        "https://www.iso.org/ics/21.060.20/x/",
    ),
    records=METRIC_FASTENER_THREAD_RECORDS,
)
