from __future__ import annotations

import hashlib
import json

from dataclasses import dataclass
from pathlib import Path

from threadrom.factory.production_doe_case_registry import (
    resolve_governed_c01_case,
)
from threadrom.factory.production_doe_completed_trial import (
    verify_completed_trial,
)


EXPECTED_GATE0_SHA256 = (
    "1de14304d291c8b5c4dfd763bafec414"
    "92128b2cba8eb9471b13c1390b6ecad6"
)


GATE0_CASE_IDS = frozenset(
    f"D-INT-{number:03d}" for number in range(12, 17)
)


@dataclass(frozen=True, slots=True)
class Gate0Trial1Evidence:
    case_id: str
    run_id: str
    preparation_sha256: str
    deck_sha256: str
    gate0_sha256: str
    completion_status: str
    completed_dat_sha256: str | None


def sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as stream:
        for chunk in iter(
            lambda: stream.read(8 * 1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def inspect_gate0_trial1(
    *,
    repo_root: Path,
    requested_case_id: str,
) -> Gate0Trial1Evidence:
    """Verify C01 Gate-0 Trial-1 evidence without executing FEM.

    This checks local evidence consistency. It does not independently
    authorize continuation or certify full-system equilibrium.
    """

    root = repo_root.resolve(strict=True)
    campaign_root = (
        root
        / "simulations/staging/phase3_cp8_production_doe"
        / "TRM-PDOE-C01"
    )

    governed_case = resolve_governed_c01_case(
        repo_root=root,
        requested_case_id=requested_case_id,
    )

    gate0_path = (
        campaign_root
        / "production_doe_gate0_execution_certification.json"
    )
    gate0_sha = sha256(gate0_path)

    if gate0_sha != EXPECTED_GATE0_SHA256:
        raise RuntimeError(
            "Frozen Gate-0 certification SHA-256 drift."
        )
    gate0 = json.loads(
        gate0_path.read_text(encoding="utf-8-sig")
    )

    authorization = gate0["execution_authorization"]

    authorized_ids = authorization["authorized_case_ids"]
    authorized_runs = authorization["authorized_run_ids"]

    if (
        gate0.get("record_status") != "FINAL"
        or authorization["authorized"] is not True
        or authorization["additional_calibration_trial_authorized"]
        is not False
        or authorization["blind_holdout_execution_authorized"]
        is not False
        or authorization["maximum_concurrent_calculix_runs"] != 4
        or not isinstance(authorized_ids, list)
        or len(authorized_ids) != 5
        or set(authorized_ids) != GATE0_CASE_IDS
        or len(set(authorized_ids)) != len(authorized_ids)
        or requested_case_id not in GATE0_CASE_IDS
        or not isinstance(authorized_runs, list)
        or len(authorized_runs) != 5
        or len(set(authorized_runs)) != len(authorized_runs)
    ):
        raise RuntimeError(
            "Frozen Gate-0 certification scope or policy mismatch."
        )

    run_id = (
        f"{governed_case.case_run_id}_cal_01_wsv21_rfobs1"
    )

    if run_id not in authorized_runs:
        raise RuntimeError(
            "Requested Trial-1 run is absent from Gate-0 scope."
        )

    certified_matches = [
        record
        for record in gate0["certified_gate0_cases"]
        if record["case_id"] == requested_case_id
    ]

    if len(certified_matches) != 1:
        raise RuntimeError(
            "Gate-0 case certification missing or ambiguous."
        )

    certified = certified_matches[0]

    if (
        certified["authorized_run_id"] != run_id
        or certified["canonical_case_run_id"]
        != governed_case.case_run_id
        or certified["case_hash"] != governed_case.case_hash
        or type(certified["authorized_trial_index"]) is not int
        or certified["authorized_trial_index"] != 1
        or certified["reaction_carrier_count"] != 9
        or certified["equilibrium_tolerance_changed"] is not False
        or certified["full_system_equilibrium_pass_claimed"] is not False
    ):
        raise RuntimeError(
            "Gate-0 case certification identity or scope mismatch."
        )

    trial_dir = (
        campaign_root
        / "solver_preparation"
        / governed_case.case_run_id
        / run_id
    )

    prep_path = (
        trial_dir
        / "production_doe_reaction_observable_revision_record.json"
    )
    prep_sha = sha256(prep_path)
    sidecar_path = prep_path.with_suffix(".sha256")

    if (
        prep_path.relative_to(root).as_posix()
        != certified["rfobs1_preparation_relative_path"]
        or prep_sha != certified["rfobs1_preparation_sha256"]
        or sidecar_path.relative_to(root).as_posix()
        != certified["rfobs1_preparation_sidecar_relative_path"]
        or sha256(sidecar_path)
        != certified["rfobs1_preparation_sidecar_sha256"]
    ):
        raise RuntimeError(
            "Trial-1 preparation or sidecar differs from "
            "the independently frozen Gate-0 case record."
        )

    expected_sidecar = (
        f"{prep_sha}  {prep_path.name}\n"
    )

    if (
        sidecar_path.read_text(encoding="ascii")
        != expected_sidecar
    ):
        raise RuntimeError(
            "Gate-0 Trial-1 preparation sidecar mismatch."
        )

    prep = json.loads(
        prep_path.read_text(encoding="utf-8-sig")
    )

    if (
        prep["case"]["case_id"] != requested_case_id
        or prep["case"]["case_hash"]
        != governed_case.case_hash
        or prep["trial"]["run_id"] != run_id
        or prep["trial"]["trial_index"] != 1
    ):
        raise RuntimeError(
            "Gate-0 Trial-1 preparation identity mismatch."
        )

    deck_path = trial_dir / f"{run_id}.inp"
    deck_sha = prep["deck"]["sha256"]

    if (
        deck_path.relative_to(root).as_posix()
        != certified["rfobs1_deck_relative_path"]
        or deck_sha != certified["rfobs1_deck_sha256"]
        or prep["trial"]["delta_temperature_c"]
        != certified["frozen_delta_temperature_c"]
    ):
        raise RuntimeError(
            "Trial-1 deck or frozen temperature differs "
            "from its Gate-0 case certification."
        )

    if (
        prep["deck"]["relative_path"]
        != deck_path.relative_to(root).as_posix()
        or deck_path.stat().st_size
        != prep["deck"]["size_bytes"]
        or sha256(deck_path) != deck_sha
    ):
        raise RuntimeError(
            "Gate-0 Trial-1 deck identity, size or SHA mismatch."
        )

    manifest_path = trial_dir / "fem_run_manifest.json"

    if not manifest_path.exists():
        return Gate0Trial1Evidence(
            case_id=requested_case_id,
            run_id=run_id,
            preparation_sha256=prep_sha,
            deck_sha256=deck_sha,
            gate0_sha256=gate0_sha,
            completion_status="PENDING_COMPLETED_MANIFEST",
            completed_dat_sha256=None,
        )

    completed = verify_completed_trial(
        repo_root=root,
        manifest_path=manifest_path,
        expected_run_id=run_id,
        expected_case_hash=governed_case.case_hash,
        expected_deck_sha256=deck_sha,
    )

    return Gate0Trial1Evidence(
        case_id=requested_case_id,
        run_id=run_id,
        preparation_sha256=prep_sha,
        deck_sha256=deck_sha,
        gate0_sha256=gate0_sha,
        completion_status="COMPLETED_INPUT_EVIDENCE_VERIFIED",
        completed_dat_sha256=completed.dat_sha256,
    )
