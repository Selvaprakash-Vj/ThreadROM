"""TOML loader for canonical analytical joint inputs."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path
from typing import cast

from threadrom.engineering.analytical_inputs import (
    BoltAxialSegmentInput,
    BoltSegmentKind,
    ElasticMaterial,
    LoadingInput,
    MemberLayerInput,
    MetricThreadInput,
    ThreadHandedness,
)
from threadrom.engineering.analytical_joint_input import (
    AnalyticalJointInput,
    AnalyticalMethodSelection,
    BoltComplianceMethod,
    BoltInput,
    ExternalLoadMethod,
    MemberCompressionMethod,
    NutInput,
    ThreadLoadDistributionMethod,
)


def load_analytical_joint_input(
    path: Path,
) -> AnalyticalJointInput:
    """Load and validate one canonical analytical joint definition."""

    with path.open("rb") as config_file:
        raw_data: dict[str, object] = tomllib.load(config_file)

    identity = _section(raw_data, "identity")
    thread_data = _section(raw_data, "thread")
    bolt_data = _section(raw_data, "bolt")
    nut_data = _section(raw_data, "nut")
    loading_data = _section(raw_data, "loading")
    methods_data = _section(raw_data, "methods")

    segment_rows = _table_array(
        bolt_data,
        "axial_segments",
    )

    member_rows = _table_array(
        raw_data,
        "member_layers",
    )

    material_rows = _table_array(
        raw_data,
        "materials",
    )

    thread = MetricThreadInput(
        nominal_diameter_mm=_number(
            thread_data,
            "nominal_diameter_mm",
        ),
        pitch_mm=_number(
            thread_data,
            "pitch_mm",
        ),
        handedness=_enum_value(
            ThreadHandedness,
            thread_data,
            "handedness",
        ),
        starts=_integer(
            thread_data,
            "starts",
        ),
        included_angle_deg=_number(
            thread_data,
            "included_angle_deg",
        ),
        external_tolerance_class=_optional_string(
            thread_data,
            "external_tolerance_class",
        ),
        internal_tolerance_class=_optional_string(
            thread_data,
            "internal_tolerance_class",
        ),
    )

    segments = tuple(_load_bolt_segment(row) for row in segment_rows)

    bolt = BoltInput(
        bolt_id=_string(
            bolt_data,
            "bolt_id",
        ),
        material_id=_string(
            bolt_data,
            "material_id",
        ),
        nominal_length_mm=_number(
            bolt_data,
            "nominal_length_mm",
        ),
        axial_segments=segments,
        head_bearing_outer_diameter_mm=_number(
            bolt_data,
            "head_bearing_outer_diameter_mm",
        ),
        head_bearing_inner_diameter_mm=_number(
            bolt_data,
            "head_bearing_inner_diameter_mm",
        ),
    )

    nut = NutInput(
        nut_id=_string(
            nut_data,
            "nut_id",
        ),
        material_id=_string(
            nut_data,
            "material_id",
        ),
        thickness_mm=_number(
            nut_data,
            "thickness_mm",
        ),
        thread_engagement_length_mm=_number(
            nut_data,
            "thread_engagement_length_mm",
        ),
        bearing_outer_diameter_mm=_number(
            nut_data,
            "bearing_outer_diameter_mm",
        ),
        bearing_inner_diameter_mm=_number(
            nut_data,
            "bearing_inner_diameter_mm",
        ),
    )

    member_layers = tuple(_load_member_layer(row) for row in member_rows)

    materials = tuple(_load_material(row) for row in material_rows)

    loading = LoadingInput(
        preload_n=_number(
            loading_data,
            "preload_n",
        ),
        external_axial_load_n=_optional_number(
            loading_data,
            "external_axial_load_n",
            default=0.0,
        ),
        cyclic_minimum_axial_load_n=_optional_number_or_none(
            loading_data,
            "cyclic_minimum_axial_load_n",
        ),
        cyclic_maximum_axial_load_n=_optional_number_or_none(
            loading_data,
            "cyclic_maximum_axial_load_n",
        ),
        preload_scatter_fraction=_optional_number(
            loading_data,
            "preload_scatter_fraction",
            default=0.0,
        ),
    )

    methods = AnalyticalMethodSelection(
        bolt_compliance=_enum_value(
            BoltComplianceMethod,
            methods_data,
            "bolt_compliance",
        ),
        member_compression=_enum_value(
            MemberCompressionMethod,
            methods_data,
            "member_compression",
        ),
        external_load=_enum_value(
            ExternalLoadMethod,
            methods_data,
            "external_load",
        ),
        thread_load_distribution=_enum_value(
            ThreadLoadDistributionMethod,
            methods_data,
            "thread_load_distribution",
        ),
        head_participation_factor=_number(
            methods_data,
            "head_participation_factor",
        ),
        nut_participation_factor=_number(
            methods_data,
            "nut_participation_factor",
        ),
        load_introduction_factor=_optional_number(
            methods_data,
            "load_introduction_factor",
            default=1.0,
        ),
    )

    return AnalyticalJointInput(
        joint_id=_string(
            identity,
            "joint_id",
        ),
        thread=thread,
        bolt=bolt,
        nut=nut,
        member_layers=member_layers,
        materials=materials,
        loading=loading,
        methods=methods,
    )


def _load_bolt_segment(
    data: Mapping[str, object],
) -> BoltAxialSegmentInput:
    """Load one bolt axial-segment definition."""

    return BoltAxialSegmentInput(
        segment_id=_string(
            data,
            "segment_id",
        ),
        kind=_enum_value(
            BoltSegmentKind,
            data,
            "kind",
        ),
        length_mm=_number(
            data,
            "length_mm",
        ),
        diameter_mm=_optional_number_or_none(
            data,
            "diameter_mm",
        ),
        area_mm2=_optional_number_or_none(
            data,
            "area_mm2",
        ),
        material_id=_optional_string(
            data,
            "material_id",
        ),
    )


def _load_member_layer(
    data: Mapping[str, object],
) -> MemberLayerInput:
    """Load one clamped-member layer."""

    return MemberLayerInput(
        layer_id=_string(
            data,
            "layer_id",
        ),
        thickness_mm=_number(
            data,
            "thickness_mm",
        ),
        material_id=_string(
            data,
            "material_id",
        ),
        clearance_hole_diameter_mm=_number(
            data,
            "clearance_hole_diameter_mm",
        ),
        outer_diameter_mm=_number(
            data,
            "outer_diameter_mm",
        ),
    )


def _load_material(
    data: Mapping[str, object],
) -> ElasticMaterial:
    """Load one elastic material definition."""

    return ElasticMaterial(
        material_id=_string(
            data,
            "material_id",
        ),
        youngs_modulus_mpa=_number(
            data,
            "youngs_modulus_mpa",
        ),
        poissons_ratio=_number(
            data,
            "poissons_ratio",
        ),
        proof_stress_mpa=_optional_number_or_none(
            data,
            "proof_stress_mpa",
        ),
        yield_strength_mpa=_optional_number_or_none(
            data,
            "yield_strength_mpa",
        ),
        ultimate_strength_mpa=_optional_number_or_none(
            data,
            "ultimate_strength_mpa",
        ),
    )


def _section(
    data: Mapping[str, object],
    key: str,
) -> Mapping[str, object]:
    """Return one required TOML table."""

    value = data.get(key)

    if not isinstance(value, dict):
        raise TypeError(f"Missing or invalid TOML table: {key}")

    return cast(Mapping[str, object], value)


def _table_array(
    data: Mapping[str, object],
    key: str,
) -> tuple[Mapping[str, object], ...]:
    """Return one required TOML array of tables."""

    value = data.get(key)

    if not isinstance(value, list) or not value:
        raise TypeError(f"Missing or invalid TOML table array: {key}")

    rows: list[Mapping[str, object]] = []

    for item in value:
        if not isinstance(item, dict):
            raise TypeError(f"Invalid entry in TOML table array: {key}")

        rows.append(cast(Mapping[str, object], item))

    return tuple(rows)


def _string(
    data: Mapping[str, object],
    key: str,
) -> str:
    """Return one required nonblank string."""

    value = data.get(key)

    if not isinstance(value, str) or not value.strip():
        raise TypeError(f"Missing or invalid string value: {key}")

    return value


def _optional_string(
    data: Mapping[str, object],
    key: str,
) -> str | None:
    """Return one optional nonblank string."""

    if key not in data:
        return None

    return _string(data, key)


def _number(
    data: Mapping[str, object],
    key: str,
) -> float:
    """Return one required numerical value."""

    value = data.get(key)

    if isinstance(value, bool) or not isinstance(
        value,
        int | float,
    ):
        raise TypeError(f"Missing or invalid numerical value: {key}")

    return float(value)


def _optional_number(
    data: Mapping[str, object],
    key: str,
    *,
    default: float,
) -> float:
    """Return one optional numerical value with a default."""

    if key not in data:
        return default

    return _number(data, key)


def _optional_number_or_none(
    data: Mapping[str, object],
    key: str,
) -> float | None:
    """Return one optional numerical value."""

    if key not in data:
        return None

    return _number(data, key)


def _integer(
    data: Mapping[str, object],
    key: str,
) -> int:
    """Return one required integer."""

    value = data.get(key)

    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"Missing or invalid integer value: {key}")

    return value


def _enum_value[EnumType: StrEnum](
    enum_type: type[EnumType],
    data: Mapping[str, object],
    key: str,
) -> EnumType:
    """Return one validated string-backed enumeration value."""

    raw_value = _string(data, key)

    try:
        return enum_type(raw_value)
    except ValueError as error:
        raise ValueError(f"Unsupported value for {key}: {raw_value}") from error
