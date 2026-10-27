import joblib

from src.data import load_dataset
from src.route_insights import (
    build_route_insights,
    get_slowest_routes,
    generate_route_findings,
)
from src.features import (
    build_eta_features,
    save_eta_features,
    build_h2_eta_features,
    H2_MODEL_FEATURES,
)
from src.preprocess import (
    TARGET_COLUMN,
    MODEL_FEATURES,
    preprocess_features,
    preprocess_h2_features,
)
from src.split import chronological_split
from src.train import (
    train_model,
    train_h2_model,
    check_production_calibration,
    CALIBRATION_MODEL_PATH,
    H2_CALIBRATION_MODEL_PATH,
)

from src.evaluate import (
    evaluate_model,
    evaluate_h2_model,
)
from src.paths import ensure_directories

from src.mlflow_tracking import (
    setup_mlflow,
    start_run,
    log_parameters,
    log_metrics,
    log_h2_metrics,
    log_dataset_metadata,
    log_calibration_metadata,
    log_model,
    log_h2_parameters,
    log_h2_model,
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
    # 3. Start MLflow run
    # ---------------------------------------------------------
    with start_run():

        # -----------------------------------------------------
        # 4. Load raw datasets
        # -----------------------------------------------------
        datasets = load_dataset()

        # -----------------------------------------------------
        # 5. Generate route-level insights
        # -----------------------------------------------------
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

        # -----------------------------------------------------
        # 6. Extract ETA features
        # -----------------------------------------------------
        features = build_eta_features(
            datasets
        )

        # -----------------------------------------------------
        # 7. Save extracted feature dataset
        # -----------------------------------------------------
        output_path = save_eta_features(
            features
        )

        print("\nFeature dataset saved to:")
        print(f"  {output_path}")

        # -----------------------------------------------------
        # 8. Inspect, validate and clean
        # -----------------------------------------------------
        features = preprocess_features(
            features
        )

        # -----------------------------------------------------
        # 9. Chronological 80/20 split
        # -----------------------------------------------------
        split = chronological_split(
            features=features,
            orders=datasets["orders"],
            test_size=0.20,
        )

        # -----------------------------------------------------
        # 10. Prepare training data
        # -----------------------------------------------------
        X_train = split.train[
            MODEL_FEATURES
        ].copy()

        y_train = split.train[
            TARGET_COLUMN
        ].copy()

        # -----------------------------------------------------
        # 11. Train and save model
        #
        # train_model() also creates the prediction
        # interval calibration artifact.
        # -----------------------------------------------------
        model = train_model(
            X_train,
            y_train,
            enforce_production_gate=True,
        )

        # -----------------------------------------------------
        # 12. Log actual trained model parameters
        #
        # MLflow reads the parameters from the trained model
        # instead of maintaining a separate hardcoded copy.
        # -----------------------------------------------------
        log_parameters(
            model
        )

        # -----------------------------------------------------
        # 13. Load calibration metadata
        # -----------------------------------------------------
        if not CALIBRATION_MODEL_PATH.exists():
            raise FileNotFoundError(
                "Prediction interval calibration artifact "
                "was not created: "
                f"{CALIBRATION_MODEL_PATH}"
            )

        calibration = joblib.load(
            CALIBRATION_MODEL_PATH
        )

        # -----------------------------------------------------
        # 14. Production calibration safety gate
        #
        # Refuse to continue if the prediction interval was
        # calibrated on too few rows, which could indicate
        # accidental training on test fixture data.
        # -----------------------------------------------------
        check_production_calibration(
            calibration
        )

        # -----------------------------------------------------
        # 15. Log calibration metadata to MLflow
        # -----------------------------------------------------
        log_calibration_metadata(
            calibration
        )

        # -----------------------------------------------------
        # 16. Log trained model to MLflow
        # -----------------------------------------------------
        model_info = log_model(
            model
        )

        print("\nMLflow model logged:")
        print(
            f"  {model_info.model_uri}"
        )

        # -----------------------------------------------------
        # 17. Evaluate model against naive baseline
        # -----------------------------------------------------
        results = evaluate_model(
            model,
            split.train,
            split.test,
        )

        # -----------------------------------------------------
        # 18. Log evaluation metrics
        # -----------------------------------------------------
        log_metrics(
            results
        )

        # -----------------------------------------------------
        # 19. Log dataset/split metadata
        # -----------------------------------------------------
        log_dataset_metadata(
            features=features,
            train=split.train,
            test=split.test,
            split_timestamp=split.split_timestamp,
        )

        # -----------------------------------------------------
        # 20. Report prediction interval calibration
        # -----------------------------------------------------
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

        # -----------------------------------------------------
        # 21. Report chronological split
        # -----------------------------------------------------
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
                # -----------------------------------------------------
        # 21. Build H2 seed-route ETA features
        #
        # H2 uses only features available at shipment dispatch:
        # date-derived features + supplier-to-warehouse distance.
        # -----------------------------------------------------
        h2_features = build_h2_eta_features(
            datasets
        )

        h2_features = preprocess_h2_features(
            h2_features
        )

        # -----------------------------------------------------
        # 22. Chronological H2 split
        #
        # The same Olist time-based split is used so H2 can be
        # evaluated honestly against the same future period.
        # -----------------------------------------------------
        h2_split = chronological_split(
            features=h2_features,
            orders=datasets["orders"],
            test_size=0.20,
        )

        # -----------------------------------------------------
        # 23. Prepare H2 training data
        # -----------------------------------------------------

        h2_X_train = h2_split.train[
            H2_MODEL_FEATURES
        ].copy()

        h2_y_train = h2_split.train[
            TARGET_COLUMN
        ].copy()

        # -----------------------------------------------------
        # 24. Train H2 seed-route model
        # -----------------------------------------------------
        h2_model = train_h2_model(
            h2_X_train,
            h2_y_train,
        )

        # -----------------------------------------------------
        # 25. Load H2 interval calibration
        # -----------------------------------------------------
        if not H2_CALIBRATION_MODEL_PATH.exists():
            raise FileNotFoundError(
                "H2 prediction interval calibration artifact "
                "was not created: "
                f"{H2_CALIBRATION_MODEL_PATH}"
            )

        h2_calibration = joblib.load(
            H2_CALIBRATION_MODEL_PATH
        )

        # -----------------------------------------------------
        # 26. Log H2 parameters and tags
        # -----------------------------------------------------
        log_h2_parameters()

        # -----------------------------------------------------
        # 27. Evaluate H2 on the Olist future test period
        # -----------------------------------------------------
        h2_results = evaluate_h2_model(
            h2_model,
            h2_split.test,
            h2_calibration,
        )

        # -----------------------------------------------------
        # 28. Log H2 metrics
        # -----------------------------------------------------
        log_h2_metrics(
            h2_results
        )

        # -----------------------------------------------------
        # 29. Log H2 calibration metadata
        # -----------------------------------------------------
        log_calibration_metadata(
            h2_calibration
        )

        # -----------------------------------------------------
        # 30. Register H2 model with MLflow signature
        # -----------------------------------------------------
        h2_input_example = h2_X_train.head(1).copy()

        h2_model_info = log_h2_model(
            h2_model,
            h2_input_example,
        )

        print("\nH2 MLflow model logged and registered:")
        print(
            f"  {h2_model_info.model_uri}"
        )

        # -----------------------------------------------------
        # 31. Report H2 evaluation
        # -----------------------------------------------------
        print("\nH2 Seed-Route ETA Evaluation")
        print("============================")

        print(
            f"\nMAE:"
            f" {h2_results['mae']:.4f} days"
        )

        print(
            f"\nInterval coverage:"
            f" {h2_results['interval_coverage'] * 100:.2f}%"
        )

        print(
            f"\nH2 training rows:"
            f" {len(h2_split.train)}"
        )

        print(
            f"\nH2 test rows:"
            f" {len(h2_split.test)}"
        )

        print(
            "\nH2 features:"
            f" {H2_MODEL_FEATURES}"
        )

if __name__ == "__main__":
    main()