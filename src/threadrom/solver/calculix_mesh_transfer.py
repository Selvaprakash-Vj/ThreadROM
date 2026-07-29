"""Convert a grouped Gmsh mesh into a CalculiX verification deck."""

from __future__ import annotations

import re
import subprocess
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import meshio  # type: ignore[import-untyped]
import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True)
class CalculixTransferDefinition:
    """Controlled mesh-transfer and verification settings."""

    simulation_id: str
    mesh_id: str
    geometry_id: str
    mesh_level: str
    executable_relative_path: Path
    job_name: str
    timeout_seconds: int
    volume_group: str
    fixed_node_group: str
    loaded_node_group: str
    element_type: str
    material_name: str
    youngs_modulus_mpa: float
    poissons_ratio: float
    total_axial_force_n: float
    minimum_node_count: int
    minimum_element_count: int
    force_balance_tolerance_n: float
    required_boundary_groups: tuple[str, ...]


@dataclass(frozen=True)
class CalculixMeshTransferData:
    """Nodes, tetrahedra and named boundary sets from a grouped mesh."""

    points_mm: NDArray[np.float64]
    tetrahedra: NDArray[np.int64]
    volume_group_name: str
    boundary_node_sets: Mapping[str, tuple[int, ...]]

    @property
    def node_count(self) -> int:
        """Return the number of mesh nodes."""

        return len(self.points_mm)

    @property
    def element_count(self) -> int:
        """Return the number of tetrahedral elements."""

        return len(self.tetrahedra)


@dataclass(frozen=True)
class CalculixDeckSummary:
    """Summary of the generated CalculiX input deck."""

    node_count: int
    element_count: int
    named_node_set_count: int
    fixed_node_count: int
    loaded_node_count: int
    load_per_node_n: float
    total_applied_force_n: float
    input_file_size_bytes: int


@dataclass(frozen=True)
class CalculixRunResult:
    """Result of one CalculiX execution."""

    return_code: int
    stdout: str
    stderr: str
    input_path: Path
    dat_path: Path
    frd_path: Path
    sta_path: Path
    stdout_log_path: Path
    stderr_log_path: Path


def _section(
    data: Mapping[str, object],
    key: str,
) -> Mapping[str, object]:
    """Return a required TOML section."""

    value = data.get(key)

    if not isinstance(value, dict):
        raise TypeError(f"Missing or invalid configuration section: {key}")

    return cast(Mapping[str, object], value)


def _string(
    data: Mapping[str, object],
    key: str,
) -> str:
    """Return a required non-empty string."""

    value = data.get(key)

    if not isinstance(value, str) or not value.strip():
        raise TypeError(f"Missing or invalid string value: {key}")

    return value


def _integer(
    data: Mapping[str, object],
    key: str,
) -> int:
    """Return a required integer."""

    value = data.get(key)

    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"Missing or invalid integer value: {key}")

    return value


def _number(
    data: Mapping[str, object],
    key: str,
) -> float:
    """Return a required numerical value."""

    value = data.get(key)

    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"Missing or invalid numerical value: {key}")

    return float(value)


def _string_tuple(
    data: Mapping[str, object],
    key: str,
) -> tuple[str, ...]:
    """Return a required list of unique non-empty strings."""

    value = data.get(key)

    if not isinstance(value, list) or not value:
        raise TypeError(f"Missing or invalid string list: {key}")

    values: list[str] = []

    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise TypeError(f"Invalid string item in list: {key}")

        values.append(item)

    if len(values) != len(set(values)):
        raise ValueError(f"Duplicate values are not permitted in: {key}")

    return tuple(values)


