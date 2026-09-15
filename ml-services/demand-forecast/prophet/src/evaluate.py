from sklearn.metrics import mean_squared_error
import numpy as np


def mape(actual, predicted):
    actual = np.array(actual)
    predicted = np.array(predicted)
    return np.mean(np.abs((actual - predicted) / actual)) * 100


def evaluate(actual, predicted):
    """
    Calculate MAPE and RMSE.
    """

    rmse = np.sqrt(mean_squared_error(actual, predicted))
    mape_score = mape(actual, predicted)

    print(f"MAPE : {mape_score:.2f}%")
    print(f"RMSE : {rmse:.2f}")

    return {
        "MAPE": float(round(mape_score, 2)),
        "RMSE": float(round(rmse, 2))
    }