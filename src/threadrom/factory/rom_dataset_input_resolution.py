from __future__ import annotations

import hashlib
import json
import math
import tomllib

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from threadrom.case.resolver import resolve_case
from threadrom.factory.diversified_doe_design import (
    _build_case,
    _select_points,
)
from threadrom.materials.diversified_candidate_catalog import (
    DIVERSIFIED_CANDIDATE_MATERIAL_CATALOG,
)


CANONICAL_DA04_FIELDS = (
    "thread_designation",
    "bolt_material_id",
    "nut_material_id",
    "head_member_material_id",
    "nut_member_material_id",
    "head_member_thickness_mm",
    "nut_member_thickness_mm",
    "member_outer_diameter_mm",
    "member_clearance_hole_diameter_mm",
    "thread_friction_coefficient",
    "head_bearing_friction_coefficient",
    "nut_bearing_friction_coefficient",
    "member_interface_friction_coefficient",
    "target_preload_n",
    "external_axial_load_n",
)


PILOT_CASE_ID = (
    "TRM-DDOE-D-M10x1_5__"
    "member_aluminium_en_aw_6082_t6-01"
)


class RomDatasetInputResolutionError(RuntimeError):
    """Fail-closed ROM engineering-input reconstruction error."""


@dataclass(frozen=True)
class ResolvedRomEngineeringInputs:
    case_id: str
    case_hash: str
    normalized_coordinates: tuple[float, float, float]
    engineering_inputs: Mapping[str, Any]
    source_kind: str
    source_relative_path: str
    source_sha256: str
    policy_sha256: str


def _require(
    condition: bool,
    message: str,
) -> None:
    if not condition:
        raise RomDatasetInputResolutionError(message)


def _sha256(
    path: Path,
) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def _read_json(
    path: Path,
) -> dict[str, Any]:
    _require(
        path.is_file(),
        f"Required governed source is missing: {path}",
    )

    payload = json.loads(
        path.read_text(
            encoding="utf-8-sig"
        )
    )

    _require(
        isinstance(payload, dict),
        f"Expected JSON object: {path}",
    )

    return payload


def _load_safe_case_policy(
    repo_root: Path,
) -> tuple[dict[str, Any], str]:
    """
    Load only the three diversified-policy surfaces consumed by _build_case.

    Holdout, partition, proposal and other policy surfaces are removed as
    text before TOML parsing.
    """

    path = (
        repo_root
        / "config"
        / "phase3_diversified_doe.toml"
    )

    _require(
        path.is_file(),
        "Diversified DOE policy is missing.",
    )

    raw_lines = path.read_text(
        encoding="utf-8-sig"
    ).splitlines()

    allowed_headers = {
        "[candidate_geometry]",
        "[candidate_preload]",
        "[[size_candidates]]",
    }

    projected_lines: list[str] = []
    seen_headers: list[str] = []
    active = False

    for raw_line in raw_lines:
        stripped = raw_line.strip()

        header = (
            stripped.split("#", 1)[0].strip()
            if stripped.startswith("[")
            else None
        )

        if (
            header is not None
            and header.startswith("[")
        ):
            active = header in allowed_headers

            if active:
                projected_lines.append(header)
                seen_headers.append(header)

            continue

        if active:
            projected_lines.append(raw_line)

    projected_text = (
        "\n".join(projected_lines)
        + "\n"
    )

    _require(
        "[candidate_geometry]" in seen_headers,
        "Safe policy projection lacks candidate_geometry.",
    )

    _require(
        "[candidate_preload]" in seen_headers,
        "Safe policy projection lacks candidate_preload.",
    )

    _require(
        seen_headers.count("[[size_candidates]]") > 0,
        "Safe policy projection lacks size_candidates.",
    )

    for forbidden in (
        "holdout",
        "case_id",
        "proposal_id",
        "partition",
    ):
        _require(
            forbidden.casefold()
            not in projected_text.casefold(),
            (
                "Forbidden identity/partition vocabulary leaked "
                f"into safe policy projection: {forbidden}"
            ),
        )

    policy = tomllib.loads(projected_text)

    _require(
        set(policy)
        == {
            "candidate_geometry",
            "candidate_preload",
            "size_candidates",
        },
        "Safe policy projection exposed unexpected sections.",
    )

    return policy, _sha256(path)


