from __future__ import annotations

import argparse
import hashlib
import json
import math
import re

from collections import Counter
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Mapping


from threadrom.factory.rom_dataset_admission import (
    AdmissionDecision,
    AdmissionGateState,
    evaluate_member_shortening_post_target_admission,
)

from threadrom.factory.rom_dataset_applicability import (
    ApplicabilityDecision,
    evaluate_rom_case_applicability,
)

from threadrom.factory.rom_dataset_holdout_protection import (
    HoldoutProtectionDecision,
    evaluate_member_shortening_holdout_protection,
)

from threadrom.factory.rom_dataset_input_resolution import (
    resolve_rom_engineering_inputs,
)


ROOT = Path(__file__).resolve().parents[1]

ATLAS = (
    ROOT
    / "docs"
    / "phase3_fem_atlas"
    / "atlas.json"
)

TARGET = (
    ROOT
    / "docs"
    / "phase3_rom_targets"
    / "member_shortening_v1.target_contract.json"
)

ADMISSION = (
    ROOT
    / "docs"
    / "phase3_rom_dataset_admission"
    / "member_shortening_v1.admission_contract.json"
)

SUPPORTED_DOMAIN = (
    ROOT
    / "docs"
    / "phase3_rom_dataset_admission"
    / "member_shortening_v1.supported_domain.json"
)

PRODUCTION_POLICY = (
    ROOT
    / "config"
    / "phase3_production_doe.toml"
)

EXPECTED_TARGET_SHA = (
    "b8fcf7519e1fe805f5093b9f3a0d01f"
    "53b64ba705b118e4d271677895e47a2bf"
)

EXPECTED_ADMISSION_SHA = (
    "5d7b127345b89327624db560cf03c49fa"
    "40346a01491188540ffc797b44f5c11"
)

EXPECTED_SUPPORTED_DOMAIN_SHA = (
    "8e299508ddff12f92fce4fcae59a2bf0"
    "34eb91dbffcf0b46db3646a6e0ccfbd6"
)


def _member_shortening_applicability(
    engineering_inputs: Mapping[str, Any],
) -> bool | None:
    """Resolve DA10 from the frozen target-specific supported domain."""

    if not SUPPORTED_DOMAIN.is_file():
        raise RuntimeError(
            "Frozen member-shortening supported-domain record is missing."
        )

    actual_sha = hashlib.sha256(
        SUPPORTED_DOMAIN.read_bytes()
    ).hexdigest()

    if actual_sha != EXPECTED_SUPPORTED_DOMAIN_SHA:
        raise RuntimeError(
            "Frozen member-shortening supported-domain SHA mismatch."
        )

    supported_domain = json.loads(
        SUPPORTED_DOMAIN.read_text(
            encoding="utf-8"
        )
    )

    applicability = evaluate_rom_case_applicability(
        engineering_inputs=engineering_inputs,
        supported_domain=supported_domain,
    )

    if (
        applicability.decision
        is ApplicabilityDecision.PASS
    ):
        return True

    if (
        applicability.decision
        is ApplicabilityDecision.REJECTED
    ):
        return False

    if (
        applicability.decision
        is ApplicabilityDecision.DEFERRED
    ):
        return None

    raise RuntimeError(
        "Unsupported DA10 applicability decision."
    )


EXPECTED_PRODUCTION_POLICY_SHA = (
    "43032557cb2abead0118362bcfc6a9b2e"
    "5246a7d363ca83eef5fcf35054befc1"
)

ACCEPTED_WAVE_EVIDENCE_KIND = (
    "DIVERSIFIED_FULL_PHYSICS_ACCEPTED"
)


def require(
    condition: bool,
    message: str,
) -> None:

    if not condition:
        raise RuntimeError(
            message
        )


def sha256(
    path: Path,
) -> str:

    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def load_json(
    path: Path,
):

    return json.loads(
        path.read_text(
            encoding="utf-8-sig"
        )
    )


def get_path(
    payload,
    dotted: str,
):

    current = payload

    for token in dotted.split("."):

        if (
            not isinstance(
                current,
                Mapping,
            )
            or token not in current
        ):
            return False, None

        current = current[
            token
        ]

    return True, current


def first_present(
    payload,
    paths: tuple[str, ...],
):

    for path in paths:

        found, value = get_path(
            payload,
            path,
        )

        if found:
            return value

    return None


