import pandas as pd
from src.build_features import build_all_features


def test_no_data_leakage():

    df = pd.DataFrame(
        {
            "date": pd.date_range(
                start="2025-01-01",
                periods=10
            ),
            "sales": [
                10, 20, 30, 40, 50,
                60, 70, 80, 90, 100
            ]
        }
    )

    result = build_all_features(
        df,
        date_col="date",
        target_col="sales"
    )

    # Lag feature check
    assert result.loc[7, "sales_lag_7"] == 10

    # Rolling mean should use only past values
    expected_mean = (10 + 20 + 30 + 40 + 50 + 60 + 70) / 7

    assert result.loc[7, "sales_roll_mean_7"] == expected_mean

    # Ensure current row is NOT included
    assert result.loc[7, "sales_roll_mean_7"] != (
        20 + 30 + 40 + 50 + 60 + 70 + 80
    ) / 7


if __name__ == "__main__":
    test_no_data_leakage()
    print("✅ No data leakage test passed!")
