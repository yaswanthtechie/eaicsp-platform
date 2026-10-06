"""
Cold-start forecasting for new SKUs.

Current similarity metadata:
- category
- region

A new SKU has no demand history, so its forecast is estimated from
existing SKUs that share the same category and region.
"""

from __future__ import annotations

from typing import Iterable
import warnings

import numpy as np
import pandas as pd


REQUIRED_COLUMNS = {
    "date",
    "sku_id",
    "category",
    "region",
    "quantity_sold",
}


def _validate_dataframe(df: pd.DataFrame) -> None:
    """Validate the input SKU demand dataframe."""
    if df.empty:
        raise ValueError("Demand dataframe cannot be empty.")

    missing_columns = REQUIRED_COLUMNS - set(df.columns)
    if missing_columns:
        raise ValueError(
            f"Missing required columns: {sorted(missing_columns)}"
        )

    if df["sku_id"].isna().any():
        raise ValueError("sku_id cannot contain missing values.")

    if df["category"].isna().any():
        raise ValueError("category cannot contain missing values.")

    if df["region"].isna().any():
        raise ValueError("region cannot contain missing values.")

    if df["quantity_sold"].isna().any():
        raise ValueError("quantity_sold cannot contain missing values.")

    if (df["quantity_sold"] < 0).any():
        raise ValueError("quantity_sold cannot contain negative values.")


def find_similar_skus(
    df: pd.DataFrame,
    *,
    category: str,
    region: str,
    exclude_sku_id: str | None = None,
) -> list[str]:
    """
    Find existing SKUs matching the requested category and region.

    exclude_sku_id is useful during honest cold-start evaluation so that
    the target SKU's own hidden history cannot leak into its forecast.
    """
    _validate_dataframe(df)

    matches = df[
        (df["category"] == category)
        & (df["region"] == region)
    ]

    if exclude_sku_id is not None:
        matches = matches[matches["sku_id"] != exclude_sku_id]

    return sorted(matches["sku_id"].drop_duplicates().tolist())


def category_region_average_forecast(
    df: pd.DataFrame,
    *,
    category: str,
    region: str,
    horizon: int,
    exclude_sku_id: str | None = None,
) -> list[float]:
    """
    Forecast a cold-start SKU using the average historical demand of
    similar SKUs from the same category and region.
    """
    if horizon <= 0:
        raise ValueError("horizon must be positive.")

    similar_skus = find_similar_skus(
        df,
        category=category,
        region=region,
        exclude_sku_id=exclude_sku_id,
    )

    if not similar_skus:
        raise ValueError(
            "No similar SKUs found for the requested category and region."
        )

    similar_history = df[df["sku_id"].isin(similar_skus)]

    average_demand = float(
        similar_history["quantity_sold"].mean()
    )

    return [average_demand] * horizon
def mean_absolute_error(
    actual: Iterable[float],
    forecast: Iterable[float],
) -> float:
    """Calculate MAE."""
    actual_values = np.asarray(list(actual), dtype=float)
    forecast_values = np.asarray(list(forecast), dtype=float)

    if actual_values.size == 0:
        raise ValueError("Actual values cannot be empty.")

    if actual_values.size != forecast_values.size:
        raise ValueError(
            "Actual and forecast lengths must match."
        )

    if np.any(~np.isfinite(actual_values)):
        raise ValueError("Actual values contain non-finite values.")

    if np.any(~np.isfinite(forecast_values)):
        raise ValueError("Forecast values contain non-finite values.")

    return float(
        np.mean(np.abs(actual_values - forecast_values))
    )


def root_mean_squared_error(
    actual: Iterable[float],
    forecast: Iterable[float],
) -> float:
    """Calculate RMSE."""
    actual_values = np.asarray(list(actual), dtype=float)
    forecast_values = np.asarray(list(forecast), dtype=float)

    if actual_values.size == 0:
        raise ValueError("Actual values cannot be empty.")

    if actual_values.size != forecast_values.size:
        raise ValueError(
            "Actual and forecast lengths must match."
        )

    if np.any(~np.isfinite(actual_values)):
        raise ValueError("Actual values contain non-finite values.")

    if np.any(~np.isfinite(forecast_values)):
        raise ValueError("Forecast values contain non-finite values.")

    return float(
        np.sqrt(
            np.mean(
                (actual_values - forecast_values) ** 2
            )
        )
    )


def category_average_forecast(
    df: pd.DataFrame,
    *,
    category: str,
    horizon: int,
    exclude_sku_id: str | None = None,
) -> list[float]:
    """
    Naive category-average baseline.

    This ignores region and uses all existing SKUs in the category.
    """
    if horizon <= 0:
        raise ValueError("horizon must be positive.")

    _validate_dataframe(df)

    matches = df[df["category"] == category]

    if exclude_sku_id is not None:
        matches = matches[matches["sku_id"] != exclude_sku_id]

    if matches.empty:
        raise ValueError(
            "No SKUs found for the requested category."
        )

    average_demand = float(matches["quantity_sold"].mean())

    return [average_demand] * horizon


