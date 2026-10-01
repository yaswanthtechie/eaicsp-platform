"""
Intermittent demand classification using ADI and CV².

ADI  = Average Demand Interval
CV²  = Squared Coefficient of Variation

Classification:
    Low ADI  + Low CV²  -> Smooth
    High ADI + Low CV²  -> Intermittent
    Low ADI  + High CV² -> Erratic
    High ADI + High CV² -> Lumpy
"""

from __future__ import annotations

import math
from typing import Iterable

import numpy as np
import pandas as pd


ADI_THRESHOLD = 1.32
CV2_THRESHOLD = 0.49


def calculate_adi(demand: Iterable[float]) -> float:
    """
    Calculate Average Demand Interval.

    ADI = total number of periods / number of non-zero demand periods.

    Returns infinity when there is no demand at all.
    """
    values = np.asarray(list(demand), dtype=float)

    if values.size == 0:
        raise ValueError("Demand history cannot be empty.")

    if np.any(~np.isfinite(values)):
        raise ValueError("Demand history contains non-finite values.")

    if np.any(values < 0):
        raise ValueError("Demand values cannot be negative.")

    non_zero_count = np.count_nonzero(values > 0)

    if non_zero_count == 0:
        return math.inf

    return float(len(values) / non_zero_count)


def calculate_cv2(demand: Iterable[float]) -> float:
    """
    Calculate squared coefficient of variation.

    CV² = (std(non-zero demand) / mean(non-zero demand))²

    Zero-demand periods are excluded because CV² measures
    variability in demand size when demand occurs.
    """
    values = np.asarray(list(demand), dtype=float)

    if values.size == 0:
        raise ValueError("Demand history cannot be empty.")

    if np.any(~np.isfinite(values)):
        raise ValueError("Demand history contains non-finite values.")

    if np.any(values < 0):
        raise ValueError("Demand values cannot be negative.")

    non_zero = values[values > 0]

    if non_zero.size <= 1:
        return 0.0

    mean_demand = float(np.mean(non_zero))

    if mean_demand == 0:
        return 0.0

    std_demand = float(np.std(non_zero, ddof=1))

    return float((std_demand / mean_demand) ** 2)


def classify_demand(
    demand: Iterable[float],
    *,
    adi_threshold: float = ADI_THRESHOLD,
    cv2_threshold: float = CV2_THRESHOLD,
) -> str:
    """
    Classify demand into Smooth, Intermittent, Erratic, or Lumpy.
    """
    if adi_threshold <= 0:
        raise ValueError("ADI threshold must be positive.")

    if cv2_threshold < 0:
        raise ValueError("CV² threshold cannot be negative.")

    adi = calculate_adi(demand)
    cv2 = calculate_cv2(demand)

    adi_high = adi > adi_threshold
    cv2_high = cv2 > cv2_threshold

    if not adi_high and not cv2_high:
        return "smooth"

    if adi_high and not cv2_high:
        return "intermittent"

    if not adi_high and cv2_high:
        return "erratic"

    return "lumpy"


def classify_demand_with_metrics(
    demand: Iterable[float],
    *,
    adi_threshold: float = ADI_THRESHOLD,
    cv2_threshold: float = CV2_THRESHOLD,
) -> dict:
    """
    Return classification together with ADI and CV² metrics.
    """
    adi = calculate_adi(demand)
    cv2 = calculate_cv2(demand)

    classification = classify_demand(
        demand,
        adi_threshold=adi_threshold,
        cv2_threshold=cv2_threshold,
    )

    return {
        "adi": adi,
        "cv2": cv2,
        "classification": classification,
    }
def classify_sku_demand(df):
    """
    Calculate ADI, CV², and demand classification for every SKU.

    Expected columns:
        sku_id
        quantity_sold
    """
    required_columns = {"sku_id", "quantity_sold"}

    missing = required_columns - set(df.columns)
    if missing:
        raise ValueError(
            f"Missing required columns: {sorted(missing)}"
        )

    results = []

    for sku_id, group in df.groupby("sku_id", sort=True):
        demand = group["quantity_sold"].astype(float).tolist()

        metrics = classify_demand_with_metrics(demand)

        results.append(
            {
                "sku_id": sku_id,
                "adi": metrics["adi"],
                "cv2": metrics["cv2"],
                "classification": metrics["classification"],
            }
        )

    return results
