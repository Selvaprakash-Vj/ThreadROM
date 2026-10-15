from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import tomllib

from datetime import datetime, timezone
from pathlib import Path

from threadrom.case.resolver import resolve_case
from threadrom.factory.diversified_doe_design import _build_case
from threadrom.materials.diversified_candidate_catalog import (
    DIVERSIFIED_CANDIDATE_MATERIAL_CATALOG,
)


ROOT = Path(r"D:\ThreadROM").resolve()

CAMPAIGN_ID = "TRM-DDOE-001"

PROPOSAL = (
    ROOT
    / "docs"
    / "phase3_diversified_doe"
    / "design_proposal.json"
)

POLICY = (
    ROOT
    / "config"
    / "phase3_diversified_doe.toml"
)

HISTORICAL_ATLAS = (
    ROOT
    / "docs"
    / "phase3_fem_atlas"
    / "historical_baselines"
    / (
        "diversified_doe_baseline_"
        "801be26733a087c8b8635406f5bde724144feb2b.json"
    )
)

W03_PLAN = (
    ROOT
    / "docs"
    / "phase3_diversified_doe"
    / "waves"
    / "TRM-DDOE-001-W03"
    / "wave_plan.json"
)

GEOMETRY_ATLAS = (
    ROOT
    / "docs"
    / "phase3_geometry_mesh_atlas"
    / "atlas.json"
)

OBSERVATION_STORE = (
    ROOT
    / "docs"
    / "phase3_calibration_knowledge"
    / "observations_v1.json"
)


EXPECTED_PROPOSAL_SHA = (
    "a386da9648af88b5577386efdc16643b0b099fe2614c2bcc18c0e8973d141e1e"
)

EXPECTED_POLICY_SHA = (
    "6d0e45c109b1ba0a279ec0f06467ea91392760171b9a91bf0467d763896108d9"
)

EXPECTED_HISTORICAL_SHA = (
    "eed5e52f4e9baaad5e2eb89634de48bbdf53c14c584921d8afb0df00631ffc60"
)

