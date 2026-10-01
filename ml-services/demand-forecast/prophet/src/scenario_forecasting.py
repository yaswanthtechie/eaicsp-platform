import pandas as pd


def create_promotion_scenario(
    future_df,
    promotion_increase=0.20,
    scenario_month=None
):
    """
    Create a what-if promotion scenario.

    scenario_month:
        1  = January
        2  = February
        ...
        12 = December
    """

    scenario_df = future_df.copy()

    if "promotion" not in scenario_df.columns:
        raise ValueError(
            "Promotion column is required for scenario forecasting."
        )

    scenario_df["promotion"] = (
        scenario_df["promotion"].astype(float)
    )

    if scenario_month is not None:

        if not 1 <= scenario_month <= 12:
            raise ValueError(
                "scenario_month must be between 1 and 12."
            )

        mask = (
            scenario_df["ds"].dt.month
            == scenario_month
        )

        # Activate promotion for the selected
        # what-if scenario month.
        scenario_df.loc[mask, "promotion"] = (
            1.0 + promotion_increase
        )

    else:
        scenario_df["promotion"] = (
            1.0 + promotion_increase
        )

    return scenario_df


def compare_scenarios(
    baseline_forecast,
    scenario_forecast
):
    comparison = pd.DataFrame({
        "date": baseline_forecast["ds"],
        "baseline_forecast": baseline_forecast["yhat"],
        "scenario_forecast": scenario_forecast["yhat"]
    })

    comparison["forecast_difference"] = (
        comparison["scenario_forecast"]
        - comparison["baseline_forecast"]
    )

    comparison["percentage_change"] = (
        comparison["forecast_difference"]
        / comparison["baseline_forecast"]
        * 100
    )

    return comparison