def croston_forecast(
    demand: Iterable[float],
    horizon: int,
    alpha: float = 0.1,
) -> list[float]:
    """
    Forecast intermittent demand using Croston's method.

    Demand size and demand interval are smoothed separately.
    """

    values = np.asarray(list(demand), dtype=float)

    if values.size == 0:
        raise ValueError("Demand history cannot be empty.")

    if np.any(~np.isfinite(values)):
        raise ValueError("Demand history contains non-finite values.")

    if np.any(values < 0):
        raise ValueError("Demand values cannot be negative.")

    if horizon <= 0:
        raise ValueError("Horizon must be positive.")

    if not 0 < alpha <= 1:
        raise ValueError("Alpha must be between 0 and 1.")

    non_zero_indices = np.flatnonzero(values > 0)

    # No historical demand.
    if len(non_zero_indices) == 0:
        return [0.0] * horizon

    # First non-zero demand.
    first_index = non_zero_indices[0]

    demand_estimate = values[first_index]

    # Initial interval is measured from the beginning
    # of the series to the first demand occurrence.
    interval_estimate = float(first_index + 1)

    previous_demand_index = first_index

    for index in non_zero_indices[1:]:
        current_demand = values[index]

        interval = index - previous_demand_index

        demand_estimate = (
            alpha * current_demand
            + (1 - alpha) * demand_estimate
        )

        interval_estimate = (
            alpha * interval
            + (1 - alpha) * interval_estimate
        )

        previous_demand_index = index

    forecast = demand_estimate / interval_estimate

    return [float(forecast)] * horizon
def mase(
    actual: Iterable[float],
    forecast: Iterable[float],
) -> float:
    """Calculate Mean Absolute Scaled Error."""
    actual_values = np.asarray(list(actual), dtype=float)
    forecast_values = np.asarray(list(forecast), dtype=float)

    if actual_values.size == 0:
        raise ValueError("Actual values cannot be empty.")

    if actual_values.size != forecast_values.size:
        raise ValueError(
            "Actual and forecast lengths must match."
        )

    if np.any(~np.isfinite(actual_values)):
        raise ValueError(
            "Actual values contain non-finite values."
        )

    if np.any(~np.isfinite(forecast_values)):
        raise ValueError(
            "Forecast values contain non-finite values."
        )

    if np.any(actual_values < 0):
        raise ValueError(
            "Actual demand cannot be negative."
        )

    if np.any(forecast_values < 0):
        raise ValueError(
            "Forecast values cannot be negative."
        )

    if actual_values.size < 2:
        raise ValueError(
            "At least two actual observations are required "
            "to calculate MASE."
        )

    naive_errors = np.abs(
        actual_values[1:] - actual_values[:-1]
    )

    scale = float(np.mean(naive_errors))

    if scale == 0:
        raise ValueError(
            "MASE is undefined when the naive scale is zero."
        )

    model_error = float(
        np.mean(np.abs(actual_values - forecast_values))
    )

    return model_error / scale
def split_sku_history(
    sku_df,
    test_periods: int = 3,
):
    """Split one SKU history chronologically into train and test."""
    if test_periods <= 0:
        raise ValueError("test_periods must be positive.")

    if sku_df.empty:
        raise ValueError("SKU history cannot be empty.")

    required_columns = {"date", "sku_id", "quantity_sold"}
    missing = required_columns - set(sku_df.columns)

    if missing:
        raise ValueError(
            f"Missing required columns: {sorted(missing)}"
        )

    data = sku_df.copy()
    data["date"] = pd.to_datetime(data["date"])
    data = data.sort_values("date").reset_index(drop=True)

    if len(data) <= test_periods:
        raise ValueError(
            "Not enough observations for the requested test period."
        )

    train = data.iloc[:-test_periods].copy()
    test = data.iloc[-test_periods:].copy()

    return train, test
