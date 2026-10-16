import json
import joblib
import mlflow
import numpy as np

from src.data import load_dataset
from src.route_insights import (
    build_route_insights,
    get_slowest_routes,
    generate_route_findings,
)
from src.features import (
    build_eta_features,
    save_eta_features,
)
from src.preprocess import (
    TARGET_COLUMN,
    MODEL_FEATURES,
    TRAINING_MODEL_FEATURES,
    preprocess_features,
)
from src.split import chronological_split
from src.train import (
    train_model,
    train_comparison_model,
    check_production_calibration,
    CALIBRATION_MODEL_PATH,
)
from src.evaluate import evaluate_model
from src.shap_explainer import explain_predictions
from src.paths import ensure_directories

from src.mlflow_tracking import (
    setup_mlflow,
    start_run,
    log_parameters,
    log_metrics,
    log_dataset_metadata,
    log_calibration_metadata,
    log_model,
)


def main():
    # ---------------------------------------------------------
    # 1. Prepare project directories
    # ---------------------------------------------------------
    ensure_directories()

    # ---------------------------------------------------------
    # 2. Configure MLflow
    # ---------------------------------------------------------
    setup_mlflow()

    # ---------------------------------------------------------
    # 3. Load raw datasets
    # ---------------------------------------------------------
    datasets = load_dataset()

    # ---------------------------------------------------------
    # 4. Generate route-level insights
    # ---------------------------------------------------------
    route_insights = build_route_insights(
        datasets,
        min_orders=10,
    )

    print("\nTop Slowest Routes")
    print("==================")

    slowest_routes = get_slowest_routes(
        route_insights,
        top_n=10,
    )

    print(
        slowest_routes.to_string(index=False)
    )

    print("\nRoute Findings")
    print("==============")

    findings = generate_route_findings(
        route_insights,
        top_n=5,
    )

    for finding in findings:
        print(f"- {finding}")

    # ---------------------------------------------------------
    # 5. Extract ETA features
    # ---------------------------------------------------------
    features = build_eta_features(
        datasets
    )

    # ---------------------------------------------------------
    # 6. Save extracted feature dataset
    # ---------------------------------------------------------
    output_path = save_eta_features(
        features
    )

    print("\nFeature dataset saved to:")
    print(f"  {output_path}")

    # ---------------------------------------------------------
    # 7. Inspect, validate and clean
    # ---------------------------------------------------------
    features = preprocess_features(
        features
    )

    # ---------------------------------------------------------
    # 8. Chronological 80/20 split
    # ---------------------------------------------------------
    split = chronological_split(
        features=features,
        orders=datasets["orders"],
        test_size=0.20,
    )

    # ---------------------------------------------------------
    # 9. Prepare training data
    # ---------------------------------------------------------
    X_train = split.train[
        TRAINING_MODEL_FEATURES
    ].copy()

    y_train = split.train[
        TARGET_COLUMN
    ].copy()

    # ---------------------------------------------------------
    # 10. Train Round 14 model
    #
    # train_model() also creates the prediction
    # interval calibration artifact.
    # ---------------------------------------------------------
    model = train_model(
        X_train,
        y_train,
        enforce_production_gate=True,
        use_eta_history_features=True,
    )

    # ---------------------------------------------------------
    # 11. Train inherited model for comparison
    # ---------------------------------------------------------
    inherited_X_train = split.train[
        MODEL_FEATURES
    ].copy()

    inherited_model, inherited_calibration = (
        train_comparison_model(
            inherited_X_train,
            y_train,
            use_eta_history_features=False,
        )
    )

    inherited_X_test = split.test[
        MODEL_FEATURES
    ].copy()

    inherited_predictions = inherited_model.predict(
        inherited_X_test
    )

    inherited_actual = split.test[
        TARGET_COLUMN
    ].to_numpy()

    inherited_mae = float(
        np.mean(
            np.abs(
                inherited_actual
                - inherited_predictions
            )
        )
    )

    inherited_interval_lower = (
        inherited_predictions
        + inherited_calibration["residual_lower"]
    )

    inherited_interval_upper = (
        inherited_predictions
        + inherited_calibration["residual_upper"]
    )

    inherited_interval_coverage = float(
        np.mean(
            (inherited_actual >= inherited_interval_lower)
            & (
                inherited_actual
                <= inherited_interval_upper
            )
        )
    )

    print("\nInherited model comparison:")
    print(
        f"MAE: {inherited_mae:.4f}"
    )
    print(
        "Interval coverage: "
        f"{inherited_interval_coverage:.4f}"
    )

    # ---------------------------------------------------------
    # 12. Log inherited model as a separate MLflow run
    # ---------------------------------------------------------
    with start_run(
        run_name="ETA - Inherited Model"
    ):

        mlflow.set_tag(
            "model_variant",
            "inherited_round_9_11",
        )

        log_parameters(
            inherited_model
        )

        inherited_results = evaluate_model(
            inherited_model,
            split.train,
            split.test,
            use_eta_history_features=False,
        )

        inherited_results[
            "interval_coverage"
        ] = inherited_interval_coverage

        log_metrics(
            inherited_results
        )

        log_dataset_metadata(
            features=features,
            train=split.train,
            test=split.test,
            split_timestamp=split.split_timestamp,
        )

        log_calibration_metadata(
            inherited_calibration
        )

        inherited_model_info = log_model(
            inherited_model
        )

        print("\nInherited MLflow model logged:")
        print(
            f"  {inherited_model_info.model_uri}"
        )

    # ---------------------------------------------------------
    # 13. Load Round 14 calibration metadata
    # ---------------------------------------------------------
    if not CALIBRATION_MODEL_PATH.exists():
        raise FileNotFoundError(
            "Prediction interval calibration artifact "
            "was not created: "
            f"{CALIBRATION_MODEL_PATH}"
        )

    calibration = joblib.load(
        CALIBRATION_MODEL_PATH
    )

    # ---------------------------------------------------------
    # 14. Production calibration safety gate
    #
    # Refuse to continue if the prediction interval was
    # calibrated on too few rows, which could indicate
    # accidental training on test fixture data.
    # ---------------------------------------------------------
    check_production_calibration(
        calibration
    )

    # ---------------------------------------------------------
    # 15. Evaluate Round 14 model against naive baseline
    # ---------------------------------------------------------
    results = evaluate_model(
        model,
        split.train,
        split.test,
        use_eta_history_features=True,
    )

    # ---------------------------------------------------------
    # 16. Calculate Round 14 interval coverage
    # ---------------------------------------------------------
    r14_predictions = model.predict(
        split.test[
            TRAINING_MODEL_FEATURES
        ]
    )
        # ---------------------------------------------------------
    # 16b. Generate SHAP explanations for Round 14 predictions
    # ---------------------------------------------------------
    r14_test_features = split.test[
        TRAINING_MODEL_FEATURES
    ].copy()

    shap_explanations = explain_predictions(
        model=model,
        features=r14_test_features,
        predictions=r14_predictions,
        top_n=5,
    )

    print("\nSHAP explanations generated:")
    print(f"  Predictions explained: {len(shap_explanations)}")

    if shap_explanations:
        print("  Top contributing features for first prediction:")
        for contribution in shap_explanations[0]["top_features"]:
            print(
                f"    {contribution['feature']}: "
                f"{contribution['shap_value']:+.4f}"
            )
    actual = split.test[
        TARGET_COLUMN
    ].to_numpy()

    r14_interval_lower = (
        r14_predictions
        + calibration["residual_lower"]
    )

    r14_interval_upper = (
        r14_predictions
        + calibration["residual_upper"]
    )

    r14_interval_coverage = float(
        np.mean(
            (actual >= r14_interval_lower)
            & (actual <= r14_interval_upper)
        )
    )

    results[
        "interval_coverage"
    ] = r14_interval_coverage

    print("\nRound 14 Model")
    print("==============")
    print(
        f"MAE: {results['mae']:.4f} days"
    )
    print(
        "Interval coverage: "
        f"{r14_interval_coverage * 100:.2f}%"
    )

    # ---------------------------------------------------------
    # 17. Model comparison
    # ---------------------------------------------------------
    print("\nModel Comparison")
    print("================")

    print(
        f"Inherited model MAE: "
        f"{inherited_mae:.4f} days"
    )

    print(
        f"Round 14 model MAE: "
        f"{results['mae']:.4f} days"
    )

    print(
        f"Inherited interval coverage: "
        f"{inherited_interval_coverage * 100:.2f}%"
    )

    print(
        f"Round 14 interval coverage: "
        f"{r14_interval_coverage * 100:.2f}%"
    )

    # ---------------------------------------------------------
    # 18. Log Round 14 model as a separate MLflow run
    # ---------------------------------------------------------
    with start_run(
        run_name="ETA - Round 14 Feature-lib Model"
    ):

        mlflow.set_tag(
            "model_variant",
            "round_14_feature_lib",
        )

        log_parameters(
            model
        )

        log_metrics(
            results
        )

        log_dataset_metadata(
            features=features,
            train=split.train,
            test=split.test,
            split_timestamp=split.split_timestamp,
        )

        log_calibration_metadata(
            calibration
        )

        model_info = log_model(
            model
        )
        mlflow.log_text(
            json.dumps(
                shap_explanations,
                indent=2,
            ),
            "r14_shap_explanations.json",
        )
        print("\nRound 14 MLflow model logged:")
        print(
            f"  {model_info.model_uri}"
        )

    # ---------------------------------------------------------
    # 19. Report prediction interval calibration
    # ---------------------------------------------------------
    print("\nPrediction Interval Calibration")
    print("================================")

    print(
        "\nMethod:"
        f" {calibration['method']}"
    )

    print(
        "\nCoverage:"
        f" {calibration['coverage'] * 100:.0f}%"
    )

    print(
        "\nCalibration rows:"
        f" {calibration['calibration_rows']}"
    )

    print(
        "\nTraining rows:"
        f" {calibration['training_rows']}"
    )

    print(
        "\nResidual lower bound:"
        f" {calibration['residual_lower']:.4f} days"
    )

    print(
        "\nResidual upper bound:"
        f" {calibration['residual_upper']:.4f} days"
    )

    # ---------------------------------------------------------
    # 20. Report chronological split
    # ---------------------------------------------------------
    print("\nChronological Split")
    print("===================")

    print(
        f"\nTotal rows : {len(features)}"
    )

    print(
        f"Train rows : {len(split.train)}"
    )

    print(
        f"Test rows  : {len(split.test)}"
    )

    print("\nTraining period:")
    print(
        f"  {split.train['order_purchase_timestamp'].min()}"
        f" → "
        f"{split.train['order_purchase_timestamp'].max()}"
    )

    print("\nTest period:")
    print(
        f"  {split.test['order_purchase_timestamp'].min()}"
        f" → "
        f"{split.test['order_purchase_timestamp'].max()}"
    )

    print("\nSplit timestamp:")
    print(
        f"  {split.split_timestamp}"
    )


if __name__ == "__main__":
    main()