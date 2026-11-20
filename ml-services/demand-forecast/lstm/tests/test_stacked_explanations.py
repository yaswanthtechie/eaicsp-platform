import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

from src.stacked_ensemble import BASE_COLUMNS, evaluate_test_predictions


def test_contributions_add_up_to_stacked_prediction():
    rng = np.random.default_rng(0)
    frame = pd.DataFrame(
        rng.uniform(10, 50, size=(20, 3)),
        columns=BASE_COLUMNS,
    )
    frame["Actual"] = frame.mean(axis=1) + rng.normal(0, 1, 20)
    meta = Ridge(alpha=1.0).fit(frame[BASE_COLUMNS], frame["Actual"])

    result, _ = evaluate_test_predictions(frame, meta)

    total = result[
        [f"{name}_contribution" for name in BASE_COLUMNS]
    ].sum(axis=1)
    np.testing.assert_allclose(
        total + result["intercept"],
        result["StackedRidge"],
    )
    assert set(result["top_contributor"]) <= set(BASE_COLUMNS)
