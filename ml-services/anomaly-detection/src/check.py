import pandas as pd

from src.model_loader import (
    feature_names,
    get_models,
)


BACKGROUND = "output/calibration_normal.csv"


def main():

    df = pd.read_csv(BACKGROUND)

    models = get_models()

    X = df[feature_names].to_numpy()

    print("=" * 60)
    print("CALIBRATION SCORE DISTRIBUTIONS")
    print("=" * 60)

    print(f"Rows: {len(df)}")
    print()

    for name, model in models.items():

        scores = -model.score(X)

        series = pd.Series(scores)

        print("=" * 60)
        print(name)
        print("=" * 60)

        print(f"min    : {series.min():.6f}")
        print(f"max    : {series.max():.6f}")
        print(f"mean   : {series.mean():.6f}")
        print(f"median : {series.median():.6f}")
        print(f"p90    : {series.quantile(0.90):.6f}")
        print(f"p95    : {series.quantile(0.95):.6f}")
        print(f"p97    : {series.quantile(0.97):.6f}")
        print(f"p98    : {series.quantile(0.98):.6f}")
        print(f"p99    : {series.quantile(0.99):.6f}")
        print(f"p995   : {series.quantile(0.995):.6f}")
        print(f"p999   : {series.quantile(0.999):.6f}")

        print()


if __name__ == "__main__":
    main()