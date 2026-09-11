"""
Base interface for all models served by the unified ML platform.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseModelAdapter(ABC):
    """
    Common interface that every model adapter must implement.
    """

    model_name: str = ""
    model_version: str = ""

    @abstractmethod
    def predict(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run prediction for the model.

        Parameters
        ----------
        payload:
            Model-specific input payload.

        Returns
        -------
        Dict[str, Any]
            Model-specific prediction result.
        """
        raise NotImplementedError

    def metadata(self) -> Dict[str, str]:
        """
        Return model metadata.
        """

        return {
            "model": self.model_name,
            "model_version": self.model_version,
            "status": "ready",
        }