from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock

from app.core.config import settings
from app.schemas.events import (
    SupplierComplianceAudit,
    SupplierComplianceStatus,
    SupplierStatusChangedEvent,
)
from app.services.supplier_onboarding_service import suppliers


class SupplierComplianceError(Exception):
    """Base exception for supplier compliance state operations."""


class SupplierNotFoundError(SupplierComplianceError):
    """Raised when a supplier ID is missing or invalid."""


class InvalidComplianceStatusError(SupplierComplianceError):
    """Raised when an unsupported compliance status is received."""


class ComplianceDatabaseError(SupplierComplianceError):
    """Raised when durable compliance storage fails."""


SEVERITY = {
    SupplierComplianceStatus.cleared: 0,
    SupplierComplianceStatus.needs_review: 1,
    SupplierComplianceStatus.suspended: 2,
}


SCHEMA = """
CREATE TABLE IF NOT EXISTS processed_events (
    event_id TEXT PRIMARY KEY,
    supplier_key TEXT NOT NULL,
    outcome TEXT NOT NULL CHECK (outcome IN ('applied', 'stale')),
    processed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS supplier_compliance_state (
    supplier_key TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    last_occurred_at TEXT NOT NULL,
    last_event_id TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS compliance_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,
    supplier_key TEXT NOT NULL,
    old_status TEXT NOT NULL,
    new_status TEXT NOT NULL,
    matched_list TEXT NOT NULL,
    reason TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    processed_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_compliance_audit_supplier
ON compliance_audit (supplier_key, id);
"""