def evaluate_croston_vs_naive(
    train_demand: Iterable[float],
    test_demand: Iterable[float],
    *,
    horizon: int | None = None,
    alpha: float = 0.1,
) -> dict:
    """Compare Croston and naive forecasts using MASE."""

    train_values = list(train_demand)
    test_values = list(test_demand)

    if not train_values:
        raise ValueError("Training demand cannot be empty.")

    if not test_values:
        raise ValueError("Test demand cannot be empty.")

    if horizon is None:
        horizon = len(test_values)

    if horizon != len(test_values):
        raise ValueError(
            "Horizon must match the test demand length."
        )

    croston_forecast_values = croston_forecast(
        train_values,
        horizon=horizon,
        alpha=alpha,
    )

    naive_forecast_values = [
        float(train_values[-1])
    ] * horizon

    croston_mase = mase(
        test_values,
        croston_forecast_values,
    )

    naive_mase = mase(
        test_values,
        naive_forecast_values,
    )

    return {
        "croston_mase": croston_mase,
        "naive_mase": naive_mase,
        "croston_forecast": croston_forecast_values,
        "naive_forecast": naive_forecast_values,
    }
def evaluate_intermittent_skus(
    df: pd.DataFrame,
    test_periods: int = 3,
    alpha: float = 0.1,
) -> list[dict]:
    """Evaluate Croston and naive forecasts for intermittent-demand SKUs."""

    classification_results = classify_sku_demand(df)

    intermittent_skus = {
        result["sku_id"]
        for result in classification_results
        if result["classification"] in {"intermittent", "lumpy"}
    }

    evaluation_results = []

    for sku_id in sorted(intermittent_skus):
        sku_df = df[df["sku_id"] == sku_id].copy()

        train, test = split_sku_history(
            sku_df,
            test_periods=test_periods,
        )

        comparison = evaluate_croston_vs_naive(
            train["quantity_sold"].tolist(),
            test["quantity_sold"].tolist(),
            alpha=alpha,
        )

        classification = next(
            result
            for result in classification_results
            if result["sku_id"] == sku_id
        )

        evaluation_results.append(
            {
                "sku_id": sku_id,
                "classification": classification["classification"],
                "adi": classification["adi"],
                "cv2": classification["cv2"],
                "croston_mase": comparison["croston_mase"],
                "naive_mase": comparison["naive_mase"],
            }
        )

    return evaluation_results
def route_intermittent_skus(
    evaluation_results: list[dict],
) -> list[dict]:
    """Select the lowest-MASE model for each intermittent SKU."""

    routed_results = []

    for result in evaluation_results:
        croston_mase = result["croston_mase"]
        naive_mase = result["naive_mase"]

        if croston_mase <= naive_mase:
            selected_model = "croston"
        else:
            selected_model = "naive"

        routed_results.append(
            {
                **result,
                "selected_model": selected_model,
            }
        )

    return routed_results
def run_intermittent_demand_pipeline(
    df: pd.DataFrame,
    test_periods: int = 3,
    alpha: float = 0.1,
) -> list[dict]:
    """Run the complete intermittent-demand classification and routing pipeline."""

    evaluation_results = evaluate_intermittent_skus(
        df,
        test_periods=test_periods,
        alpha=alpha,
    )

    return route_intermittent_skus(evaluation_results)
if __name__ == "__main__":
    from pathlib import Path

    data_path = (
        Path(__file__).resolve().parent.parent
        / "data"
        / "intermittent_demand_sample.csv"
    )

    df = pd.read_csv(data_path)

    results = run_intermittent_demand_pipeline(
        df,
        test_periods=3,
    )

    print()
    print("=== M2 INTERMITTENT DEMAND EVALUATION ===")
    print()

    columns = [
        "sku_id",
        "classification",
        "adi",
        "cv2",
        "croston_mase",
        "naive_mase",
        "selected_model",
    ]

    print(
        pd.DataFrame(results)[columns].to_string(
            index=False
        )
    )

    print()
    print("=== ROUTING ===")

    for result in results:
        print(
            f'{result["sku_id"]} -> '
            f'{result["classification"]} -> '
            f'{result["selected_model"]}'
        )