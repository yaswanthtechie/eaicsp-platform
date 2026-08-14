from itertools import product

from sklearn.ensemble import IsolationForest

from src.tuning_utils import (
    evaluate_model,
    rank_results,
    to_numpy,
)


class IsolationForestModel:
    def __init__(
        self,
        contamination=0.004,
        n_estimators=100,
        max_samples="auto",
        random_state=42,
    ):
        self.model = IsolationForest(
            contamination=contamination,
            n_estimators=n_estimators,
            max_samples=max_samples,
            random_state=random_state,
        )

    def train(self, features):
        self.model.fit(to_numpy(features))

    def predict(self, features):
        return self.model.predict(to_numpy(features))

    def score(self, features):
        return self.model.decision_function(to_numpy(features))

    def tune(
        self,
        train_features,
        test_datasets,
        contamination_values=(0.004, 0.006, 0.008, 0.01),
        n_estimators_values=(100, 200, 300, 500),
        max_samples_values=(0.6, 0.8, 1.0),
        top_n=10,
    ):
        """
        Hyperparameter tuning for Isolation Forest.
        """

        feature_columns = [
            "temperature",
            "humidity",
            "stock_count",
        ]

        print("Running Isolation Forest Hyperparameter Tuning...")

        X_train = to_numpy(train_features)

        results = []

        for contamination, n_estimators, max_samples in product(
            contamination_values,
            n_estimators_values,
            max_samples_values,
        ):

            model = IsolationForest(
                contamination=contamination,
                n_estimators=n_estimators,
                max_samples=max_samples,
                random_state=42,
            )

            model.fit(X_train)

            results.extend(
                evaluate_model(
                    model_name="Isolation Forest",
                    model=model,
                    test_datasets=test_datasets,
                    feature_columns=feature_columns,
                    hyperparameters={
                        "Contamination": contamination,
                        "n_estimators": n_estimators,
                        "max_samples": max_samples,
                        "n_neighbors": None,
                        "Metric": None,
                        "Kernel": None,
                        "nu": None,
                        "gamma": None,
                        "degree": None,
                    },
                )
            )

        return rank_results(results,top_n=top_n)