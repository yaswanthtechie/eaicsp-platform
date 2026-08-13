import os
import pickle
import pandas as pd
import matplotlib.pyplot as plt

from train_xgboost import FEATURES


MODEL_PATH = "models/xgb_model.pkl"
OUTPUT_DIR = "output"


def load_model():
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(
            f"XGBoost model not found: {MODEL_PATH}"
        )

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

    # Check whether one feature completely dominates
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

    # Check expected temporal features
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

    os.makedirs(
        OUTPUT_DIR,
        exist_ok=True
    )

    output_file = os.path.join(
        OUTPUT_DIR,
        "feature_importance.csv"
    )

    result.to_csv(
        output_file,
        index=False
    )

    print(
        f"\nFeature importance saved: "
        f"{output_file}"
    )


def create_plot(result):

    os.makedirs(
        OUTPUT_DIR,
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

    output_file = os.path.join(
        OUTPUT_DIR,
        "feature_importance.png"
    )

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

    model = load_model()

    result = extract_feature_importance(
        model
    )

    sanity_check(result)

    save_results(result)

    create_plot(result)


if __name__ == "__main__":
    main()