from .metrics import mape, rmse


def naive_forecast(series) -> list:
    """Tomorrow = today. The simplest possible forecast."""
    series = list(series)
    return [series[0]] + series[:-1]


def compare_to_baseline(model_predictions, naive_predictions, actual) -> dict:
    """Returns which one wins, and by how much, on MAPE and RMSE."""
    model_mape, naive_mape = mape(actual, model_predictions), mape(actual, naive_predictions)
    model_rmse, naive_rmse = rmse(actual, model_predictions), rmse(actual, naive_predictions)
    return {
        "mape_winner": "model" if model_mape < naive_mape else "naive",
        "mape_diff": abs(model_mape - naive_mape),
        "rmse_winner": "model" if model_rmse < naive_rmse else "naive",
        "rmse_diff": abs(model_rmse - naive_rmse),
    }