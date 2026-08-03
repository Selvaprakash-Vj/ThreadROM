"""Governed complete-joint pretension configuration."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from threadrom.meshing.complete_joint_mesh_definition import (
    CompleteJointMeshDefinition,
)


@dataclass(frozen=True)
class CompleteJointPretensionLoadSchedule:
    """Governed multi-step preload and nonlinear controls."""

    checkpoint_count: int
    maximum_increments_per_step: int
    initial_time_increment: float
    step_time: float
    minimum_time_increment: float
    maximum_time_increment: float

    @property
    def checkpoint_fractions(self) -> tuple[float, ...]:
        """Return monotonically increasing checkpoint fractions."""

        return tuple(
            checkpoint_index / self.checkpoint_count
            for checkpoint_index in range(
                1,
                self.checkpoint_count + 1,
            )
        )


@dataclass(frozen=True)
class CompleteJointPretensionRestartPolicy:
    """Governed CalculiX restart-write controls."""

    write_enabled: bool
    write_frequency_steps: int
    overlay_latest: bool


@dataclass(frozen=True)
class CompleteJointPretensionDefinition:
    """Controlled settings for the pretension-capable joint model."""

    pretension_model_id: str
    simulation_id: str
    source_mesh_id: str
    pretension_mesh_id: str
    assembly_id: str
    geometry_id: str
    contact_model_id: str
    boundary_region_id: str
    status: str

    section_name: str
    axial_position_mm: float
    normal_axis: str
    surface_type: str

    preload_force_n: float
    loading_mode: str

    load_schedule: CompleteJointPretensionLoadSchedule
    restart_policy: CompleteJointPretensionRestartPolicy

    bolt_fragment_count: int
    expected_total_cad_volume_count: int
    physical_bolt_group_name: str
    group_bolt_fragments_together: bool

    require_planar_section: bool
    require_single_connected_section: bool
    require_single_boundary_loop: bool
    require_zero_nonmanifold_edges: bool
    require_shared_section_mesh: bool


def _section(
    data: Mapping[str, object],
    key: str,
) -> Mapping[str, object]:
    value = data.get(key)

    if not isinstance(value, dict):
        raise TypeError(f"Missing or invalid configuration section: {key}")

    return cast(Mapping[str, object], value)


def _string(
    data: Mapping[str, object],
    key: str,
) -> str:
    value = data.get(key)

    if not isinstance(value, str) or not value.strip():
        raise TypeError(f"Missing or invalid string value: {key}")

    return value.strip()


def _number(
    data: Mapping[str, object],
    key: str,
) -> float:
    value = data.get(key)

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"Missing or invalid numeric value: {key}")

    return float(value)


def _integer(
    data: Mapping[str, object],
    key: str,
) -> int:
    value = data.get(key)

    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"Missing or invalid integer value: {key}")

    return value


def _boolean(
    data: Mapping[str, object],
    key: str,
) -> bool:
    value = data.get(key)

    if not isinstance(value, bool):
        raise TypeError(f"Missing or invalid Boolean value: {key}")

    return value


def load_complete_joint_pretension_definition(
    path: Path,
) -> CompleteJointPretensionDefinition:
    """Load and validate governed pretension settings."""

    with path.open("rb") as config_file:
        data: dict[str, object] = tomllib.load(config_file)

    identity = _section(data, "identity")
    section = _section(data, "section")
    load = _section(data, "load")
    load_schedule_config = _section(data, "load_schedule")
    restart = _section(data, "restart")
    volume_model = _section(data, "volume_model")
    verification = _section(data, "verification")

    definition = CompleteJointPretensionDefinition(
        pretension_model_id=_string(
            identity,
            "pretension_model_id",
        ),
        simulation_id=_string(identity, "simulation_id"),
        source_mesh_id=_string(identity, "source_mesh_id"),
        pretension_mesh_id=_string(
            identity,
            "pretension_mesh_id",
        ),
        assembly_id=_string(identity, "assembly_id"),
        geometry_id=_string(identity, "geometry_id"),
        contact_model_id=_string(
            identity,
            "contact_model_id",
        ),
        boundary_region_id=_string(
            identity,
            "boundary_region_id",
        ),
        status=_string(identity, "status"),
        section_name=_string(section, "name"),
        axial_position_mm=_number(
            section,
            "axial_position_mm",
        ),
        normal_axis=_string(section, "normal_axis").upper(),
        surface_type=_string(
            section,
            "surface_type",
        ).upper(),
        preload_force_n=_number(load, "preload_force_n"),
        loading_mode=_string(
            load,
            "loading_mode",
        ).upper(),
        load_schedule=CompleteJointPretensionLoadSchedule(
            checkpoint_count=_integer(
                load_schedule_config,
                "checkpoint_count",
            ),
            maximum_increments_per_step=_integer(
                load_schedule_config,
                "maximum_increments_per_step",
            ),
            initial_time_increment=_number(
                load_schedule_config,
                "initial_time_increment",
            ),
            step_time=_number(
                load_schedule_config,
                "step_time",
            ),
            minimum_time_increment=_number(
                load_schedule_config,
                "minimum_time_increment",
            ),
            maximum_time_increment=_number(
                load_schedule_config,
                "maximum_time_increment",
            ),
        ),
        restart_policy=CompleteJointPretensionRestartPolicy(
            write_enabled=_boolean(
                restart,
                "write_enabled",
            ),
            write_frequency_steps=_integer(
                restart,
                "write_frequency_steps",
            ),
            overlay_latest=_boolean(
                restart,
                "overlay_latest",
            ),
        ),
        bolt_fragment_count=_integer(
            volume_model,
            "bolt_fragment_count",
        ),
        expected_total_cad_volume_count=_integer(
            volume_model,
            "expected_total_cad_volume_count",
        ),
        physical_bolt_group_name=_string(
            volume_model,
            "physical_bolt_group_name",
        ),
        group_bolt_fragments_together=_boolean(
            volume_model,
            "group_bolt_fragments_together",
        ),
        require_planar_section=_boolean(
            verification,
            "require_planar_section",
        ),
        require_single_connected_section=_boolean(
            verification,
            "require_single_connected_section",
        ),
        require_single_boundary_loop=_boolean(
            verification,
            "require_single_boundary_loop",
        ),
        require_zero_nonmanifold_edges=_boolean(
            verification,
            "require_zero_nonmanifold_edges",
        ),
        require_shared_section_mesh=_boolean(
            verification,
            "require_shared_section_mesh",
        ),
    )

    if definition.axial_position_mm <= 0.0:
        raise ValueError("Pretension section position must be positive.")

    if definition.preload_force_n <= 0.0:
        raise ValueError("Pretension force must be positive.")

    load_schedule = definition.load_schedule

    if load_schedule.checkpoint_count <= 0:
        raise ValueError("Pretension checkpoint count must be positive.")

    if load_schedule.maximum_increments_per_step <= 0:
        raise ValueError("Maximum increments per preload step must be positive.")

    if not (
        0.0
        < load_schedule.minimum_time_increment
        <= load_schedule.initial_time_increment
        <= load_schedule.maximum_time_increment
        <= load_schedule.step_time
    ):
        raise ValueError(
            "Pretension increment controls must satisfy "
            "0 < minimum <= initial <= maximum <= step time."
        )

    restart_policy = definition.restart_policy

    if restart_policy.write_frequency_steps <= 0:
        raise ValueError("Restart-write frequency must be positive.")

    if restart_policy.write_frequency_steps > load_schedule.checkpoint_count:
        raise ValueError("Restart-write frequency cannot exceed the preload checkpoint count.")

    if definition.normal_axis != "Z":
        raise ValueError("The baseline pretension normal axis must be Z.")

    if definition.surface_type != "ELEMENT":
        raise ValueError("Pretension surface type must be ELEMENT.")

    if definition.bolt_fragment_count != 2:
        raise ValueError("The pretension bolt must contain two fragments.")

    return definition


def validate_complete_joint_pretension_mesh(
    pretension: CompleteJointPretensionDefinition,
    mesh: CompleteJointMeshDefinition,
) -> None:
    """Verify pretension and mesh configurations are compatible."""

    if pretension.pretension_mesh_id != mesh.mesh_id:
        raise ValueError("Pretension and mesh IDs differ.")

    if pretension.assembly_id != mesh.assembly_id:
        raise ValueError("Pretension and mesh assembly IDs differ.")

    if pretension.geometry_id != mesh.geometry_id:
        raise ValueError("Pretension and mesh geometry IDs differ.")

    if pretension.expected_total_cad_volume_count != mesh.expected_volume_count:
        raise ValueError("Pretension and mesh volume expectations differ.")

    expected_volume_count = pretension.bolt_fragment_count + 3

    if pretension.expected_total_cad_volume_count != expected_volume_count:
        raise ValueError(
            "Pretension volume count is inconsistent with "
            "the bolt fragments and three remaining components."
        )

    if pretension.source_mesh_id == pretension.pretension_mesh_id:
        raise ValueError("Source and pretension mesh IDs must differ.")

    if not pretension.group_bolt_fragments_together:
        raise ValueError("Bolt fragments must share one physical group.")
