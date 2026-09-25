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

Governance decisions are also recorded as MLflow model
version tags so that the MLflow registry contains the
governance audit trail.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Dict, List, Optional


logger = logging.getLogger(__name__)


# Persistent governance state.
# Run commands from ml-services/_reference/
GOVERNANCE_FILE = Path(
    "data/governance.json"
)


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

    Every approval/rejection is persisted locally and
    mirrored to the exact MLflow model version as governance
    audit tags.

    The local governance file remains the application
    source of truth. MLflow provides an additional
    registry-level audit trail when the model version
    exists in the MLflow registry.
    """

    def __init__(
        self,
        storage_path: Path = GOVERNANCE_FILE,
    ):
        self.storage_path = Path(
            storage_path
        )

        self._lock = Lock()

        self.storage_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._requests: Dict[
            str,
            ApprovalRequest,
        ] = {}

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

        return (
            f"{model_name}:{model_version}"
        )

    @staticmethod
    def _now() -> str:
        """
        Return current UTC timestamp.
        """

        return datetime.now(
            timezone.utc
        ).isoformat()

    @staticmethod
    def _same_person(a: str, b: str) -> bool:
        """
        Compare identities for separation of duties.

        Case and surrounding whitespace are ignored so that
        "ajith", "Ajith" and " ajith " are treated as the
        same person.
        """

        return a.strip().casefold() == b.strip().casefold()

    @staticmethod
    def _record_mlflow_decision(
        model_name: str,
        model_version: str,
        approver: str,
        decision: str,
        decision_time: str,
        reason: str = "",
    ) -> None:
        """
        Record the governance decision on the exact MLflow
        model version.

        Governance remains persisted in governance.json.

        When the exact model version exists in MLflow,
        the decision is mirrored to MLflow model-version
        tags so the registry contains the governance audit
        trail.

        Unit tests and local governance workflows may use
        logical model versions that are not registered in
        MLflow. In that situation, the local governance
        decision remains valid and the MLflow audit write
        is skipped with a warning.

        MLflow is imported lazily to avoid an import-time
        dependency cycle between governance and MLflow
        utilities.
        """

        try:
            from src.mlflow_utils import (
                record_governance_decision,
            )

            record_governance_decision(
                model_name=model_name,
                model_version=model_version,
                approver=approver,
                decision=decision,
                decision_time=decision_time,
                reason=reason,
            )

        except Exception as exc:
            # Governance itself must not fail simply because
            # an MLflow registry entry is unavailable.
            #
            # This is particularly important for:
            #
            # - Unit tests
            # - Local governance-only workflows
            # - Logical/fake model versions
            #
            # The governance.json state has already been
            # persisted by approve()/reject(), so the
            # governance decision is not lost.
            logger.warning(
                "MLflow governance audit could not be "
                "recorded for %s:%s: %s",
                model_name,
                model_version,
                exc,
            )

    def _load(self) -> None:
        """
        Load governance requests from disk.

        If the governance file is corrupt or unreadable,
        fail closed instead of silently resetting the
        governance state.

        This protects the governance audit trail from
        accidental overwrite.
        """

        if not self.storage_path.exists():
            self._requests = {}
            return

        try:
            with self.storage_path.open(
                "r",
                encoding="utf-8",
            ) as file:

                data = json.load(
                    file
                )

            loaded_requests: Dict[
                str,
                ApprovalRequest,
            ] = {}

            for key, value in data.items():

                # Backward compatibility with an older
                # governance.json that does not contain
                # rejected_by.
                value.setdefault(
                    "rejected_by",
                    None,
                )

                # Backward compatibility for governance
                # files created before decision metadata
                # was introduced.
                value.setdefault(
                    "approved_by",
                    None,
                )

                value.setdefault(
                    "decision_reason",
                    None,
                )

                value.setdefault(
                    "requested_at",
                    "",
                )

                value.setdefault(
                    "decided_at",
                    None,
                )

                value.setdefault(
                    "status",
                    "pending",
                )

                loaded_requests[key] = (
                    ApprovalRequest(
                        **value
                    )
                )

            self._requests = (
                loaded_requests
            )

        except (
            json.JSONDecodeError,
            TypeError,
            ValueError,
        ) as exc:

            raise RuntimeError(
                f"Governance file "
                f"{self.storage_path} "
                "is unreadable. Refusing to "
                "continue so the audit trail "
                "is not overwritten. "
                "Restore it from backup."
            ) from exc

    def _save(self) -> None:
        """
        Persist governance state atomically.
        """

        data = {
            key: asdict(request)
            for key, request
            in self._requests.items()
        }

        temporary_file = (
            self.storage_path.with_suffix(
                ".tmp"
            )
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

        model_version = str(
            model_version
        )

        key = self._key(
            model_name,
            model_version,
        )

        with self._lock:

            # Re-read from disk first. Another process
            # (for example the approve_model CLI) may have
            # changed governance.json since this instance
            # last read it.
            #
            # Without this, _save() could overwrite
            # governance decisions written by another process.
            self._load()

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

        The requester cannot approve their own request.
        This enforces separation of duties.

        The approval decision is persisted locally and,
        when the model version exists in MLflow, mirrored
        as MLflow model-version governance tags.
        """

        if not approved_by:
            raise ValueError(
                "approved_by is required"
            )

        model_version = str(
            model_version
        )

        key = self._key(
            model_name,
            model_version,
        )

        with self._lock:

            # Re-read from disk before evaluating or
            # modifying the governance request.
            self._load()

            request = self._requests.get(
                key
            )

            if request is None:
                raise ValueError(
                    f"No governance request found "
                    f"for {model_name} version "
                    f"{model_version}"
                )

            # Requester cannot approve their own request.
            # This enforces separation of duties.
            if self._same_person(
                approved_by,
                request.requested_by,
            ):
                raise ValueError(
                    "The requester cannot approve "
                    "their own request "
                    "(separation of duties)."
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
                    f"Cannot approve request "
                    f"with status="
                    f"{request.status}"
                )

            request.status = "approved"

            request.approved_by = (
                approved_by
            )

            # Clear rejection information if any
            # stale data exists.
            request.rejected_by = None

            request.decision_reason = (
                reason
            )

            request.decided_at = (
                self._now()
            )

            # Persist governance state first.
            #
            # This guarantees that a valid governance
            # decision is not lost if MLflow is unavailable
            # or the model version does not yet exist in
            # the registry.
            self._save()

            # --------------------------------------------------
            # MLflow governance audit trail
            # --------------------------------------------------
            #
            # Record the decision against this exact model
            # version.
            #
            # The local governance file remains the
            # application source of truth.
            #
            # MLflow contains the registry-level audit
            # metadata when the model version exists.
            #
            # --------------------------------------------------

            self._record_mlflow_decision(
                model_name=model_name,
                model_version=model_version,
                approver=approved_by,
                decision="approved",
                decision_time=(
                    request.decided_at
                ),
                reason=reason,
            )

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

        The rejection decision is persisted locally and,
        when the model version exists in MLflow, mirrored
        as MLflow model-version governance tags.
        """

        if not rejected_by:
            raise ValueError(
                "rejected_by is required"
            )

        model_version = str(
            model_version
        )

        key = self._key(
            model_name,
            model_version,
        )

        with self._lock:

            # Re-read from disk before evaluating or
            # modifying the governance request.
            self._load()

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
                    f"Cannot reject request "
                    f"with status="
                    f"{request.status}"
                )

            request.status = "rejected"

            request.rejected_by = (
                rejected_by
            )

            # A rejected request should not contain
            # approval information.
            request.approved_by = None

            request.decision_reason = (
                reason
            )

            request.decided_at = (
                self._now()
            )

            # Persist governance state first.
            self._save()

            # --------------------------------------------------
            # MLflow governance audit trail
            # --------------------------------------------------
            #
            # Record the rejection against this exact model
            # version.
            #
            # This allows the MLflow registry to show that
            # the candidate was explicitly rejected when the
            # corresponding model version exists.
            #
            # --------------------------------------------------

            self._record_mlflow_decision(
                model_name=model_name,
                model_version=model_version,
                approver=rejected_by,
                decision="rejected",
                decision_time=(
                    request.decided_at
                ),
                reason=reason,
            )

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

        model_version = str(
            model_version
        )

        key = self._key(
            model_name,
            model_version,
        )

        with self._lock:

            # Re-read from disk so a long-running service
            # sees approvals made by another process.
            self._load()

            request = self._requests.get(
                key
            )

            return (
                request is not None
                and request.status
                == "approved"
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
            status = (
                "no governance request"
            )
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

        model_version = str(
            model_version
        )

        key = self._key(
            model_name,
            model_version,
        )

        with self._lock:

            # Re-read from disk so this instance always
            # returns the latest governance state.
            self._load()

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

            # Re-read from disk so the list reflects
            # decisions made by other processes.
            self._load()

            return list(
                self._requests.values()
            )


# ==========================================================
# Global Governance Manager
# ==========================================================

governance_manager = GovernanceManager()