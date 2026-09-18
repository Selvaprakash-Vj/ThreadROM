from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import tempfile
import tomllib

from pathlib import Path

from threadrom.case.preflight import (
    PreflightSeverity,
    PreflightTarget,
)
from threadrom.case.preflight_engine import (
    preflight_case,
)
from threadrom.case.resolver import (
    resolve_case,
)
from threadrom.factory.fem_case_definition_bundle import (
    build_generic_fem_definition_bundle,
)
from threadrom.factory.fem_preload_calibration_deck import (
    write_fem_preload_calibration_trial_deck,
)
from threadrom.factory.preload_calibration_campaign import (
    PreloadCalibrationTrial,
    PreloadCalibrationTrialSource,
)
from threadrom.factory.production_doe import (
    build_phase3_production_doe,
    load_phase3_production_doe_policy,
)
from threadrom.factory.production_doe_reaction_observable_revision import (
    bridge_bundle_to_frozen_production_doe_identity,
    certify_named_reaction_observability,
    derive_reaction_observable_revision_identity,
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


ROOT = Path(r"D:\ThreadROM")

CONFIG = ROOT / "config"

CAMPAIGN_ROOT = (
    ROOT
    / "simulations"
    / "staging"
    / "phase3_cp8_production_doe"
    / "TRM-PDOE-C01"
)

SOLVER_ROOT = (
    CAMPAIGN_ROOT
    / "solver_preparation"
)

DOE_POLICY_PATH = (
    CONFIG
    / "phase3_production_doe.toml"
)

PREPARATION_CERT_PATH = (
    CAMPAIGN_ROOT
    / "production_doe_preparation_certification_record.json"
)

PENDING_CASE_IDS = (
    "D-INT-012",
    "D-INT-013",
    "D-INT-014",
    "D-INT-015",
    "D-INT-016",
)

SOURCE_PREPARATION_NAME = (
    "production_doe_v2_1_rollout_solver_preparation_record.json"
)

REVISION_PREPARATION_NAME = (
    "production_doe_reaction_observable_revision_record.json"
)

EXPECTED_SOURCE_DISPOSITION = (
    "V2_1_ROLLOUT_CASE_PREPARATION_PASS_"
    "AWAITING_BATCH_CERTIFICATION"
)

REVISION_DISPOSITION = (
    "PRODUCTION_DOE_REACTION_OBSERVABLE_"
    "REVISION_PREPARATION_PASS"
)

SOLVER_OUTPUT_SUFFIXES = frozenset(
    {
        ".12d",
        ".cvg",
        ".dat",
        ".eig",
        ".frd",
        ".msg",
        ".out",
        ".rout",
        ".sta",
    }
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare the five pending Production-DOE "
            "Trial-1 reaction-observable sibling decks. "
            "Dry-run is the default; CalculiX is never invoked."
        )
    )

    parser.add_argument(
        "--write",
        action="store_true",
        help=(
            "Publish validated rfobs1 decks and immutable "
            "preparation records. Without this flag, all "
            "candidate decks are generated in temporary storage."
        ),
    )

    return parser.parse_args()


def load_json(
    path: Path,
) -> dict:
    if not path.is_file():
        raise FileNotFoundError(
            path
        )

    value = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(
        value,
        dict,
    ):
        raise RuntimeError(
            f"Expected JSON object: {path}"
        )

    return value


def sha256(
    path: Path,
) -> str:
    if (
        not path.is_file()
        or path.stat().st_size <= 0
    ):
        raise FileNotFoundError(
            path
        )

    digest = hashlib.sha256()

    with path.open(
        "rb"
    ) as stream:
        for chunk in iter(
            lambda: stream.read(
                8 * 1024 * 1024
            ),
            b"",
        ):
            digest.update(
                chunk
            )

    return digest.hexdigest()


def relative(
    path: Path,
) -> str:
    return (
        path.resolve()
        .relative_to(
            ROOT.resolve()
        )
        .as_posix()
    )