class SupplierComplianceService:
    """
    Durable supplier compliance state backed by SQLite.

    State changes, audit entries, and idempotency records are written
    in one transaction.

    Supplier identity comes from the Kafka message key.
    """

    STATUS_MAPPING = {
        "CLEAR": SupplierComplianceStatus.cleared,
        "REVIEW": SupplierComplianceStatus.needs_review,
        "BLOCK": SupplierComplianceStatus.suspended,
    }

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._lock = RLock()
        self._db_path = (
            Path(db_path)
            if db_path is not None
            else Path(settings.COMPLIANCE_DB_PATH)
        )

    # ---------------------------------------------------------
    # DATABASE
    # ---------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        """Open a SQLite connection and ensure the schema exists."""
        try:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)

            conn = sqlite3.connect(
                str(self._db_path),
                timeout=10.0,
            )
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA busy_timeout = 10000")

            try:
                conn.executescript(SCHEMA)
            except Exception:
                conn.close()
                raise

            return conn

        except sqlite3.Error as exc:
            raise ComplianceDatabaseError(
                "Unable to open or initialize compliance database."
            ) from exc
        except OSError as exc:
            raise ComplianceDatabaseError(
                "Unable to create the compliance database directory."
            ) from exc

    @staticmethod
    def _utc_datetime(value: datetime) -> datetime:
        """Normalize a timezone-aware datetime to UTC."""
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("A timezone-aware datetime is required.")

        return value.astimezone(timezone.utc)

    @staticmethod
    def _key_for_supplier_id(supplier_id: str) -> str:
        """Use the canonical supplier ID as the database key."""
        return supplier_id.strip()

    # ---------------------------------------------------------
    # WRITE PATH: KAFKA EVENT
    # ---------------------------------------------------------

    def apply_status_changed_event(
        self,
        event: SupplierStatusChangedEvent,
        *,
        supplier_id: str,
    ) -> bool:
        """
        Persist one compliance event.

        Returns:
            True: event applied and state changed.
            False: duplicate or stale event.

        Supplier records may not exist yet. Events are still persisted
        so their status can be enforced after onboarding.
        """
        if not isinstance(supplier_id, str) or not supplier_id.strip():
            raise SupplierNotFoundError(
                "A valid supplier ID must be supplied by the Kafka message key."
            )

        supplier_id = supplier_id.strip()
        supplier_key = self._key_for_supplier_id(supplier_id)

        if (
            event.occurred_at.tzinfo is None
            or event.occurred_at.utcoffset() is None
        ):
            raise InvalidComplianceStatusError(
                "Event occurred_at must include a timezone."
            )

        new_status = self._map_status(event.payload.new_status)
        occurred_at = self._utc_datetime(event.occurred_at)
        processed_at = datetime.now(timezone.utc)

        occurred_at_text = occurred_at.isoformat()
        processed_at_text = processed_at.isoformat()

        with self._lock:
            # The supplier can be absent if onboarding has not completed.
            supplier = suppliers.get(supplier_id)

            try:
                with closing(self._connect()) as conn:
                    with conn:
                        existing = conn.execute(
                            """
                            SELECT 1
                            FROM processed_events
                            WHERE event_id = ?
                            """,
                            (event.event_id,),
                        ).fetchone()

                        if existing is not None:
                            return False

                        row = conn.execute(
                            """
                            SELECT status, last_occurred_at
                            FROM supplier_compliance_state
                            WHERE supplier_key = ?
                            """,
                            (supplier_key,),
                        ).fetchone()

                        if row is None:
                            old_status = SupplierComplianceStatus.cleared
                        else:
                            try:
                                old_status = SupplierComplianceStatus(
                                    row["status"]
                                )
                            except ValueError:
                                # Corrupt persisted state must not grant access.
                                old_status = (
                                    SupplierComplianceStatus.suspended
                                )

                        if row is not None:
                            try:
                                last_occurred_at = self._utc_datetime(
                                    datetime.fromisoformat(
                                        row["last_occurred_at"]
                                    )
                                )
                            except (ValueError, TypeError) as exc:
                                raise ComplianceDatabaseError(
                                    "Stored compliance timestamp is invalid."
                                ) from exc

                            if self._is_stale(
                                occurred_at,
                                new_status,
                                last_occurred_at,
                                old_status,
                            ):
                                conn.execute(
                                    """
                                    INSERT INTO processed_events (
                                        event_id,
                                        supplier_key,
                                        outcome,
                                        processed_at
                                    )
                                    VALUES (?, ?, 'stale', ?)
                                    """,
                                    (
                                        event.event_id,
                                        supplier_key,
                                        processed_at_text,
                                    ),
                                )
                                return False

                        conn.execute(
                            """
                            INSERT INTO supplier_compliance_state (
                                supplier_key,
                                status,
                                last_occurred_at,
                                last_event_id,
                                updated_at
                            )
                            VALUES (?, ?, ?, ?, ?)
                            ON CONFLICT(supplier_key) DO UPDATE SET
                                status = excluded.status,
                                last_occurred_at = excluded.last_occurred_at,
                                last_event_id = excluded.last_event_id,
                                updated_at = excluded.updated_at
                            """,
                            (
                                supplier_key,
                                new_status.value,
                                occurred_at_text,
                                event.event_id,
                                processed_at_text,
                            ),
                        )

                        conn.execute(
                            """
                            INSERT INTO compliance_audit (
                                event_id,
                                supplier_key,
                                old_status,
                                new_status,
                                matched_list,
                                reason,
                                occurred_at,
                                processed_at
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                event.event_id,
                                supplier_key,
                                old_status.value,
                                new_status.value,
                                json.dumps(
                                    event.payload.matched_list,
                                    ensure_ascii=False,
                                ),
                                event.payload.reason,
                                occurred_at_text,
                                processed_at_text,
                            ),
                        )

                        conn.execute(
                            """
                            INSERT INTO processed_events (
                                event_id,
                                supplier_key,
                                outcome,
                                processed_at
                            )
                            VALUES (?, ?, 'applied', ?)
                            """,
                            (
                                event.event_id,
                                supplier_key,
                                processed_at_text,
                            ),
                        )

                # SQLite transaction completed successfully.
                # Update only an existing onboarding record.
                if supplier is not None:
                    supplier["compliance_access_status"] = new_status.value
                    supplier["compliance_updated_at"] = processed_at

                return True

            except sqlite3.Error as exc:
                raise ComplianceDatabaseError(
                    f"Failed to persist compliance event '{event.event_id}'."
                ) from exc

    # ---------------------------------------------------------
    # STALENESS
    # ---------------------------------------------------------

    @staticmethod
    def _is_stale(
        occurred_at: datetime,
        new_status: SupplierComplianceStatus,
        last_occurred_at: datetime,
        last_status: SupplierComplianceStatus,
    ) -> bool:
        """Reject older events and preserve restrictive status on ties."""
        if occurred_at < last_occurred_at:
            return True

        if occurred_at == last_occurred_at:
            return SEVERITY[new_status] <= SEVERITY[last_status]

        return False

    # ---------------------------------------------------------
    # READ PATH: CURRENT STATE
    # ---------------------------------------------------------

    def get_access_status(
        self,
        supplier_id: str,
    ) -> SupplierComplianceStatus:
        """Read durable compliance state, including pre-onboarding events."""
        if not isinstance(supplier_id, str) or not supplier_id.strip():
            raise SupplierNotFoundError("A valid supplier ID is required.")

        supplier_id = supplier_id.strip()

        with self._lock:
            try:
                with closing(self._connect()) as conn:
                    row = conn.execute(
                        """
                        SELECT status
                        FROM supplier_compliance_state
                        WHERE supplier_key = ?
                        """,
                        (supplier_id,),
                    ).fetchone()

            except sqlite3.Error as exc:
                raise ComplianceDatabaseError(
                    "Failed to read supplier compliance state."
                ) from exc

            if row is None:
                return SupplierComplianceStatus.cleared

            try:
                return SupplierComplianceStatus(row["status"])
            except ValueError:
                return SupplierComplianceStatus.suspended


    # ---------------------------------------------------------
    # READ PATH: AUDIT
    # ---------------------------------------------------------

    def get_audit_history(
        self,
        supplier_id: str,
    ) -> list[SupplierComplianceAudit]:
        """Return audit history in insertion order."""
        if not isinstance(supplier_id, str) or not supplier_id.strip():
            raise SupplierNotFoundError("A valid supplier ID is required.")

        supplier_id = supplier_id.strip()

        with self._lock:
            if supplier_id not in suppliers:
                raise SupplierNotFoundError(
                    f"Supplier '{supplier_id}' was not found."
                )

            try:
                with closing(self._connect()) as conn:
                    rows = conn.execute(
                        """
                        SELECT *
                        FROM compliance_audit
                        WHERE supplier_key = ?
                        ORDER BY id
                        """,
                        (supplier_id,),
                    ).fetchall()

            except sqlite3.Error as exc:
                raise ComplianceDatabaseError(
                    "Failed to read compliance audit history."
                ) from exc

            return [
                SupplierComplianceAudit(
                    event_id=row["event_id"],
                    supplier_key=row["supplier_key"],
                    old_status=row["old_status"],
                    new_status=row["new_status"],
                    matched_list=json.loads(row["matched_list"]),
                    reason=row["reason"],
                    occurred_at=datetime.fromisoformat(row["occurred_at"]),
                    processed_at=datetime.fromisoformat(row["processed_at"]),
                )
                for row in rows
            ]

    # ---------------------------------------------------------
    # IDEMPOTENCY AND TIMESTAMP QUERIES
    # ---------------------------------------------------------

    def is_event_processed(self, event_id: str) -> bool:
        """Return whether an event was applied or marked stale."""
        try:
            with closing(self._connect()) as conn:
                row = conn.execute(
                    """
                    SELECT 1
                    FROM processed_events
                    WHERE event_id = ?
                    """,
                    (event_id,),
                ).fetchone()

                return row is not None

        except sqlite3.Error as exc:
            raise ComplianceDatabaseError(
                f"Failed to check event '{event_id}'."
            ) from exc

    def get_latest_event_time(
        self,
        supplier_id: str,
    ) -> datetime | None:
        """Return the latest accepted event timestamp from SQLite."""
        if not isinstance(supplier_id, str) or not supplier_id.strip():
            raise SupplierNotFoundError("A valid supplier ID is required.")

        supplier_id = supplier_id.strip()

        try:
            with closing(self._connect()) as conn:
                row = conn.execute(
                    """
                    SELECT last_occurred_at
                    FROM supplier_compliance_state
                    WHERE supplier_key = ?
                    """,
                    (supplier_id,),
                ).fetchone()

        except sqlite3.Error as exc:
            raise ComplianceDatabaseError(
                "Failed to read the latest compliance event timestamp."
            ) from exc

        if row is None:
            return None

        try:
            return self._utc_datetime(
                datetime.fromisoformat(row["last_occurred_at"])
            )
        except (ValueError, TypeError) as exc:
            raise ComplianceDatabaseError(
                "Stored compliance timestamp is invalid."
            ) from exc

    # ---------------------------------------------------------
    # STATUS MAPPING
    # ---------------------------------------------------------

    @classmethod
    def _map_status(
        cls,
        status: str,
    ) -> SupplierComplianceStatus:
        """Map external compliance decisions to internal statuses."""
        try:
            return cls.STATUS_MAPPING[status.strip().upper()]
        except (AttributeError, KeyError) as exc:
            raise InvalidComplianceStatusError(
                f"Unsupported compliance status: {status}"
            ) from exc


# Keep the singleton at module level, outside the class.
supplier_compliance_service = SupplierComplianceService()
