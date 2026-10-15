"""Admit one CLOSED governed Phase-3 wave into Calibration Knowledge V1.

Default mode is DRY RUN.

The adapter:
- verifies the immutable governed-wave closure;
- verifies the governed execution contract and owner authorization;
- reconstructs the exact frozen case cohort with the generic wave runner;
- replays all solved calibration trials from durable solver evidence;
- preserves valid misses as well as accepted trials;
- reconstructs the historical calibration-observation identity contract;
- registers observations idempotently using the canonical observation store;
- never launches FEM, accesses holdouts, or admits ROM data.

Use --apply only after a successful reviewed dry run.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from threadrom.factory.fem_calibration_knowledge import (
    FemGeometryRealizationIdentity,
    build_fem_calibration_feature_vector,
)
from threadrom.factory.fem_calibration_observation_store import (
    FemCalibrationObservation,
    calibration_observations,
    load_calibration_observation_store,
    persist_calibration_observation_store,
    register_calibration_observation,
)
from threadrom.factory.geometry_mesh_atlas import (
    load_geometry_mesh_atlas,
)
from threadrom.factory.governed_wave_contract import (
    build_governed_wave_execution_contract,
)
from threadrom.factory.governed_wave_runner import (
    build_governed_wave_runner,
)


ROOT = Path(r"D:\ThreadROM").resolve()

STORE_PATH = (
    ROOT
    / "docs"
    / "phase3_calibration_knowledge"
    / "observations_v1.json"
)

ATLAS_PATH = (
    ROOT
    / "docs"
    / "phase3_geometry_mesh_atlas"
    / "atlas.json"
)

EXPECTED_STORE_SCHEMA = (
    "threadrom.fem_calibration_observation_store.v1"
)

EXPECTED_ATLAS_SCHEMA = (
    "threadrom.geometry_mesh_reuse_atlas.v1"
)

EXPECTED_CLOSURE_SCHEMA = (
    "threadrom.governed_wave_closure.v1"
)

EXPECTED_CLOSURE_DISPOSITION = (
    "GOVERNED_WAVE_FULL_PHYSICS_CLOSED"
)


@dataclass(
    frozen=True,
    slots=True,
)
class _SeedProxy:
    predicted_delta_temperature_c: float


def require(
    condition: bool,
    message: str,
) -> None:
    if not condition:
        raise RuntimeError(message)


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
                8 * 1024 * 1024
            ),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def read_json(
    path: Path,
) -> dict[str, Any]:
    require(
        path.is_file(),
        f"JSON evidence missing: {path}",
    )

    payload = json.loads(
        path.read_text(
            encoding="utf-8-sig"
        )
    )

    require(
        isinstance(payload, dict),
        f"{path}: expected JSON object.",
    )

    return payload


def relative(
    path: Path,
) -> str:
    resolved = path.resolve()

    require(
        resolved.is_relative_to(ROOT),
        f"Path escapes repository root: {resolved}",
    )

    return (
        resolved
        .relative_to(ROOT)
        .as_posix()
    )


def contract_sha256(
    contract,
) -> str:
    value = getattr(
        contract,
        "contract_sha256",
        None,
    )

    require(
        value is not None,
        "Execution contract has no SHA identity.",
    )

    if callable(value):
        value = value()

    require(
        isinstance(value, str)
        and len(value) == 64,
        "Execution-contract SHA is invalid.",
    )

    return value.lower()


def runner_call(
    runner,
    name: str,
    *args,
    **kwargs,
):
    return runner.call(
        name,
        *args,
        **kwargs,
    )


def closure_cases(
    payload: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    require(
        payload.get("schema")
        == EXPECTED_CLOSURE_SCHEMA,
        "Unexpected governed-wave closure schema.",
    )

    require(
        payload.get("record_status")
        == "FINAL",
        "Governed-wave closure is not FINAL.",
    )

    require(
        payload.get("disposition")
        == EXPECTED_CLOSURE_DISPOSITION,
        "Governed wave is not full-physics CLOSED.",
    )

    cases = payload.get(
        "cases"
    )

    require(
        isinstance(cases, list)
        and cases,
        "Governed-wave closure contains no cases.",
    )

    result: dict[
        str,
        dict[str, Any],
    ] = {}

    for item in cases:

        require(
            isinstance(item, dict),
            "Invalid closure case record.",
        )

        case_id = item.get(
            "case_id"
        )

        require(
            isinstance(case_id, str)
            and case_id,
            "Closure case has no case_id.",
        )

        require(
            case_id not in result,
            f"Duplicate closure case: {case_id}",
        )

        result[
            case_id
        ] = item

    return result


def atlas_geometry_identity_candidates(
    *,
    binding: dict[str, Any],
    geometry: dict[str, Any],
) -> dict[
    str,
    str,
]:
    candidates = {
        "binding.geometry_id": (
            binding.get(
                "geometry_id"
            )
        ),
        "binding.geometry_identity_sha256": (
            binding.get(
                "geometry_identity_sha256"
            )
        ),
        "binding.geometry_artifact_sha256": (
            binding.get(
                "geometry_artifact_sha256"
            )
        ),
        "geometry.geometry_id": (
            geometry.get(
                "geometry_id"
            )
        ),
        "geometry.identity_sha256": (
            geometry.get(
                "identity_sha256"
            )
        ),
        "geometry.artifact_sha256": (
            geometry.get(
                "artifact_sha256"
            )
        ),
        "geometry.canonical_artifact_path": (
            geometry.get(
                "canonical_artifact_path"
            )
        ),
    }

    return {
        name: value
        for name, value in candidates.items()
        if (
            isinstance(value, str)
            and value
        )
    }


def infer_geometry_realization_contract(
    *,
    store: dict[str, Any],
    atlas: dict[str, Any],
) -> tuple[
    tuple[str, ...],
    Callable[
        [
            dict[str, Any],
            dict[str, Any],
        ],
        str,
    ],
]:
    observations = (
        calibration_observations(
            store
        )
    )

    require(
        observations,
        "Existing calibration knowledge is empty.",
    )

    bindings = atlas.get(
        "case_bindings"
    )
    geometries = atlas.get(
        "geometries"
    )

    require(
        isinstance(bindings, dict),
        "Atlas case_bindings missing.",
    )

    require(
        isinstance(geometries, dict),
        "Atlas geometries missing.",
    )

    matching_labels: set[str] | None = None

    generation_ids: set[str] = set()

    for observation in observations:

        binding = bindings.get(
            observation.case_id
        )

        require(
            isinstance(binding, dict),
            (
                f"{observation.case_id}: existing calibration "
                "observation has no Geometry Atlas binding."
            ),
        )

        geometry_id = binding.get(
            "geometry_id"
        )

        geometry = geometries.get(
            geometry_id
        )

        require(
            isinstance(geometry, dict),
            (
                f"{observation.case_id}: existing calibration "
                "observation geometry asset missing."
            ),
        )

        generation_id = geometry.get(
            "generation_id"
        )

        require(
            isinstance(generation_id, str)
            and generation_id,
            (
                f"{observation.case_id}: Geometry Atlas "
                "generation identity missing."
            ),
        )

        require(
            observation
            .geometry_identity
            .generation_id
            == generation_id,
            (
                f"{observation.case_id}: historical calibration "
                "geometry-generation identity disagrees "
                "with Geometry Atlas."
            ),
        )

        generation_ids.add(
            generation_id
        )

        candidates = (
            atlas_geometry_identity_candidates(
                binding=binding,
                geometry=geometry,
            )
        )

        matches = {
            label
            for label, value
            in candidates.items()
            if value
            == observation
            .geometry_identity
            .realization_id
        }

        require(
            matches,
            (
                f"{observation.case_id}: unable to map "
                "historical calibration geometry-realization "
                "identity back to Geometry Atlas."
            ),
        )

        if matching_labels is None:
            matching_labels = matches
        else:
            matching_labels.intersection_update(
                matches
            )

    require(
        matching_labels is not None
        and matching_labels,
        (
            "No single Geometry Atlas identity field "
            "reproduces all historical calibration "
            "realization identities."
        ),
    )

    require(
        len(generation_ids) == 1,
        (
            "Historical calibration observations use "
            "multiple geometry-generation contracts."
        ),
    )

    ordered = tuple(
        sorted(
            matching_labels
        )
    )

    selected = ordered[0]

    def resolve(
        binding: dict[str, Any],
        geometry: dict[str, Any],
    ) -> str:
        candidates = (
            atlas_geometry_identity_candidates(
                binding=binding,
                geometry=geometry,
            )
        )

        require(
            selected in candidates,
            (
                "Selected historical geometry-realization "
                f"field is absent: {selected}"
            ),
        )

        expected = candidates[
            selected
        ]

        for label in ordered:

            require(
                candidates.get(
                    label
                )
                == expected,
                (
                    "Historically equivalent geometry-realization "
                    "fields diverged for a new case. "
                    f"{selected}={expected!r}; "
                    f"{label}={candidates.get(label)!r}"
                ),
            )

        return expected

    return (
        ordered,
        resolve,
    )


def observation_counts(
    store: dict[str, Any],
) -> dict[str, int]:
    observations = (
        calibration_observations(
            store
        )
    )

    return {
        "observation_count": len(
            observations
        ),
        "accept_count": sum(
            item.decision_disposition
            == "accept"
            for item in observations
        ),
        "continue_count": sum(
            item.decision_disposition
            == "continue"
            for item in observations
        ),
        "case_count": len(
            {
                item.case_hash
                for item in observations
            }
        ),
    }


def update_metadata(
    *,
    store: dict[str, Any],
    wave_id: str,
    execution_generation_id: str,
    preparation_path: Path,
    preparation_sha256: str,
    closure_path: Path,
    closure_sha256: str,
    atlas_sha256: str,
) -> None:
    boundaries = store.setdefault(
        "execution_generation_boundaries",
        {},
    )

    require(
        isinstance(boundaries, dict),
        "Execution-generation boundaries are invalid.",
    )

    wave_token = wave_id.rsplit("-", 1)[-1]

    require(
        wave_token.startswith("W")
        and wave_token[1:].isdigit(),
        "Invalid governed wave token.",
    )

    existing_boundary = boundaries.get(
        wave_token
    )

    if existing_boundary is None:
        boundaries[
            wave_token
        ] = execution_generation_id
    else:
        require(
            existing_boundary
            == execution_generation_id,
            "Governed-wave execution-generation boundary conflict.",
        )

    evidence = store.setdefault(
        "source_evidence",
        {},
    )

    require(
        isinstance(evidence, dict),
        "Calibration source_evidence is invalid.",
    )

    wave_evidence = {
        "preparation_index_path": (
            relative(
                preparation_path
            )
        ),
        "preparation_index_sha256": (
            preparation_sha256
        ),
        "wave_closure_path": (
            relative(
                closure_path
            )
        ),
        "wave_closure_sha256": (
            closure_sha256
        ),
        "geometry_mesh_atlas_path": (
            relative(
                ATLAS_PATH
            )
        ),
        "geometry_mesh_atlas_sha256": (
            atlas_sha256
        ),
    }

    existing = evidence.get(
        wave_id
    )

    if existing is None:
        evidence[
            wave_id
        ] = wave_evidence
    else:
        require(
            existing == wave_evidence,
            (
                f"{wave_id}: conflicting calibration "
                "source-evidence binding."
            ),
        )

    counts = observation_counts(
        store
    )

    observations = (
        calibration_observations(
            store
        )
    )

    per_case: dict[
        str,
        int,
    ] = {}

    for item in observations:
        per_case[
            item.case_hash
        ] = (
            per_case.get(
                item.case_hash,
                0,
            )
            + 1
        )

    trial_counts = sorted(
        set(
            per_case.values()
        )
    )

    store[
        "summary"
    ] = {
        "observation_count": counts[
            "observation_count"
        ],
        "continue_count": counts[
            "continue_count"
        ],
        "accept_count": counts[
            "accept_count"
        ],
        "case_count": counts[
            "case_count"
        ],
        "trials_per_case": (
            trial_counts[0]
            if len(trial_counts) == 1
            else None
        ),
    }


def build_plan(
    *,
    wave_id: str,
    owner_authorization_sha256: str,
    preparation_index_path: Path,
    preparation_index_sha256: str,
    closure_path: Path,
    closure_sha256: str,
    expected_contract_sha256: str,
    expected_registry_sha256: str,
    expected_atlas_sha256: str,
    expected_store_sha256: str,
    expected_case_count: int,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
]:
    require(
        sha256(
            STORE_PATH
        )
        == expected_store_sha256,
        "Calibration observation store SHA drift.",
    )

    require(
        sha256(
            ATLAS_PATH
        )
        == expected_atlas_sha256,
        "Geometry/Mesh Atlas SHA drift.",
    )

    require(
        sha256(
            preparation_index_path
        )
        == preparation_index_sha256,
        "Governed-wave preparation-index SHA drift.",
    )

    require(
        sha256(
            closure_path
        )
        == closure_sha256,
        "Governed-wave closure SHA drift.",
    )

    closure = read_json(
        closure_path
    )

    require(
        closure.get(
            "wave_id"
        )
        == wave_id,
        "Closure wave identity drift.",
    )

    closed = closure_cases(
        closure
    )

    require(
        len(closed)
        == expected_case_count,
        "Closure case count drift.",
    )

    contract = (
        build_governed_wave_execution_contract(
            campaign_id="TRM-DDOE-001",
            wave_token=wave_id.rsplit("-", 1)[-1],
            expected_owner_authorization_sha256=(
                owner_authorization_sha256
            ),
            expected_preparation_index_sha256=(
                preparation_index_sha256
            ),
            authorized_case_count=(
                expected_case_count
            ),
            maximum_concurrent_solver_slots=4,
            maximum_trial_index=6,
        )
    )

    actual_contract_sha = (
        contract_sha256(
            contract
        )
    )

    require(
        actual_contract_sha
        == expected_contract_sha256,
        "Governed-wave execution-contract SHA drift.",
    )

    registry_path = (
        ROOT
        / Path(
            contract
            .factory_database_path
            .as_posix()
        )
    ).resolve()

    registry_before = sha256(
        registry_path
    )

    require(
        registry_before
        == expected_registry_sha256,
        "Governed-wave terminal factory-registry SHA drift.",
    )

    runner = (
        build_governed_wave_runner(
            repository_root=ROOT,
            contract=contract,
        )
    )

    runner_call(
        runner,
        "verify_owner_authorization",
    )

    contexts = (
        runner.build_case_contexts()
    )

    require(
        len(contexts)
        == expected_case_count,
        "Authorized governed-wave context count drift.",
    )

    context_ids = {
        context[
            "case_id"
        ]
        for context in contexts
    }

    require(
        context_ids
        == set(
            closed
        ),
        "Authorized governed-wave cohort differs from CLOSED cohort.",
    )

    store = (
        load_calibration_observation_store(
            STORE_PATH
        )
    )

    require(
        store.get(
            "schema"
        )
        == EXPECTED_STORE_SCHEMA,
        "Unexpected calibration-store schema.",
    )

    atlas = (
        load_geometry_mesh_atlas(
            ATLAS_PATH
        )
    )

    require(
        atlas.get(
            "schema"
        )
        == EXPECTED_ATLAS_SCHEMA,
        "Unexpected Geometry/Mesh Atlas schema.",
    )

    before = observation_counts(
        store
    )

    valid_before_states = (
        {
            "observation_count": 16,
            "accept_count": 8,
            "continue_count": 8,
            "case_count": 8,
        },
        {
            "observation_count": 22,
            "accept_count": 12,
            "continue_count": 10,
            "case_count": 12,
        },
    )


    (
        realization_fields,
        resolve_realization_id,
    ) = (
        infer_geometry_realization_contract(
            store=store,
            atlas=atlas,
        )
    )

    planned = copy.deepcopy(
        store
    )

    bindings = atlas[
        "case_bindings"
    ]
    geometries = atlas[
        "geometries"
    ]

    registration_statuses: dict[
        str,
        str,
    ] = {}

    histories: dict[
        str,
        int,
    ] = {}

    execution_ids: set[
        str
    ] = set()

    total_realized_trials = 0

    for context in sorted(
        contexts,
        key=lambda item: item[
            "case_id"
        ],
    ):
        case_id = context[
            "case_id"
        ]

        case_hash = context[
            "case_hash"
        ]

        case_run_id = context[
            "case_run_id"
        ]

        final = closed[
            case_id
        ]

        require(
            final.get(
                "case_hash"
            )
            == case_hash,
            f"{case_id}: closure case-hash drift.",
        )

        require(
            final.get(
                "case_run_id"
            )
            == case_run_id,
            f"{case_id}: closure case-run drift.",
        )

        binding = bindings.get(
            case_id
        )

        require(
            isinstance(binding, dict),
            f"{case_id}: Governed-wave Geometry Atlas binding missing.",
        )

        require(
            binding.get(
                "case_hash"
            )
            == case_hash,
            f"{case_id}: Governed-wave Atlas case-hash drift.",
        )

        geometry_id = binding.get(
            "geometry_id"
        )

        geometry = geometries.get(
            geometry_id
        )

        require(
            isinstance(geometry, dict),
            f"{case_id}: Governed-wave geometry asset missing.",
        )

        generation_id = geometry.get(
            "generation_id"
        )

        require(
            isinstance(generation_id, str)
            and generation_id,
            f"{case_id}: geometry generation identity missing.",
        )

        realization_id = (
            resolve_realization_id(
                binding,
                geometry,
            )
        )

        geometry_identity = (
            FemGeometryRealizationIdentity(
                generation_id=(
                    generation_id
                ),
                realization_id=(
                    realization_id
                ),
            )
        )

        preparation = context[
            "preparation"
        ]

        analytical_seed = (
            preparation.get(
                "analytical_seed"
            )
        )

        require(
            isinstance(
                analytical_seed,
                dict,
            ),
            f"{case_id}: analytical seed missing.",
        )

        analytical_dt = float(
            analytical_seed[
                "predicted_delta_temperature_c"
            ]
        )

        execution_id = preparation.get(
            "execution_generation_id"
        )

        require(
            isinstance(execution_id, str)
            and execution_id,
            f"{case_id}: execution-generation identity missing.",
        )

        execution_ids.add(
            execution_id
        )

        feature = (
            build_fem_calibration_feature_vector(
                context[
                    "resolved"
                ],
                _SeedProxy(
                    predicted_delta_temperature_c=(
                        analytical_dt
                    ),
                ),
                geometry_identity,
                execution_id,
            )
        )

        state = runner_call(
            runner,
            "recover_calibration_state",
            context,
        )

        require(
            isinstance(state, dict),
            f"{case_id}: invalid recovered calibration state.",
        )

        require(
            state.get(
                "status"
            )
            == "CALIBRATION_ACCEPTED",
            (
                f"{case_id}: Governed-wave calibration history "
                "does not terminate in ACCEPT."
            ),
        )

        accepted_trial = state.get(
            "accepted_trial"
        )

        require(
            accepted_trial is not None,
            f"{case_id}: accepted trial missing.",
        )

        require(
            accepted_trial.run_id
            == final.get(
                "run_id"
            ),
            f"{case_id}: accepted run differs from wave closure.",
        )

        require(
            accepted_trial.trial_index
            == final.get(
                "trial_index"
            ),
            f"{case_id}: accepted CAL index differs from wave closure.",
        )

        history = state.get(
            "history"
        )

        require(
            isinstance(history, list)
            and history,
            f"{case_id}: recovered calibration history is empty.",
        )

        histories[
            case_id
        ] = len(
            history
        )

        total_realized_trials += len(
            history
        )

        for item in history:

            require(
                isinstance(item, dict),
                f"{case_id}: invalid calibration history item.",
            )

            trial = item[
                "trial"
            ]
            completed = item[
                "completed"
            ]
            evaluation = item[
                "evaluation"
            ]

            extraction = completed[
                "extraction"
            ]
            measurement = completed[
                "measurement"
            ]

            dat_path = Path(
                completed[
                    "dat_path"
                ]
            ).resolve()

            dat_sha = completed[
                "dat_sha256"
            ]

            require(
                sha256(
                    dat_path
                )
                == dat_sha,
                f"{trial.run_id}: DAT SHA drift before observation admission.",
            )

            if trial.trial_index == 1:
                preparation_path = Path(
                    context[
                        "preparation_path"
                    ]
                ).resolve()
            else:
                preparation_path = Path(
                    runner_call(
                        runner,
                        "preparation_record_path",
                        context,
                        trial,
                    )
                ).resolve()

            require(
                preparation_path.is_file(),
                (
                    f"{trial.run_id}: governed "
                    "preparation record missing."
                ),
            )

            preparation_sha = sha256(
                preparation_path
            )

            disposition = (
                evaluation
                .decision
                .disposition
                .value
            )

            require(
                disposition
                in {
                    "continue",
                    "accept",
                },
                (
                    f"{trial.run_id}: unsupported "
                    f"calibration disposition {disposition!r}."
                ),
            )

            observation = (
                FemCalibrationObservation(
                    case_id=case_id,
                    case_hash=(
                        context[
                            "resolved"
                        ]
                        .case_hash
                    ),
                    resolution_hash=(
                        context[
                            "resolved"
                        ]
                        .resolution_hash
                    ),
                    geometry_identity=(
                        geometry_identity
                    ),
                    execution_generation_id=(
                        execution_id
                    ),
                    run_id=(
                        trial.run_id
                    ),
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
                    target_force_n=float(
                        context[
                            "resolved"
                        ]
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
                        dat_sha
                    ),
                    preparation_relative_path=(
                        relative(
                            preparation_path
                        )
                    ),
                    preparation_sha256=(
                        preparation_sha
                    ),
                )
            )

            (
                identifier,
                registration,
            ) = (
                register_calibration_observation(
                    planned,
                    observation,
                )
            )

            registration_statuses[
                trial.run_id
            ] = registration

            print(
                f"{case_id} | "
                f"CAL_{trial.trial_index:02d} | "
                f"{trial.run_id} | "
                f"{disposition.upper()} | "
                f"{registration} | "
                f"{identifier}"
            )

    require(
        len(histories)
        == expected_case_count,
        (
            "Recovered governed-wave calibration-history "
            "case count drift."
        ),
    )

    require(
        all(
            type(count) is int
            and 1
            <= count
            <= contract.maximum_trial_index
            for count in histories.values()
        ),
        (
            "Recovered governed-wave calibration-history "
            f"shape is invalid: {histories}"
        ),
    )

    require(
        total_realized_trials
        == sum(
            histories.values()
        ),
        (
            "Recovered governed-wave calibration-trial "
            "count drift."
        ),
    )

    require(
        len(execution_ids) == 1,
        "Governed-wave calibration observations span multiple execution generations.",
    )

    execution_id = next(
        iter(
            execution_ids
        )
    )

    update_metadata(
        store=planned,
        wave_id=wave_id,
        execution_generation_id=(
            execution_id
        ),
        preparation_path=(
            preparation_index_path
        ),
        preparation_sha256=(
            preparation_index_sha256
        ),
        closure_path=closure_path,
        closure_sha256=(
            closure_sha256
        ),
        atlas_sha256=(
            expected_atlas_sha256
        ),
    )

    after = observation_counts(
        planned
    )

    registered_count = sum(
        1
        for status
        in registration_statuses.values()
        if status == "REGISTERED"
    )

    require(
        after[
            "observation_count"
        ]
        == before[
            "observation_count"
        ]
        + registered_count,
        (
            "Planned governed-wave calibration observation "
            "count drift."
        ),
    )

    require(
        after[
            "accept_count"
        ]
        >= before[
            "accept_count"
        ],
        "Calibration ACCEPT count regressed.",
    )

    require(
        after[
            "continue_count"
        ]
        >= before[
            "continue_count"
        ],
        "Calibration CONTINUE count regressed.",
    )

    require(
        after[
            "accept_count"
        ]
        + after[
            "continue_count"
        ]
        == after[
            "observation_count"
        ],
        (
            "Calibration disposition counts do not equal "
            "observation count."
        ),
    )

    require(
        before[
            "case_count"
        ]
        <= after[
            "case_count"
        ]
        <= before[
            "case_count"
        ]
        + expected_case_count,
        (
            "Governed-wave calibration case-count delta "
            "is invalid."
        ),
    )

    require(
        set(
            registration_statuses.values()
        )
        <= {
            "REGISTERED",
            "REUSED",
        },
        "Unexpected calibration-observation registration disposition.",
    )

    registry_after = sha256(
        registry_path
    )

    require(
        registry_after
        == registry_before
        == expected_registry_sha256,
        "Calibration planning mutated governed-wave factory registry.",
    )

    report = {
        "before": before,
        "after": after,
        "histories": histories,
        "registration_statuses": (
            registration_statuses
        ),
        "geometry_realization_fields": (
            realization_fields
        ),
        "execution_generation_id": (
            execution_id
        ),
        "registry_sha256": (
            registry_after
        ),
        "contract_sha256": (
            actual_contract_sha
        ),
        "realized_trial_count": (
            total_realized_trials
        ),
    }

    return (
        planned,
        report,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__
    )

    parser.add_argument(
        "--wave-id",
        required=True,
    )

    parser.add_argument(
        "--owner-authorization-sha",
        required=True,
    )

    parser.add_argument(
        "--preparation-index",
        required=True,
    )

    parser.add_argument(
        "--expected-preparation-sha",
        required=True,
    )

    parser.add_argument(
        "--wave-closure",
        required=True,
    )

    parser.add_argument(
        "--expected-closure-sha",
        required=True,
    )

    parser.add_argument(
        "--expected-contract-sha",
        required=True,
    )

    parser.add_argument(
        "--expected-registry-sha",
        required=True,
    )

    parser.add_argument(
        "--expected-atlas-sha",
        required=True,
    )

    parser.add_argument(
        "--expected-store-sha",
        required=True,
    )

    parser.add_argument(
        "--expected-case-count",
        type=int,
        default=4,
    )

    parser.add_argument(
        "--expected-new-observations",
        type=int,
        default=None,
    )

    parser.add_argument(
        "--apply",
        action="store_true",
    )

    args = parser.parse_args()

    preparation_index_path = (
        ROOT
        / Path(
            args.preparation_index
        )
    ).resolve()

    closure_path = (
        ROOT
        / Path(
            args.wave_closure
        )
    ).resolve()

    store_before_sha = sha256(
        STORE_PATH
    )

    planned, report = build_plan(
        wave_id=args.wave_id,
        owner_authorization_sha256=(
            args.owner_authorization_sha
        ),
        preparation_index_path=(
            preparation_index_path
        ),
        preparation_index_sha256=(
            args.expected_preparation_sha.lower()
        ),
        closure_path=closure_path,
        closure_sha256=(
            args.expected_closure_sha.lower()
        ),
        expected_contract_sha256=(
            args.expected_contract_sha.lower()
        ),
        expected_registry_sha256=(
            args.expected_registry_sha.lower()
        ),
        expected_atlas_sha256=(
            args.expected_atlas_sha.lower()
        ),
        expected_store_sha256=(
            args.expected_store_sha.lower()
        ),
        expected_case_count=(
            args.expected_case_count
        ),
    )

    registered_count = sum(
        value == "REGISTERED"
        for value in report[
            "registration_statuses"
        ].values()
    )

    reused_count = sum(
        value == "REUSED"
        for value in report[
            "registration_statuses"
        ].values()
    )

    if (
        args.expected_new_observations
        is not None
    ):
        require(
            registered_count
            == args.expected_new_observations,
            (
                "Unexpected number of new calibration "
                "observations. "
                f"expected={args.expected_new_observations} "
                f"actual={registered_count}"
            ),
        )

    print()
    print("=" * 108)
    print(
        "THREADROM - GOVERNED WAVE "
        "CALIBRATION-KNOWLEDGE ADMISSION V1"
    )
    print("=" * 108)

    print(
        "Mode                       :",
        (
            "APPLY"
            if args.apply
            else "DRY_RUN"
        ),
    )

    print(
        "Wave                       :",
        args.wave_id,
    )

    print(
        "Execution contract SHA     :",
        report[
            "contract_sha256"
        ],
    )

    print(
        "Factory registry SHA       :",
        report[
            "registry_sha256"
        ],
    )

    print(
        "Store before SHA           :",
        store_before_sha,
    )

    print(
        "Geometry identity field(s) :",
        ", ".join(
            report[
                "geometry_realization_fields"
            ]
        ),
    )

    print(
        "Execution generation       :",
        report[
            "execution_generation_id"
        ],
    )

    print()
    print(
        "Before                     :",
        report[
            "before"
        ],
    )

    print(
        "Planned after              :",
        report[
            "after"
        ],
    )

    print(
        "Recovered governed trials  :",
        report[
            "realized_trial_count"
        ],
    )

    print(
        "New observations           :",
        registered_count,
    )

    print(
        "Reused observations        :",
        reused_count,
    )

    print()
    print("Per-case realized histories:")

    for case_id in sorted(
        report[
            "histories"
        ]
    ):
        print(
            " ",
            case_id,
            "->",
            report[
                "histories"
            ][
                case_id
            ],
            "trial(s)",
        )

    if not args.apply:

        store_after_sha = sha256(
            STORE_PATH
        )

        require(
            store_after_sha
            == store_before_sha,
            "DRY RUN mutated the calibration store.",
        )

        print()
        print(
            "Store after SHA            :",
            store_after_sha,
        )

        print(
            "Store persisted            : NO"
        )

        print(
            "Solver launched            : NO"
        )

        print(
            "Holdouts accessed          : NO"
        )

        print(
            "ROM dataset admission      : NO"
        )

        print(
            "Disposition                : "
            "VALIDATED_CALIBRATION_ADMISSION_PLAN_ONLY"
        )

        print("=" * 108)

        return 0

    persist_calibration_observation_store(
        STORE_PATH,
        planned,
    )

    recovered = (
        load_calibration_observation_store(
            STORE_PATH
        )
    )

    require(
        recovered == planned,
        (
            "Persisted calibration knowledge "
            "differs from planned state."
        ),
    )

    persisted_counts = (
        observation_counts(
            recovered
        )
    )

    require(
        persisted_counts
        == report[
            "after"
        ],
        "Persisted calibration counts drift.",
    )

    print()
    print(
        "Store after SHA            :",
        sha256(
            STORE_PATH
        ),
    )

    print(
        "Store persisted            : YES"
    )

    print(
        "Disposition                : "
        "GOVERNED_WAVE_CALIBRATION_KNOWLEDGE_ADMITTED"
    )

    print("=" * 108)

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )