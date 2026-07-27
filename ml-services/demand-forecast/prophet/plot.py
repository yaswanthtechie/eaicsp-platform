import os
import matplotlib.pyplot as plt


def save_forecast_plot(test, forecast):
    """
    Save forecast plot to the output directory.
    """

    # Create output directory if it doesn't exist
    os.makedirs("output", exist_ok=True)

    # Filter forecast for test period
    forecast_test = forecast[forecast["ds"] >= "2015-01-01"]

    plt.figure(figsize=(12, 6))

    # Actual values
    plt.plot(
        test["ds"],
        test["y"],
        label="Actual Sales",
        linewidth=2
    )

    # Predicted values
    plt.plot(
        forecast_test["ds"],
        forecast_test["yhat"],
        label="Predicted Sales",
        linewidth=2
    )

    # Confidence interval
    plt.fill_between(
        forecast_test["ds"],
        forecast_test["yhat_lower"],
        forecast_test["yhat_upper"],
        alpha=0.3,
        label="Confidence Band"
    )

    plt.title("Sales Forecast using Prophet")
    plt.xlabel("Date")
    plt.ylabel("Sales")
    plt.legend()
    plt.grid(True)

    plt.savefig("output/forecast.png")
    plt.close()

    print(" Forecast graph saved to output/forecast.png")