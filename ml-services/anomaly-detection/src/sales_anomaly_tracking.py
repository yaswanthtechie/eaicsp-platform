"""
MLflow tracking for sales anomaly runs (R15-K6).

Every run (the evaluation and each batch job run) logs the same things:

    parameters   the thresholds in src/config.py, the drift settings, and what
                 is specific to the run (input, window, seeds)
    data range   data_start, data_end, data_days
    metrics      anomalies_high / anomalies_medium / anomalies_low / anomalies_total
                 (flagged days by severity), plus precision and recall on the
                 injected anomalies (evaluation) or the drift numbers (batch)
    artifacts    the Evidently drift report (batch)

The tracking URI comes from the MLFLOW_TRACKING_URI environment variable and
is never hard-coded. With the variable unset nothing is logged and a warning
says so. Tracking never stops a run: safe_log_run() turns any MLflow error
into a warning.

register_configuration() registers the chosen configuration (thresholds and
code) in the MLflow model registry as a new version. The same thresholds with
the same detector code are never registered twice: versions carry a config_hash
tag, a fingerprint of both. A change to either gives a new version.

mlflow is imported inside the functions, so importing this module is cheap and
tests can replace the mlflow calls.
"""

import hashlib
import json
import logging
import math
import os
from pathlib import Path
import tempfile

import pandas as pd

from . import config


log = logging.getLogger("sales_anomaly_tracking")

EXPERIMENT = "anomaly-detection-r15-sales"
MODEL_NAME = "sales-anomaly-detector"
SEVERITIES = ("high", "medium", "low")

SERVICE_ROOT = Path(__file__).resolve().parents[1]
DETECTOR_SOURCE = Path(__file__).resolve().with_name("sales_anomaly.py")

# With MLflow down, the defaults (7 retries with growing waits) kept one call
# waiting for minutes. These cap it; an environment variable set by the
# operator wins.
MLFLOW_WAIT_LIMITS = {
    "MLFLOW_HTTP_REQUEST_MAX_RETRIES": "1",
    "MLFLOW_HTTP_REQUEST_BACKOFF_FACTOR": "1",
    "MLFLOW_HTTP_REQUEST_TIMEOUT": "10",
}

THRESHOLD_NAMES = (
    "Z_SPIKE",
    "SPIKE_MEDIUM",
    "SPIKE_HIGH",
    "DROP_MIN_EXPECTED",
    "DROP_LOW",
    "DROP_MEDIUM",
    "DROP_HIGH",
    "LOOKBACK_WEEKS",
    "MIN_WEEKS",
    "MIN_SERIES_DAYS",
    "MAD_TO_SIGMA",
    "DISPERSION_K",
    "RUN_GAP_DAYS",
    "FALSE_ALARM_BUDGET",
)

DRIFT_NAMES = (
    "DRIFT_LATEST_DAYS",
    "DRIFT_SAMPLE_ROWS",
    "DRIFT_NUM_THRESHOLD",
    "DRIFT_CAT_THRESHOLD",
    "DRIFT_ALERT_SHARE",
)


def limit_waiting():
    """Keep an MLflow outage from holding up a run for minutes."""

    for name, value in MLFLOW_WAIT_LIMITS.items():
        os.environ.setdefault(name, value)


def tracking_uri():
    """MLFLOW_TRACKING_URI, or None when it is not set."""

    return os.environ.get("MLFLOW_TRACKING_URI", "").strip() or None


def thresholds():
    """The detection thresholds in force, from src/config.py."""

    return {name.lower(): getattr(config, name) for name in THRESHOLD_NAMES}


def drift_settings():
    """The drift check settings in force, from src/config.py."""

    return {name.lower(): getattr(config, name) for name in DRIFT_NAMES}


def code_fingerprint():
    """Fingerprint of the detector code (line endings ignored, so Windows and Linux agree)."""

    source = DETECTOR_SOURCE.read_bytes().replace(b"\r\n", b"\n")

    return hashlib.sha256(source).hexdigest()[:16]


def config_hash(values=None):
    """
    Short fingerprint of a configuration: the thresholds AND the detector code.
    The same thresholds with the same code give the same hash; a change to
    either gives a new registered version.
    """

    text = json.dumps(
        {
            "thresholds": values if values is not None else thresholds(),
            "code": code_fingerprint(),
        },
        sort_keys=True,
    )

    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def severity_counts(flagged):
    """Flagged days by severity, with every severity present."""

    counts = {severity: 0 for severity in SEVERITIES}

    if len(flagged):
        for severity, count in flagged["severity"].value_counts().items():
            if severity in counts:
                counts[severity] = int(count)

    return counts


def date_range(dates):
    """(start, end) as YYYY-MM-DD strings, or (None, None) for no dates."""

    dates = pd.to_datetime(pd.Series(dates)).dropna()

    if dates.empty:
        return None, None

    return dates.min().date().isoformat(), dates.max().date().isoformat()


