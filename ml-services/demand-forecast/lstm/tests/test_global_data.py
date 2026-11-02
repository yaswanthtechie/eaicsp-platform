
import numpy as np
import pandas as pd
import pytest

from src.global_data import UNK, load_global_data


@pytest.fixture
def small_df():
    """Two SKUs with 40 consecutive daily observations each."""
    dates = pd.date_range("2026-01-01", periods=40, freq="D")
    rows = []

    for sku_number, sku in enumerate(["SKU_A", "SKU_B"]):
        for i, date in enumerate(dates):
            rows.append(
                {
                    "date": date,
                    "sku_id": sku,
                    "category": "CAT_A" if sku == "SKU_A" else "CAT_B",
                    "warehouse_id": "WH_1",
                    "sales": float(10 + sku_number * 100 + i),
                    "promotion": int(i % 3 == 0),
                    "day_of_week": int(date.dayofweek),
                }
            )

    return pd.DataFrame(rows)


def test_scaler_fit_on_train_only(small_df, tmp_path):
    csv_path = tmp_path / "small.csv"
    small_df.to_csv(csv_path, index=False)

    data = load_global_data(csv_path, lookback=5, horizon=2)

    train_end = pd.Timestamp(data.split_dates["train_end"])
    train_vals = small_df.loc[
        pd.to_datetime(small_df["date"]) <= train_end, "sales"
    ]

    assert data.scaler.mean_[0] == pytest.approx(train_vals.mean())
    assert data.scaler.scale_[0] == pytest.approx(
        train_vals.std(ddof=0)
    )


def test_no_window_crosses_split_boundary(small_df, tmp_path):
    csv_path = tmp_path / "small.csv"
    small_df.to_csv(csv_path, index=False)

    data = load_global_data(csv_path, lookback=5, horizon=2)

    train_end = pd.Timestamp(data.split_dates["train_end"])
    val_end = pd.Timestamp(data.split_dates["validation_end"])

    train_dates = pd.to_datetime(
        np.asarray(data.train_target_dates).reshape(-1)
    )
    val_dates = pd.to_datetime(
        np.asarray(data.validation_target_dates).reshape(-1)
    )
    test_dates = pd.to_datetime(
        np.asarray(data.test_target_dates).reshape(-1)
    )

    assert train_dates.max() <= train_end
    assert val_dates.min() > train_end
    assert val_dates.max() <= val_end
    assert test_dates.min() > val_end


def test_gap_raises(small_df, tmp_path):
    # Remove one date from SKU_A, creating a missing daily observation.
    missing_date = pd.Timestamp("2026-01-10")
    broken_df = small_df.loc[
        ~(
            (small_df["sku_id"] == "SKU_A")
            & (pd.to_datetime(small_df["date"]) == missing_date)
        )
    ].copy()

    csv_path = tmp_path / "missing_day.csv"
    broken_df.to_csv(csv_path, index=False)

    with pytest.raises(ValueError, match="missing days"):
        load_global_data(csv_path, lookback=5, horizon=2)


def test_sku_without_train_windows_maps_to_unk(small_df, tmp_path):
    # Base SKUs cover the full 40 days. LATE_SKU starts on day 26,
    # after the training cutoff, but has enough rows for later windows.
    dates = pd.date_range("2026-01-26", periods=15, freq="D")

    late_rows = pd.DataFrame(
        {
            "date": dates,
            "sku_id": "LATE_SKU",
            "category": "CAT_LATE",
            "warehouse_id": "WH_2",
            "sales": np.arange(200.0, 215.0),
            "promotion": 0,
            "day_of_week": [int(d.dayofweek) for d in dates],
        }
    )

    df = pd.concat([small_df, late_rows], ignore_index=True)
    csv_path = tmp_path / "late_sku.csv"
    df.to_csv(csv_path, index=False)

    data = load_global_data(csv_path, lookback=5, horizon=2)

    assert "LATE_SKU" not in data.sku_mapping
    assert data.sku_mapping.get("LATE_SKU", UNK) == UNK
    assert "LATE_SKU" in data.skus_mapped_to_unk
    assert "LATE_SKU" not in data.too_short_skipped
