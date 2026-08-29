"""Extract governed preload-calibration measurements from CalculiX."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Protocol

from threadrom.factory.preload_calibration_controller import (
    ClampForceMeasurement,
)
from threadrom.postprocessing.calculix_contact_statistics import (
    CalculixContactStatisticsRecord,
    parse_contact_statistics_records,
)


_REQUIRED_CLAMP_PAIR_NAMES = (
    "under_head",
    "nut_bearing",
    "member_interface",
)

_THREAD_PAIR_NAME = "thread"


class CalibrationContactPair(Protocol):
    """Minimum contact-pair metadata required by calibration extraction."""

    name: str
    slave_surface: str
    master_surface: str


@dataclass(frozen=True, slots=True)
class ClampForceExtraction:
    """Synchronized final contact-force result for one solved trial."""

    time: float
    measurement: ClampForceMeasurement
    thread_normal_force_n: float


def _pair_record_key(
    record: CalculixContactStatisticsRecord,
) -> tuple[str, str]:
    return (
        record.slave_surface,
        record.master_surface,
    )


def extract_clamp_force_measurement_from_dat(
    *,
    dat_path: Path,
    contact_pairs: Iterable[CalibrationContactPair],
) -> ClampForceExtraction:
    """Extract final synchronized clamp forces from native CFN statistics.

    CalculiX reports the contact normal force with a solver sign convention
    where positive denotes tension. ThreadROM's certified calibration
    convention treats clamp force as the physical magnitude, therefore
    ``abs(normal_force_n)`` is used for every required contact path.

    Pair identities and surface names come from the current case-specific
    contact definition; no legacy surface assumptions are embedded here.
    """

    if not dat_path.exists() or dat_path.stat().st_size <= 0:
        raise FileNotFoundError(
            f"Valid CalculiX DAT file not found: {dat_path}"
        )

    pair_by_name: dict[str, CalibrationContactPair] = {}

    for pair in contact_pairs:
        if pair.name in pair_by_name:
            raise ValueError(
                f"Duplicate contact-pair name: {pair.name}"
            )

        pair_by_name[pair.name] = pair

    required_names = (
        *_REQUIRED_CLAMP_PAIR_NAMES,
        _THREAD_PAIR_NAME,
    )

    missing_definitions = tuple(
        name
        for name in required_names
        if name not in pair_by_name
    )

    if missing_definitions:
        raise ValueError(
            "Calibration contact definition is missing required pairs: "
            + ", ".join(missing_definitions)
        )

    records = parse_contact_statistics_records(
        dat_path.read_text(
            encoding="utf-8",
            errors="replace",
        )
    )

    if not records:
        raise RuntimeError(
            "No complete CalculiX contact-statistics records were found."
        )

    records_by_name: dict[
        str,
        list[CalculixContactStatisticsRecord],
    ] = {}

    for name in required_names:
        pair = pair_by_name[name]
        expected_key = (
            pair.slave_surface,
            pair.master_surface,
        )

        matching = [
            record
            for record in records
            if _pair_record_key(record) == expected_key
        ]

        if not matching:
            raise RuntimeError(
                "No contact-statistics records found for "
                f"pair {name!r}: "
                f"{expected_key[0]} -> {expected_key[1]}"
            )

        records_by_name[name] = matching

    common_times = set(
        record.time
        for record in records_by_name[
            required_names[0]
        ]
    )

    for name in required_names[1:]:
        common_times.intersection_update(
            record.time
            for record in records_by_name[name]
        )

    if not common_times:
        raise RuntimeError(
            "Required contact pairs have no synchronized result time."
        )

    final_time = max(common_times)

    if not math.isfinite(final_time):
        raise RuntimeError(
            "Final synchronized contact-result time is not finite."
        )

    final_record_by_name: dict[
        str,
        CalculixContactStatisticsRecord,
    ] = {}

    for name in required_names:
        matching_at_final_time = [
            record
            for record in records_by_name[name]
            if record.time == final_time
        ]

        if not matching_at_final_time:
            raise RuntimeError(
                f"Contact pair {name!r} is missing the final "
                "synchronized result time."
            )

        # Parser order follows DAT-file order. If a solver writes repeated
        # statistics at one time, the last complete record is authoritative.
        final_record_by_name[name] = matching_at_final_time[-1]

    def magnitude(name: str) -> float:
        value = abs(
            final_record_by_name[name].normal_force_n
        )

        if not math.isfinite(value) or value <= 0.0:
            raise RuntimeError(
                f"Contact pair {name!r} produced a non-positive "
                "or non-finite clamp-force magnitude."
            )

        return value

    measurement = ClampForceMeasurement(
        under_head_force_n=magnitude("under_head"),
        nut_bearing_force_n=magnitude("nut_bearing"),
        member_interface_force_n=magnitude("member_interface"),
    )

    return ClampForceExtraction(
        time=final_time,
        measurement=measurement,
        thread_normal_force_n=magnitude("thread"),
    )
