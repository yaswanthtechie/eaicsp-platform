
"""
Model governance workflow.

A model must have an explicit governance decision before
it can be promoted to Production.

Supported workflow:

    pending -> approved
    pending -> rejected

Invalid workflow:

    approved -> rejected
    rejected -> approved

Governance state is persisted to disk so that decisions
survive between separate Python processes.
"""

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Dict, List, Optional


# Persistent governance state.
# Run commands from ml-services/_reference/
GOVERNANCE_FILE = Path("data/governance.json")


@dataclass
class ApprovalRequest:
    """
    Governance decision request for one exact model version.
    """

    model_name: str
    model_version: str
    requested_by: str
    reason: str

    # Possible values:
    # pending
    # approved
    # rejected
    status: str = "pending"

    # Approval information
    approved_by: Optional[str] = None

    # Rejection information
    rejected_by: Optional[str] = None

    # Reason for approval/rejection
    decision_reason: Optional[str] = None

    requested_at: str = ""
    decided_at: Optional[str] = None


class GovernanceManager:
    """
    Persistent model governance manager.

    Valid workflow:

        pending -> approved
        pending -> rejected

    Invalid workflow:

        approved -> rejected
        rejected -> approved
    """

    def __init__(
        self,
        storage_path: Path = GOVERNANCE_FILE,
    ):
        self.storage_path = Path(storage_path)

        self._lock = Lock()

        self.storage_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._requests: Dict[str, ApprovalRequest] = {}

        self._load()

    # ======================================================
    # Internal Helpers
    # ======================================================

    @staticmethod
    def _key(
        model_name: str,
        model_version: str,
    ) -> str:
        """
        Create a unique key for a model version.

        Example:
            iris_classifier:3
        """

        return f"{model_name}:{model_version}"

    @staticmethod
    def _now() -> str:
        """Return current UTC timestamp."""

        return datetime.now(
            timezone.utc
        ).isoformat()

    def _load(self) -> None:
        """
        Load governance requests from disk.
        """

        if not self.storage_path.exists():
            self._requests = {}
            return

        try:
            with self.storage_path.open(
                "r",
                encoding="utf-8",
            ) as file:

                data = json.load(file)

            loaded_requests: Dict[str, ApprovalRequest] = {}

            for key, value in data.items():

                # Backward compatibility with an older
                # governance.json that does not contain
                # rejected_by.
                value.setdefault(
                    "rejected_by",
                    None,
                )

                loaded_requests[key] = (
                    ApprovalRequest(**value)
                )

            self._requests = loaded_requests

        except (
            json.JSONDecodeError,
            TypeError,
            ValueError,
        ):
            # Do not crash the application because of
            # malformed governance storage.
            self._requests = {}

    def _save(self) -> None:
        """
        Persist governance state atomically.
        """

        data = {
            key: asdict(request)
            for key, request in self._requests.items()
        }

        temporary_file = (
            self.storage_path.with_suffix(".tmp")
        )

        with temporary_file.open(
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                data,
                file,
                indent=2,
            )

        temporary_file.replace(
            self.storage_path
        )

    # ======================================================
    # Request Approval
    # ======================================================

    def request_approval(
        self,
        model_name: str,
        model_version: str,
        requested_by: str,
        reason: str,
    ) -> ApprovalRequest:
        """
        Create a governance request.

        The request is tied to the exact model version.
        """

        if not model_name:
            raise ValueError(
                "model_name is required"
            )

        if not model_version:
            raise ValueError(
                "model_version is required"
            )

        if not requested_by:
            raise ValueError(
                "requested_by is required"
            )

        if not reason:
            raise ValueError(
                "reason is required"
            )

        model_version = str(model_version)

        key = self._key(
            model_name,
            model_version,
        )

        with self._lock:

            existing = self._requests.get(
                key
            )

            # Do not create duplicate requests
            # for the same model version.
            if existing is not None:
                return existing

            request = ApprovalRequest(
                model_name=model_name,
                model_version=model_version,
                requested_by=requested_by,
                reason=reason,
                status="pending",
                requested_at=self._now(),
            )

            self._requests[key] = request

            self._save()

            return request

    # ======================================================
    # Approve
    # ======================================================

    def approve(
        self,
        model_name: str,
        model_version: str,
        approved_by: str,
        reason: str = "",
    ) -> ApprovalRequest:
        """
        Approve an exact model version.
        """

        if not approved_by:
            raise ValueError(
                "approved_by is required"
            )

        model_version = str(model_version)

        key = self._key(
            model_name,
            model_version,
        )

        with self._lock:

            request = self._requests.get(
                key
            )

            if request is None:
                raise ValueError(
                    f"No governance request found "
                    f"for {model_name} version "
                    f"{model_version}"
                )

            # Already approved.
            if request.status == "approved":
                return request

            # Rejected models cannot be approved.
            if request.status == "rejected":
                raise ValueError(
                    "A rejected request cannot "
                    "be approved"
                )

            # Only pending requests can be approved.
            if request.status != "pending":
                raise ValueError(
                    f"Cannot approve request with "
                    f"status={request.status}"
                )

            request.status = "approved"

            request.approved_by = approved_by

            # Clear rejection information if any
            # stale data exists.
            request.rejected_by = None

            request.decision_reason = reason

            request.decided_at = self._now()

            self._save()

            return request

    # ======================================================
    # Reject
    # ======================================================

    def reject(
        self,
        model_name: str,
        model_version: str,
        rejected_by: str,
        reason: str = "",
    ) -> ApprovalRequest:
        """
        Reject an exact model version.
        """

        if not rejected_by:
            raise ValueError(
                "rejected_by is required"
            )

        model_version = str(model_version)

        key = self._key(
            model_name,
            model_version,
        )

        with self._lock:

            request = self._requests.get(
                key
            )

            if request is None:
                raise ValueError(
                    f"No governance request found "
                    f"for {model_name} version "
                    f"{model_version}"
                )

            # Approved models cannot be rejected.
            if request.status == "approved":
                raise ValueError(
                    "An approved request cannot "
                    "be rejected"
                )

            # Already rejected.
            if request.status == "rejected":
                return request

            # Only pending requests can be rejected.
            if request.status != "pending":
                raise ValueError(
                    f"Cannot reject request with "
                    f"status={request.status}"
                )

            request.status = "rejected"

            request.rejected_by = rejected_by

            # A rejected request should not contain
            # approval information.
            request.approved_by = None

            request.decision_reason = reason

            request.decided_at = self._now()

            self._save()

            return request

    # ======================================================
    # Approval Check
    # ======================================================

    def is_approved(
        self,
        model_name: str,
        model_version: str,
    ) -> bool:
        """
        Return True only when the exact model version
        has been approved.
        """

        model_version = str(model_version)

        key = self._key(
            model_name,
            model_version,
        )

        with self._lock:

            request = self._requests.get(
                key
            )

            return (
                request is not None
                and request.status == "approved"
            )

    # ======================================================
    # Required Approval
    # ======================================================

    def require_approval(
        self,
        model_name: str,
        model_version: str,
    ) -> None:
        """
        Block production promotion unless the exact
        model version has governance approval.
        """

        if self.is_approved(
            model_name,
            model_version,
        ):
            return

        request = self.get_request(
            model_name,
            model_version,
        )

        if request is None:
            status = "no governance request"
        else:
            status = request.status

        raise PermissionError(
            "Production promotion blocked: "
            f"{model_name} version "
            f"{model_version} does not have "
            f"governance approval "
            f"(status={status})."
        )

    # ======================================================
    # Get Request
    # ======================================================

    def get_request(
        self,
        model_name: str,
        model_version: str,
    ) -> Optional[ApprovalRequest]:
        """
        Get governance information for an exact
        model version.
        """

        model_version = str(model_version)

        key = self._key(
            model_name,
            model_version,
        )

        with self._lock:

            return self._requests.get(
                key
            )

    # ======================================================
    # List Requests
    # ======================================================

    def list_requests(
        self,
    ) -> List[ApprovalRequest]:
        """
        Return all governance requests.
        """

        with self._lock:

            return list(
                self._requests.values()
            )


# ==========================================================
# Global Governance Manager
# ==========================================================

governance_manager = GovernanceManager()