def _engineering_inputs_from_resolved(
    *,
    case_id: str,
    resolved: Any,
) -> dict[str, Any]:
    source = resolved.source_case

    _require(
        source is not None,
        f"{case_id}: resolved source case is absent.",
    )

    _require(
        len(source.members.layers) == 2,
        f"{case_id}: expected two member layers.",
    )

    head_member = source.members.layers[0]
    nut_member = source.members.layers[1]

    _require(
        math.isclose(
            head_member.outer_diameter_mm,
            nut_member.outer_diameter_mm,
            rel_tol=0.0,
            abs_tol=1.0e-12,
        ),
        f"{case_id}: member outer diameters differ.",
    )

    _require(
        math.isclose(
            head_member.clearance_hole_diameter_mm,
            nut_member.clearance_hole_diameter_mm,
            rel_tol=0.0,
            abs_tol=1.0e-12,
        ),
        f"{case_id}: member clearance diameters differ.",
    )

    values = {
        "thread_designation":
            source.fastener.thread_designation,

        "bolt_material_id":
            source.fastener.bolt_material_id,

        "nut_material_id":
            source.fastener.nut_material_id,

        "head_member_material_id":
            head_member.material_id,

        "nut_member_material_id":
            nut_member.material_id,

        "head_member_thickness_mm":
            head_member.thickness_mm,

        "nut_member_thickness_mm":
            nut_member.thickness_mm,

        "member_outer_diameter_mm":
            head_member.outer_diameter_mm,

        "member_clearance_hole_diameter_mm":
            head_member.clearance_hole_diameter_mm,

        "thread_friction_coefficient":
            source.interfaces.thread_friction_coefficient,

        "head_bearing_friction_coefficient":
            source.interfaces.head_bearing_friction_coefficient,

        "nut_bearing_friction_coefficient":
            source.interfaces.nut_bearing_friction_coefficient,

        "member_interface_friction_coefficient":
            source.interfaces.member_interface_friction_coefficient,

        "target_preload_n":
            source.loading.target_preload_n,

        "external_axial_load_n":
            source.loading.external_axial_load_n,
    }

    _require(
        tuple(values) == CANONICAL_DA04_FIELDS,
        f"{case_id}: canonical DA04 field ordering/schema drift.",
    )

    for name, value in values.items():
        _require(
            value is not None,
            f"{case_id}: reconstructed {name} is null.",
        )

        if isinstance(value, float):
            _require(
                math.isfinite(value),
                f"{case_id}: reconstructed {name} is non-finite.",
            )

    return values


def _size_for_designation(
    *,
    policy: Mapping[str, Any],
    case_id: str,
    thread_designation: str,
) -> Mapping[str, Any]:
    matches = [
        row
        for row in policy["size_candidates"]
        if (
            isinstance(row, dict)
            and row.get("designation")
            == thread_designation
        )
    ]

    _require(
        len(matches) == 1,
        (
            f"{case_id}: expected one size candidate for "
            f"{thread_designation!r}; found {len(matches)}."
        ),
    )

    return matches[0]


