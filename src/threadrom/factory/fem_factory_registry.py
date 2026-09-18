"""Persistent governed state registry for FEM factory jobs."""

from __future__ import annotations

import re
import sqlite3

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path


_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_SCHEMA_VERSION = 2


class FemFactoryJobState(StrEnum):
    """Governed lifecycle state of one factory job."""

    PLANNED = "planned"
    PREPARED = "prepared"
    RUNNING = "running"
    SOLVED = "solved"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    FAILED = "failed"
    QUARANTINED = "quarantined"


class FemFactoryPriority(StrEnum):
    """Governed scheduling priority class."""

    RECOVERY = "recovery"
    TRIAL2 = "trial2"
    HIGH_INFORMATION_DOE = "high_information_doe"
    BOUNDARY = "boundary"
    EXPLORATORY = "exploratory"

    @property
    def rank(self) -> int:
        """Return deterministic ascending scheduling rank."""

        return {
            FemFactoryPriority.RECOVERY: 10,
            FemFactoryPriority.TRIAL2: 20,
            FemFactoryPriority.HIGH_INFORMATION_DOE: 30,
            FemFactoryPriority.BOUNDARY: 40,
            FemFactoryPriority.EXPLORATORY: 50,
        }[self]


_ALLOWED_TRANSITIONS = {
    FemFactoryJobState.PLANNED: {
        FemFactoryJobState.PREPARED,
        FemFactoryJobState.FAILED,
        FemFactoryJobState.QUARANTINED,
    },
    FemFactoryJobState.PREPARED: {
        FemFactoryJobState.RUNNING,
        FemFactoryJobState.FAILED,
        FemFactoryJobState.QUARANTINED,
    },
    FemFactoryJobState.RUNNING: {
        FemFactoryJobState.SOLVED,
        FemFactoryJobState.FAILED,
        FemFactoryJobState.QUARANTINED,
    },
    FemFactoryJobState.SOLVED: {
        FemFactoryJobState.ACCEPTED,
        FemFactoryJobState.REJECTED,
        FemFactoryJobState.FAILED,
        FemFactoryJobState.QUARANTINED,
    },
    FemFactoryJobState.ACCEPTED: set(),
    FemFactoryJobState.REJECTED: set(),
    FemFactoryJobState.FAILED: set(),
    FemFactoryJobState.QUARANTINED: set(),
}


@dataclass(frozen=True, slots=True)
class FemFactoryJobRecord:
    """Persistent operational state of one governed FEM job."""

    job_id: int
    case_id: str
    case_hash: str
    trial_index: int
    run_id: str
    priority: FemFactoryPriority
    state: FemFactoryJobState
    preparation_record: str | None
    manifest_path: str | None
    acceptance_record: str | None
    failure_category: str | None
    failure_message: str | None
    lease_owner: str | None
    lease_expires_at_utc: str | None
    lease_generation: int
    created_at_utc: str
    updated_at_utc: str