def verify_sha_sidecar(
    path: Path,
) -> str:
    actual = sha256(
        path
    )

    sidecar = path.with_suffix(
        ".sha256"
    )

    if not sidecar.is_file():
        raise RuntimeError(
            f"Missing SHA sidecar: {sidecar}"
        )

    expected_text = (
        f"{actual}  {path.name}\n"
    )

    actual_text = (
        sidecar.read_text(
            encoding="ascii"
        )
    )

    if (
        actual_text
        != expected_text
    ):
        raise RuntimeError(
            f"SHA sidecar drift: {sidecar}"
        )

    return actual


def write_immutable_json(
    path: Path,
    payload: dict,
) -> tuple[str, str]:
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

        if (
            existing
            != serialized
        ):
            raise RuntimeError(
                "Immutable rfobs1 preparation exists "
                "with different content: "
                f"{path}"
            )

        action = (
            "UNCHANGED / IDENTICAL"
        )

    else:
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary = path.with_suffix(
            ".json.tmp"
        )

        if temporary.exists():
            raise RuntimeError(
                "Stale temporary preparation exists: "
                f"{temporary}"
            )

        temporary.write_text(
            serialized,
            encoding="utf-8",
            newline="\n",
        )

        temporary.replace(
            path
        )

        action = "CREATED"

    record_hash = sha256(
        path
    )

    sidecar = path.with_suffix(
        ".sha256"
    )

    sidecar_text = (
        f"{record_hash}  {path.name}\n"
    )

    if sidecar.exists():
        existing = sidecar.read_text(
            encoding="ascii"
        )

        if (
            existing
            != sidecar_text
        ):
            raise RuntimeError(
                "rfobs1 preparation SHA sidecar drift: "
                f"{sidecar}"
            )

    else:
        sidecar.write_text(
            sidecar_text,
            encoding="ascii",
            newline="\n",
        )

    return (
        action,
        record_hash,
    )


def load_toml(
    path: Path,
) -> dict:
    with path.open(
        "rb"
    ) as stream:
        return tomllib.load(
            stream
        )


def reference_temperature_c() -> float:
    data = load_toml(
        CONFIG
        / "complete_joint_preload.toml"
    )

    matches: list[float] = []

    def walk(
        value: object,
    ) -> None:
        if isinstance(
            value,
            dict,
        ):
            for (
                key,
                child,
            ) in value.items():
                if (
                    key
                    == "reference_temperature_c"
                ):
                    matches.append(
                        float(
                            child
                        )
                    )
                else:
                    walk(
                        child
                    )

        elif isinstance(
            value,
            list,
        ):
            for child in value:
                walk(
                    child
                )

    walk(
        data
    )

    if len(
        matches
    ) != 1:
        raise RuntimeError(
            "Expected exactly one governed "
            "reference_temperature_c."
        )

    return matches[0]


def find_preparation_row(
    certification: dict,
    case_id: str,
) -> dict:
    matches = [
        row
        for row in certification[
            "design_case_preparation_evidence"
        ]
        if row[
            "case_id"
        ]
        == case_id
    ]

    if len(
        matches
    ) != 1:
        raise RuntimeError(
            f"{case_id}: expected one certified "
            "preparation row; found "
            f"{len(matches)}."
        )

    return matches[0]


def solver_outputs_present(
    path: Path,
) -> tuple[str, ...]:
    if not path.exists():
        return ()

    matches = []

    for item in path.rglob(
        "*"
    ):
        if (
            item.is_file()
            and item.suffix.lower()
            in SOLVER_OUTPUT_SUFFIXES
        ):
            matches.append(
                str(
                    item
                )
            )

    return tuple(
        sorted(
            matches
        )
    )


def named_boundary_sets(
    deck_text: str,
) -> tuple[str, ...]:
    lines = deck_text.splitlines()

    names: set[str] = set()

    index = 0

    while index < len(
        lines
    ):
        row = (
            lines[
                index
            ]
            .strip()
        )

        if not row.upper().startswith(
            "*BOUNDARY"
        ):
            index += 1
            continue

        index += 1

        while index < len(
            lines
        ):
            row = (
                lines[
                    index
                ]
                .strip()
            )

            if row.startswith(
                "*"
            ):
                break

            if (
                row
                and not row.startswith(
                    "**"
                )
            ):
                token = (
                    row
                    .split(
                        ",",
                        1,
                    )[0]
                    .strip()
                    .upper()
                )

                try:
                    int(
                        token
                    )
                except ValueError:
                    names.add(
                        token
                    )

            index += 1

    return tuple(
        sorted(
            names
        )
    )


