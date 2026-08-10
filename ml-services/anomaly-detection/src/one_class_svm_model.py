from itertools import product

from sklearn.preprocessing import StandardScaler
from sklearn.svm import OneClassSVM

from src.tuning_utils import (
    evaluate_model,
    rank_results,
    to_numpy,
)


class OneClassSVMModel:

    def __init__(
        self,
        nu=0.004,
        kernel="rbf",
        gamma="scale",
        degree=3,
    ):
        self.scaler = StandardScaler()

        self.model = OneClassSVM(
            nu=nu,
            kernel=kernel,
            gamma=gamma,
            degree=degree,
        )

    def train(self, features):
        scaled = self.scaler.fit_transform(to_numpy(features))
        self.model.fit(scaled)

    def predict(self, features):
        scaled = self.scaler.transform(to_numpy(features))
        return self.model.predict(scaled)

    def score(self, features):
        scaled = self.scaler.transform(to_numpy(features))
        return self.model.decision_function(scaled)

    def tune(
        self,
        train_features,
        test_datasets,
        kernels=("linear", "rbf", "poly", "sigmoid"),
        nus=(0.004, 0.005, 0.006, 0.008, 0.01),
        gammas=("scale", "auto", 0.001, 0.01, 0.1),
        degrees=(2, 3, 4),
        top_n=10,
    ):
        """
        Hyperparameter tuning for One-Class SVM.
        """

        feature_columns = [
            "temperature",
            "humidity",
            "stock_count",
        ]

        print("Running One-Class SVM Hyperparameter Tuning...")

        X_train = self.scaler.fit_transform(to_numpy(train_features))

        results = []

        for kernel in kernels:

            for nu in nus:

                gamma_values = (
                    [None]
                    if kernel == "linear"
                    else gammas
                )

                degree_values = (
                    degrees
                    if kernel == "poly"
                    else [None]
                )

                for gamma, degree in product(
                    gamma_values,
                    degree_values,
                ):

                    params = {
                        "kernel": kernel,
                        "nu": nu,
                    }

                    if gamma is not None:
                        params["gamma"] = gamma

                    if degree is not None:
                        params["degree"] = degree

                    model = OneClassSVM(**params)

                    model.fit(X_train)

                    results.extend(
                        evaluate_model(
                            model_name="One-Class SVM",
                            model=model,
                            test_datasets=test_datasets,
                            feature_columns=feature_columns,
                            scaler=self.scaler,
                            hyperparameters={
                                "Contamination": None,
                                "n_estimators": None,
                                "max_samples": None,
                                "n_neighbors": None,
                                "Metric": None,
                                "Kernel": kernel,
                                "nu": nu,
                                "gamma": gamma,
                                "degree": degree,
                            },
                        )
                    )

        return rank_results(results,top_n=top_n)