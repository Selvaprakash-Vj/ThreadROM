"""Geometry-aware bearing-gap extraction for complete-joint FRD results."""

from __future__ import annotations

import math
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from pathlib import Path

from threadrom.postprocessing.calculix_frd_displacement import (
    FrdDisplacementDataset,
    read_targeted_frd_displacement_datasets,
)

BOLT_UNDER_HEAD_SET = "BOLT_UNDER_HEAD_BEARING"
HEAD_MEMBER_BEARING_SET = "HEAD_MEMBER_HEAD_BEARING"
NUT_LOWER_BEARING_SET = "NUT_LOWER_BEARING"
NUT_MEMBER_BEARING_SET = "NUT_MEMBER_NUT_BEARING"

_REQUIRED_BEARING_NODE_SETS = (
    BOLT_UNDER_HEAD_SET,
    HEAD_MEMBER_BEARING_SET,
    NUT_LOWER_BEARING_SET,
    NUT_MEMBER_BEARING_SET,
)


@dataclass(frozen=True)
class CompleteJointBearingGapDataset:
    """Bearing-interface motion for one accepted FRD increment."""

    dataset_sequence: int
    step: int
    increment: int
    time: float
    bolt_under_head_mean_d3_mm: float
    head_member_bearing_mean_d3_mm: float
    nut_lower_bearing_mean_d3_mm: float
    nut_member_bearing_mean_d3_mm: float
    under_head_signed_gap_change_mm: float
    nut_bearing_signed_gap_change_mm: float


def read_calculix_node_sets(
    inp_path: Path,
    node_set_names: Collection[str],
) -> dict[str, tuple[int, ...]]:
    """Read selected explicit node sets from a CalculiX input deck."""

    requested_names = tuple(
        dict.fromkeys(name.strip().upper() for name in node_set_names if name.strip())
    )

    if not requested_names:
        raise ValueError("At least one CalculiX node-set name is required.")

    node_sets: dict[str, list[int]] = {name: [] for name in requested_names}

    active_name: str | None = None

    with inp_path.open(
        "r",
        encoding="utf-8",
        errors="strict",
    ) as inp_file:
        for line_number, raw_line in enumerate(
            inp_file,
            start=1,
        ):
            line = raw_line.strip()

            if not line or line.startswith("**"):
                continue

            if line.startswith("*"):
                active_name = None
                fields = tuple(field.strip() for field in line.split(","))

                if fields[0].upper() != "*NSET":
                    continue

                parameters: dict[str, str] = {}

                for field in fields[1:]:
                    if "=" not in field:
                        continue

                    key, value = field.split(
                        "=",
                        maxsplit=1,
                    )

                    parameters[key.strip().upper()] = value.strip().upper()

                node_set_name = parameters.get("NSET")

                if node_set_name not in node_sets:
                    continue

                if any(field.upper() == "GENERATE" for field in fields[1:]):
                    raise RuntimeError(
                        "Generated CalculiX node sets are unsupported: "
                        f"{node_set_name!r} at line {line_number}."
                    )

                active_name = node_set_name
                continue

            if active_name is None:
                continue

            for raw_node_id in line.split(","):
                token = raw_node_id.strip()

                if not token:
                    continue

                try:
                    node_id = int(token)

                except ValueError as error:
                    raise RuntimeError(
                        f"Invalid CalculiX node ID {token!r} at line {line_number}."
                    ) from error

                if node_id <= 0:
                    raise RuntimeError(f"CalculiX node IDs must be positive at line {line_number}.")

                node_sets[active_name].append(node_id)

    missing_names = tuple(name for name, node_ids in node_sets.items() if not node_ids)

    if missing_names:
        raise RuntimeError(
            "CalculiX input deck lacks populated node sets: " + ", ".join(missing_names)
        )

    result: dict[str, tuple[int, ...]] = {}

    for name, node_ids in node_sets.items():
        unique_node_ids = tuple(dict.fromkeys(node_ids))

        if len(unique_node_ids) != len(node_ids):
            raise RuntimeError(f"CalculiX node set {name!r} contains duplicate node IDs.")

        result[name] = unique_node_ids

    return result


