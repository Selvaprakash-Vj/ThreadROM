from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(r"D:\ThreadROM")

BASE_PATH = (
    ROOT
    / "scripts"
    / "build_phase3_fem_atlas.py"
)

GOVERNED_ADAPTER_PATH = (
    ROOT
    / "scripts"
    / "admit_phase3_governed_wave_fem_evidence_v1.py"
)

ATLAS_PATH = (
    ROOT
    / "docs"
    / "phase3_fem_atlas"
    / "atlas.json"
)

PILOT_CERT = (
    ROOT
    / "simulations"
    / "staging"
    / "phase3_diversified_doe"
    / "pilot_calibration_preflight"
    / "trm_fem_0f92f7fbf611"
    / "trm_fem_0f92f7fbf611_cal_02"
    / "diversified_governed_physics_certificate.json"
)

PILOT_PREFLIGHT = (
    PILOT_CERT.parent
    / "pilot_adaptive_factory_preflight.json"
)

PILOT_MANIFEST = (
    PILOT_CERT.parent
    / "fem_run_manifest.json"
)

DESIGN_PROPOSAL = (
    ROOT
    / "docs"
    / "phase3_diversified_doe"
    / "design_proposal.json"
)


EXPECTED = {
    "atlas_before": (
        "284d8fadb0a869f4e2affd4f0120ee41336f0475cd2107465a569cb034619e53"
    ),
    "base_builder": (
        "8b52aba9a34852a09bd7d01855fc4b655d2d798142a591079a760009ed40ff70"
    ),
    "governed_adapter": (
        "b113d8b0f0524fc0636636fdb272686a06e3c9424e813845b12fdcd92e3e0846"
    ),
    "pilot_certificate": (
        "cc97d842aa914cc5ec0ad5c13bf7fc9bf1fa6dc9a2635acfbc94a7f1cc614397"
    ),
    "pilot_preflight": (
        "416a3b5c46a2bf4b4cef85a641f56be09f9cefc61384749d758e118e68e80a77"
    ),
    "pilot_manifest": (
        "b7240a132f2db3796aa34f5f4942b08308e9cee2db1c474f8e06230bc9add4a5"
    ),
    "design_proposal": (
        "a386da9648af88b5577386efdc16643b0b099fe2614c2bcc18c0e8973d141e1e"
    ),
}


EXPECTED_CASE_ID = (
    "TRM-DDOE-D-M10x1_5__"
    "member_aluminium_en_aw_6082_t6-01"
)

EXPECTED_CASE_HASH = (
    "db4f5abb0986d0527a06fd72849bfc948041448f6a8a320a4aad0a0858028d53"
)

EXPECTED_CASE_RUN_ID = (
    "trm_fem_0f92f7fbf611"
)

EXPECTED_ACCEPTED_RUN_ID = (
    "trm_fem_0f92f7fbf611_cal_02"
)

EXPECTED_CERTIFICATE_FILENAME = (
    "diversified_governed_physics_certificate.json"
)


def require(
    condition: bool,
    message: str,
) -> None:

    if not condition:
        raise RuntimeError(message)


def sha256(
    path: Path,
) -> str:

    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def load_json(
    path: Path,
) -> dict[str, Any]:

    obj = json.loads(
        path.read_text(
            encoding="utf-8-sig"
        )
    )

    require(
        isinstance(obj, dict),
        f"Expected JSON object: {path}",
    )

    return obj


def relative(
    path: Path,
) -> str:

    return (
        path.resolve()
        .relative_to(ROOT.resolve())
        .as_posix()
    )


def load_module(
    name: str,
    path: Path,
):

    spec = importlib.util.spec_from_file_location(
        name,
        path,
    )

    require(
        spec is not None
        and spec.loader is not None,
        f"Cannot import {path}",
    )

    module = importlib.util.module_from_spec(
        spec
    )

    sys.modules[
        name
    ] = module

    spec.loader.exec_module(
        module
    )

    return module


