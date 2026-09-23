"""ThreadROM Phase-3 accepted-FEM atlas.

Evidence registry, not a ROM dataset-admission certificate.
Reads small governed acceptance records; never launches a solver.
Initial inventory: the 20 known C01 M10 cases and two cross-size sentinels.

Later usage:
    python scripts/build_phase3_fem_atlas.py --add RELATIVE_ACCEPTANCE_RECORD
    python scripts/build_phase3_fem_atlas.py --audit

--add registers new accepted evidence without repeating the initial filesystem
search. --audit finds unregistered files with supported acceptance filenames.
New evidence schemas need an explicit reviewed adapter; they are never guessed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
import re
import sys
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ATLAS_DIR = ROOT / "docs" / "phase3_fem_atlas"
ATLAS_JSON = ATLAS_DIR / "atlas.json"
ATLAS_CSV = ATLAS_DIR / "cases.csv"
ATLAS_INDEX = ATLAS_DIR / "INDEX.md"
C01 = (
    ROOT
    / "simulations/staging/phase3_cp8_production_doe/TRM-PDOE-C01"
)
CROSS = (
    ROOT
    / "simulations/staging/phase3_cp11_cross_size_fem_campaign"
    / "physics_certification"
)
BLOCKED = re.compile(r"holdout|blind[_-]?eval|sealed[_-]?eval", re.I)

SUPPORTED = {
    "production_doe_accepted_fem_evidence.json": "CALIBRATION_ACCEPTED",
    "independent_governed_physics_certificate.json": "13_HARD_GATES_CERTIFIED",
    "cross_size_fem_physics_certificate.json": "CROSS_SIZE_PHYSICS_CERTIFIED",
}

COLUMNS = [
    "case_id",
    "case_hash",
    "thread_designation",
    "evidence_classes",
    "accepted_run_ids",
    "target_preload_n",
    "head_member_thickness_mm",
    "nut_member_thickness_mm",
    "member_outer_diameter_mm",
    "member_clearance_hole_diameter_mm",
    "bolt_material_id",
    "nut_material_id",
    "head_member_material_id",
    "nut_member_material_id",
    "thread_friction_coefficient",
    "head_bearing_friction_coefficient",
    "nut_bearing_friction_coefficient",
    "member_interface_friction_coefficient",
    "external_axial_load_n",
    "u_preload",
    "u_head_thickness",
    "u_radial_geometry",
    "configuration_status",
    "rom_admission_status",
    "dataset_partition",
    "primary_evidence_path",
    "primary_run_directory",
    "evidence_record_count",
]


def fail(message: str) -> None:
    raise RuntimeError(message)


def relative_path(path: Path) -> str:
    resolved = path.resolve()
    if not resolved.is_relative_to(ROOT):
        fail(f"Path escapes the repository: {path}")
    relative = resolved.relative_to(ROOT).as_posix()
    if BLOCKED.search(relative):
        fail(f"Sealed/evaluation path is forbidden: {relative}")
    return relative


def safe_path(relative: str) -> Path:
    if not isinstance(relative, str) or not relative:
        fail("Missing relative source path.")
    path = ROOT / relative
    relative_path(path)
    return path


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read_json(path: Path, max_bytes: int = 32_000_000):
    rel = relative_path(path)
    if not path.is_file():
        fail(f"Evidence record missing: {rel}")

    size = path.stat().st_size
    if size > max_bytes:
        fail(f"Unexpectedly large metadata record: {rel} ({size} bytes)")

    raw = path.read_bytes()
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        fail(f"Invalid JSON at {rel}: {exc}")

    if not isinstance(data, dict):
        fail(f"Expected a JSON object: {rel}")

    return data, sha256_bytes(raw)


def read_policy():
    path = ROOT / "config/phase3_production_doe.toml"
    relative_path(path)
    raw = path.read_bytes()
    policy = tomllib.loads(raw.decode("utf-8-sig"))

    if (
        policy["identity"]["status"] != "frozen"
        or policy["fixed"]["fastener"]["thread_designation"] != "M10x1.5"
        or policy["design"]["normalized_dimension_order"]
        != [
            "target_preload",
            "head_member_thickness",
            "radial_geometry_fraction",
        ]
    ):
        fail("C01 policy differs from the reconciled engineering domain.")

    points = {
        item["case_id"]: item["normalized_coordinates"]
        for item in policy["mandatory_design_points"]
    }

    if points.get("D-BND-004") != [1.0, 0.0, 1.0]:
        fail("D-BND-004 boundary definition changed.")

    return policy, sha256_bytes(raw), points


def initial_sources() -> list[str]:
    solver = C01 / "solver_preparation"

    accepted = sorted(
        solver.glob(
            "trm_fem_*/production_doe_accepted_fem_evidence.json"
        )
    )
    independent = sorted(
        solver.glob(
            "trm_fem_*/*/independent_governed_physics_certificate.json"
        )
    )
    sentinels = [
        CROSS
        / "TRM-XFEM-M8-001/cross_size_fem_physics_certificate.json",
        CROSS
        / "TRM-XFEM-M12-001/cross_size_fem_physics_certificate.json",
    ]

    if (len(accepted), len(independent)) != (15, 5):
        fail(
            "Initial C01 evidence inventory differs from 15 accepted "
            "calibrations plus 5 independent physics certificates."
        )

    paths = accepted + independent + sentinels
    if len(paths) != 22 or len(set(paths)) != 22:
        fail("Expected exactly 22 initial acceptance-record paths.")

    return [relative_path(path) for path in paths]


def initial_m10_membership() -> set[str]:
    return (
        {f"D-INT-{index:03d}" for index in range(1, 17)}
        | {f"D-BND-{index:03d}" for index in range(1, 5)}
    )


def discover_unregistered(registered: set[str]) -> list[str]:
    """Optional filenames-only audit; not run on every atlas update."""
    found = []

    for base in (
        ROOT / "simulations/staging",
        ROOT / "simulations/archive",
    ):
        if not base.is_dir():
            continue

        for directory, subdirs, filenames in os.walk(base):
            subdirs[:] = [
                name
                for name in subdirs
                if not BLOCKED.search(name)
            ]

            if BLOCKED.search(
                Path(directory).relative_to(ROOT).as_posix()
            ):
                subdirs[:] = []
                continue

            for name in filenames:
                if name not in SUPPORTED:
                    continue
                relative = relative_path(Path(directory) / name)
                if relative not in registered:
                    found.append(relative)

    return sorted(set(found))


def evidence_entry(path_string: str):
    path = safe_path(path_string)

    if path.name not in SUPPORTED:
        fail(
            "Unsupported acceptance-record filename: "
            f"{path_string}. A governed schema adapter is required."
        )

    if not (
        path.is_relative_to(ROOT / "simulations/staging")
        or path.is_relative_to(ROOT / "simulations/archive")
    ):
        fail("Acceptance evidence must be under simulations/staging or archive.")

    record, digest = read_json(path)
    kind = SUPPORTED[path.name]

    if kind == "CALIBRATION_ACCEPTED":
        case = record.get("case")
        accepted = record.get("accepted_calibration")

        if not isinstance(case, dict) or not isinstance(accepted, dict):
            fail(f"Malformed accepted-calibration record: {path_string}")

        if (
            record.get("record_status") != "FINAL"
            or record.get("overall_disposition")
            != "PRODUCTION_DOE_FEM_CALIBRATION_ACCEPTED"
            or accepted.get("decision", {}).get("disposition") != "accept"
        ):
            fail(f"Calibration evidence is not finally accepted: {path_string}")

        case_id = case.get("case_id")
        case_hash = case.get("case_hash")
        case_run_id = case.get("case_run_id")
        accepted_run_id = accepted.get("accepted_run_id")
        disposition = record["overall_disposition"]
        scope = (
            "Governed FEM calibration accepted; broader physics and "
            "ROM dataset admission are separate decisions."
        )

        candidate_run_dir = path.parent / str(accepted_run_id)

    elif kind == "13_HARD_GATES_CERTIFIED":
        if (
            record.get("record_status") != "FINAL"
            or record.get("disposition")
            != "GOVERNED_13_HARD_GATES_CERTIFIED"
            or record.get("governed_hard_gates_passed") != 13
        ):
            fail(f"Independent physics record is not certified: {path_string}")

        case_id = record.get("case_id")
        case_hash = record.get("case_hash")
        case_run_id = record.get("case_run_id")
        accepted_run_id = record.get("run_id")
        disposition = record["disposition"]
        scope = record.get("scope_limitation")
        candidate_run_dir = path.parent

    else:
        physics = record.get("physics_acceptance")
        if (
            record.get("overall_disposition")
            != "CROSS_SIZE_FEM_PHYSICS_CERTIFIED"
            or not isinstance(physics, dict)
            or physics.get("disposition") != "pass"
        ):
            fail(f"Cross-size physics record is not certified: {path_string}")

        case_id = record.get("sentinel_id")
        case_hash = record.get("case_hash")
        case_run_id = record.get("case_run_id")
        accepted_run_id = record.get("accepted_run_id")
        disposition = record["overall_disposition"]
        scope = (
            "Cross-size FEM physics certified under its recorded policy; "
            "full-system external-support-equilibrium acceptance is not "
            "claimed by the sentinel governance."
        )
        candidate_run_dir = (
            CROSS / str(case_run_id) / str(accepted_run_id)
        )

    if (
        not isinstance(case_id, str)
        or not case_id
        or not isinstance(case_hash, str)
        or not re.fullmatch(r"[0-9a-f]{64}", case_hash)
        or not isinstance(case_run_id, str)
        or not re.fullmatch(r"trm_fem_[0-9a-f]{12}", case_run_id)
        or not isinstance(accepted_run_id, str)
        or not accepted_run_id
    ):
        fail(f"Invalid governed case/run identity: {path_string}")

    if kind != "CROSS_SIZE_PHYSICS_CERTIFIED" and not case_hash.startswith(
        case_run_id.removeprefix("trm_fem_")
    ):
        fail(f"Case hash/run ID mismatch: {path_string}")

    if kind == "CROSS_SIZE_PHYSICS_CERTIFIED":
        if not case_id.startswith("TRM-XFEM-"):
            fail(f"Unexpected sentinel identity: {path_string}")

    run_directory = (
        relative_path(candidate_run_dir)
        if candidate_run_dir.is_dir()
        else None
    )

    entry = {
        "kind": kind,
        "path": path_string,
        "sha256": digest,
        "accepted_run_id": accepted_run_id,
        "disposition": disposition,
        "certification_scope": scope,
        "run_directory": run_directory,
        "run_directory_status": (
            "LOCATED" if run_directory else "NOT_VERIFIED"
        ),
    }

    return {
        "case_id": case_id,
        "case_hash": case_hash,
        "case_run_id": case_run_id,
        "record": record,
        "entry": entry,
    }


def c01_inputs(group, policy, policy_sha, boundary_points):
    case_id = group["case_id"]
    case_hash = group["case_hash"]
    case_run_id = group["case_run_id"]

    if case_id not in initial_m10_membership():
        fail(f"Unexpected C01 case identity: {case_id}")

    prepared_dir = C01 / "prepared_cases" / case_run_id
    prep_path = prepared_dir / "production_doe_preparation_record.json"

    source_metadata = []

    if prep_path.is_file():
        preparation, prep_sha = read_json(prep_path)
        prep_case = preparation.get("case")
        campaign = preparation.get("campaign")

        if (
            not isinstance(prep_case, dict)
            or not isinstance(campaign, dict)
            or prep_case.get("case_id") != case_id
            or prep_case.get("case_hash") != case_hash
            or campaign.get("policy_sha256") != policy_sha
        ):
            fail(f"Preparation/policy identity mismatch: {case_id}")

        coordinates = prep_case.get("normalized_coordinates")
        source_metadata.append({
            "kind": "GOVERNED_PREPARATION",
            "path": relative_path(prep_path),
            "sha256": prep_sha,
        })

    elif case_id == "D-BND-004":
        reuse_path = (
            prepared_dir / "production_doe_geometry_mesh_reuse_record.json"
        )
        reuse, reuse_sha = read_json(reuse_path)

        source = reuse.get("source")
        if (
            reuse.get("record_status") != "FINAL"
            or reuse.get("overall_disposition")
            != "GEOMETRY_AND_MESH_REUSE_CERTIFIED"
            or not isinstance(source, dict)
            or source.get("case_id") != "D-BND-002"
        ):
            fail("D-BND-004 governed geometry/mesh reuse is not certified.")

        source_prep = safe_path(
            source.get("preparation_record_relative_path")
        )

        if (
            not source_prep.is_file()
            or sha256_bytes(source_prep.read_bytes())
            != source.get("preparation_record_sha256")
        ):
            fail("D-BND-004 source-preparation hash mismatch.")

        coordinates = boundary_points["D-BND-004"]
        source_metadata.append({
            "kind": "GEOMETRY_MESH_REUSE",
            "path": relative_path(reuse_path),
            "sha256": reuse_sha,
            "source_case_id": "D-BND-002",
            "source_preparation_path": relative_path(source_prep),
            "source_preparation_sha256":
                source["preparation_record_sha256"],
        })

    else:
        fail(f"No governed C01 preparation/reuse evidence: {case_id}")

    if (
        not isinstance(coordinates, list)
        or len(coordinates) != 3
        or any(
            not isinstance(x, (float, int))
            or isinstance(x, bool)
            or not math.isfinite(x)
            or not 0.0 <= x <= 1.0
            for x in coordinates
        )
    ):
        fail(f"Invalid normalized C01 coordinates: {case_id}")

    if (
        case_id in boundary_points
        and coordinates != boundary_points[case_id]
    ):
        fail(f"Frozen boundary-point mismatch: {case_id}")

    u_preload, u_head, u_radial = coordinates
    target = 15000.0 + 5000.0 * u_preload

    for item in group["source_records"]:
        if item["entry"]["kind"] == "CALIBRATION_ACCEPTED":
            recorded_target = item["record"]["case"]["target_preload_n"]
            if abs(recorded_target - target) > 0.01:
                fail(f"Preload/case-coordinate mismatch: {case_id}")

            governance = item["record"].get("governance")
            if isinstance(governance, dict):
                saved_sha = governance.get("doe_policy_sha256")
                if saved_sha is not None and saved_sha != policy_sha:
                    fail(f"Accepted-record policy mismatch: {case_id}")

    fixed = policy["fixed"]

    return {
        "thread_designation": "M10x1.5",
        "target_preload_n": target,
        "head_member_thickness_mm": 8.0 + 2.0 * u_head,
        "nut_member_thickness_mm": 12.0 - 2.0 * u_head,
        "member_outer_diameter_mm": 30.0 + 6.0 * u_radial,
        "member_clearance_hole_diameter_mm": 11.0 + u_radial,
        "bolt_material_id": fixed["fastener"]["bolt_material_id"],
        "nut_material_id": fixed["fastener"]["nut_material_id"],
        "head_member_material_id":
            fixed["materials"]["head_side_member_material_id"],
        "nut_member_material_id":
            fixed["materials"]["nut_side_member_material_id"],
        "thread_friction_coefficient":
            fixed["interfaces"]["thread_friction_coefficient"],
        "head_bearing_friction_coefficient":
            fixed["interfaces"]["head_bearing_friction_coefficient"],
        "nut_bearing_friction_coefficient":
            fixed["interfaces"]["nut_bearing_friction_coefficient"],
        "member_interface_friction_coefficient":
            fixed["interfaces"]["member_interface_friction_coefficient"],
        "external_axial_load_n":
            fixed["loading"]["external_axial_load_n"],
        "normalized_coordinates": coordinates,
        "configuration_status": "C01_POLICY_AND_CASE_COORDINATES_VERIFIED",
        "configuration_sources": source_metadata,
        "fastener_fixed_configuration": fixed["fastener"],
    }


def sentinel_inputs(group):
    """Recover a historical sentinel only after canonical hash parity."""
    from dataclasses import asdict

    from threadrom.case.serialization import case_sha256
    from threadrom.factory.cross_size_fem_sentinel import (
        build_phase3_cross_size_fem_sentinels,
    )

    case_id = group["case_id"]

    if case_id not in {
        "TRM-XFEM-M8-001",
        "TRM-XFEM-M12-001",
    }:
        fail(f"Unexpected baseline sentinel identity: {case_id}")

    if len(group["source_records"]) != 1:
        fail(f"{case_id}: unexpected historical evidence count.")

    record = group["source_records"][0]["record"]
    reference = record.get("preparation_record")

    if not isinstance(reference, dict):
        fail(f"{case_id}: preparation reference missing.")

    path = safe_path(reference.get("path"))
    preparation, preparation_sha = read_json(path)

    if (
        preparation_sha != reference.get("sha256")
        or preparation.get("case_hash") != group["case_hash"]
        or preparation.get("thread_designation")
        != record.get("thread_designation")
    ):
        fail(f"{case_id}: pinned historical preparation mismatch.")

    sentinels = {
        sentinel.definition.sentinel_id: sentinel
        for sentinel in build_phase3_cross_size_fem_sentinels()
    }

    if set(sentinels) != {
        "TRM-XFEM-M8-001",
        "TRM-XFEM-M12-001",
    }:
        fail("Cross-size builder returned unexpected sentinel identities.")

    sentinel = sentinels[case_id]
    reconstructed_hash = case_sha256(sentinel.case)

    if (
        reconstructed_hash != group["case_hash"]
        or reconstructed_hash != record.get("case_hash")
    ):
        fail(
            f"{case_id}: canonical case hash differs from historical FEM. "
            "Existing atlas configuration must remain unchanged."
        )

    if (
        sentinel.definition.thread_designation
        != record.get("thread_designation")
        or abs(
            sentinel.target_preload_n
            - float(record["target_preload_n"])
        ) > 1e-8
    ):
        fail(f"{case_id}: historical designation/preload mismatch.")

    product_case = json.loads(
        json.dumps(asdict(sentinel.case), sort_keys=True)
    )
    fastener = product_case["fastener"]
    members = product_case["members"]["layers"]
    interfaces = product_case["interfaces"]
    loading = product_case["loading"]

    if (
        len(members) != 2
        or members[0]["layer_id"] != "head_side_member"
        or members[1]["layer_id"] != "nut_side_member"
    ):
        fail(f"{case_id}: unexpected member-stack structure.")

    upper, lower = members

    if (
        fastener["bolt_material_id"] != fastener["nut_material_id"]
        or upper["material_id"] != lower["material_id"]
    ):
        fail(f"{case_id}: paired-material rule is not satisfied.")

    for field in (
        "outer_diameter_mm",
        "clearance_hole_diameter_mm",
    ):
        if upper[field] != lower[field]:
            fail(f"{case_id}: shared member geometry differs for {field}.")

    if abs(
        float(loading["target_preload_n"])
        - sentinel.target_preload_n
    ) > 1e-8:
        fail(f"{case_id}: case loading/preload mismatch.")

    return {
        "thread_designation": fastener["thread_designation"],
        "target_preload_n": sentinel.target_preload_n,
        "head_member_thickness_mm": upper["thickness_mm"],
        "nut_member_thickness_mm": lower["thickness_mm"],
        "member_outer_diameter_mm": upper["outer_diameter_mm"],
        "member_clearance_hole_diameter_mm":
            upper["clearance_hole_diameter_mm"],
        "bolt_material_id": fastener["bolt_material_id"],
        "nut_material_id": fastener["nut_material_id"],
        "head_member_material_id": upper["material_id"],
        "nut_member_material_id": lower["material_id"],
        "thread_friction_coefficient":
            interfaces["thread_friction_coefficient"],
        "head_bearing_friction_coefficient":
            interfaces["head_bearing_friction_coefficient"],
        "nut_bearing_friction_coefficient":
            interfaces["nut_bearing_friction_coefficient"],
        "member_interface_friction_coefficient":
            interfaces["member_interface_friction_coefficient"],
        "external_axial_load_n":
            loading["external_axial_load_n"],
        "normalized_coordinates": None,
        "configuration_status":
            "CROSS_SIZE_CANONICAL_CASE_HASH_VERIFIED",
        "configuration_sources": [
            {
                "kind": "PINNED_SENTINEL_PREPARATION",
                "path": relative_path(path),
                "sha256": preparation_sha,
            },
            {
                "kind": "HISTORICAL_CANONICAL_CASE_HASH_PARITY",
                "path":
                    "src/threadrom/factory/cross_size_fem_sentinel.py",
                "case_sha256": reconstructed_hash,
                "recovery_source_commit":
                    "993272112af8c828ad8a7f50037e87e7bbe8ebe5",
            },
        ],
        "fastener_fixed_configuration": fastener,
        "resolved_product_case": product_case,
    }


def unresolved_future_inputs(group):
    """Register future evidence without inventing unverified DOE coordinates."""
    record = group["source_records"][0]["record"]
    case = record.get("case")

    designation = record.get("thread_designation")
    target = record.get("target_preload_n")

    if isinstance(case, dict):
        designation = designation or case.get("thread_designation")
        target = target if target is not None else case.get(
            "target_preload_n"
        )

    if not isinstance(designation, str):
        designation = None
    if not isinstance(target, (int, float)) or isinstance(target, bool):
        target = None

    return {
        "thread_designation": designation,
        "target_preload_n": target,
        "head_member_thickness_mm": None,
        "nut_member_thickness_mm": None,
        "member_outer_diameter_mm": None,
        "member_clearance_hole_diameter_mm": None,
        "bolt_material_id": None,
        "nut_material_id": None,
        "head_member_material_id": None,
        "nut_member_material_id": None,
        "thread_friction_coefficient": None,
        "head_bearing_friction_coefficient": None,
        "nut_bearing_friction_coefficient": None,
        "member_interface_friction_coefficient": None,
        "external_axial_load_n": None,
        "normalized_coordinates": None,
        "configuration_status": "NEW_CAMPAIGN_INPUT_ADAPTER_REQUIRED",
        "configuration_sources": [],
        "fastener_fixed_configuration": None,
    }


def assemble_cases(source_paths, policy, policy_sha, boundary_points):
    groups = {}
    labels = {}

    for source_path in source_paths:
        item = evidence_entry(source_path)
        case_id = item["case_id"]
        case_hash = item["case_hash"]

        previous_hash = labels.setdefault(case_id, case_hash)
        if previous_hash != case_hash:
            fail(f"Case ID maps to multiple hashes: {case_id}")

        group = groups.setdefault(
            case_hash,
            {
                "case_id": case_id,
                "case_hash": case_hash,
                "case_run_id": item["case_run_id"],
                "source_records": [],
            },
        )

        if group["case_id"] != case_id:
            fail(f"Case hash maps to multiple case IDs: {case_hash}")

        if group["case_run_id"] != item["case_run_id"]:
            fail(f"Case hash has conflicting run IDs: {case_id}")

        group["source_records"].append(item)

    expected = (
        initial_m10_membership()
        | {"TRM-XFEM-M8-001", "TRM-XFEM-M12-001"}
    )
    if not expected.issubset(set(labels)):
        missing = sorted(expected - set(labels))
        fail(f"Previously reconciled baseline cases missing: {missing}")

    cases = []

    for group in groups.values():
        case_id = group["case_id"]
        paths = [
            item["entry"]["path"]
            for item in group["source_records"]
        ]

        if len(paths) != len(set(paths)):
            fail(f"Duplicate evidence path for case {case_id}")

        if case_id in initial_m10_membership():
            if not all(
                "TRM-PDOE-C01/" in path for path in paths
            ):
                fail(f"Baseline C01 case has evidence outside C01: {case_id}")

            inputs = c01_inputs(
                group, policy, policy_sha, boundary_points
            )

        elif case_id in {
            "TRM-XFEM-M8-001",
            "TRM-XFEM-M12-001",
        }:
            inputs = sentinel_inputs(group)

        else:
            inputs = unresolved_future_inputs(group)

        evidence = sorted(
            (item["entry"] for item in group["source_records"]),
            key=lambda entry: (entry["kind"], entry["path"]),
        )

        calibration = [
            entry for entry in evidence
            if entry["kind"] == "CALIBRATION_ACCEPTED"
        ]

        primary = calibration[0] if calibration else evidence[0]

        cases.append({
            "case_id": case_id,
            "case_hash": group["case_hash"],
            "case_run_id": group["case_run_id"],
            "engineering_inputs": inputs,
            "evidence": evidence,
            "primary_evidence_path": primary["path"],
            "primary_run_directory": primary["run_directory"],
            "rom_admission_status": "NOT_EVALUATED",
            "dataset_partition": None,
        })

    cases.sort(key=lambda case: case["case_id"])
    return cases


def check_prior_atlas(cases, previous, *, allow_cross_size_upgrade=False):
    if previous is None:
        return [], []

    if previous.get("schema_version") != 1:
        fail("Existing atlas schema is not supported.")

    old_cases = previous.get("cases")
    if not isinstance(old_cases, list):
        fail("Existing atlas has no case registry.")

    old_by_id = {
        case["case_id"]: case for case in old_cases
    }
    new_by_id = {
        case["case_id"]: case for case in cases
    }

    if len(old_by_id) != len(old_cases):
        fail("Existing atlas has duplicate case IDs.")

    missing = sorted(set(old_by_id) - set(new_by_id))
    if missing:
        fail(f"Existing atlas cases would disappear: {missing}")

    for case_id, old in old_by_id.items():
        new = new_by_id[case_id]

        if old["case_hash"] != new["case_hash"]:
            fail(f"Existing case identity changed: {case_id}")

        if old["engineering_inputs"] != new["engineering_inputs"]:
            old_inputs = old["engineering_inputs"]
            new_inputs = new["engineering_inputs"]

            allowed = (
                allow_cross_size_upgrade
                and case_id in {
                    "TRM-XFEM-M8-001",
                    "TRM-XFEM-M12-001",
                }
                and old_inputs.get("configuration_status")
                == "CROSS_SIZE_FULL_INPUTS_UNRESOLVED"
                and new_inputs.get("configuration_status")
                == "CROSS_SIZE_CANONICAL_CASE_HASH_VERIFIED"
                and old.get("rom_admission_status")
                == new.get("rom_admission_status")
                == "NOT_EVALUATED"
                and old.get("dataset_partition")
                == new.get("dataset_partition")
            )

            if allowed:
                for key, old_value in old_inputs.items():
                    if key in {
                        "configuration_status",
                        "configuration_sources",
                    }:
                        continue
                    if (
                        old_value is not None
                        and new_inputs.get(key) != old_value
                    ):
                        allowed = False
                        break

                if allowed:
                    old_sources = old_inputs.get(
                        "configuration_sources", []
                    )
                    new_sources = new_inputs.get(
                        "configuration_sources", []
                    )
                    allowed = all(
                        source in new_sources
                        for source in old_sources
                    )

            if not allowed:
                fail(
                    f"Existing case configuration changed: {case_id}. "
                    "A governed atlas migration is required."
                )

        old_sources = {
            source["path"]: source["sha256"]
            for source in old["evidence"]
        }
        new_sources = {
            source["path"]: source["sha256"]
            for source in new["evidence"]
        }

        for path, digest in old_sources.items():
            if new_sources.get(path) != digest:
                fail(
                    f"Previously registered evidence changed/disappeared: "
                    f"{path}"
                )

    added_cases = sorted(set(new_by_id) - set(old_by_id))
    old_sources = {
        source["path"]
        for case in old_cases
        for source in case["evidence"]
    }
    new_sources = {
        source["path"]
        for case in cases
        for source in case["evidence"]
    }
    added_evidence = sorted(new_sources - old_sources)

    return added_cases, added_evidence


def csv_content(cases):
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=COLUMNS)
    writer.writeheader()

    for case in cases:
        inputs = case["engineering_inputs"]
        u = inputs["normalized_coordinates"]
        sources = case["evidence"]

        row = {
            "case_id": case["case_id"],
            "case_hash": case["case_hash"],
            "thread_designation": inputs["thread_designation"],
            "evidence_classes": ";".join(sorted({
                source["kind"] for source in sources
            })),
            "accepted_run_ids": ";".join(sorted({
                source["accepted_run_id"] for source in sources
            })),
            "target_preload_n": inputs["target_preload_n"],
            "head_member_thickness_mm":
                inputs["head_member_thickness_mm"],
            "nut_member_thickness_mm":
                inputs["nut_member_thickness_mm"],
            "member_outer_diameter_mm":
                inputs["member_outer_diameter_mm"],
            "member_clearance_hole_diameter_mm":
                inputs["member_clearance_hole_diameter_mm"],
            "bolt_material_id": inputs["bolt_material_id"],
            "nut_material_id": inputs["nut_material_id"],
            "head_member_material_id":
                inputs["head_member_material_id"],
            "nut_member_material_id":
                inputs["nut_member_material_id"],
            "thread_friction_coefficient":
                inputs["thread_friction_coefficient"],
            "head_bearing_friction_coefficient":
                inputs["head_bearing_friction_coefficient"],
            "nut_bearing_friction_coefficient":
                inputs["nut_bearing_friction_coefficient"],
            "member_interface_friction_coefficient":
                inputs["member_interface_friction_coefficient"],
            "external_axial_load_n":
                inputs["external_axial_load_n"],
            "u_preload": u[0] if u else None,
            "u_head_thickness": u[1] if u else None,
            "u_radial_geometry": u[2] if u else None,
            "configuration_status": inputs["configuration_status"],
            "rom_admission_status": case["rom_admission_status"],
            "dataset_partition": case["dataset_partition"],
            "primary_evidence_path": case["primary_evidence_path"],
            "primary_run_directory": case["primary_run_directory"],
            "evidence_record_count": len(sources),
        }
        writer.writerow(row)

    return buffer.getvalue()


def markdown_content(cases, policy_sha):
    lines = [
        "# ThreadROM — Phase-3 accepted-FEM evidence atlas",
        "",
        "**Scope:** Indexed accepted/certified FEM evidence. "
        "This is not a frozen ROM dataset or a claim that every case has "
        "passed the same physics-certification gates.",
        "",
        f"**Indexed case identities:** {len(cases)}",
        "",
        "**Atlas files:** [Case table](cases.csv) · "
        "[Full evidence registry](atlas.json)",
        "",
        f"**Frozen C01 policy SHA256:** `{policy_sha}`",
        "",
        "| Case | Size | Evidence | Target preload (kN) | "
        "Configuration | Accepted result locator |",
        "|---|---|---|---:|---|---|",
    ]

    for case in cases:
        inputs = case["engineering_inputs"]
        path = case["primary_evidence_path"]
        link = f"../../{path}"
        evidence_classes = ", ".join(sorted({
            source["kind"] for source in case["evidence"]
        }))
        preload = inputs["target_preload_n"]
        preload_display = (
            f"{preload / 1000:.4f}"
            if isinstance(preload, (int, float))
            else "Unresolved"
        )

        lines.append(
            f'| `{case["case_id"]}` | '
            f'{inputs["thread_designation"] or "Unresolved"} | '
            f'{evidence_classes} | {preload_display} | '
            f'{inputs["configuration_status"]} | '
            f'[Acceptance record]({link}) |'
        )

    lines += [
        "",
        "## How to navigate a case",
        "",
        "Find its case ID in the table above. Open the acceptance record "
        "to see its certified disposition. The corresponding object in "
        "`atlas.json` contains the source SHA256, accepted run ID, "
        "available run-directory locator, complete recorded acceptance "
        "scope, configuration metadata and preparation/reuse references.",
        "",
        "The CSV contains one row per **distinct case identity**, not "
        "one row per calibration attempt or supporting certificate. "
        "Multiple accepted certificates for the same case are preserved "
        "under that case's `evidence` array.",
        "",
        "## Boundaries",
        "",
        "- The 15 C01 calibration-accepted results, five independently "
        "13-hard-gate-certified results and two cross-size certificates "
        "retain their **different documented acceptance scopes**.",
        "- The baseline M8/M12 configurations were reconstructed from "
        "their governed case builder and verified against historical "
        "canonical case hashes. Future campaigns require their own "
        "governed configuration resolvers.",
        "- `rom_admission_status = NOT_EVALUATED` is deliberate. "
        "ROM target extraction, sufficiency, admission and dataset "
        "freeze are separate governed checkpoints.",
        "- Trial-1 attempts and rejected results are not counted as "
        "additional accepted case identities. Their provenance remains "
        "in the original acceptance records.",
        "",
        "## Append a new accepted DOE result",
        "",
        "From `D:\\ThreadROM`, after the factory emits a **FINAL accepted "
        "record with a supported schema**:",
        "",
        "```powershell",
        r'.\.venv\Scripts\python.exe .\scripts\build_phase3_fem_atlas.py '
        r'--add "simulations/staging/<campaign>/<case>/<accepted-record>.json"',
        "```",
        "",
        "The actual path must point to a supported governed acceptance "
        "record. The builder verifies acceptance and evidence identity, "
        "retains all existing source hashes, and appends a new case—or "
        "adds evidence under its existing case hash.",
        "",
        "New campaign-specific engineering coordinates are intentionally "
        "marked `NEW_CAMPAIGN_INPUT_ADAPTER_REQUIRED` until a governed "
        "resolver for that campaign is connected. **Registering evidence "
        "is not ROM dataset admission.** Wire the factory's final "
        "acceptance event to `--add` before launching a new DOE campaign.",
        "",
        "If an older accepted result might have been missed, run the "
        "optional filenames-only audit:",
        "",
        "```powershell",
        r".\.venv\Scripts\python.exe .\scripts\build_phase3_fem_atlas.py --audit",
        "```",
        "",
    ]

    return "\n".join(lines)


def write_if_changed(path: Path, text: str):
    encoded = text.encode("utf-8")
    if path.is_file() and path.read_bytes() == encoded:
        return "UNCHANGED"

    temporary = path.with_name(path.name + ".tmp")
    if temporary.exists():
        fail(f"Unexpected temporary output exists: {temporary}")

    try:
        with temporary.open("xb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()

    return "WRITTEN"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--add",
        action="append",
        default=[],
        metavar="RELATIVE_ACCEPTANCE_RECORD",
        help="Register an additional final accepted evidence record.",
    )
    parser.add_argument(
        "--promote-cross-size-inputs",
        action="store_true",
        help=(
            "Explicitly promote only the two baseline M8/M12 cases "
            "after historical canonical case-hash parity verification."
        ),
    )
    parser.add_argument(
        "--audit",
        action="store_true",
        help="List supported acceptance filenames not yet registered.",
    )
    args = parser.parse_args()

    policy, policy_sha, boundaries = read_policy()

    previous = None
    if ATLAS_JSON.is_file():
        previous, _ = read_json(ATLAS_JSON)

    if previous is None:
        sources = initial_sources()
    else:
        sources = sorted({
            entry["path"]
            for case in previous["cases"]
            for entry in case["evidence"]
        })

    for supplied in args.add:
        path = safe_path(supplied)
        if path.name not in SUPPORTED:
            fail(f"Unsupported acceptance-record filename: {supplied}")
        sources.append(relative_path(path))

    sources = sorted(set(sources))

    if args.audit:
        missing = discover_unregistered(set(sources))
        print("=== ACCEPTED-EVIDENCE ATLAS AUDIT ===")
        print("Registered source records:", len(sources))
        print("Unregistered supported record filenames:", len(missing))
        for path in missing:
            print("  ", path)
        print(
            "Audit is filenames-only. Unregistered records have "
            "NOT been assumed accepted or admitted."
        )
        return

    cases = assemble_cases(sources, policy, policy_sha, boundaries)
    added_cases, added_evidence = check_prior_atlas(
        cases,
        previous,
        allow_cross_size_upgrade=args.promote_cross_size_inputs,
    )

    atlas = {
        "schema_version": 1,
        "atlas_name": "threadrom_phase3_accepted_fem_evidence",
        "governing_c01_policy_path": "config/phase3_production_doe.toml",
        "governing_c01_policy_sha256": policy_sha,
        "meaning": (
            "Persistent acceptance-evidence registry; not a "
            "ROM dataset-admission or dataset-freeze certificate."
        ),
        "distinct_case_count": len(cases),
        "acceptance_source_count": sum(
            len(case["evidence"]) for case in cases
        ),
        "cases": cases,
    }

    ATLAS_DIR.mkdir(parents=True, exist_ok=True)

    rendered = {
        ATLAS_JSON: json.dumps(
            atlas, indent=2, ensure_ascii=False, sort_keys=True
        ) + "\n",
        ATLAS_CSV: csv_content(cases),
        ATLAS_INDEX: markdown_content(cases, policy_sha),
    }

    print("=== PHASE-3 ACCEPTED-FEM ATLAS ===")
    for path, content in rendered.items():
        status = write_if_changed(path, content)
        print(f"{status}: {relative_path(path)}")

    print("\nDistinct case identities:", len(cases))
    print("Acceptance source records:", atlas["acceptance_source_count"])
    print("New case identities this run:", len(added_cases))
    print("New acceptance records this run:", len(added_evidence))

    for case_id in added_cases:
        print("  NEW CASE:", case_id)

    for path in added_evidence:
        print("  NEW EVIDENCE:", path)

    verified_statuses = {
        "C01_POLICY_AND_CASE_COORDINATES_VERIFIED",
        "CROSS_SIZE_CANONICAL_CASE_HASH_VERIFIED",
    }
    unresolved = [
        case["case_id"]
        for case in cases
        if case["engineering_inputs"]["configuration_status"]
        not in verified_statuses
    ]

    print("Cases awaiting full input-coordinate resolution:", len(unresolved))
    for case_id in unresolved:
        print("  INPUTS PENDING:", case_id)

    print("ROM-admitted samples: NOT YET EVALUATED")
    print("Solver output/holdouts opened: 0")
    print("CAD/mesh/FEM executions: 0")
    print("ATLAS BUILD: COMPLETE")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, KeyError, TypeError, ValueError) as exc:
        print(f"ATLAS BUILD FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