def extract_complete_joint_bearing_gap_datasets(
    *,
    inp_path: Path,
    frd_path: Path,
) -> tuple[CompleteJointBearingGapDataset, ...]:
    """Extract geometry-aware bearing gaps for every accepted increment."""

    node_sets = read_calculix_node_sets(
        inp_path,
        _REQUIRED_BEARING_NODE_SETS,
    )

    target_node_ids = frozenset(node_id for node_ids in node_sets.values() for node_id in node_ids)

    displacement_datasets = read_targeted_frd_displacement_datasets(
        frd_path,
        target_node_ids=target_node_ids,
    )

    return tuple(
        _calculate_bearing_gap_dataset(
            dataset,
            node_sets=node_sets,
        )
        for dataset in displacement_datasets
    )


def _calculate_bearing_gap_dataset(
    dataset: FrdDisplacementDataset,
    *,
    node_sets: Mapping[str, tuple[int, ...]],
) -> CompleteJointBearingGapDataset:
    """Calculate one accepted-increment bearing-gap result."""

    d3_by_node_id = {record.node_id: record.d3_mm for record in dataset.records}

    if len(d3_by_node_id) != len(dataset.records):
        raise RuntimeError(
            f"Duplicate nodal displacement records occur in FRD dataset {dataset.dataset_sequence}."
        )

    bolt_under_head_mean = _mean_d3(
        d3_by_node_id,
        node_sets[BOLT_UNDER_HEAD_SET],
        node_set_name=BOLT_UNDER_HEAD_SET,
        dataset_sequence=dataset.dataset_sequence,
    )

    head_member_bearing_mean = _mean_d3(
        d3_by_node_id,
        node_sets[HEAD_MEMBER_BEARING_SET],
        node_set_name=HEAD_MEMBER_BEARING_SET,
        dataset_sequence=dataset.dataset_sequence,
    )

    nut_lower_bearing_mean = _mean_d3(
        d3_by_node_id,
        node_sets[NUT_LOWER_BEARING_SET],
        node_set_name=NUT_LOWER_BEARING_SET,
        dataset_sequence=dataset.dataset_sequence,
    )

    nut_member_bearing_mean = _mean_d3(
        d3_by_node_id,
        node_sets[NUT_MEMBER_BEARING_SET],
        node_set_name=NUT_MEMBER_BEARING_SET,
        dataset_sequence=dataset.dataset_sequence,
    )

    return CompleteJointBearingGapDataset(
        dataset_sequence=dataset.dataset_sequence,
        step=dataset.step,
        increment=dataset.increment,
        time=dataset.time,
        bolt_under_head_mean_d3_mm=bolt_under_head_mean,
        head_member_bearing_mean_d3_mm=head_member_bearing_mean,
        nut_lower_bearing_mean_d3_mm=nut_lower_bearing_mean,
        nut_member_bearing_mean_d3_mm=nut_member_bearing_mean,
        under_head_signed_gap_change_mm=(head_member_bearing_mean - bolt_under_head_mean),
        nut_bearing_signed_gap_change_mm=(nut_lower_bearing_mean - nut_member_bearing_mean),
    )


def _mean_d3(
    d3_by_node_id: Mapping[int, float],
    node_ids: tuple[int, ...],
    *,
    node_set_name: str,
    dataset_sequence: int,
) -> float:
    """Return mean axial displacement for one required node set."""

    missing_node_ids = tuple(node_id for node_id in node_ids if node_id not in d3_by_node_id)

    if missing_node_ids:
        preview = ", ".join(str(node_id) for node_id in missing_node_ids[:5])

        raise RuntimeError(
            f"FRD dataset {dataset_sequence} lacks "
            f"{len(missing_node_ids)} nodes from {node_set_name!r}; "
            f"first missing IDs: {preview}."
        )

    return math.fsum(d3_by_node_id[node_id] for node_id in node_ids) / len(node_ids)