def evaluate_cold_start(
    df: pd.DataFrame,
    *,
    sku_id: str,
    hidden_periods: int = 3,
) -> dict:
    """
    Evaluate an existing SKU as if it were a new SKU.

    The final hidden_periods observations become the actual future demand.
    Peer SKUs may contribute only history from before the hidden window,
    so future demand cannot leak into the cold-start forecast.
    """
    if hidden_periods <= 0:
        raise ValueError("hidden_periods must be positive.")

    _validate_dataframe(df)

    sku_history = df[df["sku_id"] == sku_id].copy()

    if sku_history.empty:
        raise ValueError(f"SKU not found: {sku_id}")

    sku_history["date"] = pd.to_datetime(sku_history["date"])
    sku_history = (
        sku_history
        .sort_values("date")
        .reset_index(drop=True)
    )

    if len(sku_history) <= hidden_periods:
        raise ValueError(
            "Not enough SKU history for the requested hidden period."
        )

    hidden_actuals = sku_history.iloc[-hidden_periods:].copy()
    hidden_start = hidden_actuals["date"].min()

    # Peers may only contribute history from BEFORE the hidden window.
    # At launch time, nobody knows how similar products will sell
    # during the hidden/launch months.
    peer_dates = pd.to_datetime(df["date"])

    reference_data = df[
        (df["sku_id"] != sku_id)
        & (peer_dates < hidden_start)
    ].copy()

    if reference_data.empty:
        raise ValueError(
            "No peer history available before the hidden window."
        )

    category = str(sku_history["category"].iloc[0])
    region = str(sku_history["region"].iloc[0])

    try:
        cold_start_forecast = category_region_average_forecast(
            reference_data,
            category=category,
            region=region,
            horizon=hidden_periods,
        )
        forecast_source = "category_region"

    except ValueError as exc:
        if "No similar SKUs" not in str(exc):
            raise

        cold_start_forecast = category_average_forecast(
            reference_data,
            category=category,
            horizon=hidden_periods,
        )
        forecast_source = "category"

    category_baseline = category_average_forecast(
        reference_data,
        category=category,
        horizon=hidden_periods,
    )

    actuals = (
        hidden_actuals["quantity_sold"]
        .astype(float)
        .tolist()
    )

    cold_start_mae = mean_absolute_error(
        actuals,
        cold_start_forecast,
    )

    cold_start_rmse = root_mean_squared_error(
        actuals,
        cold_start_forecast,
    )

    category_baseline_mae = mean_absolute_error(
        actuals,
        category_baseline,
    )

    category_baseline_rmse = root_mean_squared_error(
        actuals,
        category_baseline,
    )

    return {
        "sku_id": sku_id,
        "category": category,
        "region": region,
        "hidden_periods": hidden_periods,
        "forecast_source": forecast_source,
        "actual": actuals,
        "cold_start_forecast": cold_start_forecast,
        "category_baseline": category_baseline,
        "cold_start_mae": cold_start_mae,
        "cold_start_rmse": cold_start_rmse,
        "category_baseline_mae": category_baseline_mae,
        "category_baseline_rmse": category_baseline_rmse,
    }


def evaluate_all_skus(
    df: pd.DataFrame,
    *,
    hidden_periods: int = 3,
) -> list[dict]:
    """Run honest cold-start evaluation for every eligible SKU."""
    _validate_dataframe(df)

    results = []
    skipped = []

    for sku_id in sorted(df["sku_id"].unique()):
        try:
            results.append(
                evaluate_cold_start(
                    df,
                    sku_id=str(sku_id),
                    hidden_periods=hidden_periods,
                )
            )
        except ValueError as exc:
            skipped.append(f"{sku_id}: {exc}")

    if skipped:
        warnings.warn(
            f"Skipped {len(skipped)} SKUs: " + "; ".join(skipped)
        )

    return results
if __name__ == "__main__":
    

    from src.cold_start import evaluate_all_skus

    data_path = "data/hierarchy_sales.csv"

    df = pd.read_csv(data_path)

    results = evaluate_all_skus(
        df,
        hidden_periods=3,
    )

    results_df = pd.DataFrame(results)

    print("=== Milestone 3: Cold-Start Forecasting ===")
    print()
    print(f"Eligible SKUs: {len(results_df)}")
    print()

    print("Forecast source:")
    print(results_df["forecast_source"].value_counts().to_string())
    print()

    print("Average MAE:")
    print(
        results_df[
            [
                "cold_start_mae",
                "category_baseline_mae",
            ]
        ].mean().to_string()
    )
    print()

    results_df["cold_start_wins"] = (
        results_df["cold_start_mae"]
        < results_df["category_baseline_mae"]
    )

    print("Cold-start vs category baseline:")
    print(
        results_df["cold_start_wins"]
        .value_counts()
        .rename(
            {
                True: "Cold-start better",
                False: "Category baseline better",
            }
        )
        .to_string()
    )