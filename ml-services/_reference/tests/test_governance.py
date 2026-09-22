
from pathlib import Path

import pytest

from src.governance import GovernanceManager


@pytest.fixture
def governance(tmp_path: Path) -> GovernanceManager:
    """Use isolated governance state for every test."""
    return GovernanceManager(tmp_path / "governance.json")


def create_request(
    governance: GovernanceManager,
    model_name: str = "iris_classifier",
    model_version: str = "3",
):
    return governance.request_approval(
        model_name=model_name,
        model_version=model_version,
        requested_by="ml-services",
        reason="Model passed the quality gate",
    )


def test_new_model_requires_governance_approval(governance):
    """A newly requested model must start in pending state."""
    request = create_request(governance)

    assert request.status == "pending"
    assert request.model_name == "iris_classifier"
    assert request.model_version == "3"


def test_pending_model_is_blocked_from_production(governance):
    """Production promotion must be blocked while approval is pending."""
    create_request(governance)

    with pytest.raises(PermissionError, match="does not have governance approval"):
        governance.require_approval(
            model_name="iris_classifier",
            model_version="3",
        )


def test_approved_model_can_pass_governance_check(governance):
    """An explicitly approved version can pass the governance check."""
    create_request(governance)

    governance.approve(
        model_name="iris_classifier",
        model_version="3",
        approved_by="reviewer",
        reason="Approved after governance review",
    )

    governance.require_approval(
        model_name="iris_classifier",
        model_version="3",
    )

    request = governance.get_request(
        model_name="iris_classifier",
        model_version="3",
    )

    assert request is not None
    assert request.status == "approved"
    assert request.approved_by == "reviewer"


def test_rejected_model_is_blocked(governance):
    """A rejected model must not be promoted."""
    create_request(governance)

    governance.reject(
        model_name="iris_classifier",
        model_version="3",
        rejected_by="reviewer",
        reason="Model requires further evaluation",
    )

    with pytest.raises(PermissionError, match="status=rejected"):
        governance.require_approval(
            model_name="iris_classifier",
            model_version="3",
        )


def test_unknown_model_version_is_blocked(governance):
    """A model version with no governance request must be blocked."""
    with pytest.raises(PermissionError, match="status=no governance request"):
        governance.require_approval(
            model_name="iris_classifier",
            model_version="99",
        )


def test_wrong_model_version_is_blocked(governance):
    """Approval for one version must not authorize another version."""
    create_request(
        governance,
        model_name="iris_classifier",
        model_version="3",
    )

    governance.approve(
        model_name="iris_classifier",
        model_version="3",
        approved_by="reviewer",
        reason="Approved version 3",
    )

    with pytest.raises(PermissionError):
        governance.require_approval(
            model_name="iris_classifier",
            model_version="4",
        )


def test_approval_is_recorded(governance):
    """Approval metadata must be persisted."""
    create_request(governance)

    request = governance.approve(
        model_name="iris_classifier",
        model_version="3",
        approved_by="reviewer",
        reason="Approved after governance review",
    )

    assert request.status == "approved"
    assert request.approved_by == "reviewer"
    assert request.decision_reason == "Approved after governance review"
    assert request.decided_at is not None


def test_duplicate_approval_does_not_change_approved_request(governance):
    """Approving an already-approved version should preserve the approval."""
    create_request(governance)

    first = governance.approve(
        model_name="iris_classifier",
        model_version="3",
        approved_by="reviewer",
        reason="Approved",
    )

    second = governance.approve(
        model_name="iris_classifier",
        model_version="3",
        approved_by="another-reviewer",
        reason="Second approval",
    )

    assert second.status == "approved"
    assert second.approved_by == first.approved_by
    assert second.decision_reason == first.decision_reason


def test_rejected_model_cannot_be_approved(governance):
    """A rejected request cannot later be approved."""
    create_request(governance)

    governance.reject(
        model_name="iris_classifier",
        model_version="3",
        rejected_by="reviewer",
        reason="Rejected during review",
    )

    with pytest.raises(ValueError, match="rejected"):
        governance.approve(
            model_name="iris_classifier",
            model_version="3",
            approved_by="reviewer",
            reason="Trying to approve again",
        )


def test_approved_model_cannot_be_rejected(governance):
    """An already-approved request cannot be changed to rejected."""
    create_request(governance)

    governance.approve(
        model_name="iris_classifier",
        model_version="3",
        approved_by="reviewer",
        reason="Approved",
    )

    with pytest.raises(ValueError, match="approved"):
        governance.reject(
            model_name="iris_classifier",
            model_version="3",
            rejected_by="reviewer",
            reason="Trying to reject after approval",
        )