def recursive_values(
    payload,
    key: str,
):

    result = []

    if isinstance(
        payload,
        Mapping,
    ):

        for name, value in payload.items():

            if name == key:
                result.append(
                    value
                )

            result.extend(
                recursive_values(
                    value,
                    key,
                )
            )

    elif isinstance(
        payload,
        list,
    ):

        for value in payload:

            result.extend(
                recursive_values(
                    value,
                    key,
                )
            )

    return result


def identity_present(
    payload,
    *,
    key: str,
    expected: str,
    preferred_paths: tuple[str, ...],
) -> bool:

    preferred = first_present(
        payload,
        preferred_paths,
    )

    if preferred is not None:

        return (
            str(
                preferred
            )
            == expected
        )

    return expected in {
        str(
            value
        )
        for value in recursive_values(
            payload,
            key,
        )
        if value is not None
    }


def mapping_from_resolved(
    resolved,
) -> dict[str, Any]:

    if isinstance(
        resolved,
        Mapping,
    ):

        raw = dict(
            resolved
        )

    elif is_dataclass(
        resolved
    ):

        raw = asdict(
            resolved
        )

    else:

        raw = {
            name: getattr(
                resolved,
                name,
            )
            for name in dir(
                resolved
            )
            if (
                not name.startswith(
                    "_"
                )
                and not callable(
                    getattr(
                        resolved,
                        name,
                    )
                )
            )
        }

    for candidate_key in (
        "engineering_inputs",
        "values",
        "canonical_engineering_inputs",
    ):

        candidate = raw.get(
            candidate_key
        )

        if isinstance(
            candidate,
            Mapping,
        ):
            return dict(
                candidate
            )

    return raw


def resolve_engineering_inputs(
    row,
    required_fields: tuple[str, ...],
):

    existing = row.get(
        "engineering_inputs"
    )

    if isinstance(
        existing,
        Mapping,
    ):
        engineering = dict(
            existing
        )
    else:
        engineering = {}

    missing = tuple(
        field
        for field in required_fields
        if (
            field not in engineering
            or engineering[
                field
            ]
            is None
        )
    )

    resolver_required = (
        bool(
            missing
        )
        or engineering.get(
            "configuration_status"
        )
        == "NEW_CAMPAIGN_INPUT_ADAPTER_REQUIRED"
    )

    if resolver_required:

        resolved = (
            resolve_rom_engineering_inputs(
                repo_root=ROOT,
                case_id=row[
                    "case_id"
                ],
                expected_case_hash=row[
                    "case_hash"
                ],
            )
        )

        require(
            resolved.case_id
            == row[
                "case_id"
            ],
            (
                f"{row['case_id']}: governed "
                "engineering-input resolver "
                "case-ID drift."
            ),
        )

        require(
            resolved.case_hash
            == row[
                "case_hash"
            ],
            (
                f"{row['case_id']}: governed "
                "engineering-input resolver "
                "case-hash drift."
            ),
        )

        recovered = (
            mapping_from_resolved(
                resolved
            )
        )

        for key, value in recovered.items():

            if (
                key in engineering
                and engineering[
                    key
                ] is not None
                and engineering[
                    key
                ] != value
            ):
                raise RuntimeError(
                    (
                        f"{row['case_id']}: canonical "
                        f"engineering-input conflict "
                        f"for {key!r}: "
                        f"Atlas={engineering[key]!r}, "
                        f"resolver={value!r}."
                    )
                )

            engineering[
                key
            ] = value

    remaining_missing = tuple(
        field
        for field in required_fields
        if (
            field not in engineering
            or engineering[
                field
            ]
            is None
        )
    )

    require(
        not remaining_missing,
        (
            f"{row['case_id']}: governed "
            "engineering-input resolution "
            f"remains incomplete: "
            f"{list(remaining_missing)!r}"
        ),
    )

    # This is a transient governed admission view.
    # The FEM Atlas remains immutable here.
    engineering[
        "configuration_status"
    ] = "RESOLVED"

    return engineering


def accepted_trial_index(
    *,
    entry,
    payload,
    accepted_run_id: str,
) -> int | None:

    candidates = (
        entry.get(
            "accepted_trial_index"
        ),
        entry.get(
            "trial_index"
        ),
        first_present(
            payload,
            (
                "accepted_trial_index",
                "trial_index",
                "assessment.accepted_trial_index",
                "assessment.trial_index",
                "assessment.trial.index",
            ),
        ),
    )

    for value in candidates:

        if (
            isinstance(
                value,
                int,
            )
            and value >= 1
        ):
            return value

    match = re.search(
        r"_cal_(\d+)",
        accepted_run_id,
    )

    if match:

        return int(
            match.group(
                1
            )
        )

    return None


