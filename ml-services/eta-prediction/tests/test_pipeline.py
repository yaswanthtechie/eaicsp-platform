import numpy as np
import pandas as pd

from src.pipeline import (
    H2_NUMERIC_FEATURES,
    create_h2_pipeline,
)


def test_h2_pipeline_uses_expected_features():
    assert H2_NUMERIC_FEATURES == [
        "purchase_year",
        "purchase_month",
        "purchase_day_of_week",
        "purchase_hour",
        "distance_km",
    ]


def test_h2_pipeline_can_fit_and_predict():
    X = pd.DataFrame(
        {
            "purchase_year": [2018, 2018, 2018, 2018],
            "purchase_month": [1, 1, 2, 2],
            "purchase_day_of_week": [1, 2, 3, 4],
            "purchase_hour": [8, 10, 12, 14],
            "distance_km": [10.0, 50.0, 100.0, 200.0],
        }
    )

    y = pd.Series(
        [2.0, 4.0, 7.0, 10.0],
        name="delivery_days",
    )

    pipeline = create_h2_pipeline()

    pipeline.fit(X, y)

    predictions = pipeline.predict(X)

    assert len(predictions) == len(X)
    assert np.isfinite(predictions).all()


def test_h2_pipeline_rejects_missing_feature():
    X = pd.DataFrame(
        {
            "purchase_year": [2018, 2018],
            "purchase_month": [1, 1],
            "purchase_day_of_week": [1, 2],
            "purchase_hour": [8, 10],
        }
    )

    y = pd.Series([2.0, 4.0])

    pipeline = create_h2_pipeline()

    try:
        pipeline.fit(X, y)
    except ValueError:
        return

    raise AssertionError(
        "H2 pipeline should reject missing distance_km."
    )