def rf_observable_node_print_sets(
    deck_text: str,
) -> tuple[str, ...]:
    lines = deck_text.splitlines()

    names: set[str] = set()

    for (
        index,
        row,
    ) in enumerate(
        lines
    ):
        upper = (
            row
            .strip()
            .upper()
        )

        if not upper.startswith(
            "*NODE PRINT"
        ):
            continue

        match = re.search(
            r"NSET\s*=\s*([^,\s]+)",
            upper,
        )

        if match is None:
            continue

        set_name = (
            match
            .group(1)
            .strip()
            .upper()
        )

        cursor = (
            index
            + 1
        )

        has_rf = False

        while cursor < len(
            lines
        ):
            child = (
                lines[
                    cursor
                ]
                .strip()
                .upper()
            )

            if child.startswith(
                "*"
            ):
                break

            if (
                child
                and not child.startswith(
                    "**"
                )
            ):
                variables = {
                    value.strip()
                    for value in child.split(
                        ","
                    )
                }

                if (
                    "RF"
                    in variables
                ):
                    has_rf = True

            cursor += 1

        if has_rf:
            names.add(
                set_name
            )

    return tuple(
        sorted(
            names
        )
    )


def require_close(
    label: str,
    actual: float,
    expected: float,
) -> None:
    if not math.isclose(
        actual,
        expected,
        rel_tol=0.0,
        abs_tol=1.0e-10,
    ):
        raise RuntimeError(
            f"{label} drift: "
            f"{actual!r} != {expected!r}"
        )


