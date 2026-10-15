"""Persistent governed FEM calibration-observation knowledge store.

Unlike the historical accepted-only FEM warm-start records, this store keeps
every valid solved calibration observation that is eligible for learning.

A calibration miss is useful physical evidence.  It is therefore preserved
with the same provenance discipline as an accepted calibration point.

This store is deliberately separate from the ThreadROM surrogate/ROM dataset.
"""

from __future__ import annotations

import hashlib
import json
import math

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from threadrom.factory.fem_calibration_knowledge import (
    FemCalibrationCompatibilityKey,
    FemCalibrationFeatureVector,
    FemGeometryRealizationIdentity,
)


STORE_SCHEMA = (
    "threadrom.fem_calibration_observation_store.v1"
)

STORE_SCHEMA_VERSION = 1

_LEARNING_DISPOSITIONS = frozenset(
    {
        "accept",
        "continue",
    }
)

_HEX = frozenset(
    "0123456789abcdef"
)


class FemCalibrationObservationStoreError(
    RuntimeError
):
    """Fail-closed calibration-knowledge-store error."""


@dataclass(frozen=True, slots=True)
class FemCalibrationObservation:
    """One valid solved FEM calibration observation."""

    case_id: str
    case_hash: str
    resolution_hash: str

    geometry_identity: (
        FemGeometryRealizationIdentity
    )

    execution_generation_id: str

    run_id: str
    trial_index: int
    trial_source: str

    delta_temperature_c: float
    analytical_delta_temperature_c: float

    target_force_n: float

    under_head_force_n: float
    nut_bearing_force_n: float
    member_interface_force_n: float

    extraction_time: float
    thread_normal_force_n: float

    decision_disposition: str

    feature: FemCalibrationFeatureVector

    dat_relative_path: str
    dat_sha256: str

    preparation_relative_path: str
    preparation_sha256: str

    @property
    def measured_mean_clamp_force_n(
        self,
    ) -> float:
        return (
            self.under_head_force_n
            + self.nut_bearing_force_n
            + self.member_interface_force_n
        ) / 3.0

    @property
    def clamp_force_spread_relative(
        self,
    ) -> float:
        values = (
            self.under_head_force_n,
            self.nut_bearing_force_n,
            self.member_interface_force_n,
        )

        mean = (
            self.measured_mean_clamp_force_n
        )

        return (
            max(values)
            - min(values)
        ) / mean

    @property
    def target_relative_error(
        self,
    ) -> float:
        return (
            self.measured_mean_clamp_force_n
            - self.target_force_n
        ) / self.target_force_n

    @property
    def proportional_target_delta_temperature_c(
        self,
    ) -> float:
        """One-point physical target estimate from this solved observation."""

        return (
            self.delta_temperature_c
            * self.target_force_n
            / self.measured_mean_clamp_force_n
        )

    @property
    def proportional_correction_factor(
        self,
    ) -> float:
        """Correction relative to the governed analytical trial-1 seed."""

        return (
            self.proportional_target_delta_temperature_c
            / self.analytical_delta_temperature_c
        )

    @property
    def reusable_for_prediction(
        self,
    ) -> bool:
        return (
            self.decision_disposition
            in _LEARNING_DISPOSITIONS
        )


def _require_text(
    value: object,
    name: str,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or not value.strip()
        or value != value.strip()
    ):
        raise FemCalibrationObservationStoreError(
            f"{name} must be a non-blank trimmed string."
        )

    return value


def _require_sha256(
    value: object,
    name: str,
) -> str:
    text = _require_text(
        value,
        name,
    )

    if (
        len(text) != 64
        or any(
            character not in _HEX
            for character in text
        )
    ):
        raise FemCalibrationObservationStoreError(
            f"{name} must be exactly 64 lowercase hexadecimal characters."
        )

    return text


def _require_positive(
    value: float,
    name: str,
) -> float:
    if (
        not math.isfinite(value)
        or value <= 0.0
    ):
        raise FemCalibrationObservationStoreError(
            f"{name} must be finite and positive."
        )

    return value


def _require_finite(
    value: float,
    name: str,
) -> float:
    if not math.isfinite(value):
        raise FemCalibrationObservationStoreError(
            f"{name} must be finite."
        )

    return value


def _require_relative_path(
    value: str,
    name: str,
) -> str:
    text = _require_text(
        value,
        name,
    )

    path = Path(
        text
    )

    if (
        path.is_absolute()
        or ".." in path.parts
    ):
        raise FemCalibrationObservationStoreError(
            f"{name} must be repository-relative."
        )

    return path.as_posix()