EXPECTED_W03_PLAN_SHA = (
    "3714441cb14386e2fcc3adf7b90300a1dcec6ebd2d4404212f2a1adbacb3b225"
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256(path: Path) -> str:
    require(
        path.is_file(),
        f"Missing required file: {path}",
    )
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def read_json(path: Path) -> dict:
    payload = json.loads(
        path.read_text(
            encoding="utf-8-sig"
        )
    )
    require(
        isinstance(payload, dict),
        f"JSON root is not object: {path}",
    )
    return payload


def canonical_bytes(payload: dict) -> bytes:
    return (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def proposal_id(row: dict) -> str:
    value = row.get("proposal_id")
    require(
        isinstance(value, str)
        and bool(value),
        "Proposal row lacks proposal_id.",
    )
    return value


def find_strings(value) -> list[str]:
    result = []

    if isinstance(value, dict):
        for child in value.values():
            result.extend(
                find_strings(child)
            )

    elif isinstance(value, list):
        for child in value:
            result.extend(
                find_strings(child)
            )

    elif isinstance(value, str):
        result.append(value)

    return result


def locate_plan_case_list(
    plan: dict,
    proposal_ids: set[str],
):
    candidates = []

    for key, value in plan.items():

        if (
            not isinstance(value, list)
            or len(value) != 4
            or not all(
                isinstance(item, dict)
                for item in value
            )
        ):
            continue

        identities = []

        valid = True

        for item in value:
            matches = sorted(
                set(
                    find_strings(item)
                )
                & proposal_ids
            )

            if len(matches) != 1:
                valid = False
                break

            identities.append(
                matches[0]
            )

        if valid:
            candidates.append(
                (
                    key,
                    value,
                    identities,
                )
            )

    require(
        len(candidates) == 1,
        (
            "Could not uniquely locate governed case cohort "
            f"inside W03 wave plan; candidates={len(candidates)}."
        ),
    )

    return candidates[0]


def governed_case_identity(
    row: dict,
    policy: dict,
) -> tuple[str, str]:

    size = next(
        (
            item
            for item
            in policy["size_candidates"]
            if item["designation"]
            == row["thread_designation"]
        ),
        None,
    )

    require(
        size is not None,
        (
            f"{proposal_id(row)}: thread designation "
            "not present in policy."
        ),
    )

    case, _ = _build_case(
        policy,
        size,
        row["member_material_id"],
        tuple(
            row["normalized_coordinates"]
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
        == row["case_hash"],
        (
            f"{proposal_id(row)}: canonical "
            "case-hash reconstruction drift."
        ),
    )

    return (
        resolved.case_hash,
        "trm_fem_"
        + resolved.resolution_hash[:12],
    )


def stratum(row: dict) -> tuple[str, str]:
    return (
        row["thread_designation"],
        row["member_material_id"],
    )


def rebind(
    value,
    *,
    old_row: dict,
    new_row: dict,
    old_run: str,
    new_run: str,
    new_wave_token: str,
    now_utc: str,
    key: str | None = None,
):
    if isinstance(value, dict):

        output = {}

        for child_key, child in value.items():

            if child_key in new_row:
                output[
                    child_key
                ] = copy.deepcopy(
                    new_row[
                        child_key
                    ]
                )
                continue

            if child_key == "case_run_id":
                output[child_key] = new_run
                continue

            if child_key in {
                "created_at_utc",
                "generated_at_utc",
                "planned_at_utc",
            }:
                output[child_key] = now_utc
                continue

            output[
                child_key
            ] = rebind(
                child,
                old_row=old_row,
                new_row=new_row,
                old_run=old_run,
                new_run=new_run,
                new_wave_token=new_wave_token,
                now_utc=now_utc,
                key=child_key,
            )

        return output

    if isinstance(value, list):
        return [
            rebind(
                child,
                old_row=old_row,
                new_row=new_row,
                old_run=old_run,
                new_run=new_run,
                new_wave_token=new_wave_token,
                now_utc=now_utc,
                key=key,
            )
            for child in value
        ]

    if isinstance(value, str):

        replacements = (
            (
                proposal_id(old_row),
                proposal_id(new_row),
            ),
            (
                old_row["case_hash"],
                new_row["case_hash"],
            ),
            (
                old_run,
                new_run,
            ),
            (
                "TRM-DDOE-001-W03",
                f"TRM-DDOE-001-{new_wave_token}",
            ),
            (
                "W03",
                new_wave_token,
            ),
            (
                "w03",
                new_wave_token.lower(),
            ),
        )

        rendered = value

        for old, new in replacements:
            rendered = rendered.replace(
                old,
                new,
            )

        return rendered

    return copy.deepcopy(value)


def replace_global_wave_text(
    value,
    *,
    new_wave_token: str,
    now_utc: str,
):
    if isinstance(value, dict):

        result = {}

        for key, child in value.items():

            if key in {
                "created_at_utc",
                "generated_at_utc",
                "planned_at_utc",
            }:
                result[key] = now_utc
            else:
                result[key] = (
                    replace_global_wave_text(
                        child,
                        new_wave_token=new_wave_token,
                        now_utc=now_utc,
                    )
                )

        return result

    if isinstance(value, list):
        return [
            replace_global_wave_text(
                child,
                new_wave_token=new_wave_token,
                now_utc=now_utc,
            )
            for child in value
        ]

    if isinstance(value, str):

        value = value.replace(
            "TRM-DDOE-001-W03",
            f"TRM-DDOE-001-{new_wave_token}",
        )

        value = value.replace(
            "W03",
            new_wave_token,
        )

        value = value.replace(
            "w03",
            new_wave_token.lower(),
        )

        return value

    return copy.deepcopy(value)


def main() -> int:

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--wave-id",
        required=True,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
    )

    args = parser.parse_args()

    match = re.fullmatch(
        r"TRM-DDOE-001-(W\d{2})",
        args.wave_id,
    )

    require(
        match is not None,
        "wave-id must have form TRM-DDOE-001-WNN.",
    )

    wave_token = match.group(1)

    wave_number = int(
        wave_token[1:]
    )

    require(
        wave_number >= 3,
        (
            "Generic next-wave builder is certified "
            "from W03 onward."
        ),
    )

    require(
        sha256(PROPOSAL)
        == EXPECTED_PROPOSAL_SHA,
        "Frozen design proposal SHA drift.",
    )

    require(
        sha256(POLICY)
        == EXPECTED_POLICY_SHA,
        "Frozen diversified DOE policy SHA drift.",
    )

    require(
        sha256(HISTORICAL_ATLAS)
        == EXPECTED_HISTORICAL_SHA,
        "Historical FEM baseline SHA drift.",
    )

    require(
        sha256(W03_PLAN)
        == EXPECTED_W03_PLAN_SHA,
        "Certified W03 plan SHA drift.",
    )

    proposal = read_json(
        PROPOSAL
    )

    historical = read_json(
        HISTORICAL_ATLAS
    )

    template = read_json(
        W03_PLAN
    )

    rows = proposal.get(
        "cases"
    )

    require(
        isinstance(rows, list)
        and len(rows) == 72,
        "Frozen design proposal must contain 72 cases.",
    )

    proposal_by_id = {
        proposal_id(row): row
        for row in rows
    }

    require(
        len(proposal_by_id) == 72,
        "Proposal IDs are not unique.",
    )

    historical_hashes = {
        row["case_hash"]
        for row in historical["cases"]
    }

    fresh = [
        row
        for row in rows
        if row["case_hash"]
        not in historical_hashes
    ]

    historical_overlap = (
        len(rows)
        - len(fresh)
    )

    require(
        historical_overlap == 14,
        (
            "Frozen proposal / historical baseline "
            f"overlap drift: {historical_overlap}, expected 14."
        ),
    )

    require(
        len(fresh) == 58,
        (
            f"Fresh FEM proposal count={len(fresh)}, "
            "expected 58."
        ),
    )

    (
        plan_case_key,
        template_cases,
        template_ids,
    ) = locate_plan_case_list(
        template,
        set(
            proposal_by_id
        ),
    )

    # ------------------------------------------------------------------
    # Generic governed lane continuation.
    #
    # A wave number is NOT a proposal suffix.
    #
    # Certified W03 semantics:
    #   previous-wave active thread/material lane
    #       -> deterministic next unused governed new-evidence state
    #          in frozen proposal order.
    #
    # This deliberately reproduces W03 from W02 before it is allowed
    # to materialize W04 from W03.
    # ------------------------------------------------------------------

    waves_root = (
        ROOT
        / "docs"
        / "phase3_diversified_doe"
        / "waves"
    )

    previous_wave_number = (
        wave_number - 1
    )

    previous_wave_token = (
        f"W{previous_wave_number:02d}"
    )

    previous_wave_id = (
        f"{CAMPAIGN_ID}-"
        f"{previous_wave_token}"
    )

    previous_wave_path = (
        waves_root
        / previous_wave_id
        / "wave_plan.json"
    )

    require(
        previous_wave_path.is_file(),
        (
            f"{wave_token}: previous governed wave "
            f"plan missing: {previous_wave_path}"
        ),
    )

    previous_wave = read_json(
        previous_wave_path
    )

    (
        _previous_case_key,
        _previous_case_records,
        previous_case_ids,
    ) = locate_plan_case_list(
        previous_wave,
        set(
            proposal_by_id
        ),
    )

    require(
        len(previous_case_ids) == 4,
        (
            f"{previous_wave_token}: expected exactly "
            "four governed predecessor lanes."
        ),
    )

    # Bind every proposal already consumed by earlier governed waves.
    used = set()

    for prior_number in range(
        1,
        wave_number,
    ):

        prior_token = (
            f"W{prior_number:02d}"
        )

        prior_id = (
            f"{CAMPAIGN_ID}-"
            f"{prior_token}"
        )

        prior_path = (
            waves_root
            / prior_id
            / "wave_plan.json"
        )

        require(
            prior_path.is_file(),
            (
                f"{wave_token}: governed predecessor "
                f"plan missing: {prior_path}"
            ),
        )

        prior_plan = read_json(
            prior_path
        )

        (
            _prior_key,
            _prior_records,
            prior_ids,
        ) = locate_plan_case_list(
            prior_plan,
            set(
                proposal_by_id
            ),
        )

        require(
            len(prior_ids) == 4,
            (
                f"{prior_token}: governed cohort "
                "count drift."
            ),
        )

        for prior_case_id in prior_ids:

            require(
                prior_case_id
                not in used,
                (
                    "A proposal state appears in more "
                    "than one historical governed wave: "
                    f"{prior_case_id}"
                ),
            )

            used.add(
                prior_case_id
            )

    selected = []

    predecessor_by_stratum = {}

    for predecessor_id in previous_case_ids:

        predecessor_row = (
            proposal_by_id[
                predecessor_id
            ]
        )

        signature = stratum(
            predecessor_row
        )

        require(
            signature
            not in predecessor_by_stratum,
            (
                f"{previous_wave_token}: duplicate "
                f"active lane {signature}."
            ),
        )

        predecessor_by_stratum[
            signature
        ] = predecessor_id

        proposal_order = {
            proposal_id(row): index
            for index, row in enumerate(
                rows
            )
        }

        predecessor_position = (
            proposal_order[
                predecessor_id
            ]
        )

        lane_candidates = [
            row
            for row in fresh
            if (
                stratum(row)
                == signature
                and proposal_id(row)
                not in used
                and proposal_order[
                    proposal_id(row)
                ]
                > predecessor_position
            )
        ]

        require(
            lane_candidates,
            (
                f"{wave_token}: no unused governed "
                "new-evidence state remains AFTER "
                f"predecessor {predecessor_id} "
                f"for lane {signature}."
            ),
        )

        lane_candidates.sort(
            key=lambda row: (
                proposal_order[
                    proposal_id(row)
                ]
            )
        )

        # Certified semantics:
        # deterministic next unused governed state AFTER
        # the previous-wave predecessor in frozen proposal order.
        next_row = lane_candidates[
            0
        ]

        selected.append(
            next_row
        )

        used.add(
            proposal_id(
                next_row
            )
        )

    require(
        len(selected) == 4,
        (
            f"{wave_token}: expected four selected "
            "lane continuations."
        ),
    )

    require(
        len(
            {
                proposal_id(row)
                for row in selected
            }
        )
        == 4,
        (
            f"{wave_token}: duplicate selected "
            "proposal identities."
        ),
    )

    require(
        {
            stratum(row)
            for row in selected
        }
        == {
            stratum(
                proposal_by_id[
                    case_id
                ]
            )
            for case_id
            in previous_case_ids
        },
        (
            f"{wave_token}: selected cohort does not "
            "preserve the previous wave's four "
            "thread/material lanes."
        ),
    )

    # ------------------------------------------------------------------
    # Mandatory replay proof.
    #
    # The generic rule is certified only if W02 -> W03 reconstructs
    # the immutable W03 cohort exactly, in order.
    # ------------------------------------------------------------------

    if wave_token == "W03":

        selected_ids = [
            proposal_id(row)
            for row in selected
        ]

        require(
            selected_ids
            == template_ids,
            (
                "Generic lane-continuation selector "
                "does not reproduce certified W03.\n"
                f"expected={template_ids}\n"
                f"actual  ={selected_ids}"
            ),
        )

        print(
            "PASS: generic lane-continuation rule "
            "exactly reproduces certified W03."
        )

        for index, case_id in enumerate(
            selected_ids,
            start=1,
        ):
            print(
                f"  {index}. {case_id}"
            )

        print(
            "Certified W03 plan SHA:",
            sha256(
                W03_PLAN
            ),
        )

        print(
            "FILES WRITTEN: NO"
        )

        return 0

    with POLICY.open("rb") as stream:
        policy = tomllib.load(
            stream
        )

    now_utc = (
        datetime.now(
            timezone.utc
        )
        .replace(
            microsecond=0
        )
        .isoformat()
        .replace(
            "+00:00",
            "Z",
        )
    )

    output = (
        replace_global_wave_text(
            template,
            new_wave_token=wave_token,
            now_utc=now_utc,
        )
    )

    new_case_records = []

    template_lookup = {}

    for case_record, case_id in zip(
        template_cases,
        template_ids,
        strict=True,
    ):
        template_lookup[
            stratum(
                proposal_by_id[
                    case_id
                ]
            )
        ] = (
            case_record,
            proposal_by_id[
                case_id
            ],
        )

    for wave_order, selected_row in enumerate(
        selected,
        start=1,
    ):

        signature = stratum(
            selected_row
        )

        (
            old_case_record,
            old_row,
        ) = template_lookup[
            signature
        ]

        _, old_run = (
            governed_case_identity(
                old_row,
                policy,
            )
        )

        _, new_run = (
            governed_case_identity(
                selected_row,
                policy,
            )
        )

        rebound = rebind(
            old_case_record,
            old_row=old_row,
            new_row=selected_row,
            old_run=old_run,
            new_run=new_run,
            new_wave_token=wave_token,
            now_utc=now_utc,
        )

        if isinstance(
            rebound,
            dict,
        ):
            if "wave_order" in rebound:
                rebound[
                    "wave_order"
                ] = wave_order

            predecessor_id = (
                predecessor_by_stratum[
                    signature
                ]
            )

            if (
                "selection_reason"
                in rebound
            ):
                rebound[
                    "selection_reason"
                ] = (
                    f"Deterministic "
                    f"{previous_wave_token}-lane "
                    "continuation to next unused "
                    "governed new-evidence state; "
                    f"predecessor={predecessor_id}"
                )

            if (
                "predecessor"
                in rebound
            ):
                rebound[
                    "predecessor"
                ] = predecessor_id

        new_case_records.append(
            rebound
        )

    output[
        plan_case_key
    ] = new_case_records

    # Update W03 learning-store hashes only if the W03 template actually
    # carried them. The frozen 22-case historical DOE baseline SHA is
    # intentionally NOT replaced.
    hash_replacements = {
        (
            "29b39b7da47bf96410fd4d6af3b6780e"
            "cb25f06047d333aef9076f54c2c84ff4"
        ): sha256(
            GEOMETRY_ATLAS
        ),
        (
            "bd55e1715f2e0ae958c30a1b6dd1715"
            "519e48286420fad6bce0d76431d2168d9"
        ): sha256(
            OBSERVATION_STORE
        ),
    }

    def replace_hashes(value):
        if isinstance(value, dict):
            return {
                key: replace_hashes(child)
                for key, child
                in value.items()
            }

        if isinstance(value, list):
            return [
                replace_hashes(child)
                for child in value
            ]

        if (
            isinstance(value, str)
            and value in hash_replacements
        ):
            return hash_replacements[
                value
            ]

        return value

    output = replace_hashes(
        output
    )

    # --------------------------------------------------------------
    # Advance wave-chain provenance to the actual previous wave.
    # --------------------------------------------------------------

    if (
        "previous_wave_plan_sha256"
        in output
    ):
        output[
            "previous_wave_plan_sha256"
        ] = sha256(
            previous_wave_path
        )

    if (
        "previous_wave_id"
        in output
    ):
        output[
            "previous_wave_id"
        ] = previous_wave_id

    if (
        "previous_wave_token"
        in output
    ):
        output[
            "previous_wave_token"
        ] = previous_wave_token

    if (
        "meaning"
        in output
    ):
        output[
            "meaning"
        ] = (
            f"Immutable four-case {wave_token} "
            "selection from the frozen Phase-3 "
            "diversified DOE. The cohort is the "
            "deterministic next unused governed "
            "new-evidence state in each "
            f"{previous_wave_token} thread/material "
            "lane. This record grants no preparation, "
            "solver execution, adaptive continuation, "
            "dataset admission, physics certification, "
            "artifact retirement, surrogate training, "
            "or holdout access."
        )

    if (
        "wave_purpose"
        in output
    ):
        output[
            "wave_purpose"
        ] = (
            f"PRODUCTION_{wave_token}_"
            "NEXT_UNUSED_NEW_EVIDENCE_"
            "LANE_CONTINUATION"
        )

    selection_basis = (
        output.get(
            "selection_basis"
        )
    )

    previous_selection_basis = (
        previous_wave.get(
            "selection_basis"
        )
    )

    if isinstance(
        selection_basis,
        dict,
    ):

        selection_basis[
            "selected_group_count"
        ] = 4

        selection_basis[
            "selection_rule"
        ] = (
            f"Continue each "
            f"{previous_wave_token} "
            "thread/material lane to its "
            "deterministic next unused "
            "governed new-evidence state."
        )

        if (
            isinstance(
                previous_selection_basis,
                dict,
            )
            and isinstance(
                previous_selection_basis.get(
                    "anchor_inventory_count"
                ),
                int,
            )
        ):
            selection_basis[
                "anchor_inventory_count"
            ] = (
                previous_selection_basis[
                    "anchor_inventory_count"
                ]
                + 4
            )

        if (
            isinstance(
                previous_selection_basis,
                dict,
            )
            and isinstance(
                previous_selection_basis.get(
                    "anchor_inventory_meaning"
                ),
                str,
            )
        ):
            selection_basis[
                "anchor_inventory_meaning"
            ] = (
                previous_selection_basis[
                    "anchor_inventory_meaning"
                ]
                + " + 4 "
                + previous_wave_token
                + " governed full-physics "
                "accepted states"
            )

    selected_ids = {
        proposal_id(row)
        for row in selected
    }

    rendered_ids = set()

    for record in output[
        plan_case_key
    ]:
        matches = (
            set(
                find_strings(record)
            )
            & selected_ids
        )

        require(
            len(matches) == 1,
            (
                f"{wave_token}: rendered case record "
                "does not bind exactly one selected proposal."
            ),
        )

        rendered_ids.update(
            matches
        )

    require(
        rendered_ids
        == selected_ids,
        (
            f"{wave_token}: rendered plan cohort identity drift."
        ),
    )

    if (
        "wave_id"
        in output
    ):
        require(
            output[
                "wave_id"
            ]
            == args.wave_id,
            (
                f"{wave_token}: current wave-id "
                "binding drift."
            ),
        )

    if (
        "previous_wave_plan_sha256"
        in output
    ):
        require(
            output[
                "previous_wave_plan_sha256"
            ]
            == sha256(
                previous_wave_path
            ),
            (
                f"{wave_token}: predecessor "
                "wave-plan SHA binding drift."
            ),
        )

    output_dir = (
        ROOT
        / "docs"
        / "phase3_diversified_doe"
        / "waves"
        / args.wave_id
    )

    output_path = (
        output_dir
        / "wave_plan.json"
    )

    encoded = canonical_bytes(
        output
    )

    digest = hashlib.sha256(
        encoded
    ).hexdigest()

    print()
    print(
        "=" * 108
    )
    print(
        "GENERIC NEXT GOVERNED WAVE PLAN"
    )
    print(
        "=" * 108
    )

    print(
        "Wave              :",
        args.wave_id,
    )

    print(
        "Plan case key     :",
        plan_case_key,
    )

    print(
        "Fresh DOE total   :",
        len(fresh),
    )

    print(
        "Selected cases    :",
        len(selected),
    )

    for index, row in enumerate(
        selected,
        start=1,
    ):
        _, case_run_id = (
            governed_case_identity(
                row,
                policy,
            )
        )

        print(
            f"  {index}. "
            f"{proposal_id(row)} | "
            f"{row['case_hash']} | "
            f"{case_run_id}"
        )

    print(
        "Plan SHA          :",
        digest,
    )

    if args.dry_run:
        print(
            "FILES WRITTEN     : NO"
        )
        return 0

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    if output_path.exists():

        existing = (
            output_path.read_bytes()
        )

        require(
            existing == encoded,
            (
                "Existing immutable wave plan differs "
                "from deterministic rendering. "
                "Refusing overwrite."
            ),
        )

        print(
            "REUSED:",
            output_path.relative_to(
                ROOT
            ).as_posix(),
        )

    else:

        temporary = (
            output_path
            .with_name(
                output_path.name
                + ".tmp"
            )
        )

        temporary.write_bytes(
            encoded
        )

        temporary.replace(
            output_path
        )

        print(
            "CREATED:",
            output_path.relative_to(
                ROOT
            ).as_posix(),
        )

    require(
        sha256(
            output_path
        )
        == digest,
        "Persisted wave-plan SHA drift.",
    )

    print(
        "FINAL SHA          :",
        sha256(
            output_path
        ),
    )

    print(
        "SOLVER             : NO"
    )

    print(
        "HOLDOUTS           : NO"
    )

    print(
        "DATASET ADMISSION  : NO"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )