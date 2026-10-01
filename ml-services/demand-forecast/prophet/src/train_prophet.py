# train_prophet.py

import os

import pandas as pd

from prophet import Prophet
from prophet.serialize import model_to_json


# ============================================================
# External regressors used by Prophet
# ============================================================

EXTERNAL_REGRESSORS = [
    "is_holiday",
    "promotion",
    "weather_index",
]


# ============================================================
# Resolve Regressors
# ============================================================

def resolve_regressors(regressors=None):
    """
    Resolve and validate the external regressors used by Prophet.

    Parameters
    ----------
    regressors : list[str] or None
        Regressors to use.

        None:
            Use all default external regressors.

    Returns
    -------
    list[str]
        Validated copy of the selected regressors.
    """

    if regressors is None:
        return EXTERNAL_REGRESSORS.copy()

    regressors = list(regressors)

    unknown_regressors = [
        regressor
        for regressor in regressors
        if regressor not in EXTERNAL_REGRESSORS
    ]

    if unknown_regressors:
        raise ValueError(
            f"Unknown external regressors: "
            f"{unknown_regressors}. "
            f"Allowed regressors: "
            f"{EXTERNAL_REGRESSORS}"
        )

    if len(regressors) != len(set(regressors)):
        raise ValueError(
            "Duplicate external regressors are not allowed."
        )

    return regressors


# ============================================================
# Train Prophet
# ============================================================

def train_prophet(
    train_df,
    regressors=None,
    save_model=True,
):
    """
    Train Prophet model with configurable external regressors.

    Parameters
    ----------
    train_df : pd.DataFrame
        Training dataframe.

    regressors : list[str] or None
        External regressors to use.

        If None, all default regressors are used:

            - is_holiday
            - promotion
            - weather_index

    save_model : bool
        If True, save the trained model to:

            output/prophet_model.json

        Set False for experiments such as regressor ablation
        where multiple temporary models are trained.

    Returns
    -------
    Prophet
        Trained Prophet model.
    """

    print("Training Prophet model...")

    # --------------------------------------------------------
    # Resolve regressors
    # --------------------------------------------------------

    selected_regressors = resolve_regressors(
        regressors
    )

    print(
        "Selected external regressors:"
    )

    if selected_regressors:

        for regressor in selected_regressors:

            print(
                f" - {regressor}"
            )

    else:

        print(
            " - None"
        )

    # --------------------------------------------------------
    # Copy dataframe
    # --------------------------------------------------------

    df = train_df.copy()

    # --------------------------------------------------------
    # Rename columns if required
    # --------------------------------------------------------

    if "date" in df.columns:

        df = df.rename(
            columns={
                "date": "ds"
            }
        )

    if "demand" in df.columns:

        df = df.rename(
            columns={
                "demand": "y"
            }
        )

    # --------------------------------------------------------
    # Validate required columns
    # --------------------------------------------------------

    required_columns = [
        "ds",
        "y",
        *selected_regressors,
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:

        raise ValueError(
            f"Missing required columns: "
            f"{missing_columns}"
        )

    # --------------------------------------------------------
    # Validate dataframe
    # --------------------------------------------------------

    if df.empty:

        raise ValueError(
            "Training dataframe is empty."
        )

    df["ds"] = pd.to_datetime(
        df["ds"]
    )

    # --------------------------------------------------------
    # Create Prophet model
    # --------------------------------------------------------

    model = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=True,
        daily_seasonality=False,
    )

    # --------------------------------------------------------
    # Add selected external regressors
    # --------------------------------------------------------

    for regressor in selected_regressors:

        model.add_regressor(
            regressor
        )

    # --------------------------------------------------------
    # Training columns
    # --------------------------------------------------------

    training_columns = [
        "ds",
        "y",
        *selected_regressors,
    ]

    # --------------------------------------------------------
    # Train model
    # --------------------------------------------------------

    model.fit(
        df[training_columns]
    )

    # --------------------------------------------------------
    # Save model
    # --------------------------------------------------------

    if save_model:

        os.makedirs(
            "output",
            exist_ok=True,
        )

        with open(
            "output/prophet_model.json",
            "w",
        ) as file:

            file.write(
                model_to_json(model)
            )

        print(
            "Prophet model saved: "
            "output/prophet_model.json"
        )

    else:

        print(
            "Model save skipped."
        )

    print(
        "Prophet model trained successfully."
    )

    return model


# ============================================================
# Predict Prophet
# ============================================================

def predict_prophet(
    model,
    test_df,
    regressors=None,
):
    """
    Generate Prophet forecast using the selected
    external regressors.

    Parameters
    ----------
    model : Prophet
        Trained Prophet model.

    test_df : pd.DataFrame
        Test dataframe.

    regressors : list[str] or None
        External regressors used by the model.

        If None, all default external regressors are expected.

    Returns
    -------
    pd.DataFrame
        Forecast containing:

            ds
            yhat
            yhat_lower
            yhat_upper
    """

    print(
        "\n========== Running Prophet Prediction =========="
    )

    # --------------------------------------------------------
    # Resolve regressors
    # --------------------------------------------------------

    selected_regressors = resolve_regressors(
        regressors
    )

    # --------------------------------------------------------
    # Copy dataframe
    # --------------------------------------------------------

    df = test_df.copy()

    # --------------------------------------------------------
    # Validate dataframe
    # --------------------------------------------------------

    if df.empty:

        raise ValueError(
            "Test dataframe is empty."
        )

    # --------------------------------------------------------
    # Rename Date column
    # --------------------------------------------------------

    if "ds" not in df.columns:

        if "date" in df.columns:

            df = df.rename(
                columns={
                    "date": "ds"
                }
            )

        else:

            raise ValueError(
                "Missing 'ds' column."
            )

    df["ds"] = pd.to_datetime(
        df["ds"]
    )

    # --------------------------------------------------------
    # Validate selected external regressors
    # --------------------------------------------------------

    missing_regressors = [
        regressor
        for regressor in selected_regressors
        if regressor not in df.columns
    ]

    if missing_regressors:

        raise ValueError(
            "Missing external regressors: "
            f"{missing_regressors}"
        )

    # --------------------------------------------------------
    # Create future dataframe
    # --------------------------------------------------------

    future_columns = [
        "ds",
        *selected_regressors,
    ]

    future_df = df[
        future_columns
    ].copy()

    print(
        "Future dataframe:",
        future_df.shape,
    )

    print(
        "Prediction regressors:"
    )

    if selected_regressors:

        for regressor in selected_regressors:

            print(
                f" - {regressor}"
            )

    else:

        print(
            " - None"
        )

    # --------------------------------------------------------
    # Generate forecast
    # --------------------------------------------------------

    forecast = model.predict(
        future_df
    )

    # --------------------------------------------------------
    # Return required columns
    # --------------------------------------------------------

    forecast = forecast[
        [
            "ds",
            "yhat",
            "yhat_lower",
            "yhat_upper",
        ]
    ].copy()

    return forecast