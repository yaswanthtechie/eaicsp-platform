from unittest.mock import Mock

import pytest

from src.blue_green import BlueGreenManager
from src.governance import GovernanceManager


class FakeAdapter:
    def __init__(
        self,
        model_name,
        model_version,
    ):
        self.model_name = model_name
        self.model_version = model_version

    def predict(self, payload):
        return {
            "prediction": f"{self.model_version}-prediction"
        }


def create_manager():
    model_manager = Mock()

    adapters = {
        "v1": FakeAdapter(
            "forecast",
            "v1",
        ),
        "v2": FakeAdapter(
            "forecast",
            "v2",
        ),
    }

    def get_version_adapter(
        model_name,
        version,
    ):
        if version not in adapters:
            raise KeyError(
                f"Version '{version}' not found"
            )

        return adapters[version]

    def predict_version(
        model_name,
        version,
        payload,
        variant=None,
        quality_score=None,
    ):
        adapter = adapters[version]

        return {
            "model": adapter.model_name,
            "model_version": adapter.model_version,
            "prediction": (
                f"{version}-prediction"
            ),
            "confidence": None,
            "quality_score": quality_score,
            "latency_ms": 1.0,
        }

    # ------------------------------------------------------
    # Version lookup
    # ------------------------------------------------------

    model_manager.get_version_adapter.side_effect = (
        get_version_adapter
    )

    # ------------------------------------------------------
    # Blue-Green prediction
    # ------------------------------------------------------

    model_manager.predict_version.side_effect = (
        predict_version
    )

    # ------------------------------------------------------
    # Fix 3:
    # Blue must represent the version currently serving
    # production traffic.
    # ------------------------------------------------------

    model_manager.get_production_version.return_value = (
        "v1"
    )

    return model_manager


# ==========================================================
# Governance Helpers
# ==========================================================


def create_governance(tmp_path):
    """
    Create an isolated governance manager for a test.
    """

    return GovernanceManager(
        tmp_path / "governance.json"
    )


def approve_green_version(
    governance,
    model_name="forecast",
    model_version="v2",
):
    """
    Create and approve a governance request for
    the Green model version.

    The requester and approver are intentionally
    different to satisfy separation of duties.
    """

    governance.request_approval(
        model_name=model_name,
        model_version=model_version,
        requested_by="ajith",
        reason="candidate model",
    )

    governance.approve(
        model_name=model_name,
        model_version=model_version,
        approved_by="lead",
        reason="reviewed candidate",
    )


def create_governed_manager(tmp_path):
    """
    Create a Blue-Green manager with governance enabled.
    """

    manager = create_manager()

    governance = create_governance(
        tmp_path
    )

    blue_green = BlueGreenManager(
        manager,
        governance=governance,
    )

    return blue_green, governance


# ==========================================================
# Existing Blue-Green Tests
# ==========================================================


def test_configure_blue_green():
    manager = BlueGreenManager(
        create_manager()
    )

    result = manager.configure(
        model_name="forecast",
        blue_version="v1",
        green_version="v2",
    )

    assert result["model_name"] == "forecast"
    assert result["blue_version"] == "v1"
    assert result["green_version"] == "v2"
    assert result["active_color"] == "blue"
    assert result["active_version"] == "v1"


def test_blue_is_active_initially():
    manager = BlueGreenManager(
        create_manager()
    )

    manager.configure(
        "forecast",
        "v1",
        "v2",
    )

    result = manager.predict(
        "forecast",
        {"history": [100, 110]},
    )

    assert result["model_version"] == "v1"
    assert result["deployment_color"] == "blue"


# ==========================================================
# Fix 3 - Production Version Validation
# ==========================================================


def test_blue_must_be_current_production_version():
    """
    Blue must be the version currently serving production.

    This prevents Blue-Green configuration from silently
    changing the meaning of the known-good Blue version.
    """

    manager = BlueGreenManager(
        create_manager()
    )

    with pytest.raises(
        ValueError,
        match="currently serving production",
    ):
        manager.configure(
            "forecast",
            "v2",
            "v1",
        )


# ==========================================================
# Fix 3 - Real Production Traffic Switch
# ==========================================================


def test_switch_moves_real_production_traffic(
    tmp_path,
):
    """
    Switching Blue -> Green and Green -> Blue must update
    the ModelManager production adapter.

    This verifies that Blue-Green is a real traffic switch,
    not only an internal deployment-state flag.
    """

    model_manager = create_manager()

    governance = GovernanceManager(
        tmp_path / "governance.json"
    )

    blue_green = BlueGreenManager(
        model_manager,
        governance=governance,
    )

    blue_green.configure(
        "forecast",
        "v1",
        "v2",
    )

    # ------------------------------------------------------
    # Green requires governance approval.
    # ------------------------------------------------------

    governance.request_approval(
        "forecast",
        "v2",
        requested_by="ajith",
        reason="candidate",
    )

    governance.approve(
        "forecast",
        "v2",
        approved_by="lead",
        reason="reviewed",
    )

    # ------------------------------------------------------
    # Switch real production traffic to Green.
    # ------------------------------------------------------

    blue_green.switch_to_green(
        "forecast"
    )

    model_manager.set_production_version.assert_called_with(
        "forecast",
        "v2",
    )

    # ------------------------------------------------------
    # Roll back real production traffic to Blue.
    # ------------------------------------------------------

    blue_green.switch_to_blue(
        "forecast"
    )

    model_manager.set_production_version.assert_called_with(
        "forecast",
        "v1",
    )


