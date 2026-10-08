import pandas as pd
import pytest

from feature_lib.asof_join import asof_join


def test_uses_latest_feature_strictly_before_observation():
    observations = pd.DataFrame({
        "observed_at": pd.to_datetime([
            "2026-01-03",
            "2026-01-05",
        ]),
        "entity": ["A", "A"],
    })
    features = pd.DataFrame({
        "available_at": pd.to_datetime([
            "2026-01-01",
            "2026-01-02",
            "2026-01-04",
        ]),
        "entity": ["A", "A", "A"],
        "demand": [10, 20, 40],
    })

    result = asof_join(
        observations, features,
        observation_time="observed_at",
        feature_time="available_at",
        by="entity",
    )

    assert result["demand"].tolist() == [20, 40]


def test_blocks_future_feature_leakage():
    observations = pd.DataFrame({
        "observed_at": pd.to_datetime(["2026-01-02"]),
        "entity": ["A"],
    })
    features = pd.DataFrame({
        "available_at": pd.to_datetime([
            "2026-01-03",
            "2026-01-04",
        ]),
        "entity": ["A", "A"],
        "demand": [999, 1000],
    })

    result = asof_join(
        observations, features,
        observation_time="observed_at",
        feature_time="available_at",
        by="entity",
    )

    assert pd.isna(result.loc[0, "demand"])


def test_excludes_feature_with_exact_matching_timestamp():
    observations = pd.DataFrame({
        "observed_at": pd.to_datetime(["2026-01-02"]),
        "entity": ["A"],
    })
    features = pd.DataFrame({
        "available_at": pd.to_datetime(["2026-01-02"]),
        "entity": ["A"],
        "demand": [50],
    })

    result = asof_join(
        observations, features,
        observation_time="observed_at",
        feature_time="available_at",
        by="entity",
    )

    assert pd.isna(result.loc[0, "demand"])


def test_does_not_match_features_across_entities():
    observations = pd.DataFrame({
        "observed_at": pd.to_datetime(["2026-01-03"]),
        "entity": ["B"],
    })
    features = pd.DataFrame({
        "available_at": pd.to_datetime(["2026-01-01"]),
        "entity": ["A"],
        "demand": [100],
    })

    result = asof_join(
        observations, features,
        observation_time="observed_at",
        feature_time="available_at",
        by="entity",
    )

    assert pd.isna(result.loc[0, "demand"])


def test_preserves_observation_order_and_index():
    observations = pd.DataFrame(
        {
            "observed_at": pd.to_datetime([
                "2026-01-05",
                "2026-01-02",
                "2026-01-04",
            ]),
            "entity": ["A", "A", "A"],
        },
        index=[20, 10, 30],
    )
    features = pd.DataFrame({
        "available_at": pd.to_datetime([
            "2026-01-01",
            "2026-01-03",
        ]),
        "entity": ["A", "A"],
        "demand": [10, 30],
    })

    result = asof_join(
        observations,
        features,
        observation_time="observed_at",
        feature_time="available_at",
        by="entity",
    )

    assert result.index.tolist() == [20, 10, 30]
    assert result["demand"].tolist() == [30, 10, 30]


def test_rejects_missing_time_column():
    observations = pd.DataFrame({"entity": ["A"]})
    features = pd.DataFrame({
        "available_at": pd.to_datetime(["2026-01-01"]),
        "entity": ["A"],
        "demand": [10],
    })

    with pytest.raises(ValueError, match="observation time column"):
        asof_join(
            observations, features,
            observation_time="observed_at",
            feature_time="available_at",
            by="entity",
        )


def test_rejects_null_observation_timestamps():
    observations = pd.DataFrame({
        "observed_at": [pd.NaT],
        "entity": ["A"],
    })
    features = pd.DataFrame({
        "available_at": pd.to_datetime(["2026-01-01"]),
        "entity": ["A"],
        "demand": [10],
    })

    with pytest.raises(ValueError, match="cannot contain null"):
        asof_join(
            observations, features,
            observation_time="observed_at",
            feature_time="available_at",
            by="entity",
        )

def test_rejects_null_feature_availability_timestamps():
    """Reject feature records whose availability time is unknown."""
    observations = pd.DataFrame({
        "observed_at": pd.to_datetime(["2026-01-03"]),
        "entity": ["A"],
    })
    features = pd.DataFrame({
        "available_at": pd.to_datetime(["2026-01-01", None]),
        "entity": ["A", "A"],
        "demand": [10, 20],
    })

    with pytest.raises(ValueError, match="Feature timestamps cannot contain null"):
        asof_join(
            observations,
            features,
            observation_time="observed_at",
            feature_time="available_at",
            by="entity",
        )


def test_rejects_missing_feature_grouping_column():
    """Reject a requested grouping column missing from the features."""
    observations = pd.DataFrame({
        "observed_at": pd.to_datetime(["2026-01-03"]),
        "entity": ["A"],
    })
    features = pd.DataFrame({
        "available_at": pd.to_datetime(["2026-01-01"]),
        "demand": [10],
    })

    with pytest.raises(
        ValueError,
        match="Missing grouping column in features: entity",
    ):
        asof_join(
            observations,
            features,
            observation_time="observed_at",
            feature_time="available_at",
            by="entity",
        )


def test_rejects_mismatched_timestamp_dtypes():
    """Reject incompatible observation and feature timestamp types."""
    observations = pd.DataFrame({
        "observed_at": pd.to_datetime(["2026-01-03"]),
        "entity": ["A"],
    })
    features = pd.DataFrame({
        "available_at": ["2026-01-01"],
        "entity": ["A"],
        "demand": [10],
    })

    with pytest.raises(
        TypeError,
        match="time columns must have matching dtypes",
    ):
        asof_join(
            observations,
            features,
            observation_time="observed_at",
            feature_time="available_at",
            by="entity",
        )


