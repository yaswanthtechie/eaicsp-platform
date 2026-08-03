import os
import matplotlib.pyplot as plt


def save_forecast_plot(test_df, forecast_df):
    """
    Save Prophet forecast plot.
    """

    # Create output directory
    os.makedirs("output", exist_ok=True)

    plt.figure(figsize=(12, 6))

    # -----------------------------------
    # Actual Sales
    # -----------------------------------
    plt.plot(
        test_df["ds"],
        test_df["y"],
        label="Actual Sales",
        linewidth=2,
        color="blue"
    )

    # -----------------------------------
    # Prophet Predictions
    # -----------------------------------
    plt.plot(
        forecast_df["ds"],
        forecast_df["yhat"],
        label="Prophet Forecast",
        linewidth=2,
        color="red"
    )

    # -----------------------------------
    # Confidence Interval
    # -----------------------------------
    plt.fill_between(
        forecast_df["ds"],
        forecast_df["yhat_lower"],
        forecast_df["yhat_upper"],
        alpha=0.25,
        color="red",
        label="Prediction Interval"
    )

    # -----------------------------------
    # Labels
    # -----------------------------------
    plt.title("Sales Forecast")
    plt.xlabel("Date")
    plt.ylabel("Sales")

    plt.legend()

    plt.grid(True)

    plt.tight_layout()

    # -----------------------------------
    # Save Figure
    # -----------------------------------
    plt.savefig("output/forecast.png")

    plt.close()

    print(" Forecast plot saved: output/forecast.png")