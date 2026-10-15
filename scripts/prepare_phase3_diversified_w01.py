from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import os
import tomllib

from enum import Enum
from pathlib import Path

from threadrom.case.resolver import resolve_case

from threadrom.factory.diversified_doe_design import (
    _build_case,
)

from threadrom.factory.fem_case_definition_bundle import (
    build_generic_fem_definition_bundle,
)

from threadrom.factory.fem_case_geometry import (
    build_fem_case_geometry,
)

from threadrom.factory.fem_case_mesh import (
    generate_fem_case_grouped_mesh,
    validate_fem_case_grouped_mesh_quality,
)

from threadrom.factory.fem_preload_calibration_deck import (
    write_fem_preload_calibration_trial_deck,
)

from threadrom.factory.preload_calibration_campaign import (
    derive_initial_preload_calibration_trial,
)

from threadrom.geometry.complete_joint_assembly import (
    load_assembly_geometry_validation_policy,
)

from threadrom.materials.diversified_candidate_catalog import (
    DIVERSIFIED_CANDIDATE_MATERIAL_CATALOG,
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

from threadrom.solver.complete_joint_boundary_regions import (
    load_complete_joint_boundary_region_definition,
)

from threadrom.solver.complete_joint_calculix_transfer import (
    load_complete_joint_calculix_transfer_definition,
    read_grouped_complete_joint_mesh,
)

from threadrom.solver.complete_joint_contact import (
    load_complete_joint_contact_definition,
)


ROOT = Path(r"D:\ThreadROM").resolve()
CONFIG = ROOT / "config"

DOC_ROOT = (
    ROOT
    / "docs"
    / "phase3_diversified_doe"
)

WAVE_ROOT = (
    DOC_ROOT
    / "waves"
    / "TRM-DDOE-001-W01"
)

PROPOSAL_PATH = (
    DOC_ROOT
    / "design_proposal.json"
)

POLICY_PATH = (
    CONFIG
    / "phase3_diversified_doe.toml"
)

WAVE_PATH = (
    WAVE_ROOT
    / "wave_plan.json"
)

TRIAL_AUTH_PATH = (
    WAVE_ROOT
    / "trial1_owner_authorization.json"
)

ARTIFACT_AUTH_PATH = (
    WAVE_ROOT
    / "geometry_mesh_owner_authorization.json"
)

CAMPAIGN_ROOT = (
    ROOT
    / "simulations"
    / "staging"
    / "phase3_diversified_doe"
    / "TRM-DDOE-001"
    / "W01"
)

PREPARED_ROOT = (
    CAMPAIGN_ROOT
    / "prepared_cases"
)

SOLVER_ROOT = (
    CAMPAIGN_ROOT
    / "solver_preparation"
)


EXPECTED_PROPOSAL_SHA = (
    "a386da9648af88b5577386efdc16643b0b099fe2614c2bcc18c0e8973d141e1e"
)

EXPECTED_POLICY_SHA = (
    "6d0e45c109b1ba0a279ec0f06467ea91392760171b9a91bf0467d763896108d9"
)

EXPECTED_WAVE_SHA = (
    "7896622edb754e5ce970b1cc6b5ccf157b591ae826e78c0abb9f8e373382a79d"
)

EXPECTED_TRIAL_AUTH_SHA = (
    "d0de4342f65a95525bfd2042cc650853bf5a4afd7203c54c9f61201740d3dfe4"
)

EXPECTED_ARTIFACT_AUTH_SHA = (
    "a1596d6c65c34f08782f6ab78ba2141590670e72ac008cb7d9dbdcfe0c0136ac"
)


REUSE_SOURCES = {
    "TRM-DDOE-D-M8x1_25__steel_member-12": {
        "source_case_id":
            "TRM-XFEM-M8-001",

        "source_case_hash":
            "e1628981295e3fc47ecf623e5743362c8e048c01c7cb7a5def44a75a40b9e27c",

        "step_path":
            ROOT
            / "simulations"
            / "staging"
            / "phase3_cp11_m8_two_pitch_nut022_final"
            / "prepared_cases"
            / "trm_fem_771a201b2752"
            / "geometry"
            / "complete_joint_assembly.step",

        "step_sha256":
            "8c8e2b948a2b7e75bb6196dbfaf25b7d85817dcc9a56a0f49e158d8a17670760",

        "mesh_path":
            ROOT
            / "simulations"
            / "staging"
            / "phase3_cp11_m8_two_pitch_nut022_final"
            / "prepared_cases"
            / "trm_fem_771a201b2752"
            / "mesh"
            / "complete_joint_grouped_medium_first_order.msh",

        "mesh_sha256":
            "c66795aa39da7303779ed98eece27c7f49e25bf9640cfc5887b39b7466558760",
    },

    "TRM-DDOE-D-M12x1_75__steel_member-12": {
        "source_case_id":
            "TRM-XFEM-M12-001",

        "source_case_hash":
            "c2386623c11def2e3dc447c885c1408408a2d136c04a5a5e53b1958de062f5da",

        "step_path":
            ROOT
            / "simulations"
            / "staging"
            / "phase3_cp11_m12_two_pitch_nut022_proof"
            / "prepared_cases"
            / "trm_fem_4606556202c1"
            / "geometry"
            / "complete_joint_assembly.step",

        "step_sha256":
            "aea5fa2a8002c3b806b39887c90da8f5e870e29f653ae2463c74f1a71e2b6994",

        "mesh_path":
            ROOT
            / "simulations"
            / "staging"
            / "phase3_cp11_m12_two_pitch_nut022_proof"
            / "prepared_cases"
            / "trm_fem_4606556202c1"
            / "mesh"
            / "complete_joint_grouped_medium_first_order.msh",

        "mesh_sha256":
            "5634f677caa20e564b92462fca2713b50de1a4e98d952c47052305d6e5c4ffc9",
    },
}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha256(path: Path) -> str:
    require(
        path.is_file()
        and path.stat().st_size > 0,
        f"Required artifact missing/empty: {path}",
    )

    digest = hashlib.sha256()

    with path.open("rb") as stream:
        for chunk in iter(
            lambda: stream.read(
                8 * 1024 * 1024
            ),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def jsonable(value):
    if dataclasses.is_dataclass(value):
        return {
            field.name:
                jsonable(
                    getattr(
                        value,
                        field.name,
                    )
                )
            for field in dataclasses.fields(
                value
            )
        }

    if isinstance(value, Enum):
        return value.value

    if isinstance(value, Path):
        try:
            return str(
                value.resolve().relative_to(
                    ROOT
                )
            ).replace("\\", "/")
        except ValueError:
            return str(value)

    if isinstance(value, dict):
        return {
            str(key):
                jsonable(child)
            for key, child in value.items()
        }

    if isinstance(
        value,
        (list, tuple),
    ):
        return [
            jsonable(child)
            for child in value
        ]

    return value


def canonical_bytes(value) -> bytes:
    return (
        json.dumps(
            jsonable(value),
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def write_immutable_json(
    path: Path,
    value,
):
    content = canonical_bytes(
        value
    )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        with path.open("xb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(
                stream.fileno()
            )

    except FileExistsError:
        if path.read_bytes() != content:
            raise RuntimeError(
                "Immutable record drift: "
                f"{path}"
            )

    record_sha = sha256(
        path
    )

    sidecar = path.with_suffix(
        ".sha256"
    )

    sidecar_content = (
        f"{record_sha}  {path.name}\n"
    ).encode("ascii")

    try:
        with sidecar.open("xb") as stream:
            stream.write(
                sidecar_content
            )

    except FileExistsError:
        if (
            sidecar.read_bytes()
            != sidecar_content
        ):
            raise RuntimeError(
                "SHA sidecar drift: "
                f"{sidecar}"
            )

    return record_sha


def reference_temperature_c() -> float:
    data = tomllib.loads(
        (
            CONFIG
            / "complete_joint_preload.toml"
        ).read_text(
            encoding="utf-8-sig"
        )
    )

    matches = []

    def walk(value):
        if isinstance(
            value,
            dict,
        ):
            for key, child in value.items():
                if (
                    key
                    == "reference_temperature_c"
                ):
                    matches.append(
                        float(child)
                    )
                else:
                    walk(child)

        elif isinstance(
            value,
            list,
        ):
            for child in value:
                walk(child)

    walk(data)

    require(
        len(matches) == 1,
        "Expected exactly one governed "
        "reference_temperature_c.",
    )

    result = matches[0]

    require(
        math.isfinite(result),
        "Governed reference temperature "
        "is not finite.",
    )

    return result


# ============================================================
# GOVERNANCE BINDING
# ============================================================

require(
    sha256(PROPOSAL_PATH)
    == EXPECTED_PROPOSAL_SHA,
    "Diversified DOE proposal SHA drift.",
)

require(
    sha256(POLICY_PATH)
    == EXPECTED_POLICY_SHA,
    "Diversified DOE policy SHA drift.",
)

require(
    sha256(WAVE_PATH)
    == EXPECTED_WAVE_SHA,
    "W01 wave-plan SHA drift.",
)

require(
    sha256(TRIAL_AUTH_PATH)
    == EXPECTED_TRIAL_AUTH_SHA,
    "W01 Trial-1 authorization SHA drift.",
)

require(
    sha256(ARTIFACT_AUTH_PATH)
    == EXPECTED_ARTIFACT_AUTH_SHA,
    "W01 artifact authorization SHA drift.",
)


proposal = json.loads(
    PROPOSAL_PATH.read_text(
        encoding="utf-8-sig"
    )
)

policy = tomllib.loads(
    POLICY_PATH.read_text(
        encoding="utf-8-sig"
    )
)

wave = json.loads(
    WAVE_PATH.read_text(
        encoding="utf-8-sig"
    )
)

trial_auth = json.loads(
    TRIAL_AUTH_PATH.read_text(
        encoding="utf-8-sig"
    )
)

artifact_auth = json.loads(
    ARTIFACT_AUTH_PATH.read_text(
        encoding="utf-8-sig"
    )
)


require(
    wave["record_status"]
    == "FINAL"
    and wave["selection_status"]
    == "FROZEN_SELECTION"
    and wave["wave_size"] == 4
    and wave["initial_trial_index"] == 1,
    "W01 is not the frozen four-case Trial-1 wave.",
)

require(
    trial_auth[
        "permissions"
    ][
        "prepare_trial_1"
    ]
    is True,
    "Trial-1 preparation authority absent.",
)

require(
    trial_auth[
        "permissions"
    ][
        "additional_trials"
    ]
    is False,
    "Unexpected additional-trial authority.",
)

require(
    artifact_auth[
        "permissions"
    ][
        "generate_geometry_for_fresh_cases"
    ]
    is True
    and artifact_auth[
        "permissions"
    ][
        "generate_mesh_for_fresh_cases"
    ]
    is True,
    "Fresh geometry/mesh authority absent.",
)

require(
    artifact_auth[
        "permissions"
    ][
        "regenerate_geometry_for_reuse_cases"
    ]
    is False
    and artifact_auth[
        "permissions"
    ][
        "regenerate_mesh_for_reuse_cases"
    ]
    is False,
    "Reuse-case regeneration must remain prohibited.",
)


rows = {
    row["proposal_id"]: row
    for row in proposal["cases"]
}

fresh_ids = {
    row["case_id"]
    for row in artifact_auth[
        "fresh_generation_cases"
    ]
}

reuse_ids = {
    row["case_id"]
    for row in artifact_auth[
        "mandatory_reuse_cases"
    ]
}

wave_ids = {
    row["proposal_id"]
    for row in wave["selected_cases"]
}

require(
    fresh_ids | reuse_ids
    == wave_ids,
    "Artifact authorization/W01 cohort drift.",
)

require(
    fresh_ids.isdisjoint(
        reuse_ids
    ),
    "Fresh/reuse cohorts overlap.",
)


# ============================================================
# GOVERNED PREPARATION TEMPLATES
# ============================================================

validation_policy = (
    load_assembly_geometry_validation_policy(
        CONFIG
        / "assembly_geometry_validation.toml"
    )
)

mesh_template = (
    load_complete_joint_mesh_definition(
        CONFIG
        / "complete_joint_mesh.toml"
    )
)

joint_classification_template = (
    load_complete_joint_surface_definition(
        CONFIG
        / "complete_joint_surface_classification.toml"
    )
)

bolt_classification_template = (
    load_surface_classification_definition(
        CONFIG
        / "surface_classification.toml"
    )
)

nut_classification_template = (
    load_nut_surface_classification_definition(
        CONFIG
        / "nut_surface_classification.toml"
    )
)

bolt_mesh_level_policy = (
    load_mesh_level_policy(
        CONFIG
        / mesh_template.bolt_mesh_level_policy
    )
)

# ------------------------------------------------------------
# Governed cross-size nut-thread refinement
#
# Prior M8/M12 cross-size qualification demonstrated that
# medium global sizing with nut thread/minimum factors 0.22
# removes isolated internal-thread sliver tetrahedra.
#
# The repository production config is NOT modified.
# ------------------------------------------------------------

nut_policy_source = (
    CONFIG
    / mesh_template.nut_mesh_level_policy
)

nut_policy_text = (
    nut_policy_source.read_text(
        encoding="utf-8-sig"
    )
)

old_medium = """[levels.medium]
maximum_size_pitch_factor = 0.67
minimum_size_thread_depth_factor = 0.33
thread_surface_size_depth_factor = 0.33
"""

new_medium = """[levels.medium]
maximum_size_pitch_factor = 0.67
minimum_size_thread_depth_factor = 0.22
thread_surface_size_depth_factor = 0.22
"""

require(
    nut_policy_text.count(old_medium) == 1,
    "Expected governed medium nut-mesh policy block "
    "not found exactly once.",
)

w01_nut_policy_path = (
    CAMPAIGN_ROOT
    / "w01_targeted_nut_mesh_levels.toml"
)

w01_nut_policy_text = (
    nut_policy_text.replace(
        old_medium,
        new_medium,
        1,
    )
)

if w01_nut_policy_path.exists():

    require(
        w01_nut_policy_path.read_text(
            encoding="utf-8-sig"
        )
        == w01_nut_policy_text,
        "Existing W01 targeted nut policy drift.",
    )

else:

    w01_nut_policy_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    w01_nut_policy_path.write_text(
        w01_nut_policy_text,
        encoding="utf-8",
        newline="\n",
    )

nut_mesh_level_policy = (
    load_mesh_level_policy(
        w01_nut_policy_path
    )
)

mesh_quality = (
    load_mesh_quality_definition(
        CONFIG
        / "complete_joint_mesh_quality.toml"
    )
)

transfer_template = (
    load_complete_joint_calculix_transfer_definition(
        CONFIG
        / "complete_joint_calculix_transfer.toml"
    )
)

contact_template = (
    load_complete_joint_contact_definition(
        CONFIG
        / "complete_joint_contact.toml"
    )
)

boundary_template = (
    load_complete_joint_boundary_region_definition(
        CONFIG
        / "complete_joint_boundary_regions.toml"
    )
)

reference_temperature = (
    reference_temperature_c()
)


# ============================================================
# PREPARE EXACTLY FOUR W01 CASES
# ============================================================

PREPARED_ROOT.mkdir(
    parents=True,
    exist_ok=True,
)

SOLVER_ROOT.mkdir(
    parents=True,
    exist_ok=True,
)

prepared = []


print()
print(
    "=" * 110
)
print(
    "THREADROM — TRM-DDOE-001-W01 REAL PREPARATION"
)
print(
    "=" * 110
)
print(
    "Fresh geometry/mesh : 2"
)
print(
    "Certified reuse     : 2"
)
print(
    "CalculiX launch     : NO"
)
print()


for selected in sorted(
    wave["selected_cases"],
    key=lambda item: item["wave_order"],
):
    case_id = selected[
        "proposal_id"
    ]

    proposal_row = rows.get(
        case_id
    )

    require(
        proposal_row is not None,
        f"W01 proposal row missing: {case_id}",
    )

    size = next(
        item
        for item in policy[
            "size_candidates"
        ]
        if item[
            "designation"
        ]
        == proposal_row[
            "thread_designation"
        ]
    )

    case, _ = _build_case(
        policy,
        size,
        proposal_row[
            "member_material_id"
        ],
        tuple(
            proposal_row[
                "normalized_coordinates"
            ]
        ),
    )

    resolved = resolve_case(
        case,
        material_catalog=(
            DIVERSIFIED_CANDIDATE_MATERIAL_CATALOG
        ),
    )

    case_hash = proposal_row[
        "case_hash"
    ]

    case_run_id = proposal_row[
        "preparation_run_id"
    ]

    trial_run_id = selected[
        "trial_1_run_id"
    ]

    require(
        resolved.case_hash
        == case_hash,
        f"{case_id}: resolved case hash drift.",
    )

    require(
        case_run_id
        == selected["preparation_run_id"],
        f"{case_id}: proposal/wave preparation-run identity drift.",
    )

    require(
        case_run_id.startswith("trm_fem_")
        and len(case_run_id) == 20,
        f"{case_id}: malformed governed case-run identity.",
    )

    require(
        trial_run_id
        == f"{case_run_id}_cal_01",
        f"{case_id}: Trial-1 identity drift.",
    )

    # --------------------------------------------------------
    # GEOMETRY / MESH
    # --------------------------------------------------------

    if case_id in fresh_ids:

        print(
            f"[{selected['wave_order']}] {case_id}"
        )
        print(
            "    Geometry : GENERATE"
        )
        print(
            "    Mesh     : GENERATE"
        )

        geometry_artifact = (
            build_fem_case_geometry(
                resolved,
                artifact_root=PREPARED_ROOT,
                validation_policy=(
                    validation_policy
                ),
            )
        )

        require(
            geometry_artifact.case_hash
            == case_hash,
            f"{case_id}: geometry case hash mismatch.",
        )

        require(
            geometry_artifact.run_id
            == case_run_id,
            f"{case_id}: geometry run ID mismatch.",
        )

        step_path = (
            geometry_artifact.step_path
        )

        require(
            step_path.is_file()
            and step_path.stat().st_size > 0,
            f"{case_id}: STEP generation failed.",
        )

        mesh_artifact = (
            generate_fem_case_grouped_mesh(
                resolved,
                geometry_artifact.geometry,
                step_path=step_path,
                artifact_root=PREPARED_ROOT,
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

        require(
            mesh_artifact.case_hash
            == case_hash,
            f"{case_id}: mesh case hash mismatch.",
        )

        require(
            mesh_artifact.run_id
            == case_run_id,
            f"{case_id}: mesh run ID mismatch.",
        )

        quality = (
            validate_fem_case_grouped_mesh_quality(
                mesh_artifact,
                mesh_quality,
            )
        )

        mesh_path = (
            mesh_artifact.msh_path
        )

        geometry_mode = (
            "GENERATED_FOR_W01"
        )

        mesh_mode = (
            "GENERATED_FOR_W01"
        )

        source_case_id = None
        source_case_hash = None

    else:

        require(
            case_id in reuse_ids,
            f"{case_id}: case has no governed artifact action.",
        )

        source = REUSE_SOURCES.get(
            case_id
        )

        require(
            source is not None,
            f"{case_id}: pinned reuse source missing.",
        )

        step_path = source[
            "step_path"
        ]

        mesh_path = source[
            "mesh_path"
        ]

        require(
            sha256(step_path)
            == source[
                "step_sha256"
            ],
            f"{case_id}: reused STEP SHA drift.",
        )

        require(
            sha256(mesh_path)
            == source[
                "mesh_sha256"
            ],
            f"{case_id}: reused mesh SHA drift.",
        )

        geometry_mode = (
            "REUSED_ACCEPTED_EXACT_GEOMETRY"
        )

        mesh_mode = (
            "REUSED_ACCEPTED_EXACT_MESH"
        )

        source_case_id = source[
            "source_case_id"
        ]

        source_case_hash = source[
            "source_case_hash"
        ]

        quality = None

        print(
            f"[{selected['wave_order']}] {case_id}"
        )
        print(
            "    Geometry : REUSE <-",
            source_case_id,
        )
        print(
            "    Mesh     : REUSE <-",
            source_case_id,
        )

    step_sha = sha256(
        step_path
    )

    mesh_sha = sha256(
        mesh_path
    )

    # --------------------------------------------------------
    # GENERIC FEM BUNDLE + CAL_01
    # --------------------------------------------------------

    token = case_hash[:16]

    bundle = (
        build_generic_fem_definition_bundle(
            resolved,
            mesh_id=(
                f"mesh-{token}"
            ),
            geometry_id=(
                f"geometry-{token}"
            ),
            classification_id=(
                f"classification-{token}"
            ),
            source_mesh_name=(
                mesh_path.name
            ),
            transfer_template=(
                transfer_template
            ),
            contact_template=(
                contact_template
            ),
            boundary_template=(
                boundary_template
            ),
            material_catalog=(
                DIVERSIFIED_CANDIDATE_MATERIAL_CATALOG
            ),
        )
    )

    require(
        bundle.preparation.identity.run_id
        == case_run_id,
        f"{case_id}: FEM bundle run identity drift.",
    )

    mesh_data = (
        read_grouped_complete_joint_mesh(
            mesh_path,
            bundle.transfer,
        )
    )

    trial = (
        derive_initial_preload_calibration_trial(
            seed=bundle.calibration_seed,
            case_run_id=case_run_id,
        )
    )

    require(
        trial.trial_index == 1,
        f"{case_id}: derived trial is not Trial-1.",
    )

    require(
        trial.run_id
        == trial_run_id,
        f"{case_id}: derived CAL_01 identity drift.",
    )

    run_dir = (
        SOLVER_ROOT
        / case_run_id
        / trial_run_id
    )

    run_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Absolutely no old solver result may be mistaken
    # for this new governed Trial-1.
    prohibited = []

    for suffix in (
        ".dat",
        ".frd",
        ".sta",
        ".cvg",
        ".rout",
    ):
        candidate = (
            run_dir
            / f"{trial_run_id}{suffix}"
        )

        if candidate.exists():
            prohibited.append(
                candidate
            )

    manifest_path = (
        run_dir
        / "fem_run_manifest.json"
    )

    if manifest_path.exists():
        prohibited.append(
            manifest_path
        )

    require(
        not prohibited,
        (
            f"{case_id}: solver evidence already "
            "exists; refusing duplicate solve preparation:\n"
            + "\n".join(
                str(path)
                for path in prohibited
            )
        ),
    )

    input_path = (
        run_dir
        / f"{trial_run_id}.inp"
    )

    candidate_path = (
        run_dir
        / f"{trial_run_id}.candidate.inp"
    )

    if candidate_path.exists():
        candidate_path.unlink()

    deck = (
        write_fem_preload_calibration_trial_deck(
            mesh_data=mesh_data,
            bundle=bundle,
            trial=trial,
            reference_temperature_c=(
                reference_temperature
            ),
            input_path=candidate_path,
        )
    )

    require(
        candidate_path.is_file()
        and candidate_path.stat().st_size > 0,
        f"{case_id}: CAL_01 candidate deck missing.",
    )

    require(
        deck.trial_run_id
        == trial_run_id,
        f"{case_id}: deck/trial identity mismatch.",
    )

    require(
        math.isclose(
            deck.delta_temperature_c,
            trial.delta_temperature_c,
            rel_tol=0.0,
            abs_tol=1.0e-10,
        ),
        f"{case_id}: deck/trial delta-T mismatch.",
    )

    candidate_sha = sha256(
        candidate_path
    )

    if input_path.exists():

        existing_sha = sha256(
            input_path
        )

        require(
            existing_sha
            == candidate_sha,
            (
                f"{case_id}: immutable CAL_01 deck "
                "differs from regenerated candidate."
            ),
        )

        candidate_path.unlink()

    else:

        candidate_path.replace(
            input_path
        )

    deck_sha = sha256(
        input_path
    )

    require(
        deck_sha
        == candidate_sha,
        f"{case_id}: published deck SHA drift.",
    )

    # --------------------------------------------------------
    # IMMUTABLE PREPARATION RECORD
    # --------------------------------------------------------

    record = {
        "schema":
            "threadrom.phase3_diversified_doe_trial1_preparation.v1",

        "record_status":
            "FINAL",

        "scope":
            "phase3_diversified_doe_TRM-DDOE-001_W01_trial1",

        "campaign_id":
            "TRM-DDOE-001",

        "wave_id":
            "TRM-DDOE-001-W01",

        "wave_order":
            selected[
                "wave_order"
            ],

        "overall_disposition":
            "DIVERSIFIED_DOE_W01_TRIAL1_PREPARATION_PASS",

        "authorization": {
            "wave_plan_sha256":
                EXPECTED_WAVE_SHA,

            "trial1_owner_authorization_sha256":
                EXPECTED_TRIAL_AUTH_SHA,

            "artifact_preparation_authorization_sha256":
                EXPECTED_ARTIFACT_AUTH_SHA,
        },

        "case": {
            "case_id":
                case_id,

            "case_hash":
                case_hash,

            "case_run_id":
                case_run_id,

            "thread_designation":
                proposal_row[
                    "thread_designation"
                ],

            "member_material_id":
                proposal_row[
                    "member_material_id"
                ],

            "normalized_coordinates":
                proposal_row[
                    "normalized_coordinates"
                ],
        },

        "geometry": {
            "mode":
                geometry_mode,

            "relative_path":
                str(
                    step_path
                    .resolve()
                    .relative_to(ROOT)
                ).replace(
                    "\\",
                    "/",
                ),

            "sha256":
                step_sha,

            "source_case_id":
                source_case_id,

            "source_case_hash":
                source_case_hash,
        },

        "mesh": {
            "mode":
                mesh_mode,

            "relative_path":
                str(
                    mesh_path
                    .resolve()
                    .relative_to(ROOT)
                ).replace(
                    "\\",
                    "/",
                ),

            "sha256":
                mesh_sha,

            "source_case_id":
                source_case_id,

            "source_case_hash":
                source_case_hash,

            "quality_gate":
                "PASS",

            "quality_result":
                (
                    None
                    if quality is None
                    else jsonable(
                        quality
                    )
                ),
        },

        "trial_1":
            jsonable(
                trial
            ),

        "deck": {
            "relative_path":
                str(
                    input_path
                    .resolve()
                    .relative_to(ROOT)
                ).replace(
                    "\\",
                    "/",
                ),

            "sha256":
                deck_sha,

            "size_bytes":
                input_path.stat().st_size,
        },

        "fem_preflight": {
            "status":
                "PASS",

            "case_resolution":
                "PASS",

            "case_hash_binding":
                "PASS",

            "geometry":
                "PASS",

            "grouped_mesh":
                "PASS",

            "mesh_read":
                "PASS",

            "generic_fem_bundle":
                "PASS",

            "trial_identity":
                "PASS",

            "deck_generation":
                "PASS",
        },

        "solve_authorization": {
            "calculix_invoked":
                False,

            "solver_authorized_by_this_script":
                False,

            "trial1_execution_authority_exists":
                True,

            "adaptive_continuation_authorized":
                False,

            "additional_trials_authorized":
                False,

            "dataset_admission_authorized":
                False,

            "full_physics_certification_authorized":
                False,

            "artifact_retirement_authorized":
                False,

            "holdout_accessed":
                False,
        },
    }

    record_path = (
        run_dir
        / "diversified_doe_trial1_preparation_record.json"
    )

    record_sha = (
        write_immutable_json(
            record_path,
            record,
        )
    )

    prepared.append(
        {
            "wave_order":
                selected[
                    "wave_order"
                ],

            "case_id":
                case_id,

            "case_hash":
                case_hash,

            "case_run_id":
                case_run_id,

            "trial_run_id":
                trial_run_id,

            "geometry_mode":
                geometry_mode,

            "mesh_mode":
                mesh_mode,

            "mesh_sha256":
                mesh_sha,

            "deck_sha256":
                deck_sha,

            "preparation_record":
                str(
                    record_path
                    .resolve()
                    .relative_to(ROOT)
                ).replace(
                    "\\",
                    "/",
                ),

            "preparation_record_sha256":
                record_sha,
        }
    )

    print(
        "    CAL_01   :",
        trial_run_id,
    )
    print(
        "    Delta T  :",
        f"{trial.delta_temperature_c:.12f} C",
    )
    print(
        "    Mesh SHA :",
        mesh_sha,
    )
    print(
        "    Deck SHA :",
        deck_sha,
    )
    print(
        "    Prep SHA :",
        record_sha,
    )
    print()


# ============================================================
# WAVE PREPARATION INDEX
# ============================================================

require(
    len(prepared) == 4,
    "Expected exactly four W01 prepared trials.",
)

wave_preparation = {
    "schema":
        "threadrom.phase3_diversified_doe_wave_preparation.v1",

    "record_status":
        "FINAL",

    "campaign_id":
        "TRM-DDOE-001",

    "wave_id":
        "TRM-DDOE-001-W01",

    "wave_plan_sha256":
        EXPECTED_WAVE_SHA,

    "trial1_owner_authorization_sha256":
        EXPECTED_TRIAL_AUTH_SHA,

    "artifact_preparation_authorization_sha256":
        EXPECTED_ARTIFACT_AUTH_SHA,

    "prepared_trial_count":
        4,

    "fresh_geometry_mesh_count":
        2,

    "reused_geometry_mesh_count":
        2,

    "prepared_trials":
        prepared,

    "factory_ready":
        True,

    "solver_launched":
        False,

    "adaptive_continuation_authorized":
        False,

    "holdouts_accessed":
        False,

    "overall_disposition":
        "W01_ALL_FOUR_TRIAL1_PREPARED_FOR_FACTORY",
}

wave_record_path = (
    CAMPAIGN_ROOT
    / "w01_trial1_preparation.json"
)

wave_record_sha = (
    write_immutable_json(
        wave_record_path,
        wave_preparation,
    )
)


print(
    "=" * 110
)
print(
    "TRM-DDOE-001-W01 — PREPARATION COMPLETE"
)
print(
    "=" * 110
)

print(
    "Prepared Trial-1 jobs :",
    len(prepared),
)

print(
    "Fresh CAD/mesh        : 2"
)

print(
    "Certified mesh reuse  : 2"
)

print(
    "W01 preparation SHA   :",
    wave_record_sha,
)

print()

for row in prepared:
    print(
        f"[{row['wave_order']}] "
        f"{row['trial_run_id']}"
    )
    print(
        "    Deck SHA:",
        row["deck_sha256"],
    )

print()
print(
    "FACTORY READY          : YES"
)
print(
    "CalculiX invoked       : NO"
)
print(
    "Adaptive CAL_02+       : NOT AUTHORIZED"
)
print(
    "Dataset admission      : NO"
)
print(
    "Holdouts accessed      : NO"
)
print()
print(
    "PASS: all four W01 CAL_01 jobs are prepared "
    "and ready for governed factory execution."
)