def _validate_observation(
    observation: FemCalibrationObservation,
) -> None:
    for name, value in (
        (
            "case_id",
            observation.case_id,
        ),
        (
            "case_hash",
            observation.case_hash,
        ),
        (
            "resolution_hash",
            observation.resolution_hash,
        ),
        (
            "execution_generation_id",
            observation.execution_generation_id,
        ),
        (
            "run_id",
            observation.run_id,
        ),
        (
            "trial_source",
            observation.trial_source,
        ),
        (
            "decision_disposition",
            observation.decision_disposition,
        ),
    ):
        _require_text(
            value,
            name,
        )

    _require_sha256(
        observation.case_hash,
        "case_hash",
    )

    _require_sha256(
        observation.resolution_hash,
        "resolution_hash",
    )

    if observation.trial_index < 1:
        raise FemCalibrationObservationStoreError(
            "trial_index must be positive."
        )

    for name, value in (
        (
            "target_force_n",
            observation.target_force_n,
        ),
        (
            "under_head_force_n",
            observation.under_head_force_n,
        ),
        (
            "nut_bearing_force_n",
            observation.nut_bearing_force_n,
        ),
        (
            "member_interface_force_n",
            observation.member_interface_force_n,
        ),
    ):
        _require_positive(
            value,
            name,
        )

    for name, value in (
        (
            "delta_temperature_c",
            observation.delta_temperature_c,
        ),
        (
            "analytical_delta_temperature_c",
            observation.analytical_delta_temperature_c,
        ),
        (
            "extraction_time",
            observation.extraction_time,
        ),
        (
            "thread_normal_force_n",
            observation.thread_normal_force_n,
        ),
    ):
        _require_finite(
            value,
            name,
        )

    if observation.delta_temperature_c >= 0.0:
        raise FemCalibrationObservationStoreError(
            "Calibration delta temperature must represent contraction."
        )

    if (
        observation.analytical_delta_temperature_c
        >= 0.0
    ):
        raise FemCalibrationObservationStoreError(
            "Analytical calibration seed must represent contraction."
        )

    if observation.extraction_time < 0.0:
        raise FemCalibrationObservationStoreError(
            "extraction_time must be non-negative."
        )

    if observation.thread_normal_force_n < 0.0:
        raise FemCalibrationObservationStoreError(
            "thread_normal_force_n must be non-negative."
        )

    _require_relative_path(
        observation.dat_relative_path,
        "dat_relative_path",
    )

    _require_sha256(
        observation.dat_sha256,
        "dat_sha256",
    )

    _require_relative_path(
        observation.preparation_relative_path,
        "preparation_relative_path",
    )

    _require_sha256(
        observation.preparation_sha256,
        "preparation_sha256",
    )

    correction = (
        observation.proportional_correction_factor
    )

    if (
        not math.isfinite(
            correction
        )
        or correction <= 0.0
    ):
        raise FemCalibrationObservationStoreError(
            "Derived proportional correction factor is non-physical."
        )


def observation_natural_key(
    observation: FemCalibrationObservation,
) -> dict[str, str]:
    """Stable identity of one governed solved calibration run."""

    return {
        "case_hash": observation.case_hash,
        "resolution_hash": (
            observation.resolution_hash
        ),
        "geometry_generation_id": (
            observation.geometry_identity.generation_id
        ),
        "geometry_realization_id": (
            observation.geometry_identity.realization_id
        ),
        "execution_generation_id": (
            observation.execution_generation_id
        ),
        "run_id": observation.run_id,
    }


def observation_id(
    observation: FemCalibrationObservation,
) -> str:
    """Deterministic ID bound to the governed solved-run identity."""

    _validate_observation(
        observation
    )

    encoded = json.dumps(
        observation_natural_key(
            observation
        ),
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
        allow_nan=False,
    ).encode(
        "utf-8"
    )

    digest = hashlib.sha256(
        encoded
    ).hexdigest()

    return (
        "calobs-"
        + digest[:20]
    )


def observation_to_dict(
    observation: FemCalibrationObservation,
) -> dict[str, Any]:
    """Serialize one observation deterministically."""

    _validate_observation(
        observation
    )

    payload = asdict(
        observation
    )

    payload[
        "feature"
    ][
        "compatibility"
    ][
        "member_material_ids"
    ] = list(
        observation.feature.compatibility.member_material_ids
    )

    payload[
        "derived"
    ] = {
        "measured_mean_clamp_force_n": (
            observation.measured_mean_clamp_force_n
        ),
        "clamp_force_spread_relative": (
            observation.clamp_force_spread_relative
        ),
        "target_relative_error": (
            observation.target_relative_error
        ),
        "proportional_target_delta_temperature_c": (
            observation.proportional_target_delta_temperature_c
        ),
        "proportional_correction_factor": (
            observation.proportional_correction_factor
        ),
        "reusable_for_prediction": (
            observation.reusable_for_prediction
        ),
    }

    return payload


