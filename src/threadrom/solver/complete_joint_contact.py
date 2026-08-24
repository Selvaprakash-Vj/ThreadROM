"""Governed nonlinear contact definition for the complete joint."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from threadrom.solver.complete_joint_calculix_transfer import (
    CompleteJointCalculixDeckSummary,
    CompleteJointCalculixMeshData,
    CompleteJointCalculixTransferDefinition,
    _calculix_surface_name,
    write_complete_joint_calculix_transfer_deck,
)

THREAD = "thread"
UNDER_HEAD = "under_head"
NUT_BEARING = "nut_bearing"
MEMBER_INTERFACE = "member_interface"

CONTACT_PAIR_ORDER = (
    THREAD,
    UNDER_HEAD,
    NUT_BEARING,
    MEMBER_INTERFACE,
)


@dataclass(frozen=True)
class ContactPairDefinition:
    """One slave-to-master contact interface."""

    name: str
    slave_surface: str
    master_surface: str


@dataclass(frozen=True)
class CompleteJointContactDefinition:
    """Governed settings for all complete-joint contacts."""

    contact_model_id: str
    simulation_id: str
    mesh_id: str
    assembly_id: str
    geometry_id: str
    classification_id: str
    solver_job_name: str
    interaction_name: str
    contact_type: str
    pressure_overclosure: str
    normal_stiffness_scale_per_mm: float
    friction_coefficient: float
    friction_stick_slope_ratio: float
    contact_pairs: tuple[ContactPairDefinition, ...]
    expected_contact_pair_count: int
    expected_unique_surface_count: int
    require_common_contact_type: bool

    def pair(
        self,
        name: str,
    ) -> ContactPairDefinition:
        """Return one governed contact pair."""

        for pair in self.contact_pairs:
            if pair.name == name:
                return pair

        raise ValueError(
            f"Unknown complete-joint contact pair: {name}"
        )


def _section(
    data: Mapping[str, object],
    key: str,
) -> Mapping[str, object]:
    """Return one required configuration section."""

    value = data.get(key)

    if not isinstance(value, dict):
        raise TypeError(
            f"Missing or invalid configuration section: {key}"
        )

    return cast(Mapping[str, object], value)


def _string(
    data: Mapping[str, object],
    key: str,
) -> str:
    """Return one required non-empty string."""

    value = data.get(key)

    if not isinstance(value, str) or not value.strip():
        raise TypeError(
            f"Missing or invalid string value: {key}"
        )

    return value


def _integer(
    data: Mapping[str, object],
    key: str,
) -> int:
    """Return one required positive integer."""

    value = data.get(key)

    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(
            f"Missing or invalid integer value: {key}"
        )

    if value <= 0:
        raise ValueError(
            f"Integer value must be positive: {key}"
        )

    return value


def _number(
    data: Mapping[str, object],
    key: str,
) -> float:
    """Return one required numerical value."""

    value = data.get(key)

    if (
        isinstance(value, bool)
        or not isinstance(value, int | float)
    ):
        raise TypeError(
            f"Missing or invalid numerical value: {key}"
        )

    return float(value)


def _boolean(
    data: Mapping[str, object],
    key: str,
) -> bool:
    """Return one required Boolean value."""

    value = data.get(key)

    if not isinstance(value, bool):
        raise TypeError(
            f"Missing or invalid Boolean value: {key}"
        )

    return value


def load_complete_joint_contact_definition(
    config_path: Path,
) -> CompleteJointContactDefinition:
    """Load and validate the complete-joint contact model."""

    with config_path.open("rb") as config_file:
        data: dict[str, object] = tomllib.load(
            config_file
        )

    identity = _section(data, "identity")
    solver = _section(data, "solver")
    interaction = _section(data, "interaction")
    pair_sections = _section(data, "contact_pairs")
    verification = _section(data, "verification")

    contact_pairs: list[ContactPairDefinition] = []

    for pair_name in CONTACT_PAIR_ORDER:
        pair_section = _section(
            pair_sections,
            pair_name,
        )

        contact_pairs.append(
            ContactPairDefinition(
                name=pair_name,
                slave_surface=_string(
                    pair_section,
                    "slave_surface",
                ),
                master_surface=_string(
                    pair_section,
                    "master_surface",
                ),
            )
        )

    definition = CompleteJointContactDefinition(
        contact_model_id=_string(
            identity,
            "contact_model_id",
        ),
        simulation_id=_string(
            identity,
            "simulation_id",
        ),
        mesh_id=_string(
            identity,
            "mesh_id",
        ),
        assembly_id=_string(
            identity,
            "assembly_id",
        ),
        geometry_id=_string(
            identity,
            "geometry_id",
        ),
        classification_id=_string(
            identity,
            "classification_id",
        ),
        solver_job_name=_string(
            solver,
            "job_name",
        ),
        interaction_name=_string(
            interaction,
            "name",
        ),
        contact_type=_string(
            interaction,
            "contact_type",
        ).upper(),
        pressure_overclosure=_string(
            interaction,
            "pressure_overclosure",
        ).upper(),
        normal_stiffness_scale_per_mm=_number(
            interaction,
            "normal_stiffness_scale_per_mm",
        ),
        friction_coefficient=_number(
            interaction,
            "friction_coefficient",
        ),
        friction_stick_slope_ratio=_number(
            interaction,
            "friction_stick_slope_ratio",
        ),
        contact_pairs=tuple(contact_pairs),
        expected_contact_pair_count=_integer(
            verification,
            "expected_contact_pair_count",
        ),
        expected_unique_surface_count=_integer(
            verification,
            "expected_unique_surface_count",
        ),
        require_common_contact_type=_boolean(
            verification,
            "require_common_contact_type",
        ),
    )

    if definition.contact_type != "SURFACE TO SURFACE":
        raise ValueError(
            "The baseline contact model requires "
            "SURFACE TO SURFACE contact."
        )

    if definition.pressure_overclosure != "LINEAR":
        raise ValueError(
            "The baseline normal contact law requires LINEAR."
        )

    if definition.normal_stiffness_scale_per_mm <= 0.0:
        raise ValueError(
            "Normal stiffness scale must be positive."
        )

    if definition.friction_coefficient < 0.0:
        raise ValueError(
            "Friction coefficient cannot be negative."
        )

    if not 0.0 < definition.friction_stick_slope_ratio <= 1.0:
        raise ValueError(
            "Friction stick-slope ratio must lie in (0, 1]."
        )

    if (
        len(definition.contact_pairs)
        != definition.expected_contact_pair_count
    ):
        raise ValueError(
            "Contact-pair count does not match the "
            "governed expectation."
        )

    all_surfaces = tuple(
        surface
        for pair in definition.contact_pairs
        for surface in (
            pair.slave_surface,
            pair.master_surface,
        )
    )

    if (
        len(set(all_surfaces))
        != definition.expected_unique_surface_count
    ):
        raise ValueError(
            "Contact surfaces are duplicated or the unique "
            "surface count is incorrect."
        )

    for pair in definition.contact_pairs:
        if pair.slave_surface == pair.master_surface:
            raise ValueError(
                f"Contact pair {pair.name} uses the same "
                "surface as slave and master."
            )

    return definition


def validate_contact_surfaces_against_transfer(
    contact: CompleteJointContactDefinition,
    transfer: CompleteJointCalculixTransferDefinition,
) -> None:
    """Verify contact IDs and surfaces against the mesh transfer."""

    identity_pairs = (
        (
            "mesh",
            contact.mesh_id,
            transfer.mesh_id,
        ),
        (
            "assembly",
            contact.assembly_id,
            transfer.assembly_id,
        ),
        (
            "geometry",
            contact.geometry_id,
            transfer.geometry_id,
        ),
        (
            "classification",
            contact.classification_id,
            transfer.classification_id,
        ),
    )

    for identity_name, contact_value, transfer_value in (
        identity_pairs
    ):
        if contact_value != transfer_value:
            raise ValueError(
                f"Contact and transfer {identity_name} IDs differ."
            )

    available_surfaces = {
        _calculix_surface_name(boundary_name)
        for boundary_name in transfer.required_boundary_groups
    }

    required_surfaces = {
        surface
        for pair in contact.contact_pairs
        for surface in (
            pair.slave_surface,
            pair.master_surface,
        )
    }

    missing_surfaces = required_surfaces.difference(
        available_surfaces
    )

    if missing_surfaces:
        raise ValueError(
            "Contact surfaces are missing from the transferred "
            "CalculiX deck: "
            + ", ".join(sorted(missing_surfaces))
        )



def render_complete_joint_contact_keywords(
    contact: CompleteJointContactDefinition,
    transfer: CompleteJointCalculixTransferDefinition,
) -> tuple[str, ...]:
    """Render verified CalculiX interaction and contact cards."""

    validate_contact_surfaces_against_transfer(
        contact,
        transfer,
    )

    normal_stiffness_n_per_mm3 = (
        contact.normal_stiffness_scale_per_mm
        * transfer.youngs_modulus_mpa
    )

    stick_slope_n_per_mm3 = (
        normal_stiffness_n_per_mm3
        * contact.friction_stick_slope_ratio
    )

    if normal_stiffness_n_per_mm3 <= 0.0:
        raise RuntimeError(
            "Derived normal contact stiffness is invalid."
        )

    if stick_slope_n_per_mm3 <= 0.0:
        raise RuntimeError(
            "Derived friction stick slope is invalid."
        )

    lines = [
        (
            "*SURFACE INTERACTION, NAME="
            f"{contact.interaction_name}"
        ),
        (
            "*SURFACE BEHAVIOR, "
            "PRESSURE-OVERCLOSURE=LINEAR"
        ),
        f"{normal_stiffness_n_per_mm3:.12e}",
        "*FRICTION",
        (
            f"{contact.friction_coefficient:.12e}, "
            f"{stick_slope_n_per_mm3:.12e}"
        ),
    ]

    for pair in contact.contact_pairs:
        lines.extend(
            [
                f"** Contact pair: {pair.name}",
                (
                    "*CONTACT PAIR, "
                    f"INTERACTION={contact.interaction_name}, "
                    f"TYPE={contact.contact_type}"
                ),
                (
                    f"{pair.slave_surface}, "
                    f"{pair.master_surface}"
                ),
            ]
        )

    return tuple(lines)



@dataclass(frozen=True)
class CompleteJointContactSmokeDeckSummary:
    """Summary of the contact-enabled smoke deck."""

    transfer: CompleteJointCalculixDeckSummary
    contact_pair_count: int
    interaction_count: int
    normal_stiffness_n_per_mm3: float
    friction_stick_slope_n_per_mm3: float
    input_file_size_bytes: int


def write_complete_joint_contact_smoke_deck(
    mesh_data: CompleteJointCalculixMeshData,
    transfer: CompleteJointCalculixTransferDefinition,
    contact: CompleteJointContactDefinition,
    input_path: Path,
) -> CompleteJointContactSmokeDeckSummary:
    """Write a fully constrained contact parser smoke deck."""

    validate_contact_surfaces_against_transfer(
        contact,
        transfer,
    )

    internal_surface_normals = (
        {
            "BOLT_PRETENSION_SECTION": (
                0.0,
                0.0,
                1.0,
            )
        }
        if "BOLT_PRETENSION_SECTION"
        in transfer.required_boundary_groups
        else None
    )

    transfer_summary = (
        write_complete_joint_calculix_transfer_deck(
            mesh_data,
            transfer,
            input_path,
            internal_surface_normals=internal_surface_normals,
        )
    )

    contact_lines = render_complete_joint_contact_keywords(
        contact,
        transfer,
    )

    text = input_path.read_text(encoding="utf-8")

    insertion_marker = (
        "** Fully constrained zero-load solver-read "
        "smoke step"
    )

    if insertion_marker not in text:
        raise RuntimeError(
            "Transfer smoke-step insertion marker "
            "was not found."
        )

    contact_block = "\n".join(
        (
            "**",
            "** Complete-joint nonlinear contact model",
            *contact_lines,
            "**",
            "",
        )
    )

    text = text.replace(
        insertion_marker,
        contact_block + insertion_marker,
        1,
    )

    input_path.write_text(
        text,
        encoding="utf-8",
        newline="\n",
    )

    contact_pair_count = text.count(
        "*CONTACT PAIR,"
    )

    interaction_count = text.count(
        "*SURFACE INTERACTION,"
    )

    if (
        contact_pair_count
        != contact.expected_contact_pair_count
    ):
        raise RuntimeError(
            "Written contact-pair count does not match "
            "the governed expectation."
        )

    if interaction_count != 1:
        raise RuntimeError(
            "Contact smoke deck must contain exactly "
            "one surface interaction."
        )

    first_contact_index = text.index(
        "*SURFACE INTERACTION,"
    )
    step_index = text.index("*STEP,")

    if first_contact_index >= step_index:
        raise RuntimeError(
            "Contact definitions must appear before "
            "the analysis step."
        )

    normal_stiffness = (
        contact.normal_stiffness_scale_per_mm
        * transfer.youngs_modulus_mpa
    )

    friction_stick_slope = (
        normal_stiffness
        * contact.friction_stick_slope_ratio
    )

    return CompleteJointContactSmokeDeckSummary(
        transfer=transfer_summary,
        contact_pair_count=contact_pair_count,
        interaction_count=interaction_count,
        normal_stiffness_n_per_mm3=normal_stiffness,
        friction_stick_slope_n_per_mm3=(
            friction_stick_slope
        ),
        input_file_size_bytes=input_path.stat().st_size,
    )