def test_handles_empty_feature_dataframe():
    """Return observations with missing feature values when no features exist."""
    observations = pd.DataFrame(
        {
            "observed_at": pd.to_datetime([
                "2026-01-03",
                "2026-01-02",
            ]),
            "entity": ["A", "B"],
        },
        index=[20, 10],
    )
    features = pd.DataFrame({
        "available_at": pd.Series([], dtype="datetime64[ns]"),
        "entity": pd.Series([], dtype="object"),
        "demand": pd.Series([], dtype="float64"),
    })

    result = asof_join(
        observations,
        features,
        observation_time="observed_at",
        feature_time="available_at",
        by="entity",
    )

    assert result.index.tolist() == [20, 10]
    assert result["entity"].tolist() == ["A", "B"]
    assert result["demand"].isna().all()
    assert len(result) == len(observations)
def test_rejects_null_observation_grouping_key():
    """Reject observations with an unknown grouping key."""
    observations = pd.DataFrame({
        "observed_at": pd.to_datetime(["2026-01-03"]),
        "entity": [None],
    })
    features = pd.DataFrame({
        "available_at": pd.to_datetime(["2026-01-01"]),
        "entity": ["A"],
        "demand": [10],
    })

    with pytest.raises(
        ValueError,
        match="Observation grouping column cannot contain null values: entity",
    ):
        asof_join(
            observations,
            features,
            observation_time="observed_at",
            feature_time="available_at",
            by="entity",
        )


def test_rejects_null_feature_grouping_key():
    """Reject feature records with an unknown grouping key."""
    observations = pd.DataFrame({
        "observed_at": pd.to_datetime(["2026-01-03"]),
        "entity": ["A"],
    })
    features = pd.DataFrame({
        "available_at": pd.to_datetime(["2026-01-01"]),
        "entity": [None],
        "demand": [10],
    })

    with pytest.raises(
        ValueError,
        match="Feature grouping column cannot contain null values: entity",
    ):
        asof_join(
            observations,
            features,
            observation_time="observed_at",
            feature_time="available_at",
            by="entity",
        )
def test_rejects_duplicate_feature_timestamps_for_same_entity():
    """Reject ambiguous feature records for the same entity and time."""
    observations = pd.DataFrame({
        "observed_at": pd.to_datetime(["2026-01-03"]),
        "entity": ["A"],
    })
    features = pd.DataFrame({
        "available_at": pd.to_datetime([
            "2026-01-01",
            "2026-01-01",
        ]),
        "entity": ["A", "A"],
        "demand": [10, 20],
    })

    with pytest.raises(
        ValueError,
        match="duplicate timestamps for the same grouping key",
    ):
        asof_join(
            observations,
            features,
            observation_time="observed_at",
            feature_time="available_at",
            by="entity",
        )
def test_handles_timezone_aware_timestamps():
    """Join correctly when both timestamp columns share a timezone."""
    observations = pd.DataFrame({
        "observed_at": pd.to_datetime(
            ["2026-01-03 12:00:00"],
            utc=True,
        ),
        "entity": ["A"],
    })
    features = pd.DataFrame({
        "available_at": pd.to_datetime(
            ["2026-01-03 10:00:00"],
            utc=True,
        ),
        "entity": ["A"],
        "demand": [25],
    })

    result = asof_join(
        observations,
        features,
        observation_time="observed_at",
        feature_time="available_at",
        by="entity",
    )

    assert result["demand"].iloc[0] == 25


def test_rejects_incompatible_timezone_dtypes():
    """Reject timestamp columns with incompatible timezone dtypes."""
    observations = pd.DataFrame({
        "observed_at": pd.to_datetime(
            ["2026-01-03 12:00:00"],
            utc=True,
        ),
        "entity": ["A"],
    })
    features = pd.DataFrame({
        "available_at": pd.to_datetime(
            ["2026-01-03 10:00:00"]
        ),
        "entity": ["A"],
        "demand": [25],
    })

    with pytest.raises(
        TypeError,
        match="time columns must have matching dtypes",
    ):
        asof_join(
            observations,
            features,
            observation_time="observed_at",
            feature_time="available_at",
            by="entity",
        )
def test_handles_empty_observations():
    """Return an empty result with the original observation columns."""
    observations = pd.DataFrame({
        "observed_at": pd.Series([], dtype="datetime64[ns]"),
        "entity": pd.Series([], dtype="object"),
    })
    features = pd.DataFrame({
        "available_at": pd.to_datetime(["2026-01-01"]),
        "entity": ["A"],
        "demand": [25],
    })

    result = asof_join(
        observations,
        features,
        observation_time="observed_at",
        feature_time="available_at",
        by="entity",
    )

    assert result.empty
    assert result.columns.tolist() == observations.columns.tolist()
    assert result.index.equals(observations.index)


def test_suffixes_overlapping_columns():
    """Apply configured suffixes to overlapping observation and feature columns."""
    observations = pd.DataFrame({
        "observed_at": pd.to_datetime(["2026-01-03"]),
        "entity": ["A"],
        "demand": [30],
    })
    features = pd.DataFrame({
        "available_at": pd.to_datetime(["2026-01-01"]),
        "entity": ["A"],
        "demand": [25],
    })

    result = asof_join(
        observations,
        features,
        observation_time="observed_at",
        feature_time="available_at",
        by="entity",
    )

    assert result["demand_observation"].iloc[0] == 30
    assert result["demand_feature"].iloc[0] == 25