def load_governed_closure_cases(
    source_path: Path,
) -> dict[str, dict[str, Any]]:

    parts = source_path.resolve().parts

    try:
        campaign_index = parts.index(
            "TRM-DDOE-001"
        )
    except ValueError as exc:
        raise RuntimeError(
            "Governed certificate is outside expected "
            "TRM-DDOE-001 campaign path."
        ) from exc

    require(
        campaign_index + 1 < len(parts),
        "Cannot derive historical governed-wave token.",
    )

    wave_token = parts[
        campaign_index + 1
    ]

    require(
        re.fullmatch(
            r"W\d{2}",
            wave_token,
        )
        is not None,
        (
            "Cannot derive governed-wave identity "
            f"from path token {wave_token!r}."
        ),
    )

    wave_id = (
        f"TRM-DDOE-001-{wave_token}"
    )

    closure_root = (
        ROOT
        / "docs"
        / "phase3_governed_wave_closure"
    )

    candidates = [
        closure_root
        / f"{wave_id}.wave_closure.json",

        closure_root
        / "historical_replay"
        / f"{wave_id}.wave_closure.json",
    ]

    existing = [
        path
        for path in candidates
        if path.is_file()
    ]

    require(
        existing,
        (
            f"Immutable closure missing for {wave_id}. "
            f"Checked: {candidates}"
        ),
    )

    if len(existing) > 1:

        payloads = {
            path.read_bytes()
            for path in existing
        }

        require(
            len(payloads) == 1,
            (
                "Conflicting immutable closure copies "
                f"for {wave_id}: {existing}"
            ),
        )

    closure_path = existing[0]

    closure = load_json(
        closure_path
    )

    require(
        closure.get("schema")
        == "threadrom.governed_wave_closure.v1",
        f"{wave_id}: closure schema drift.",
    )

    require(
        closure.get("record_status")
        == "FINAL",
        f"{wave_id}: closure is not FINAL.",
    )

    require(
        closure.get("disposition")
        == "GOVERNED_WAVE_FULL_PHYSICS_CLOSED",
        f"{wave_id}: closure disposition drift.",
    )

    require(
        closure.get("wave_id")
        == wave_id,
        f"{wave_id}: closure wave identity drift.",
    )

    cases = closure.get(
        "cases"
    )

    require(
        isinstance(cases, list)
        and len(cases) == 4,
        f"{wave_id}: expected four CLOSED cases.",
    )

    mapped: dict[
        str,
        dict[str, Any],
    ] = {}

    for row in cases:

        require(
            isinstance(row, dict),
            f"{wave_id}: malformed closure case.",
        )

        case_id = row.get(
            "case_id"
        )

        require(
            isinstance(case_id, str)
            and case_id not in mapped,
            f"{wave_id}: invalid/duplicate closure case identity.",
        )

        mapped[
            case_id
        ] = row

    return mapped


