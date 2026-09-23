import mlflow
from mlflow.tracking import MlflowClient
import pandas as pd


def get_all_runs(experiment_name: str, tracking_uri: str = None) -> pd.DataFrame:
    """
    Reads all FINISHED runs for an experiment from MLflow, across every
    model owner who has logged to it -- this is what lets the framework
    act as a pod-wide quality-control center rather than a single person's
    tool.

    Uses an explicit MlflowClient rather than mlflow.set_tracking_uri(),
    deliberately avoiding global state mutation -- calling this function
    should never change tracking behavior for unrelated code running in
    the same process.

    Only runs with status FINISHED are included. A crashed or still-running
    run typically has incomplete or missing metrics, which would silently
    corrupt downstream dashboard/regression calculations if included.

    experiment_name: the MLflow experiment to read
    tracking_uri: optional MLflow tracking URI. If not given, uses
        whatever MLflow is currently configured to use.

    Returns a dataframe with one row per finished run: run_id, start_time,
    status, plus one column per logged metric (prefixed "metrics."), tag
    (prefixed "tags."), and param (prefixed "params."). Expects a
    "tags.owner" and "tags.model_name" on each run for later aggregation.

    Raises ValueError if the experiment doesn't exist, or has no finished runs.
    """
    client = MlflowClient(tracking_uri=tracking_uri) if tracking_uri else MlflowClient()

    experiment = client.get_experiment_by_name(experiment_name)
    if experiment is None:
        raise ValueError(f"get_all_runs: no MLflow experiment named '{experiment_name}' found.")

    all_runs = client.search_runs(experiment_ids=[experiment.experiment_id])
    finished_runs = [r for r in all_runs if r.info.status == "FINISHED"]

    if not finished_runs:
        raise ValueError(
            f"get_all_runs: experiment '{experiment_name}' has no FINISHED runs "
            f"({len(all_runs)} run(s) found in other states)."
        )

    rows = []
    for run in finished_runs:
        row = {
            "run_id": run.info.run_id,
            "start_time": pd.Timestamp(run.info.start_time, unit="ms"),
            "status": run.info.status,
        }
        for k, v in run.data.metrics.items():
            row[f"metrics.{k}"] = v
        for k, v in run.data.params.items():
            row[f"params.{k}"] = v
        for k, v in run.data.tags.items():
            row[f"tags.{k}"] = v
        rows.append(row)

    return pd.DataFrame(rows)


def summarize_dashboard(runs_df: pd.DataFrame, metric: str, owner_tag_col: str = "tags.owner",
                           model_tag_col: str = "tags.model_name") -> dict:
    """
    Summarizes runs into a pod-wide dashboard view: for each (owner, model)
    pair, the latest run's value for the given metric, plus how many runs
    that owner/model has logged in total.

    metric: the metric name WITHOUT the "metrics." prefix (e.g. "mape").

    Returns:
    {
        "by_owner_model": {(owner, model): {"latest_score": float,
                                              "n_runs": int,
                                              "latest_run_id": str}},
        "owners": [distinct owners],
        "models": [distinct models],
    }

    Raises ValueError if the metric or tag columns aren't present in runs_df.
    """
    metric_col = f"metrics.{metric}"
    if metric_col not in runs_df.columns:
        raise ValueError(
            f"summarize_dashboard: metric '{metric}' not found (expected column "
            f"'{metric_col}'). Logged metrics: "
            f"{[c for c in runs_df.columns if c.startswith('metrics.')]}."
        )
    for col in (owner_tag_col, model_tag_col):
        if col not in runs_df.columns:
            raise ValueError(
                f"summarize_dashboard: expected tag column '{col}' not found. "
                f"Runs must be tagged with owner and model_name."
            )

    by_owner_model = {}
    for (owner, model), group in runs_df.groupby([owner_tag_col, model_tag_col]):
        latest = group.sort_values("start_time", ascending=False).iloc[0]
        by_owner_model[(owner, model)] = {
            "latest_score": latest[metric_col],
            "n_runs": len(group),
            "latest_run_id": latest["run_id"],
        }

    return {
        "by_owner_model": by_owner_model,
        "owners": sorted(runs_df[owner_tag_col].unique().tolist()),
        "models": sorted(runs_df[model_tag_col].unique().tolist()),
    }