from __future__ import annotations

import dataclasses
import hashlib
import importlib.util
import json
import tomllib

from pathlib import Path
from typing import Any


from threadrom.case.serialization import (
    case_sha256,
)

from threadrom.case.resolver import (
    resolve_case,
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

from threadrom.factory.geometry_mesh_reuse import (
    build_fem_case_mesh_definitions,
    build_geometry_definitions,
)

from threadrom.factory.production_doe import (
    build_phase3_production_doe,
    load_phase3_production_doe_policy,
)

from threadrom.geometry.complete_joint_assembly import (
    load_assembly_geometry_validation_policy,
)

from threadrom.meshing.complete_joint_mesh_definition import (
    load_complete_joint_mesh_definition,
)

from threadrom.meshing.complete_joint_surface_classification import (
    load_complete_joint_surface_definition,
)

from threadrom.meshing.mesh_levels import (
    load_mesh_level_policy,
)

from threadrom.meshing.nut_surface_classification import (
    load_nut_surface_classification_definition,
)

from threadrom.meshing.surface_classification import (
    load_surface_classification_definition,
)

from threadrom.meshing.tetrahedral_quality import (
    load_mesh_quality_definition,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config"


RECOVERY_PATH = (
    ROOT
    / "docs"
    / "phase3_rom_dataset_admission"
    / "member_shortening_v1.da08_exact_case_recovery.json"
)

EXPECTED_RECOVERY_SHA256 = (
    "61a84b602e654a867945b130110b81ed5bd75bc1d1187676543d0da544f42637"
)

CAMPAIGN_PATH = (
    ROOT
    / "docs"
    / "phase3_rom_dataset_admission"
    / "member_shortening_v1.da08_fine_reference_campaign.json"
)

EXPECTED_CAMPAIGN_SHA256 = (
    "c5cf32cf65129d190fc7a468d104c54965b3991d8b7df409a7b7c0388e0a0b3b"
)

PROPOSAL_PATH = (
    ROOT
    / "docs"
    / "phase3_diversified_doe"
    / "design_proposal.json"
)

DIVERSIFIED_POLICY_PATH = (
    CONFIG
    / "phase3_diversified_doe.toml"
)

PRODUCTION_POLICY_PATH = (
    CONFIG
    / "phase3_production_doe.toml"
)

NEXT_WAVE_BUILDER_PATH = (
    ROOT
    / "scripts"
    / "build_phase3_next_governed_wave_v1.py"
)


ARTIFACT_ROOT = (
    ROOT
    / "simulations"
    / "staging"
    / "phase3_da08_fine_reference"
)

CERTIFICATE_PATH = (
    ARTIFACT_ROOT
    / "da08_fine_reference_mesh_preparation_certificate.json"
)

CERTIFICATE_SIDECAR = (
    ARTIFACT_ROOT
    / "da08_fine_reference_mesh_preparation_certificate.sha256"
)


def sha256(
    path: Path,
) -> str:

    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def relative(
    path: Path,
) -> str:

    return str(
        path.resolve().relative_to(
            ROOT.resolve()
        )
    ).replace(
        "\\",
        "/",
    )


def write_immutable_json(
    path: Path,
    payload: dict[str, Any],
) -> str:

    rendered = (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode(
        "utf-8"
    )

    expected = hashlib.sha256(
        rendered
    ).hexdigest()

    if path.exists():

        existing = path.read_bytes()

        if existing != rendered:

            raise RuntimeError(
                "Immutable artifact exists with different content: "
                f"{path}"
            )

        return expected


    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_bytes(
        rendered
    )

    return expected


def promote_global_mesh_level_to_fine(
    value: Any,
    *,
    path: str = "$",
) -> tuple[Any, list[str]]:

    """
    Replace exactly the governed dataclass mesh-level selector
    currently set to 'medium' with 'fine'.

    Recursive because the selector may live in a nested mesh
    definition component.

    No arbitrary string replacement is permitted.
    """

    if not dataclasses.is_dataclass(
        value
    ):

        return value, []


    updates = {}
    hits: list[str] = []


    for field in dataclasses.fields(
        value
    ):

        child = getattr(
            value,
            field.name,
        )

        child_path = (
            f"{path}.{field.name}"
        )


        if (
            isinstance(
                child,
                str,
            )
            and child == "medium"
            and "level" in field.name.lower()
        ):

            updates[
                field.name
            ] = "fine"

            hits.append(
                child_path
            )

            continue


        if dataclasses.is_dataclass(
            child
        ):

            replaced_child, child_hits = (
                promote_global_mesh_level_to_fine(
                    child,
                    path=child_path,
                )
            )

            if child_hits:

                updates[
                    field.name
                ] = replaced_child

                hits.extend(
                    child_hits
                )


    if updates:

        value = dataclasses.replace(
            value,
            **updates,
        )


    return (
        value,
        hits,
    )


def main() -> int:

    # =============================================================================================
    # AUTHORITY PINS
    # =============================================================================================

    if sha256(
        RECOVERY_PATH
    ) != EXPECTED_RECOVERY_SHA256:

        raise RuntimeError(
            "DA08 exact-case recovery authority SHA drift."
        )


    if sha256(
        CAMPAIGN_PATH
    ) != EXPECTED_CAMPAIGN_SHA256:

        raise RuntimeError(
            "DA08 fine-reference campaign SHA drift."
        )


    if "W06" in str(
        ARTIFACT_ROOT
    ).upper():

        raise RuntimeError(
            "DA08 artifact root illegally intersects W06."
        )


    recovery = json.loads(
        RECOVERY_PATH.read_text(
            encoding="utf-8"
        )
    )


    if (
        recovery.get(
            "record_status"
        )
        != "FINAL"
        or recovery.get(
            "disposition"
        )
        != "DA08_EXACT_THREADROMCASE_RECOVERY_COMPLETE"
        or recovery.get(
            "proof",
            {},
        ).get(
            "recovered_cases"
        )
        != 19
    ):

        raise RuntimeError(
            "DA08 exact-case recovery closure is not FINAL / 19-of-19."
        )


    recovered_rows = recovery[
        "cases"
    ]


    if len(
        recovered_rows
    ) != 19:

        raise RuntimeError(
            "Recovery authority case count drift."
        )


    # =============================================================================================
    # LOAD DIVERSIFIED AUTHORITY
    # =============================================================================================

    proposal = json.loads(
        PROPOSAL_PATH.read_text(
            encoding="utf-8-sig"
        )
    )


    proposal_index = {
        row["proposal_id"]: row
        for row in proposal["cases"]
    }


    with DIVERSIFIED_POLICY_PATH.open(
        "rb"
    ) as stream:

        diversified_policy = (
            tomllib.load(
                stream
            )
        )


    spec = (
        importlib.util.spec_from_file_location(
            "threadrom_da08_next_wave_authority_v2",
            NEXT_WAVE_BUILDER_PATH,
        )
    )


    if (
        spec is None
        or spec.loader is None
    ):

        raise RuntimeError(
            "Unable to load diversified reconstruction authority."
        )


    next_wave = (
        importlib.util.module_from_spec(
            spec
        )
    )

    spec.loader.exec_module(
        next_wave
    )


    identity_fn = getattr(
        next_wave,
        "governed_case_identity",
    )


    authority_globals = (
        identity_fn.__globals__
    )


    diversified_builder = (
        authority_globals[
            "_build_case"
        ]
    )

    diversified_catalog = (
        authority_globals[
            "DIVERSIFIED_CANDIDATE_MATERIAL_CATALOG"
        ]
    )

    diversified_resolver = (
        authority_globals[
            "resolve_case"
        ]
    )


    # =============================================================================================
    # LOAD PRODUCTION-DOE AUTHORITY
    # =============================================================================================

    production_policy = (
        load_phase3_production_doe_policy(
            PRODUCTION_POLICY_PATH
        )
    )

    production_campaign = (
        build_phase3_production_doe(
            production_policy
        )
    )


    # DESIGN CASES ONLY.
    production_index = {
        case.case_id: case
        for case
        in production_campaign.design_cases
    }


    # =============================================================================================
    # RECONSTRUCT EXACT 19 CASE OBJECTS AGAIN
    # =============================================================================================

    reconstructed = []


    for row in sorted(
        recovered_rows,
        key=lambda item: item[
            "ordinal"
        ],
    ):

        case_id = row[
            "case_id"
        ]

        expected_hash = row[
            "case_hash"
        ]

        authority = row[
            "authority"
        ]


        if (
            authority
            == "DIVERSIFIED_DESIGN_PROPOSAL"
        ):

            proposal_row = (
                proposal_index.get(
                    case_id
                )
            )


            if proposal_row is None:

                raise RuntimeError(
                    f"{case_id}: diversified proposal row missing."
                )


            thread = proposal_row[
                "thread_designation"
            ]

            size_matches = [
                item
                for item
                in diversified_policy[
                    "size_candidates"
                ]
                if (
                    item[
                        "designation"
                    ]
                    == thread
                )
            ]


            if len(
                size_matches
            ) != 1:

                raise RuntimeError(
                    f"{case_id}: diversified size resolution drift."
                )


            case, _ = (
                diversified_builder(
                    diversified_policy,
                    size_matches[
                        0
                    ],
                    proposal_row[
                        "member_material_id"
                    ],
                    tuple(
                        proposal_row[
                            "normalized_coordinates"
                        ]
                    ),
                )
            )


            if (
                case_sha256(
                    case
                )
                != expected_hash
            ):

                raise RuntimeError(
                    f"{case_id}: diversified canonical-hash drift."
                )


            resolved = (
                diversified_resolver(
                    case,
                    material_catalog=(
                        diversified_catalog
                    ),
                )
            )


        elif authority in {
            "PRODUCTION_DOE_DESIGN_CASE",
            "PRODUCTION_DOE_CP7_REUSABLE_ANCHOR",
        }:

            production_case = (
                production_index.get(
                    case_id
                )
            )


            if (
                production_case is None
                or production_case.case_hash
                != expected_hash
            ):

                raise RuntimeError(
                    f"{case_id}: Production-DOE identity drift."
                )


            case = production_case.case


            if (
                case_sha256(
                    case
                )
                != expected_hash
            ):

                raise RuntimeError(
                    f"{case_id}: Production-DOE canonical-hash drift."
                )


            resolved = resolve_case(
                case
            )


        else:

            raise RuntimeError(
                f"{case_id}: unsupported recovery authority {authority!r}."
            )


        if (
            resolved.case_hash
            != expected_hash
        ):

            raise RuntimeError(
                f"{case_id}: reconstructed resolved-hash drift."
            )


        preparation = (
            derive_fem_case_preparation(
                resolved
            )
        )


        if (
            preparation.identity.run_id
            != row[
                "case_run_id"
            ]
        ):

            raise RuntimeError(
                f"{case_id}: reconstructed preparation identity drift."
            )


        reconstructed.append(
            {
                "recovery":
                    row,

                "case":
                    case,

                "resolved":
                    resolved,

                "preparation":
                    preparation,
            }
        )


    if len(
        reconstructed
    ) != 19:

        raise RuntimeError(
            "Expected 19 reconstructed cases."
        )


    print(
        "PASS: 19/19 cases reconstructed from closed recovery authority."
    )


    # =============================================================================================
    # LOAD GOVERNED GEOMETRY/MESH CONFIGURATION
    # =============================================================================================

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

    normal_nut_levels_path = (
        CONFIG
        / "nut_mesh_levels.toml"
    )

    cross_size_nut_levels_path = (
        CONFIG
        / "nut_mesh_levels_cross_size_sentinel.toml"
    )


    validation_policy = (
        load_assembly_geometry_validation_policy(
            geometry_validation_path
        )
    )

    base_mesh_template = (
        load_complete_joint_mesh_definition(
            mesh_template_path
        )
    )


    (
        fine_mesh_template,
        selector_hits,
    ) = promote_global_mesh_level_to_fine(
        base_mesh_template
    )


    if len(
        selector_hits
    ) != 1:

        raise RuntimeError(
            "Expected exactly one governed global mesh-level "
            "selector changing medium -> fine; "
            f"found {selector_hits}"
        )


    print(
        "PASS: global mesh-level selector promoted to fine:"
    )

    print(
        "      ",
        selector_hits[
            0
        ],
    )


    joint_classification_template = (
        load_complete_joint_surface_definition(
            joint_classification_path
        )
    )

    bolt_classification_template = (
        load_surface_classification_definition(
            bolt_classification_path
        )
    )

    nut_classification_template = (
        load_nut_surface_classification_definition(
            nut_classification_path
        )
    )


    bolt_levels_path = (
        CONFIG
        / fine_mesh_template
        .bolt_mesh_level_policy
    )


    bolt_mesh_policy = (
        load_mesh_level_policy(
            bolt_levels_path
        )
    )

    normal_nut_policy = (
        load_mesh_level_policy(
            normal_nut_levels_path
        )
    )

    cross_size_nut_policy = (
        load_mesh_level_policy(
            cross_size_nut_levels_path
        )
    )

    quality_definition = (
        load_mesh_quality_definition(
            mesh_quality_path
        )
    )


    # =============================================================================================
    # PURE 19/19 FINE-SIZING PREFLIGHT
    #
    # No STEP, no Gmsh, no file generation.
    # =============================================================================================

    mesh_globals = (
        generate_fem_case_grouped_mesh
        .__globals__
    )


    resolve_mesh_levels_fn = (
        mesh_globals.get(
            "resolve_mesh_levels"
        )
    )

    resolve_joint_sizes_fn = (
        mesh_globals.get(
            "resolve_complete_joint_mesh_sizes"
        )
    )


    if not callable(
        resolve_mesh_levels_fn
    ):

        raise RuntimeError(
            "Mesh-level resolver unavailable."
        )


    if not callable(
        resolve_joint_sizes_fn
    ):

        raise RuntimeError(
            "Complete-joint mesh-size resolver unavailable."
        )


    for item in reconstructed:

        resolved = item[
            "resolved"
        ]

        thread = (
            resolved.thread_standard
            .designation
        )


        geometry = (
            build_geometry_definitions(
                resolved
            )
        )


        definitions = (
            build_fem_case_mesh_definitions(
                resolved,
                geometry,
                mesh_template=(
                    fine_mesh_template
                ),
                joint_classification_template=(
                    joint_classification_template
                ),
                bolt_classification_template=(
                    bolt_classification_template
                ),
                nut_classification_template=(
                    nut_classification_template
                ),
            )
        )


        bolt_levels = (
            resolve_mesh_levels_fn(
                bolt_mesh_policy,
                geometry.external_thread,
            )
        )


        if (
            thread.startswith(
                "M8"
            )
            or thread.startswith(
                "M12"
            )
        ):

            nut_policy = (
                cross_size_nut_policy
            )

        else:

            nut_policy = (
                normal_nut_policy
            )


        nut_levels = (
            resolve_mesh_levels_fn(
                nut_policy,
                geometry.internal_thread,
            )
        )


        sizes = (
            resolve_joint_sizes_fn(
                definitions.mesh,
                bolt_levels,
                nut_levels,
            )
        )


        if sizes.level_name != "fine":

            raise RuntimeError(
                f"{item['recovery']['case_id']}: "
                "true-global-fine preflight failed; "
                f"resolved level={sizes.level_name!r}"
            )


    print(
        "PASS: 19/19 pure sizing preflights resolve TRUE GLOBAL FINE."
    )

    print(
        "PASS: no physical artifact generated before fine-level proof."
    )


    # =============================================================================================
    # PHYSICAL PREPARATION
    # =============================================================================================

    ARTIFACT_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )


    prepared_records = []


    for number, item in enumerate(
        reconstructed,
        start=1,
    ):

        row = item[
            "recovery"
        ]

        resolved = item[
            "resolved"
        ]

        preparation = item[
            "preparation"
        ]

        case_id = row[
            "case_id"
        ]

        thread = (
            resolved.thread_standard
            .designation
        )


        print()
        print(
            "=" * 120
        )

        print(
            f"DA08 GLOBAL FINE "
            f"{number:02d}/19"
        )

        print(
            "Case      :",
            case_id,
        )

        print(
            "Authority :",
            row[
                "authority"
            ],
        )

        print(
            "Run ID    :",
            preparation
            .identity
            .run_id,
        )


        if (
            thread.startswith(
                "M8"
            )
            or thread.startswith(
                "M12"
            )
        ):

            nut_policy = (
                cross_size_nut_policy
            )

            nut_policy_path = (
                cross_size_nut_levels_path
            )

        else:

            nut_policy = (
                normal_nut_policy
            )

            nut_policy_path = (
                normal_nut_levels_path
            )


        geometry_artifact = (
            build_fem_case_geometry(
                resolved,
                artifact_root=(
                    ARTIFACT_ROOT
                ),
                validation_policy=(
                    validation_policy
                ),
            )
        )


        if (
            geometry_artifact.case_hash
            != row[
                "case_hash"
            ]
        ):

            raise RuntimeError(
                f"{case_id}: geometry case-hash drift."
            )


        if (
            geometry_artifact.run_id
            != preparation
            .identity
            .run_id
        ):

            raise RuntimeError(
                f"{case_id}: geometry run-ID drift."
            )


        mesh_artifact = (
            generate_fem_case_grouped_mesh(
                resolved,
                geometry_artifact.geometry,
                step_path=(
                    geometry_artifact
                    .step_path
                ),
                artifact_root=(
                    ARTIFACT_ROOT
                ),
                mesh_template=(
                    fine_mesh_template
                ),
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
                    bolt_mesh_policy
                ),
                nut_mesh_level_policy=(
                    nut_policy
                ),
                local_refinement_policy=None,
            )
        )


        if (
            mesh_artifact.case_hash
            != row[
                "case_hash"
            ]
        ):

            raise RuntimeError(
                f"{case_id}: mesh case-hash drift."
            )


        if (
            mesh_artifact.run_id
            != preparation
            .identity
            .run_id
        ):

            raise RuntimeError(
                f"{case_id}: mesh run-ID drift."
            )


        if (
            mesh_artifact.sizes
            .level_name
            != "fine"
        ):

            raise RuntimeError(
                f"{case_id}: generated mesh is NOT fine."
            )


        if (
            mesh_artifact
            .local_refinement
            is not None
        ):

            raise RuntimeError(
                f"{case_id}: global-fine mesh "
                "unexpectedly contains local refinement."
            )


        if (
            "_fine_"
            not in mesh_artifact
            .msh_path
            .name
        ):

            raise RuntimeError(
                f"{case_id}: mesh filename does "
                "not carry fine identity."
            )


        quality = (
            validate_fem_case_grouped_mesh_quality(
                mesh_artifact,
                quality_definition,
            )
        )


        case_root = (
            ARTIFACT_ROOT
            / preparation
            .identity
            .run_id
        )


        record_path = (
            case_root
            / "da08_global_fine_mesh_preparation.json"
        )


        case_record = {
            "schema":
                "threadrom.da08_global_fine_mesh_preparation.v1",

            "record_status":
                "FINAL_PRE_SOLVE",

            "target_id":
                "member_shortening_v1",

            "ordinal":
                row[
                    "ordinal"
                ],

            "case": {
                "case_id":
                    case_id,

                "case_hash":
                    row[
                        "case_hash"
                    ],

                "resolution_hash":
                    resolved
                    .resolution_hash,

                "run_id":
                    preparation
                    .identity
                    .run_id,

                "recovery_authority":
                    row[
                        "authority"
                    ],

                "thread_designation":
                    thread,

                "member_material_id":
                    row[
                        "member_material_id"
                    ],
            },

            "geometry": {
                "step_relative_path":
                    relative(
                        geometry_artifact
                        .step_path
                    ),

                "step_sha256":
                    sha256(
                        geometry_artifact
                        .step_path
                    ),

                "step_size_bytes":
                    geometry_artifact
                    .step_path
                    .stat()
                    .st_size,
            },

            "mesh": {
                "mesh_level":
                    mesh_artifact
                    .sizes
                    .level_name,

                "mesh_kind":
                    "TRUE_GLOBAL_FINE",

                "local_refinement":
                    None,

                "msh_relative_path":
                    relative(
                        mesh_artifact
                        .msh_path
                    ),

                "msh_sha256":
                    sha256(
                        mesh_artifact
                        .msh_path
                    ),

                "msh_size_bytes":
                    mesh_artifact
                    .msh_path
                    .stat()
                    .st_size,

                "mesh_id":
                    mesh_artifact
                    .definitions
                    .mesh_id,

                "classification_id":
                    mesh_artifact
                    .definitions
                    .classification_id,

                "joint_geometry_id":
                    mesh_artifact
                    .definitions
                    .joint_geometry_id,
            },

            "mesh_policies": {
                "selector_path":
                    selector_hits[
                        0
                    ],

                "bolt_mesh_levels": {
                    "relative_path":
                        relative(
                            bolt_levels_path
                        ),

                    "sha256":
                        sha256(
                            bolt_levels_path
                        ),
                },

                "nut_mesh_levels": {
                    "relative_path":
                        relative(
                            nut_policy_path
                        ),

                    "sha256":
                        sha256(
                            nut_policy_path
                        ),
                },
            },

            "mesh_quality": {
                "status":
                    "PASS",

                "policy_relative_path":
                    relative(
                        mesh_quality_path
                    ),

                "policy_sha256":
                    sha256(
                        mesh_quality_path
                    ),

                "node_count":
                    quality.node_count,

                "tetrahedron_count":
                    quality.tetrahedron_count,

                "degenerate_count":
                    quality.degenerate_count,

                "minimum_volume_mm3":
                    quality.minimum_volume_mm3,

                "minimum_mean_ratio":
                    quality.minimum_mean_ratio,

                "maximum_edge_ratio":
                    quality.maximum_edge_ratio,

                "mixed_orientation":
                    quality.has_mixed_orientation,
            },

            "gates": {
                "exact_case_recovery":
                    "PASS",

                "case_hash":
                    "PASS",

                "resolution_identity":
                    "PASS",

                "geometry_validation":
                    "PASS",

                "step_round_trip":
                    "PASS",

                "true_global_fine_preflight":
                    "PASS",

                "true_global_fine_generated":
                    "PASS",

                "mesh_quality":
                    "PASS",
            },

            "solver": {
                "deck_prepared":
                    False,

                "calculix_authorized":
                    False,

                "calculix_invoked":
                    False,
            },

            "governance": {
                "w06_mutated":
                    False,

                "holdout_accessed":
                    False,

                "dataset_mutated":
                    False,

                "rom_training":
                    False,
            },

            "disposition":
                "DA08_TRUE_GLOBAL_FINE_MESH_PREPARED",
        }


        record_sha = (
            write_immutable_json(
                record_path,
                case_record,
            )
        )


        prepared_records.append(
            {
                "ordinal":
                    row[
                        "ordinal"
                    ],

                "case_id":
                    case_id,

                "case_hash":
                    row[
                        "case_hash"
                    ],

                "run_id":
                    preparation
                    .identity
                    .run_id,

                "authority":
                    row[
                        "authority"
                    ],

                "record_relative_path":
                    relative(
                        record_path
                    ),

                "record_sha256":
                    record_sha,

                "mesh_relative_path":
                    relative(
                        mesh_artifact
                        .msh_path
                    ),

                "mesh_sha256":
                    sha256(
                        mesh_artifact
                        .msh_path
                    ),

                "node_count":
                    quality.node_count,

                "tetrahedron_count":
                    quality.tetrahedron_count,
            }
        )


        print(
            "Mesh level : fine"
        )

        print(
            "Nodes      :",
            quality.node_count,
        )

        print(
            "Tets       :",
            quality.tetrahedron_count,
        )

        print(
            "Mesh SHA   :",
            sha256(
                mesh_artifact
                .msh_path
            ),
        )

        print(
            "Quality    : PASS"
        )

        print(
            "CalculiX   : NO"
        )


    # =============================================================================================
    # CERTIFICATE
    # =============================================================================================

    if len(
        prepared_records
    ) != 19:

        raise RuntimeError(
            "Expected 19 prepared global-fine meshes."
        )


    certificate = {
        "schema":
            "threadrom.da08_global_fine_mesh_campaign.v1",

        "record_status":
            "FINAL_PRE_SOLVE",

        "target_id":
            "member_shortening_v1",

        "exact_case_recovery": {
            "relative_path":
                relative(
                    RECOVERY_PATH
                ),

            "sha256":
                sha256(
                    RECOVERY_PATH
                ),
        },

        "fine_reference_campaign": {
            "relative_path":
                relative(
                    CAMPAIGN_PATH
                ),

            "sha256":
                sha256(
                    CAMPAIGN_PATH
                ),
        },

        "case_count":
            19,

        "global_fine_mesh_count":
            19,

        "mesh_quality_pass_count":
            19,

        "cases":
            sorted(
                prepared_records,
                key=lambda row: row[
                    "ordinal"
                ],
            ),

        "authorization": {
            "fine_mesh_preparation":
                True,

            "solver_deck_preparation":
                False,

            "calculix_launch":
                False,
        },

        "governance": {
            "w06_mutated":
                False,

            "holdout_accessed":
                False,

            "dataset_mutated":
                False,

            "rom_training":
                False,
        },

        "disposition":
            "DA08_TRUE_GLOBAL_FINE_MESH_PREPARATION_COMPLETE",
    }


    certificate_sha = (
        write_immutable_json(
            CERTIFICATE_PATH,
            certificate,
        )
    )


    sidecar_text = (
        certificate_sha
        + "  "
        + CERTIFICATE_PATH.name
        + "\n"
    )


    if CERTIFICATE_SIDECAR.exists():

        if (
            CERTIFICATE_SIDECAR.read_text(
                encoding="ascii"
            )
            != sidecar_text
        ):

            raise RuntimeError(
                "Fine-mesh certificate sidecar drift."
            )

    else:

        CERTIFICATE_SIDECAR.write_text(
            sidecar_text,
            encoding="ascii",
        )


    print()
    print(
        "=" * 120
    )

    print(
        "DA08 TRUE GLOBAL-FINE MESH PREPARATION COMPLETE"
    )

    print(
        "=" * 120
    )

    print(
        "Exact cases       : 19/19"
    )

    print(
        "Fine preflight    : 19/19"
    )

    print(
        "Fine meshes       : 19/19"
    )

    print(
        "Mesh quality PASS : 19/19"
    )

    print(
        "CalculiX          : NO"
    )

    print(
        "W06               : UNTOUCHED"
    )

    print(
        "Holdouts          : UNTOUCHED"
    )

    print(
        "Certificate       :",
        relative(
            CERTIFICATE_PATH
        ),
    )

    print(
        "Certificate SHA   :",
        certificate_sha,
    )

    print()
    print(
        "NEXT : DA08 FINE-REFERENCE "
        "SOLVER-DECK PREPARATION"
    )

    print(
        "=" * 120
    )


    return 0


if __name__ == "__main__":

    raise SystemExit(
        main()
    )
