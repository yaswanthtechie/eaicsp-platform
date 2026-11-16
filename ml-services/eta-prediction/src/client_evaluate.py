
"""Evaluation helpers for R15 client ETA predictions."""

import numpy as np
import pandas as pd


def evaluate_client_predictions(
    y_true: pd.Series,
    predictions: pd.Series,
    metadata: pd.DataFrame,
) -> dict:
    """Calculate overall and per-carrier MAE."""

    if not (len(y_true) == len(predictions) == len(metadata)):
        raise ValueError(
            "y_true, predictions, and metadata must have equal lengths."
        )

    if "carrier_name" not in metadata.columns:
        raise ValueError("metadata must contain carrier_name.")

    actual = pd.to_numeric(y_true, errors="coerce").reset_index(drop=True)
    predicted = pd.to_numeric(
        predictions, errors="coerce"
    ).reset_index(drop=True)
    carriers = metadata["carrier_name"].reset_index(drop=True)

    valid = np.isfinite(actual) & np.isfinite(predicted)

    if not valid.any():
        raise ValueError("No valid predictions available for evaluation.")

    errors = (actual[valid] - predicted[valid]).abs()
    valid_carriers = carriers[valid].fillna("Unknown")

    per_carrier_mae = errors.groupby(valid_carriers).mean().to_dict()

    return {
        "mae_days": float(errors.mean()),
        "evaluated_shipments": int(valid.sum()),
        "excluded_shipments": int((~valid).sum()),
        "per_carrier_mae": {
            str(carrier): float(mae)
            for carrier, mae in per_carrier_mae.items()
        },
    }


def evaluate_client_baseline(
    y_true: pd.Series,
    metadata: pd.DataFrame,
) -> dict:
    """Evaluate the planned delivery date as a baseline."""

    if "planned_delivery_days" not in metadata.columns:
        raise ValueError(
            "metadata must contain planned_delivery_days."
        )

    planned_days = metadata["planned_delivery_days"].reset_index(drop=True)

    return evaluate_client_predictions(
        y_true=y_true,
        predictions=planned_days,
        metadata=metadata,
    )


def compare_client_baseline_and_model(
    y_true: pd.Series,
    model_predictions: pd.Series,
    metadata: pd.DataFrame,
) -> dict:
    """Compare model and planned-date baseline on identical shipments."""

    if not (
        len(y_true) == len(model_predictions) == len(metadata)
    ):
        raise ValueError(
            "y_true, predictions, and metadata must have equal lengths."
        )

    required_columns = {"carrier_name", "planned_delivery_days"}
    missing = required_columns - set(metadata.columns)

    if missing:
        raise ValueError(
            f"Missing metadata columns: {sorted(missing)}"
        )

    actual = pd.to_numeric(
        y_true, errors="coerce"
    ).reset_index(drop=True)

    predicted = pd.to_numeric(
        model_predictions, errors="coerce"
    ).reset_index(drop=True)

    planned = pd.to_numeric(
        metadata["planned_delivery_days"], errors="coerce"
    ).reset_index(drop=True)

    # Build one common mask so both evaluations use identical shipments.
    valid = (
        np.isfinite(actual)
        & np.isfinite(predicted)
        & np.isfinite(planned)
    )

    if not valid.any():
        raise ValueError(
            "No common valid shipments for baseline and model comparison."
        )

    # Filter all three inputs using the same mask.
    actual_valid = actual[valid].reset_index(drop=True)
    predicted_valid = predicted[valid].reset_index(drop=True)
    planned_valid = planned[valid].reset_index(drop=True)
    metadata_valid = (
        metadata.reset_index(drop=True)
        .loc[valid]
        .reset_index(drop=True)
    )

    # Reuse the shared evaluation helper instead of duplicating MAE logic.
    model_result = evaluate_client_predictions(
        y_true=actual_valid,
        predictions=predicted_valid,
        metadata=metadata_valid,
    )

    baseline_result = evaluate_client_predictions(
        y_true=actual_valid,
        predictions=planned_valid,
        metadata=metadata_valid,
    )

    model_mae = model_result["mae_days"]
    baseline_mae = baseline_result["mae_days"]

    return {
        "evaluated_shipments": int(valid.sum()),
        "excluded_shipments": int((~valid).sum()),
        "baseline_mae_days": baseline_mae,
        "model_mae_days": model_mae,
        "model_beats_baseline": model_mae < baseline_mae,
        "improvement_days": baseline_mae - model_mae,
        "model_per_carrier_mae": model_result["per_carrier_mae"],
        "baseline_per_carrier_mae": baseline_result["per_carrier_mae"],
    }