def build_pilot_evidence_entry(
    *,
    base,
    source_path: str,
) -> dict[str, Any]:

    path = (
        ROOT
        / Path(
            source_path
        )
    ).resolve()

    require(
        path == PILOT_CERT.resolve(),
        (
            "Pilot adapter may process only the certified "
            "historical aluminium-pilot certificate."
        ),
    )

    require(
        path.is_file(),
        "Historical pilot certificate missing.",
    )

    require(
        sha256(path)
        == EXPECTED[
            "pilot_certificate"
        ],
        "Historical pilot certificate SHA drift.",
    )

    require(
        sha256(PILOT_PREFLIGHT)
        == EXPECTED[
            "pilot_preflight"
        ],
        "Historical pilot preflight SHA drift.",
    )

    require(
        sha256(PILOT_MANIFEST)
        == EXPECTED[
            "pilot_manifest"
        ],
        "Historical pilot manifest SHA drift.",
    )

    require(
        sha256(DESIGN_PROPOSAL)
        == EXPECTED[
            "design_proposal"
        ],
        "Frozen diversified DOE proposal SHA drift.",
    )


    certificate = load_json(
        path
    )

    preflight = load_json(
        PILOT_PREFLIGHT
    )

    manifest = load_json(
        PILOT_MANIFEST
    )


    # ==========================================================================
    # Frozen DOE membership + source binding
    # ==========================================================================

    source_sha = certificate.get(
        "source_sha256"
    )

    require(
        isinstance(source_sha, dict),
        "Pilot certificate source_sha256 is malformed.",
    )

    require(
        source_sha.get(
            "docs/phase3_diversified_doe/design_proposal.json"
        )
        == EXPECTED[
            "design_proposal"
        ],
        "Pilot certificate is not bound to frozen diversified DOE proposal.",
    )

    proposal_text = DESIGN_PROPOSAL.read_text(
        encoding="utf-8-sig"
    )

    require(
        EXPECTED_CASE_ID
        in proposal_text,
        "Historical pilot case is absent from frozen DOE proposal.",
    )


    # ==========================================================================
    # Certificate contract
    # ==========================================================================

    require(
        certificate.get(
            "schema"
        )
        == "threadrom.diversified_governed_physics_certificate.v1",
        "Pilot certificate schema drift.",
    )

    require(
        certificate.get(
            "record_status"
        )
        == "FINAL",
        "Pilot physics certificate is not FINAL.",
    )

    require(
        certificate.get(
            "disposition"
        )
        == "GOVERNED_FULL_PHYSICS_ACCEPTED",
        "Pilot certificate is not full-physics accepted.",
    )

    require(
        certificate.get(
            "case_id"
        )
        == EXPECTED_CASE_ID,
        "Pilot certificate case identity drift.",
    )

    require(
        certificate.get(
            "case_hash"
        )
        == EXPECTED_CASE_HASH,
        "Pilot certificate case hash drift.",
    )

    require(
        certificate.get(
            "case_run_id"
        )
        == EXPECTED_CASE_RUN_ID,
        "Pilot certificate case-run identity drift.",
    )

    require(
        certificate.get(
            "run_id"
        )
        == EXPECTED_ACCEPTED_RUN_ID,
        "Pilot certificate accepted-run identity drift.",
    )

    require(
        certificate.get(
            "trial_index"
        )
        == 2,
        "Pilot accepted trial index drift.",
    )

    require(
        certificate.get(
            "holdout_access_authorized"
        )
        is False,
        "Pilot certificate unexpectedly authorizes holdout access.",
    )

    require(
        certificate.get(
            "additional_fem_authorized"
        )
        is False,
        "Pilot certificate unexpectedly authorizes additional FEM.",
    )

    require(
        certificate.get(
            "artifact_retirement_authorized"
        )
        is False,
        "Pilot certificate unexpectedly authorizes artifact retirement.",
    )


    assessment = certificate.get(
        "assessment"
    )

    require(
        isinstance(
            assessment,
            dict,
        ),
        "Pilot certificate assessment is malformed.",
    )

    require(
        assessment.get(
            "accepted_increment_count"
        )
        == 20,
        "Pilot certificate does not record 20 accepted increments.",
    )

    require(
        assessment.get(
            "full_physics_passed"
        )
        is True,
        "Pilot certificate does not record full-physics PASS.",
    )

    failed_checks = assessment.get(
        "failed_governed_checks"
    )

    require(
        failed_checks in (
            [],
            None,
        ),
        (
            "Pilot certificate records failed governed checks: "
            f"{failed_checks!r}"
        ),
    )


    # ==========================================================================
    # Historical pilot preflight contract
    # ==========================================================================

    require(
        preflight.get(
            "case_hash"
        )
        == EXPECTED_CASE_HASH,
        "Pilot preflight case hash drift.",
    )

    require(
        preflight.get(
            "case_run_id"
        )
        == EXPECTED_CASE_RUN_ID,
        "Pilot preflight case-run identity drift.",
    )

    require(
        preflight.get(
            "scope"
        )
        == "phase3_diversified_pilot_only",
        "Pilot preflight scope drift.",
    )

    require(
        preflight.get(
            "production_doe_authorization_claimed"
        )
        is False,
        (
            "Historical pilot must not claim "
            "production-DOE authorization."
        ),
    )

    require(
        preflight.get(
            "dataset_admission_authorized"
        )
        is False,
        (
            "Historical pilot unexpectedly "
            "authorizes dataset admission."
        ),
    )

    require(
        preflight.get(
            "sealed_holdouts_accessed"
        )
        is False,
        "Historical pilot preflight accessed sealed holdouts.",
    )

    require(
        preflight.get(
            "doe_wide_solver_launch_authorized"
        )
        is False,
        (
            "Historical pilot unexpectedly claims "
            "DOE-wide solver authorization."
        ),
    )


    next_trial = preflight.get(
        "next_trial"
    )

    require(
        isinstance(
            next_trial,
            dict,
        )
        and next_trial.get(
            "run_id"
        )
        == EXPECTED_ACCEPTED_RUN_ID
        and next_trial.get(
            "trial_index"
        )
        == 2,
        "Pilot preflight CAL_02 identity drift.",
    )


    deck = preflight.get(
        "deck"
    )

    require(
        isinstance(
            deck,
            dict,
        ),
        "Pilot preflight deck record malformed.",
    )

    deck_path = (
        ROOT
        / Path(
            str(
                deck.get(
                    "relative_path"
                )
            )
        )
    ).resolve()

    require(
        deck_path.is_file(),
        "Historical pilot input deck is missing.",
    )

    require(
        sha256(
            deck_path
        )
        == deck.get(
            "sha256"
        )
        == "d5af61f667727449d4de21e5e3db08ad7e61e1e6700c2ee4f1e58214d8d5487a",
        "Pilot input-deck SHA drift.",
    )


    # ==========================================================================
    # Solver manifest + artifact contract
    # ==========================================================================

    require(
        manifest.get(
            "run_id"
        )
        == EXPECTED_ACCEPTED_RUN_ID,
        "Pilot manifest run identity drift.",
    )

    require(
        manifest.get(
            "case_hash"
        )
        == EXPECTED_CASE_HASH,
        "Pilot manifest case hash drift.",
    )

    require(
        manifest.get(
            "disposition"
        )
        == "succeeded",
        "Pilot solver manifest is not succeeded.",
    )

    require(
        manifest.get(
            "return_code"
        )
        == 0,
        "Pilot solver return code is not zero.",
    )

    require(
        manifest.get(
            "job_finished"
        )
        is True,
        "Pilot solver manifest lacks Job finished.",
    )

    require(
        manifest.get(
            "accepted_increment_count"
        )
        == 20,
        "Pilot solver manifest does not record 20 increments.",
    )

    require(
        manifest.get(
            "final_step"
        )
        == 20,
        "Pilot solver final-step drift.",
    )


    artifact_sha = certificate.get(
        "artifact_sha256"
    )

    require(
        isinstance(
            artifact_sha,
            dict,
        ),
        "Pilot certificate artifact hash map malformed.",
    )

    require(
        artifact_sha.get(
            "manifest"
        )
        == EXPECTED[
            "pilot_manifest"
        ],
        "Pilot certificate/manifest SHA binding drift.",
    )

    manifest_artifacts = manifest.get(
        "artifacts"
    )

    require(
        isinstance(
            manifest_artifacts,
            list,
        ),
        "Pilot manifest artifact list malformed.",
    )

    manifest_by_role = {
        row.get("role"): row.get("sha256")
        for row in manifest_artifacts
        if isinstance(
            row,
            dict,
        )
    }

    for role in (
        "cvg",
        "dat",
        "frd",
        "input_deck",
        "sta",
        "stdout",
    ):

        require(
            artifact_sha.get(
                role
            )
            == manifest_by_role.get(
                role
            ),
            (
                f"Pilot certificate/manifest artifact "
                f"SHA drift for {role}."
            ),
        )


    # ==========================================================================
    # Canonical FEM-Atlas evidence projection
    # ==========================================================================

    scope = certificate.get(
        "scope_limitation"
    )

    if not isinstance(
        scope,
        str,
    ) or not scope.strip():

        scope = (
            "Historical Phase-3 diversified aluminium pilot "
            "full-physics acceptance. Evidence registration only; "
            "production DOE authorization, ROM target extraction, "
            "dataset admission, partitioning, and holdout access "
            "remain separate governed decisions."
        )


    entry = {
        "kind": (
            "DIVERSIFIED_FULL_PHYSICS_ACCEPTED"
        ),
        "path": relative(
            path
        ),
        "sha256": EXPECTED[
            "pilot_certificate"
        ],
        "accepted_run_id": (
            EXPECTED_ACCEPTED_RUN_ID
        ),
        "disposition": (
            "GOVERNED_FULL_PHYSICS_ACCEPTED"
        ),
        "certification_scope": scope,
        "run_directory": relative(
            path.parent
        ),
        "run_directory_status": (
            "LOCATED"
        ),
    }


    return {
        "case_id": (
            EXPECTED_CASE_ID
        ),
        "case_hash": (
            EXPECTED_CASE_HASH
        ),
        "case_run_id": (
            EXPECTED_CASE_RUN_ID
        ),
        "entry": entry,
        "record": certificate,
    }


