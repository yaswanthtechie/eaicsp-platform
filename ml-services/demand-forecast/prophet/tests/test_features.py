import sys
import os

sys.path.append(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    )
)

import pandas as pd

from src.inference import create_features



def test_create_features_no_target_leakage():

    df = pd.DataFrame({

        "ds": pd.date_range(
            "2024-01-01",
            periods=60,
            freq="D"
        ),

        "y": range(1, 61)

    })


    result = create_features(df)


    # Check rows are generated
    assert len(result) > 0


    # Target column should exist
    assert "y" in result.columns


    # Rolling features should not directly equal target
    assert not result[
        "rolling_mean_7"
    ].equals(
        result["y"]
    )