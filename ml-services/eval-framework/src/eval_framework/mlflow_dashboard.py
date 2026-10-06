import mlflow
from mlflow.tracking import MlflowClient
import pandas as pd


def get_all_runs(experiment_name: str, tracking_uri: str = None, max_results: int = None) -> pd.DataFrame:
    """
    Reads all FINISHED runs for an experiment from MLflow, across every
    model owner who has logged to it -- this is what lets the framework
    act as a pod-wide quality-control center rather than a single person's
    tool.

    Uses an explicit MlflowClient rather than mlflow.set_tracking_uri(),
    deliberately avoiding global state mutation.

    Filters to FINISHED runs SERVER-SIDE via MLflow's filter_string, not by
    fetching everything and filtering afterward -- filtering after the fact
    would make max_results cap the number of RAW runs fetched (including
    ones later discarded), silently returning fewer FINISHED runs than the
    caller asked for. Filtering server-side means max_results genuinely
    means "up to this many finished runs".

    Paginates through MLflow's search results automatically -- MLflow's
    default page size is 1000, so a naive single call silently truncates
    any experiment with more runs than that.

    experiment_name: the MLflow experiment to read
    tracking_uri: optional MLflow tracking URI. If not given, uses
        whatever MLflow is currently configured to use.
    max_results: optional cap on the number of FINISHED runs returned
        (None = fetch everything).

    Returns a dataframe with one row per finished run: run_id, start_time,
    status, plus one column per logged metric (prefixed "metrics."), tag
    (prefixed "tags."), and param (prefixed "params."). Runs missing the
    "tags.owner" or "tags.model_name" tag are still included (as NaN in
    those columns) -- they are NOT silently dropped; summarize_dashboard()
    reports how many were untagged rather than hiding them.

    Raises ValueError if the experiment doesn't exist, or has no finished runs.
    """
    client = MlflowClient(tracking_uri=tracking_uri) if tracking_uri else MlflowClient()

    experiment = client.get_experiment_by_name(experiment_name)
    if experiment is None:
        raise ValueError(f"get_all_runs: no MLflow experiment named '{experiment_name}' found.")

    finished_runs = []
    page_token = None
    while True:
        remaining = None if max_results is None else max_results - len(finished_runs)
        if remaining is not None and remaining <= 0:
            break
        page_size = 1000 if remaining is None else min(1000, remaining)
        page = client.search_runs(
            experiment_ids=[experiment.experiment_id],
            filter_string="attributes.status = 'FINISHED'",
            page_token=page_token,
            max_results=page_size,
        )
        finished_runs.extend(page)
        page_token = page.token if hasattr(page, "token") else None
        if not page_token:
            break

    if not finished_runs:
        raise ValueError(f"get_all_runs: experiment '{experiment_name}' has no FINISHED runs.")

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

    Runs missing the owner and/or model tag are grouped under the explicit
    sentinel "untagged" rather than crashing or being silently dropped by
    groupby. The count of such runs is reported explicitly.

    metric: the metric name WITHOUT the "metrics." prefix (e.g. "mape").

    Returns:
    {
        "by_owner_model": {(owner, model): {"latest_score": float,
                                              "n_runs": int,
                                              "latest_run_id": str}},
        "owners": [distinct owners, including "untagged" if applicable],
        "models": [distinct models, including "untagged" if applicable],
        "untagged_runs": int,
    }

    Raises ValueError if runs_df is empty, or if the metric or tag columns
    aren't present.
    """
    if len(runs_df) == 0:
        raise ValueError("summarize_dashboard: runs_df is empty -- nothing to summarize.")

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

    runs_df = runs_df.copy()
    untagged_mask = runs_df[owner_tag_col].isna() | runs_df[model_tag_col].isna()
    untagged_runs = int(untagged_mask.sum())

    runs_df[owner_tag_col] = runs_df[owner_tag_col].fillna("untagged")
    runs_df[model_tag_col] = runs_df[model_tag_col].fillna("untagged")

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
        "untagged_runs": untagged_runs,
    }