def _resolve_wave_case(
    *,
    repo_root: Path,
    case_id: str,
    expected_case_hash: str,
    policy: Mapping[str, Any],
    policy_sha256: str,
) -> ResolvedRomEngineeringInputs | None:
    wave_root = (
        repo_root
        / "docs"
        / "phase3_diversified_doe"
        / "waves"
    )

    _require(
        wave_root.is_dir(),
        "Governed wave-plan root is missing.",
    )

    matches: list[
        tuple[Path, dict[str, Any], dict[str, Any]]
    ] = []

    for wave_plan_path in sorted(
        wave_root.glob(
            "TRM-DDOE-001-W*/wave_plan.json"
        )
    ):
        wave_plan = _read_json(
            wave_plan_path
        )

        selected = wave_plan.get(
            "selected_cases"
        )

        _require(
            isinstance(selected, list),
            (
                "Governed wave plan has invalid selected_cases: "
                f"{wave_plan_path}"
            ),
        )

        for row in selected:
            if not isinstance(row, dict):
                continue

            row_case_id = (
                row.get("proposal_id")
                or row.get("case_id")
            )

            if row_case_id == case_id:
                matches.append(
                    (
                        wave_plan_path,
                        wave_plan,
                        row,
                    )
                )

    if not matches:
        return None

    _require(
        len(matches) == 1,
        (
            f"{case_id}: expected exactly one governed wave-plan "
            f"binding; found {len(matches)}."
        ),
    )

    (
        wave_plan_path,
        wave_plan,
        row,
    ) = matches[0]

    _require(
        wave_plan.get(
            "holdout_configurations_generated"
        )
        is False,
        (
            f"{case_id}: wave plan does not prove "
            "holdout configurations remained ungenerated."
        ),
    )

    _require(
        wave_plan.get(
            "policy_sha256"
        )
        == policy_sha256,
        f"{case_id}: wave-plan policy SHA drift.",
    )

    _require(
        row.get("case_hash")
        == expected_case_hash,
        f"{case_id}: frozen wave-plan case hash drift.",
    )

    thread_designation = row.get(
        "thread_designation"
    )

    member_material_id = row.get(
        "member_material_id"
    )

    coordinates_raw = row.get(
        "normalized_coordinates"
    )

    _require(
        isinstance(thread_designation, str)
        and bool(thread_designation),
        f"{case_id}: wave-plan thread designation missing.",
    )

    _require(
        isinstance(member_material_id, str)
        and bool(member_material_id),
        f"{case_id}: wave-plan member material missing.",
    )

    _require(
        isinstance(coordinates_raw, list)
        and len(coordinates_raw) == 3,
        f"{case_id}: invalid wave-plan normalized coordinates.",
    )

    coordinates = tuple(
        float(value)
        for value in coordinates_raw
    )

    _require(
        all(
            math.isfinite(value)
            for value in coordinates
        ),
        f"{case_id}: non-finite normalized coordinates.",
    )

    wave_id = wave_plan.get(
        "wave_id"
    )

    _require(
        isinstance(wave_id, str)
        and wave_id.startswith(
            "TRM-DDOE-001-W"
        ),
        f"{case_id}: invalid governed wave identity.",
    )

    token = wave_id.rsplit(
        "-",
        1,
    )[-1]

    preparation_index_path = (
        repo_root
        / "simulations"
        / "staging"
        / "phase3_diversified_doe"
        / "TRM-DDOE-001"
        / token
        / f"{token.lower()}_trial1_preparation.json"
    )

    preparation_index = _read_json(
        preparation_index_path
    )

    _require(
        preparation_index.get(
            "wave_plan_sha256"
        )
        == _sha256(
            wave_plan_path
        ),
        (
            f"{case_id}: governed preparation index is not "
            "cryptographically bound to its wave plan."
        ),
    )

    prepared_rows = preparation_index.get(
        "prepared_trials"
    )

    _require(
        isinstance(prepared_rows, list),
        f"{case_id}: prepared_trials is invalid.",
    )

    prepared_matches = [
        prepared
        for prepared in prepared_rows
        if (
            isinstance(prepared, dict)
            and prepared.get("case_id")
            == case_id
        )
    ]

    _require(
        len(prepared_matches) == 1,
        (
            f"{case_id}: expected one preparation-index row; "
            f"found {len(prepared_matches)}."
        ),
    )

    prepared = prepared_matches[0]

    _require(
        prepared.get("case_hash")
        == expected_case_hash,
        f"{case_id}: preparation-index case hash drift.",
    )

    size = _size_for_designation(
        policy=policy,
        case_id=case_id,
        thread_designation=(
            thread_designation
        ),
    )

    product_case, _ = _build_case(
        policy,
        size,
        member_material_id,
        coordinates,
    )

    resolved = resolve_case(
        product_case,
        material_catalog=(
            DIVERSIFIED_CANDIDATE_MATERIAL_CATALOG
        ),
    )

    _require(
        resolved.case_hash
        == expected_case_hash,
        (
            f"{case_id}: deterministic governed-wave "
            "case-hash reconstruction failed."
        ),
    )

    values = _engineering_inputs_from_resolved(
        case_id=case_id,
        resolved=resolved,
    )

    _require(
        values[
            "thread_designation"
        ]
        == thread_designation,
        f"{case_id}: thread reconstruction drift.",
    )

    _require(
        values[
            "head_member_material_id"
        ]
        == member_material_id,
        f"{case_id}: head-member material reconstruction drift.",
    )

    _require(
        values[
            "nut_member_material_id"
        ]
        == member_material_id,
        f"{case_id}: nut-member material reconstruction drift.",
    )

    return ResolvedRomEngineeringInputs(
        case_id=case_id,
        case_hash=expected_case_hash,
        normalized_coordinates=coordinates,
        engineering_inputs=values,
        source_kind="GOVERNED_WAVE_PLAN",
        source_relative_path=(
            wave_plan_path.relative_to(
                repo_root
            ).as_posix()
        ),
        source_sha256=_sha256(
            wave_plan_path
        ),
        policy_sha256=policy_sha256,
    )


