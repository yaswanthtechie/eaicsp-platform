import hashlib
import json

import pandas as pd

from src.build_features import build_all_features


class FeatureStore:
    """
    Simple in-memory feature store for caching engineered features.

    Cached features are identified by:
    - dataset contents
    - feature definition version
    - feature configuration
    - date column
    - target column
    """

    def __init__(self):
        self._cache = {}

    def _create_cache_key(
        self,
        df: pd.DataFrame,
        date_col: str,
        target_col: str,
        config: dict | None,
        feature_version: str,
    ) -> str:
        """
        Create a deterministic cache key for a feature computation.
        """

        dataset_hash = hashlib.sha256(
            pd.util.hash_pandas_object(
                df,
                index=True
            ).values.tobytes()
        ).hexdigest()

        definition = {
            "date_col": date_col,
            "target_col": target_col,
            "config": config,
            "feature_version": feature_version,
        }

        definition_hash = hashlib.sha256(
            json.dumps(
                definition,
                sort_keys=True,
                default=str
            ).encode("utf-8")
        ).hexdigest()

        return f"{dataset_hash}:{definition_hash}"

    def get_or_compute(
        self,
        df: pd.DataFrame,
        date_col: str,
        target_col: str,
        config: dict | None = None,
        feature_version: str = "v1",
    ) -> pd.DataFrame:
        """
        Return cached engineered features when available.

        Otherwise, compute the features using build_all_features(),
        store them, and return the result.
        """

        cache_key = self._create_cache_key(
            df=df,
            date_col=date_col,
            target_col=target_col,
            config=config,
            feature_version=feature_version,
        )

        if cache_key in self._cache:
            return self._cache[cache_key].copy()

        features = build_all_features(
            df=df,
            date_col=date_col,
            target_col=target_col,
            config=config,
        )

        self._cache[cache_key] = features.copy()

        return features.copy()

    def clear(self) -> None:
        """Clear all cached feature sets."""

        self._cache.clear()

    def __len__(self) -> int:
        """Return the number of cached feature sets."""

        return len(self._cache)