def main() -> int:

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--wave-id",
        required=True,
    )

    parser.add_argument(
        "--expected-atlas-sha256",
        required=True,
    )

    parser.add_argument(
        "--expected-count",
        required=True,
        type=int,
    )

    args = parser.parse_args()

    wave_id = (
        args.wave_id
        .strip()
        .upper()
    )

    require(
        re.fullmatch(
            r"W\d{2}",
            wave_id,
        )
        is not None,
        (
            "wave-id must have form WNN."
        ),
    )

    require(
        sha256(
            ATLAS
        )
        == args.expected_atlas_sha256,
        "FEM Atlas SHA drift.",
    )

    require(
        sha256(
            TARGET
        )
        == EXPECTED_TARGET_SHA,
        "Frozen target-contract SHA drift.",
    )

    require(
        sha256(
            ADMISSION
        )
        == EXPECTED_ADMISSION_SHA,
        "Frozen admission-contract SHA drift.",
    )

    require(
        sha256(
            PRODUCTION_POLICY
        )
        == EXPECTED_PRODUCTION_POLICY_SHA,
        "Production-DOE policy SHA drift.",
    )

    atlas = load_json(
        ATLAS
    )

    target = load_json(
        TARGET
    )

    admission = load_json(
        ADMISSION
    )

    cases = atlas.get(
        "cases"
    )

    require(
        isinstance(
            cases,
            list,
        ),
        "FEM Atlas cases missing.",
    )

    required_fields_raw = (
        admission[
            "canonical_sample_schema"
        ][
            "engineering_inputs"
        ][
            "minimum_semantic_fields"
        ]
    )

    require(
        isinstance(
            required_fields_raw,
            list,
        )
        and bool(
            required_fields_raw
        ),
        (
            "Admission contract engineering-input "
            "field inventory invalid."
        ),
    )

    required_fields = tuple(
        str(
            field
        )
        for field in required_fields_raw
    )

    source_field = (
        target[
            "target"
        ][
            "source_field"
        ]
    )

    implementation = (
        target[
            "extraction"
        ][
            "implementation"
        ]
    )

    extractor_path = (
        ROOT
        / Path(
            implementation[
                "path"
            ]
        )
    )

    require(
        extractor_path.is_file(),
        "Frozen target extractor missing.",
    )

    require(
        sha256(
            extractor_path
        )
        == implementation[
            "sha256"
        ],
        (
            "Frozen target-extractor "
            "implementation SHA drift."
        ),
    )

    token = (
        f"/{wave_id}/"
    )

    wave_rows = [
        row
        for row in cases
        if (
            isinstance(
                row.get(
                    "primary_evidence_path"
                ),
                str,
            )
            and token
            in (
                "/"
                + row[
                    "primary_evidence_path"
                ]
                .replace(
                    "\\",
                    "/",
                )
                .strip(
                    "/"
                )
                + "/"
            )
        )
    ]

    require(
        len(
            wave_rows
        )
        == args.expected_count,
        (
            f"{wave_id}: expected "
            f"{args.expected_count} Atlas rows; "
            f"found {len(wave_rows)}."
        ),
    )

    print()
    print("=" * 120)
    print(
        "THREADROM - GENERIC GOVERNED-WAVE "
        "ROM-CANDIDATE EVALUATION"
    )
    print("=" * 120)

    print(
        "Wave                     :",
        wave_id,
    )

    print(
        "Accepted FEM Atlas rows  :",
        len(
            wave_rows
        ),
    )

    print(
        "Atlas SHA                :",
        args.expected_atlas_sha256,
    )

    results = []

    for index, row in enumerate(
        sorted(
            wave_rows,
            key=lambda item: item[
                "case_id"
            ],
        ),
        start=1,
    ):

        case_id = row[
            "case_id"
        ]

        case_hash = row[
            "case_hash"
        ]

        require(
            row.get(
                "dataset_partition"
            )
            is None,
            (
                f"{case_id}: dataset partition "
                "already assigned."
            ),
        )

        holdout = (
            evaluate_member_shortening_holdout_protection(
                repo_root=ROOT,
                expected_atlas_sha256=(
                    args.expected_atlas_sha256
                ),
                expected_policy_sha256=(
                    EXPECTED_PRODUCTION_POLICY_SHA
                ),
                case_id=case_id,
                case_hash=case_hash,
            )
        )

        require(
            holdout
            is HoldoutProtectionDecision
            .SOURCE_INSPECTION_ALLOWED,
            (
                f"{case_id}: DA11 denied "
                "target-source inspection."
            ),
        )

        # DA11 PASSED before any target-bearing source is opened.

        evidence_records = row.get(
            "evidence"
        )

        require(
            isinstance(
                evidence_records,
                list,
            )
            and len(
                evidence_records
            )
            == 1,
            (
                f"{case_id}: expected one "
                "accepted FEM evidence record."
            ),
        )

        entry = evidence_records[
            0
        ]

        require(
            entry.get(
                "kind"
            )
            == ACCEPTED_WAVE_EVIDENCE_KIND,
            (
                f"{case_id}: unexpected "
                f"accepted evidence kind "
                f"{entry.get('kind')!r}."
            ),
        )

        evidence_rel = row.get(
            "primary_evidence_path"
        )

        evidence_path = (
            ROOT
            / Path(
                evidence_rel
            )
        )

        require(
            evidence_path.is_file(),
            (
                f"{case_id}: accepted FEM "
                "evidence file missing."
            ),
        )

        require(
            sha256(
                evidence_path
            )
            == entry.get(
                "sha256"
            ),
            (
                f"{case_id}: accepted FEM "
                "evidence SHA drift."
            ),
        )

        payload = load_json(
            evidence_path
        )

        direct_found, direct_value = (
            get_path(
                payload,
                source_field,
            )
        )

        nested_found, nested_value = (
            get_path(
                payload,
                "assessment."
                + source_field,
            )
        )

        require(
            not (
                direct_found
                and nested_found
            ),
            (
                f"{case_id}: ambiguous "
                "target-source path."
            ),
        )

        require(
            direct_found
            or nested_found,
            (
                f"{case_id}: frozen member-shortening "
                "target source missing."
            ),
        )

        target_value = (
            direct_value
            if direct_found
            else nested_value
        )

        target_extraction_valid = (
            isinstance(
                target_value,
                (int, float),
            )
            and not isinstance(
                target_value,
                bool,
            )
            and math.isfinite(
                float(
                    target_value
                )
            )
        )

        case_identity_valid = (
            identity_present(
                payload,
                key="case_id",
                expected=case_id,
                preferred_paths=(
                    "case_id",
                    "case.case_id",
                    "assessment.case_id",
                    "assessment.case.case_id",
                ),
            )
            and identity_present(
                payload,
                key="case_hash",
                expected=case_hash,
                preferred_paths=(
                    "case_hash",
                    "case.case_hash",
                    "assessment.case_hash",
                    "assessment.case.case_hash",
                ),
            )
        )

        accepted_run_id = entry.get(
            "accepted_run_id"
        )

        require(
            isinstance(
                accepted_run_id,
                str,
            )
            and bool(
                accepted_run_id
            ),
            (
                f"{case_id}: Atlas accepted-run "
                "identity missing."
            ),
        )

        run_dir_rel = row.get(
            "primary_run_directory"
        )

        require(
            isinstance(
                run_dir_rel,
                str,
            )
            and bool(
                run_dir_rel
            ),
            (
                f"{case_id}: Atlas accepted-run "
                "directory missing."
            ),
        )

        run_dir = (
            ROOT
            / Path(
                run_dir_rel
            )
        )

        trial_index = (
            accepted_trial_index(
                entry=entry,
                payload=payload,
                accepted_run_id=accepted_run_id,
            )
        )

        execution_identity_valid = (
            run_dir.is_dir()
            and run_dir.name
            == accepted_run_id
            and trial_index
            is not None
        )

        engineering = (
            resolve_engineering_inputs(
                row,
                required_fields,
            )
        )

        resolved_row = dict(
            row
        )

        resolved_row[
            "engineering_inputs"
        ] = engineering

        applicability_inputs = dict(
            row.get(
                "engineering_inputs",
                {},
            )
        )

        applicability_inputs.update(
            engineering
        )

        applicability_passed = (
            _member_shortening_applicability(
                applicability_inputs
            )
        )

        provenance_valid = (
            case_identity_valid
            and execution_identity_valid
            and sha256(
                evidence_path
            )
            == entry[
                "sha256"
            ]
            and sha256(
                extractor_path
            )
            == implementation[
                "sha256"
            ]
        )

        result = (
            evaluate_member_shortening_post_target_admission(
                atlas_case=resolved_row,
                required_engineering_input_fields=(
                    required_fields
                ),
                target_binding_valid=True,
                case_identity_valid=(
                    case_identity_valid
                ),
                execution_identity_valid=(
                    execution_identity_valid
                ),
                physics_acceptance_valid=True,
                target_extraction_valid=(
                    target_extraction_valid
                ),
                target_value_mm=(
                    target_value
                ),
                numerical_certification_passed=None,
                provenance_valid=(
                    provenance_valid
                ),
                applicability_passed=(
                    applicability_passed
                ),
                opaque_holdout_oracle_available=True,
                opaque_holdout_membership_cleared=True,
                partition_unassigned=True,
            )
        )

        results.append(
            result
        )

        print()
        print(
            f"[{index:02d}/{len(wave_rows):02d}] "
            f"{case_id}"
        )

        print(
            "  accepted run      :",
            accepted_run_id,
        )

        print(
            "  trial index       :",
            trial_index,
        )

        print(
            "  target [mm]       :",
            format(
                float(
                    target_value
                ),
                ".15g",
            ),
        )

        print(
            "  admission decision:",
            result.decision.value,
        )

        print(
            "  gates             :",
            ", ".join(
                (
                    f"{gate.gate_id}="
                    f"{gate.state.value}"
                )
                for gate in result.gates
            ),
        )

    decision_counts = Counter(
        result.decision.value
        for result in results
    )

    require(
        decision_counts
        == {
            AdmissionDecision.DEFERRED.value:
            args.expected_count
        },
        (
            f"{wave_id}: expected every current "
            "candidate to be honestly DEFERRED "
            f"only by unresolved later authorities; "
            f"found {dict(decision_counts)}."
        ),
    )

    expected_pass_gates = {
        "DA01_TARGET_BINDING",
        "DA02_CASE_IDENTITY",
        "DA03_EXECUTION_IDENTITY",
        "DA04_ENGINEERING_INPUTS",
        "DA05_PHYSICS_ACCEPTANCE",
        "DA06_TARGET_EXTRACTION",
        "DA07_TARGET_VALUE",
        "DA09_PROVENANCE",
        "DA11_HOLDOUT_PROTECTION",
        "DA12_PARTITION_BOUNDARY",
    }

    for result in results:

        for gate_id in expected_pass_gates:

            require(
                result.gate(
                    gate_id
                ).state
                is AdmissionGateState.PASS,
                (
                    f"{result.case_id}: "
                    f"{gate_id} did not PASS."
                ),
            )

        for gate_id in (
            "DA08_NUMERICAL_CERTIFICATION",
            "DA10_APPLICABILITY",
        ):

            require(
                result.gate(
                    gate_id
                ).state
                is AdmissionGateState.DEFERRED,
                (
                    f"{result.case_id}: "
                    f"{gate_id} must currently "
                    "remain DEFERRED."
                ),
            )

    print()
    print("=" * 120)
    print("GENERIC GOVERNED-WAVE ROM-CANDIDATE SUMMARY")
    print("=" * 120)

    print(
        "Wave                       :",
        wave_id,
    )

    print(
        "Accepted FEM candidates    :",
        len(
            results
        ),
    )

    print(
        "DA01-DA07 except DA08      : PASS"
    )

    print(
        "DA08 numerical cert        : DEFERRED"
    )

    print(
        "DA09 provenance            : PASS"
    )

    print(
        "DA10 applicability         : DEFERRED"
    )

    print(
        "DA11 holdout protection    : PASS"
    )

    print(
        "DA12 partition boundary    : PASS"
    )

    print(
        "Overall                    :",
        dict(
            decision_counts
        ),
    )

    print()
    print(
        "Atlas mutated              : NO"
    )

    print(
        "Dataset created            : NO"
    )

    print(
        "Partitions assigned        : NO"
    )

    print(
        "ROM training               : NO"
    )

    print(
        "Solver launched            : NO"
    )

    print()
    print(
        "DISPOSITION : "
        "GENERIC_GOVERNED_WAVE_ROM_CANDIDATE_PATH_PROVEN"
    )

    print("=" * 120)

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
