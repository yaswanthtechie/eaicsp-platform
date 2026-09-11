import pandas as pd


def create_promotion_scenario(
    future_df,
    promotion_increase=0.20,
    scenario_month=None
):
    """
    Create a what-if promotion scenario.

    Parameters
    ----------
    future_df : pd.DataFrame
        Future dataframe containing external regressors.

    promotion_increase : float
        Promotion increase percentage.
        Example:
        0.20 = 20% increase

    scenario_month : int
        Month where promotion scenario is applied.
        Example:
        12 = December

    Returns
    -------
    pd.DataFrame
        Scenario dataframe.
    """

    scenario_df = future_df.copy()

    if "promotion" not in scenario_df.columns:

        raise ValueError(
            "Promotion column is required for scenario forecasting."
        )

    if scenario_month is not None:

        mask = (
            scenario_df["ds"]
            .dt.month
            ==
            scenario_month
        )

        scenario_df.loc[
            mask,
            "promotion"
        ] = (
            scenario_df.loc[
                mask,
                "promotion"
            ]
            *
            (1 + promotion_increase)
        )

    else:

        scenario_df["promotion"] = (
            scenario_df["promotion"].astype(float)
            *
            (1 + promotion_increase)
        )

    return scenario_df


def compare_scenarios(
    baseline_forecast,
    scenario_forecast
):
    """
    Compare baseline and scenario forecasts.
    """

    comparison = pd.DataFrame({

        "date":
            baseline_forecast["ds"],

        "baseline_forecast":
            baseline_forecast["yhat"],

        "scenario_forecast":
            scenario_forecast["yhat"]

    })


    comparison["forecast_difference"] = (

        comparison["scenario_forecast"]

        -

        comparison["baseline_forecast"]

    )


    comparison["percentage_change"] = (

        comparison["forecast_difference"]

        /

        comparison["baseline_forecast"]

        * 100

    )


    return comparison