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

        tn, fp, fn, tp = confusion_matrix(y_true,predictions).ravel()

        precision = precision_score(y_true,predictions,zero_division=0)

        recall = recall_score(y_true,predictions,zero_division=0)

        f1 = f1_score(y_true,predictions,zero_division=0)

        row = {
            "Model": model_name,
            "Test Dataset": dataset_name,
            "Precision": precision,
            "Recall": recall,
            "PR Score": (
                precision + recall
            ) / 2,
            "F1": f1,
            "TP": tp,
            "TN": tn,
            "FP": fp,
            "FN": fn,
        }

        row.update(hyperparameters)

        results.append(row)

    return results


def rank_results(results,top_n=10,):
    """
    Rank hyperparameter combinations.

    Produces two types of rankings:

    1. OVERALL ranking
       Each exact hyperparameter configuration is
       evaluated across all four anomaly datasets.

       Overall candidates are selected using the
       Pareto frontier of Average Recall and
       Average Precision.

       A configuration is removed only when another
       configuration has:

       - Equal or better Average Recall
       - Equal or better Average Precision

       and is strictly better in at least one.

       Remaining Pareto configurations are ranked by:

       - Average Recall: higher is better
       - Minimum Recall: higher is better
       - Average Precision: higher is better
       - Average F1: higher is better
       - Total FP: lower is better
       - Total FN: lower is better

    2. PER-DATASET ranking
       Top configurations are retained separately
       for each anomaly dataset.
    """

    results = pd.DataFrame(results)

    if results.empty:
        return results

    # Columns that describe evaluation results
    # rather than hyperparameters.

    metric_columns = {
        "Test Dataset",
        "Precision",
        "Recall",
        "PR Score",
        "F1",
        "TP",
        "TN",
        "FP",
        "FN",
        "Rank",
        "Minimum Recall",
    }

    # Everything else identifies the model/configuration.

    configuration_columns = [column for column in results.columns if column not in metric_columns]

    # Overall ranking

    overall = (
        results
        .groupby(
            configuration_columns,
            dropna=False,
        )
        .agg(
            {
                "Precision": "mean",
                "Recall": [
                    "mean",
                    "min",
                ],
                "PR Score": "mean",
                "F1": "mean",
                "TP": "sum",
                "TN": "sum",
                "FP": "sum",
                "FN": "sum",
            }
        )
        .reset_index()
    )

    overall.columns = [
        " ".join(
            column
        ).strip()
        if isinstance(column,tuple)
        else column
        for column in overall.columns
    ]

    overall.rename(
        columns={
            "Recall mean": "Recall",
            "Recall min": "Minimum Recall",
            "Precision mean": "Precision",
            "PR Score mean": "PR Score",
            "F1 mean": "F1",
            "TP sum": "TP",
            "TN sum": "TN",
            "FP sum": "FP",
            "FN sum": "FN",
        },
        inplace=True,
    )

    # Find Pareto-optimal configurations.

    pareto_mask = []

    for index, current in overall.iterrows():

        dominated = False

        for other_index, other in overall.iterrows():

            if index == other_index:
                continue

            recall_better_or_equal = (
                other["Recall"]
                >= current["Recall"]
            )

            precision_better_or_equal = (
                other["Precision"]
                >= current["Precision"]
            )

            recall_strictly_better = (
                other["Recall"]
                > current["Recall"]
            )

            precision_strictly_better = (
                other["Precision"]
                > current["Precision"]
            )

            if (
                recall_better_or_equal
                and precision_better_or_equal
                and (
                    recall_strictly_better
                    or precision_strictly_better
                )
            ):

                dominated = True

                break

        pareto_mask.append(
            not dominated
        )

    overall["Pareto"] = pareto_mask

    overall = overall[
        overall["Pareto"]
    ].copy()

    # Mark these rows so they can be identified later.

    overall.insert(1,"Test Dataset","OVERALL")

    # Rank Pareto configurations.

    overall = (
        overall
        .sort_values(
            by=[
                "Recall",
                "Minimum Recall",
                "Precision",
                "F1",
                "FP",
                "FN",
            ],
            ascending=[
                False,
                False,
                False,
                False,
                True,
                True,
            ],
        )
        .copy()
    )

    overall.insert(0,"Rank",range(1,len(overall) + 1))

    # Per-dataset ranking

    ranked = []

    for dataset_name in (results["Test Dataset"].unique()):

        dataset_df = (
            results[
                results["Test Dataset"]
                == dataset_name
            ]
            .sort_values(
                by=[
                    "Recall",
                    "Precision",
                    "F1",
                    "FP",
                    "FN",
                ],
                ascending=[
                    False,
                    False,
                    False,
                    True,
                    True,
                ],
            )
            .head(top_n)
            .copy()
        )

        dataset_df.insert(0,"Rank", range(1,len(dataset_df) + 1))

        ranked.append(dataset_df)

    per_dataset = pd.concat(ranked,ignore_index=True)

    # Combine rankings

    return pd.concat([overall,per_dataset],ignore_index=True)


def to_numpy(data):
    """
    Convert pandas DataFrame/Series to NumPy array.
    Leaves NumPy arrays unchanged.
    """

    if isinstance(data,(pd.DataFrame,pd.Series)):

        return data.to_numpy()

    return np.asarray(data)