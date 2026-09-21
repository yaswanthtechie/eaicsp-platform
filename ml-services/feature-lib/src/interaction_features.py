import pandas as pd


def add_interaction_features(
    df: pd.DataFrame,
    feature_pairs=None
):
    """
    Add interaction features by multiplying pairs of existing features.
    """

    data = df.copy()

    if feature_pairs is None:
        feature_pairs = [
            ("day_of_week", "is_holiday")
        ]

    for feature_1, feature_2 in feature_pairs:
        if feature_1 not in data.columns:
            raise ValueError(
                f"Feature '{feature_1}' not found in dataframe."
            )

        if feature_2 not in data.columns:
            raise ValueError(
                f"Feature '{feature_2}' not found in dataframe."
            )

        interaction_name = f"{feature_1}_x_{feature_2}"

        data[interaction_name] = (
            data[feature_1] * data[feature_2]
        )

    return data