def load_calculix_transfer_definition(
    config_path: Path,
) -> CalculixTransferDefinition:
    """Load and validate the CalculiX transfer definition."""

    with config_path.open("rb") as config_file:
        data: dict[str, object] = tomllib.load(config_file)

    identity = _section(data, "identity")
    input_section = _section(data, "input")
    solver = _section(data, "solver")
    model = _section(data, "model")
    verification = _section(data, "verification")

    definition = CalculixTransferDefinition(
        simulation_id=_string(
            identity,
            "simulation_id",
        ),
        mesh_id=_string(
            identity,
            "mesh_id",
        ),
        geometry_id=_string(
            identity,
            "geometry_id",
        ),
        mesh_level=_string(
            input_section,
            "mesh_level",
        ).lower(),
        executable_relative_path=Path(
            _string(
                solver,
                "executable_relative_path",
            )
        ),
        job_name=_string(
            solver,
            "job_name",
        ),
        timeout_seconds=_integer(
            solver,
            "timeout_seconds",
        ),
        volume_group=_string(
            model,
            "volume_group",
        ),
        fixed_node_group=_string(
            model,
            "fixed_node_group",
        ),
        loaded_node_group=_string(
            model,
            "loaded_node_group",
        ),
        element_type=_string(
            model,
            "element_type",
        ),
        material_name=_string(
            model,
            "material_name",
        ),
        youngs_modulus_mpa=_number(
            model,
            "youngs_modulus_mpa",
        ),
        poissons_ratio=_number(
            model,
            "poissons_ratio",
        ),
        total_axial_force_n=_number(
            model,
            "total_axial_force_n",
        ),
        minimum_node_count=_integer(
            verification,
            "minimum_node_count",
        ),
        minimum_element_count=_integer(
            verification,
            "minimum_element_count",
        ),
        force_balance_tolerance_n=_number(
            verification,
            "force_balance_tolerance_n",
        ),
        required_boundary_groups=_string_tuple(
            verification,
            "required_boundary_groups",
        ),
    )

    if definition.mesh_level not in {
        "coarse",
        "medium",
        "fine",
    }:
        raise ValueError("Mesh level must be coarse, medium or fine.")

    if definition.timeout_seconds <= 0:
        raise ValueError("Solver timeout must be positive.")

    if definition.youngs_modulus_mpa <= 0.0:
        raise ValueError("Young's modulus must be positive.")

    if not -1.0 < definition.poissons_ratio < 0.5:
        raise ValueError("Poisson's ratio must lie between -1 and 0.5.")

    if definition.total_axial_force_n == 0.0:
        raise ValueError("Verification force cannot be zero.")

    if definition.minimum_node_count <= 0:
        raise ValueError("Minimum node count must be positive.")

    if definition.minimum_element_count <= 0:
        raise ValueError("Minimum element count must be positive.")

    return definition


def _calculix_name(name: str) -> str:
    """Convert one physical name into a safe CalculiX identifier."""

    converted = re.sub(
        r"[^A-Za-z0-9_]",
        "_",
        name.strip().upper(),
    )

    converted = re.sub(
        r"_+",
        "_",
        converted,
    ).strip("_")

    if not converted:
        raise ValueError(f"Physical name cannot be converted: {name!r}")

    if converted[0].isdigit():
        converted = f"SET_{converted}"

    return converted[:80]


