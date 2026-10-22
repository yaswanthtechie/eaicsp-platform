import json
import joblib
import mlflow
import numpy as np
from pathlib import Path
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
    train_comparison_model,
    check_production_calibration,
)
from src.evaluate import compare_models, evaluate_model
from src.shap_explainer import explain_predictions
from src.paths import (
    ensure_directories,
    R14_MODEL_PATH,
    R14_CALIBRATION_MODEL_PATH,
)

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
    # 10. Train Round 14 model as a candidate
    #
    # train_comparison_model() keeps the candidate model
    # in memory and does not write production artifacts.
    # ---------------------------------------------------------
    model, calibration = train_comparison_model(
        X_train,
        y_train,
        use_eta_history_features=True,
    )

    # Safety check before any promotion
    check_production_calibration(
        calibration
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
    # 13. Production calibration safety gate
    #
    # Refuse to continue if the prediction interval was
    # calibrated on too few rows, which could indicate
    # accidental training on test fixture data.
    # ---------------------------------------------------------
    check_production_calibration(
        calibration
    )

    # ---------------------------------------------------------
    # 14. Evaluate Round 14 model against naive baseline
    # ---------------------------------------------------------
    results = evaluate_model(
        model,
        split.train,
        split.test,
        use_eta_history_features=True,
    )

    # ---------------------------------------------------------
    # 15. Generate Round 14 predictions
    # ---------------------------------------------------------
    r14_predictions = model.predict(
        split.test[
            TRAINING_MODEL_FEATURES
        ]
    )

    # ---------------------------------------------------------
    # 15b. Generate SHAP explanations for Round 14 predictions
    # ---------------------------------------------------------
    r14_test_features = split.test[
        TRAINING_MODEL_FEATURES
    ].copy()

    shap_explanations = explain_predictions(
        model=model,
        features=r14_test_features,
        predictions=r14_predictions,
        top_n=5,
        sample_size=1000,
        order_ids=split.test["order_id"],
    )

    print("\nSHAP explanations generated:")
    print(
        f"  Predictions explained: "
        f"{len(shap_explanations)}"
    )

    if shap_explanations:
        print(
            "  Top contributing features for first prediction:"
        )

        for contribution in shap_explanations[0]["top_features"]:
            print(
                f"    {contribution['feature']}: "
                f"{contribution['shap_value']:+.4f}"
            )

    actual = split.test[
        TARGET_COLUMN
    ].to_numpy()

    # ---------------------------------------------------------
    # 15c. Compare inherited and Round 14 models
    #      using the shared comparison helper.
    # ---------------------------------------------------------
    comparison = compare_models(
        y_true=actual,
        inherited_predictions=inherited_predictions,
        inherited_calibration=inherited_calibration,
        r14_predictions=r14_predictions,
        r14_calibration=calibration,
    )

    inherited_mae = comparison[
        "inherited"
    ]["mae"]

    inherited_interval_coverage = comparison[
        "inherited"
    ]["actual_coverage"]

    inherited_interval_width = comparison[
        "inherited"
    ]["mean_interval_width"]

    r14_interval_coverage = comparison[
        "r14"
    ]["actual_coverage"]

    r14_interval_width = comparison[
        "r14"
    ]["mean_interval_width"]

    results[
        "interval_coverage"
    ] = r14_interval_coverage

    # ---------------------------------------------------------
    # 15d. Add inherited comparison coverage to MLflow results
    # ---------------------------------------------------------
    # The inherited MLflow run has already been logged above.
    # The comparison metrics are retained here for the final
    # side-by-side reporting.
    # ---------------------------------------------------------

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
    # 16. Model comparison
    # ---------------------------------------------------------
    print("\nModel Comparison")
    print("================")

    print(
        f"{'Metric':<25}"
        f"{'Inherited':>15}"
        f"{'Round 14':>15}"
    )

    print(
        f"{'MAE (days)':<25}"
        f"{inherited_mae:>15.4f}"
        f"{results['mae']:>15.4f}"
    )

    print(
        f"{'Nominal coverage':<25}"
        f"{comparison['inherited']['nominal_coverage'] * 100:>14.2f}%"
        f"{comparison['r14']['nominal_coverage'] * 100:>14.2f}%"
    )

    print(
        f"{'Actual coverage':<25}"
        f"{inherited_interval_coverage * 100:>14.2f}%"
        f"{r14_interval_coverage * 100:>14.2f}%"
    )

    print(
        f"{'Mean interval width':<25}"
        f"{inherited_interval_width:>15.4f}"
        f"{r14_interval_width:>15.4f}"
    )
        # Save the Round 14 comparison metrics as a committed artifact.
    metrics_path = Path("results/round14_metrics.json")
    metrics_path.parent.mkdir(parents=True, exist_ok=True)

    round14_metrics = {
        "evaluation": {
            "type": "chronological_test_period",
            "nominal_coverage": comparison["r14"]["nominal_coverage"],
        },
        "inherited": comparison["inherited"],
        "round14": comparison["r14"],
    }

    metrics_path.write_text(
        json.dumps(round14_metrics, indent=2),
        encoding="utf-8",
    )

    print(f"\nComparison metrics saved to: {metrics_path}")
    # ---------------------------------------------------------
    # 17. Log Round 14 model as a separate MLflow run
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
    # 18. Promote Round 14 candidate artifacts
    #
    # Only save the candidate artifacts after:
    # - validation
    # - comparison
    # - SHAP generation
    # - MLflow logging
    # have completed successfully.
    # ---------------------------------------------------------
    joblib.dump(
        model,
        R14_MODEL_PATH,
    )

    joblib.dump(
        calibration,
        R14_CALIBRATION_MODEL_PATH,
    )

    print("\nRound 14 candidate artifacts promoted:")
    print(f"  Model: {R14_MODEL_PATH}")
    print(
        f"  Calibration: {R14_CALIBRATION_MODEL_PATH}"
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