def main() -> None:
    args = parse_args()

    policy = (
        load_phase3_production_doe_policy(
            DOE_POLICY_PATH
        )
    )

    campaign = (
        build_phase3_production_doe(
            policy
        )
    )

    fresh = tuple(
        case
        for case
        in campaign.design_cases
        if case.source_case_id
        is None
    )

    pending = tuple(
        case
        for case
        in fresh
        if not (
            SOLVER_ROOT
            / (
                "trm_fem_"
                + case.case_hash[:12]
            )
            / "production_doe_accepted_fem_evidence.json"
        ).exists()
    )

    actual_pending_ids = tuple(
        sorted(
            case.case_id
            for case
            in pending
        )
    )

    if (
        actual_pending_ids
        != PENDING_CASE_IDS
    ):
        raise RuntimeError(
            "Pending Production-DOE identity drift.\n"
            f"Expected: {PENDING_CASE_IDS}\n"
            f"Actual  : {actual_pending_ids}"
        )

    preparation_cert = load_json(
        PREPARATION_CERT_PATH
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

    results = []

    for doe_case in pending:
        resolved = resolve_case(
            doe_case.case
        )

        if (
            resolved.case_hash
            != doe_case.case_hash
        ):
            raise RuntimeError(
                f"{doe_case.case_id}: "
                "resolved case-hash drift."
            )

        case_run_id = (
            "trm_fem_"
            + resolved.case_hash[:12]
        )

        identity = (
            derive_reaction_observable_revision_identity(
                case_run_id=(
                    case_run_id
                ),
            )
        )

        source_dir = (
            SOLVER_ROOT
            / case_run_id
            / identity.source_trial_run_id
        )

        source_record_path = (
            source_dir
            / SOURCE_PREPARATION_NAME
        )

        source_record_hash = (
            verify_sha_sidecar(
                source_record_path
            )
        )

        source_record = load_json(
            source_record_path
        )

        if (
            source_record.get(
                "record_status"
            )
            != "FINAL"
            or source_record.get(
                "overall_disposition"
            )
            != EXPECTED_SOURCE_DISPOSITION
        ):
            raise RuntimeError(
                f"{doe_case.case_id}: "
                "source WSV21 preparation is not "
                "governed FINAL PASS."
            )

        source_case = (
            source_record[
                "case"
            ]
        )

        if (
            source_case[
                "case_id"
            ]
            != doe_case.case_id
            or source_case[
                "case_hash"
            ]
            != doe_case.case_hash
            or source_case[
                "v2_1_trial1_run_id"
            ]
            != identity.source_trial_run_id
        ):
            raise RuntimeError(
                f"{doe_case.case_id}: "
                "source WSV21 identity drift."
            )

        source_trial = (
            source_record[
                "trial_1"
            ]
        )

        if (
            int(
                source_trial[
                    "trial_index"
                ]
            )
            != 1
            or source_trial[
                "run_id"
            ]
            != identity.source_trial_run_id
        ):
            raise RuntimeError(
                f"{doe_case.case_id}: "
                "source WSV21 Trial-1 identity drift."
            )

        delta_temperature_c = float(
            source_trial[
                "delta_temperature_c"
            ]
        )

        source_deck_path = (
            ROOT
            / source_record[
                "deck"
            ][
                "relative_path"
            ]
        )

        source_deck_hash = sha256(
            source_deck_path
        )

        if (
            source_deck_hash
            != source_record[
                "deck"
            ][
                "sha256"
            ]
        ):
            raise RuntimeError(
                f"{doe_case.case_id}: "
                "source WSV21 deck SHA drift."
            )

        source_outputs = (
            solver_outputs_present(
                source_dir
            )
        )

        if source_outputs:
            raise RuntimeError(
                f"{doe_case.case_id}: "
                "pending WSV21 source unexpectedly "
                "contains solver output:\n"
                + "\n".join(
                    source_outputs
                )
            )

        preflight = preflight_case(
            doe_case.case,
            PreflightTarget.FEM,
        )

        blocking = tuple(
            finding
            for finding
            in preflight.findings
            if (
                finding.severity
                is PreflightSeverity.ERROR
            )
        )

        if blocking:
            raise RuntimeError(
                f"{doe_case.case_id}: "
                "FEM preflight BLOCKED: "
                + "; ".join(
                    str(
                        finding
                    )
                    for finding
                    in blocking
                )
            )

        preparation_row = (
            find_preparation_row(
                preparation_cert,
                doe_case.case_id,
            )
        )

        if (
            preparation_row[
                "case_hash"
            ]
            != doe_case.case_hash
            or preparation_row[
                "mesh_policy_name"
            ]
            != doe_case.mesh_policy_name
        ):
            raise RuntimeError(
                f"{doe_case.case_id}: "
                "certified prepared-artifact "
                "identity drift."
            )

        mesh_path = (
            ROOT
            / preparation_row[
                "mesh_relative_path"
            ]
        )

        step_path = (
            ROOT
            / preparation_row[
                "step_relative_path"
            ]
        )

        mesh_hash = sha256(
            mesh_path
        )

        step_hash = sha256(
            step_path
        )

        if (
            mesh_hash
            != preparation_row[
                "mesh_sha256"
            ]
        ):
            raise RuntimeError(
                f"{doe_case.case_id}: "
                "certified mesh SHA drift."
            )

        if (
            step_hash
            != preparation_row[
                "step_sha256"
            ]
        ):
            raise RuntimeError(
                f"{doe_case.case_id}: "
                "certified STEP SHA drift."
            )

        if (
            source_record[
                "prepared_artifacts"
            ][
                "mesh_sha256"
            ]
            != mesh_hash
            or source_record[
                "prepared_artifacts"
            ][
                "step_sha256"
            ]
            != step_hash
        ):
            raise RuntimeError(
                f"{doe_case.case_id}: "
                "source WSV21 prepared-artifact "
                "binding drift."
            )

        token = (
            resolved.case_hash[:16]
        )

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
            )
        )

        current_resolution_run_id = (
            bundle
            .preparation
            .identity
            .run_id
        )

        bundle = (
            bridge_bundle_to_frozen_production_doe_identity(
                bundle=bundle,
                case_hash=(
                    doe_case.case_hash
                ),
                resolution_hash=(
                    resolved.resolution_hash
                ),
                frozen_case_run_id=(
                    case_run_id
                ),
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
                f"{doe_case.case_id}: "
                "frozen-lineage bridge did not "
                "restore the governed DOE case run ID."
            )

        mesh_data = (
            read_grouped_complete_joint_mesh(
                mesh_path,
                bundle.transfer,
            )
        )

        trial = (
            PreloadCalibrationTrial(
                trial_index=1,
                run_id=(
                    identity
                    .revision_trial_run_id
                ),
                delta_temperature_c=(
                    delta_temperature_c
                ),
                source=(
                    PreloadCalibrationTrialSource
                    .FEM_WARM_START
                ),
            )
        )

        revision_dir = (
            SOLVER_ROOT
            / case_run_id
            / identity.revision_trial_run_id
        )

        final_deck_path = (
            revision_dir
            / (
                identity
                .revision_trial_run_id
                + ".inp"
            )
        )

        source_record_hash_before = (
            sha256(
                source_record_path
            )
        )

        source_deck_hash_before = (
            sha256(
                source_deck_path
            )
        )

        if args.write:
            revision_dir.mkdir(
                parents=True,
                exist_ok=True,
            )

            candidate_path = (
                final_deck_path
                .with_suffix(
                    ".inp.tmp"
                )
            )

            if candidate_path.exists():
                raise RuntimeError(
                    "Stale rfobs1 deck temporary exists: "
                    f"{candidate_path}"
                )

        else:
            temp_context = (
                tempfile.TemporaryDirectory(
                    prefix=(
                        "threadrom_rfobs1_"
                        + doe_case.case_id
                        + "_"
                    )
                )
            )

            temp_name = (
                temp_context
                .__enter__()
            )

            candidate_path = (
                Path(
                    temp_name
                )
                / (
                    identity
                    .revision_trial_run_id
                    + ".inp"
                )
            )

        try:
            deck = (
                write_fem_preload_calibration_trial_deck(
                    mesh_data=(
                        mesh_data
                    ),
                    bundle=(
                        bundle
                    ),
                    trial=(
                        trial
                    ),
                    reference_temperature_c=(
                        reference_temperature
                    ),
                    input_path=(
                        candidate_path
                    ),
                )
            )

            candidate_hash = sha256(
                candidate_path
            )

            if (
                candidate_hash
                != deck.sha256
            ):
                raise RuntimeError(
                    f"{doe_case.case_id}: "
                    "candidate deck SHA mismatch."
                )

            if (
                deck.trial_run_id
                != identity
                .revision_trial_run_id
            ):
                raise RuntimeError(
                    f"{doe_case.case_id}: "
                    "candidate deck/trial "
                    "identity mismatch."
                )

            require_close(
                (
                    f"{doe_case.case_id} "
                    "rfobs1 delta T"
                ),
                deck.delta_temperature_c,
                delta_temperature_c,
            )

            candidate_text = (
                candidate_path.read_text(
                    encoding="utf-8",
                    errors="replace",
                )
            )

            constrained_sets = (
                named_boundary_sets(
                    candidate_text
                )
            )

            observable_sets = (
                rf_observable_node_print_sets(
                    candidate_text
                )
            )

            observability = (
                certify_named_reaction_observability(
                    constrained_reaction_sets=(
                        constrained_sets
                    ),
                    observable_reaction_sets=(
                        observable_sets
                    ),
                )
            )

            if (
                len(
                    constrained_sets
                )
                != 9
            ):
                raise RuntimeError(
                    f"{doe_case.case_id}: "
                    "expected support plus eight "
                    "constrained reference carriers; "
                    f"found {constrained_sets!r}."
                )

            if args.write:
                if final_deck_path.exists():
                    existing_hash = (
                        sha256(
                            final_deck_path
                        )
                    )

                    if (
                        existing_hash
                        != candidate_hash
                    ):
                        raise RuntimeError(
                            f"{doe_case.case_id}: "
                            "immutable rfobs1 deck "
                            "already exists with "
                            "different content."
                        )

                    candidate_path.unlink()

                    deck_action = (
                        "UNCHANGED / IDENTICAL"
                    )

                else:
                    candidate_path.replace(
                        final_deck_path
                    )

                    deck_action = (
                        "CREATED"
                    )

                published_deck_path = (
                    final_deck_path
                )

            else:
                deck_action = (
                    "DRY-RUN / NOT WRITTEN"
                )

                published_deck_path = (
                    candidate_path
                )

            record = {
                "schema_version": 1,
                "record_id": (
                    "TRM-P3-CP8-RFOBS1-"
                    f"{doe_case.case_id}-PREP-P01"
                ),
                "record_status": "FINAL",
                "case": {
                    "case_id": (
                        doe_case.case_id
                    ),
                    "case_hash": (
                        doe_case.case_hash
                    ),
                    "canonical_case_run_id": (
                        case_run_id
                    ),
                    "current_resolution_hash": (
                        resolved.resolution_hash
                    ),
                    "current_resolution_run_id": (
                        current_resolution_run_id
                    ),
                    "source_v2_1_trial_run_id": (
                        identity
                        .source_trial_run_id
                    ),
                    "reaction_observable_trial_run_id": (
                        identity
                        .revision_trial_run_id
                    ),
                    "trial_index": 1,
                    "mesh_policy_name": (
                        doe_case
                        .mesh_policy_name
                    ),
                    "target_preload_n": (
                        resolved
                        .source_case
                        .loading
                        .target_preload_n
                    ),
                },
                "revision_semantics": {
                    "revision_tag": (
                        identity
                        .revision_tag
                    ),
                    "purpose": (
                        "REACTION_OUTPUT_CONTRACT_ONLY"
                    ),
                    "new_calibration_attempt": False,
                    "trial_one_semantics_preserved": True,
                    "source_v2_1_prediction_preserved": True,
                    "source_delta_temperature_preserved": True,
                    "frozen_lineage_identity_bridge_applied": True,
                    "frozen_lineage_identity_bridge_scope": (
                        "EXECUTION_IDENTITY_ONLY"
                    ),
                    "current_resolution_hash_preserved": True,
                    "mesh_regenerated": False,
                    "fem_solution_reused": False,
                    "solver_result_read": False,
                    "equilibrium_pass_claimed": False,
                    "equilibrium_tolerance_changed": False,
                    "holdout_accessed": False,
                },
                "source_v2_1_preparation": {
                    "relative_path": (
                        relative(
                            source_record_path
                        )
                    ),
                    "sha256": (
                        source_record_hash
                    ),
                    "deck_relative_path": (
                        relative(
                            source_deck_path
                        )
                    ),
                    "deck_sha256": (
                        source_deck_hash
                    ),
                    "delta_temperature_c": (
                        delta_temperature_c
                    ),
                    "overall_disposition": (
                        source_record[
                            "overall_disposition"
                        ]
                    ),
                },
                "certified_prepared_artifacts": {
                    "mesh_relative_path": (
                        relative(
                            mesh_path
                        )
                    ),
                    "mesh_sha256": (
                        mesh_hash
                    ),
                    "step_relative_path": (
                        relative(
                            step_path
                        )
                    ),
                    "step_sha256": (
                        step_hash
                    ),
                },
                "fem_preflight": {
                    "target": "fem",
                    "blocking_error_count": 0,
                    "status": "PASS",
                },
                "trial": {
                    "trial_index": 1,
                    "run_id": (
                        identity
                        .revision_trial_run_id
                    ),
                    "delta_temperature_c": (
                        delta_temperature_c
                    ),
                    "source": (
                        trial.source.value
                    ),
                },
                "deck": {
                    "relative_path": (
                        relative(
                            final_deck_path
                        )
                        if args.write
                        else (
                            "DRY_RUN_TEMPORARY"
                        )
                    ),
                    "sha256": (
                        candidate_hash
                    ),
                    "size_bytes": (
                        published_deck_path
                        .stat()
                        .st_size
                    ),
                    "node_count": (
                        deck.node_count
                    ),
                    "element_count": (
                        deck.element_count
                    ),
                    "delta_temperature_c": (
                        deck
                        .delta_temperature_c
                    ),
                },
                "reaction_observability": {
                    "constrained_reaction_sets": list(
                        observability
                        .constrained_reaction_sets
                    ),
                    "observable_reaction_sets": list(
                        observability
                        .observable_reaction_sets
                    ),
                    "missing_reaction_sets": list(
                        observability
                        .missing_reaction_sets
                    ),
                    "fully_observable": (
                        observability
                        .fully_observable
                    ),
                    "full_system_equilibrium_pass_claimed": False,
                    "equilibrium_tolerance_changed": False,
                },
                "execution_authorization": {
                    "calculix_invoked_by_this_record": False,
                    "execution_authorized_by_this_record": False,
                    "blind_holdout_execution_authorized": False,
                    "requires_gate0_authorization_before_execution": True,
                },
                "overall_disposition": (
                    REVISION_DISPOSITION
                ),
            }

            if args.write:
                record_path = (
                    revision_dir
                    / REVISION_PREPARATION_NAME
                )

                (
                    record_action,
                    record_hash,
                ) = write_immutable_json(
                    record_path,
                    record,
                )

            else:
                record_action = (
                    "DRY-RUN / NOT WRITTEN"
                )

                serialized = (
                    json.dumps(
                        record,
                        indent=2,
                        sort_keys=True,
                    )
                    + "\n"
                )

                record_hash = (
                    hashlib.sha256(
                        serialized.encode(
                            "utf-8"
                        )
                    )
                    .hexdigest()
                )

            if (
                sha256(
                    source_record_path
                )
                != source_record_hash_before
                or sha256(
                    source_deck_path
                )
                != source_deck_hash_before
            ):
                raise RuntimeError(
                    f"{doe_case.case_id}: "
                    "source WSV21 evidence changed "
                    "during rfobs1 preparation."
                )

            results.append(
                {
                    "case_id": (
                        doe_case.case_id
                    ),
                    "run_id": (
                        identity
                        .revision_trial_run_id
                    ),
                    "delta_temperature_c": (
                        delta_temperature_c
                    ),
                    "deck_sha256": (
                        candidate_hash
                    ),
                    "deck_action": (
                        deck_action
                    ),
                    "record_sha256": (
                        record_hash
                    ),
                    "record_action": (
                        record_action
                    ),
                    "constrained_count": len(
                        observability
                        .constrained_reaction_sets
                    ),
                    "observable_count": len(
                        observability
                        .observable_reaction_sets
                    ),
                    "missing_count": len(
                        observability
                        .missing_reaction_sets
                    ),
                }
            )

        finally:
            if not args.write:
                temp_context.__exit__(
                    None,
                    None,
                    None,
                )

            elif candidate_path.exists():
                candidate_path.unlink()

    print(
        "=" * 132
    )

    print(
        "THREADROM - PRODUCTION DOE RFOBS1 "
        "ZERO-SOLVE PREPARATION"
    )

    print(
        "=" * 132
    )

    for result in results:
        print()

        print(
            result[
                "case_id"
            ],
            "|",
            result[
                "run_id"
            ],
        )

        print(
            "  Delta T             :",
            result[
                "delta_temperature_c"
            ],
        )

        print(
            "  Deck SHA256         :",
            result[
                "deck_sha256"
            ],
        )

        print(
            "  Deck action         :",
            result[
                "deck_action"
            ],
        )

        print(
            "  Preparation SHA256  :",
            result[
                "record_sha256"
            ],
        )

        print(
            "  Preparation action  :",
            result[
                "record_action"
            ],
        )

        print(
            "  Constrained carriers:",
            result[
                "constrained_count"
            ],
        )

        print(
            "  RF-observable sets  :",
            result[
                "observable_count"
            ],
        )

        print(
            "  Missing carriers    :",
            result[
                "missing_count"
            ],
        )

    print()

    print(
        "-" * 132
    )

    print(
        "Cases prepared           :",
        len(
            results
        ),
    )

    print(
        "Mode                     :",
        (
            "WRITE"
            if args.write
            else "DRY-RUN"
        ),
    )

    print(
        "CalculiX invoked         : NO"
    )

    print(
        "FEM solutions executed   : NO"
    )

    print(
        "Meshes generated         : NO"
    )

    print(
        "Source WSV21 mutated     : NO"
    )

    print(
        "Holdouts accessed        : NO"
    )

    print(
        "Equilibrium PASS claimed : NO"
    )

    print(
        "Tolerance changed        : NO"
    )

    print(
        "=" * 132
    )


if __name__ == "__main__":
    main()
