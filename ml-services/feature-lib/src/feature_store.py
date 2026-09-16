import hashlib
import json
import inspect
import pandas as pd
from collections import OrderedDict

from src.build_features import (
    build_all_features,
    add_lag_features,
    add_rolling_features,
    add_calendar_features,
    create_holiday_features,
    add_interaction_features,
)


class FeatureStore:

    """
    Simple in-memory feature store for caching engineered features.

    Cached features are identified by:
    - dataset contents
    - feature definition version
    - feature configuration
    - date column
    - target column
    - group columns
    """

    def __init__(self, max_cache_size: int = 10):
        if max_cache_size < 1:
            raise ValueError("max_cache_size must be at least 1.")

        self.max_cache_size = max_cache_size
        self._cache = OrderedDict()

    def _create_cache_key(
        self,
        df: pd.DataFrame,
        date_col: str,
        target_col: str,
        config: dict | None,
        feature_version: str,
        group_cols=None,
    ) -> str:
        """Create a deterministic cache key for a feature computation."""

        dataset_content = pd.util.hash_pandas_object(
            df,
            index=True,
        ).values.tobytes()

        dataset_schema = json.dumps(
            {
                "columns": list(df.columns),
                "dtypes": [str(dtype) for dtype in df.dtypes],
            },
            sort_keys=True,
        ).encode("utf-8")

        dataset_hash = hashlib.sha256(
            dataset_content + dataset_schema
        ).hexdigest()

        feature_sources = [
            inspect.getsource(build_all_features),
            inspect.getsource(add_lag_features),
            inspect.getsource(add_rolling_features),
            inspect.getsource(add_calendar_features),
            inspect.getsource(create_holiday_features),
            inspect.getsource(add_interaction_features),
        ]

        feature_code_hash = hashlib.sha256(
            "\n".join(feature_sources).encode("utf-8")
        ).hexdigest()

        definition = {
            "date_col": date_col,
            "target_col": target_col,
            "config": config,
            "feature_version": feature_version,
            "group_cols": group_cols,
            "feature_code_hash": feature_code_hash,
        }

        definition_hash = hashlib.sha256(
            json.dumps(
                definition,
                sort_keys=True,
                default=str,
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
        group_cols=None,
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
            group_cols=group_cols,
        )

        if cache_key in self._cache:
            self._cache.move_to_end(cache_key)
            return self._cache[cache_key].copy()

        features = build_all_features(
            df=df,
            date_col=date_col,
            target_col=target_col,
            config=config,
            group_cols=group_cols,
        )

        self._cache[cache_key] = features.copy()
        self._cache.move_to_end(cache_key)

        if len(self._cache) > self.max_cache_size:
            self._cache.popitem(last=False)

        return features.copy()

    def clear(self) -> None:
        """Clear all cached feature sets."""

        self._cache.clear()

    def __len__(self) -> int:
        """Return the number of cached feature sets."""

        return len(self._cache)