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

    with pytest.raises(
        PermissionError,
        match="does not have governance approval",
    ):
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

    with pytest.raises(
        PermissionError,
        match="status=rejected",
    ):
        governance.require_approval(
            model_name="iris_classifier",
            model_version="3",
        )


def test_unknown_model_version_is_blocked(governance):
    """A model version with no governance request must be blocked."""

    with pytest.raises(
        PermissionError,
        match="status=no governance request",
    ):
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
    assert (
        request.decision_reason
        == "Approved after governance review"
    )
    assert request.decided_at is not None


def test_duplicate_approval_does_not_change_approved_request(
    governance,
):
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

    with pytest.raises(
        ValueError,
        match="rejected",
    ):
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

    with pytest.raises(
        ValueError,
        match="approved",
    ):
        governance.reject(
            model_name="iris_classifier",
            model_version="3",
            rejected_by="reviewer",
            reason="Trying to reject after approval",
        )


def test_requester_cannot_self_approve(governance):
    """
    The person who requested the model cannot approve
    the same governance request.

    This verifies the separation-of-duties control.
    """

    governance.request_approval(
        model_name="iris_classifier",
        model_version="3",
        requested_by="ajith",
        reason="Model passed the quality gate",
    )

    with pytest.raises(
        ValueError,
        match="separation of duties",
    ):
        governance.approve(
            model_name="iris_classifier",
            model_version="3",
            approved_by="ajith",
            reason="Self approval",
        )


@pytest.mark.parametrize(
    "approver",
    [
        "Ajith",
        "AJITH",
        " ajith ",
        "ajith\t",
    ],
)
def test_self_approval_cannot_bypass_with_case_or_spaces(
    governance,
    approver,
):
    """
    Self-approval must be rejected even when the approver
    uses different capitalisation or surrounding whitespace.
    """

    governance.request_approval(
        model_name="iris_classifier",
        model_version="3",
        requested_by="ajith",
        reason="Model passed the quality gate",
    )

    with pytest.raises(
        ValueError,
        match="separation of duties",
    ):
        governance.approve(
            model_name="iris_classifier",
            model_version="3",
            approved_by=approver,
            reason="Self approval attempt",
        )


def test_different_reviewer_can_approve_request(governance):
    """
    A different person can approve a request created by
    another requester.
    """

    governance.request_approval(
        model_name="iris_classifier",
        model_version="3",
        requested_by="ajith",
        reason="Model passed the quality gate",
    )

    request = governance.approve(
        model_name="iris_classifier",
        model_version="3",
        approved_by="reviewer",
        reason="Approved after independent review",
    )

    assert request.status == "approved"
    assert request.requested_by == "ajith"
    assert request.approved_by == "reviewer"


def test_corrupt_governance_file_fails_closed(tmp_path):
    """
    A corrupt governance file must not silently reset the
    governance state.
    """

    governance_file = tmp_path / "governance.json"

    governance_file.write_text(
        "{ invalid json",
        encoding="utf-8",
    )

    with pytest.raises(
        RuntimeError,
        match="audit trail is not overwritten",
    ):
        GovernanceManager(governance_file)


def test_running_instance_sees_approval_made_by_another_process(
    tmp_path,
):
    """
    The service's GovernanceManager must see approvals written
    by the approve_model CLI (a separate process) without a restart.
    """

    path = tmp_path / "governance.json"

    server = GovernanceManager(path)
    cli = GovernanceManager(path)

    cli.request_approval(
        model_name="forecast",
        model_version="v2",
        requested_by="ajith",
        reason="Candidate v2",
    )

    cli.approve(
        model_name="forecast",
        model_version="v2",
        approved_by="lead",
        reason="Reviewed",
    )

    assert server.is_approved(
        "forecast",
        "v2",
    ) is True


def test_write_from_one_instance_does_not_erase_another_approval(
    tmp_path,
):
    """
    A save from one instance must not overwrite approvals
    written by another instance.
    """

    path = tmp_path / "governance.json"

    server = GovernanceManager(path)
    cli = GovernanceManager(path)

    cli.request_approval(
        model_name="forecast",
        model_version="v2",
        requested_by="ajith",
        reason="Candidate v2",
    )

    cli.approve(
        model_name="forecast",
        model_version="v2",
        approved_by="lead",
        reason="Reviewed",
    )

    # The server writes after the CLI approved.
    server.request_approval(
        model_name="forecast",
        model_version="v3",
        requested_by="auto_retraining",
        reason="Retrained candidate",
    )

    fresh = GovernanceManager(path)

    assert fresh.is_approved(
        "forecast",
        "v2",
    ) is True

    assert fresh.get_request(
        "forecast",
        "v3",
    ) is not None