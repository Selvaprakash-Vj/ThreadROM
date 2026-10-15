from __future__ import annotations

import dataclasses
import hashlib
import importlib.util
import inspect
import json
import math
import re
import tomllib

from pathlib import Path
from types import SimpleNamespace
from typing import Any


from threadrom.case.serialization import (
    case_sha256,
)

from threadrom.case.resolver import (
    resolve_case,
)

import threadrom.factory.fem_case_definition_bundle as bundle_mod
import threadrom.factory.fem_production_deck as production_deck_mod

import threadrom.factory.fem_guidance as fem_guidance_mod

from threadrom.factory.fem_preload_calibration_measurement import (
    extract_clamp_force_measurement_from_dat,
)

from threadrom.factory.preload_calibration_campaign import (
    PreloadCalibrationTrial,
    PreloadCalibrationTrialSource,
    evaluate_preload_calibration_trial,
)

from threadrom.factory.fem_case_definition_bundle import (
    PHASE2_CERTIFIED_FEM_PROFILE,
    build_generic_fem_definition_bundle,
)

from threadrom.factory.production_doe import (
    build_phase3_production_doe,
    load_phase3_production_doe_policy,
)

from threadrom.materials.diversified_candidate_catalog import (
    DIVERSIFIED_CANDIDATE_MATERIAL_CATALOG,
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

from threadrom.solver.complete_joint_preload import (
    load_complete_joint_preload_definition,
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


MESH_CERTIFICATE_PATH = (
    ROOT
    / "simulations"
    / "staging"
    / "phase3_da08_fine_reference"
    / "da08_fine_reference_mesh_preparation_certificate.json"
)

EXPECTED_MESH_CERTIFICATE_SHA256 = (
    "d22f971212ed8e367b6aea0c06a4c4d64df67bbdeeb9a40bb47858ab8b60f0ec"
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


ATLAS_PATH = (
    ROOT
    / "docs"
    / "phase3_fem_atlas"
    / "atlas.json"
)

EXPECTED_ATLAS_SHA256 = (
    "2f491e19c248c13986c195a0161d00ab69c787f34998cb57c2e1b2d172d19515"
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


AUTHORIZATION_PATH = (
    ARTIFACT_ROOT
    / "da08_fine_reference_deck_preparation_authorization.json"
)

AUTHORIZATION_SIDECAR = (
    ARTIFACT_ROOT
    / "da08_fine_reference_deck_preparation_authorization.sha256"
)


CERTIFICATE_PATH = (
    ARTIFACT_ROOT
    / "da08_fine_reference_deck_preparation_certificate.json"
)

CERTIFICATE_SIDECAR = (
    ARTIFACT_ROOT
    / "da08_fine_reference_deck_preparation_certificate.sha256"
)


EXPECTED_SOURCE_SHAS = {
    (
        ROOT
        / "src"
        / "threadrom"
        / "factory"
        / "fem_case_definition_bundle.py"
    ):
        "bd43b928de15f0c9e88f672c107502fdd56cb58c3d89807c58c1eb1fc35e7e0d",

    (
        ROOT
        / "src"
        / "threadrom"
        / "factory"
        / "fem_production_deck.py"
    ):
        "1f6c533577062740b90c7b99795d9789c53f64725e2e9581a169129e568f5697",

    (
        ROOT
        / "src"
        / "threadrom"
        / "solver"
        / "complete_joint_calculix_transfer.py"
    ):
        "1b6bef490d5022b009ff15098a4ec7821eab11ffdeeef53534033962179ec0d3",

    (
        ROOT
        / "src"
        / "threadrom"
        / "solver"
        / "complete_joint_preload.py"
    ):
        "8aeb467a9c6fcb94e40eeae3d2624e96a65ac1ffcad2c86ebf0427312a947fe6",

    (
        ROOT
        / "src"
        / "threadrom"
        / "factory"
        / "fem_profile.py"
    ):
        "ebd1e02f0148f5ab3079f2d1f0f4698b5d0963fa006ab148da16a90e949ccf6b",

    (
        ROOT
        / "src"
        / "threadrom"
        / "factory"
        / "production_doe.py"
    ):
        "25094c5d808d29e56d61a4936f505a1023bba2d91f514be6e1127fa88032b5bf",
}


SOLVER_OUTPUT_SUFFIXES = {
    ".dat",
    ".sta",
    ".frd",
    ".cvg",
    ".rout",
    ".12d",
    ".eig",
    ".out",
}



REPLAY_SOURCE_SHAS = {
    (
        ROOT
        / "src"
        / "threadrom"
        / "factory"
        / "fem_preload_calibration_measurement.py"
    ):
        "8fe971e17a9c10a126a0c28d5e92d0ebd8ed731bfecd0b84d5383310cce419b5",

    (
        ROOT
        / "src"
        / "threadrom"
        / "factory"
        / "preload_calibration_campaign.py"
    ):
        "ef768ce5e27d17151995f8b322cca3c0a2afc216ce3cb5eab3412c3051b03064",

    (
        ROOT
        / "src"
        / "threadrom"
        / "factory"
        / "fem_guidance.py"
    ):
        "fcc85e92ab7f0528f983688eca17476edbdef4a40ac733f810160eebf82e30a9",
}


def verify_replay_source_pins() -> None:

    for path, expected in REPLAY_SOURCE_SHAS.items():

        if not path.is_file():
            raise RuntimeError(
                "DA08 replay source missing: "
                f"{path}"
            )

        actual = hashlib.sha256(
            path.read_bytes()
        ).hexdigest()

        if actual != expected:
            raise RuntimeError(
                "DA08 replay source SHA drift: "
                f"{path}"
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


def read_json(
    path: Path,
) -> Any:

    return json.loads(
        path.read_text(
            encoding="utf-8-sig"
        )
    )


def require_close(
    name: str,
    actual: float,
    expected: float,
    *,
    abs_tol: float = 1.0e-9,
) -> None:

    if not math.isclose(
        float(actual),
        float(expected),
        rel_tol=0.0,
        abs_tol=abs_tol,
    ):

        raise RuntimeError(
            f"{name} drift: "
            f"expected={expected!r}, "
            f"actual={actual!r}"
        )


def safe_repo_path(
    raw: str,
) -> Path:

    if not isinstance(
        raw,
        str,
    ):

        raise RuntimeError(
            "Governed path must be a string."
        )


    candidate = Path(
        raw.replace(
            "\\",
            "/",
        )
    )


    if not candidate.is_absolute():

        candidate = (
            ROOT
            / candidate
        )


    candidate = candidate.resolve()


    try:

        candidate.relative_to(
            ROOT.resolve()
        )

    except ValueError as exc:

        raise RuntimeError(
            "Governed artifact escaped repository root."
        ) from exc


    normalized = str(
        candidate
    ).replace(
        "\\",
        "/",
    ).lower()


    if (
        "/w06/" in normalized
        or normalized.endswith(
            "/w06"
        )
        or "holdout" in normalized
        or "/blind/" in normalized
    ):

        raise RuntimeError(
            "DA08 deck preparation attempted "
            "forbidden W06/holdout access."
        )


    return candidate


def write_immutable_json(
    path: Path,
    payload: dict[str, Any],
) -> str:

    encoded = (
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


    digest = hashlib.sha256(
        encoded
    ).hexdigest()


    if path.exists():

        if path.read_bytes() != encoded:

            raise RuntimeError(
                "Immutable JSON drift: "
                f"{path}"
            )

        return digest


    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_bytes(
        encoded
    )

    return digest


def write_sidecar(
    path: Path,
    *,
    digest: str,
    target_name: str,
) -> None:

    text = (
        f"{digest}  "
        f"{target_name}\n"
    )


    if path.exists():

        existing = path.read_text(
            encoding="ascii"
        )

        if existing != text:

            raise RuntimeError(
                "Immutable SHA sidecar drift: "
                f"{path}"
            )

        return


    path.write_text(
        text,
        encoding="ascii",
    )


def function_source(
    function,
) -> str:

    try:

        return inspect.getsource(
            function
        )

    except (
        OSError,
        TypeError,
    ) as exc:

        raise RuntimeError(
            "Unable to inspect governed function source: "
            f"{function!r}"
        ) from exc


def discover_calibration_binder():

    required_tokens = (
        "ThermalPreloadDefinition(",
        "automatic_case_specific_fem_campaign",
        "measurement.mean_force_n",
        "trial.delta_temperature_c",
        "trial.run_id",
    )


    candidates = []


    for name, function in inspect.getmembers(
        bundle_mod,
        inspect.isfunction,
    ):

        if (
            function.__module__
            != bundle_mod.__name__
        ):
            continue


        source = function_source(
            function
        )


        if all(
            token in source
            for token in required_tokens
        ):

            candidates.append(
                (
                    name,
                    function,
                    source,
                )
            )


    if len(
        candidates
    ) != 1:

        raise RuntimeError(
            "Expected exactly one existing "
            "accepted-calibration preload binder; "
            f"found {[item[0] for item in candidates]}"
        )


    (
        name,
        function,
        source,
    ) = candidates[
        0
    ]


    trial_attributes = set(
        re.findall(
            r"\btrial\.([A-Za-z_][A-Za-z0-9_]*)",
            source,
        )
    )


    measurement_attributes = set(
        re.findall(
            r"\bmeasurement\.([A-Za-z_][A-Za-z0-9_]*)",
            source,
        )
    )


    if not trial_attributes.issubset(
        {
            "delta_temperature_c",
            "run_id",
        }
    ):

        raise RuntimeError(
            "Calibration binder consumes unhandled "
            f"trial fields: {sorted(trial_attributes)}"
        )


    if not measurement_attributes.issubset(
        {
            "mean_force_n",
        }
    ):

        raise RuntimeError(
            "Calibration binder consumes unhandled "
            "measurement fields: "
            f"{sorted(measurement_attributes)}"
        )


    return (
        name,
        function,
    )


def discover_production_deck_writer():

    required_tokens = (
        "THREADROM PHASE 3 GENERIC FEM PRODUCTION RUN",
        "calibration_measured_clamp_force_n",
        "input_path",
        "render_complete_joint_calculix_model",
    )


    candidates = []


    for name, function in inspect.getmembers(
        production_deck_mod,
        inspect.isfunction,
    ):

        if (
            function.__module__
            != production_deck_mod.__name__
        ):
            continue


        source = function_source(
            function
        )


        if all(
            token in source
            for token in required_tokens
        ):

            candidates.append(
                (
                    name,
                    function,
                    source,
                )
            )


    if len(
        candidates
    ) != 1:

        raise RuntimeError(
            "Expected exactly one generic FEM "
            "production-deck writer; "
            f"found {[item[0] for item in candidates]}"
        )


    return (
        candidates[
            0
        ][
            0
        ],
        candidates[
            0
        ][
            1
        ],
    )


def discover_guidance_builder():

    candidates = []


    for name, function in inspect.getmembers(
        fem_guidance_mod,
        inspect.isfunction,
    ):

        if (
            function.__module__
            != fem_guidance_mod.__name__
        ):

            continue


        signature = inspect.signature(
            function
        )


        annotation = (
            signature.return_annotation
        )


        annotation_text = str(
            annotation
        )


        source = function_source(
            function
        )


        score = 0


        if (
            "FemGuidanceGeometry"
            in annotation_text
        ):

            score += 4


        if (
            "FemGuidanceGeometry("
            in source
        ):

            score += 3


        if (
            "guidance"
            in name.lower()
            and "geometry"
            in name.lower()
        ):

            score += 1


        if score > 0:

            candidates.append(
                (
                    score,
                    name,
                    function,
                )
            )


    if not candidates:

        raise RuntimeError(
            "No governed FemGuidanceGeometry "
            "builder was found."
        )


    best_score = max(
        item[
            0
        ]
        for item in candidates
    )


    best = [
        item
        for item in candidates
        if item[
            0
        ]
        == best_score
    ]


    if len(
        best
    ) != 1:

        raise RuntimeError(
            "Governed guidance-geometry builder "
            "is ambiguous: "
            f"{[(item[1], item[0]) for item in best]}"
        )


    return (
        best[
            0
        ][
            1
        ],
        best[
            0
        ][
            2
        ],
    )


def resolve_guidance_geometry(
    *,
    mesh_data,
    transfer,
    resolved,
    bundle,
    backend,
):

    name, builder = (
        discover_guidance_builder()
    )


    value = invoke_by_contract(
        builder,
        {
            "mesh_data":
                mesh_data,

            "transfer":
                transfer,

            "resolved":
                resolved,

            "bundle":
                bundle,

            "backend":
                backend,
        },
        {
            "transfer_definition":
                "transfer",

            "definition":
                "transfer",

            "case":
                "resolved",
        },
    )


    if (
        value.__class__.__name__
        != "FemGuidanceGeometry"
    ):

        raise RuntimeError(
            "Governed guidance builder returned "
            "unexpected type: "
            f"{value.__class__.__name__}"
        )


    return (
        name,
        value,
    )

def invoke_by_contract(
    function,
    available: dict[str, Any],
    aliases: dict[str, str],
):

    signature = inspect.signature(
        function
    )


    args = []
    kwargs = {}


    for parameter in (
        signature.parameters.values()
    ):

        if parameter.kind in {
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        }:

            continue


        lookup = (
            parameter.name
            if parameter.name
            in available
            else aliases.get(
                parameter.name
            )
        )


        if (
            lookup is None
            or lookup not in available
        ):

            if (
                parameter.default
                is not inspect.Parameter.empty
            ):

                continue


            raise RuntimeError(
                "Unable to satisfy required parameter "
                f"{parameter.name!r} for "
                f"{function.__module__}."
                f"{function.__name__}"
                f"{signature}"
            )


        value = available[
            lookup
        ]


        if (
            parameter.kind
            is inspect.Parameter.POSITIONAL_ONLY
        ):

            args.append(
                value
            )

        else:

            kwargs[
                parameter.name
            ] = value


    return function(
        *args,
        **kwargs,
    )


def normalize_calibrated_preload(
    result,
):

    if (
        hasattr(
            result,
            "target_force_n",
        )
        and hasattr(
            result,
            "thermal",
        )
    ):

        return result


    candidate = getattr(
        result,
        "preload",
        None,
    )


    if (
        candidate is not None
        and hasattr(
            candidate,
            "target_force_n",
        )
        and hasattr(
            candidate,
            "thermal",
        )
    ):

        return candidate


    raise RuntimeError(
        "Accepted-calibration binder did not "
        "return a governed preload definition."
    )


def extract_case_identity(
    payload: dict,
) -> tuple[str | None, str | None]:

    nested = payload.get(
        "case"
    )


    if not isinstance(
        nested,
        dict,
    ):

        nested = {}


    case_id = (
        payload.get(
            "case_id"
        )
        or nested.get(
            "case_id"
        )
    )


    case_hash = (
        payload.get(
            "case_hash"
        )
        or nested.get(
            "case_hash"
        )
    )


    return (
        case_id,
        case_hash,
    )


def walk_dicts(
    value: Any,
):

    if isinstance(
        value,
        dict,
    ):

        yield value

        for child in value.values():
            yield from walk_dicts(
                child
            )

    elif isinstance(
        value,
        list,
    ):

        for child in value:
            yield from walk_dicts(
                child
            )


def normalize_trial_source(
    raw: Any,
) -> PreloadCalibrationTrialSource:

    value = str(
        raw
    ).strip()


    try:

        return PreloadCalibrationTrialSource(
            value
        )

    except ValueError:

        token = (
            value.split(
                "."
            )[-1]
            .strip()
            .upper()
        )


        try:

            return PreloadCalibrationTrialSource[
                token
            ]

        except KeyError as exc:

            raise RuntimeError(
                "Unknown governed preload-calibration "
                f"trial source: {raw!r}"
            ) from exc


def recover_exact_accepted_trial(
    *,
    run_directory: Path,
    accepted_run_id: str,
    case_id: str,
) -> tuple[
    PreloadCalibrationTrial,
    tuple[str, ...],
]:

    if (
        not run_directory.is_dir()
    ):

        raise RuntimeError(
            f"{case_id}: accepted run directory "
            "is missing."
        )


    json_paths = tuple(
        sorted(
            path
            for path
            in run_directory.glob(
                "*.json"
            )
            if path.is_file()
        )
    )


    if not json_paths:

        raise RuntimeError(
            f"{case_id}: accepted run directory "
            "contains no governed JSON provenance."
        )


    candidates: dict[
        tuple[int, str, float, str],
        list[str],
    ] = {}


    for path in json_paths:

        try:

            payload = read_json(
                path
            )

        except (
            json.JSONDecodeError,
            UnicodeDecodeError,
        ):

            continue


        for node in walk_dicts(
            payload
        ):

            if (
                node.get(
                    "run_id"
                )
                != accepted_run_id
            ):

                continue


            required = (
                "trial_index",
                "delta_temperature_c",
                "source",
            )


            if not all(
                field in node
                for field in required
            ):

                continue


            try:

                trial_index = int(
                    node[
                        "trial_index"
                    ]
                )

                delta_temperature_c = float(
                    node[
                        "delta_temperature_c"
                    ]
                )

                source = (
                    normalize_trial_source(
                        node[
                            "source"
                        ]
                    )
                )

            except (
                TypeError,
                ValueError,
                RuntimeError,
            ):

                continue


            if (
                trial_index < 1
                or not math.isfinite(
                    delta_temperature_c
                )
                or delta_temperature_c == 0.0
            ):

                continue


            key = (
                trial_index,
                accepted_run_id,
                delta_temperature_c,
                source.value,
            )


            candidates.setdefault(
                key,
                [],
            ).append(
                relative(
                    path
                )
            )


    if len(
        candidates
    ) != 1:

        raise RuntimeError(
            f"{case_id}: exact accepted trial "
            "did not resolve uniquely from its "
            "accepted run directory. "
            f"Candidates={list(candidates)}"
        )


    (
        trial_index,
        run_id,
        delta_temperature_c,
        source_value,
    ) = next(
        iter(
            candidates
        )
    )


    trial = PreloadCalibrationTrial(
        trial_index=trial_index,
        run_id=run_id,
        delta_temperature_c=(
            delta_temperature_c
        ),
        source=(
            PreloadCalibrationTrialSource(
                source_value
            )
        ),
    )


    provenance_paths = tuple(
        sorted(
            set(
                next(
                    iter(
                        candidates.values()
                    )
                )
            )
        )
    )


    return (
        trial,
        provenance_paths,
    )


def verify_exact_accepted_dat(
    *,
    run_directory: Path,
    accepted_run_id: str,
    case_id: str,
    case_hash: str,
) -> dict[str, Any]:

    dat_path = (
        run_directory
        / f"{accepted_run_id}.dat"
    )


    if (
        not dat_path.is_file()
        or dat_path.stat().st_size <= 0
    ):

        raise RuntimeError(
            f"{case_id}: accepted DAT missing: "
            f"{dat_path}"
        )


    manifest_path = (
        run_directory
        / "fem_run_manifest.json"
    )


    if (
        not manifest_path.is_file()
    ):

        raise RuntimeError(
            f"{case_id}: accepted FEM run "
            "manifest missing."
        )


    manifest = read_json(
        manifest_path
    )


    if (
        manifest.get(
            "run_id"
        )
        != accepted_run_id
        or manifest.get(
            "case_hash"
        )
        != case_hash
    ):

        raise RuntimeError(
            f"{case_id}: accepted run manifest "
            "identity drift."
        )


    disposition = str(
        manifest.get(
            "disposition",
            "",
        )
    ).lower()


    if disposition != "succeeded":

        raise RuntimeError(
            f"{case_id}: accepted run manifest "
            f"is not succeeded: {disposition!r}"
        )


    if (
        manifest.get(
            "return_code"
        )
        not in {
            None,
            0,
        }
    ):

        raise RuntimeError(
            f"{case_id}: accepted solver run "
            "has non-zero return code."
        )


    if (
        manifest.get(
            "job_finished"
        )
        not in {
            None,
            True,
        }
    ):

        raise RuntimeError(
            f"{case_id}: accepted solver run "
            "is not marked finished."
        )


    dat_artifacts = []


    for artifact in manifest.get(
        "artifacts",
        [],
    ):

        if not isinstance(
            artifact,
            dict,
        ):

            continue


        raw_path = artifact.get(
            "relative_path"
        )


        role = str(
            artifact.get(
                "role",
                "",
            )
        ).lower()


        if (
            role == "dat"
            or (
                isinstance(
                    raw_path,
                    str,
                )
                and Path(
                    raw_path.replace(
                        "\\",
                        "/",
                    )
                ).name
                == dat_path.name
            )
        ):

            dat_artifacts.append(
                artifact
            )


    if len(
        dat_artifacts
    ) != 1:

        raise RuntimeError(
            f"{case_id}: DAT artifact did not "
            "resolve uniquely in accepted manifest."
        )


    expected_dat_sha = (
        dat_artifacts[
            0
        ].get(
            "sha256"
        )
    )


    if (
        not isinstance(
            expected_dat_sha,
            str,
        )
        or sha256(
            dat_path
        )
        != expected_dat_sha
    ):

        raise RuntimeError(
            f"{case_id}: accepted DAT SHA drift."
        )


    return {
        "accepted_dat_path":
            dat_path,

        "accepted_dat_sha256":
            expected_dat_sha,

        "accepted_manifest_path":
            manifest_path,

        "accepted_manifest_sha256":
            sha256(
                manifest_path
            ),
    }


def extract_accepted_source_state(
    payload: dict,
    *,
    evidence_row: dict,
    case_id: str,
    case_hash: str,
) -> dict[str, Any]:

    payload_case_id, payload_case_hash = (
        extract_case_identity(
            payload
        )
    )


    if (
        payload_case_id is not None
        and payload_case_id
        != case_id
    ):

        raise RuntimeError(
            f"{case_id}: accepted evidence "
            "case-ID drift."
        )


    if (
        payload_case_hash is not None
        and payload_case_hash
        != case_hash
    ):

        raise RuntimeError(
            f"{case_id}: accepted evidence "
            "case-hash drift."
        )


    if (
        payload.get(
            "record_status"
        )
        not in {
            None,
            "FINAL",
        }
    ):

        raise RuntimeError(
            f"{case_id}: accepted evidence "
            "is not FINAL."
        )


    accepted_run_id = (
        evidence_row.get(
            "accepted_run_id"
        )
    )


    if (
        not isinstance(
            accepted_run_id,
            str,
        )
        or not accepted_run_id.strip()
    ):

        raise RuntimeError(
            f"{case_id}: FEM Atlas accepted "
            "run ID missing."
        )


    raw_run_directory = (
        evidence_row.get(
            "run_directory"
        )
    )


    if not isinstance(
        raw_run_directory,
        str,
    ):

        raise RuntimeError(
            f"{case_id}: FEM Atlas accepted "
            "run-directory locator missing."
        )


    run_directory = safe_repo_path(
        raw_run_directory
    )


    direct_dat = (
        run_directory
        / f"{accepted_run_id}.dat"
    )


    nested_run_directory = (
        run_directory
        / accepted_run_id
    )


    if (
        not direct_dat.is_file()
        and (
            nested_run_directory
            / f"{accepted_run_id}.dat"
        ).is_file()
    ):

        run_directory = (
            nested_run_directory
        )


    trial, trial_provenance = (
        recover_exact_accepted_trial(
            run_directory=(
                run_directory
            ),
            accepted_run_id=(
                accepted_run_id
            ),
            case_id=case_id,
        )
    )


    dat_state = (
        verify_exact_accepted_dat(
            run_directory=(
                run_directory
            ),
            accepted_run_id=(
                accepted_run_id
            ),
            case_id=case_id,
            case_hash=case_hash,
        )
    )


    if (
        trial.run_id
        != accepted_run_id
    ):

        raise RuntimeError(
            f"{case_id}: recovered trial/run "
            "identity drift."
        )


    return {
        "accepted_run_id":
            accepted_run_id,

        "accepted_trial_index":
            trial.trial_index,

        "accepted_delta_temperature_c":
            trial.delta_temperature_c,

        "accepted_trial_source":
            trial.source.value,

        "trial":
            trial,

        "trial_provenance_paths":
            trial_provenance,

        "accepted_run_directory":
            run_directory,

        "source_schema":
            payload.get(
                "schema"
            ),

        **dat_state,
    }

def reconstruct_cases(
    recovery_rows: list[dict],
) -> dict[str, dict[str, Any]]:

    proposal = read_json(
        PROPOSAL_PATH
    )


    proposal_index = {
        row[
            "proposal_id"
        ]: row
        for row in proposal[
            "cases"
        ]
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
            "threadrom_da08_deck_identity_authority",
            NEXT_WAVE_BUILDER_PATH,
        )
    )


    if (
        spec is None
        or spec.loader is None
    ):

        raise RuntimeError(
            "Unable to load diversified "
            "case authority."
        )


    next_wave = (
        importlib.util.module_from_spec(
            spec
        )
    )

    spec.loader.exec_module(
        next_wave
    )


    identity_function = getattr(
        next_wave,
        "governed_case_identity",
    )


    authority_globals = (
        identity_function
        .__globals__
    )


    diversified_builder = (
        authority_globals[
            "_build_case"
        ]
    )


    diversified_resolver = (
        authority_globals[
            "resolve_case"
        ]
    )


    diversified_catalog = (
        authority_globals[
            "DIVERSIFIED_CANDIDATE_MATERIAL_CATALOG"
        ]
    )


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


    production_index = {
        item.case_id: item
        for item
        in production_campaign.design_cases
    }


    result = {}


    for row in recovery_rows:

        case_id = row[
            "case_id"
        ]

        case_hash = row[
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
                    f"{case_id}: diversified "
                    "proposal row missing."
                )


            size_matches = [
                item
                for item
                in diversified_policy[
                    "size_candidates"
                ]
                if item[
                    "designation"
                ]
                == proposal_row[
                    "thread_designation"
                ]
            ]


            if len(
                size_matches
            ) != 1:

                raise RuntimeError(
                    f"{case_id}: diversified "
                    "size resolution drift."
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


            resolved = (
                diversified_resolver(
                    case,
                    material_catalog=(
                        diversified_catalog
                    ),
                )
            )


            material_catalog = (
                diversified_catalog
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
                != case_hash
            ):

                raise RuntimeError(
                    f"{case_id}: Production-DOE "
                    "identity drift."
                )


            case = production_case.case

            resolved = resolve_case(
                case
            )

            material_catalog = None


        else:

            raise RuntimeError(
                f"{case_id}: unsupported "
                f"recovery authority {authority!r}."
            )


        if (
            case_sha256(
                case
            )
            != case_hash
            or resolved.case_hash
            != case_hash
        ):

            raise RuntimeError(
                f"{case_id}: exact case "
                "identity reconstruction drift."
            )


        expected_run_id = (
            row[
                "case_run_id"
            ]
        )


        actual_run_id = (
            "trm_fem_"
            + resolved
            .resolution_hash[
                :12
            ]
        )


        if actual_run_id != expected_run_id:

            raise RuntimeError(
                f"{case_id}: case-run "
                "identity drift."
            )


        result[
            case_id
        ] = {
            "recovery":
                row,

            "case":
                case,

            "resolved":
                resolved,

            "material_catalog":
                material_catalog,
        }


    if len(
        result
    ) != 19:

        raise RuntimeError(
            "Expected 19 reconstructed cases."
        )


    return result


def main() -> int:

    print(
        "=" * 120
    )

    print(
        "THREADROM - DA08"
    )

    print(
        "19-CASE FINE-REFERENCE "
        "PRODUCTION-DECK PREPARATION"
    )

    print(
        "NO CALCULIX - NO W06 - "
        "NO HOLDOUT ACCESS"
    )

    print(
        "=" * 120
    )


    # =============================================================================================
    # 1. AUTHORITY / SOURCE PINS
    # =============================================================================================

    pins = {
        RECOVERY_PATH:
            EXPECTED_RECOVERY_SHA256,

        MESH_CERTIFICATE_PATH:
            EXPECTED_MESH_CERTIFICATE_SHA256,

        CAMPAIGN_PATH:
            EXPECTED_CAMPAIGN_SHA256,

        ATLAS_PATH:
            EXPECTED_ATLAS_SHA256,
    }


    pins.update(
        EXPECTED_SOURCE_SHAS
    )


    for path, expected in pins.items():

        if (
            not path.is_file()
            or sha256(
                path
            )
            != expected
        ):

            raise RuntimeError(
                "Pinned authority/source drift: "
                f"{path}"
            )


    print(
        "PASS: all DA08 and software "
        "authorities verified."
    )

    verify_replay_source_pins()

    print(
        "PASS: accepted-run replay and "
        "guidance sources verified."
    )


    # =============================================================================================
    # 2. DISCOVER EXISTING GOVERNED SEMANTIC SEAMS
    # =============================================================================================

    (
        binder_name,
        calibration_binder,
    ) = discover_calibration_binder()


    (
        writer_name,
        deck_writer,
    ) = discover_production_deck_writer()


    print(
        "PASS: accepted-calibration binder:",
        binder_name,
        inspect.signature(
            calibration_binder
        ),
    )


    print(
        "PASS: production-deck writer      :",
        writer_name,
        inspect.signature(
            deck_writer
        ),
    )


    # =============================================================================================
    # 3. LOAD CLOSED AUTHORITIES
    # =============================================================================================

    recovery = read_json(
        RECOVERY_PATH
    )

    mesh_certificate = read_json(
        MESH_CERTIFICATE_PATH
    )

    campaign = read_json(
        CAMPAIGN_PATH
    )

    atlas = read_json(
        ATLAS_PATH
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
            "Exact case-recovery closure is invalid."
        )


    if (
        mesh_certificate.get(
            "record_status"
        )
        != "FINAL_PRE_SOLVE"
        or mesh_certificate.get(
            "disposition"
        )
        != "DA08_TRUE_GLOBAL_FINE_MESH_PREPARATION_COMPLETE"
        or mesh_certificate.get(
            "global_fine_mesh_count"
        )
        != 19
        or mesh_certificate.get(
            "mesh_quality_pass_count"
        )
        != 19
    ):

        raise RuntimeError(
            "Fine-mesh certificate is not "
            "19/19 FINAL_PRE_SOLVE."
        )


    recovery_rows = (
        recovery[
            "cases"
        ]
    )


    mesh_rows = (
        mesh_certificate[
            "cases"
        ]
    )


    if (
        len(
            recovery_rows
        )
        != 19
        or len(
            mesh_rows
        )
        != 19
    ):

        raise RuntimeError(
            "DA08 19-case inventory drift."
        )


    # =============================================================================================
    # 4. DECK-PREPARATION-ONLY AUTHORIZATION
    # =============================================================================================

    authorization = {
        "schema":
            "threadrom.da08_fine_reference_deck_preparation_authorization.v1",

        "record_status":
            "FINAL",

        "authorization_basis":
            (
                "Explicit operator execution after successful "
                "19/19 true-global-fine mesh gate."
            ),

        "authorities": {
            "fine_reference_campaign_sha256":
                sha256(
                    CAMPAIGN_PATH
                ),

            "exact_case_recovery_sha256":
                sha256(
                    RECOVERY_PATH
                ),

            "fine_mesh_certificate_sha256":
                sha256(
                    MESH_CERTIFICATE_PATH
                ),

            "fem_atlas_sha256":
                sha256(
                    ATLAS_PATH
                ),
        },

        "scope": {
            "case_count":
                19,

            "solver_deck_preparation":
                True,

            "calculix_launch":
                False,

            "fem_execution":
                False,

            "w06_mutation":
                False,

            "holdout_access":
                False,

            "dataset_mutation":
                False,

            "rom_training":
                False,
        },

        "disposition":
            "DA08_FINE_REFERENCE_DECK_PREPARATION_AUTHORIZED_ONLY",
    }


    authorization_sha = (
        write_immutable_json(
            AUTHORIZATION_PATH,
            authorization,
        )
    )


    write_sidecar(
        AUTHORIZATION_SIDECAR,
        digest=authorization_sha,
        target_name=(
            AUTHORIZATION_PATH.name
        ),
    )


    print(
        "PASS: deck-preparation-only "
        "authorization frozen."
    )


    # =============================================================================================
    # 5. CASE RECONSTRUCTION
    # =============================================================================================

    cases = reconstruct_cases(
        recovery_rows
    )


    print(
        "PASS: 19/19 exact cases reconstructed."
    )


    # =============================================================================================
    # 6. MESH PREPARATION INDEX
    # =============================================================================================

    mesh_index = {
        row[
            "case_id"
        ]: row
        for row in mesh_rows
    }


    if len(
        mesh_index
    ) != 19:

        raise RuntimeError(
            "Duplicate fine-mesh case IDs."
        )


    # =============================================================================================
    # 7. FEM ATLAS INDEX + SOURCE ACCEPTED STATE
    # =============================================================================================

    atlas_cases = atlas.get(
        "cases"
    )


    if not isinstance(
        atlas_cases,
        list,
    ):

        raise RuntimeError(
            "Malformed FEM Atlas."
        )


    atlas_index = {
        (
            row[
                "case_id"
            ],
            row[
                "case_hash"
            ],
        ): row
        for row in atlas_cases
    }


    accepted_states = {}


    for case_id, context in cases.items():

        case_hash = (
            context[
                "recovery"
            ][
                "case_hash"
            ]
        )


        atlas_row = (
            atlas_index.get(
                (
                    case_id,
                    case_hash,
                )
            )
        )


        if atlas_row is None:

            raise RuntimeError(
                f"{case_id}: exact FEM-Atlas "
                "identity missing."
            )


        primary_path_raw = (
            atlas_row.get(
                "primary_evidence_path"
            )
        )


        if not isinstance(
            primary_path_raw,
            str,
        ):

            raise RuntimeError(
                f"{case_id}: FEM Atlas primary "
                "evidence path missing."
            )


        evidence_rows = (
            atlas_row.get(
                "evidence"
            )
        )


        if not isinstance(
            evidence_rows,
            list,
        ):

            raise RuntimeError(
                f"{case_id}: FEM Atlas evidence "
                "inventory missing."
            )


        matching_evidence = [
            row
            for row in evidence_rows
            if (
                isinstance(
                    row,
                    dict,
                )
                and row.get(
                    "path"
                )
                == primary_path_raw
            )
        ]


        if len(
            matching_evidence
        ) != 1:

            raise RuntimeError(
                f"{case_id}: primary evidence "
                "does not resolve uniquely."
            )


        evidence_row = (
            matching_evidence[
                0
            ]
        )


        evidence_path = (
            safe_repo_path(
                primary_path_raw
            )
        )


        if (
            not evidence_path.is_file()
            or evidence_path
            .stat()
            .st_size
            <= 0
        ):

            raise RuntimeError(
                f"{case_id}: accepted evidence "
                "file missing."
            )


        expected_evidence_sha = (
            evidence_row.get(
                "sha256"
            )
        )


        if (
            not isinstance(
                expected_evidence_sha,
                str,
            )
            or sha256(
                evidence_path
            )
            != expected_evidence_sha
        ):

            raise RuntimeError(
                f"{case_id}: accepted evidence "
                "SHA drift."
            )


        evidence_payload = read_json(
            evidence_path
        )


        state = (
            extract_accepted_source_state(
                evidence_payload,
                evidence_row=(
                    evidence_row
                ),
                case_id=case_id,
                case_hash=case_hash,
            )
        )


        accepted_states[
            case_id
        ] = {
            **state,

            "evidence_path":
                evidence_path,

            "evidence_sha256":
                expected_evidence_sha,

            "evidence_kind":
                evidence_row.get(
                    "kind"
                ),
        }


    if len(
        accepted_states
    ) != 19:

        raise RuntimeError(
            "Accepted source-state count "
            "is not 19."
        )


    print(
        "PASS: 19/19 exact accepted-run "
        "trial + DAT authorities resolved and pinned."
    )


    # =============================================================================================
    # 8. GOVERNED FEM TEMPLATES
    # =============================================================================================

    transfer_path = (
        CONFIG
        / "complete_joint_calculix_transfer.toml"
    )

    contact_path = (
        CONFIG
        / "complete_joint_contact.toml"
    )

    preload_path = (
        CONFIG
        / "complete_joint_preload.toml"
    )

    boundary_path = (
        CONFIG
        / "complete_joint_boundary_regions.toml"
    )


    transfer_template = (
        load_complete_joint_calculix_transfer_definition(
            transfer_path
        )
    )

    contact_template = (
        load_complete_joint_contact_definition(
            contact_path
        )
    )

    preload_template = (
        load_complete_joint_preload_definition(
            preload_path
        )
    )

    boundary_template = (
        load_complete_joint_boundary_region_definition(
            boundary_path
        )
    )


    base_backend = (
        PHASE2_CERTIFIED_FEM_PROFILE
        .backend
    )


    if not dataclasses.is_dataclass(
        base_backend
    ):

        raise RuntimeError(
            "Certified backend is not a dataclass."
        )


    fine_backend = (
        dataclasses.replace(
            base_backend,
            mesh_level="fine",
        )
    )


    if fine_backend.mesh_level != "fine":

        raise RuntimeError(
            "Fine backend derivation failed."
        )


    print(
        "PASS: certified backend methodology "
        "derived with mesh_level=fine only."
    )


    # =============================================================================================
    # 9. PREPARE 19 PRODUCTION/REFERENCE DECKS
    # =============================================================================================

    deck_records = []


    for ordinal, recovery_row in enumerate(
        sorted(
            recovery_rows,
            key=lambda row: row[
                "ordinal"
            ],
        ),
        start=1,
    ):

        case_id = recovery_row[
            "case_id"
        ]

        case_hash = recovery_row[
            "case_hash"
        ]

        case_run_id = recovery_row[
            "case_run_id"
        ]


        context = cases[
            case_id
        ]

        resolved = context[
            "resolved"
        ]


        mesh_row = (
            mesh_index.get(
                case_id
            )
        )


        if (
            mesh_row is None
            or mesh_row[
                "case_hash"
            ]
            != case_hash
            or mesh_row[
                "run_id"
            ]
            != case_run_id
        ):

            raise RuntimeError(
                f"{case_id}: fine-mesh "
                "certificate identity drift."
            )


        mesh_record_path = (
            safe_repo_path(
                mesh_row[
                    "record_relative_path"
                ]
            )
        )


        if (
            sha256(
                mesh_record_path
            )
            != mesh_row[
                "record_sha256"
            ]
        ):

            raise RuntimeError(
                f"{case_id}: fine-mesh "
                "preparation record SHA drift."
            )


        mesh_record = read_json(
            mesh_record_path
        )


        mesh_info = (
            mesh_record[
                "mesh"
            ]
        )


        if (
            mesh_info[
                "mesh_level"
            ]
            != "fine"
            or mesh_info[
                "mesh_kind"
            ]
            != "TRUE_GLOBAL_FINE"
            or mesh_info[
                "local_refinement"
            ]
            is not None
        ):

            raise RuntimeError(
                f"{case_id}: mesh is not "
                "certified true-global-fine."
            )


        mesh_path = (
            safe_repo_path(
                mesh_info[
                    "msh_relative_path"
                ]
            )
        )


        if (
            sha256(
                mesh_path
            )
            != mesh_info[
                "msh_sha256"
            ]
            or sha256(
                mesh_path
            )
            != mesh_row[
                "mesh_sha256"
            ]
        ):

            raise RuntimeError(
                f"{case_id}: fine mesh SHA drift."
            )


        # -----------------------------------------------------------------------------------------
        # Base generic bundle keeps all exact case-specific
        # material/contact/boundary/preparation semantics.
        # -----------------------------------------------------------------------------------------

        bundle_kwargs = {
            "resolved":
                resolved,

            "mesh_id":
                mesh_info[
                    "mesh_id"
                ],

            "geometry_id":
                mesh_info[
                    "joint_geometry_id"
                ],

            "classification_id":
                mesh_info[
                    "classification_id"
                ],

            "source_mesh_name":
                mesh_path.name,

            "transfer_template":
                transfer_template,

            "contact_template":
                contact_template,

            "boundary_template":
                boundary_template,
        }


        if (
            context[
                "material_catalog"
            ]
            is not None
        ):

            bundle_kwargs[
                "material_catalog"
            ] = context[
                "material_catalog"
            ]


        bundle = (
            build_generic_fem_definition_bundle(
                **bundle_kwargs
            )
        )


        if (
            bundle
            .preparation
            .identity
            .run_id
            != case_run_id
        ):

            raise RuntimeError(
                f"{case_id}: FEM bundle "
                "case-run identity drift."
            )


        # -----------------------------------------------------------------------------------------
        # TRUE FINE TRANSFER
        #
        # build_generic_fem_definition_bundle inherits the certified
        # backend's historical medium level. We preserve everything
        # except the truthful mesh-level selector.
        # -----------------------------------------------------------------------------------------

        if not dataclasses.is_dataclass(
            bundle.transfer
        ):

            raise RuntimeError(
                f"{case_id}: transfer definition "
                "is not a dataclass."
            )


        fine_transfer = (
            dataclasses.replace(
                bundle.transfer,
                mesh_level="fine",
            )
        )


        if (
            fine_transfer.mesh_level
            != "fine"
            or fine_backend.mesh_level
            != "fine"
        ):

            raise RuntimeError(
                f"{case_id}: fine transfer/backend "
                "binding failed."
            )


        mesh_data = (
            read_grouped_complete_joint_mesh(
                mesh_path,
                fine_transfer,
            )
        )


        # -----------------------------------------------------------------------------------------
        # Accepted source preload state
        # -----------------------------------------------------------------------------------------

        source = (
            accepted_states[
                case_id
            ]
        )



        accepted_dat_path = (
            source[
                "accepted_dat_path"
            ]
        )


        dat_sha_before = sha256(
            accepted_dat_path
        )


        extraction = (
            extract_clamp_force_measurement_from_dat(
                dat_path=(
                    accepted_dat_path
                ),
                contact_pairs=(
                    contact_template
                    .contact_pairs
                ),
            )
        )


        if (
            sha256(
                accepted_dat_path
            )
            != dat_sha_before
            or dat_sha_before
            != source[
                "accepted_dat_sha256"
            ]
        ):

            raise RuntimeError(
                f"{case_id}: accepted DAT changed "
                "during read-only replay."
            )


        measurement = (
            extraction
            .measurement
        )


        evaluation = (
            evaluate_preload_calibration_trial(
                case_run_id=(
                    case_run_id
                ),
                target_force_n=(
                    resolved
                    .source_case
                    .loading
                    .target_preload_n
                ),
                target_relative_tolerance=(
                    preload_template
                    .target_relative_tolerance
                ),
                spread_relative_tolerance=(
                    preload_template
                    .interface_spread_relative_tolerance
                ),
                current_trial=(
                    source[
                        "trial"
                    ]
                ),
                measurement=(
                    measurement
                ),
            )
        )


        disposition = getattr(
            evaluation
            .decision
            .disposition,
            "value",
            str(
                evaluation
                .decision
                .disposition
            ),
        )


        if (
            str(
                disposition
            ).lower()
            != "accept"
            or evaluation.next_trial
            is not None
        ):

            raise RuntimeError(
                f"{case_id}: accepted source run "
                "did not independently replay to "
                "governed ACCEPT."
            )


        if (
            evaluation
            .completed_trial
            .run_id
            != source[
                "accepted_run_id"
            ]
            or evaluation
            .completed_trial
            .trial_index
            != source[
                "accepted_trial_index"
            ]
        ):

            raise RuntimeError(
                f"{case_id}: replayed accepted "
                "trial identity drift."
            )


        source[
            "accepted_delta_temperature_c"
        ] = float(
            evaluation
            .completed_trial
            .delta_temperature_c
        )


        source[
            "mean_clamp_force_n"
        ] = float(
            evaluation
            .decision
            .measurement
            .mean_force_n
        )


        source[
            "target_relative_error"
        ] = float(
            evaluation
            .decision
            .target_relative_error
        )


        binder_available = {
            "bundle":
                bundle,

            "evaluation":
                evaluation,

            "preload_template":
                preload_template,
        }


        calibrated_result = (
            invoke_by_contract(
                calibration_binder,
                binder_available,
                aliases={},
            )
        )


        calibrated_preload = (
            normalize_calibrated_preload(
                calibrated_result
            )
        )


        thermal = (
            calibrated_preload
            .thermal
        )


        require_close(
            f"{case_id} target preload",
            calibrated_preload
            .target_force_n,
            resolved
            .source_case
            .loading
            .target_preload_n,
        )


        require_close(
            f"{case_id} accepted dT",
            thermal
            .equivalent_delta_temperature_c,
            source[
                "accepted_delta_temperature_c"
            ],
        )


        require_close(
            f"{case_id} calibration dT",
            thermal
            .calibration_delta_temperature_c,
            source[
                "accepted_delta_temperature_c"
            ],
        )


        require_close(
            f"{case_id} accepted clamp force",
            thermal
            .calibration_measured_clamp_force_n,
            source[
                "mean_clamp_force_n"
            ],
            abs_tol=1.0e-6,
        )


        if (
            thermal
            .calibration_run_id
            != source[
                "accepted_run_id"
            ]
        ):

            raise RuntimeError(
                f"{case_id}: calibration-run "
                "provenance drift."
            )


        if (
            thermal
            .calibration_method
            != "automatic_case_specific_fem_campaign"
        ):

            raise RuntimeError(
                f"{case_id}: unexpected "
                "calibration method."
            )


        # -----------------------------------------------------------------------------------------
        # New DA08 numerical-reference execution identity
        # -----------------------------------------------------------------------------------------

        fine_run_id = (
            f"{case_run_id}"
            "_da08_fine_ref_01"
        )


        run_directory = (
            ARTIFACT_ROOT
            / case_run_id
            / "solver"
            / fine_run_id
        )


        run_directory.mkdir(
            parents=True,
            exist_ok=True,
        )


        for existing in (
            run_directory.iterdir()
        ):

            if (
                existing.name
                == "fem_run_manifest.json"
                or existing.suffix.lower()
                in SOLVER_OUTPUT_SUFFIXES
            ):

                raise RuntimeError(
                    f"{case_id}: solver output "
                    "already exists in DA08 "
                    "fine-reference run directory: "
                    f"{existing}"
                )


        input_path = (
            run_directory
            / f"{fine_run_id}.inp"
        )


        prior_deck_sha = (
            sha256(
                input_path
            )
            if input_path.is_file()
            else None
        )


        writer_globals = (
            deck_writer
            .__globals__
        )


        resilience = (
            writer_globals.get(
                "PHASE3_CP8_EXECUTION_RESILIENCE"
            )
        )



        (
            guidance_builder_name,
            guidance_geometry,
        ) = (
            resolve_guidance_geometry(
                mesh_data=(
                    mesh_data
                ),
                transfer=(
                    fine_transfer
                ),
                resolved=(
                    resolved
                ),
                bundle=(
                    bundle
                ),
                backend=(
                    fine_backend
                ),
            )
        )


        writer_available = {
            "mesh_data":
                mesh_data,

            "guidance_geometry":
                guidance_geometry,

            "transfer":
                fine_transfer,

            "contact":
                bundle.contact,

            "preload":
                calibrated_preload,

            "boundary":
                bundle.boundary,

            "backend":
                fine_backend,

            "input_path":
                input_path,

            "resolved":
                resolved,

            "bundle":
                bundle,

            "case_run_id":
                case_run_id,

            "run_id":
                fine_run_id,

            "reference_temperature_c":
                thermal
                .reference_temperature_c,
        }


        if resilience is not None:

            writer_available[
                "resilience"
            ] = resilience


        deck_result = (
            invoke_by_contract(
                deck_writer,
                writer_available,
                aliases={
                    "transfer_definition":
                        "transfer",

                    "contact_definition":
                        "contact",

                    "preload_definition":
                        "preload",

                    "boundary_definition":
                        "boundary",

                    "backend_policy":
                        "backend",

                    "output_path":
                        "input_path",

                    "deck_path":
                        "input_path",

                    "execution_resilience":
                        "resilience",
                },
            )
        )


        if (
            not input_path.is_file()
            or input_path.stat().st_size
            <= 0
        ):

            raise RuntimeError(
                f"{case_id}: production deck "
                "was not generated."
            )


        deck_sha = sha256(
            input_path
        )


        result_sha = getattr(
            deck_result,
            "sha256",
            None,
        )


        if (
            result_sha is not None
            and result_sha
            != deck_sha
        ):

            raise RuntimeError(
                f"{case_id}: production deck "
                "metadata SHA drift."
            )


        if (
            prior_deck_sha is not None
            and prior_deck_sha
            != deck_sha
        ):

            raise RuntimeError(
                f"{case_id}: deterministic "
                "deck regeneration drift."
            )


        deck_text = (
            input_path.read_text(
                encoding="utf-8",
                errors="replace",
            )
        )


        if (
            "THREADROM PHASE 3 "
            "GENERIC FEM PRODUCTION RUN"
            not in deck_text
        ):

            raise RuntimeError(
                f"{case_id}: generated deck "
                "is not a generic production deck."
            )


        if (
            "CASE-SPECIFIC PRELOAD CALIBRATION"
            in deck_text
            or (
                "No accepted calibration evidence "
                "exists at this stage."
            )
            in deck_text
        ):

            raise RuntimeError(
                f"{case_id}: DA08 reference "
                "deck accidentally has "
                "calibration-trial semantics."
            )


        if (
            source[
                "accepted_run_id"
            ]
            not in deck_text
        ):

            raise RuntimeError(
                f"{case_id}: accepted calibration "
                "run ID absent from production deck."
            )


        per_case_record_path = (
            run_directory
            / "da08_fine_reference_deck_preparation.json"
        )


        per_case_record = {
            "schema":
                "threadrom.da08_fine_reference_deck_preparation.v1",

            "record_status":
                "FINAL_PRE_SOLVE",

            "ordinal":
                recovery_row[
                    "ordinal"
                ],

            "case": {
                "case_id":
                    case_id,

                "case_hash":
                    case_hash,

                "case_run_id":
                    case_run_id,

                "fine_reference_run_id":
                    fine_run_id,

                "recovery_authority":
                    recovery_row[
                        "authority"
                    ],
            },

            "fine_mesh": {
                "preparation_record":
                    relative(
                        mesh_record_path
                    ),

                "preparation_record_sha256":
                    sha256(
                        mesh_record_path
                    ),

                "mesh_relative_path":
                    relative(
                        mesh_path
                    ),

                "mesh_sha256":
                    sha256(
                        mesh_path
                    ),

                "mesh_level":
                    "fine",

                "mesh_kind":
                    "TRUE_GLOBAL_FINE",

                "local_refinement":
                    None,
            },

            "accepted_source_calibration": {
                "evidence_kind":
                    source[
                        "evidence_kind"
                    ],

                "evidence_relative_path":
                    relative(
                        source[
                            "evidence_path"
                        ]
                    ),

                "evidence_sha256":
                    source[
                        "evidence_sha256"
                    ],

                "evidence_schema":
                    source[
                        "source_schema"
                    ],

                "accepted_trial_index":
                    source[
                        "accepted_trial_index"
                    ],

                "accepted_run_id":
                    source[
                        "accepted_run_id"
                    ],

                "accepted_delta_temperature_c":
                    source[
                        "accepted_delta_temperature_c"
                    ],

                "mean_clamp_force_n":
                    source[
                        "mean_clamp_force_n"
                    ],
            },

            "derived_reference_backend": {
                "base_policy_id":
                    base_backend
                    .policy_id,

                "base_mesh_level":
                    base_backend
                    .mesh_level,

                "derived_mesh_level":
                    fine_backend
                    .mesh_level,

                "semantic_change":
                    (
                        "mesh_level only; all other "
                        "certified backend methodology "
                        "preserved"
                    ),
            },

            "transfer": {
                "mesh_level":
                    fine_transfer
                    .mesh_level,
            },

            "deck": {
                "relative_path":
                    relative(
                        input_path
                    ),

                "sha256":
                    deck_sha,

                "size_bytes":
                    input_path
                    .stat()
                    .st_size,

                "renderer":
                    (
                        f"{deck_writer.__module__}."
                        f"{deck_writer.__name__}"
                    ),

                "guidance_builder":
                    (
                        f"{fem_guidance_mod.__name__}."
                        f"{guidance_builder_name}"
                    ),

                "semantic_mode":
                    "GENERIC_FEM_PRODUCTION_REFERENCE",
            },

            "gates": {
                "exact_case_identity":
                    "PASS",

                "true_global_fine_mesh":
                    "PASS",

                "accepted_calibration_evidence":
                    "PASS",

                "accepted_delta_temperature_reused":
                    "PASS",

                "accepted_mean_clamp_force_reused":
                    "PASS",

                "fine_transfer":
                    "PASS",

                "fine_backend":
                    "PASS",

                "production_deck":
                    "PASS",

                "deterministic_deck":
                    "PASS",
            },

            "authorization": {
                "deck_preparation":
                    True,

                "calculix_launch":
                    False,

                "fem_execution":
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
                "DA08_FINE_REFERENCE_PRODUCTION_DECK_PREPARED",
        }


        record_sha = (
            write_immutable_json(
                per_case_record_path,
                per_case_record,
            )
        )


        deck_records.append(
            {
                "ordinal":
                    recovery_row[
                        "ordinal"
                    ],

                "case_id":
                    case_id,

                "case_hash":
                    case_hash,

                "case_run_id":
                    case_run_id,

                "fine_reference_run_id":
                    fine_run_id,

                "accepted_source_run_id":
                    source[
                        "accepted_run_id"
                    ],

                "accepted_delta_temperature_c":
                    source[
                        "accepted_delta_temperature_c"
                    ],

                "accepted_mean_clamp_force_n":
                    source[
                        "mean_clamp_force_n"
                    ],

                "mesh_relative_path":
                    relative(
                        mesh_path
                    ),

                "mesh_sha256":
                    sha256(
                        mesh_path
                    ),

                "deck_relative_path":
                    relative(
                        input_path
                    ),

                "deck_sha256":
                    deck_sha,

                "deck_size_bytes":
                    input_path
                    .stat()
                    .st_size,

                "record_relative_path":
                    relative(
                        per_case_record_path
                    ),

                "record_sha256":
                    record_sha,
            }
        )


        print()
        print(
            f"{ordinal:02d}/19 PASS | "
            f"{case_id}"
        )

        print(
            "  fine mesh       : PASS"
        )

        print(
            "  source accepted :",
            source[
                "accepted_run_id"
            ],
        )

        print(
            "  accepted dT C   :",
            source[
                "accepted_delta_temperature_c"
            ],
        )

        print(
            "  accepted clamp N:",
            source[
                "mean_clamp_force_n"
            ],
        )

        print(
            "  fine run ID     :",
            fine_run_id,
        )

        print(
            "  deck SHA        :",
            deck_sha,
        )

        print(
            "  CalculiX        : NO"
        )


    # =============================================================================================
    # 10. CAMPAIGN CERTIFICATE
    # =============================================================================================

    if len(
        deck_records
    ) != 19:

        raise RuntimeError(
            "Fine-reference deck count "
            "is not 19."
        )


    if len({
        row[
            "deck_sha256"
        ]
        for row in deck_records
    }) != 19:

        raise RuntimeError(
            "Fine-reference deck SHA "
            "inventory is not unique."
        )


    certificate = {
        "schema":
            "threadrom.da08_fine_reference_deck_campaign.v1",

        "record_status":
            "FINAL_PRE_SOLVE",

        "target_id":
            "member_shortening_v1",

        "authorities": {
            "deck_preparation_authorization": {
                "relative_path":
                    relative(
                        AUTHORIZATION_PATH
                    ),

                "sha256":
                    authorization_sha,
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

            "fine_mesh_certificate": {
                "relative_path":
                    relative(
                        MESH_CERTIFICATE_PATH
                    ),

                "sha256":
                    sha256(
                        MESH_CERTIFICATE_PATH
                    ),
            },

            "fem_atlas": {
                "relative_path":
                    relative(
                        ATLAS_PATH
                    ),

                "sha256":
                    sha256(
                        ATLAS_PATH
                    ),
            },
        },

        "software": {
            "calibration_binder":
                (
                    f"{calibration_binder.__module__}."
                    f"{calibration_binder.__name__}"
                ),

            "production_deck_renderer":
                (
                    f"{deck_writer.__module__}."
                    f"{deck_writer.__name__}"
                ),

            "fem_case_definition_bundle_sha256":
                EXPECTED_SOURCE_SHAS[
                    ROOT
                    / "src"
                    / "threadrom"
                    / "factory"
                    / "fem_case_definition_bundle.py"
                ],

            "fem_production_deck_sha256":
                EXPECTED_SOURCE_SHAS[
                    ROOT
                    / "src"
                    / "threadrom"
                    / "factory"
                    / "fem_production_deck.py"
                ],

            "calculix_transfer_sha256":
                EXPECTED_SOURCE_SHAS[
                    ROOT
                    / "src"
                    / "threadrom"
                    / "solver"
                    / "complete_joint_calculix_transfer.py"
                ],
        },

        "configuration": {
            "transfer": {
                "relative_path":
                    relative(
                        transfer_path
                    ),

                "sha256":
                    sha256(
                        transfer_path
                    ),
            },

            "contact": {
                "relative_path":
                    relative(
                        contact_path
                    ),

                "sha256":
                    sha256(
                        contact_path
                    ),
            },

            "preload": {
                "relative_path":
                    relative(
                        preload_path
                    ),

                "sha256":
                    sha256(
                        preload_path
                    ),
            },

            "boundary": {
                "relative_path":
                    relative(
                        boundary_path
                    ),

                "sha256":
                    sha256(
                        boundary_path
                    ),
            },
        },

        "proof": {
            "expected_cases":
                19,

            "exact_case_count":
                19,

            "true_global_fine_mesh_count":
                19,

            "accepted_source_calibration_count":
                19,

            "fine_transfer_count":
                19,

            "fine_backend_count":
                19,

            "production_deck_count":
                19,

            "deterministic_deck_count":
                19,
        },

        "cases":
            sorted(
                deck_records,
                key=lambda row: row[
                    "ordinal"
                ],
            ),

        "authorization": {
            "fine_reference_decks_prepared":
                True,

            "calculix_launch":
                False,

            "fem_execution":
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
            "DA08_FINE_REFERENCE_DECK_PREPARATION_COMPLETE",
    }


    certificate_sha = (
        write_immutable_json(
            CERTIFICATE_PATH,
            certificate,
        )
    )


    write_sidecar(
        CERTIFICATE_SIDECAR,
        digest=certificate_sha,
        target_name=(
            CERTIFICATE_PATH.name
        ),
    )


    print()
    print(
        "=" * 120
    )

    print(
        "DA08 FINE-REFERENCE "
        "SOLVER-DECK PREPARATION COMPLETE"
    )

    print(
        "=" * 120
    )

    print(
        "Exact cases              : 19/19"
    )

    print(
        "True global-fine meshes  : 19/19"
    )

    print(
        "Accepted source states   : 19/19"
    )

    print(
        "Fine transfer/backend    : 19/19"
    )

    print(
        "Production decks         : 19/19"
    )

    print(
        "Deterministic decks      : 19/19"
    )

    print(
        "CalculiX                 : NO"
    )

    print(
        "FEM execution            : NO"
    )

    print(
        "W06                      : UNTOUCHED"
    )

    print(
        "Holdouts                 : UNTOUCHED"
    )

    print(
        "Dataset                  : UNTOUCHED"
    )

    print(
        "Certificate              :",
        relative(
            CERTIFICATE_PATH
        ),
    )

    print(
        "Certificate SHA256       :",
        certificate_sha,
    )

    print()
    print(
        "NEXT : EXPLICIT DA08 FINE-REFERENCE "
        "SOLVER-LAUNCH AUTHORIZATION"
    )

    print(
        "=" * 120
    )


    return 0


if __name__ == "__main__":

    raise SystemExit(
        main()
    )
