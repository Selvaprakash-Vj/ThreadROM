from __future__ import annotations

import hashlib
from pathlib import Path


ROOT = Path(r"D:\ThreadROM")

V1 = (
    ROOT
    / "scripts"
    / "prepare_phase3_da08_fine_reference_decks_v1.py"
)

V2 = (
    ROOT
    / "scripts"
    / "prepare_phase3_da08_fine_reference_decks_v2.py"
)

EXPECTED_V1_SHA256 = (
    "ccbe06ea8e27297ae21a1db7d7f1846040867a96fc75a9203db41a1bc6ac65ed"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def require_once(
    text: str,
    needle: str,
    label: str,
) -> None:

    count = text.count(needle)

    if count != 1:
        raise RuntimeError(
            f"{label}: expected exactly one source seam; "
            f"found {count}."
        )


if sha256(V1) != EXPECTED_V1_SHA256:
    raise RuntimeError(
        "Pinned V1 source SHA drift."
    )

if V2.exists():
    raise RuntimeError(
        "V2 already exists; refusing overwrite."
    )

text = V1.read_text(
    encoding="utf-8-sig"
)


# ======================================================================
# 1. IMPORT GOVERNED REPLAY + GUIDANCE SEAMS
# ======================================================================

import_anchor = (
    "import threadrom.factory.fem_production_deck "
    "as production_deck_mod\n"
)

require_once(
    text,
    import_anchor,
    "module import anchor",
)

text = text.replace(
    import_anchor,
    import_anchor
    + """
import threadrom.factory.fem_guidance as fem_guidance_mod

from threadrom.factory.fem_preload_calibration_measurement import (
    extract_clamp_force_measurement_from_dat,
)

from threadrom.factory.preload_calibration_campaign import (
    PreloadCalibrationTrial,
    PreloadCalibrationTrialSource,
    evaluate_preload_calibration_trial,
)
""",
    1,
)


# ======================================================================
# 2. ADD EXACT SOURCE PINS FOR THE REPLAY SEAM
# ======================================================================

sha_anchor = "def sha256(\n"

require_once(
    text,
    sha_anchor,
    "sha helper anchor",
)

replay_pins = r'''
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


'''

text = text.replace(
    sha_anchor,
    replay_pins + sha_anchor,
    1,
)


# ======================================================================
# 3. REPLACE SCHEMA-ASSUMPTIVE ACCEPTED-STATE PARSER
#
# Instead:
#   Atlas exact evidence
#       -> exact accepted run directory
#       -> exact governed trial metadata
#       -> exact DAT + manifest hash
#
# No broad search. No W06. No holdout paths.
# ======================================================================

start = text.index(
    "def extract_accepted_source_state("
)

end = text.index(
    "\ndef reconstruct_cases(",
    start,
)

new_source_resolver = r'''
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


'''

text = (
    text[
        :start
    ]
    + new_source_resolver.strip()
    + "\n\n"
    + text[
        end + 1:
    ]
)


# ======================================================================
# 4. ADD FAIL-CLOSED GUIDANCE-GEOMETRY DISCOVERY
# ======================================================================

guidance_anchor = "def invoke_by_contract(\n"

require_once(
    text,
    guidance_anchor,
    "invoke contract anchor",
)

guidance_helpers = r'''
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


'''

text = text.replace(
    guidance_anchor,
    guidance_helpers.strip()
    + "\n\n"
    + guidance_anchor,
    1,
)


# ======================================================================
# 5. VERIFY THE NEW REPLAY SOURCE PINS AT RUNTIME
# ======================================================================

pin_print = '''    print(
        "PASS: all DA08 and software "
        "authorities verified."
    )
'''

require_once(
    text,
    pin_print,
    "authority verification print",
)

text = text.replace(
    pin_print,
    pin_print
    + '''
    verify_replay_source_pins()

    print(
        "PASS: accepted-run replay and "
        "guidance sources verified."
    )
''',
    1,
)


# ======================================================================
# 6. REPLACE RAW PROXY CALIBRATION WITH EXACT GOVERNED REPLAY
# ======================================================================

binder_start = text.index(
    "        trial_proxy = ("
)

binder_end = text.index(
    "        thermal = (",
    binder_start,
)

new_binder_block = r'''
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


'''

text = (
    text[
        :binder_start
    ]
    + new_binder_block
    + text[
        binder_end:
    ]
)


# ======================================================================
# 7. DERIVE GUIDANCE GEOMETRY FROM THE TRUE-FINE MESH
# ======================================================================

writer_anchor = (
    "        writer_available = {\n"
)

require_once(
    text,
    writer_anchor,
    "production writer available-map anchor",
)

guidance_call = r'''
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


'''

text = text.replace(
    writer_anchor,
    guidance_call
    + writer_anchor,
    1,
)


writer_mesh_anchor = '''        writer_available = {
            "mesh_data":
                mesh_data,
'''

require_once(
    text,
    writer_mesh_anchor,
    "production writer mesh-data anchor",
)

text = text.replace(
    writer_mesh_anchor,
    '''        writer_available = {
            "mesh_data":
                mesh_data,

            "guidance_geometry":
                guidance_geometry,
''',
    1,
)


# ======================================================================
# 8. RECORD THE GUIDANCE BUILDER IN EACH DECK CERTIFICATE
# ======================================================================

renderer_anchor = '''                "renderer":
                    (
                        f"{deck_writer.__module__}."
                        f"{deck_writer.__name__}"
                    ),

                "semantic_mode":
'''

require_once(
    text,
    renderer_anchor,
    "deck renderer record anchor",
)

text = text.replace(
    renderer_anchor,
    '''                "renderer":
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
''',
    1,
)


# ======================================================================
# 9. IMPROVE THE SOURCE-STATE GATE MESSAGE
# ======================================================================

old_message = (
    '        "PASS: 19/19 accepted source "\n'
    '        "preload states resolved and pinned."\n'
)

new_message = (
    '        "PASS: 19/19 exact accepted-run "\n'
    '        "trial + DAT authorities resolved and pinned."\n'
)

if old_message in text:
    text = text.replace(
        old_message,
        new_message,
        1,
    )


# ======================================================================
# 10. WRITE V2 ONLY
# ======================================================================

V2.write_text(
    text,
    encoding="utf-8",
    newline="\n",
)

print(
    "PASS: V1 source SHA pinned."
)

print(
    "PASS: V1 left untouched."
)

print(
    "PASS: exact accepted-run replay seam installed."
)

print(
    "PASS: calibration evaluation binding installed."
)

print(
    "PASS: fine-mesh guidance-geometry binding installed."
)

print(
    "V2    :",
    V2,
)

print(
    "SHA256:",
    sha256(
        V2
    ),
)
