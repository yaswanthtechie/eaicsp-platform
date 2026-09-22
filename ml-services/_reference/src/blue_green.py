"""
Blue-Green model deployment support.

Blue:
    Current production model version.

Green:
    Candidate model version prepared for deployment.

The deployment manager allows traffic to be switched between
Blue and Green without changing the model prediction API.
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
    """

    def __init__(self, model_manager) -> None:
        self.model_manager = model_manager
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

        result = self.model_manager.predict_version(
            model_name=model_name,
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

        # Verify the target version is still loaded.
        target_version = (
            deployment.blue_version
            if target_color == "blue"
            else deployment.green_version
        )

        self.model_manager.get_version_adapter(
            model_name,
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
        """Switch production traffic to Blue."""

        return self.switch(
            model_name,
            "blue",
        )

    def switch_to_green(
        self,
        model_name: str,
    ) -> Dict[str, Any]:
        """Switch production traffic to Green."""

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