"""Governed case-level applicability resolution for ROM dataset admission.

The resolver is generic and fail-closed.

A target-specific supported-domain record declares the complete bounded
engineering domain. This module evaluates canonical engineering inputs
against that record without expanding the domain, inspecting FEM results,
accessing holdouts, assigning dataset partitions, or training a ROM.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Any, Mapping, Sequence


SUPPORTED_DOMAIN_SCHEMA = "threadrom.rom_supported_domain.v1"


class ApplicabilityDecision(str, Enum):
    PASS = "PASS"
    REJECTED = "REJECTED"
    DEFERRED = "DEFERRED"


@dataclass(frozen=True)
class ApplicabilityResult:
    decision: ApplicabilityDecision
    domain_id: str
    reason_code: str | None
    detail: str
    checked_fields: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return self.decision is ApplicabilityDecision.PASS


def _mapping(
    value: Any,
    *,
    name: str,
) -> Mapping[str, Any]:

    if not isinstance(value, Mapping):
        raise ValueError(
            f"{name} must be a mapping."
        )

    return value


def _sequence(
    value: Any,
    *,
    name: str,
) -> Sequence[Any]:

    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes))
    ):
        raise ValueError(
            f"{name} must be a sequence."
        )

    return value


def _string_sequence(
    value: Any,
    *,
    name: str,
) -> tuple[str, ...]:

    raw = _sequence(
        value,
        name=name,
    )

    result = tuple(raw)

    if (
        not result
        or any(
            not isinstance(item, str)
            or not item
            for item in result
        )
    ):
        raise ValueError(
            f"{name} must contain non-empty strings."
        )

    if len(set(result)) != len(result):
        raise ValueError(
            f"{name} contains duplicate fields."
        )

    return result


def _number(
    value: Any,
    *,
    name: str,
) -> float:

    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
    ):
        raise ValueError(
            f"{name} must be numeric."
        )

    number = float(value)

    if not isfinite(number):
        raise ValueError(
            f"{name} must be finite."
        )

    return number


def _numeric_range_passes(
    *,
    candidate: Any,
    specification: Mapping[str, Any],
    field: str,
) -> bool:

    lower = _number(
        specification.get("minimum"),
        name=f"{field}.minimum",
    )

    upper = _number(
        specification.get("maximum"),
        name=f"{field}.maximum",
    )

    if lower > upper:
        raise ValueError(
            f"Invalid numeric applicability range for {field!r}."
        )

    inclusive_minimum = specification.get(
        "inclusive_minimum",
        True,
    )

    inclusive_maximum = specification.get(
        "inclusive_maximum",
        True,
    )

    if not isinstance(inclusive_minimum, bool):
        raise ValueError(
            f"{field}.inclusive_minimum must be boolean."
        )

    if not isinstance(inclusive_maximum, bool):
        raise ValueError(
            f"{field}.inclusive_maximum must be boolean."
        )

    value = _number(
        candidate,
        name=field,
    )

    below = (
        value < lower
        if inclusive_minimum
        else value <= lower
    )

    above = (
        value > upper
        if inclusive_maximum
        else value >= upper
    )

    return not (
        below
        or above
    )


def _derive_conditional_vector(
    *,
    inputs: Mapping[str, Any],
    field: str,
    specification: Mapping[str, Any],
    profile: Mapping[str, Any],
) -> tuple[float, ...] | None:
    """Derive a governed normalized vector from physical engineering inputs.

    This is deliberately generic.  The supported-domain record declares
    which physical source field corresponds to each normalized component
    and which conditional numeric range defines the linear transform.
    """

    raw_rules = specification.get(
        "derived_components"
    )

    if raw_rules is None:
        return None

    rules = _sequence(
        raw_rules,
        name=f"{field}.derived_components",
    )

    components = _sequence(
        specification.get(
            "components"
        ),
        name=f"{field}.components",
    )

    if len(rules) != len(components):
        raise ValueError(
            f"{field}.derived_components must match the governed "
            "vector component count."
        )

    profile_ranges = _mapping(
        profile.get(
            "numeric_ranges",
            {},
        ),
        name="conditional profile numeric_ranges",
    )

    derived: list[float] = []

    for index, raw_rule in enumerate(
        rules
    ):

        rule = _mapping(
            raw_rule,
            name=f"{field}.derived_components[{index}]",
        )

        source_field = rule.get(
            "source_field"
        )

        range_field = rule.get(
            "profile_numeric_range_field"
        )

        transform = rule.get(
            "transform",
            "linear",
        )

        if (
            not isinstance(source_field, str)
            or not source_field
            or not isinstance(range_field, str)
            or not range_field
        ):
            raise ValueError(
                f"{field}.derived_components[{index}] requires "
                "source_field and profile_numeric_range_field."
            )

        if transform != "linear":
            raise ValueError(
                f"Unsupported derived-vector transform for {field!r}: "
                f"{transform!r}."
            )

        if (
            source_field not in inputs
            or inputs[source_field] is None
        ):
            return None

        range_spec = _mapping(
            profile_ranges.get(
                range_field
            ),
            name=(
                f"conditional numeric range "
                f"{range_field!r}"
            ),
        )

        lower = _number(
            range_spec.get(
                "minimum"
            ),
            name=f"{range_field}.minimum",
        )

        upper = _number(
            range_spec.get(
                "maximum"
            ),
            name=f"{range_field}.maximum",
        )

        if upper <= lower:
            raise ValueError(
                f"Derived normalized coordinate requires a "
                f"non-degenerate range for {range_field!r}."
            )

        value = _number(
            inputs[source_field],
            name=source_field,
        )

        derived.append(
            (
                value
                - lower
            )
            / (
                upper
                - lower
            )
        )

    return tuple(
        derived
    )


def evaluate_rom_case_applicability(
    *,
    engineering_inputs: Mapping[str, Any],
    supported_domain: Mapping[str, Any],
) -> ApplicabilityResult:

    domain = _mapping(
        supported_domain,
        name="supported_domain",
    )

    if domain.get("schema") != SUPPORTED_DOMAIN_SCHEMA:
        raise ValueError(
            "Unsupported ROM supported-domain schema."
        )

    if domain.get("record_status") != "FINAL":
        raise ValueError(
            "Supported-domain record must be FINAL."
        )

    domain_id = domain.get(
        "domain_id"
    )

    if (
        not isinstance(domain_id, str)
        or not domain_id
    ):
        raise ValueError(
            "Supported-domain record requires a non-empty domain_id."
        )

    governance = _mapping(
        domain.get("governance"),
        name="supported_domain.governance",
    )

    if (
        governance.get(
            "domain_expansion_by_admission_forbidden"
        )
        is not True
    ):
        raise ValueError(
            "Supported-domain authority must forbid domain expansion "
            "by dataset admission."
        )

    required_fields = _string_sequence(
        domain.get(
            "required_engineering_fields"
        ),
        name="supported_domain.required_engineering_fields",
    )

    constraints = _mapping(
        domain.get(
            "constraints"
        ),
        name="supported_domain.constraints",
    )

    categorical = _mapping(
        constraints.get(
            "categorical",
            {},
        ),
        name="supported_domain.constraints.categorical",
    )

    numeric_ranges = _mapping(
        constraints.get(
            "numeric_ranges",
            {},
        ),
        name="supported_domain.constraints.numeric_ranges",
    )

    vector_ranges = _mapping(
        constraints.get(
            "vector_ranges",
            {},
        ),
        name="supported_domain.constraints.vector_ranges",
    )

    equalities = _sequence(
        constraints.get(
            "equalities",
            (),
        ),
        name="supported_domain.constraints.equalities",
    )

    conditional = constraints.get(
        "conditional_profiles"
    )

    conditional_fields: set[str] = set()

    if conditional is not None:

        conditional_map = _mapping(
            conditional,
            name="supported_domain.constraints.conditional_profiles",
        )

        selector_field = conditional_map.get(
            "selector_field"
        )

        if (
            not isinstance(selector_field, str)
            or selector_field not in required_fields
        ):
            raise ValueError(
                "Conditional-profile selector must be a required engineering field."
            )

        profiles = _mapping(
            conditional_map.get(
                "profiles"
            ),
            name="supported_domain.constraints.conditional_profiles.profiles",
        )

        if not profiles:
            raise ValueError(
                "Conditional profiles cannot be empty."
            )

        field_sets: list[set[str]] = []

        for profile_name, raw_profile in profiles.items():

            profile = _mapping(
                raw_profile,
                name=f"conditional profile {profile_name!r}",
            )

            profile_ranges = _mapping(
                profile.get(
                    "numeric_ranges",
                    {},
                ),
                name=f"conditional profile {profile_name!r}.numeric_ranges",
            )

            field_sets.append(
                set(
                    profile_ranges
                )
            )

        first_fields = field_sets[0]

        if any(
            fields != first_fields
            for fields in field_sets[1:]
        ):
            raise ValueError(
                "Every conditional profile must constrain the same numeric fields."
            )

        conditional_fields = first_fields

    else:

        selector_field = None
        profiles = {}

    directly_bounded = (
        set(categorical)
        | set(numeric_ranges)
        | set(vector_ranges)
        | conditional_fields
    )

    unbounded_required = (
        set(required_fields)
        - directly_bounded
    )

    if unbounded_required:
        raise ValueError(
            "Supported-domain record leaves required engineering fields "
            f"unbounded: {sorted(unbounded_required)!r}"
        )

    inputs = dict(
        _mapping(
            engineering_inputs,
            name="engineering_inputs",
        )
    )

    # Derived normalized representations are not independent physics.
    # If a governed vector is absent, reconstruct it deterministically
    # from the already-governed physical engineering fields.
    if (
        conditional is not None
        and selector_field is not None
        and selector_field in inputs
        and inputs[selector_field] is not None
    ):
        profile_raw = profiles.get(
            str(
                inputs[
                    selector_field
                ]
            )
        )

        if profile_raw is not None:

            profile_for_derivation = _mapping(
                profile_raw,
                name=(
                    "conditional profile "
                    f"{inputs[selector_field]!r}"
                ),
            )

            for field, raw_specification in vector_ranges.items():

                if (
                    field in inputs
                    and inputs[field] is not None
                ):
                    continue

                specification = _mapping(
                    raw_specification,
                    name=f"vector range {field!r}",
                )

                derived = _derive_conditional_vector(
                    inputs=inputs,
                    field=field,
                    specification=specification,
                    profile=profile_for_derivation,
                )

                if derived is not None:
                    inputs[field] = derived

    missing = tuple(
        field
        for field in required_fields
        if (
            field not in inputs
            or inputs[field] is None
        )
    )

    if missing:
        return ApplicabilityResult(
            decision=ApplicabilityDecision.DEFERRED,
            domain_id=domain_id,
            reason_code="ENGINEERING_INPUTS_INCOMPLETE",
            detail=(
                "Applicability cannot be evaluated because canonical "
                f"engineering inputs are missing: {list(missing)!r}"
            ),
            checked_fields=(),
        )

    checked: list[str] = []

    for field, allowed_raw in categorical.items():

        allowed = tuple(
            _sequence(
                allowed_raw,
                name=f"categorical applicability field {field!r}",
            )
        )

        if not allowed:
            raise ValueError(
                f"Categorical applicability field {field!r} "
                "must declare at least one allowed value."
            )

        if inputs[field] not in allowed:
            return ApplicabilityResult(
                decision=ApplicabilityDecision.REJECTED,
                domain_id=domain_id,
                reason_code="OUTSIDE_APPLICABILITY",
                detail=(
                    f"{field}={inputs[field]!r} is outside the governed "
                    f"allowed values {list(allowed)!r}."
                ),
                checked_fields=tuple(
                    checked
                    + [field]
                ),
            )

        checked.append(
            field
        )

    for field, raw_specification in numeric_ranges.items():

        specification = _mapping(
            raw_specification,
            name=f"numeric range {field!r}",
        )

        if not _numeric_range_passes(
            candidate=inputs[field],
            specification=specification,
            field=field,
        ):
            return ApplicabilityResult(
                decision=ApplicabilityDecision.REJECTED,
                domain_id=domain_id,
                reason_code="OUTSIDE_APPLICABILITY",
                detail=(
                    f"{field}={inputs[field]!r} lies outside its "
                    "governed numeric range."
                ),
                checked_fields=tuple(
                    checked
                    + [field]
                ),
            )

        checked.append(
            field
        )

    for field, raw_specification in vector_ranges.items():

        specification = _mapping(
            raw_specification,
            name=f"vector range {field!r}",
        )

        candidate = _sequence(
            inputs[field],
            name=field,
        )

        components = _sequence(
            specification.get(
                "components"
            ),
            name=f"{field}.components",
        )

        if len(candidate) != len(components):
            return ApplicabilityResult(
                decision=ApplicabilityDecision.REJECTED,
                domain_id=domain_id,
                reason_code="OUTSIDE_APPLICABILITY",
                detail=(
                    f"{field} has {len(candidate)} components; "
                    f"{len(components)} are governed."
                ),
                checked_fields=tuple(
                    checked
                    + [field]
                ),
            )

        # If this vector has a governed physical derivation, an existing
        # supplied vector must agree with it.  This prevents apparently
        # valid 0..1 coordinates from drifting away from the actual
        # physical case.
        if (
            conditional is not None
            and selector_field is not None
        ):
            profile_raw = profiles.get(
                str(
                    inputs[
                        selector_field
                    ]
                )
            )

            if profile_raw is not None:

                profile_for_vector = _mapping(
                    profile_raw,
                    name=(
                        "conditional profile "
                        f"{inputs[selector_field]!r}"
                    ),
                )

                expected_vector = _derive_conditional_vector(
                    inputs=inputs,
                    field=field,
                    specification=specification,
                    profile=profile_for_vector,
                )

                if expected_vector is not None:

                    if len(expected_vector) != len(candidate):
                        raise ValueError(
                            f"Derived vector length mismatch for {field!r}."
                        )

                    tolerance = _number(
                        specification.get(
                            "derived_absolute_tolerance",
                            1.0e-9,
                        ),
                        name=(
                            f"{field}.derived_absolute_tolerance"
                        ),
                    )

                    if tolerance < 0.0:
                        raise ValueError(
                            f"{field}.derived_absolute_tolerance "
                            "cannot be negative."
                        )

                    for index, expected_component in enumerate(
                        expected_vector
                    ):

                        actual_component = _number(
                            candidate[index],
                            name=f"{field}[{index}]",
                        )

                        if abs(
                            actual_component
                            - expected_component
                        ) > tolerance:
                            return ApplicabilityResult(
                                decision=(
                                    ApplicabilityDecision.REJECTED
                                ),
                                domain_id=domain_id,
                                reason_code="OUTSIDE_APPLICABILITY",
                                detail=(
                                    f"{field}[{index}]={actual_component!r} "
                                    "is inconsistent with the governed "
                                    "physical engineering inputs; expected "
                                    f"{expected_component!r}."
                                ),
                                checked_fields=tuple(
                                    checked
                                    + [field]
                                ),
                            )

        for index, raw_component in enumerate(
            components
        ):

            component = _mapping(
                raw_component,
                name=f"{field}[{index}]",
            )

            if not _numeric_range_passes(
                candidate=candidate[index],
                specification=component,
                field=f"{field}[{index}]",
            ):
                return ApplicabilityResult(
                    decision=ApplicabilityDecision.REJECTED,
                    domain_id=domain_id,
                    reason_code="OUTSIDE_APPLICABILITY",
                    detail=(
                        f"{field}[{index}]={candidate[index]!r} lies "
                        "outside its governed component range."
                    ),
                    checked_fields=tuple(
                        checked
                        + [field]
                    ),
                )

        checked.append(
            field
        )

    for raw_pair in equalities:

        pair = tuple(
            _sequence(
                raw_pair,
                name="equality constraint",
            )
        )

        if (
            len(pair) != 2
            or any(
                not isinstance(field, str)
                or field not in required_fields
                for field in pair
            )
        ):
            raise ValueError(
                "Each equality constraint must reference exactly two "
                "required engineering fields."
            )

        left, right = pair

        if inputs[left] != inputs[right]:
            return ApplicabilityResult(
                decision=ApplicabilityDecision.REJECTED,
                domain_id=domain_id,
                reason_code="OUTSIDE_APPLICABILITY",
                detail=(
                    f"Governed equality constraint failed: "
                    f"{left}={inputs[left]!r}; "
                    f"{right}={inputs[right]!r}."
                ),
                checked_fields=tuple(checked),
            )

    if conditional is not None:

        selector_value = inputs[
            selector_field
        ]

        profile_raw = profiles.get(
            str(selector_value)
        )

        if profile_raw is None:
            return ApplicabilityResult(
                decision=ApplicabilityDecision.REJECTED,
                domain_id=domain_id,
                reason_code="OUTSIDE_APPLICABILITY",
                detail=(
                    f"No governed conditional profile exists for "
                    f"{selector_field}={selector_value!r}."
                ),
                checked_fields=tuple(checked),
            )

        profile = _mapping(
            profile_raw,
            name=f"conditional profile {selector_value!r}",
        )

        profile_ranges = _mapping(
            profile.get(
                "numeric_ranges",
                {},
            ),
            name=f"conditional profile {selector_value!r}.numeric_ranges",
        )

        for field, raw_specification in profile_ranges.items():

            specification = _mapping(
                raw_specification,
                name=f"conditional numeric range {field!r}",
            )

            if not _numeric_range_passes(
                candidate=inputs[field],
                specification=specification,
                field=field,
            ):
                return ApplicabilityResult(
                    decision=ApplicabilityDecision.REJECTED,
                    domain_id=domain_id,
                    reason_code="OUTSIDE_APPLICABILITY",
                    detail=(
                        f"{field}={inputs[field]!r} lies outside the "
                        f"governed {selector_value!r} profile."
                    ),
                    checked_fields=tuple(
                        checked
                        + [field]
                    ),
                )

            checked.append(
                field
            )

        sum_constraints = _sequence(
            profile.get(
                "sum_constraints",
                (),
            ),
            name=f"conditional profile {selector_value!r}.sum_constraints",
        )

        for raw_constraint in sum_constraints:

            rule = _mapping(
                raw_constraint,
                name="sum constraint",
            )

            fields = _string_sequence(
                rule.get(
                    "fields"
                ),
                name="sum constraint fields",
            )

            expected = _number(
                rule.get(
                    "equals"
                ),
                name="sum constraint equals",
            )

            tolerance = _number(
                rule.get(
                    "absolute_tolerance",
                    1.0e-9,
                ),
                name="sum constraint absolute_tolerance",
            )

            actual = sum(
                _number(
                    inputs[field],
                    name=field,
                )
                for field in fields
            )

            if abs(
                actual
                - expected
            ) > tolerance:
                return ApplicabilityResult(
                    decision=ApplicabilityDecision.REJECTED,
                    domain_id=domain_id,
                    reason_code="OUTSIDE_APPLICABILITY",
                    detail=(
                        f"Governed sum relation failed for {list(fields)!r}: "
                        f"{actual!r} != {expected!r}."
                    ),
                    checked_fields=tuple(checked),
                )

        affine_constraints = _sequence(
            profile.get(
                "affine_constraints",
                (),
            ),
            name=f"conditional profile {selector_value!r}.affine_constraints",
        )

        for raw_constraint in affine_constraints:

            rule = _mapping(
                raw_constraint,
                name="affine constraint",
            )

            dependent = rule.get(
                "dependent"
            )

            source = rule.get(
                "source"
            )

            if (
                not isinstance(dependent, str)
                or dependent not in required_fields
                or not isinstance(source, str)
                or source not in required_fields
            ):
                raise ValueError(
                    "Affine constraints must reference required "
                    "engineering fields."
                )

            intercept = _number(
                rule.get(
                    "intercept"
                ),
                name="affine constraint intercept",
            )

            slope = _number(
                rule.get(
                    "slope"
                ),
                name="affine constraint slope",
            )

            tolerance = _number(
                rule.get(
                    "absolute_tolerance",
                    1.0e-9,
                ),
                name="affine constraint absolute_tolerance",
            )

            expected = (
                intercept
                + slope
                * _number(
                    inputs[source],
                    name=source,
                )
            )

            actual = _number(
                inputs[dependent],
                name=dependent,
            )

            if abs(
                actual
                - expected
            ) > tolerance:
                return ApplicabilityResult(
                    decision=ApplicabilityDecision.REJECTED,
                    domain_id=domain_id,
                    reason_code="OUTSIDE_APPLICABILITY",
                    detail=(
                        f"Governed affine relation failed: "
                        f"{dependent}={actual!r}; expected {expected!r}."
                    ),
                    checked_fields=tuple(checked),
                )

    return ApplicabilityResult(
        decision=ApplicabilityDecision.PASS,
        domain_id=domain_id,
        reason_code=None,
        detail=(
            "Candidate canonical engineering inputs lie inside the "
            "complete governed supported-domain record."
        ),
        checked_fields=tuple(
            required_fields
        ),
    )
