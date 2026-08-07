import numpy as np
import pandas as pd

from sklearn.metrics import (
    confusion_matrix,
    precision_score,
    recall_score,
    f1_score,
)


def evaluate_model(
    model_name,
    model,
    test_datasets,
    feature_columns,
    hyperparameters,
    scaler=None,
):
    """
    Evaluate a trained model on all test datasets.

    Parameters
    ----------
    model_name : str
        Display name of the model.

    model : sklearn estimator
        Trained estimator.

    test_datasets : dict
        Dictionary containing test DataFrames.

    feature_columns : list
        Feature column names.

    hyperparameters : dict
        Hyperparameters used for this model.

    scaler : sklearn scaler, optional
        Used only for One-Class SVM.

    Returns
    -------
    list
        List of result dictionaries.
    """

    results = []

    for dataset_name, dataset in test_datasets.items():

        X_test = dataset[feature_columns].to_numpy()
        y_true = dataset["is_anomaly"].to_numpy()

        if scaler is not None:
            X_test = scaler.transform(X_test)

        predictions = (model.predict(X_test) == -1).astype(int)

        tn, fp, fn, tp = confusion_matrix(
            y_true,
            predictions,
        ).ravel()

        precision = precision_score(
            y_true,
            predictions,
            zero_division=0,
        )

        recall = recall_score(
            y_true,
            predictions,
            zero_division=0,
        )

        f1 = f1_score(
            y_true,
            predictions,
            zero_division=0,
        )

        row = {
            "Model": model_name,
            "Test Dataset": dataset_name,
            "Precision": precision,
            "Recall": recall,
            "PR Score": (precision + recall) / 2,
            "F1": f1,
            "TP": tp,
            "TN": tn,
            "FP": fp,
            "FN": fn,
        }

        row.update(hyperparameters)

        results.append(row)

    return results


def rank_results(results, top_n=10):
    """
    Rank the hyperparameter combinations separately
    for each test dataset using the average of
    Precision and Recall.
    """

    results = pd.DataFrame(results)

    ranked = []

    for dataset_name in results["Test Dataset"].unique():

        dataset_df = (
            results[
                results["Test Dataset"] == dataset_name
            ]
            .sort_values(
                by=[
                    "PR Score",
                    "F1",
                    "FP",
                    "FN",
                ],
                ascending=[
                    False,
                    False,
                    True,
                    True,
                ],
            )
            .head(top_n)
            .copy()
        )

        dataset_df.insert(
            0,
            "Rank",
            range(1, len(dataset_df) + 1),
        )

        ranked.append(dataset_df)

    return pd.concat(
        ranked,
        ignore_index=True,
    )


def to_numpy(data):
    """
    Convert pandas DataFrame/Series to NumPy array.
    Leaves NumPy arrays unchanged.
    """

    if isinstance(data, (pd.DataFrame, pd.Series)):
        return data.to_numpy()

    return np.asarray(data)