"""Build/audit the governed Phase-3 calibration observation store V1.

Historical W01/W02 calibration solves are replayed from their immutable
preparation records and CalculiX DAT evidence.

No CAD, mesh, deck, solver, dataset admission, or holdout access occurs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import tomllib

from dataclasses import dataclass
from pathlib import Path

from threadrom.case.resolver import resolve_case
from threadrom.factory.diversified_doe_design import (
    _build_case,
)
from threadrom.factory.fem_calibration_knowledge import (
    FemGeometryRealizationIdentity,
    build_fem_calibration_feature_vector,
)
from threadrom.factory.fem_calibration_observation_store import (
    FemCalibrationObservation,
    calibration_observations,
    load_calibration_observation_store,
    new_calibration_observation_store,
    persist_calibration_observation_store,
    register_calibration_observation,
)
from threadrom.factory.fem_preload_calibration_measurement import (
    extract_clamp_force_measurement_from_dat,
)
from threadrom.factory.preload_calibration_campaign import (
    PreloadCalibrationTrial,
    PreloadCalibrationTrialSource,
    evaluate_preload_calibration_trial,
)
from threadrom.materials.diversified_candidate_catalog import (
    DIVERSIFIED_CANDIDATE_MATERIAL_CATALOG,
)
from threadrom.solver.complete_joint_contact import (
    load_complete_joint_contact_definition,
)
from threadrom.solver.complete_joint_preload import (
    load_complete_joint_preload_definition,
)


ROOT = Path(r"D:\ThreadROM").resolve()

DOE_ROOT = (
    ROOT
    / "simulations"
    / "staging"
    / "phase3_diversified_doe"
    / "TRM-DDOE-001"
)

WAVE_DOC_ROOT = (
    ROOT
    / "docs"
    / "phase3_diversified_doe"
    / "waves"
)

PROPOSAL_PATH = (
    ROOT
    / "docs"
    / "phase3_diversified_doe"
    / "design_proposal.json"
)

POLICY_PATH = (
    ROOT
    / "config"
    / "phase3_diversified_doe.toml"
)

GEOMETRY_ATLAS_PATH = (
    ROOT
    / "docs"
    / "phase3_geometry_mesh_atlas"
    / "atlas.json"
)

GEOMETRY_CLOSURE_PATH = (
    ROOT
    / "docs"
    / "phase3_geometry_mesh_atlas"
    / "slice1_closure.json"
)

STORE_PATH = (
    ROOT
    / "docs"
    / "phase3_calibration_knowledge"
    / "observations_v1.json"
)

WAVES = (
    "W01",
    "W02",
)

LEGACY_W01_EXECUTION_GENERATION_ID = (
    "legacy_diversified_w01_unversioned_execution"
)


@dataclass(frozen=True)
class _SeedProxy:
    """Only field consumed by the existing feature-vector builder."""

    predicted_delta_temperature_c: float


def require(
    condition: bool,
    message: str,
) -> None:
    if not condition:
        raise RuntimeError(
            message
        )


def read_json(
    path: Path,
):
    return json.loads(
        path.read_text(
            encoding="utf-8-sig"
        )
    )


def sha256(
    path: Path,
) -> str:
    require(
        path.is_file(),
        f"Required file missing: {path}",
    )

    digest = hashlib.sha256()

    with path.open("rb") as stream:
        for chunk in iter(
            lambda: stream.read(
                1024 * 1024
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
        .relative_to(ROOT)
        .as_posix()
    )


def find_generation_values(
    value,
) -> set[str]:
    """Find explicitly governed execution-generation values."""

    found: set[str] = set()

    if isinstance(
        value,
        dict,
    ):
        for key, child in value.items():
            folded = str(
                key
            ).casefold()

            if (
                folded
                in {
                    "execution_generation",
                    "execution_generation_id",
                }
                and isinstance(
                    child,
                    str,
                )
                and child.strip()
            ):
                found.add(
                    child.strip()
                )

            found.update(
                find_generation_values(
                    child
                )
            )

    elif isinstance(
        value,
        list,
    ):
        for child in value:
            found.update(
                find_generation_values(
                    child
                )
            )

    return found


def execution_generation_id(
    wave_name: str,
) -> str:
    """Recover W02 generation; keep pre-generation W01 isolated."""

    if wave_name == "W01":
        return (
            LEGACY_W01_EXECUTION_GENERATION_ID
        )

    candidates: set[str] = set()

    wave_docs = (
        WAVE_DOC_ROOT
        / "TRM-DDOE-001-W02"
    )

    for name in (
        "trial1_owner_authorization.json",
        "adaptive_campaign_owner_authorization.json",
        "geometry_mesh_owner_authorization.json",
    ):
        path = (
            wave_docs
            / name
        )

        if path.is_file():
            candidates.update(
                find_generation_values(
                    read_json(
                        path
                    )
                )
            )

    require(
        len(
            candidates
        )
        == 1,
        (
            "W02 execution generation must be "
            "uniquely recoverable from governed authorization; "
            f"found {sorted(candidates)!r}."
        ),
    )

    return next(
        iter(
            candidates
        )
    )


def proposal_case_map():
    proposal = read_json(
        PROPOSAL_PATH
    )

    return {
        row[
            "proposal_id"
        ]: row
        for row in proposal[
            "cases"
        ]
    }


def reconstruct_resolved_case(
    *,
    case_id: str,
    proposal_row: dict,
    policy: dict,
):
    size = next(
        row
        for row in policy[
            "size_candidates"
        ]
        if row[
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

    require(
        resolved.case_hash
        == proposal_row[
            "case_hash"
        ],
        f"{case_id}: reconstructed case hash drift.",
    )

    return resolved


def geometry_identity_for_case(
    *,
    case_id: str,
    geometry_atlas: dict,
) -> FemGeometryRealizationIdentity:
    binding = geometry_atlas[
        "case_bindings"
    ][
        case_id
    ]

    generation_id = geometry_atlas[
        "identity_contract"
    ][
        "geometry_generation_id"
    ]

    return FemGeometryRealizationIdentity(
        generation_id=(
            generation_id
        ),
        realization_id=(
            binding[
                "geometry_id"
            ]
        ),
    )


def adaptive_preparation_path(
    trial_dir: Path,
) -> Path:
    candidates = sorted(
        trial_dir.glob(
            "*_adaptive_preparation.json"
        )
    )

    require(
        len(
            candidates
        )
        == 1,
        (
            f"{trial_dir}: expected exactly one "
            "adaptive preparation record."
        ),
    )

    return candidates[0]


def build_store() -> dict:
    geometry_closure = read_json(
        GEOMETRY_CLOSURE_PATH
    )

    require(
        sha256(
            GEOMETRY_ATLAS_PATH
        )
        == geometry_closure[
            "atlas"
        ][
            "sha256"
        ],
        "Slice-1 Geometry/Mesh Atlas SHA drift.",
    )

    geometry_atlas = read_json(
        GEOMETRY_ATLAS_PATH
    )

    proposal_by_id = (
        proposal_case_map()
    )

    policy = tomllib.loads(
        POLICY_PATH.read_text(
            encoding="utf-8-sig"
        )
    )

    contact = (
        load_complete_joint_contact_definition(
            ROOT
            / "config"
            / "complete_joint_contact.toml"
        )
    )

    preload = (
        load_complete_joint_preload_definition(
            ROOT
            / "config"
            / "complete_joint_preload.toml"
        )
    )

    store = (
        new_calibration_observation_store()
    )

    store[
        "scope"
    ] = (
        "Governed W01/W02 solved calibration observations "
        "for prospective Trial-1 prediction."
    )

    store[
        "governance"
    ] = {
        "accepted_trials_included": True,
        "valid_calibration_misses_included": True,
        "interrupted_zero_byte_attempts_included": False,
        "rom_dataset_admission": False,
        "holdout_access": False,
    }

    store[
        "execution_generation_boundaries"
    ] = {}

    store[
        "source_evidence"
    ] = {
        "design_proposal": {
            "path": relative(
                PROPOSAL_PATH
            ),
            "sha256": sha256(
                PROPOSAL_PATH
            ),
        },
        "design_policy": {
            "path": relative(
                POLICY_PATH
            ),
            "sha256": sha256(
                POLICY_PATH
            ),
        },
        "geometry_mesh_atlas": {
            "path": relative(
                GEOMETRY_ATLAS_PATH
            ),
            "sha256": sha256(
                GEOMETRY_ATLAS_PATH
            ),
        },
    }

    counts = {
        "continue": 0,
        "accept": 0,
    }

    for wave_name in WAVES:
        execution_id = (
            execution_generation_id(
                wave_name
            )
        )

        store[
            "execution_generation_boundaries"
        ][
            wave_name
        ] = execution_id

        wave_root = (
            DOE_ROOT
            / wave_name
        )

        index_path = (
            wave_root
            / (
                f"{wave_name.casefold()}"
                "_trial1_preparation.json"
            )
        )

        index = read_json(
            index_path
        )

        store[
            "source_evidence"
        ][
            wave_name
        ] = {
            "preparation_index_path": (
                relative(
                    index_path
                )
            ),
            "preparation_index_sha256": (
                sha256(
                    index_path
                )
            ),
        }

        rows = index[
            "prepared_trials"
        ]

        require(
            len(
                rows
            )
            == 4,
            f"{wave_name}: expected exactly four cases.",
        )

        for row in rows:
            case_id = row[
                "case_id"
            ]

            proposal_row = (
                proposal_by_id[
                    case_id
                ]
            )

            resolved = (
                reconstruct_resolved_case(
                    case_id=case_id,
                    proposal_row=proposal_row,
                    policy=policy,
                )
            )

            require(
                resolved.case_hash
                == row[
                    "case_hash"
                ],
                f"{case_id}: preparation-index case hash drift.",
            )

            geometry_identity = (
                geometry_identity_for_case(
                    case_id=case_id,
                    geometry_atlas=geometry_atlas,
                )
            )

            case_run_id = row[
                "case_run_id"
            ]

            case_root = (
                wave_root
                / "solver_preparation"
                / case_run_id
            )

            trial1_prep_path = (
                ROOT
                / row[
                    "preparation_record"
                ]
            )

            trial1_prep = read_json(
                trial1_prep_path
            )

            trial1_payload = (
                trial1_prep[
                    "trial_1"
                ]
            )

            trial1 = (
                PreloadCalibrationTrial(
                    trial_index=int(
                        trial1_payload[
                            "trial_index"
                        ]
                    ),
                    run_id=str(
                        trial1_payload[
                            "run_id"
                        ]
                    ),
                    delta_temperature_c=float(
                        trial1_payload[
                            "delta_temperature_c"
                        ]
                    ),
                    source=(
                        PreloadCalibrationTrialSource(
                            trial1_payload[
                                "source"
                            ]
                        )
                    ),
                )
            )

            require(
                trial1.trial_index == 1,
                f"{case_id}: Trial-1 index drift.",
            )

            trial1_dir = (
                case_root
                / trial1.run_id
            )

            trial1_dat = (
                trial1_dir
                / f"{trial1.run_id}.dat"
            )

            require(
                trial1_dat.is_file()
                and trial1_dat.stat().st_size > 0,
                f"{trial1.run_id}: valid DAT missing.",
            )

            trial1_extraction = (
                extract_clamp_force_measurement_from_dat(
                    dat_path=trial1_dat,
                    contact_pairs=(
                        contact.contact_pairs
                    ),
                )
            )

            trial1_evaluation = (
                evaluate_preload_calibration_trial(
                    case_run_id=case_run_id,
                    target_force_n=(
                        resolved.source_case.loading.target_preload_n
                    ),
                    target_relative_tolerance=(
                        preload.target_relative_tolerance
                    ),
                    spread_relative_tolerance=(
                        preload.interface_spread_relative_tolerance
                    ),
                    current_trial=trial1,
                    measurement=(
                        trial1_extraction.measurement
                    ),
                )
            )

            require(
                trial1_evaluation.decision.disposition.value
                == "continue",
                (
                    f"{trial1.run_id}: expected historical "
                    "CAL_01 disposition CONTINUE."
                ),
            )

            trial2_dir = (
                case_root
                / f"{case_run_id}_cal_02"
            )

            trial2_prep_path = (
                adaptive_preparation_path(
                    trial2_dir
                )
            )

            trial2_prep = read_json(
                trial2_prep_path
            )

            trial2_payload = (
                trial2_prep[
                    "trial"
                ]
            )

            trial2 = (
                PreloadCalibrationTrial(
                    trial_index=int(
                        trial2_payload[
                            "trial_index"
                        ]
                    ),
                    run_id=str(
                        trial2_payload[
                            "run_id"
                        ]
                    ),
                    delta_temperature_c=float(
                        trial2_payload[
                            "delta_temperature_c"
                        ]
                    ),
                    source=(
                        PreloadCalibrationTrialSource(
                            trial2_payload[
                                "source"
                            ]
                        )
                    ),
                )
            )

            require(
                trial2.trial_index == 2,
                f"{case_id}: Trial-2 index drift.",
            )

            trial2_dat = (
                trial2_dir
                / f"{trial2.run_id}.dat"
            )

            require(
                trial2_dat.is_file()
                and trial2_dat.stat().st_size > 0,
                f"{trial2.run_id}: valid DAT missing.",
            )

            trial2_extraction = (
                extract_clamp_force_measurement_from_dat(
                    dat_path=trial2_dat,
                    contact_pairs=(
                        contact.contact_pairs
                    ),
                )
            )

            trial2_evaluation = (
                evaluate_preload_calibration_trial(
                    case_run_id=case_run_id,
                    target_force_n=(
                        resolved.source_case.loading.target_preload_n
                    ),
                    target_relative_tolerance=(
                        preload.target_relative_tolerance
                    ),
                    spread_relative_tolerance=(
                        preload.interface_spread_relative_tolerance
                    ),
                    current_trial=trial2,
                    measurement=(
                        trial2_extraction.measurement
                    ),
                    previous_trial=trial1,
                    previous_measurement=(
                        trial1_extraction.measurement
                    ),
                )
            )

            require(
                trial2_evaluation.decision.disposition.value
                == "accept",
                (
                    f"{trial2.run_id}: expected historical "
                    "CAL_02 disposition ACCEPT."
                ),
            )

            analytical_dt = (
                trial1.delta_temperature_c
            )

            feature = (
                build_fem_calibration_feature_vector(
                    resolved,
                    _SeedProxy(
                        predicted_delta_temperature_c=(
                            analytical_dt
                        )
                    ),
                    geometry_identity,
                    execution_id,
                )
            )

            trials = (
                (
                    trial1,
                    trial1_extraction,
                    trial1_evaluation,
                    trial1_dat,
                    trial1_prep_path,
                ),
                (
                    trial2,
                    trial2_extraction,
                    trial2_evaluation,
                    trial2_dat,
                    trial2_prep_path,
                ),
            )

            for (
                trial,
                extraction,
                evaluation,
                dat_path,
                preparation_path,
            ) in trials:
                measurement = (
                    extraction.measurement
                )

                disposition = (
                    evaluation
                    .decision
                    .disposition
                    .value
                )

                observation = (
                    FemCalibrationObservation(
                        case_id=case_id,
                        case_hash=(
                            resolved.case_hash
                        ),
                        resolution_hash=(
                            resolved.resolution_hash
                        ),
                        geometry_identity=(
                            geometry_identity
                        ),
                        execution_generation_id=(
                            execution_id
                        ),
                        run_id=trial.run_id,
                        trial_index=(
                            trial.trial_index
                        ),
                        trial_source=(
                            trial.source.value
                        ),
                        delta_temperature_c=(
                            trial.delta_temperature_c
                        ),
                        analytical_delta_temperature_c=(
                            analytical_dt
                        ),
                        target_force_n=(
                            resolved
                            .source_case
                            .loading
                            .target_preload_n
                        ),
                        under_head_force_n=(
                            measurement
                            .under_head_force_n
                        ),
                        nut_bearing_force_n=(
                            measurement
                            .nut_bearing_force_n
                        ),
                        member_interface_force_n=(
                            measurement
                            .member_interface_force_n
                        ),
                        extraction_time=(
                            extraction.time
                        ),
                        thread_normal_force_n=abs(
                            extraction
                            .thread_normal_force_n
                        ),
                        decision_disposition=(
                            disposition
                        ),
                        feature=feature,
                        dat_relative_path=(
                            relative(
                                dat_path
                            )
                        ),
                        dat_sha256=(
                            sha256(
                                dat_path
                            )
                        ),
                        preparation_relative_path=(
                            relative(
                                preparation_path
                            )
                        ),
                        preparation_sha256=(
                            sha256(
                                preparation_path
                            )
                        ),
                    )
                )

                _, registration = (
                    register_calibration_observation(
                        store,
                        observation,
                    )
                )

                require(
                    registration
                    == "REGISTERED",
                    (
                        f"{trial.run_id}: unexpected duplicate "
                        "during clean deterministic build."
                    ),
                )

                counts[
                    disposition
                ] += 1

    require(
        len(
            store[
                "observations"
            ]
        )
        == 16,
        "Expected exactly sixteen governed observations.",
    )

    require(
        counts
        == {
            "continue": 8,
            "accept": 8,
        },
        (
            "Unexpected calibration disposition counts: "
            f"{counts!r}"
        ),
    )

    store[
        "summary"
    ] = {
        "observation_count": 16,
        "continue_count": 8,
        "accept_count": 8,
        "case_count": 8,
        "trials_per_case": 2,
    }

    return store


def validate_store(
    store: dict,
) -> None:
    observations = (
        calibration_observations(
            store
        )
    )

    require(
        len(
            observations
        )
        == 16,
        "Persisted store must contain 16 observations.",
    )

    require(
        len(
            {
                item.run_id
                for item in observations
            }
        )
        == 16,
        "Calibration run IDs must be unique.",
    )

    require(
        sum(
            item.decision_disposition
            == "continue"
            for item in observations
        )
        == 8,
        "Expected eight CAL_01 CONTINUE observations.",
    )

    require(
        sum(
            item.decision_disposition
            == "accept"
            for item in observations
        )
        == 8,
        "Expected eight CAL_02 ACCEPT observations.",
    )

    require(
        all(
            item.reusable_for_prediction
            for item in observations
        ),
        "Every retained observation must be prediction-eligible.",
    )

    require(
        all(
            "_interrupted_attempt_"
            not in item.dat_relative_path
            for item in observations
        ),
        "Interrupted attempt leaked into knowledge store.",
    )

    for item in observations:
        dat_path = (
            ROOT
            / item.dat_relative_path
        )

        prep_path = (
            ROOT
            / item.preparation_relative_path
        )

        require(
            dat_path.stat().st_size > 0,
            f"{item.run_id}: zero-byte DAT admitted.",
        )

        require(
            sha256(
                dat_path
            )
            == item.dat_sha256,
            f"{item.run_id}: DAT SHA drift.",
        )

        require(
            sha256(
                prep_path
            )
            == item.preparation_sha256,
            f"{item.run_id}: preparation SHA drift.",
        )

        require(
            math.isfinite(
                item.proportional_correction_factor
            )
            and item.proportional_correction_factor > 0.0,
            f"{item.run_id}: non-physical learned correction.",
        )


def write_mode() -> None:
    store = build_store()

    persist_calibration_observation_store(
        STORE_PATH,
        store,
    )

    persisted = (
        load_calibration_observation_store(
            STORE_PATH
        )
    )

    validate_store(
        persisted
    )

    print()
    print("=" * 110)
    print("CALIBRATION OBSERVATION STORE V1 — WRITTEN")
    print("=" * 110)
    print("Observations       :", len(persisted["observations"]))
    print("Cases              :", persisted["summary"]["case_count"])
    print("CONTINUE / misses  :", persisted["summary"]["continue_count"])
    print("ACCEPT              :", persisted["summary"]["accept_count"])
    print("Store SHA-256       :", sha256(STORE_PATH))
    print("Interrupted attempts: EXCLUDED")
    print("ROM dataset         : UNTOUCHED")
    print("Holdouts            : SEALED")
    print("FEM launched        : NO")
    print("=" * 110)


def audit_mode() -> None:
    persisted = (
        load_calibration_observation_store(
            STORE_PATH
        )
    )

    expected = build_store()

    require(
        persisted == expected,
        (
            "Persisted calibration store differs from "
            "deterministic evidence reconstruction."
        ),
    )

    validate_store(
        persisted
    )

    print()
    print("=" * 110)
    print("CALIBRATION OBSERVATION STORE V1 — AUDIT PASS")
    print("=" * 110)
    print("Deterministic rebuild: PASS")
    print("Observation count    : 16")
    print("CONTINUE / misses    : 8")
    print("ACCEPT                : 8")
    print("DAT SHA replay        : PASS")
    print("Preparation SHA replay: PASS")
    print("Interrupted attempts : EXCLUDED")
    print("ROM dataset           : UNTOUCHED")
    print("Holdouts              : SEALED")
    print("FEM launched          : NO")
    print("=" * 110)


def main() -> None:
    parser = argparse.ArgumentParser()

    group = parser.add_mutually_exclusive_group(
        required=True
    )

    group.add_argument(
        "--write",
        action="store_true",
    )

    group.add_argument(
        "--audit",
        action="store_true",
    )

    args = parser.parse_args()

    if args.write:
        write_mode()
    else:
        audit_mode()


if __name__ == "__main__":
    main()