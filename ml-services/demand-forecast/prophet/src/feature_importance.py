import os
import pickle
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt

from src.data import load_sales_data
from src.train_xgboost import FEATURES, train_xgboost


PROJECT_ROOT = Path(__file__).resolve().parent.parent

MODEL_PATH = PROJECT_ROOT / "models" / "xgb_model.pkl"
OUTPUT_DIR = PROJECT_ROOT / "output"


def load_model(df):
    if not MODEL_PATH.exists():
        print(
            "\nXGBoost model not found."
            "\nTraining XGBoost model..."
        )

        train_xgboost(df)

    with open(MODEL_PATH, "rb") as f:
        model_info = pickle.load(f)

    return model_info["model"]


def extract_feature_importance(model):
    importance = model.feature_importances_

    result = pd.DataFrame({
        "feature": FEATURES,
        "importance": importance
    })

    result = result.sort_values(
        "importance",
        ascending=False
    ).reset_index(drop=True)

    return result


def sanity_check(result):
    print("\n========== Feature Importance Sanity Check ==========")

    print("\nFeature importance ranking:")
    print(result.to_string(index=False))

    top_feature = result.iloc[0]

    print(
        f"\nTop feature: {top_feature['feature']}"
    )

    print(
        f"Top importance: "
        f"{top_feature['importance']:.4f}"
    )

    total_importance = result["importance"].sum()

    top_share = (
        top_feature["importance"]
        / total_importance
    )

    print(
        f"Top feature share: "
        f"{top_share:.2%}"
    )

    if top_share > 0.80:
        print(
            "WARNING: One feature dominates "
            "more than 80% of total importance."
        )
    else:
        print(
            "Sanity check passed: "
            "no single feature dominates the model."
        )

    temporal_features = [
        "lag_1",
        "lag_7",
        "lag_30",
        "rolling_mean_7",
        "rolling_mean_30",
        "rolling_std_7",
        "day_of_week",
        "month",
        "quarter",
        "year"
    ]

    temporal_importance = result[
        result["feature"].isin(temporal_features)
    ]["importance"].sum()

    print(
        f"\nTemporal feature importance: "
        f"{temporal_importance:.4f}"
    )

    if temporal_importance > 0:
        print(
            "Temporal features have measurable "
            "influence on the forecast."
        )
    else:
        print(
            "WARNING: Temporal features have "
            "zero total importance."
        )


def save_results(result):

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    output_file = OUTPUT_DIR / "feature_importance.csv"

    result.to_csv(
        output_file,
        index=False
    )

    print(
        f"\nFeature importance saved: "
        f"{output_file}"
    )


def create_plot(result):

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    plt.figure(figsize=(10, 6))

    plt.barh(
        result["feature"],
        result["importance"]
    )

    plt.xlabel("Importance")
    plt.ylabel("Feature")
    plt.title("XGBoost Feature Importance")

    plt.gca().invert_yaxis()

    plt.tight_layout()

    output_file = OUTPUT_DIR / "feature_importance.png"

    plt.savefig(
        output_file,
        dpi=150
    )

    plt.close()

    print(
        f"Feature importance plot saved: "
        f"{output_file}"
    )


def main():

    print(
        "========== XGBoost Feature Importance =========="
    )

    # train_xgboost() / create_features() expect the Prophet-style
    # frame (ds / y), the same shape main.py builds.
    df = load_sales_data().rename(
        columns={
            "date": "ds",
            "quantity_sold": "y",
        }
    )

    model = load_model(df)

    result = extract_feature_importance(
        model
    )

    sanity_check(result)

    save_results(result)

    create_plot(result)


if __name__ == "__main__":
    main()