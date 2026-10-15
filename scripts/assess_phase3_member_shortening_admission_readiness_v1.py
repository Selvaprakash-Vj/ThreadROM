from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

from threadrom.factory.rom_dataset_admission import (
    AdmissionDecision,
    AdmissionGateState,
    evaluate_member_shortening_pre_target_readiness,
)

from threadrom.factory.rom_dataset_input_resolution import (
    resolve_rom_engineering_inputs,
)

from threadrom.factory.rom_dataset_holdout_protection import (
    HoldoutProtectionDecision,
    evaluate_member_shortening_holdout_protection,
)




ROOT = Path(r"D:\ThreadROM")

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


EXPECTED_ATLAS_SHA = (
    "172bfe7e226519e876b4ff2f75fa3d4133573b48646cb4b941be39890f0b240b"
)

EXPECTED_TARGET_SHA = (
    "b8fcf7519e1fe805f5093b9f3a0d01f53b64ba705b118e4d271677895e47a2bf"
)

EXPECTED_ADMISSION_SHA = (
    "5d7b127345b89327624db560cf03c49fa40346a01491188540ffc797b44f5c11"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def load(path: Path):
    return json.loads(
        path.read_text(
            encoding="utf-8-sig"
        )
    )


require(
    sha256(ATLAS) == EXPECTED_ATLAS_SHA,
    "39/39 FEM Atlas SHA drift.",
)

require(
    sha256(TARGET) == EXPECTED_TARGET_SHA,
    "Frozen target-contract SHA drift.",
)

require(
    sha256(ADMISSION) == EXPECTED_ADMISSION_SHA,
    "Frozen admission-contract SHA drift.",
)


atlas = load(ATLAS)
target = load(TARGET)
admission = load(ADMISSION)


require(
    target.get("contract_id")
    == "TRM-ROM-TARGET-MEMBER-SHORTENING-V1",
    "Unexpected member-shortening target identity.",
)

require(
    admission.get("contract_id")
    == "TRM-ROM-DATASET-ADMISSION-MEMBER-SHORTENING-V1",
    "Unexpected member-shortening admission-contract identity.",
)

require(
    admission.get(
        "target_binding",
        {},
    ).get("sha256")
    == EXPECTED_TARGET_SHA,
    "Admission/target binding drift.",
)


required_fields = (
    admission[
        "canonical_sample_schema"
    ][
        "engineering_inputs"
    ][
        "minimum_semantic_fields"
    ]
)

require(
    isinstance(required_fields, list)
    and required_fields,
    "Canonical engineering-input field contract missing.",
)


cases = atlas.get("cases")

require(
    isinstance(cases, list)
    and len(cases) == 39,
    "Expected exactly 39 reconciled FEM cases.",
)



# Governed DA04 engineering-input resolution.
# The canonical FEM Atlas remains immutable. For each candidate, only a
# transaction-local copy is enriched before pre-target readiness evaluation.
results = []

for case in cases:
    _resolved_atlas_case = dict(case)

    _atlas_engineering_inputs = (
        _resolved_atlas_case.get(
            "engineering_inputs"
        )
    )

    if (
        isinstance(
            _atlas_engineering_inputs,
            dict,
        )
        and _atlas_engineering_inputs.get(
            "configuration_status"
        )
        == "NEW_CAMPAIGN_INPUT_ADAPTER_REQUIRED"
    ):
        _input_resolution = (
            resolve_rom_engineering_inputs(
                repo_root=ROOT,
                case_id=(
                    _resolved_atlas_case[
                        "case_id"
                    ]
                ),
                expected_case_hash=(
                    _resolved_atlas_case[
                        "case_hash"
                    ]
                ),
            )
        )

        _resolved_engineering_inputs = dict(
            _atlas_engineering_inputs
        )

        _resolved_engineering_inputs.update(
            _input_resolution.engineering_inputs
        )

        _resolved_engineering_inputs[
            "configuration_status"
        ] = (
            "GOVERNED_ROM_INPUT_ADAPTER_RESOLVED"
        )

        _resolved_engineering_inputs[
            "configuration_sources"
        ] = [
            {
                "authority":
                    _input_resolution.source_kind,

                "relative_path":
                    _input_resolution.source_relative_path,

                "sha256":
                    _input_resolution.source_sha256,

                "policy_sha256":
                    _input_resolution.policy_sha256,

                "case_hash":
                    _input_resolution.case_hash,
            }
        ]

        _resolved_engineering_inputs[
            "normalized_coordinates"
        ] = list(
            _input_resolution
            .normalized_coordinates
        )

        _resolved_atlas_case[
            "engineering_inputs"
        ] = _resolved_engineering_inputs

        # DA11: opaque sealed-holdout protection must clear
    # before any future target-bearing source inspection.
    _holdout_decision = (
        evaluate_member_shortening_holdout_protection(
            repo_root=ROOT,
            expected_atlas_sha256=(
                "172bfe7e226519e876b4ff2f75fa3d4133573b48646cb4b941be39890f0b240b"
            ),
            expected_policy_sha256=(
                "43032557cb2abead0118362bcfc6a9b2e"
                "5246a7d363ca83eef5fcf35054befc1"
            ),
            case_id=_resolved_atlas_case[
                "case_id"
            ],
            case_hash=_resolved_atlas_case[
                "case_hash"
            ],
        )
    )

    require(
        _holdout_decision
        is HoldoutProtectionDecision.SOURCE_INSPECTION_ALLOWED,
        (
            f"{_resolved_atlas_case['case_id']}: "
            "DA11 denied target-source inspection."
        ),
    )

    results.append(
            evaluate_member_shortening_pre_target_readiness(
                atlas_case=_resolved_atlas_case,
                required_engineering_input_fields=(
                    required_fields
                ),
                target_binding_valid=True,

                # Explicit current governance state.
                numerical_certification_authority_available=False,
                case_applicability_resolver_available=False,
                opaque_holdout_oracle_available=True,
                opaque_holdout_membership_cleared=True,
            )
        )

decision_counts = Counter(
    result.decision.value
    for result in results
)

da04_counts = Counter(
    result.gate(
        "DA04_ENGINEERING_INPUTS"
    ).state.value
    for result in results
)

da08_counts = Counter(
    result.gate(
        "DA08_NUMERICAL_CERTIFICATION"
    ).state.value
    for result in results
)

da10_counts = Counter(
    result.gate(
        "DA10_APPLICABILITY"
    ).state.value
    for result in results
)

da11_counts = Counter(
    result.gate(
        "DA11_HOLDOUT_PROTECTION"
    ).state.value
    for result in results
)

da12_counts = Counter(
    result.gate(
        "DA12_PARTITION_BOUNDARY"
    ).state.value
    for result in results
)


require(
    decision_counts.get(
        AdmissionDecision.ADMITTED.value,
        0,
    )
    == 0,
    "Pre-target readiness unexpectedly admitted a sample.",
)

require(
    da04_counts.get(
        AdmissionGateState.DEFERRED.value,
        0,
    )
    == 0,
    (
        "Expected zero DA04-deferred cases after governed engineering-input resolution; "
        f"found {dict(da04_counts)}"
    ),
)

require(
    da04_counts.get(
        AdmissionGateState.PASS.value,
        0,
    )
    == 39,
    (
        "Expected all 39 cases to pass DA04 after governed engineering-input resolution; "
        f"found {dict(da04_counts)}"
    ),
)

require(
    da08_counts
    == {"DEFERRED": 39},
    f"DA08 fail-closed boundary drift: {dict(da08_counts)}",
)

require(
    da10_counts
    == {"DEFERRED": 39},
    f"DA10 fail-closed boundary drift: {dict(da10_counts)}",
)

require(
    da11_counts
    == {"PASS": 39},
    f"DA11 opaque holdout boundary drift: {dict(da11_counts)}",
)

require(
    da12_counts
    == {"PASS": 39},
    f"DA12 partition boundary drift: {dict(da12_counts)}",
)


print()
print("=" * 120)
print("THREADROM - MEMBER_SHORTENING PRE-TARGET ADMISSION READINESS V1")
print("=" * 120)

print()
print("Accepted FEM Atlas         : 39/39")
print("Atlas SHA                  :", EXPECTED_ATLAS_SHA)
print("Target contract SHA        :", EXPECTED_TARGET_SHA)
print("Admission contract SHA     :", EXPECTED_ADMISSION_SHA)

print()
print("DA04 engineering inputs:")
print("  PASS                     :", da04_counts["PASS"])
print("  DEFERRED                 :", da04_counts["DEFERRED"])

print()
print("Authority state:")
print("  DA08 numerical cert      : DEFERRED 39/39")
print("  DA10 applicability map   : DEFERRED 39/39")
print("  DA11 opaque holdout gate : PASS 39/39")

print()
print("DA12 partition boundary    : PASS 39/39")

print()
print("Candidate decisions:")
for key in sorted(decision_counts):
    print(
        f"  {key:24s}: {decision_counts[key]}"
    )

print()
print("Target-bearing certificates opened : 0")
print("FRD/DAT/STA opened                 : 0")
print("member_shortening values extracted : 0")
print("Public holdout identities exposed       : 0")
print("Dataset samples created            : 0")
print("Partitions assigned                : 0")
print("ROM training                       : NO")
print("Solver launched                    : NO")

print()
print(
    "DISPOSITION : "
    "MEMBER_SHORTENING_PRE_TARGET_ADMISSION_ENGINE_FAIL_CLOSED"
)
print("=" * 120)
