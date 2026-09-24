"""
Blue-Green model deployment support.

Blue:
    Current production model version.

Green:
    Candidate model version prepared for deployment.

The deployment manager allows traffic to be switched between
Blue and Green without changing the model prediction API.

Green promotion requires governance approval.

Blue rollback is always allowed because Blue represents the
known-good production version.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional


@dataclass
class BlueGreenDeployment:
    model_name: str
    blue_version: str
    green_version: str
    active_color: str = "blue"
    status: str = "configured"
    switched_at: Optional[str] = None

    @property
    def active_version(self) -> str:
        """Return the currently active model version."""

        if self.active_color == "blue":
            return self.blue_version

        return self.green_version

    @property
    def inactive_color(self) -> str:
        """Return the inactive deployment color."""

        return (
            "green"
            if self.active_color == "blue"
            else "blue"
        )

    @property
    def inactive_version(self) -> str:
        """Return the inactive model version."""

        if self.active_color == "blue":
            return self.green_version

        return self.blue_version

    def to_dict(self) -> Dict[str, Any]:
        """Return deployment information."""

        return {
            "model_name": self.model_name,
            "blue_version": self.blue_version,
            "green_version": self.green_version,
            "active_color": self.active_color,
            "active_version": self.active_version,
            "inactive_color": self.inactive_color,
            "inactive_version": self.inactive_version,
            "status": self.status,
            "switched_at": self.switched_at,
        }


class BlueGreenManager:
    """
    Manage Blue-Green deployment state for model versions.

    The manager does not load models itself. Model loading remains
    centralized in ModelManager.

    When governance is configured, switching traffic to Green
    requires explicit governance approval for the Green version.

    Switching back to Blue is always allowed as a rollback.
    """

    def __init__(
        self,
        model_manager,
        governance=None,
    ) -> None:
        self.model_manager = model_manager
        self.governance = governance

        self.deployments: Dict[
            str,
            BlueGreenDeployment,
        ] = {}

    # ========================================================
    # Configuration
    # ========================================================

    def configure(
        self,
        model_name: str,
        blue_version: str,
        green_version: str,
    ) -> Dict[str, Any]:
        """
        Configure Blue and Green versions for a model.

        Both versions must already be registered with
        ModelManager.

        Blue must also be the version currently serving
        production traffic. Configuring a different Blue
        version would silently change the production meaning
        of the deployment.
        """

        model_name = model_name.strip().lower()

        if not model_name:
            raise ValueError(
                "model_name cannot be empty."
            )

        if not blue_version.strip():
            raise ValueError(
                "blue_version cannot be empty."
            )

        if not green_version.strip():
            raise ValueError(
                "green_version cannot be empty."
            )

        if blue_version == green_version:
            raise ValueError(
                "Blue and Green versions must be different."
            )

        # Verify Blue exists.
        self.model_manager.get_version_adapter(
            model_name,
            blue_version,
        )

        # Verify Green exists.
        self.model_manager.get_version_adapter(
            model_name,
            green_version,
        )

        # Blue must be the version that is live right now.
        # Otherwise "configure" would silently change what
        # production serves, without governance approval.
        current_version = (
            self.model_manager.get_production_version(
                model_name
            )
        )

        if blue_version != current_version:
            raise ValueError(
                f"blue_version must be the version currently "
                f"serving production traffic "
                f"('{current_version}')."
            )

        deployment = BlueGreenDeployment(
            model_name=model_name,
            blue_version=blue_version,
            green_version=green_version,
            active_color="blue",
            status="ready",
        )

        self.deployments[
            model_name
        ] = deployment

        return deployment.to_dict()

    # ========================================================
    # Deployment Access
    # ========================================================

    def get_deployment(
        self,
        model_name: str,
    ) -> BlueGreenDeployment:
        """Return Blue-Green deployment state."""

        model_name = model_name.strip().lower()

        if model_name not in self.deployments:
            raise KeyError(
                f"No Blue-Green deployment configured "
                f"for model '{model_name}'."
            )

        return self.deployments[
            model_name
        ]

    # ========================================================
    # Prediction
    # ========================================================

    def predict(
        self,
        model_name: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Run prediction using the currently active color.

        Blue or Green is selected according to deployment state.
        """

        deployment = self.get_deployment(
            model_name
        )

        version = deployment.active_version

        # Use the normalized model name stored in the deployment.
        result = self.model_manager.predict_version(
            model_name=deployment.model_name,
            version=version,
            payload=payload,
        )

        result["deployment_color"] = (
            deployment.active_color
        )

        result["deployment_status"] = (
            deployment.status
        )

        return result

    # ========================================================
    # Switch Traffic
    # ========================================================

    def switch(
        self,
        model_name: str,
        target_color: str,
    ) -> Dict[str, Any]:
        """
        Switch active traffic to Blue or Green.

        Switching to Green requires governance approval
        for the exact Green model version.

        Switching back to Blue is always allowed because
        it is a rollback to the known-good version.

        Example:
            switch("forecast", "green")
        """

        deployment = self.get_deployment(
            model_name
        )

        target_color = (
            target_color.strip().lower()
        )

        if target_color not in {
            "blue",
            "green",
        }:
            raise ValueError(
                "target_color must be 'blue' or 'green'."
            )

        if target_color == deployment.active_color:
            return deployment.to_dict()

        # Determine the exact model version associated
        # with the requested deployment color.
        target_version = (
            deployment.blue_version
            if target_color == "blue"
            else deployment.green_version
        )

        # Verify the target version is still loaded.
        self.model_manager.get_version_adapter(
            deployment.model_name,
            target_version,
        )

        # Going live on the candidate (Green) requires
        # explicit governance approval.
        #
        # Switching back to Blue is a rollback to the
        # known-good version and does not require approval.
        if (
            target_color == "green"
            and self.governance is not None
        ):
            self.governance.require_approval(
                deployment.model_name,
                target_version,
            )

        # Governance passed: move REAL production traffic.
        # This makes the switch a deployment rather than
        # a flag that only /blue-green/predict reads.
        self.model_manager.set_production_version(
            deployment.model_name,
            target_version,
        )

        deployment.active_color = target_color

        deployment.status = "switched"

        deployment.switched_at = (
            datetime.now(
                timezone.utc
            ).isoformat()
        )

        return deployment.to_dict()

    # ========================================================
    # Convenience Operations
    # ========================================================

    def switch_to_blue(
        self,
        model_name: str,
    ) -> Dict[str, Any]:
        """
        Switch production traffic to Blue.

        This is the rollback path and does not require
        governance approval.
        """

        return self.switch(
            model_name,
            "blue",
        )

    def switch_to_green(
        self,
        model_name: str,
    ) -> Dict[str, Any]:
        """
        Switch production traffic to Green.

        Green requires governance approval when a governance
        manager has been configured.
        """

        return self.switch(
            model_name,
            "green",
        )

    # ========================================================
    # Status
    # ========================================================

    def status(
        self,
        model_name: str,
    ) -> Dict[str, Any]:
        """Return current Blue-Green deployment status."""

        return self.get_deployment(
            model_name
        ).to_dict()