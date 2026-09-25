"""
Train Iris classifier.

Workflow:

1. Load data
2. Train model
3. Evaluate model
4. Log metrics to MLflow
5. Register model
6. Assign staging alias
7. Run quality gate
8. Request governance approval
9. Promote only if governance approval exists

Production promotion is blocked when governance approval
has not been granted for the exact model version.
"""

from sklearn.ensemble import RandomForestClassifier

from src.config import (
    MODEL_NAME,
    EXPERIMENT_NAME,
    RANDOM_STATE,
    N_ESTIMATORS,
    MAX_DEPTH,
    PROMOTION_ACCURACY_THRESHOLD,
    PROMOTED_BY,
    should_promote,
)

from src.data import load_data
from src.evaluate import evaluate

from src.mlflow_utils import (
    set_experiment,
    start_run,
    log_params,
    log_metrics,
    log_model,
    set_tags,
    assign_staging,
    promote_model,
)

from src.governance import governance_manager


def train():
    """
    Complete training pipeline.
    """

    # ======================================================
    # 1. Configure MLflow experiment
    # ======================================================

    set_experiment(
        EXPERIMENT_NAME
    )

    # ======================================================
    # 2. Load training data
    # ======================================================

    X_train, X_test, y_train, y_test = load_data()

    # ======================================================
    # 3. Start MLflow run
    # ======================================================

    with start_run(
        "RandomForest_Training"
    ):

        # ==================================================
        # 4. Create model
        # ==================================================

        model = RandomForestClassifier(
            n_estimators=N_ESTIMATORS,
            max_depth=MAX_DEPTH,
            random_state=RANDOM_STATE,
        )

        # ==================================================
        # 5. Train model
        # ==================================================

        model.fit(
            X_train,
            y_train,
        )

        # ==================================================
        # 6. Evaluate model
        # ==================================================

        accuracy, precision, recall, f1 = evaluate(
            model,
            X_test,
            y_test,
        )

        # ==================================================
        # 7. Log parameters
        # ==================================================

        log_params(
            {
                "algorithm": (
                    "RandomForestClassifier"
                ),
                "n_estimators": N_ESTIMATORS,
                "max_depth": MAX_DEPTH,
                "random_state": RANDOM_STATE,
            }
        )

        # ==================================================
        # 8. Log metrics
        # ==================================================

        log_metrics(
            {
                "accuracy": accuracy,
                "precision": precision,
                "recall": recall,
                "f1_score": f1,
            }
        )

        # ==================================================
        # 9. Add MLflow tags
        # ==================================================

        set_tags(
            {
                "project": "iris_reference",
                "framework": "scikit-learn",
                "workflow": (
                    "staging_to_production"
                ),
            }
        )

        # ==================================================
        # 10. Register model
        # ==================================================

        model_info = log_model(
            model=model,
            artifact_path="model",
            registered_model_name=MODEL_NAME,
        )

        # ==================================================
        # 11. Assign latest version to staging
        # ==================================================

        staging_version = assign_staging(
            MODEL_NAME
        )

        staging_version = str(
            staging_version
        )

        # ==================================================
        # 12. Production promotion
        # ==================================================

        production_version = None

        # --------------------------------------------------
        # Quality gate
        # --------------------------------------------------

        if should_promote(
            accuracy
        ):

            print(
                "\nModel passed the quality gate "
                f"(accuracy={accuracy:.4f} >= "
                f"{PROMOTION_ACCURACY_THRESHOLD:.2f})"
            )

            # ----------------------------------------------
            # Create governance request
            # ----------------------------------------------

            governance_request = (
                governance_manager.request_approval(
                    model_name=MODEL_NAME,
                    model_version=staging_version,
                    requested_by=PROMOTED_BY,
                    reason=(
                        "Model passed the quality gate "
                        f"with accuracy={accuracy:.4f}"
                    ),
                )
            )

            print(
                "\nGovernance approval required"
            )

            print(
                f"Model Version    : "
                f"{governance_request.model_version}"
            )

            print(
                f"Governance Status: "
                f"{governance_request.status}"
            )

            # ----------------------------------------------
            # Governance gate
            # ----------------------------------------------
            #
            # A freshly trained version is normally still
            # pending. That is the expected outcome, not
            # an error: we stop at staging and tell the
            # operator exactly what to run next.
            # ----------------------------------------------

            if governance_manager.is_approved(
                model_name=MODEL_NAME,
                model_version=staging_version,
            ):

                production_version = promote_model(
                    model_name=MODEL_NAME,
                    from_alias="staging",
                    to_alias="production",
                    expected_version=staging_version,
                )

            else:

                set_tags(
                    {
                        "governance_status": (
                            governance_request.status
                        )
                    }
                )

                print(
                    "\nProduction promotion is waiting "
                    "for governance approval."
                )

                print(
                    f"  Approve : python -m src.approve_model "
                    f"{MODEL_NAME} "
                    f'{staging_version} '
                    f'<approver_name> '
                    f'"<reason>"'
                )

                print(
                    f"  Promote : python -m src.promote_approved_model "
                    f"{MODEL_NAME} "
                    f"{staging_version}"
                )

        else:

            print(
                "\nModel remains in STAGING "
                f"(accuracy={accuracy:.4f} < "
                f"{PROMOTION_ACCURACY_THRESHOLD:.2f})"
            )

        # ==================================================
        # 13. Training summary
        # ==================================================

        print(
            "\n" + "=" * 60
        )

        print(
            "TRAINING COMPLETED"
        )

        print(
            "=" * 60
        )

        print(
            f"Model Name        : {MODEL_NAME}"
        )

        print(
            f"Staging Version   : "
            f"{staging_version}"
        )

        if production_version is not None:

            print(
                f"Production Version: "
                f"{production_version}"
            )

        else:

            print(
                "Production Version: Not promoted"
            )

        print(
            f"Accuracy          : "
            f"{accuracy:.4f}"
        )

        print(
            f"Precision         : "
            f"{precision:.4f}"
        )

        print(
            f"Recall            : "
            f"{recall:.4f}"
        )

        print(
            f"F1 Score          : "
            f"{f1:.4f}"
        )

        print(
            f"Model URI         : "
            f"{model_info.model_uri}"
        )

        print(
            "=" * 60
        )

        return model


if __name__ == "__main__":
    train()