from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseModelLoader(ABC):
    """Common interface for loading a model implementation."""

    @abstractmethod
    def load(self) -> Any:
        """Load and return a prediction-capable model."""
        raise NotImplementedError