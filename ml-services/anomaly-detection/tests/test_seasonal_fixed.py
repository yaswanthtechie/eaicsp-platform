import pandas as pd

from src.model_loader import (
    feature_names,
    get_models,
)


DATASET = "output/test_seasonal_normal.csv"


def main():

    print("=" * 80)
    print("FIXED MODEL BEHAVIOR ON SEASONAL NORMAL DATA")
    print("=" * 80)

    df = pd.read_csv(DATASET)

    X = df[
        feature_names
    ].to_numpy()

    models = get_models()

    print()
    print(
        f"Samples : {len(df)}"
    )

    print(
        f"Actual anomalies : "
        f"{df['is_anomaly'].sum()}"
    )

    for model_name, model in models.items():

        predictions = model.predict(X)

        anomaly_mask = (
            predictions == -1
        )

        anomaly_count = int(
            anomaly_mask.sum()
        )

        false_positive_rate = (
            anomaly_count / len(df)
        )

        scores = -model.score(X)

        print()
        print("=" * 80)
        print(model_name.upper())
        print("=" * 80)

        print(
            f"Model anomalies      : "
            f"{anomaly_count}"
        )

        print(
            f"False positive rate   : "
            f"{false_positive_rate:.4f}"
        )

        print(
            f"Anomaly percentage    : "
            f"{false_positive_rate * 100:.2f}%"
        )

        print()

        print("SCORE DISTRIBUTION")
        print("-" * 80)

        print(
            f"Minimum : {scores.min():.6f}"
        )

        print(
            f"Maximum : {scores.max():.6f}"
        )

        print(
            f"Median  : "
            f"{pd.Series(scores).median():.6f}"
        )

        print(
            f"P95     : "
            f"{pd.Series(scores).quantile(0.95):.6f}"
        )

        print(
            f"P99     : "
            f"{pd.Series(scores).quantile(0.99):.6f}"
        )

    print()
    print("=" * 80)
    print("TEST COMPLETED")
    print("=" * 80)


if __name__ == "__main__":
    main()