def _utc_now() -> str:
    return (
        datetime.now(UTC)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


@dataclass(frozen=True, slots=True)
class FemFactoryClaim:
    """Exclusive worker ownership token for one running FEM job."""

    job_id: int
    case_hash: str
    trial_index: int
    run_id: str
    worker_id: str
    lease_generation: int
    lease_expires_at_utc: str
    recovered: bool


def _parse_utc_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(
        value.replace("Z", "+00:00")
    )

    if parsed.tzinfo is None:
        raise ValueError(
            "Factory timestamp must be timezone-aware."
        )

    return parsed.astimezone(UTC)


def _format_utc_timestamp(value: datetime) -> str:
    return (
        value.astimezone(UTC)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


class FemFactoryRegistry:
    """SQLite-backed operational registry for governed FEM jobs."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def _connect(self) -> sqlite3.Connection:
        self.database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        connection = sqlite3.connect(
            self.database_path,
            timeout=30.0,
        )

        connection.row_factory = sqlite3.Row

        connection.execute(
            "PRAGMA foreign_keys = ON"
        )
        connection.execute(
            "PRAGMA busy_timeout = 30000"
        )

        return connection

    def initialize(self) -> None:
        """Create, migrate, or verify the persistent registry schema."""

        connection = self._connect()

        try:
            connection.execute(
                "PRAGMA journal_mode = WAL"
            )

            with connection:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS registry_metadata (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL
                    )
                    """
                )

                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS fem_jobs (
                        job_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        case_id TEXT NOT NULL,
                        case_hash TEXT NOT NULL,
                        trial_index INTEGER NOT NULL,
                        run_id TEXT NOT NULL UNIQUE,
                        priority_class TEXT NOT NULL,
                        priority_rank INTEGER NOT NULL,
                        state TEXT NOT NULL,
                        preparation_record TEXT,
                        manifest_path TEXT,
                        acceptance_record TEXT,
                        failure_category TEXT,
                        failure_message TEXT,
                        lease_owner TEXT,
                        lease_expires_at_utc TEXT,
                        lease_generation INTEGER NOT NULL DEFAULT 0,
                        created_at_utc TEXT NOT NULL,
                        updated_at_utc TEXT NOT NULL,

                        UNIQUE(case_hash, trial_index)
                    )
                    """
                )

                existing = connection.execute(
                    """
                    SELECT value
                    FROM registry_metadata
                    WHERE key = 'schema_version'
                    """
                ).fetchone()

                if existing is None:
                    connection.execute(
                        """
                        INSERT INTO registry_metadata(key, value)
                        VALUES ('schema_version', ?)
                        """,
                        (str(_SCHEMA_VERSION),),
                    )

                elif existing["value"] == "1":
                    columns = {
                        str(row["name"])
                        for row in connection.execute(
                            "PRAGMA table_info(fem_jobs)"
                        ).fetchall()
                    }

                    if "lease_owner" not in columns:
                        connection.execute(
                            """
                            ALTER TABLE fem_jobs
                            ADD COLUMN lease_owner TEXT
                            """
                        )

                    if "lease_expires_at_utc" not in columns:
                        connection.execute(
                            """
                            ALTER TABLE fem_jobs
                            ADD COLUMN lease_expires_at_utc TEXT
                            """
                        )

                    if "lease_generation" not in columns:
                        connection.execute(
                            """
                            ALTER TABLE fem_jobs
                            ADD COLUMN lease_generation
                            INTEGER NOT NULL DEFAULT 0
                            """
                        )

                    connection.execute(
                        """
                        UPDATE registry_metadata
                        SET value = ?
                        WHERE key = 'schema_version'
                        """,
                        (str(_SCHEMA_VERSION),),
                    )

                elif existing["value"] != str(_SCHEMA_VERSION):
                    raise RuntimeError(
                        "Unsupported FEM factory registry "
                        f"schema version: {existing['value']}"
                    )

                connection.execute(
                    """
                    CREATE INDEX IF NOT EXISTS
                    idx_fem_jobs_scheduler
                    ON fem_jobs(
                        state,
                        priority_rank,
                        job_id
                    )
                    """
                )

                connection.execute(
                    """
                    CREATE INDEX IF NOT EXISTS
                    idx_fem_jobs_lease
                    ON fem_jobs(
                        state,
                        lease_expires_at_utc,
                        job_id
                    )
                    """
                )
        finally:
            connection.close()

    @staticmethod
    def _validate_identity(
        *,
        case_id: str,
        case_hash: str,
        trial_index: int,
        run_id: str,
    ) -> None:
        if not case_id.strip():
            raise ValueError(
                "Factory case ID must not be blank."
            )

        if not _SHA256_PATTERN.fullmatch(case_hash):
            raise ValueError(
                "Factory case hash must be 64 lowercase "
                "hexadecimal characters."
            )

        if trial_index < 1:
            raise ValueError(
                "Factory trial index must be >= 1."
            )

        if not run_id.strip():
            raise ValueError(
                "Factory run ID must not be blank."
            )

    @staticmethod
    def _record(row: sqlite3.Row) -> FemFactoryJobRecord:
        return FemFactoryJobRecord(
            job_id=int(row["job_id"]),
            case_id=str(row["case_id"]),
            case_hash=str(row["case_hash"]),
            trial_index=int(row["trial_index"]),
            run_id=str(row["run_id"]),
            priority=FemFactoryPriority(
                row["priority_class"]
            ),
            state=FemFactoryJobState(
                row["state"]
            ),
            preparation_record=row["preparation_record"],
            manifest_path=row["manifest_path"],
            acceptance_record=row["acceptance_record"],
            failure_category=row["failure_category"],
            failure_message=row["failure_message"],
            lease_owner=row["lease_owner"],
            lease_expires_at_utc=row["lease_expires_at_utc"],
            lease_generation=int(row["lease_generation"]),
            created_at_utc=str(row["created_at_utc"]),
            updated_at_utc=str(row["updated_at_utc"]),
        )

    def register_job(
        self,
        *,
        case_id: str,
        case_hash: str,
        trial_index: int,
        run_id: str,
        priority: FemFactoryPriority,
    ) -> FemFactoryJobRecord:
        """Idempotently register one planned factory job."""

        self._validate_identity(
            case_id=case_id,
            case_hash=case_hash,
            trial_index=trial_index,
            run_id=run_id,
        )

        now = _utc_now()
        connection = self._connect()

        try:
            connection.execute("BEGIN IMMEDIATE")

            existing = connection.execute(
                """
                SELECT *
                FROM fem_jobs
                WHERE case_hash = ?
                  AND trial_index = ?
                """,
                (
                    case_hash,
                    trial_index,
                ),
            ).fetchone()

            if existing is not None:
                record = self._record(existing)

                if (
                    record.case_id != case_id
                    or record.run_id != run_id
                    or record.priority is not priority
                ):
                    raise RuntimeError(
                        "Factory job identity drift detected "
                        "for an existing case/trial."
                    )

                connection.commit()
                return record

            connection.execute(
                """
                INSERT INTO fem_jobs(
                    case_id,
                    case_hash,
                    trial_index,
                    run_id,
                    priority_class,
                    priority_rank,
                    state,
                    created_at_utc,
                    updated_at_utc
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    case_id,
                    case_hash,
                    trial_index,
                    run_id,
                    priority.value,
                    priority.rank,
                    FemFactoryJobState.PLANNED.value,
                    now,
                    now,
                ),
            )

            row = connection.execute(
                """
                SELECT *
                FROM fem_jobs
                WHERE case_hash = ?
                  AND trial_index = ?
                """,
                (
                    case_hash,
                    trial_index,
                ),
            ).fetchone()

            if row is None:
                raise RuntimeError(
                    "Factory job registration disappeared "
                    "inside its transaction."
                )

            connection.commit()
            return self._record(row)

        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def get_job(
        self,
        *,
        case_hash: str,
        trial_index: int,
    ) -> FemFactoryJobRecord | None:
        """Return one persisted job if it exists."""

        connection = self._connect()

        try:
            row = connection.execute(
                """
                SELECT *
                FROM fem_jobs
                WHERE case_hash = ?
                  AND trial_index = ?
                """,
                (
                    case_hash,
                    trial_index,
                ),
            ).fetchone()

            return (
                None
                if row is None
                else self._record(row)
            )
        finally:
            connection.close()

    def transition_job(
        self,
        *,
        case_hash: str,
        trial_index: int,
        new_state: FemFactoryJobState,
        preparation_record: str | None = None,
        manifest_path: str | None = None,
        acceptance_record: str | None = None,
        failure_category: str | None = None,
        failure_message: str | None = None,
    ) -> FemFactoryJobRecord:
        """Atomically perform one governed lifecycle transition."""

        connection = self._connect()

        try:
            connection.execute("BEGIN IMMEDIATE")

            row = connection.execute(
                """
                SELECT *
                FROM fem_jobs
                WHERE case_hash = ?
                  AND trial_index = ?
                """,
                (
                    case_hash,
                    trial_index,
                ),
            ).fetchone()

            if row is None:
                raise KeyError(
                    "Factory job does not exist."
                )

            current = self._record(row)

            if (
                current.state is FemFactoryJobState.RUNNING
                and current.lease_owner is not None
            ):
                raise RuntimeError(
                    "Leased RUNNING jobs require a valid "
                    "worker claim token."
                )

            if new_state not in _ALLOWED_TRANSITIONS[
                current.state
            ]:
                raise RuntimeError(
                    "Illegal FEM factory state transition: "
                    f"{current.state.value} -> "
                    f"{new_state.value}"
                )

            prepared = (
                preparation_record
                if preparation_record is not None
                else current.preparation_record
            )
            manifest = (
                manifest_path
                if manifest_path is not None
                else current.manifest_path
            )
            acceptance = (
                acceptance_record
                if acceptance_record is not None
                else current.acceptance_record
            )
            failure_kind = (
                failure_category
                if failure_category is not None
                else current.failure_category
            )
            failure_text = (
                failure_message
                if failure_message is not None
                else current.failure_message
            )

            if (
                new_state
                in {
                    FemFactoryJobState.PREPARED,
                    FemFactoryJobState.RUNNING,
                    FemFactoryJobState.SOLVED,
                    FemFactoryJobState.ACCEPTED,
                    FemFactoryJobState.REJECTED,
                }
                and not prepared
            ):
                raise RuntimeError(
                    "Prepared-or-later factory state requires "
                    "a preparation record."
                )

            if (
                new_state
                in {
                    FemFactoryJobState.SOLVED,
                    FemFactoryJobState.ACCEPTED,
                    FemFactoryJobState.REJECTED,
                }
                and not manifest
            ):
                raise RuntimeError(
                    "Solved-or-later factory state requires "
                    "an immutable FEM run manifest."
                )

            if (
                new_state
                is FemFactoryJobState.ACCEPTED
                and not acceptance
            ):
                raise RuntimeError(
                    "Accepted factory state requires "
                    "an acceptance record."
                )

            if (
                new_state is FemFactoryJobState.FAILED
                and (
                    not failure_kind
                    or not failure_text
                )
            ):
                raise RuntimeError(
                    "Failed factory state requires governed "
                    "failure category and message."
                )

            if (
                new_state
                is FemFactoryJobState.QUARANTINED
                and not failure_text
            ):
                raise RuntimeError(
                    "Quarantined factory state requires "
                    "a reason."
                )

            now = _utc_now()

            cursor = connection.execute(
                """
                UPDATE fem_jobs
                SET state = ?,
                    preparation_record = ?,
                    manifest_path = ?,
                    acceptance_record = ?,
                    failure_category = ?,
                    failure_message = ?,
                    updated_at_utc = ?
                WHERE job_id = ?
                  AND state = ?
                """,
                (
                    new_state.value,
                    prepared,
                    manifest,
                    acceptance,
                    failure_kind,
                    failure_text,
                    now,
                    current.job_id,
                    current.state.value,
                ),
            )

            if cursor.rowcount != 1:
                raise RuntimeError(
                    "Factory job changed concurrently while "
                    "performing a lifecycle transition."
                )

            updated = connection.execute(
                """
                SELECT *
                FROM fem_jobs
                WHERE job_id = ?
                """,
                (current.job_id,),
            ).fetchone()

            if updated is None:
                raise RuntimeError(
                    "Factory job disappeared after transition."
                )

            connection.commit()
            return self._record(updated)

        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def claim_next_job(
        self,
        *,
        worker_id: str,
        lease_seconds: int,
        now_utc: str | None = None,
        recover_expired: bool = False,
    ) -> FemFactoryClaim | None:
        """Atomically claim the next eligible job.

        Expired RUNNING work is always recovered before new PREPARED
        work. This gives recovery the highest scheduler priority.
        """

        if not worker_id.strip():
            raise ValueError(
                "Factory worker ID must not be blank."
            )

        if lease_seconds <= 0:
            raise ValueError(
                "Factory lease duration must be positive."
            )

        now = (
            _parse_utc_timestamp(now_utc)
            if now_utc is not None
            else datetime.now(UTC)
        )

        now_text = _format_utc_timestamp(now)
        expiry_text = _format_utc_timestamp(
            now + timedelta(seconds=lease_seconds)
        )

        connection = self._connect()

        try:
            connection.execute("BEGIN IMMEDIATE")

            row = None

            if recover_expired:
                row = connection.execute(
                    """
                    SELECT *
                    FROM fem_jobs
                    WHERE state = ?
                      AND lease_expires_at_utc IS NOT NULL
                      AND lease_expires_at_utc <= ?
                    ORDER BY priority_rank, job_id
                    LIMIT 1
                    """,
                    (
                        FemFactoryJobState.RUNNING.value,
                        now_text,
                    ),
                ).fetchone()

            recovered = row is not None

            if row is None:
                row = connection.execute(
                    """
                    SELECT *
                    FROM fem_jobs
                    WHERE state = ?
                    ORDER BY priority_rank, job_id
                    LIMIT 1
                    """,
                    (
                        FemFactoryJobState.PREPARED.value,
                    ),
                ).fetchone()

            if row is None:
                connection.commit()
                return None

            current = self._record(row)
            next_generation = (
                current.lease_generation + 1
            )

            cursor = connection.execute(
                """
                UPDATE fem_jobs
                SET state = ?,
                    lease_owner = ?,
                    lease_expires_at_utc = ?,
                    lease_generation = ?,
                    updated_at_utc = ?
                WHERE job_id = ?
                  AND state = ?
                  AND lease_generation = ?
                """,
                (
                    FemFactoryJobState.RUNNING.value,
                    worker_id,
                    expiry_text,
                    next_generation,
                    now_text,
                    current.job_id,
                    current.state.value,
                    current.lease_generation,
                ),
            )

            if cursor.rowcount != 1:
                raise RuntimeError(
                    "Factory job changed concurrently while "
                    "claiming worker ownership."
                )

            updated = connection.execute(
                """
                SELECT *
                FROM fem_jobs
                WHERE job_id = ?
                """,
                (current.job_id,),
            ).fetchone()

            if updated is None:
                raise RuntimeError(
                    "Claimed factory job disappeared."
                )

            record = self._record(updated)
            connection.commit()

            return FemFactoryClaim(
                job_id=record.job_id,
                case_hash=record.case_hash,
                trial_index=record.trial_index,
                run_id=record.run_id,
                worker_id=worker_id,
                lease_generation=record.lease_generation,
                lease_expires_at_utc=expiry_text,
                recovered=recovered,
            )

        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def heartbeat_claim(
        self,
        claim: FemFactoryClaim,
        *,
        lease_seconds: int,
        now_utc: str | None = None,
    ) -> FemFactoryClaim:
        """Extend an active worker lease using ownership fencing."""

        if lease_seconds <= 0:
            raise ValueError(
                "Factory lease duration must be positive."
            )

        now = (
            _parse_utc_timestamp(now_utc)
            if now_utc is not None
            else datetime.now(UTC)
        )

        now_text = _format_utc_timestamp(now)
        expiry_text = _format_utc_timestamp(
            now + timedelta(seconds=lease_seconds)
        )

        connection = self._connect()

        try:
            connection.execute("BEGIN IMMEDIATE")

            cursor = connection.execute(
                """
                UPDATE fem_jobs
                SET lease_expires_at_utc = ?,
                    updated_at_utc = ?
                WHERE job_id = ?
                  AND state = ?
                  AND lease_owner = ?
                  AND lease_generation = ?
                  AND lease_expires_at_utc > ?
                """,
                (
                    expiry_text,
                    now_text,
                    claim.job_id,
                    FemFactoryJobState.RUNNING.value,
                    claim.worker_id,
                    claim.lease_generation,
                    now_text,
                ),
            )

            if cursor.rowcount != 1:
                raise RuntimeError(
                    "Factory lease ownership is stale, expired, "
                    "or has been recovered by another worker."
                )

            connection.commit()

            return FemFactoryClaim(
                job_id=claim.job_id,
                case_hash=claim.case_hash,
                trial_index=claim.trial_index,
                run_id=claim.run_id,
                worker_id=claim.worker_id,
                lease_generation=claim.lease_generation,
                lease_expires_at_utc=expiry_text,
                recovered=claim.recovered,
            )

        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def transition_claimed_job(
        self,
        claim: FemFactoryClaim,
        *,
        new_state: FemFactoryJobState,
        manifest_path: str | None = None,
        failure_category: str | None = None,
        failure_message: str | None = None,
        now_utc: str | None = None,
    ) -> FemFactoryJobRecord:
        """Finish a worker-owned RUNNING job using lease fencing."""

        if new_state not in {
            FemFactoryJobState.SOLVED,
            FemFactoryJobState.FAILED,
            FemFactoryJobState.QUARANTINED,
        }:
            raise ValueError(
                "Worker-owned jobs may transition only to "
                "SOLVED, FAILED, or QUARANTINED."
            )

        now = (
            _parse_utc_timestamp(now_utc)
            if now_utc is not None
            else datetime.now(UTC)
        )
        now_text = _format_utc_timestamp(now)

        connection = self._connect()

        try:
            connection.execute("BEGIN IMMEDIATE")

            row = connection.execute(
                """
                SELECT *
                FROM fem_jobs
                WHERE job_id = ?
                """,
                (claim.job_id,),
            ).fetchone()

            if row is None:
                raise KeyError(
                    "Factory job does not exist."
                )

            current = self._record(row)

            if (
                current.state is not FemFactoryJobState.RUNNING
                or current.lease_owner != claim.worker_id
                or current.lease_generation
                != claim.lease_generation
                or current.lease_expires_at_utc is None
                or current.lease_expires_at_utc <= now_text
            ):
                raise RuntimeError(
                    "Factory lease ownership is stale, expired, "
                    "or has been recovered by another worker."
                )

            manifest = (
                manifest_path
                if manifest_path is not None
                else current.manifest_path
            )

            failure_kind = (
                failure_category
                if failure_category is not None
                else current.failure_category
            )

            failure_text = (
                failure_message
                if failure_message is not None
                else current.failure_message
            )

            if (
                new_state is FemFactoryJobState.SOLVED
                and not manifest
            ):
                raise RuntimeError(
                    "Solved factory state requires an immutable "
                    "FEM run manifest."
                )

            if (
                new_state is FemFactoryJobState.FAILED
                and (
                    not failure_kind
                    or not failure_text
                )
            ):
                raise RuntimeError(
                    "Failed factory state requires governed "
                    "failure category and message."
                )

            if (
                new_state is FemFactoryJobState.QUARANTINED
                and not failure_text
            ):
                raise RuntimeError(
                    "Quarantined factory state requires a reason."
                )

            cursor = connection.execute(
                """
                UPDATE fem_jobs
                SET state = ?,
                    manifest_path = ?,
                    failure_category = ?,
                    failure_message = ?,
                    lease_owner = NULL,
                    lease_expires_at_utc = NULL,
                    updated_at_utc = ?
                WHERE job_id = ?
                  AND state = ?
                  AND lease_owner = ?
                  AND lease_generation = ?
                """,
                (
                    new_state.value,
                    manifest,
                    failure_kind,
                    failure_text,
                    now_text,
                    claim.job_id,
                    FemFactoryJobState.RUNNING.value,
                    claim.worker_id,
                    claim.lease_generation,
                ),
            )

            if cursor.rowcount != 1:
                raise RuntimeError(
                    "Factory lease changed concurrently while "
                    "finishing worker-owned execution."
                )

            updated = connection.execute(
                """
                SELECT *
                FROM fem_jobs
                WHERE job_id = ?
                """,
                (claim.job_id,),
            ).fetchone()

            if updated is None:
                raise RuntimeError(
                    "Factory job disappeared after worker transition."
                )

            connection.commit()
            return self._record(updated)

        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def list_expired_running_jobs(
        self,
        *,
        now_utc: str | None = None,
    ) -> tuple[FemFactoryJobRecord, ...]:
        """Return expired RUNNING jobs in recovery priority order."""

        now = (
            _parse_utc_timestamp(now_utc)
            if now_utc is not None
            else datetime.now(UTC)
        )
        now_text = _format_utc_timestamp(now)

        connection = self._connect()

        try:
            rows = connection.execute(
                """
                SELECT *
                FROM fem_jobs
                WHERE state = ?
                  AND lease_expires_at_utc IS NOT NULL
                  AND lease_expires_at_utc <= ?
                ORDER BY priority_rank, job_id
                """,
                (
                    FemFactoryJobState.RUNNING.value,
                    now_text,
                ),
            ).fetchall()

            return tuple(
                self._record(row)
                for row in rows
            )
        finally:
            connection.close()

    def recover_expired_job(
        self,
        *,
        case_hash: str,
        trial_index: int,
        expected_generation: int,
        worker_id: str,
        lease_seconds: int,
        now_utc: str | None = None,
    ) -> FemFactoryClaim:
        """Atomically recover one specifically adjudicated stale job."""

        if not worker_id.strip():
            raise ValueError(
                "Factory worker ID must not be blank."
            )

        if lease_seconds <= 0:
            raise ValueError(
                "Factory lease duration must be positive."
            )

        now = (
            _parse_utc_timestamp(now_utc)
            if now_utc is not None
            else datetime.now(UTC)
        )

        now_text = _format_utc_timestamp(now)
        expiry_text = _format_utc_timestamp(
            now + timedelta(seconds=lease_seconds)
        )

        connection = self._connect()

        try:
            connection.execute("BEGIN IMMEDIATE")

            row = connection.execute(
                """
                SELECT *
                FROM fem_jobs
                WHERE case_hash = ?
                  AND trial_index = ?
                """,
                (
                    case_hash,
                    trial_index,
                ),
            ).fetchone()

            if row is None:
                raise KeyError(
                    "Factory job does not exist."
                )

            current = self._record(row)

            if (
                current.state is not FemFactoryJobState.RUNNING
                or current.lease_expires_at_utc is None
                or current.lease_expires_at_utc > now_text
                or current.lease_generation != expected_generation
            ):
                raise RuntimeError(
                    "Factory job is no longer the specifically "
                    "adjudicated expired lease."
                )

            next_generation = (
                current.lease_generation + 1
            )

            cursor = connection.execute(
                """
                UPDATE fem_jobs
                SET lease_owner = ?,
                    lease_expires_at_utc = ?,
                    lease_generation = ?,
                    updated_at_utc = ?
                WHERE job_id = ?
                  AND state = ?
                  AND lease_generation = ?
                  AND lease_expires_at_utc <= ?
                """,
                (
                    worker_id,
                    expiry_text,
                    next_generation,
                    now_text,
                    current.job_id,
                    FemFactoryJobState.RUNNING.value,
                    expected_generation,
                    now_text,
                ),
            )

            if cursor.rowcount != 1:
                raise RuntimeError(
                    "Expired factory job changed concurrently "
                    "during recovery."
                )

            connection.commit()

            return FemFactoryClaim(
                job_id=current.job_id,
                case_hash=current.case_hash,
                trial_index=current.trial_index,
                run_id=current.run_id,
                worker_id=worker_id,
                lease_generation=next_generation,
                lease_expires_at_utc=expiry_text,
                recovered=True,
            )

        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def list_jobs(
        self,
        *,
        state: FemFactoryJobState | None = None,
    ) -> tuple[FemFactoryJobRecord, ...]:
        """Return jobs in deterministic scheduler order."""

        connection = self._connect()

        try:
            if state is None:
                rows = connection.execute(
                    """
                    SELECT *
                    FROM fem_jobs
                    ORDER BY priority_rank, job_id
                    """
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT *
                    FROM fem_jobs
                    WHERE state = ?
                    ORDER BY priority_rank, job_id
                    """,
                    (state.value,),
                ).fetchall()

            return tuple(
                self._record(row)
                for row in rows
            )
        finally:
            connection.close()
