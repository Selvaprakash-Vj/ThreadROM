from __future__ import annotations

import hashlib
import inspect
import json
from dataclasses import (
    fields,
    is_dataclass,
    replace,
)
from pathlib import Path
from typing import Any


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

CONFIG = (
    ROOT
    / "config"
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

DOE_POLICY_PATH = (
    CONFIG
    / "phase3_production_doe.toml"
)

EXPECTED_DOE_POLICY_SHA256 = (
    "43032557cb2abead0118362bcfc6a9b2e5246a7d363ca83eef5fcf35054befc1"
)

ARTIFACT_ROOT = (
    ROOT
    / "simulations"
    / "staging"
    / "phase3_rom_dataset_admission"
    / "da08_fine_reference"
)

SUMMARY_PATH = (
    ARTIFACT_ROOT
    / "da08_fine_reference_preparation_certificate.json"
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
        path.relative_to(
            ROOT
        )
    ).replace(
        "\\",
        "/",
    )


def write_immutable_json(
    path: Path,
    payload: dict[str, Any],
) -> tuple[str, str]:

    rendered = (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode(
        "utf-8"
    )

    digest = hashlib.sha256(
        rendered
    ).hexdigest()

    if path.exists():

        existing = path.read_bytes()

        if existing != rendered:

            raise RuntimeError(
                "Immutable DA08 artifact already exists with "
                f"different content: {path}"
            )

        return (
            "REUSED_IDENTICAL",
            digest,
        )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_bytes(
        rendered
    )

    return (
        "CREATED",
        digest,
    )


def call_build_production_doe(
    policy,
):

    signature = inspect.signature(
        build_phase3_production_doe
    )

    required = [
        parameter
        for parameter in signature.parameters.values()
        if (
            parameter.default
            is inspect.Parameter.empty
            and parameter.kind
            in {
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.KEYWORD_ONLY,
            }
        )
    ]


    if len(
        signature.parameters
    ) == 0:

        return (
            build_phase3_production_doe()
        )


    if "policy" in signature.parameters:

        return (
            build_phase3_production_doe(
                policy=policy
            )
        )


    if len(required) == 1:

        return (
            build_phase3_production_doe(
                policy
            )
        )


    raise RuntimeError(
        "Unsupported build_phase3_production_doe API: "
        f"{signature}"
    )


def walk_objects(
    value: Any,
    *,
    depth: int = 0,
    seen: set[int] | None = None,
):

    if depth > 12:
        return

    if seen is None:
        seen = set()

    identity = id(
        value
    )

    if identity in seen:
        return

    seen.add(
        identity
    )

    yield value


    if is_dataclass(
        value
    ):

        for field in fields(
            value
        ):

            yield from walk_objects(
                getattr(
                    value,
                    field.name,
                ),
                depth=depth + 1,
                seen=seen,
            )


    elif isinstance(
        value,
        dict,
    ):

        for child in value.values():

            yield from walk_objects(
                child,
                depth=depth + 1,
                seen=seen,
            )


    elif isinstance(
        value,
        (
            tuple,
            list,
        ),
    ):

        for child in value:

            yield from walk_objects(
                child,
                depth=depth + 1,
                seen=seen,
            )


def production_case_index(
    production,
) -> dict[
    tuple[str, str],
    Any,
]:

    result = {}

    for obj in walk_objects(
        production
    ):

        case_id = getattr(
            obj,
            "case_id",
            None,
        )

        case_hash = getattr(
            obj,
            "case_hash",
            None,
        )

        case = getattr(
            obj,
            "case",
            None,
        )


        if (
            isinstance(
                case_id,
                str,
            )
            and isinstance(
                case_hash,
                str,
            )
            and case is not None
        ):

            result[
                (
                    case_id,
                    case_hash,
                )
            ] = obj


    return result


def force_global_fine(
    mesh_template,
):

    if not is_dataclass(
        mesh_template
    ):

        raise RuntimeError(
            "CompleteJointMeshDefinition is unexpectedly "
            "not a dataclass."
        )


    field_names = {
        field.name
        for field in fields(
            mesh_template
        )
    }


    candidates = [
        name
        for name in (
            "mesh_level",
            "level_name",
            "mesh_level_name",
        )
        if name in field_names
    ]


    if len(
        candidates
    ) != 1:

        raise RuntimeError(
            "Unable to identify exactly one governed mesh-level "
            "selector on CompleteJointMeshDefinition. "
            f"Candidates: {candidates}; "
            f"fields: {sorted(field_names)}"
        )


    selector = candidates[
        0
    ]

    original = getattr(
        mesh_template,
        selector,
    )


    if not isinstance(
        original,
        str,
    ):

        raise RuntimeError(
            "Governed mesh-level selector is not textual."
        )


    fine_template = replace(
        mesh_template,
        **{
            selector:
                "fine",
        },
    )


    if getattr(
        fine_template,
        selector,
    ) != "fine":

        raise RuntimeError(
            "Global-fine mesh-template replacement failed."
        )


    return (
        fine_template,
        selector,
        original,
    )


def main() -> int:

    # ==============================================================================================
    # PINNED AUTHORITIES
    # ==============================================================================================

    if sha256(
        CAMPAIGN_PATH
    ) != EXPECTED_CAMPAIGN_SHA256:

        raise RuntimeError(
            "Frozen DA08 campaign SHA drift."
        )


    if sha256(
        DOE_POLICY_PATH
    ) != EXPECTED_DOE_POLICY_SHA256:

        raise RuntimeError(
            "Production DOE policy SHA drift."
        )


    campaign = json.loads(
        CAMPAIGN_PATH.read_text(
            encoding="utf-8"
        )
    )


    if (
        campaign.get(
            "record_status"
        )
        != "FROZEN_PRE_EXECUTION"
    ):

        raise RuntimeError(
            "DA08 campaign is not FROZEN_PRE_EXECUTION."
        )


    frozen_cases = campaign.get(
        "cases"
    )

    if (
        not isinstance(
            frozen_cases,
            list,
        )
        or len(
            frozen_cases
        ) != 19
    ):

        raise RuntimeError(
            "Expected exactly 19 frozen DA08 cases."
        )


    # ==============================================================================================
    # RECOVER EXACT GOVERNED CASE OBJECTS BEFORE WRITING ANY PHYSICAL ARTIFACT
    # ==============================================================================================

    doe_policy = (
        load_phase3_production_doe_policy(
            DOE_POLICY_PATH
        )
    )

    production = (
        call_build_production_doe(
            doe_policy
        )
    )

    case_index = (
        production_case_index(
            production
        )
    )


    governed_cases = []


    for frozen in frozen_cases:

        identity = (
            frozen[
                "case_id"
            ],
            frozen[
                "case_hash"
            ],
        )

        production_case = (
            case_index.get(
                identity
            )
        )


        if production_case is None:

            raise RuntimeError(
                "Frozen DA08 case is absent from deterministic "
                "Production-DOE case generation: "
                f"{identity[0]} / {identity[1]}"
            )


        resolved = resolve_case(
            production_case.case
        )


        if (
            resolved.case_hash
            != frozen[
                "case_hash"
            ]
        ):

            raise RuntimeError(
                "Recovered DA08 case hash mismatch: "
                f"{frozen['case_id']}"
            )


        governed_cases.append(
            (
                frozen,
                production_case,
                resolved,
            )
        )


    if len(
        governed_cases
    ) != 19:

        raise RuntimeError(
            "DA08 exact-case recovery failed."
        )


    print(
        "PASS: 19/19 frozen cases recovered "
        "from deterministic Production-DOE generation."
    )


    # ==============================================================================================
    # LOAD GOVERNED TEMPLATES
    # ==============================================================================================

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
        mesh_selector,
        production_mesh_level,
    ) = force_global_fine(
        base_mesh_template
    )


    print(
        "PASS: governed mesh selector identified: "
        f"{mesh_selector}"
    )

    print(
        "Production template level:",
        production_mesh_level,
    )

    print(
        "DA08 reference level      : fine"
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


    bolt_mesh_level_path = (
        CONFIG
        / fine_mesh_template.bolt_mesh_level_policy
    )


    bolt_mesh_level_policy = (
        load_mesh_level_policy(
            bolt_mesh_level_path
        )
    )


    ordinary_nut_mesh_level_path = (
        CONFIG
        / fine_mesh_template.nut_mesh_level_policy
    )

    cross_size_nut_mesh_level_path = (
        CONFIG
        / "nut_mesh_levels_cross_size_sentinel.toml"
    )


    ordinary_nut_policy = (
        load_mesh_level_policy(
            ordinary_nut_mesh_level_path
        )
    )

    cross_size_nut_policy = (
        load_mesh_level_policy(
            cross_size_nut_mesh_level_path
        )
    )


    quality_definition = (
        load_mesh_quality_definition(
            mesh_quality_path
        )
    )


    # ==============================================================================================
    # GLOBAL FINE GENERATION
    # ==============================================================================================

    ARTIFACT_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )


    records = []


    for index, (
        frozen,
        production_case,
        resolved,
    ) in enumerate(
        governed_cases,
        start=1,
    ):

        case_id = frozen[
            "case_id"
        ]

        thread = (
            frozen[
                "cohort"
            ][
                "thread_designation"
            ]
        )


        print()
        print("=" * 120)

        print(
            f"DA08 GLOBAL-FINE "
            f"{index:02d}/19"
        )

        print(
            "Case ID   :",
            case_id,
        )

        print(
            "Thread    :",
            thread,
        )

        print(
            "Case hash :",
            frozen[
                "case_hash"
            ],
        )


        preparation = (
            derive_fem_case_preparation(
                resolved
            )
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
            != frozen[
                "case_hash"
            ]
        ):

            raise RuntimeError(
                f"{case_id}: geometry case-hash mismatch."
            )


        if (
            geometry_artifact.run_id
            != preparation.identity.run_id
        ):

            raise RuntimeError(
                f"{case_id}: geometry run-ID mismatch."
            )


        # Existing ThreadROM governance already established the
        # cross-size nut policy for M8/M12 families.
        #
        # The frozen global-fine sizing factors are currently identical,
        # but this selector preserves the correct provenance authority.

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
                cross_size_nut_mesh_level_path
            )

        else:

            nut_policy = (
                ordinary_nut_policy
            )

            nut_policy_path = (
                ordinary_nut_mesh_level_path
            )


        mesh_artifact = (
            generate_fem_case_grouped_mesh(
                resolved,
                geometry_artifact.geometry,
                step_path=(
                    geometry_artifact.step_path
                ),
                artifact_root=ARTIFACT_ROOT,
                mesh_template=fine_mesh_template,
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
                    nut_policy
                ),
                local_refinement_policy=None,
            )
        )


        if (
            mesh_artifact.case_hash
            != frozen[
                "case_hash"
            ]
        ):

            raise RuntimeError(
                f"{case_id}: mesh case-hash mismatch."
            )


        if (
            mesh_artifact.run_id
            != preparation.identity.run_id
        ):

            raise RuntimeError(
                f"{case_id}: mesh run-ID mismatch."
            )


        if (
            mesh_artifact.sizes.level_name
            != "fine"
        ):

            raise RuntimeError(
                f"{case_id}: produced mesh is not global fine; "
                f"got {mesh_artifact.sizes.level_name!r}."
            )


        if (
            mesh_artifact.local_refinement
            is not None
        ):

            raise RuntimeError(
                f"{case_id}: global-fine reference unexpectedly "
                "contains local refinement."
            )


        quality = (
            validate_fem_case_grouped_mesh_quality(
                mesh_artifact,
                quality_definition,
            )
        )


        case_root = (
            ARTIFACT_ROOT
            / preparation.identity.run_id
        )

        record_path = (
            case_root
            / "da08_fine_reference_preparation.json"
        )


        record = {
            "schema":
                "threadrom.da08_fine_reference_preparation.v1",

            "record_status":
                "FINAL_PRE_SOLVE",

            "target_id":
                "member_shortening_v1",

            "ordinal":
                frozen[
                    "ordinal"
                ],

            "case": {
                "case_id":
                    case_id,

                "case_hash":
                    frozen[
                        "case_hash"
                    ],

                "run_id":
                    preparation.identity.run_id,

                "thread_designation":
                    thread,

                "member_material_id":
                    frozen[
                        "cohort"
                    ][
                        "member_material_id"
                    ],

                "radial_regime":
                    frozen[
                        "cohort"
                    ][
                        "radial_regime"
                    ],
            },

            "reference_mesh": {
                "kind":
                    "GLOBAL_FINE",

                "mesh_level":
                    mesh_artifact.sizes.level_name,

                "local_refinement":
                    None,

                "mesh_level_selector_field":
                    mesh_selector,

                "bolt_policy_relative_path":
                    relative(
                        bolt_mesh_level_path
                    ),

                "bolt_policy_sha256":
                    sha256(
                        bolt_mesh_level_path
                    ),

                "nut_policy_relative_path":
                    relative(
                        nut_policy_path
                    ),

                "nut_policy_sha256":
                    sha256(
                        nut_policy_path
                    ),
            },

            "geometry": {
                "step_relative_path":
                    relative(
                        geometry_artifact.step_path
                    ),

                "step_sha256":
                    sha256(
                        geometry_artifact.step_path
                    ),

                "step_size_bytes":
                    geometry_artifact.step_path.stat().st_size,
            },

            "mesh": {
                "msh_relative_path":
                    relative(
                        mesh_artifact.msh_path
                    ),

                "msh_sha256":
                    sha256(
                        mesh_artifact.msh_path
                    ),

                "msh_size_bytes":
                    mesh_artifact.msh_path.stat().st_size,

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

            "mesh_quality_policy": {
                "relative_path":
                    relative(
                        mesh_quality_path
                    ),

                "sha256":
                    sha256(
                        mesh_quality_path
                    ),
            },

            "gates": {
                "frozen_campaign_membership":
                    "PASS",

                "exact_case_hash":
                    "PASS",

                "geometry_validation":
                    "PASS",

                "step_round_trip_validation":
                    "PASS",

                "global_fine_mesh_generation":
                    "PASS",

                "global_fine_identity":
                    "PASS",

                "mesh_quality":
                    "PASS",

                "holdout_accessed":
                    False,

                "calculix_invoked":
                    False,
            },

            "solver_authorization": {
                "calculix_launch_authorized":
                    False,

                "preload_calibration_performed":
                    False,
            },

            "overall_disposition":
                "DA08_GLOBAL_FINE_REFERENCE_PREPARED",
        }


        action, record_sha = (
            write_immutable_json(
                record_path,
                record,
            )
        )


        records.append(
            {
                "ordinal":
                    frozen[
                        "ordinal"
                    ],

                "case_id":
                    case_id,

                "case_hash":
                    frozen[
                        "case_hash"
                    ],

                "run_id":
                    preparation.identity.run_id,

                "preparation_record":
                    relative(
                        record_path
                    ),

                "preparation_record_sha256":
                    record_sha,

                "mesh_sha256":
                    sha256(
                        mesh_artifact.msh_path
                    ),

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
            "Mesh       :",
            relative(
                mesh_artifact.msh_path
            ),
        )

        print(
            "Record     :",
            relative(
                record_path
            ),
        )

        print(
            "Action     :",
            action,
        )

        print(
            "CalculiX   : NO"
        )


    # ==============================================================================================
    # CAMPAIGN PREPARATION CERTIFICATE
    # ==============================================================================================

    if len(
        records
    ) != 19:

        raise RuntimeError(
            "Expected exactly 19 prepared DA08 references."
        )


    certificate = {
        "schema":
            "threadrom.da08_fine_reference_preparation_certificate.v1",

        "record_status":
            "FINAL_PRE_SOLVE",

        "target_id":
            "member_shortening_v1",

        "campaign_sha256":
            EXPECTED_CAMPAIGN_SHA256,

        "production_doe_policy_sha256":
            EXPECTED_DOE_POLICY_SHA256,

        "reference_case_count":
            19,

        "prepared_case_count":
            len(
                records
            ),

        "global_fine_count":
            len(
                records
            ),

        "calculix_invoked":
            False,

        "holdout_accessed":
            False,

        "dataset_mutated":
            False,

        "rom_training":
            False,

        "w06_mutated":
            False,

        "records":
            sorted(
                records,
                key=lambda row: row[
                    "ordinal"
                ],
            ),

        "authorization": {
            "fine_reference_meshes_prepared":
                True,

            "fine_reference_decks_prepared":
                False,

            "calculix_launch_authorized":
                False,
        },

        "disposition":
            "DA08_GLOBAL_FINE_REFERENCE_MESH_PREPARATION_COMPLETE",
    }


    action, certificate_sha = (
        write_immutable_json(
            SUMMARY_PATH,
            certificate,
        )
    )


    print()
    print("=" * 120)

    print(
        "DA08 GLOBAL-FINE REFERENCE MESH PREPARATION"
    )

    print("=" * 120)

    print(
        "Prepared        : 19/19"
    )

    print(
        "Global fine     : 19/19"
    )

    print(
        "CalculiX        : NO"
    )

    print(
        "Holdout access  : NO"
    )

    print(
        "W06 mutated     : NO"
    )

    print(
        "Certificate     :",
        relative(
            SUMMARY_PATH
        ),
    )

    print(
        "Certificate SHA :",
        certificate_sha,
    )

    print(
        "Record action   :",
        action,
    )

    print()

    print(
        "NEXT GATE       : "
        "DA08 FINE-REFERENCE DECK PREPARATION"
    )

    print("=" * 120)


    return 0


if __name__ == "__main__":

    raise SystemExit(
        main()
    )
