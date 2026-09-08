from __future__ import annotations

import hashlib
import json
import math
import tomllib

from dataclasses import asdict
from pathlib import Path

from threadrom.case.resolver import resolve_case
from threadrom.factory.fem_calibration_knowledge import (
    build_fem_calibration_knowledge_record,
    load_fem_warm_start_policy,
)
from threadrom.factory.preload_calibration_seed import (
    derive_analytical_thermal_preload_seed,
)
from threadrom.factory.production_doe import (
    build_phase3_production_doe,
    load_phase3_production_doe_policy,
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

DOE_POLICY_PATH = (
    CONFIG
    / "phase3_production_doe.toml"
)

CAMPAIGN_MANIFEST_PATH = (
    CAMPAIGN_ROOT
    / "production_doe_campaign_manifest.json"
)

ANCHOR_BINDING_PATH = (
    CAMPAIGN_ROOT
    / "existing_anchor_binding_record.json"
)

PREPARATION_CERT_PATH = (
    CAMPAIGN_ROOT
    / "production_doe_preparation_certification_record.json"
)

WARM_POLICY_PATH = (
    CONFIG
    / "fem_calibration_warm_start.toml"
)

OUTPUT = (
    CAMPAIGN_ROOT
    / "production_doe_warm_start_knowledge_record.json"
)

EXPECTED_DOE_POLICY_SHA256 = (
    "43032557cb2abead0118362bcfc6a9b2e"
    "5246a7d363ca83eef5fcf35054befc1"
)

EXPECTED_CAMPAIGN_SHA256 = (
    "84516519bbb188664268936e2d116e133"
    "431d90d037bed407ffb2d1fe92d2a67"
)

EXPECTED_ANCHOR_BINDING_SHA256 = (
    "ab861ff62af6bbc4589b3a469e8dc159"
    "c92dd61116fd8275c02e8f1adcf813b2"
)

EXPECTED_PREPARATION_CERT_SHA256 = (
    "ad49cc35b61e95147ae669f0f915b8d7a"
    "e403145d098729e5540285f319befd5"
)


def sha256(path: Path) -> str:
    if (
        not path.is_file()
        or path.stat().st_size <= 0
    ):
        raise FileNotFoundError(path)

    digest = hashlib.sha256()

    with path.open("rb") as stream:
        for chunk in iter(
            lambda: stream.read(8 * 1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def require_sha256(
    path: Path,
    expected: str,
    label: str,
) -> str:
    actual = sha256(path)

    if actual != expected:
        raise RuntimeError(
            f"{label} drift detected.\n"
            f"Expected: {expected}\n"
            f"Actual  : {actual}\n"
            f"Path    : {path}"
        )

    return actual


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def walk_dicts(value):
    if isinstance(value, dict):
        yield value

        for child in value.values():
            yield from walk_dicts(child)

    elif isinstance(value, list):
        for child in value:
            yield from walk_dicts(child)


def recursive_values(
    value,
    key_names: tuple[str, ...],
):
    found = []

    if isinstance(value, dict):
        for key, child in value.items():
            if (
                key in key_names
                and not isinstance(
                    child,
                    (dict, list),
                )
            ):
                found.append(
                    (key, child)
                )

            found.extend(
                recursive_values(
                    child,
                    key_names,
                )
            )

    elif isinstance(value, list):
        for child in value:
            found.extend(
                recursive_values(
                    child,
                    key_names,
                )
            )

    return found


def anchor_binding_row(
    binding: dict,
    case_hash: str,
) -> dict:
    matches = [
        item
        for item in walk_dicts(binding)
        if item.get("case_hash") == case_hash
    ]

    if not matches:
        raise RuntimeError(
            "No anchor-binding row found for "
            f"case hash {case_hash}."
        )

    scored = []

    for item in matches:
        run_hits = recursive_values(
            item,
            (
                "accepted_run_id",
                "run_id",
                "evidence_run_id",
            ),
        )

        clamp_hits = recursive_values(
            item,
            (
                "realized_mean_clamp_force_n",
                "mean_clamp_force_n",
                "realized_clamp_force_n",
                "realized_clamp_n",
            ),
        )

        scored.append(
            (
                int(bool(run_hits))
                + int(bool(clamp_hits)),
                item,
            )
        )

    scored.sort(
        key=lambda entry: entry[0],
        reverse=True,
    )

    if scored[0][0] < 2:
        raise RuntimeError(
            "Anchor-binding row does not expose both "
            "accepted run identity and realized clamp "
            f"for case {case_hash}."
        )

    return scored[0][1]


def unique_scalar(
    row: dict,
    keys: tuple[str, ...],
    label: str,
):
    hits = recursive_values(
        row,
        keys,
    )

    values = []

    for _, value in hits:
        if value not in values:
            values.append(value)

    if len(values) != 1:
        raise RuntimeError(
            f"{label}: expected exactly one value; "
            f"found {values!r}."
        )

    return values[0]


def reference_temperature_c() -> float:
    path = (
        CONFIG
        / "complete_joint_preload.toml"
    )

    with path.open("rb") as stream:
        data = tomllib.load(stream)

    matches = []

    def walk(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "reference_temperature_c":
                    matches.append(
                        float(child)
                    )
                else:
                    walk(child)

        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(data)

    if len(matches) != 1:
        raise RuntimeError(
            "Expected exactly one governed "
            "reference_temperature_c."
        )

    value = matches[0]

    if not math.isfinite(value):
        raise RuntimeError(
            "Reference temperature is not finite."
        )

    return value


CERTIFIED_ACCEPTED_DECKS = {
    (
        "trm_sim_000004_run_a2_thermal_20kn"
    ): (
        ROOT
        / ".tmp"
        / "cp4_step6_live_reproduction"
        / "trm_sim_000004_run_a2_thermal_20kn.inp"
    ),

    (
        "trm_fem_a9b6196a25d4_cal_02"
    ): (
        ROOT
        / "simulations"
        / "staging"
        / "phase3_cp8_overnight"
        / "trm_fem_a9b6196a25d4"
        / "trm_fem_a9b6196a25d4_cal_02"
        / "trm_fem_a9b6196a25d4_cal_02.inp"
    ),

    (
        "trm_fem_30059c410f5c_cal_02"
    ): (
        ROOT
        / "simulations"
        / "staging"
        / "phase3_cp7_pilot"
        / "trm_fem_30059c410f5c"
        / "calibration"
        / "trm_fem_30059c410f5c_cal_02"
        / "trm_fem_30059c410f5c_cal_02.inp"
    ),

    (
        "trm_fem_ae87c6fcba11_cal_02_medium_plus_sentinel"
    ): (
        ROOT
        / "simulations"
        / "staging"
        / "phase3_cp8_p04"
        / "trm_fem_ae87c6fcba11_cal_02_medium_plus_sentinel"
        / (
            "trm_fem_ae87c6fcba11"
            "_cal_02_medium_plus_sentinel.inp"
        )
    ),
}


def find_accepted_deck(
    accepted_run_id: str,
) -> Path:
    try:
        path = CERTIFIED_ACCEPTED_DECKS[
            accepted_run_id
        ]
    except KeyError as exc:
        raise RuntimeError(
            "No certified accepted-deck provenance "
            "binding exists for run "
            f"{accepted_run_id!r}."
        ) from exc

    if (
        not path.is_file()
        or path.stat().st_size <= 0
    ):
        raise FileNotFoundError(
            "Certified accepted FEM deck is missing "
            f"or empty: {path}"
        )

    if path.name != f"{accepted_run_id}.inp":
        raise RuntimeError(
            "Certified deck/run identity mismatch: "
            f"{accepted_run_id} -> {path}"
        )

    return path


def applied_temperature_c(
    path: Path,
) -> float:
    lines = path.read_text(
        encoding="utf-8",
        errors="replace",
    ).splitlines()

    values = []
    in_temperature = False

    for line in lines:
        stripped = line.strip()

        if stripped.upper().startswith(
            "*TEMPERATURE"
        ):
            in_temperature = True
            continue

        if not in_temperature:
            continue

        if stripped.startswith("*"):
            in_temperature = False
            continue

        if not stripped:
            continue

        parts = [
            item.strip()
            for item in stripped.split(",")
        ]

        if len(parts) < 2:
            continue

        try:
            value = float(
                parts[-1]
            )
        except ValueError:
            continue

        if math.isfinite(value):
            values.append(value)

    unique = sorted(
        set(
            round(value, 12)
            for value in values
        )
    )

    if len(unique) != 1:
        raise RuntimeError(
            "Expected exactly one applied FEM "
            f"temperature in {path}; found {unique}."
        )

    return float(unique[0])


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

        if existing != serialized:
            raise RuntimeError(
                "Warm-start knowledge record already "
                "exists with different content. "
                f"Refusing overwrite: {path}"
            )

        action = "UNCHANGED / IDENTICAL"

    else:
        temporary = path.with_suffix(
            ".json.tmp"
        )

        temporary.write_text(
            serialized,
            encoding="utf-8",
            newline="\n",
        )

        temporary.replace(path)

        action = "CREATED"

    record_hash = sha256(path)

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

        if existing != sidecar_text:
            raise RuntimeError(
                "Warm-start knowledge SHA sidecar "
                "drift detected."
            )
    else:
        sidecar.write_text(
            sidecar_text,
            encoding="ascii",
            newline="\n",
        )

    return action, record_hash


# --------------------------------------------------
# GOVERNANCE
# --------------------------------------------------

doe_policy_hash = require_sha256(
    DOE_POLICY_PATH,
    EXPECTED_DOE_POLICY_SHA256,
    "Production DOE policy",
)

campaign_hash = require_sha256(
    CAMPAIGN_MANIFEST_PATH,
    EXPECTED_CAMPAIGN_SHA256,
    "Production DOE campaign manifest",
)

anchor_binding_hash = require_sha256(
    ANCHOR_BINDING_PATH,
    EXPECTED_ANCHOR_BINDING_SHA256,
    "Existing-anchor binding record",
)

preparation_cert_hash = require_sha256(
    PREPARATION_CERT_PATH,
    EXPECTED_PREPARATION_CERT_SHA256,
    "Preparation certification record",
)

warm_policy_hash = sha256(
    WARM_POLICY_PATH
)

warm_policy = load_fem_warm_start_policy(
    WARM_POLICY_PATH
)

policy = load_phase3_production_doe_policy(
    DOE_POLICY_PATH
)

campaign = build_phase3_production_doe(
    policy
)

binding = json.loads(
    ANCHOR_BINDING_PATH.read_text(
        encoding="utf-8"
    )
)

anchors = tuple(
    item
    for item in campaign.design_cases
    if item.source_case_id is not None
)

if len(anchors) != 4:
    raise RuntimeError(
        f"Expected 4 Production DOE anchors; "
        f"found {len(anchors)}."
    )

reference_c = reference_temperature_c()

evidence_rows = []
knowledge_records = []


# --------------------------------------------------
# BUILD KNOWLEDGE FROM CERTIFIED EVIDENCE
# --------------------------------------------------

for anchor in anchors:
    resolved = resolve_case(
        anchor.case
    )

    if resolved.case_hash != anchor.case_hash:
        raise RuntimeError(
            f"{anchor.case_id}: resolved hash drift."
        )

    seed = (
        derive_analytical_thermal_preload_seed(
            resolved
        )
    )

    row = anchor_binding_row(
        binding,
        anchor.case_hash,
    )

    accepted_run_id = str(
        unique_scalar(
            row,
            (
                "accepted_run_id",
                "run_id",
                "evidence_run_id",
            ),
            f"{anchor.case_id} accepted run",
        )
    )

    realized_clamp_n = float(
        unique_scalar(
            row,
            (
                "realized_mean_clamp_force_n",
                "mean_clamp_force_n",
                "realized_clamp_force_n",
                "realized_clamp_n",
            ),
            f"{anchor.case_id} realized clamp",
        )
    )

    if (
        not math.isfinite(realized_clamp_n)
        or realized_clamp_n <= 0.0
    ):
        raise RuntimeError(
            f"{anchor.case_id}: invalid realized clamp."
        )

    deck_path = find_accepted_deck(
        accepted_run_id
    )

    applied_c = applied_temperature_c(
        deck_path
    )

    accepted_delta_c = (
        applied_c
        - reference_c
    )

    if accepted_delta_c >= 0.0:
        raise RuntimeError(
            f"{anchor.case_id}: accepted preload "
            "temperature must be contraction."
        )

    knowledge = (
        build_fem_calibration_knowledge_record(
            resolved=resolved,
            seed=seed,
            accepted_run_id=accepted_run_id,
            accepted_delta_temperature_c=(
                accepted_delta_c
            ),
            measured_mean_clamp_force_n=(
                realized_clamp_n
            ),
        )
    )

    if knowledge.case_hash != anchor.case_hash:
        raise RuntimeError(
            f"{anchor.case_id}: generated knowledge "
            "record hash mismatch."
        )

    knowledge_records.append(
        knowledge
    )

    evidence_rows.append(
        {
            "case_id": anchor.case_id,
            "source_case_id": (
                anchor.source_case_id
            ),
            "case_hash": anchor.case_hash,
            "accepted_run_id": (
                accepted_run_id
            ),
            "accepted_deck_relative_path": (
                relative(deck_path)
            ),
            "accepted_deck_sha256": (
                sha256(deck_path)
            ),
            "reference_temperature_c": (
                reference_c
            ),
            "applied_temperature_c": (
                applied_c
            ),
            "accepted_delta_temperature_c": (
                accepted_delta_c
            ),
            "measured_mean_clamp_force_n": (
                realized_clamp_n
            ),
            "analytical_delta_temperature_c": (
                seed.predicted_delta_temperature_c
            ),
            "correction_factor": (
                knowledge.correction_factor
            ),
            "knowledge_record": (
                asdict(knowledge)
            ),
            "status": "CERTIFIED_REUSABLE",
        }
    )


# Deterministic order.
evidence_rows.sort(
    key=lambda item: item["case_id"]
)

knowledge_records.sort(
    key=lambda item: item.case_hash
)


record = {
    "schema_version": 1,

    "record_id": (
        "TRM-P3-CP8-PDOE-C01-WARM-KNOWLEDGE-001"
    ),

    "record_status": "FINAL",

    "campaign": {
        "campaign_id": (
            "TRM-PDOE-C01"
        ),
        "doe_policy_sha256": (
            doe_policy_hash
        ),
        "campaign_manifest_sha256": (
            campaign_hash
        ),
        "anchor_binding_sha256": (
            anchor_binding_hash
        ),
        "preparation_certification_sha256": (
            preparation_cert_hash
        ),
    },

    "warm_start_policy": {
        "policy_id": (
            warm_policy.policy_id
        ),
        "policy_sha256": (
            warm_policy_hash
        ),
        "maximum_neighbors": (
            warm_policy.maximum_neighbors
        ),
        "maximum_reuse_distance": (
            warm_policy.maximum_reuse_distance
        ),
        "minimum_neighbors_for_reuse": (
            warm_policy.minimum_neighbors_for_reuse
        ),
        "require_target_preload_bracketing": (
            warm_policy.require_target_preload_bracketing
        ),
        (
            "maximum_correction_factor_"
            "relative_spread"
        ): (
            warm_policy
            .maximum_correction_factor_relative_spread
        ),
    },

    "knowledge_scope": {
        "certified_anchor_count": 4,
        "reference_temperature_c": (
            reference_c
        ),
        "accepted_temperatures_derived_from_decks": (
            True
        ),
        "realized_clamps_derived_from_anchor_binding": (
            True
        ),
        "manual_temperature_constants_in_record_builder": (
            False
        ),
    },

    "anchors": evidence_rows,

    "overall_disposition": (
        "FOUR_CERTIFIED_FEM_ANCHORS_BOUND_AS_"
        "WARM_START_KNOWLEDGE"
    ),
}


action, record_hash = (
    write_immutable_json(
        OUTPUT,
        record,
    )
)


print("=" * 124)
print(
    "THREADROM — PRODUCTION DOE WARM-START KNOWLEDGE"
)
print("=" * 124)

print(
    "Record action          :",
    action,
)

print(
    "Record status          : FINAL"
)

print(
    "Warm-start policy      :",
    warm_policy.policy_id,
)

print(
    "Certified anchors      :",
    len(evidence_rows),
)

print(
    "Reference temperature  :",
    reference_c,
    "C",
)

print()

for item in evidence_rows:
    print(
        f"{item['case_id']:4s} | "
        f"{item['accepted_run_id']} | "
        f"dT={item['accepted_delta_temperature_c']:.12f} C | "
        f"clamp={item['measured_mean_clamp_force_n']:.6f} N | "
        f"k={item['correction_factor']:.9f}"
    )

print()

print(
    "Disposition            : "
    "FOUR_CERTIFIED_FEM_ANCHORS_BOUND_AS_"
    "WARM_START_KNOWLEDGE"
)

print(
    "Record SHA256          :",
    record_hash,
)

print(
    "Record                 :",
    OUTPUT,
)

print(
    "CalculiX invoked       : NO"
)

print(
    "Holdouts accessed      : NO"
)

print("=" * 124)