def observation_from_dict(
    payload: dict[str, Any],
) -> FemCalibrationObservation:
    """Deserialize and validate one persisted observation."""

    feature_payload = dict(
        payload[
            "feature"
        ]
    )

    compatibility_payload = dict(
        feature_payload.pop(
            "compatibility"
        )
    )

    compatibility_payload[
        "member_material_ids"
    ] = tuple(
        compatibility_payload[
            "member_material_ids"
        ]
    )

    feature = FemCalibrationFeatureVector(
        compatibility=(
            FemCalibrationCompatibilityKey(
                **compatibility_payload
            )
        ),
        **feature_payload,
    )

    geometry = FemGeometryRealizationIdentity(
        **payload[
            "geometry_identity"
        ]
    )

    constructor = dict(
        payload
    )

    constructor.pop(
        "derived",
        None,
    )

    constructor[
        "geometry_identity"
    ] = geometry

    constructor[
        "feature"
    ] = feature

    observation = FemCalibrationObservation(
        **constructor
    )

    _validate_observation(
        observation
    )

    return observation


def new_calibration_observation_store() -> dict[str, Any]:
    """Create an empty V1 store."""

    return {
        "schema": STORE_SCHEMA,
        "schema_version": STORE_SCHEMA_VERSION,
        "meaning": (
            "Governed solved FEM preload-calibration observations. "
            "Includes accepted trials and valid calibration misses. "
            "This store is not the ThreadROM ROM/surrogate dataset."
        ),
        "observations": {},
    }


def _validate_store(
    store: object,
) -> dict[str, Any]:
    if not isinstance(
        store,
        dict,
    ):
        raise FemCalibrationObservationStoreError(
            "Calibration observation store root must be an object."
        )

    if store.get(
        "schema"
    ) != STORE_SCHEMA:
        raise FemCalibrationObservationStoreError(
            "Unexpected calibration observation store schema."
        )

    if store.get(
        "schema_version"
    ) != STORE_SCHEMA_VERSION:
        raise FemCalibrationObservationStoreError(
            "Unexpected calibration observation store schema version."
        )

    observations = store.get(
        "observations"
    )

    if not isinstance(
        observations,
        dict,
    ):
        raise FemCalibrationObservationStoreError(
            "Calibration observation store observations must be an object."
        )

    return store


def register_calibration_observation(
    store: dict[str, Any],
    observation: FemCalibrationObservation,
) -> tuple[str, str]:
    """Register one observation idempotently and fail closed on conflict."""

    root = _validate_store(
        store
    )

    _validate_observation(
        observation
    )

    identifier = observation_id(
        observation
    )

    serialized = observation_to_dict(
        observation
    )

    existing = root[
        "observations"
    ].get(
        identifier
    )

    if existing is None:
        root[
            "observations"
        ][
            identifier
        ] = serialized

        return (
            identifier,
            "REGISTERED",
        )

    if existing != serialized:
        raise FemCalibrationObservationStoreError(
            f"{identifier}: conflicting evidence exists for the same governed calibration run."
        )

    return (
        identifier,
        "REUSED",
    )


def load_calibration_observation_store(
    path: Path,
) -> dict[str, Any]:
    """Load and fully validate a persisted store."""

    store = json.loads(
        path.read_text(
            encoding="utf-8-sig"
        )
    )

    root = _validate_store(
        store
    )

    for identifier, payload in root[
        "observations"
    ].items():
        observation = observation_from_dict(
            payload
        )

        if observation_id(
            observation
        ) != identifier:
            raise FemCalibrationObservationStoreError(
                f"{identifier}: observation identity drift."
            )

    return root


def calibration_observations(
    store: dict[str, Any],
) -> tuple[
    FemCalibrationObservation,
    ...,
]:
    """Return deterministic typed observations."""

    root = _validate_store(
        store
    )

    return tuple(
        observation_from_dict(
            root[
                "observations"
            ][
                identifier
            ]
        )
        for identifier in sorted(
            root[
                "observations"
            ]
        )
    )


def persist_calibration_observation_store(
    path: Path,
    store: dict[str, Any],
) -> None:
    """Atomically persist a deterministic validated V1 store."""

    root = _validate_store(
        store
    )

    # Full typed replay before persistence.
    for identifier, payload in root[
        "observations"
    ].items():
        observation = observation_from_dict(
            payload
        )

        if observation_id(
            observation
        ) != identifier:
            raise FemCalibrationObservationStoreError(
                f"{identifier}: observation identity drift before persistence."
            )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    encoded = (
        json.dumps(
            root,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    )

    temporary = path.with_name(
        path.name
        + ".tmp"
    )

    temporary.write_text(
        encoded,
        encoding="utf-8",
        newline="\n",
    )

    temporary.replace(
        path
    )