# ==========================================================
# Governance-Aware Green Switch Tests
# ==========================================================


def test_switch_to_green_is_blocked_until_approved(
    tmp_path,
):
    """
    Green deployment must be blocked when there is
    no governance approval.
    """

    manager = create_manager()

    governance = GovernanceManager(
        tmp_path / "governance.json"
    )

    blue_green = BlueGreenManager(
        manager,
        governance=governance,
    )

    blue_green.configure(
        "forecast",
        "v1",
        "v2",
    )

    # Green must not become active without approval.
    with pytest.raises(
        PermissionError
    ):
        blue_green.switch_to_green(
            "forecast"
        )

    # Deployment must remain on Blue.
    assert (
        blue_green.status(
            "forecast"
        )["active_color"]
        == "blue"
    )

    assert (
        blue_green.status(
            "forecast"
        )["active_version"]
        == "v1"
    )

    # Real production traffic must not move.
    manager.set_production_version.assert_not_called()


def test_switch_to_green_succeeds_after_governance_approval(
    tmp_path,
):
    """
    Green deployment should succeed after the
    candidate version receives governance approval.
    """

    blue_green, governance = (
        create_governed_manager(
            tmp_path
        )
    )

    blue_green.configure(
        "forecast",
        "v1",
        "v2",
    )

    approve_green_version(
        governance,
        model_name="forecast",
        model_version="v2",
    )

    result = blue_green.switch_to_green(
        "forecast"
    )

    assert result["active_color"] == "green"
    assert result["active_version"] == "v2"
    assert result["status"] == "switched"

    # Real production traffic must follow Green.
    blue_green.model_manager.set_production_version.assert_called_with(
        "forecast",
        "v2",
    )


def test_switch_back_to_blue_is_always_allowed(
    tmp_path,
):
    """
    Blue is the known-good version, so switching
    back to Blue must always be allowed as rollback.
    """

    blue_green, governance = (
        create_governed_manager(
            tmp_path
        )
    )

    blue_green.configure(
        "forecast",
        "v1",
        "v2",
    )

    # Approve Green first so we can switch to it.
    approve_green_version(
        governance,
        model_name="forecast",
        model_version="v2",
    )

    blue_green.switch_to_green(
        "forecast"
    )

    result = blue_green.switch_to_blue(
        "forecast"
    )

    assert result["active_color"] == "blue"
    assert result["active_version"] == "v1"
    assert result["status"] == "switched"

    # Real production traffic must return to Blue.
    blue_green.model_manager.set_production_version.assert_called_with(
        "forecast",
        "v1",
    )


def test_green_prediction_works_after_approved_switch(
    tmp_path,
):
    """
    After approved Green deployment, predictions
    must use the Green model version.
    """

    blue_green, governance = (
        create_governed_manager(
            tmp_path
        )
    )

    blue_green.configure(
        "forecast",
        "v1",
        "v2",
    )

    approve_green_version(
        governance,
        model_name="forecast",
        model_version="v2",
    )

    blue_green.switch_to_green(
        "forecast"
    )

    result = blue_green.predict(
        "forecast",
        {"history": [100, 110]},
    )

    assert result["model_version"] == "v2"
    assert result["deployment_color"] == "green"
    assert result["deployment_status"] == "switched"


# ==========================================================
# Existing Switch Tests Updated for Governance
# ==========================================================


def test_switch_to_green():
    """
    Green switch requires governance approval only when
    a governance manager has been injected.

    Without governance, the manager preserves the
    original standalone Blue-Green behavior.
    """

    manager = create_manager()

    # No governance configured.
    blue_green = BlueGreenManager(
        manager
    )

    blue_green.configure(
        "forecast",
        "v1",
        "v2",
    )

    result = blue_green.switch_to_green(
        "forecast"
    )

    assert result["active_color"] == "green"
    assert result["active_version"] == "v2"

    # Real production traffic follows Green.
    manager.set_production_version.assert_called_with(
        "forecast",
        "v2",
    )


def test_green_receives_predictions_after_switch():
    """
    Without an injected governance manager, the
    manager preserves backward-compatible behavior.
    """

    manager = create_manager()

    blue_green = BlueGreenManager(
        manager
    )

    blue_green.configure(
        "forecast",
        "v1",
        "v2",
    )

    blue_green.switch_to_green(
        "forecast"
    )

    result = blue_green.predict(
        "forecast",
        {"history": [100, 110]},
    )

    assert result["model_version"] == "v2"
    assert result["deployment_color"] == "green"

    manager.set_production_version.assert_called_with(
        "forecast",
        "v2",
    )


