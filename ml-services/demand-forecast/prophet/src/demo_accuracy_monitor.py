import pandas as pd

from src.accuracy_monitor import (
    monitor_forecast_accuracy
)


def main():

    print("=" * 60)
    print("FORECAST ACCURACY MONITORING")
    print("=" * 60)


    data = pd.DataFrame({

        "date": [
            "2026-01-01",
            "2026-02-01",
            "2026-03-01",
            "2026-04-01",
            "2026-05-01",
            "2026-06-01",
        ],

        "actual": [
            100000,
            110000,
            120000,
            130000,
            140000,
            150000,
        ],

        "predicted": [
            99000,
            112000,
            118000,
            125000,
            125000,
            120000,
        ]

    })


    result = monitor_forecast_accuracy(

        data,

        window=3,

        threshold=10.0

    )


    print("\n========== OVERALL METRICS ==========")

    print(
        "MAPE:",
        round(
            result["metrics"]["mape"],
            2
        ),
        "%"
    )

    print(
        "RMSE:",
        round(
            result["metrics"]["rmse"],
            2
        )
    )


    print("\n========== LATEST ROLLING MAPE ==========")

    print(
        result["latest_rolling_mape"]
    )


    print("\n========== ALERT STATUS ==========")

    print(
        result["alert"]["message"]
    )


    print("\n========== MONITORING DATA ==========")

    print(
        result["monitoring_data"][
            [
                "date",
                "actual",
                "predicted",
                "absolute_percentage_error",
                "rolling_mape"
            ]
        ]
    )


if __name__ == "__main__":

    main()