def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "Admit the historical Phase-3 diversified "
            "aluminium pilot as accepted FEM evidence. "
            "This is NOT ROM dataset admission."
        )
    )

    parser.add_argument(
        "--apply",
        action="store_true",
    )

    args = parser.parse_args()


    # ==========================================================================
    # Immutable source boundaries
    # ==========================================================================

    require(
        sha256(
            ATLAS_PATH
        )
        == EXPECTED[
            "atlas_before"
        ],
        (
            "FEM Atlas SHA does not match reviewed "
            "post-W02 reconciliation state."
        ),
    )

    require(
        sha256(
            BASE_PATH
        )
        == EXPECTED[
            "base_builder"
        ],
        "Base FEM-Atlas builder SHA drift.",
    )

    require(
        sha256(
            GOVERNED_ADAPTER_PATH
        )
        == EXPECTED[
            "governed_adapter"
        ],
        "Generic governed-wave evidence adapter SHA drift.",
    )


    base = load_module(
        "threadrom_phase3_fem_atlas_base",
        BASE_PATH,
    )

    governed = load_module(
        "threadrom_governed_wave_fem_evidence_adapter",
        GOVERNED_ADAPTER_PATH,
    )


    previous = load_json(
        ATLAS_PATH
    )

    old_cases = previous.get(
        "cases"
    )

    require(
        isinstance(
            old_cases,
            list,
        ),
        "Existing FEM Atlas case registry malformed.",
    )

    require(
        len(
            old_cases
        )
        == 38,
        (
            "Expected exactly 38 cases before "
            "historical-pilot reconciliation."
        ),
    )


    previous_sources = sorted({
        evidence[
            "path"
        ]
        for case in old_cases
        for evidence in case.get(
            "evidence",
            []
        )
    })


    pilot_relative = relative(
        PILOT_CERT
    )

    require(
        pilot_relative
        not in previous_sources,
        (
            "Historical pilot certificate is already "
            "registered in FEM Atlas."
        ),
    )


    sources = sorted(
        set(
            previous_sources
            + [
                pilot_relative
            ]
        )
    )


    original_evidence_entry = (
        base.evidence_entry
    )


    def adapted_evidence_entry(
        source_path,
    ):

        candidate = (
            ROOT
            / Path(
                source_path
            )
        ).resolve()


        if (
            candidate
            == PILOT_CERT.resolve()
        ):

            return build_pilot_evidence_entry(
                base=base,
                source_path=source_path,
            )


        if (
            candidate.name
            == EXPECTED_CERTIFICATE_FILENAME
        ):

            closure_cases = (
                load_governed_closure_cases(
                    candidate
                )
            )

            return governed.build_governed_wave_evidence_entry(
                base=base,
                source_path=source_path,
                closure_cases=closure_cases,
            )


        return original_evidence_entry(
            source_path
        )


    base.evidence_entry = (
        adapted_evidence_entry
    )


    policy, policy_sha, boundaries = (
        base.read_policy()
    )


    cases = base.assemble_cases(
        sources,
        policy,
        policy_sha,
        boundaries,
    )


    (
        added_cases,
        added_evidence,
    ) = base.check_prior_atlas(
        cases,
        previous,
    )


    require(
        len(
            cases
        )
        == 39,
        (
            "Historical-pilot projection did not "
            f"produce 39 cases; found {len(cases)}."
        ),
    )

    require(
        added_cases
        == [
            EXPECTED_CASE_ID
        ],
        (
            "Historical-pilot projection added "
            f"unexpected cases: {added_cases}"
        ),
    )

    require(
        added_evidence
        == [
            pilot_relative
        ],
        (
            "Historical-pilot projection added "
            f"unexpected evidence: {added_evidence}"
        ),
    )


    pilot_cases = [
        case
        for case in cases
        if case.get(
            "case_id"
        )
        == EXPECTED_CASE_ID
    ]

    require(
        len(
            pilot_cases
        )
        == 1,
        "Expected exactly one pilot case projection.",
    )

    pilot_case = (
        pilot_cases[0]
    )

    require(
        pilot_case.get(
            "rom_admission_status"
        )
        == "NOT_EVALUATED",
        "Pilot projection unexpectedly changes ROM status.",
    )

    require(
        pilot_case.get(
            "dataset_partition"
        )
        is None,
        "Pilot projection unexpectedly assigns dataset partition.",
    )

    require(
        pilot_case.get(
            "engineering_inputs",
            {},
        ).get(
            "configuration_status"
        )
        == "NEW_CAMPAIGN_INPUT_ADAPTER_REQUIRED",
        (
            "Pilot projection configuration boundary "
            "differs from governed diversified evidence."
        ),
    )


    mode = (
        "APPLY"
        if args.apply
        else "DRY_RUN"
    )


    print()
    print("=" * 116)
    print(
        "THREADROM - HISTORICAL ALUMINIUM PILOT "
        "ACCEPTED-FEM EVIDENCE ADMISSION V1"
    )
    print("=" * 116)

    print(
        "Mode                       :",
        mode,
    )
    print(
        "Pilot case                 :",
        EXPECTED_CASE_ID,
    )
    print(
        "Pilot accepted run         :",
        EXPECTED_ACCEPTED_RUN_ID,
    )
    print(
        "Certificate SHA            :",
        EXPECTED[
            "pilot_certificate"
        ],
    )
    print(
        "Preflight SHA              :",
        EXPECTED[
            "pilot_preflight"
        ],
    )
    print(
        "Manifest SHA               :",
        EXPECTED[
            "pilot_manifest"
        ],
    )

    print()
    print(
        "Distinct cases before      :",
        len(
            old_cases
        ),
    )
    print(
        "Distinct cases planned     :",
        len(
            cases
        ),
    )
    print(
        "Evidence records before    :",
        len(
            previous_sources
        ),
    )
    print(
        "Evidence records planned   :",
        len(
            sources
        ),
    )
    print(
        "New case identities        :",
        len(
            added_cases
        ),
    )
    print(
        "New acceptance evidence    :",
        len(
            added_evidence
        ),
    )

    print()
    print(
        "Evidence kind              :",
        "DIVERSIFIED_FULL_PHYSICS_ACCEPTED",
    )
    print(
        "Configuration status       :",
        "NEW_CAMPAIGN_INPUT_ADAPTER_REQUIRED",
    )
    print(
        "ROM admission              :",
        "NOT_EVALUATED",
    )
    print(
        "Dataset partition          :",
        "None",
    )


    if args.apply:

        # ----------------------------------------------------------------------
        # APPLY deliberately delegates persistence to the canonical base builder
        # after installing the exact same evidence routing validated above.
        # ----------------------------------------------------------------------

        base.SUPPORTED[
            EXPECTED_CERTIFICATE_FILENAME
        ] = (
            "DIVERSIFIED_FULL_PHYSICS_ACCEPTED"
        )

        old_argv = sys.argv[:]

        try:

            sys.argv = [
                str(
                    BASE_PATH
                ),
                "--add",
                pilot_relative,
            ]

            base.main()

        finally:

            sys.argv = old_argv


        require(
            sha256(
                ATLAS_PATH
            )
            != EXPECTED[
                "atlas_before"
            ],
            (
                "APPLY returned without changing "
                "FEM Atlas SHA."
            ),
        )


        persisted = load_json(
            ATLAS_PATH
        )

        persisted_cases = (
            persisted.get(
                "cases"
            )
        )

        require(
            isinstance(
                persisted_cases,
                list,
            )
            and len(
                persisted_cases
            )
            == 39,
            "Persisted FEM Atlas does not contain 39 cases.",
        )


        print()
        print(
            "FEM Atlas persisted        : YES"
        )
        print(
            "FEM Atlas JSON SHA         :",
            sha256(
                ATLAS_PATH
            ),
        )
        print(
            "Disposition                : "
            "HISTORICAL_PILOT_ACCEPTED_FEM_EVIDENCE_ADMITTED"
        )

    else:

        print()
        print(
            "FEM Atlas persisted        : NO"
        )
        print(
            "Disposition                : "
            "VALIDATED_HISTORICAL_PILOT_EVIDENCE_PLAN_ONLY"
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
    print("=" * 116)


if __name__ == "__main__":
    main()
