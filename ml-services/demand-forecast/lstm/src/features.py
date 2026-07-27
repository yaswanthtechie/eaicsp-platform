import numpy as np


def create_sequences(series, lookback=30, horizon=7):
    series = np.asarray(series)
    
    # Ensure 2D shape (N, 1) if a 1D series is passed
    if series.ndim == 1:
        series = series.reshape(-1, 1)

    X, y = [], []
    num_samples = len(series) - lookback - horizon + 1

    if num_samples <= 0:
        raise ValueError(
            f"Series length ({len(series)}) is too short for lookback={lookback} "
            f"and horizon={horizon}."
        )

    for i in range(num_samples):
        X.append(series[i : i + lookback])
        y.append(series[i + lookback : i + lookback + horizon])

    return np.array(X), np.array(y)


if __name__ == "__main__":
    # Sanity check with synthetic 100-day series
    dummy_series = np.arange(100)
    X_test, y_test = create_sequences(dummy_series, lookback=30, horizon=7)

    print("features.py logic verified!")
    print(f"X shape: {X_test.shape} (Expected: [64, 30, 1])")
    print(f"y shape: {y_test.shape} (Expected: [64, 7, 1])")