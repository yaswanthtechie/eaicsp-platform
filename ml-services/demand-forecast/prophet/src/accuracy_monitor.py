import pandas as pd
import numpy as np


def monitor_forecast_accuracy(
    monitoring_df,
    window=3,
    threshold=10.0
):
    """
    Monitor forecast accuracy using actual vs predicted values.

    Parameters
    ----------
    monitoring_df : pd.DataFrame
        Must contain:
        date
        actual
        predicted

    window : int
        Rolling window size.

    threshold : float
        Rolling MAPE threshold percentage.

    Returns
    -------
    dict
        Monitoring metrics and alert status.
    """

    df = monitoring_df.copy()


    # ===============================
    # Validate Required Columns
    # ===============================

    required_columns = [

        "date",

        "actual",

        "predicted"

    ]


    for column in required_columns:

        if column not in df.columns:

            raise ValueError(
                f"Missing required column: {column}"
            )


    # ===============================
    # Prepare Data
    # ===============================

    df["date"] = pd.to_datetime(
        df["date"]
    )


    df = df.sort_values(
        "date"
    ).reset_index(
        drop=True
    )


    # ===============================
    # Calculate Absolute Percentage Error
    # ===============================

    df["absolute_percentage_error"] = (

        np.abs(

            (
                df["actual"]
                -
                df["predicted"]
            )

            /

            df["actual"]

        )

        * 100

    )


    # ===============================
    # Overall MAPE
    # ===============================

    overall_mape = (

        df[
            "absolute_percentage_error"
        ].mean()

    )


    # ===============================
    # Rolling MAPE
    # ===============================

    df["rolling_mape"] = (

        df[
            "absolute_percentage_error"
        ]

        .rolling(
            window=window
        )

        .mean()

    )


    # ===============================
    # Latest Rolling MAPE
    # ===============================

    latest_rolling_mape = (

        df[
            "rolling_mape"
        ]

        .dropna()

        .iloc[-1]

    )


    # ===============================
    # Alert Check
    # ===============================

    if latest_rolling_mape > threshold:

        alert_status = "WARNING"


        alert_message = (

            "WARNING: Forecast accuracy "
            "degradation detected."

        )

    else:

        alert_status = "HEALTHY"


        alert_message = (

            "HEALTHY: Forecast accuracy "
            "is within the acceptable threshold."

        )


    # ===============================
    # Return Results
    # ===============================

    return {

        "overall_mape":
            float(overall_mape),

        "latest_rolling_mape":
            float(latest_rolling_mape),

        "threshold":
            threshold,

        "alert_status":
            alert_status,

        "alert_message":
            alert_message,

        "monitoring_data":
            df

    }