def _resolve_historical_pilot(
    *,
    repo_root: Path,
    case_id: str,
    expected_case_hash: str,
    policy: Mapping[str, Any],
    policy_sha256: str,
) -> ResolvedRomEngineeringInputs:
    _require(
        case_id == PILOT_CASE_ID,
        f"{case_id}: unsupported historical pilot identity.",
    )

    base = (
        repo_root
        / "simulations"
        / "staging"
        / "phase3_diversified_doe"
        / "pilot_calibration_preflight"
        / "trm_fem_0f92f7fbf611"
    )

    cal1_path = (
        base
        / "trm_fem_0f92f7fbf611_cal_01"
        / "pilot_calibration_deck_preflight.json"
    )

    adaptive_path = (
        base
        / "trm_fem_0f92f7fbf611_cal_02"
        / "pilot_adaptive_factory_preflight.json"
    )

    manifest_path = (
        base
        / "trm_fem_0f92f7fbf611_cal_02"
        / "fem_run_manifest.json"
    )

    cal1 = _read_json(
        cal1_path
    )

    adaptive = _read_json(
        adaptive_path
    )

    manifest = _read_json(
        manifest_path
    )

    _require(
        cal1.get("pilot_proposal_id")
        == case_id,
        "Historical pilot proposal identity drift.",
    )

    _require(
        cal1.get("pilot_case_hash")
        == expected_case_hash,
        "Historical pilot CAL_01 case hash drift.",
    )

    _require(
        adaptive.get("case_hash")
        == expected_case_hash,
        "Historical pilot adaptive-preflight case hash drift.",
    )

    _require(
        manifest.get("case_hash")
        == expected_case_hash,
        "Historical pilot run-manifest case hash drift.",
    )

    _require(
        adaptive.get(
            "sealed_holdouts_accessed"
        )
        is False,
        "Historical pilot claims sealed-holdout access.",
    )

    _require(
        adaptive.get(
            "dataset_admission_authorized"
        )
        is False,
        "Historical pilot pre-authorized dataset admission.",
    )

    _require(
        manifest.get("disposition")
        == "succeeded",
        "Historical pilot accepted run is not successful.",
    )

    member_material_id = adaptive.get(
        "member_material_id"
    )

    _require(
        member_material_id
        == "member_aluminium_en_aw_6082_t6",
        "Historical pilot member-material identity drift.",
    )

    design_points = tuple(
        _select_points(
            (),
            12,
        )
    )

    _require(
        len(design_points) == 12
        and len(set(design_points)) == 12,
        "Historical pilot design-point sequence drift.",
    )

    matches: list[
        tuple[
            int,
            tuple[float, float, float],
            Mapping[str, Any],
            Any,
        ]
    ] = []

    for point_index, point in enumerate(
        design_points,
        start=1,
    ):
        coordinates = tuple(
            float(value)
            for value in point
        )

        for size in policy[
            "size_candidates"
        ]:
            product_case, _ = _build_case(
                policy,
                size,
                member_material_id,
                coordinates,
            )

            resolved = resolve_case(
                product_case,
                material_catalog=(
                    DIVERSIFIED_CANDIDATE_MATERIAL_CATALOG
                ),
            )

            if (
                resolved.case_hash
                == expected_case_hash
            ):
                matches.append(
                    (
                        point_index,
                        coordinates,
                        size,
                        resolved,
                    )
                )

    _require(
        len(matches) == 1,
        (
            "Historical pilot frozen hash must resolve uniquely; "
            f"found {len(matches)} matches."
        ),
    )

    (
        point_index,
        coordinates,
        size,
        resolved,
    ) = matches[0]

    cohort_name = (
        size["designation"]
        .replace(".", "_")
        + "__"
        + member_material_id
    )

    reconstructed_case_id = (
        f"TRM-DDOE-D-"
        f"{cohort_name}-"
        f"{point_index:02d}"
    )

    _require(
        reconstructed_case_id
        == case_id,
        "Historical pilot reconstructed proposal-ID drift.",
    )

    values = _engineering_inputs_from_resolved(
        case_id=case_id,
        resolved=resolved,
    )

    return ResolvedRomEngineeringInputs(
        case_id=case_id,
        case_hash=expected_case_hash,
        normalized_coordinates=coordinates,
        engineering_inputs=values,
        source_kind=(
            "HISTORICAL_DIVERSIFIED_PILOT_HASH_RECOVERY"
        ),
        source_relative_path=(
            adaptive_path.relative_to(
                repo_root
            ).as_posix()
        ),
        source_sha256=_sha256(
            adaptive_path
        ),
        policy_sha256=policy_sha256,
    )


