import pandas as pd
import pytest
from src.feature_usefulness import select_top_features
from src.feature_store import FeatureStore
from src.build_features import build_all_features


def sample_data():
    return pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=10),
            "sales": [10, 12, 15, 14, 18, 20, 22, 21, 25, 28],
        }
    )


def test_feature_store_computes_and_caches(monkeypatch):
    df = sample_data()
    store = FeatureStore()

    call_count = {"count": 0}

    def fake_build_all_features(*args, **kwargs):
        call_count["count"] += 1
        return df.copy()

    monkeypatch.setattr(
        "src.feature_store.build_all_features",
        fake_build_all_features,
    )

    first = store.get_or_compute(
        df=df,
        date_col="date",
        target_col="sales",
        feature_version="v1",
    )

    second = store.get_or_compute(
        df=df,
        date_col="date",
        target_col="sales",
        feature_version="v1",
    )

    assert call_count["count"] == 1
    pd.testing.assert_frame_equal(first, second)
    assert len(store) == 1


def test_different_versions_are_cached_separately(monkeypatch):
    df = sample_data()
    store = FeatureStore()

    call_count = {"count": 0}

    def fake_build_all_features(*args, **kwargs):
        call_count["count"] += 1
        return df.copy()

    monkeypatch.setattr(
        "src.feature_store.build_all_features",
        fake_build_all_features,
    )

    store.get_or_compute(
        df=df,
        date_col="date",
        target_col="sales",
        feature_version="v1",
    )

    store.get_or_compute(
        df=df,
        date_col="date",
        target_col="sales",
        feature_version="v2",
    )

    assert call_count["count"] == 2
    assert len(store) == 2


def test_different_datasets_are_cached_separately(monkeypatch):
    df1 = sample_data()
    df2 = sample_data()
    df2["sales"] = df2["sales"] + 100

    store = FeatureStore()

    call_count = {"count": 0}

    def fake_build_all_features(*args, **kwargs):
        call_count["count"] += 1
        return kwargs["df"].copy()

    monkeypatch.setattr(
        "src.feature_store.build_all_features",
        fake_build_all_features,
    )

    store.get_or_compute(
        df=df1,
        date_col="date",
        target_col="sales",
        feature_version="v1",
    )

    store.get_or_compute(
        df=df2,
        date_col="date",
        target_col="sales",
        feature_version="v1",
    )

    assert call_count["count"] == 2
    assert len(store) == 2


def test_cached_features_can_be_reused_by_multiple_models(monkeypatch):
    df = sample_data()
    store = FeatureStore()

    call_count = {"count": 0}

    def fake_build_all_features(*args, **kwargs):
        call_count["count"] += 1

        return pd.DataFrame(
            {
                "lag_1": [1, 2, 3],
                "lag_7": [7, 8, 9],
                "rolling_mean_7": [10.0, 11.0, 12.0],
                "is_holiday": [0, 1, 0],
            }
        )

    monkeypatch.setattr(
        "src.feature_store.build_all_features",
        fake_build_all_features,
    )

    model_a_features = store.get_or_compute(
        df=df,
        date_col="date",
        target_col="sales",
        feature_version="v1",
    )

    model_b_features = store.get_or_compute(
        df=df,
        date_col="date",
        target_col="sales",
        feature_version="v1",
    )

    model_a_selected = model_a_features[
        ["lag_1", "rolling_mean_7", "is_holiday"]
    ]

    model_b_selected = model_b_features[
        ["lag_7", "is_holiday"]
    ]

    assert call_count["count"] == 1
    assert list(model_a_selected.columns) == [
        "lag_1",
        "rolling_mean_7",
        "is_holiday",
    ]
    assert list(model_b_selected.columns) == [
        "lag_7",
        "is_holiday",
    ]


def test_cached_result_is_protected_from_caller_modification(monkeypatch):
    df = sample_data()
    store = FeatureStore()

    def fake_build_all_features(*args, **kwargs):
        return df.copy()

    monkeypatch.setattr(
        "src.feature_store.build_all_features",
        fake_build_all_features,
    )

    first = store.get_or_compute(
        df=df,
        date_col="date",
        target_col="sales",
        feature_version="v1",
    )

    first["new_feature"] = 123

    second = store.get_or_compute(
        df=df,
        date_col="date",
        target_col="sales",
        feature_version="v1",
    )

    assert "new_feature" not in second.columns


def test_clear_removes_cached_features(monkeypatch):
    df = sample_data()
    store = FeatureStore()

    call_count = {"count": 0}

    def fake_build_all_features(*args, **kwargs):
        call_count["count"] += 1
        return df.copy()

    monkeypatch.setattr(
        "src.feature_store.build_all_features",
        fake_build_all_features,
    )

    store.get_or_compute(
        df=df,
        date_col="date",
        target_col="sales",
        feature_version="v1",
    )

    assert len(store) == 1

    store.clear()

    assert len(store) == 0

    store.get_or_compute(
        df=df,
        date_col="date",
        target_col="sales",
        feature_version="v1",
    )

    assert call_count["count"] == 2