def read_grouped_mesh_for_calculix(
    msh_path: Path,
    definition: CalculixTransferDefinition,
) -> CalculixMeshTransferData:
    """Read volume elements and named boundary nodes from Gmsh MSH."""

    if not msh_path.exists() or msh_path.stat().st_size <= 0:
        raise FileNotFoundError(f"Valid grouped mesh not found: {msh_path}")

    mesh = meshio.read(msh_path)

    physical_data = mesh.cell_data.get("gmsh:physical")

    if physical_data is None:
        raise RuntimeError("Grouped mesh contains no gmsh:physical data.")

    if len(physical_data) != len(mesh.cells):
        raise RuntimeError("Physical data does not align with mesh cell blocks.")

    field_lookup: dict[tuple[int, int], str] = {}

    for name, values in mesh.field_data.items():
        physical_tag = int(values[0])
        dimension = int(values[1])

        field_lookup[(physical_tag, dimension)] = _calculix_name(name)

    expected_volume_group = _calculix_name(definition.volume_group)

    tetrahedron_blocks: list[NDArray[np.int64]] = []
    boundary_nodes: dict[str, set[int]] = {}

    for cell_block, block_physical_tags in zip(
        mesh.cells,
        physical_data,
        strict=True,
    ):
        if cell_block.type == "tetra":
            connectivity = np.asarray(
                cell_block.data,
                dtype=np.int64,
            )

            for physical_tag in np.unique(block_physical_tags):
                name = field_lookup.get((int(physical_tag), 3))

                if name != expected_volume_group:
                    raise RuntimeError(
                        "A tetrahedral block is not assigned "
                        f"to volume group {expected_volume_group!r}."
                    )

            tetrahedron_blocks.append(connectivity)

        elif cell_block.type == "triangle":
            connectivity = np.asarray(
                cell_block.data,
                dtype=np.int64,
            )

            for triangle, physical_tag in zip(
                connectivity,
                block_physical_tags,
                strict=True,
            ):
                physical_name = field_lookup.get((int(physical_tag), 2))

                if physical_name is None:
                    raise RuntimeError("A boundary triangle belongs to an unknown physical group.")

                node_set = boundary_nodes.setdefault(
                    physical_name,
                    set(),
                )

                node_set.update(int(node_index) + 1 for node_index in triangle)

    if not tetrahedron_blocks:
        raise RuntimeError("Grouped mesh contains no first-order tetrahedra.")

    tetrahedra = np.vstack(tetrahedron_blocks)

    points = np.asarray(
        mesh.points[:, :3],
        dtype=np.float64,
    )

    resolved_boundary_sets = {
        name: tuple(sorted(node_ids)) for name, node_ids in boundary_nodes.items()
    }

    required_groups = {_calculix_name(name) for name in definition.required_boundary_groups}

    missing_groups = required_groups.difference(resolved_boundary_sets)

    if missing_groups:
        raise RuntimeError(
            "Required boundary groups were not recovered: " + ", ".join(sorted(missing_groups))
        )

    if len(points) < definition.minimum_node_count:
        raise RuntimeError("Transferred node count is below the controlled minimum.")

    if len(tetrahedra) < definition.minimum_element_count:
        raise RuntimeError("Transferred element count is below the controlled minimum.")

    if np.min(tetrahedra) < 0:
        raise RuntimeError("Tetrahedral connectivity contains a negative node index.")

    if np.max(tetrahedra) >= len(points):
        raise RuntimeError("Tetrahedral connectivity references a missing node.")

    return CalculixMeshTransferData(
        points_mm=points,
        tetrahedra=tetrahedra,
        volume_group_name=expected_volume_group,
        boundary_node_sets=resolved_boundary_sets,
    )


def _format_identifier_rows(
    identifiers: tuple[int, ...],
    values_per_row: int = 16,
) -> list[str]:
    """Format CalculiX node or element identifiers."""

    if values_per_row <= 0:
        raise ValueError("Values per row must be positive.")

    return [
        ", ".join(str(identifier) for identifier in identifiers[start : start + values_per_row])
        for start in range(
            0,
            len(identifiers),
            values_per_row,
        )
    ]


