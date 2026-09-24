import pandas as pd

from src.scenario_forecasting import create_promotion_scenario


def test_scenario_activates_selected_non_promotion_month():
    future_df = pd.DataFrame({
        "ds": pd.to_datetime([
            "2025-01-01",
            "2025-02-01",
            "2025-03-01",
        ]),
        "promotion": [0, 0, 1],
    })

    result = create_promotion_scenario(
        future_df,
        promotion_increase=0.20,
        scenario_month=1,
    )

    # January was not a baseline promotion month,
    # but it should become a promotion in the what-if scenario.
    assert result.loc[0, "promotion"] == 1.20

    # February remains unchanged.
    assert result.loc[1, "promotion"] == 0

    # March baseline promotion remains unchanged.
    assert result.loc[2, "promotion"] == 1