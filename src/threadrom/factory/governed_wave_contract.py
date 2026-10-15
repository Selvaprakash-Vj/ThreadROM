"""Generic governed diversified-DOE wave execution contract.

This module contains no wave-specific execution implementation.

A wave is described entirely through a validated contract. Derived paths,
artifact names and evidence-schema names therefore do not require another
copied W01/W02/W03 runner.

The contract itself does not authorize execution. Authorization remains bound
to the immutable owner-authorization artifact and preparation-index SHA-256.
"""

from __future__ import annotations

import hashlib
import json
import re

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any


CONTRACT_SCHEMA = (
    "threadrom.governed_wave_execution_contract.v1"
)

_WAVE_TOKEN = re.compile(
    r"^W[0-9]{2}$"
)

_CAMPAIGN_ID = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]*$"
)

_HEX = frozenset(
    "0123456789abcdef"
)


class GovernedWaveContractError(
    RuntimeError
):
    """Fail-closed governed-wave contract error."""


def _require_text(
    value: object,
    name: str,
) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or value != value.strip()
    ):
        raise GovernedWaveContractError(
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
        raise GovernedWaveContractError(
            f"{name} must be exactly 64 lowercase hexadecimal characters."
        )

    return text


@dataclass(frozen=True, slots=True)
class GovernedWaveExecutionContract:
    """All wave-varying inputs consumed by the generic runner."""

    campaign_id: str
    wave_token: str

    expected_owner_authorization_sha256: str
    expected_preparation_index_sha256: str

    authorized_case_count: int
    maximum_concurrent_solver_slots: int
    maximum_trial_index: int

    def __post_init__(
        self,
    ) -> None:
        campaign = _require_text(
            self.campaign_id,
            "campaign_id",
        )

        if _CAMPAIGN_ID.fullmatch(
            campaign
        ) is None:
            raise GovernedWaveContractError(
                "campaign_id contains unsafe path or identifier characters."
            )

        wave = _require_text(
            self.wave_token,
            "wave_token",
        )

        if _WAVE_TOKEN.fullmatch(
            wave
        ) is None:
            raise GovernedWaveContractError(
                "wave_token must have canonical form WNN."
            )

        _require_sha256(
            self.expected_owner_authorization_sha256,
            "expected_owner_authorization_sha256",
        )

        _require_sha256(
            self.expected_preparation_index_sha256,
            "expected_preparation_index_sha256",
        )

        for name, value in (
            (
                "authorized_case_count",
                self.authorized_case_count,
            ),
            (
                "maximum_concurrent_solver_slots",
                self.maximum_concurrent_solver_slots,
            ),
            (
                "maximum_trial_index",
                self.maximum_trial_index,
            ),
        ):
            if (
                not isinstance(
                    value,
                    int,
                )
                or isinstance(
                    value,
                    bool,
                )
                or value <= 0
            ):
                raise GovernedWaveContractError(
                    f"{name} must be a positive integer."
                )

    @property
    def wave_key(
        self,
    ) -> str:
        return self.wave_token.casefold()

    @property
    def wave_id(
        self,
    ) -> str:
        return (
            f"{self.campaign_id}-"
            f"{self.wave_token}"
        )

    @property
    def campaign_root(
        self,
    ) -> PurePosixPath:
        return (
            PurePosixPath(
                "simulations"
            )
            / "staging"
            / "phase3_diversified_doe"
            / self.campaign_id
            / self.wave_token
        )

    @property
    def solver_root(
        self,
    ) -> PurePosixPath:
        return (
            self.campaign_root
            / "solver_preparation"
        )

    @property
    def factory_root(
        self,
    ) -> PurePosixPath:
        return (
            self.campaign_root
            / "factory"
        )

    @property
    def factory_database_path(
        self,
    ) -> PurePosixPath:
        return (
            self.factory_root
            / (
                f"{self.wave_key}"
                "_trial1_factory.sqlite3"
            )
        )

    @property
    def admission_lock_path(
        self,
    ) -> PurePosixPath:
        return (
            self.factory_root
            / (
                f"{self.wave_key}"
                "_adaptive_parallel_admission.lock"
            )
        )

    @property
    def owner_authorization_path(
        self,
    ) -> PurePosixPath:
        return (
            PurePosixPath(
                "docs"
            )
            / "phase3_diversified_doe"
            / "waves"
            / self.wave_id
            / "adaptive_campaign_owner_authorization.json"
        )

    @property
    def preparation_index_path(
        self,
    ) -> PurePosixPath:
        return (
            self.campaign_root
            / (
                f"{self.wave_key}"
                "_trial1_preparation.json"
            )
        )

    @property
    def adaptive_preparation_filename(
        self,
    ) -> str:
        return (
            f"{self.wave_key}"
            "_adaptive_preparation.json"
        )

    @property
    def adaptive_preparation_schema(
        self,
    ) -> str:
        return (
            "threadrom.phase3_diversified_"
            f"{self.wave_key}"
            "_adaptive_preparation.v1"
        )

    @property
    def adaptive_preparation_disposition(
        self,
    ) -> str:
        return (
            f"{self.wave_token}"
            "_ADAPTIVE_TRIAL_PREPARATION_PASS"
        )

    @property
    def worker_prefix(
        self,
    ) -> str:
        return (
            f"TRM-DDOE-{self.wave_token}"
            "-adaptive-worker-"
        )

    @property
    def physics_assessment_filename(
        self,
    ) -> str:
        return (
            f"{self.wave_key}"
            "_governed_full_physics_assessment_v2.json"
        )

    @property
    def nonlinear_progress_filename(
        self,
    ) -> str:
        return (
            f"{self.wave_key}"
            "_nonlinear_progress.json"
        )

    @property
    def external_total_force_filename(
        self,
    ) -> str:
        return (
            f"{self.wave_key}"
            "_external_translational_total_force.json"
        )

    @property
    def external_equilibrium_filename(
        self,
    ) -> str:
        return (
            f"{self.wave_key}"
            "_external_translational_equilibrium.json"
        )

    @property
    def physics_assessment_schema(
        self,
    ) -> str:
        return (
            "threadrom.phase3_diversified_"
            f"{self.wave_key}"
            "_full_physics_assessment.v2"
        )

    @property
    def preflight_title(
        self,
    ) -> str:
        return (
            "THREADROM — "
            f"{self.wave_token} "
            "AUTONOMOUS ADAPTIVE FACTORY PREFLIGHT"
        )

    @property
    def execution_title(
        self,
    ) -> str:
        return (
            "THREADROM — "
            f"{self.wave_token} "
            "AUTONOMOUS ADAPTIVE FACTORY"
        )

    @property
    def completion_message(
        self,
    ) -> str:
        return (
            f"{self.wave_id} — ALL "
            f"{self.authorized_case_count} CASES "
            "GOVERNED FULL-PHYSICS ACCEPTED"
        )

    def canonical_payload(
        self,
    ) -> dict[str, Any]:
        """Return deterministic contract evidence."""

        return {
            "schema": CONTRACT_SCHEMA,
            "campaign_id": self.campaign_id,
            "wave_token": self.wave_token,
            "wave_id": self.wave_id,
            "authority": {
                "path": (
                    self.owner_authorization_path.as_posix()
                ),
                "expected_sha256": (
                    self.expected_owner_authorization_sha256
                ),
            },
            "preparation": {
                "path": (
                    self.preparation_index_path.as_posix()
                ),
                "expected_sha256": (
                    self.expected_preparation_index_sha256
                ),
            },
            "limits": {
                "authorized_case_count": (
                    self.authorized_case_count
                ),
                "maximum_concurrent_solver_slots": (
                    self.maximum_concurrent_solver_slots
                ),
                "maximum_trial_index": (
                    self.maximum_trial_index
                ),
            },
            "paths": {
                "campaign_root": (
                    self.campaign_root.as_posix()
                ),
                "solver_root": (
                    self.solver_root.as_posix()
                ),
                "factory_root": (
                    self.factory_root.as_posix()
                ),
                "factory_database": (
                    self.factory_database_path.as_posix()
                ),
                "admission_lock": (
                    self.admission_lock_path.as_posix()
                ),
            },
            "naming": {
                "adaptive_preparation_filename": (
                    self.adaptive_preparation_filename
                ),
                "adaptive_preparation_schema": (
                    self.adaptive_preparation_schema
                ),
                "adaptive_preparation_disposition": (
                    self.adaptive_preparation_disposition
                ),
                "worker_prefix": (
                    self.worker_prefix
                ),
                "physics_assessment_filename": (
                    self.physics_assessment_filename
                ),
                "physics_assessment_schema": (
                    self.physics_assessment_schema
                ),
                "nonlinear_progress_filename": (
                    self.nonlinear_progress_filename
                ),
                "external_total_force_filename": (
                    self.external_total_force_filename
                ),
                "external_equilibrium_filename": (
                    self.external_equilibrium_filename
                ),
            },
        }

    @property
    def contract_sha256(
        self,
    ) -> str:
        encoded = json.dumps(
            self.canonical_payload(),
            sort_keys=True,
            separators=(
                ",",
                ":",
            ),
            allow_nan=False,
        ).encode(
            "utf-8"
        )

        return hashlib.sha256(
            encoded
        ).hexdigest()


def build_governed_wave_execution_contract(
    *,
    campaign_id: str,
    wave_token: str,
    expected_owner_authorization_sha256: str,
    expected_preparation_index_sha256: str,
    authorized_case_count: int,
    maximum_concurrent_solver_slots: int,
    maximum_trial_index: int,
) -> GovernedWaveExecutionContract:
    """Build a validated wave-agnostic execution contract."""

    return GovernedWaveExecutionContract(
        campaign_id=campaign_id,
        wave_token=wave_token,
        expected_owner_authorization_sha256=(
            expected_owner_authorization_sha256
        ),
        expected_preparation_index_sha256=(
            expected_preparation_index_sha256
        ),
        authorized_case_count=(
            authorized_case_count
        ),
        maximum_concurrent_solver_slots=(
            maximum_concurrent_solver_slots
        ),
        maximum_trial_index=(
            maximum_trial_index
        ),
    )