def write_calculix_transfer_deck(
    mesh_data: CalculixMeshTransferData,
    definition: CalculixTransferDefinition,
    input_path: Path,
) -> CalculixDeckSummary:
    """Write a linear-elastic CalculiX mesh-transfer deck."""

    fixed_group = _calculix_name(definition.fixed_node_group)
    loaded_group = _calculix_name(definition.loaded_node_group)

    try:
        fixed_nodes = mesh_data.boundary_node_sets[fixed_group]
    except KeyError as error:
        raise RuntimeError(f"Fixed node group not found: {fixed_group}") from error

    try:
        loaded_nodes = mesh_data.boundary_node_sets[loaded_group]
    except KeyError as error:
        raise RuntimeError(f"Loaded node group not found: {loaded_group}") from error

    if not fixed_nodes:
        raise RuntimeError("Fixed node group contains no nodes.")

    if not loaded_nodes:
        raise RuntimeError("Loaded node group contains no nodes.")

    shared_nodes = set(fixed_nodes).intersection(loaded_nodes)

    if shared_nodes:
        raise RuntimeError("Fixed and loaded boundary groups share nodes.")

    load_per_node_n = definition.total_axial_force_n / len(loaded_nodes)

    lines = [
        "*HEADING",
        (f"{definition.simulation_id} Gmsh-to-CalculiX mesh-transfer verification"),
        "**",
        "** Solver working units: mm, N, MPa",
        ("** Canonical ThreadROM values are converted before deck generation."),
        "**",
        "*NODE",
    ]

    for node_id, point in enumerate(
        mesh_data.points_mm,
        start=1,
    ):
        lines.append(f"{node_id}, {point[0]:.12e}, {point[1]:.12e}, {point[2]:.12e}")

    lines.append(f"*ELEMENT, TYPE={definition.element_type}, ELSET={mesh_data.volume_group_name}")

    for element_id, connectivity in enumerate(
        mesh_data.tetrahedra,
        start=1,
    ):
        node_ids = (
            int(connectivity[0]) + 1,
            int(connectivity[1]) + 1,
            int(connectivity[2]) + 1,
            int(connectivity[3]) + 1,
        )

        lines.append(f"{element_id}, " + ", ".join(str(node_id) for node_id in node_ids))

    for name in sorted(mesh_data.boundary_node_sets):
        lines.append(f"*NSET, NSET={name}")

        lines.extend(_format_identifier_rows(mesh_data.boundary_node_sets[name]))

    lines.extend(
        [
            f"*MATERIAL, NAME={definition.material_name}",
            "*ELASTIC",
            (f"{definition.youngs_modulus_mpa:.12e}, {definition.poissons_ratio:.12e}"),
            (
                "*SOLID SECTION, "
                f"ELSET={mesh_data.volume_group_name}, "
                f"MATERIAL={definition.material_name}"
            ),
            "",
            "*STEP, NLGEOM=NO",
            "*STATIC",
            "1.0, 1.0",
            "*BOUNDARY",
            f"{fixed_group}, 1, 3, 0.0",
            "*CLOAD",
        ]
    )

    for node_id in loaded_nodes:
        lines.append(f"{node_id}, 3, {load_per_node_n:.12e}")

    lines.extend(
        [
            f"*NODE PRINT,NSET={fixed_group},TOTALS=ONLY",
            "RF",
            f"*NODE PRINT,NSET={loaded_group}",
            "U",
            f"*NODE FILE,NSET={loaded_group}",
            "U",
            "*END STEP",
            "",
        ]
    )

    input_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    input_path.write_text(
        "\n".join(lines),
        encoding="utf-8",
        newline="\n",
    )

    total_applied_force_n = load_per_node_n * len(loaded_nodes)

    return CalculixDeckSummary(
        node_count=mesh_data.node_count,
        element_count=mesh_data.element_count,
        named_node_set_count=len(mesh_data.boundary_node_sets),
        fixed_node_count=len(fixed_nodes),
        loaded_node_count=len(loaded_nodes),
        load_per_node_n=load_per_node_n,
        total_applied_force_n=total_applied_force_n,
        input_file_size_bytes=input_path.stat().st_size,
    )


def run_calculix_transfer_job(
    project_root: Path,
    input_path: Path,
    definition: CalculixTransferDefinition,
) -> CalculixRunResult:
    """Execute CalculiX for one generated verification deck."""

    executable_path = project_root / definition.executable_relative_path

    if not executable_path.exists():
        raise FileNotFoundError(f"CalculiX executable not found: {executable_path}")

    if not input_path.exists() or input_path.stat().st_size <= 0:
        raise FileNotFoundError(f"Valid CalculiX input not found: {input_path}")

    if input_path.stem != definition.job_name:
        raise ValueError("Input filename must match the configured job name.")

    working_directory = input_path.parent

    completed = subprocess.run(
        [
            str(executable_path),
            "-i",
            definition.job_name,
        ],
        cwd=working_directory,
        capture_output=True,
        text=True,
        timeout=definition.timeout_seconds,
        check=False,
    )

    stdout_log_path = working_directory / f"{definition.job_name}.stdout.log"

    stderr_log_path = working_directory / f"{definition.job_name}.stderr.log"

    stdout_log_path.write_text(
        completed.stdout,
        encoding="utf-8",
        errors="replace",
    )

    stderr_log_path.write_text(
        completed.stderr,
        encoding="utf-8",
        errors="replace",
    )

    dat_path = working_directory / f"{definition.job_name}.dat"

    frd_path = working_directory / f"{definition.job_name}.frd"

    sta_path = working_directory / f"{definition.job_name}.sta"

    combined_diagnostics = completed.stdout + "\n" + completed.stderr

    if dat_path.exists():
        combined_diagnostics += "\n" + dat_path.read_text(
            encoding="utf-8",
            errors="replace",
        )

    if completed.returncode != 0:
        raise RuntimeError(
            "CalculiX returned a nonzero exit code.\n" + combined_diagnostics[-4000:]
        )

    if "*ERROR" in combined_diagnostics.upper():
        raise RuntimeError(
            "CalculiX reported an input or solution error.\n" + combined_diagnostics[-4000:]
        )

    required_outputs = (
        dat_path,
        frd_path,
        sta_path,
    )

    missing_outputs = [
        path for path in required_outputs if not path.exists() or path.stat().st_size <= 0
    ]

    if missing_outputs:
        raise RuntimeError(
            "CalculiX did not create required outputs: "
            + ", ".join(str(path) for path in missing_outputs)
        )

    return CalculixRunResult(
        return_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        input_path=input_path,
        dat_path=dat_path,
        frd_path=frd_path,
        sta_path=sta_path,
        stdout_log_path=stdout_log_path,
        stderr_log_path=stderr_log_path,
    )