def test_feature_store_feeds_feature_selection(monkeypatch):
    df = sample_data()
    store = FeatureStore()

    def fake_build_all_features(*args, **kwargs):
        return pd.DataFrame(
            {
                "date": df["date"],
                "sales": df["sales"],
                "lag_1": [10, 12, 15, 14, 18, 20, 22, 21, 25, 28],
                "lag_7": [7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
                "rolling_mean_7": [10.0] * 10,
                "is_holiday": [0, 1] * 5,
            }
        )

    monkeypatch.setattr(
        "src.feature_store.build_all_features",
        fake_build_all_features,
    )

    stored_features = store.get_or_compute(
        df=df,
        date_col="date",
        target_col="sales",
        feature_version="v1",
    )

    selected_features = select_top_features(
        stored_features,
        target_col="sales",
        n_features=2,
    )

    assert len(selected_features) == 2
    assert set(selected_features.index).issubset(
        {
            "lag_1",
            "lag_7",
            "rolling_mean_7",
            "is_holiday",
        }
    )
    assert "sales" not in selected_features.index
    assert len(store) == 1

def test_feature_store_cache_key_changes_when_column_name_changes():
    df1 = pd.DataFrame({
        "date": ["2024-01-01", "2024-01-02"],
        "sales": [100, 120],
    })

    df2 = pd.DataFrame({
        "date": ["2024-01-01", "2024-01-02"],
        "revenue": [100, 120],
    })

    store = FeatureStore()

    key1 = store._create_cache_key(
        df=df1,
        date_col="date",
        target_col="sales",
        config={"lags": [1], "windows": [1]},
        feature_version="v1",
    )

    key2 = store._create_cache_key(
        df=df2,
        date_col="date",
        target_col="revenue",
        config={"lags": [1], "windows": [1]},
        feature_version="v1",
    )

    assert key1 != key2

def test_feature_code_hash_changes_when_feature_implementation_changes(monkeypatch):
    df = sample_data()
    store = FeatureStore()

    original_sources = {
        "build_all_features": "build source",
        "add_lag_features": "lag source",
        "add_rolling_features": "rolling source",
        "add_calendar_features": "calendar source",
        "create_holiday_features": "holiday source",
        "add_interaction_features": "interaction source",
    }

    def fake_getsource(function):
        return original_sources[function.__name__]

    monkeypatch.setattr(
        "src.feature_store.inspect.getsource",
        fake_getsource,
    )

    key_before = store._create_cache_key(
        df=df,
        date_col="date",
        target_col="sales",
        config={"lags": [1], "windows": [1]},
        feature_version="v1",
    )

    original_sources["add_lag_features"] = "CHANGED lag source"

    key_after = store._create_cache_key(
        df=df,
        date_col="date",
        target_col="sales",
        config={"lags": [1], "windows": [1]},
        feature_version="v1",
    )

    assert key_before != key_after

def test_feature_store_evicts_oldest_entry_when_cache_is_full(monkeypatch):
    df = sample_data()
    store = FeatureStore(max_cache_size=2)

    def fake_build_all_features(*args, **kwargs):
        return kwargs["df"].copy()

    monkeypatch.setattr(
        "src.feature_store.build_all_features",
        fake_build_all_features,
    )

    store.get_or_compute(
        df=df,
        date_col="date",
        target_col="sales",
        feature_version="v1",
    )

    store.get_or_compute(
        df=df,
        date_col="date",
        target_col="sales",
        feature_version="v2",
    )

    store.get_or_compute(
        df=df,
        date_col="date",
        target_col="sales",
        feature_version="v3",
    )

    assert len(store) == 2

def test_feature_store_lru_keeps_recently_used_entry(monkeypatch):
    df = sample_data()
    store = FeatureStore(max_cache_size=2)

    call_count = {"count": 0}

    def fake_build_all_features(*args, **kwargs):
        call_count["count"] += 1
        return kwargs["df"].copy()

    monkeypatch.setattr(
        "src.feature_store.build_all_features",
        fake_build_all_features,
    )

    store.get_or_compute(
        df=df,
        date_col="date",
        target_col="sales",
        feature_version="v1",
    )

    store.get_or_compute(
        df=df,
        date_col="date",
        target_col="sales",
        feature_version="v2",
    )

    # Reuse v1, making it the most recently used entry.
    store.get_or_compute(
        df=df,
        date_col="date",
        target_col="sales",
        feature_version="v1",
    )

    # v3 should evict v2, not v1.
    store.get_or_compute(
        df=df,
        date_col="date",
        target_col="sales",
        feature_version="v3",
    )

    store.get_or_compute(
        df=df,
        date_col="date",
        target_col="sales",
        feature_version="v1",
    )

    assert call_count["count"] == 3
    assert len(store) == 2

def test_feature_store_rejects_invalid_cache_size():
    with pytest.raises(ValueError, match="max_cache_size"):
        FeatureStore(max_cache_size=0)

def test_feature_version_backward_compatibility():
    df = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=30),
        "target": range(30),
    })

    config = {
        "lags": [1, 7],
        "windows": [7],
    }

    v1_features = build_all_features(
        df,
        date_col="date",
        target_col="target",
        config=config,
        feature_version="v1",
    )

    v2_features = build_all_features(
        df,
        date_col="date",
        target_col="target",
        config=config,
        feature_version="v2",
    )

    assert "target_roll_mean_7" in v1_features.columns
    assert "target_roll_mean_14" not in v1_features.columns

    assert "target_roll_mean_7" in v2_features.columns
    assert "target_roll_mean_14" in v2_features.columns