def test_switch_back_to_blue():
    """
    Verify Blue rollback after Green deployment.
    """

    manager = create_manager()

    blue_green = BlueGreenManager(
        manager
    )

    blue_green.configure(
        "forecast",
        "v1",
        "v2",
    )

    blue_green.switch_to_green(
        "forecast"
    )

    result = blue_green.switch_to_blue(
        "forecast"
    )

    assert result["active_color"] == "blue"
    assert result["active_version"] == "v1"

    manager.set_production_version.assert_called_with(
        "forecast",
        "v1",
    )


# ==========================================================
# Configuration Validation Tests
# ==========================================================


def test_same_versions_are_rejected():
    manager = BlueGreenManager(
        create_manager()
    )

    with pytest.raises(
        ValueError,
        match="must be different",
    ):
        manager.configure(
            "forecast",
            "v1",
            "v1",
        )


def test_missing_version_is_rejected():
    manager = BlueGreenManager(
        create_manager()
    )

    with pytest.raises(KeyError):
        manager.configure(
            "forecast",
            "v1",
            "v3",
        )


# ==========================================================
# Additional Governance Safety Tests
# ==========================================================


def test_governance_approval_for_wrong_version_does_not_allow_green(
    tmp_path,
):
    """
    Approval for another model version must not allow
    the configured Green version to become active.
    """

    blue_green, governance = (
        create_governed_manager(
            tmp_path
        )
    )

    blue_green.configure(
        "forecast",
        "v1",
        "v2",
    )

    # Approve v3, but Green is v2.
    governance.request_approval(
        model_name="forecast",
        model_version="v3",
        requested_by="ajith",
        reason="different candidate",
    )

    governance.approve(
        model_name="forecast",
        model_version="v3",
        approved_by="lead",
        reason="reviewed different candidate",
    )

    with pytest.raises(
        PermissionError
    ):
        blue_green.switch_to_green(
            "forecast"
        )

    assert (
        blue_green.status(
            "forecast"
        )["active_color"]
        == "blue"
    )

    # Real traffic must remain unchanged.
    blue_green.model_manager.set_production_version.assert_not_called()


def test_requester_cannot_approve_green_candidate(
    tmp_path,
):
    """
    Governance separation of duties must be enforced:
    the requester cannot approve their own Green candidate.
    """

    blue_green, governance = (
        create_governed_manager(
            tmp_path
        )
    )

    blue_green.configure(
        "forecast",
        "v1",
        "v2",
    )

    governance.request_approval(
        model_name="forecast",
        model_version="v2",
        requested_by="ajith",
        reason="candidate",
    )

    with pytest.raises(
        ValueError,
        match="requester cannot approve",
    ):
        governance.approve(
            model_name="forecast",
            model_version="v2",
            approved_by="ajith",
            reason="self approval",
        )

    with pytest.raises(
        PermissionError
    ):
        blue_green.switch_to_green(
            "forecast"
        )

    assert (
        blue_green.status(
            "forecast"
        )["active_color"]
        == "blue"
    )

    blue_green.model_manager.set_production_version.assert_not_called()


def test_green_switch_requires_approval_even_after_configuration(
    tmp_path,
):
    """
    Configuration only prepares Blue and Green.
    It must not implicitly approve Green.
    """

    blue_green, governance = (
        create_governed_manager(
            tmp_path
        )
    )

    result = blue_green.configure(
        "forecast",
        "v1",
        "v2",
    )

    assert result["active_color"] == "blue"

    with pytest.raises(
        PermissionError
    ):
        blue_green.switch_to_green(
            "forecast"
        )

    status = blue_green.status(
        "forecast"
    )

    assert status["active_color"] == "blue"
    assert status["active_version"] == "v1"

    blue_green.model_manager.set_production_version.assert_not_called()


def test_rollback_to_blue_does_not_require_governance(
    tmp_path,
):
    """
    Once Green is active, rollback to Blue should not
    require a new governance request.
    """

    blue_green, governance = (
        create_governed_manager(
            tmp_path
        )
    )

    blue_green.configure(
        "forecast",
        "v1",
        "v2",
    )

    approve_green_version(
        governance,
        model_name="forecast",
        model_version="v2",
    )

    blue_green.switch_to_green(
        "forecast"
    )

    result = blue_green.switch_to_blue(
        "forecast"
    )

    assert result["active_color"] == "blue"
    assert result["active_version"] == "v1"

    blue_green.model_manager.set_production_version.assert_called_with(
        "forecast",
        "v1",
    )


def test_prediction_uses_normalized_deployment_model_name(
    tmp_path,
):
    """
    Verify that Blue-Green prediction uses the normalized
    deployment model name rather than the raw request name.
    """

    blue_green, governance = (
        create_governed_manager(
            tmp_path
        )
    )

    blue_green.configure(
        " FORECAST ",
        "v1",
        "v2",
    )

    result = blue_green.predict(
        " FORECAST ",
        {"history": [100, 110]},
    )

    assert result["model"] == "forecast"
    assert result["model_version"] == "v1"
    assert result["deployment_color"] == "blue"