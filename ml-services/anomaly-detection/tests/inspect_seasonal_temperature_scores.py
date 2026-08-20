import pandas as pd

from src.model_loader import (
    feature_names,
    get_models,
)


DATASET = "output/test_seasonal_normal.csv"


def main():

    print("=" * 90)
    print("SEASONAL TEMPERATURE VS MODEL SCORE")
    print("=" * 90)

    df = pd.read_csv(DATASET)

    models = get_models()

    temperature_bins = [
        (21, 22),
        (22, 23),
        (23, 24),
        (24, 25),
        (25, 26),
        (26, 27),
        (27, 28),
        (28, 29),
        (29, 30),
        (30, 31),
        (31, 32),
    ]

    print()

    for model_name, model in models.items():

        print()
        print("=" * 90)
        print(model_name.upper())
        print("=" * 90)

        X = df[
            feature_names
        ].to_numpy()

        scores = -model.score(X)

        temp = df["temperature"]

        print(
            f"{'Temperature':<18}"
            f"{'Count':<10}"
            f"{'Mean Score':<18}"
            f"{'P95 Score':<18}"
            f"{'Max Score':<18}"
        )

        print("-" * 90)

        for lower, upper in temperature_bins:

            mask = (
                (temp >= lower)
                & (temp < upper)
            )

            bin_scores = scores[mask]

            if len(bin_scores) == 0:
                continue

            series = pd.Series(
                bin_scores
            )

            print(
                f"{lower:02d}-{upper:02d}°C"
                f"{'':<10}"
                f"{len(bin_scores):<10}"
                f"{series.mean():<18.6f}"
                f"{series.quantile(0.95):<18.6f}"
                f"{series.max():<18.6f}"
            )

    print()
    print("=" * 90)
    print("TEST COMPLETED")
    print("=" * 90)


if __name__ == "__main__":
    main()