def _finite_metrics(values):

    clean = {}

    for name, value in values.items():
        if value is None:
            continue

        value = float(value)

        if math.isfinite(value):
            clean[name] = value

    return clean


def log_run(
    run_name,
    *,
    params=None,
    data_start=None,
    data_end=None,
    severities=None,
    metrics=None,
    texts=None,
    tags=None,
    register=False,
):
    """
    Log one run. Returns {"run_id": ..., "model_version": ...}, or None when
    MLFLOW_TRACKING_URI is not set. model_version is None unless register=True.

    severities: flagged days by severity, {"high": n, "medium": n, "low": n}.
    texts: {artifact file name: text}, e.g. the drift report HTML.
    """

    uri = tracking_uri()

    if uri is None:
        log.warning(
            "MLFLOW_TRACKING_URI is not set: run '%s' is not logged to MLflow.",
            run_name,
        )
        return None

    limit_waiting()

    import mlflow

    mlflow.set_tracking_uri(uri)
    mlflow.set_experiment(EXPERIMENT)

    all_params = {**thresholds(), **drift_settings(), **(params or {})}
    all_params["data_start"] = data_start
    all_params["data_end"] = data_end

    if data_start and data_end:
        all_params["data_days"] = (
            pd.Timestamp(data_end) - pd.Timestamp(data_start)
        ).days + 1

    all_metrics = dict(metrics or {})

    if severities is not None:
        for severity in SEVERITIES:
            all_metrics[f"anomalies_{severity}"] = severities.get(severity, 0)

        all_metrics["anomalies_total"] = sum(
            severities.get(severity, 0) for severity in SEVERITIES
        )

    model_version = None

    with mlflow.start_run(run_name=run_name) as run:

        mlflow.log_params({k: v for k, v in all_params.items() if v is not None})
        mlflow.log_metrics(_finite_metrics(all_metrics))

        # Tags before any artifact upload: a failed upload must not lose them.
        if tags:
            mlflow.set_tags(tags)

        for name, text in (texts or {}).items():
            try:
                mlflow.log_text(text, name)
            except Exception as error:
                mlflow.set_tag("artifact_upload", "failed")
                log.warning(
                    "Could not save artifact '%s' for run '%s': %s",
                    name,
                    run_name,
                    error,
                )

        if register:
            model_version = register_configuration()

            mlflow.set_tag("registered_model", MODEL_NAME)
            mlflow.set_tag("registered_model_version", str(model_version))

        run_id = run.info.run_id

    return {"run_id": run_id, "model_version": model_version}


def safe_log_run(run_name, **kwargs):
    """log_run that never raises: an MLflow problem becomes a warning."""

    try:
        return log_run(run_name, **kwargs)
    except Exception as error:
        log.warning("MLflow logging failed for run '%s': %s", run_name, error)
        return None


def _version_with_hash(client, digest, model_name=MODEL_NAME):

    for version in client.search_model_versions(f"name='{model_name}'"):
        if (version.tags or {}).get("config_hash") == digest:
            return version

    return None


def register_configuration(model_name=MODEL_NAME):
    """
    Register the configuration in force as a new model version, inside the
    active MLflow run. Returns the version number. If a version with the same
    thresholds already exists, no new version is made and its number returned.
    """

    import mlflow
    import mlflow.pyfunc
    from mlflow.tracking import MlflowClient

    values = thresholds()
    digest = config_hash(values)

    existing = _version_with_hash(MlflowClient(), digest, model_name)

    if existing is not None:
        log.info(
            "Configuration %s is already registered as %s version %s.",
            digest,
            model_name,
            existing.version,
        )
        return int(existing.version)

    from .sales_anomaly_model import SalesAnomalyModel

    with tempfile.TemporaryDirectory() as folder:

        config_path = Path(folder) / "config.json"
        config_path.write_text(
            json.dumps(values, indent=2, sort_keys=True), encoding="utf-8"
        )

        info = mlflow.pyfunc.log_model(
            name="model",
            python_model=SalesAnomalyModel(),
            artifacts={"config": str(config_path)},
            code_paths=[str(SERVICE_ROOT / "src")],
        )

    registered = mlflow.register_model(
        info.model_uri,
        model_name,
        tags={"config_hash": digest, "z_spike": str(values["z_spike"])},
    )

    return int(registered.version)


def registered_setup(model_name=MODEL_NAME):
    """
    The registered version that matches the configuration in force, with the
    precision and recall measured when it was set up:
    {"version": int, "precision": float|None, "recall": float|None}, or None
    when this configuration was never registered.
    """

    from mlflow.tracking import MlflowClient

    limit_waiting()

    client = MlflowClient()
    version = _version_with_hash(client, config_hash(), model_name)

    if version is None:
        return None

    metrics = client.get_run(version.run_id).data.metrics

    return {
        "version": int(version.version),
        "precision": metrics.get("precision"),
        "recall": metrics.get("recall"),
    }