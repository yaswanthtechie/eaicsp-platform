import pandas as pd
import pytest

from src.interaction_features import add_interaction_features


def test_day_of_week_holiday_interaction():
    df = pd.DataFrame({
        "day_of_week": [0, 1, 5],
        "is_holiday": [0, 1, 1]
    })

    result = add_interaction_features(df)

    assert result["day_of_week_x_is_holiday"].tolist() == [0, 1, 5]


def test_interaction_features_do_not_mutate_input():
    df = pd.DataFrame({
        "day_of_week": [0, 1],
        "is_holiday": [0, 1]
    })

    add_interaction_features(df)

    assert "day_of_week_x_is_holiday" not in df.columns


def test_interaction_features_reject_missing_feature():
    df = pd.DataFrame({
        "day_of_week": [0, 1]
    })

    with pytest.raises(ValueError, match="is_holiday"):
        add_interaction_features(df)