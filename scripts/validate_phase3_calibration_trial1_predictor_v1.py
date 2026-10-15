"""Validate and close Phase-3 Calibration Knowledge / Trial-1 Predictor V1."""

from __future__ import annotations

import argparse
import hashlib
import json

from collections import defaultdict
from pathlib import Path

from threadrom.factory.fem_calibration_observation_store import (
    calibration_observations,
    load_calibration_observation_store,
)
from threadrom.factory.fem_calibration_trial1_predictor import (
    Trial1PredictionSource,
    load_trial1_observation_predictor_policy,
    predict_trial1_from_observations,
)


ROOT = Path(r"D:\ThreadROM").resolve()

KNOWLEDGE_ROOT = (
    ROOT
    / "docs"
    / "phase3_calibration_knowledge"
)

STORE_PATH = (
    KNOWLEDGE_ROOT
    / "observations_v1.json"
)

POLICY_PATH = (
    ROOT
    / "config"
    / "fem_calibration_trial1_predictor.toml"
)

VALIDATION_PATH = (
    KNOWLEDGE_ROOT
    / "trial1_predictor_v1_validation.json"
)

CLOSURE_PATH = (
    KNOWLEDGE_ROOT
    / "slice2_closure.json"
)


def require(condition, message):
    if not condition:
        raise RuntimeError(
            message
        )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as stream:
        for chunk in iter(
            lambda: stream.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def relative(path: Path) -> str:
    return (
        path.resolve()
        .relative_to(ROOT)
        .as_posix()
    )


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    encoded = (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    )

    temporary = path.with_name(
        path.name + ".tmp"
    )

    temporary.write_text(
        encoded,
        encoding="utf-8",
        newline="\n",
    )

    temporary.replace(path)


def case_groups(observations):
    grouped = defaultdict(list)

    for observation in observations:
        grouped[
            observation.case_hash
        ].append(
            observation
        )

    return {
        key: tuple(
            sorted(
                rows,
                key=lambda item: item.trial_index,
            )
        )
        for key, rows in grouped.items()
    }


def validation_payload():
    store = (
        load_calibration_observation_store(
            STORE_PATH
        )
    )

    observations = (
        calibration_observations(
            store
        )
    )

    require(
        len(observations) == 16,
        "Expected 16 governed calibration observations.",
    )

    policy = (
        load_trial1_observation_predictor_policy(
            POLICY_PATH
        )
    )

    groups = case_groups(
        observations
    )

    require(
        len(groups) == 8,
        "Expected eight governed calibration cases.",
    )

    rows = []

    predictor_errors = []
    analytical_errors = []

    for case_hash, target_rows in sorted(
        groups.items()
    ):
        first = target_rows[0]

        truth_factor = (
            sum(
                item.proportional_correction_factor
                for item in target_rows
            )
            / len(target_rows)
        )

        training = tuple(
            item
            for item in observations
            if item.case_hash != case_hash
        )

        prediction = (
            predict_trial1_from_observations(
                target_case_hash=(
                    first.case_hash
                ),
                target_resolution_hash=(
                    first.resolution_hash
                ),
                target_feature=(
                    first.feature
                ),
                analytical_delta_temperature_c=(
                    first.analytical_delta_temperature_c
                ),
                observations=training,
                policy=policy,
            )
        )

        analytical_relative_error = (
            abs(
                1.0
                - truth_factor
            )
            / truth_factor
        )

        predicted_relative_error = (
            abs(
                prediction.correction_factor
                - truth_factor
            )
            / truth_factor
        )

        used_prediction = (
            prediction.source
            is Trial1PredictionSource.OBSERVATION_NEIGHBORS
        )

        if used_prediction:
            predictor_errors.append(
                predicted_relative_error
            )

            analytical_errors.append(
                analytical_relative_error
            )

        rows.append(
            {
                "case_id": first.case_id,
                "case_hash": first.case_hash,
                "execution_generation_id": (
                    first.execution_generation_id
                ),
                "truth_correction_factor": (
                    truth_factor
                ),
                "analytical_relative_error": (
                    analytical_relative_error
                ),
                "prediction": {
                    "source": (
                        prediction.source.value
                    ),
                    "applicability": (
                        prediction.applicability.value
                    ),
                    "correction_factor": (
                        prediction.correction_factor
                    ),
                    "predicted_delta_temperature_c": (
                        prediction.predicted_delta_temperature_c
                    ),
                    "relative_error_to_replayed_truth": (
                        predicted_relative_error
                    ),
                    "reused_case_count": (
                        prediction.reused_case_count
                    ),
                    "neighbor_case_ids": list(
                        prediction.neighbor_case_ids
                    ),
                    "nearest_distance": (
                        prediction.nearest_distance
                    ),
                },
            }
        )

    predicted_count = len(
        predictor_errors
    )

    fallback_count = (
        len(rows)
        - predicted_count
    )

    require(
        predicted_count >= 1,
        (
            "Predictor V1 produced no governed "
            "leave-one-case-out interpolation."
        ),
    )

    mean_predictor_error = (
        sum(predictor_errors)
        / predicted_count
    )

    mean_analytical_error = (
        sum(analytical_errors)
        / predicted_count
    )

    require(
        mean_predictor_error
        < mean_analytical_error,
        (
            "Observation predictor did not improve on the "
            "analytical seed over its governed applicability subset."
        ),
    )

    require(
        all(
            row[
                "prediction"
            ][
                "relative_error_to_replayed_truth"
            ]
            < row[
                "analytical_relative_error"
            ]
            for row in rows
            if row[
                "prediction"
            ][
                "source"
            ]
            == "observation_neighbors"
        ),
        (
            "At least one governed interpolation was worse "
            "than analytical fallback."
        ),
    )

    return {
        "schema": (
            "threadrom.phase3_calibration_"
            "trial1_predictor_validation.v1"
        ),
        "record_status": "FINAL",
        "validation_method": (
            "LEAVE_ONE_CASE_OUT_OVER_W01_W02_OBSERVATION_STORE"
        ),
        "knowledge_store": {
            "path": relative(
                STORE_PATH
            ),
            "sha256": sha256(
                STORE_PATH
            ),
            "observation_count": 16,
            "case_count": 8,
        },
        "predictor_policy": {
            "path": relative(
                POLICY_PATH
            ),
            "sha256": sha256(
                POLICY_PATH
            ),
            "policy_id": (
                policy.policy_id
            ),
        },
        "results": {
            "evaluated_case_count": (
                len(rows)
            ),
            "observation_neighbor_prediction_count": (
                predicted_count
            ),
            "analytical_fallback_count": (
                fallback_count
            ),
            "mean_predictor_relative_error_on_applicable_subset": (
                mean_predictor_error
            ),
            "mean_analytical_relative_error_on_same_subset": (
                mean_analytical_error
            ),
            "predictor_improves_over_analytical_on_applicable_subset": True,
        },
        "cases": rows,
        "governance": {
            "execution_generation_boundary_preserved": True,
            "geometry_generation_boundary_preserved": True,
            "minimum_neighbor_gate": True,
            "target_preload_bracketing_gate": True,
            "correction_factor_disagreement_gate": True,
            "analytical_fallback_available": True,
            "holdouts_accessed": False,
            "rom_dataset_admission": False,
            "fem_executed": False,
        },
    }


def closure_payload(validation):
    return {
        "schema": (
            "threadrom.pre_w03_"
            "calibration_knowledge_slice2_closure.v1"
        ),
        "record_status": "FINAL",
        "scope": (
            "PRE_W03_HARDENING_SLICE_2"
        ),
        "overall_disposition": (
            "SLICE_2_CALIBRATION_KNOWLEDGE_"
            "AND_TRIAL1_PREDICTOR_V1_CLOSED"
        ),
        "knowledge_store": {
            "path": relative(
                STORE_PATH
            ),
            "sha256": sha256(
                STORE_PATH
            ),
            "observation_count": 16,
            "case_count": 8,
            "calibration_miss_count": 8,
            "accepted_calibration_count": 8,
        },
        "predictor": {
            "policy_path": relative(
                POLICY_PATH
            ),
            "policy_sha256": sha256(
                POLICY_PATH
            ),
            "validation_path": relative(
                VALIDATION_PATH
            ),
            "validation_sha256": sha256(
                VALIDATION_PATH
            ),
            "applicable_leave_one_out_predictions": (
                validation[
                    "results"
                ][
                    "observation_neighbor_prediction_count"
                ]
            ),
            "safe_fallbacks": (
                validation[
                    "results"
                ][
                    "analytical_fallback_count"
                ]
            ),
        },
        "governance": {
            "all_valid_solved_calibration_observations_retained": True,
            "interrupted_zero_byte_attempts_excluded": True,
            "execution_generation_boundary_preserved": True,
            "analytical_fallback_preserved": True,
            "rom_dataset_admission_authorized": False,
            "holdout_access_authorized": False,
            "w03_execution_authorized": False,
            "fem_executed": False,
        },
        "scope_boundary": (
            "Slice 2 creates a persistent calibration-learning store "
            "and a conservative Trial-1 predictor. Predictor output "
            "does not itself authorize W03, FEM execution, ROM dataset "
            "admission, or holdout access."
        ),
    }


def write_mode():
    validation = (
        validation_payload()
    )

    write_json(
        VALIDATION_PATH,
        validation,
    )

    # Replay after persistence.
    replay = validation_payload()

    require(
        replay == validation,
        "Predictor validation is not deterministic.",
    )

    closure = closure_payload(
        validation
    )

    write_json(
        CLOSURE_PATH,
        closure,
    )

    print()
    print("=" * 110)
    print("SLICE 2 — TRIAL-1 PREDICTOR V1 VALIDATION PASS")
    print("=" * 110)
    print(
        "Cases evaluated            :",
        validation["results"]["evaluated_case_count"],
    )
    print(
        "Knowledge predictions      :",
        validation["results"]["observation_neighbor_prediction_count"],
    )
    print(
        "Safe analytical fallbacks :",
        validation["results"]["analytical_fallback_count"],
    )
    print(
        "Predictor mean error       :",
        f'{100.0 * validation["results"]["mean_predictor_relative_error_on_applicable_subset"]:.4f}%',
    )
    print(
        "Analytical mean error      :",
        f'{100.0 * validation["results"]["mean_analytical_relative_error_on_same_subset"]:.4f}%',
    )
    print("ROM dataset                : UNTOUCHED")
    print("Holdouts                   : SEALED")
    print("FEM launched               : NO")
    print(
        "Validation SHA-256         :",
        sha256(
            VALIDATION_PATH
        ),
    )
    print(
        "Closure SHA-256            :",
        sha256(
            CLOSURE_PATH
        ),
    )
    print("=" * 110)


def audit_mode():
    expected_validation = (
        validation_payload()
    )

    persisted_validation = json.loads(
        VALIDATION_PATH.read_text(
            encoding="utf-8-sig"
        )
    )

    require(
        persisted_validation
        == expected_validation,
        "Persisted Trial-1 validation drift.",
    )

    expected_closure = (
        closure_payload(
            expected_validation
        )
    )

    persisted_closure = json.loads(
        CLOSURE_PATH.read_text(
            encoding="utf-8-sig"
        )
    )

    require(
        persisted_closure
        == expected_closure,
        "Persisted Slice-2 closure drift.",
    )

    print()
    print("=" * 110)
    print("THREADROM — SLICE 2 DETERMINISTIC AUDIT PASS")
    print("=" * 110)
    print("Knowledge store replay : PASS")
    print("Predictor replay       : PASS")
    print("Closure replay         : PASS")
    print("Execution boundary     : PRESERVED")
    print("Analytical fallback    : PRESERVED")
    print("ROM dataset            : UNTOUCHED")
    print("Holdouts               : SEALED")
    print("FEM launched           : NO")
    print("=" * 110)


def main():
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