@dataclass(frozen=True)
class CalculixForceBalance:
    """Applied-load and support-reaction equilibrium summary."""

    reaction_x_n: float
    reaction_y_n: float
    reaction_z_n: float
    applied_z_n: float
    residual_x_n: float
    residual_y_n: float
    residual_z_n: float
    maximum_absolute_residual_n: float


_CALCULIX_NUMBER_PATTERN = re.compile(
    r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)"
    r"(?:[EeDd][+-]?\d+)?"
)


def _parse_calculix_number(value: str) -> float:
    """Parse E- or D-exponent CalculiX numbers."""

    return float(value.replace("D", "E").replace("d", "e"))


def read_total_force_from_dat(
    dat_path: Path,
    node_set_name: str,
) -> tuple[float, float, float]:
    """Read a TOTALS=ONLY force vector from a CalculiX DAT file."""

    if not dat_path.exists() or dat_path.stat().st_size <= 0:
        raise FileNotFoundError(f"Valid CalculiX DAT file not found: {dat_path}")

    lines = dat_path.read_text(
        encoding="utf-8",
        errors="replace",
    ).splitlines()

    header_pattern = re.compile(
        (
            r"total\s+force\s*\(\s*fx\s*,\s*fy\s*,\s*fz\s*\)"
            r"\s+for\s+set\s+" + re.escape(node_set_name) + r"\s+and\s+time"
        ),
        re.IGNORECASE,
    )

    for line_index, line in enumerate(lines):
        if not header_pattern.search(line):
            continue

        for value_line in lines[line_index + 1 : line_index + 8]:
            values = _CALCULIX_NUMBER_PATTERN.findall(value_line)

            if len(values) < 3:
                continue

            return (
                _parse_calculix_number(values[0]),
                _parse_calculix_number(values[1]),
                _parse_calculix_number(values[2]),
            )

    raise RuntimeError(f"CalculiX total-force output was not found for node set {node_set_name!r}.")


def evaluate_calculix_force_balance(
    dat_path: Path,
    definition: CalculixTransferDefinition,
) -> CalculixForceBalance:
    """Verify global equilibrium between applied and reaction forces."""

    fixed_group = _calculix_name(definition.fixed_node_group)

    reaction_x_n, reaction_y_n, reaction_z_n = read_total_force_from_dat(
        dat_path,
        fixed_group,
    )

    residual_x_n = reaction_x_n
    residual_y_n = reaction_y_n
    residual_z_n = reaction_z_n + definition.total_axial_force_n

    maximum_absolute_residual_n = max(
        abs(residual_x_n),
        abs(residual_y_n),
        abs(residual_z_n),
    )

    if maximum_absolute_residual_n > (definition.force_balance_tolerance_n):
        raise RuntimeError(
            "CalculiX force equilibrium failed: "
            f"maximum residual "
            f"{maximum_absolute_residual_n:.9e} N exceeds "
            f"{definition.force_balance_tolerance_n:.9e} N."
        )

    return CalculixForceBalance(
        reaction_x_n=reaction_x_n,
        reaction_y_n=reaction_y_n,
        reaction_z_n=reaction_z_n,
        applied_z_n=definition.total_axial_force_n,
        residual_x_n=residual_x_n,
        residual_y_n=residual_y_n,
        residual_z_n=residual_z_n,
        maximum_absolute_residual_n=(maximum_absolute_residual_n),
    )
