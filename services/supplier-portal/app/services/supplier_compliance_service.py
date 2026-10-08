from __future__ import annotations

from datetime import datetime, timezone
from threading import RLock
from typing import Any

from app.schemas.events import (
    SupplierComplianceAudit,
    SupplierComplianceStatus,
    SupplierStatusChangedEvent,
)
from app.services.supplier_onboarding_service import suppliers


class SupplierComplianceError(Exception):
    """Base exception for supplier compliance state operations."""


class SupplierNotFoundError(SupplierComplianceError):
    """Raised when a supplier does not exist."""


class InvalidComplianceStatusError(SupplierComplianceError):
    """Raised when an unsupported compliance status is received."""


class SupplierComplianceService:
    """
    Manages supplier compliance access state.

    The existing supplier onboarding lifecycle remains untouched.
    Compliance access is maintained separately on the supplier record.
    """

    STATUS_MAPPING = {
        "CLEAR": SupplierComplianceStatus.cleared,
        "REVIEW": SupplierComplianceStatus.needs_review,
        "BLOCK": SupplierComplianceStatus.suspended,
    }

    def __init__(self) -> None:
        self._lock = RLock()

        # Event ids already applied by this service.
        self._processed_event_ids: set[str] = set()

        # Latest accepted compliance event timestamp per supplier.
        self._latest_event_times: dict[str, datetime] = {}

        # Append-only compliance audit history.
        self._audit_history: dict[str, list[SupplierComplianceAudit]] = {}

    def apply_status_changed_event(
        self,
        event: SupplierStatusChangedEvent,
    ) -> bool:
        """
        Apply a supplier compliance status-change event.

        Returns:
            True  -> event changed supplier state.
            False -> event was ignored because it was duplicate/stale.
        """

        with self._lock:
            if event.event_id in self._processed_event_ids:
                return False

            supplier_id = event.payload.supplier_id

            supplier = suppliers.get(supplier_id)

            if supplier is None:
                raise SupplierNotFoundError(
                    f"Supplier '{supplier_id}' was not found."
                )

            new_status = self._map_status(
                event.payload.new_status
            )

            latest_event_at = self._latest_event_times.get(
                supplier_id
            )

            if (
                latest_event_at is not None
                and event.occurred_at <= latest_event_at
            ):
                # Mark the event as processed so that an old event
                # does not keep getting re-applied.
                self._processed_event_ids.add(event.event_id)

                return False

            current_status = self._get_current_status(
                supplier
            )

            processed_at = datetime.now(timezone.utc)

            audit = SupplierComplianceAudit(
                event_id=event.event_id,
                supplier_id=supplier_id,
                old_status=current_status,
                new_status=new_status,
                matched_list=event.payload.matched_list,
                reason=event.payload.reason,
                occurred_at=event.occurred_at,
                processed_at=processed_at,
            )

            # Do not overwrite supplier["status"].
            #
            # supplier["status"] belongs to the onboarding lifecycle:
            # pending_documents -> documents_submitted -> verified
            # -> approved -> active
            #
            # Compliance access is a separate state.
            supplier["compliance_access_status"] = new_status.value
            supplier["compliance_updated_at"] = processed_at

            self._audit_history.setdefault(
                supplier_id,
                [],
            ).append(audit)

            self._latest_event_times[supplier_id] = (
                event.occurred_at
            )

            self._processed_event_ids.add(
                event.event_id
            )

            return True

    def get_access_status(
        self,
        supplier_id: str,
    ) -> SupplierComplianceStatus:
        """Return the current supplier compliance access status."""

        with self._lock:
            supplier = suppliers.get(supplier_id)

            if supplier is None:
                raise SupplierNotFoundError(
                    f"Supplier '{supplier_id}' was not found."
                )

            return self._get_current_status(supplier)

    def can_view(
        self,
        supplier_id: str,
    ) -> bool:
        """
        Supplier can view data when cleared or under review.

        Suspended suppliers cannot access supplier-facing resources.
        """

        status = self.get_access_status(supplier_id)

        return status in {
            SupplierComplianceStatus.cleared,
            SupplierComplianceStatus.needs_review,
        }

    def can_write(
        self,
        supplier_id: str,
    ) -> bool:
        """
        Supplier write operations are allowed only when cleared.

        This is used for supplier actions such as:
        - acknowledging purchase orders
        - submitting invoices
        """

        return (
            self.get_access_status(supplier_id)
            == SupplierComplianceStatus.cleared
        )

    def get_audit_history(
        self,
        supplier_id: str,
    ) -> list[SupplierComplianceAudit]:
        """Return a copy of the supplier's compliance audit history."""

        with self._lock:
            if supplier_id not in suppliers:
                raise SupplierNotFoundError(
                    f"Supplier '{supplier_id}' was not found."
                )

            return list(
                self._audit_history.get(
                    supplier_id,
                    [],
                )
            )

    def is_event_processed(
        self,
        event_id: str,
    ) -> bool:
        """Return whether an event id has already been processed."""

        with self._lock:
            return event_id in self._processed_event_ids

    def get_latest_event_time(
        self,
        supplier_id: str,
    ) -> datetime | None:
        """Return the latest accepted event timestamp."""

        with self._lock:
            return self._latest_event_times.get(
                supplier_id
            )

    @classmethod
    def _map_status(
        cls,
        status: str,
    ) -> SupplierComplianceStatus:
        normalized_status = status.strip().upper()

        try:
            return cls.STATUS_MAPPING[normalized_status]
        except KeyError as exc:
            raise InvalidComplianceStatusError(
                f"Unsupported compliance status: {status}"
            ) from exc

    @staticmethod
    def _get_current_status(
        supplier: dict[str, Any],
    ) -> SupplierComplianceStatus:
        """
        Read compliance state from the supplier record.

        Existing suppliers created before Round 14 do not have
        compliance_access_status, so they are treated as cleared
        until a compliance event changes their state.
        """

        raw_status = supplier.get(
            "compliance_access_status"
        )

        if raw_status is None:
            return SupplierComplianceStatus.cleared

        try:
            return SupplierComplianceStatus(raw_status)
        except ValueError:
            # Existing/corrupted state should not silently grant
            # access. Treat an unknown state as suspended.
            return SupplierComplianceStatus.suspended


supplier_compliance_service = SupplierComplianceService()