def resolve_rom_engineering_inputs(
    *,
    repo_root: Path,
    case_id: str,
    expected_case_hash: str,
) -> ResolvedRomEngineeringInputs:
    """
    Resolve canonical DA04 engineering inputs for diversified cases whose
    FEM Atlas row carries NEW_CAMPAIGN_INPUT_ADAPTER_REQUIRED.

    This resolver never opens design_proposal.json and never constructs or
    reads sealed holdout identities.
    """

    root = Path(
        repo_root
    ).resolve()

    _require(
        root.is_dir(),
        f"Repository root does not exist: {root}",
    )

    _require(
        isinstance(case_id, str)
        and bool(case_id.strip()),
        "case_id must be a nonblank string.",
    )

    _require(
        isinstance(expected_case_hash, str)
        and len(expected_case_hash) == 64,
        "expected_case_hash must be a SHA-256 hex string.",
    )

    try:
        int(
            expected_case_hash,
            16,
        )
    except ValueError as exc:
        raise RomDatasetInputResolutionError(
            "expected_case_hash must be hexadecimal."
        ) from exc

    policy, policy_sha256 = (
        _load_safe_case_policy(
            root
        )
    )

    wave = _resolve_wave_case(
        repo_root=root,
        case_id=case_id,
        expected_case_hash=(
            expected_case_hash
        ),
        policy=policy,
        policy_sha256=(
            policy_sha256
        ),
    )

    if wave is not None:
        return wave

    if case_id == PILOT_CASE_ID:
        return _resolve_historical_pilot(
            repo_root=root,
            case_id=case_id,
            expected_case_hash=(
                expected_case_hash
            ),
            policy=policy,
            policy_sha256=(
                policy_sha256
            ),
        )

    raise RomDatasetInputResolutionError(
        (
            f"{case_id}: no governed ROM engineering-input "
            "authority is registered."
        )
    )