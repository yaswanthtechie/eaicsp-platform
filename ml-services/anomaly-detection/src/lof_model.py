from itertools import product

from sklearn.neighbors import LocalOutlierFactor

from src.tuning_utils import (
    evaluate_model,
    rank_results,
    to_numpy,
)


class LOFModel:

    def __init__(
        self,
        contamination=0.004,
        n_neighbors=20,
        metric="minkowski",
        novelty=True,
    ):
        self.model = LocalOutlierFactor(
            contamination=contamination,
            n_neighbors=n_neighbors,
            metric=metric,
            novelty=novelty,
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
        n_neighbors_values=(10, 20, 30, 40, 50),
        metric_values=("euclidean", "manhattan", "minkowski"),
        top_n=10,
    ):
        """
        Hyperparameter tuning for Local Outlier Factor.
        """

        feature_columns = [
            "temperature",
            "humidity",
            "stock_count",
        ]

        print("Running LOF Hyperparameter Tuning...")

        X_train = to_numpy(train_features)

        results = []

        for contamination, n_neighbors, metric in product(
            contamination_values,
            n_neighbors_values,
            metric_values,
        ):

            model = LocalOutlierFactor(
                contamination=contamination,
                n_neighbors=n_neighbors,
                metric=metric,
                novelty=True,
            )

            model.fit(X_train)

            results.extend(
                evaluate_model(
                    model_name="LOF",
                    model=model,
                    test_datasets=test_datasets,
                    feature_columns=feature_columns,
                    hyperparameters={
                        "Contamination": contamination,
                        "n_estimators": None,
                        "max_samples": None,
                        "n_neighbors": n_neighbors,
                        "Metric": metric,
                        "Kernel": None,
                        "nu": None,
                        "gamma": None,
                        "degree": None,
                    },
                )
            )

        return rank_results(results,top_n=top_n)