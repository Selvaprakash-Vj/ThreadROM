"""Prepare M8/M12 cross-size FEM sentinels without launching CalculiX."""

from __future__ import annotations

import hashlib
import importlib.util
import json

from pathlib import Path

from threadrom.case.resolver import resolve_case
from threadrom.factory.cross_size_fem_sentinel import (
    build_phase3_cross_size_fem_sentinels,
)
from threadrom.factory.fem_case_geometry import (
    build_fem_case_geometry,
)
from threadrom.factory.fem_case_mesh import (
    generate_fem_case_grouped_mesh,
    validate_fem_case_grouped_mesh_quality,
)
from threadrom.factory.fem_case_preparation import (
    derive_fem_case_preparation,
)


ROOT = Path(r"D:\ThreadROM")
CONFIG = ROOT / "config"

ARTIFACT_ROOT = (
    ROOT
    / "simulations"
    / "staging"
    / "phase3_cp11_cross_size_sentinels"
    / "prepared_cases"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as stream:
        for chunk in iter(
            lambda: stream.read(8 * 1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def relative(path: Path) -> str:
    return path.resolve().relative_to(
        ROOT.resolve()
    ).as_posix()


def load_production_policy_api():
    """Reuse the exact loader stack used by Production-DOE preparation."""

    path = (
        ROOT
        / "scripts"
        / "prepare_phase3_production_doe_case.py"
    )

    spec = importlib.util.spec_from_file_location(
        "_threadrom_production_preparation",
        path,
    )

    if spec is None or spec.loader is None:
        raise RuntimeError(
            "Unable to load Production-DOE preparation policy API."
        )

    module = importlib.util.module_from_spec(
        spec
    )
    spec.loader.exec_module(module)

    return module


def write_immutable_json(
    path: Path,
    payload: dict[str, object],
) -> str:
    serialized = (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    if path.exists():
        existing = path.read_text(
            encoding="utf-8"
        )

        if existing != serialized:
            raise RuntimeError(
                "Cross-size preparation evidence already exists "
                "with different content; refusing overwrite: "
                f"{path}"
            )

        return "UNCHANGED / IDENTICAL"

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        serialized,
        encoding="utf-8",
    )

    return "CREATED"


def main() -> int:
    production = load_production_policy_api()

    geometry_validation_path = (
        CONFIG
        / "assembly_geometry_validation.toml"
    )

    mesh_template_path = (
        CONFIG
        / "complete_joint_mesh.toml"
    )

    joint_classification_path = (
        CONFIG
        / "complete_joint_surface_classification.toml"
    )

    bolt_classification_path = (
        CONFIG
        / "surface_classification.toml"
    )

    nut_classification_path = (
        CONFIG
        / "nut_surface_classification.toml"
    )

    mesh_quality_path = (
        CONFIG
        / "complete_joint_mesh_quality.toml"
    )

    validation_policy = (
        production.load_assembly_geometry_validation_policy(
            geometry_validation_path
        )
    )

    mesh_template = (
        production.load_complete_joint_mesh_definition(
            mesh_template_path
        )
    )

    joint_classification_template = (
        production.load_complete_joint_surface_definition(
            joint_classification_path
        )
    )

    bolt_classification_template = (
        production.load_surface_classification_definition(
            bolt_classification_path
        )
    )

    nut_classification_template = (
        production.load_nut_surface_classification_definition(
            nut_classification_path
        )
    )

    bolt_mesh_level_policy = (
        production.load_mesh_level_policy(
            CONFIG
            / mesh_template.bolt_mesh_level_policy
        )
    )

    cross_size_nut_mesh_level_path = (
        CONFIG
        / "nut_mesh_levels_cross_size_sentinel.toml"
    )

    nut_mesh_level_policy = (
        production.load_mesh_level_policy(
            cross_size_nut_mesh_level_path
        )
    )

    quality_definition = (
        production.load_mesh_quality_definition(
            mesh_quality_path
        )
    )

    sentinels = (
        build_phase3_cross_size_fem_sentinels()
    )

    print("=" * 110)
    print(
        "THREADROM - CROSS-SIZE FEM SENTINEL PREPARATION"
    )
    print("=" * 110)
    print("CalculiX invoked  : NO")
    print("Holdouts accessed : NO")
    print("Capability upgrade: NO")
    print()

    for sentinel in sentinels:
        resolved = resolve_case(
            sentinel.case
        )

        preparation = (
            derive_fem_case_preparation(
                resolved
            )
        )

        print("-" * 110)
        print(
            f"{sentinel.definition.sentinel_id} | "
            f"{sentinel.definition.thread_designation}"
        )
        print(
            f"Target preload : "
            f"{sentinel.target_preload_n:.9f} N"
        )
        print(
            f"F / As         : "
            f"{sentinel.reference_nominal_stress_mpa:.9f} MPa"
        )
        print(
            f"Run identity   : "
            f"{preparation.identity.run_id}"
        )

        geometry_artifact = (
            build_fem_case_geometry(
                resolved,
                artifact_root=ARTIFACT_ROOT,
                validation_policy=validation_policy,
            )
        )

        if (
            geometry_artifact.case_hash
            != resolved.case_hash
        ):
            raise RuntimeError(
                "Cross-size geometry case-hash mismatch."
            )

        if (
            geometry_artifact.run_id
            != preparation.identity.run_id
        ):
            raise RuntimeError(
                "Cross-size geometry run-ID mismatch."
            )

        mesh_artifact = (
            generate_fem_case_grouped_mesh(
                resolved,
                geometry_artifact.geometry,
                step_path=geometry_artifact.step_path,
                artifact_root=ARTIFACT_ROOT,
                mesh_template=mesh_template,
                joint_classification_template=(
                    joint_classification_template
                ),
                bolt_classification_template=(
                    bolt_classification_template
                ),
                nut_classification_template=(
                    nut_classification_template
                ),
                bolt_mesh_level_policy=(
                    bolt_mesh_level_policy
                ),
                nut_mesh_level_policy=(
                    nut_mesh_level_policy
                ),
                local_refinement_policy=None,
            )
        )

        if (
            mesh_artifact.case_hash
            != resolved.case_hash
        ):
            raise RuntimeError(
                "Cross-size mesh case-hash mismatch."
            )

        if (
            mesh_artifact.run_id
            != preparation.identity.run_id
        ):
            raise RuntimeError(
                "Cross-size mesh run-ID mismatch."
            )

        quality = (
            validate_fem_case_grouped_mesh_quality(
                mesh_artifact,
                quality_definition,
            )
        )

        record = {
            "schema_version": 1,
            "sentinel_id": (
                sentinel.definition.sentinel_id
            ),
            "thread_designation": (
                sentinel.definition.thread_designation
            ),
            "case_hash": resolved.case_hash,
            "resolution_hash": (
                resolved.resolution_hash
            ),
            "run_id": (
                preparation.identity.run_id
            ),
            "physics": {
                "tensile_stress_area_mm2": (
                    sentinel.tensile_stress_area_mm2
                ),
                "reference_nominal_stress_mpa": (
                    sentinel.reference_nominal_stress_mpa
                ),
                "target_preload_n": (
                    sentinel.target_preload_n
                ),
            },
            "geometry": {
                "step_path": relative(
                    geometry_artifact.step_path
                ),
                "step_sha256": sha256(
                    geometry_artifact.step_path
                ),
            },
            "mesh": {
                "msh_path": relative(
                    mesh_artifact.msh_path
                ),
                "msh_sha256": sha256(
                    mesh_artifact.msh_path
                ),
                "node_count": quality.node_count,
                "tetrahedron_count": (
                    quality.tetrahedron_count
                ),
                "degenerate_count": (
                    quality.degenerate_count
                ),
                "minimum_volume_mm3": (
                    quality.minimum_volume_mm3
                ),
                "minimum_mean_ratio": (
                    quality.minimum_mean_ratio
                ),
                "maximum_edge_ratio": (
                    quality.maximum_edge_ratio
                ),
                "mixed_orientation": (
                    quality.has_mixed_orientation
                ),
            },
            "mesh_quality_policy": {
                "relative_path": relative(
                    mesh_quality_path
                ),
                "sha256": sha256(
                    mesh_quality_path
                ),
            },
            "gates": {
                "case_resolution": "PASS",
                "geometry_validation": "PASS",
                "step_round_trip_validation": "PASS",
                "grouped_mesh_generation": "PASS",
                "mesh_quality_validation": "PASS",
                "calculix_invoked": False,
                "holdouts_accessed": False,
                "capability_upgrade_performed": False,
            },
            "solver_launch_authorized": False,
            "overall_disposition": (
                "CROSS_SIZE_SENTINEL_PREPARED"
            ),
        }

        record_path = (
            ARTIFACT_ROOT
            / preparation.identity.run_id
            / "cross_size_fem_sentinel_preparation_record.json"
        )

        action = write_immutable_json(
            record_path,
            record,
        )

        print(
            f"STEP            : "
            f"{relative(geometry_artifact.step_path)}"
        )
        print(
            f"Mesh            : "
            f"{relative(mesh_artifact.msh_path)}"
        )
        print(
            f"Nodes / tets    : "
            f"{quality.node_count} / "
            f"{quality.tetrahedron_count}"
        )
        print(
            f"Min mean ratio  : "
            f"{quality.minimum_mean_ratio:.9f}"
        )
        print(
            f"Max edge ratio  : "
            f"{quality.maximum_edge_ratio:.9f}"
        )
        print(
            f"Degenerate      : "
            f"{quality.degenerate_count}"
        )
        print(
            f"Record          : "
            f"{relative(record_path)}"
        )
        print(
            f"Record action   : {action}"
        )
        print("Disposition     : PASS")

    print()
    print("=" * 110)
    print(
        "CROSS-SIZE SENTINEL PREPARATION: PASS"
    )
    print("CalculiX invoked  : NO")
    print("Holdouts accessed : NO")
    print("Capability upgrade: NO")
    print("=" * 110)

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
