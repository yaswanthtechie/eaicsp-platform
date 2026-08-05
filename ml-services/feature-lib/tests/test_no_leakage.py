import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))

import pandas as pd

from build_features import build_all_features


def test_no_data_leakage():

    df = pd.DataFrame(
        {
            "date": pd.date_range(
                start="2025-01-01",
                periods=10
            ),
            "sales": [
                10,20,30,40,50,
                60,70,80,90,100
            ]
        }
    )

    result = build_all_features(
        df,
        date_col="date",
        target_col="sales"
    )

    # Lag check
    assert result.loc[7, "sales_lag_7"] == 10

    # Rolling Mean Check
    expected_mean = (10+20+30+40+50+60+70)/7

    assert result.loc[6, "sales_roll_mean_7"] == expected_mean
if __name__ == "__main__":
    test_no_data_leakage()
    print("✅ No data leakage test passed!")    