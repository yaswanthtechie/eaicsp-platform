"""
MLflow tracking for sales anomaly runs: a run logs the expected keys, the
tracking URI comes from the environment, MLflow problems never stop a run,
and the configuration is registered once per set of thresholds.
"""

import logging
from pathlib import Path
import types
from unittest.mock import MagicMock

import mlflow
import pandas as pd
import pytest

import src.sales_anomaly_eval as sales_eval
from src import config
from src.sales_anomaly_tracking import (
    DRIFT_NAMES,
    EXPERIMENT,
    MODEL_NAME,
    THRESHOLD_NAMES,
    config_hash,
    date_range,
    drift_settings,
    log_run,
    register_configuration,
    registered_setup,
    safe_log_run,
    severity_counts,
    thresholds,
    tracking_uri,
)

URI = "http://mlflow.test:5000"


@pytest.fixture
def mlflow_calls(monkeypatch):
    """Replace the MLflow calls with mocks and point the URI at a fake server."""

    monkeypatch.setenv("MLFLOW_TRACKING_URI", URI)

    run = MagicMock()
    run.info.run_id = "run-1"

    start_run = MagicMock()
    start_run.return_value.__enter__.return_value = run

    calls = types.SimpleNamespace(start_run=start_run)

    for name in (
        "set_tracking_uri",
        "set_experiment",
        "log_params",
        "log_metrics",
        "log_text",
        "set_tags",
        "set_tag",
    ):
        mock = MagicMock()
        monkeypatch.setattr(mlflow, name, mock)
        setattr(calls, name, mock)

    monkeypatch.setattr(mlflow, "start_run", start_run)

    return calls


def logged_params(calls):
    return calls.log_params.call_args.args[0]


def logged_metrics(calls):
    return calls.log_metrics.call_args.args[0]


# ---------------------------------------------------------------------
# what a run logs
# ---------------------------------------------------------------------


def test_a_run_logs_the_expected_keys(mlflow_calls):

    result = log_run(
        "sales-anomaly-eval",
        params={"eval_seed": 5151},
        data_start="2025-01-06",
        data_end="2026-01-05",
        severities={"high": 1, "medium": 2, "low": 3},
        metrics={"precision": 0.82, "recall": 0.55},
        tags={"run_kind": "evaluation"},
    )

    params = logged_params(mlflow_calls)
    metrics = logged_metrics(mlflow_calls)

    # parameters: every threshold, every drift setting, the run's own and the data range
    for name in THRESHOLD_NAMES:
        assert name.lower() in params
    for name in DRIFT_NAMES:
        assert name.lower() in params

    assert params["eval_seed"] == 5151
    assert params["data_start"] == "2025-01-06"
    assert params["data_end"] == "2026-01-05"
    assert params["data_days"] == 365
    assert params["z_spike"] == config.Z_SPIKE

    # metrics: precision and recall, and anomalies by severity
    assert metrics["precision"] == 0.82
    assert metrics["recall"] == 0.55
    assert metrics["anomalies_high"] == 1
    assert metrics["anomalies_medium"] == 2
    assert metrics["anomalies_low"] == 3
    assert metrics["anomalies_total"] == 6

    mlflow_calls.set_tags.assert_called_once_with({"run_kind": "evaluation"})
    mlflow_calls.start_run.assert_called_once_with(run_name="sales-anomaly-eval")
    mlflow_calls.set_experiment.assert_called_once_with(EXPERIMENT)

    assert result == {"run_id": "run-1", "model_version": None}


def test_texts_are_logged_as_artifacts(mlflow_calls):

    log_run("batch", texts={"drift_report.html": "<html></html>"})

    mlflow_calls.log_text.assert_called_once_with("<html></html>", "drift_report.html")


def test_none_and_non_finite_values_are_not_logged(mlflow_calls):

    log_run(
        "batch",
        params={"reference": None, "last_days": 7},
        metrics={"a": None, "b": float("nan"), "c": float("inf"), "d": 2},
    )

    params = logged_params(mlflow_calls)

    assert "reference" not in params
    assert "data_start" not in params
    assert params["last_days"] == 7
    assert logged_metrics(mlflow_calls) == {"d": 2.0}


def test_severities_missing_from_the_input_are_logged_as_zero(mlflow_calls):

    log_run("batch", severities={"high": 4})

    metrics = logged_metrics(mlflow_calls)

    assert metrics["anomalies_high"] == 4
    assert metrics["anomalies_medium"] == 0
    assert metrics["anomalies_low"] == 0
    assert metrics["anomalies_total"] == 4


# ---------------------------------------------------------------------
# the tracking URI comes from the environment
# ---------------------------------------------------------------------


def test_the_tracking_uri_comes_from_the_environment(mlflow_calls, monkeypatch):

    log_run("batch")
    mlflow_calls.set_tracking_uri.assert_called_once_with(URI)

    mlflow_calls.set_tracking_uri.reset_mock()
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://other.test:9999")

    log_run("batch")
    mlflow_calls.set_tracking_uri.assert_called_once_with("http://other.test:9999")


def test_no_tracking_uri_is_hard_coded_in_the_sources():

    src = Path(sales_eval.__file__).parent

    for name in (
        "sales_anomaly_eval.py",
        "sales_anomaly_batch.py",
        "sales_anomaly_tracking.py",
        "sales_anomaly_drift.py",
        "sales_anomaly_model.py",
    ):
        text = (src / name).read_text(encoding="utf-8")

        assert "sqlite:///" not in text, name
        assert "http://localhost" not in text, name
        assert "http://mlflow" not in text, name


def test_without_a_tracking_uri_nothing_is_logged(mlflow_calls, monkeypatch, caplog):

    monkeypatch.delenv("MLFLOW_TRACKING_URI")

    with caplog.at_level(logging.WARNING):
        assert log_run("batch") is None

    mlflow_calls.start_run.assert_not_called()
    mlflow_calls.set_tracking_uri.assert_not_called()
    assert "MLFLOW_TRACKING_URI is not set" in caplog.text
    assert tracking_uri() is None


def test_a_blank_tracking_uri_counts_as_not_set(monkeypatch):

    monkeypatch.setenv("MLFLOW_TRACKING_URI", "   ")

    assert tracking_uri() is None


# ---------------------------------------------------------------------
# MLflow problems never stop a run
# ---------------------------------------------------------------------


def test_an_mlflow_error_becomes_a_warning(mlflow_calls, caplog):

    mlflow_calls.start_run.side_effect = RuntimeError("server down")

    with caplog.at_level(logging.WARNING):
        assert safe_log_run("batch") is None

    assert "MLflow logging failed" in caplog.text
    assert "server down" in caplog.text


def test_log_run_itself_raises(mlflow_calls):

    mlflow_calls.start_run.side_effect = RuntimeError("server down")

    with pytest.raises(RuntimeError):
        log_run("batch")


# ---------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------


def test_severity_counts_cover_every_severity():

    flagged = pd.DataFrame({"severity": ["low", "low", "high", "odd"]})

    assert severity_counts(flagged) == {"high": 1, "medium": 0, "low": 2}
    assert severity_counts(flagged.iloc[0:0]) == {"high": 0, "medium": 0, "low": 0}


def test_date_range():

    assert date_range(pd.to_datetime(["2026-03-02", "2026-01-05", None])) == (
        "2026-01-05",
        "2026-03-02",
    )
    assert date_range([]) == (None, None)


def test_thresholds_are_the_ones_in_config():

    values = thresholds()

    assert values["z_spike"] == config.Z_SPIKE
    assert values["drop_min_expected"] == config.DROP_MIN_EXPECTED
    assert set(values) == {name.lower() for name in THRESHOLD_NAMES}
    assert set(drift_settings()) == {name.lower() for name in DRIFT_NAMES}


def test_config_hash_follows_the_thresholds():

    base = config_hash()

    assert base == config_hash()
    assert base != config_hash({**thresholds(), "z_spike": config.Z_SPIKE + 1})


# ---------------------------------------------------------------------
# registering the configuration
# ---------------------------------------------------------------------


@pytest.fixture
def registry(monkeypatch):
    """Mocks for the model registry. `versions` is what the registry already holds."""

    registry = types.SimpleNamespace(versions=[])

    client = MagicMock()
    client.search_model_versions.side_effect = lambda query: registry.versions
    monkeypatch.setattr("mlflow.tracking.MlflowClient", lambda *a, **k: client)

    registry.client = client
    registry.log_model = MagicMock(return_value=types.SimpleNamespace(model_uri="runs:/run-1/model"))
    registry.register_model = MagicMock(return_value=types.SimpleNamespace(version="3"))

    import sys

    import mlflow.pyfunc  # load it for real, so the patch lands on the module itself

    monkeypatch.setattr(sys.modules["mlflow.pyfunc"], "log_model", registry.log_model)
    monkeypatch.setattr(mlflow, "register_model", registry.register_model)

    return registry


def test_the_configuration_is_registered_with_a_version(mlflow_calls, registry):

    result = log_run("sales-anomaly-eval", register=True)

    assert result == {"run_id": "run-1", "model_version": 3}

    kwargs = registry.log_model.call_args.kwargs
    assert kwargs["name"] == "model"
    assert any(path.endswith("src") for path in kwargs["code_paths"])
    assert "config" in kwargs["artifacts"]

    args, kwargs = registry.register_model.call_args
    assert args == ("runs:/run-1/model", MODEL_NAME)
    assert kwargs["tags"]["config_hash"] == config_hash()
    assert kwargs["tags"]["z_spike"] == str(config.Z_SPIKE)

    mlflow_calls.set_tag.assert_any_call("registered_model", MODEL_NAME)
    mlflow_calls.set_tag.assert_any_call("registered_model_version", "3")


def test_a_run_without_register_does_not_touch_the_registry(mlflow_calls, registry):

    log_run("batch")

    registry.log_model.assert_not_called()
    registry.register_model.assert_not_called()


def test_the_same_configuration_is_not_registered_twice(mlflow_calls, registry):

    registry.versions = [
        types.SimpleNamespace(version="2", tags={"config_hash": config_hash()}),
        types.SimpleNamespace(version="1", tags={"config_hash": "old"}),
    ]

    assert log_run("eval", register=True)["model_version"] == 2

    registry.log_model.assert_not_called()
    registry.register_model.assert_not_called()


def test_changed_thresholds_get_a_new_version(mlflow_calls, registry, monkeypatch):

    registry.versions = [
        types.SimpleNamespace(version="2", tags={"config_hash": config_hash()}),
    ]

    monkeypatch.setattr(config, "Z_SPIKE", config.Z_SPIKE + 0.5)

    assert register_configuration() == 3

    registry.register_model.assert_called_once()


def test_registered_setup_returns_the_metrics_of_the_matching_version(registry):

    registry.versions = [
        types.SimpleNamespace(
            version="4", run_id="run-9", tags={"config_hash": config_hash()}
        )
    ]
    registry.client.get_run.return_value = types.SimpleNamespace(
        data=types.SimpleNamespace(metrics={"precision": 0.82, "recall": 0.55})
    )

    assert registered_setup() == {"version": 4, "precision": 0.82, "recall": 0.55}
    registry.client.get_run.assert_called_once_with("run-9")


def test_registered_setup_is_none_when_this_configuration_is_not_registered(registry):

    registry.versions = [
        types.SimpleNamespace(version="1", run_id="run-1", tags={"config_hash": "old"})
    ]

    assert registered_setup() is None


# ---------------------------------------------------------------------
# the evaluation run
# ---------------------------------------------------------------------


def test_the_evaluation_logs_precision_recall_and_severity_counts(mlflow_calls):

    sales_eval.evaluate(log_mlflow=True, run_name="sales-anomaly-eval")

    params = logged_params(mlflow_calls)
    metrics = logged_metrics(mlflow_calls)

    assert params["eval_seed"] == sales_eval.EVAL_SEED
    assert params["dispersion"] == sales_eval.DISPERSION
    assert params["data_start"] == "2025-01-06"
    assert params["data_end"] == "2026-01-05"
    assert params["z_spike"] == config.Z_SPIKE

    for key in (
        "precision",
        "recall",
        "f1",
        "recall_spike",
        "recall_drop",
        "clean_false_alarms_per_1000",
        "anomalies_high",
        "anomalies_medium",
        "anomalies_low",
        "anomalies_total",
    ):
        assert key in metrics, key

    assert 0 < metrics["precision"] <= 1
    assert 0 < metrics["recall"] <= 1
    assert metrics["anomalies_total"] == (
        metrics["anomalies_high"] + metrics["anomalies_medium"] + metrics["anomalies_low"]
    )
    mlflow_calls.set_tags.assert_called_once_with({"run_kind": "evaluation"})


def test_the_evaluation_without_mlflow_logging_calls_nothing(mlflow_calls):

    sales_eval.evaluate()

    mlflow_calls.start_run.assert_not_called()


def test_register_goes_to_the_realistic_run_only(monkeypatch, tmp_path):

    calls = []

    def fake_evaluate(**kwargs):
        calls.append(kwargs)
        return pd.DataFrame([{"part": "overall"}])

    monkeypatch.setattr(sales_eval, "evaluate", fake_evaluate)
    monkeypatch.setattr(sales_eval, "results_dir", tmp_path)

    sales_eval.main(["--register"])

    assert calls[0]["register"] is True
    assert "register" not in calls[1]


def test_the_evaluation_does_not_register_by_default(monkeypatch, tmp_path):

    calls = []

    monkeypatch.setattr(
        sales_eval,
        "evaluate",
        lambda **kwargs: calls.append(kwargs) or pd.DataFrame([{"part": "overall"}]),
    )
    monkeypatch.setattr(sales_eval, "results_dir", tmp_path)

    sales_eval.main([])

    assert calls[0]["register"] is False


# ---------------------------------------------------------------------
# a real MLflow store (local database, nothing mocked)
# ---------------------------------------------------------------------


def test_a_run_is_stored_in_a_real_mlflow_database(tmp_path, monkeypatch):

    uri = "sqlite:///" + (tmp_path / "mlflow.db").as_posix()

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MLFLOW_TRACKING_URI", uri)
    monkeypatch.setenv("MLFLOW_DISABLE_TELEMETRY", "true")

    log_run(
        "real-store",
        params={"input": "x.csv"},
        data_start="2026-01-01",
        data_end="2026-03-31",
        severities={"high": 1, "medium": 2, "low": 3},
        metrics={"precision": 0.8, "recall": 0.5},
        texts={"drift_report.html": "<html>report</html>"},
        tags={"run_kind": "batch"},
    )

    from mlflow.tracking import MlflowClient

    client = MlflowClient(tracking_uri=uri)
    experiment = client.get_experiment_by_name(EXPERIMENT)
    [run] = client.search_runs([experiment.experiment_id])

    assert run.data.params["z_spike"] == str(config.Z_SPIKE)
    assert run.data.params["data_days"] == "90"
    assert run.data.metrics["anomalies_total"] == 6.0
    assert run.data.metrics["precision"] == 0.8
    assert run.data.tags["run_kind"] == "batch"
    assert [a.path for a in client.list_artifacts(run.info.run_id)] == ["drift_report.html"]


# ---------------------------------------------------------------------
# review fixes: tags survive a failed upload, short waits, code in the hash,
# --register that fails is a failure
# ---------------------------------------------------------------------


def test_tags_are_set_before_the_artifacts_are_uploaded(mlflow_calls):

    order = MagicMock()
    order.attach_mock(mlflow_calls.set_tags, "set_tags")
    order.attach_mock(mlflow_calls.log_text, "log_text")

    log_run("batch", texts={"drift_report.html": "<html/>"}, tags={"drift_alert": "true"})

    names = [call[0] for call in order.mock_calls]

    assert names.index("set_tags") < names.index("log_text")


def test_a_failed_artifact_upload_keeps_the_tags_and_only_warns(mlflow_calls, caplog):

    mlflow_calls.log_text.side_effect = RuntimeError("No module named 'boto3'")

    with caplog.at_level(logging.WARNING):
        result = log_run(
            "batch",
            texts={"drift_report.html": "<html/>"},
            tags={"drift_alert": "true"},
        )

    assert result["run_id"] == "run-1"
    mlflow_calls.set_tags.assert_called_once_with({"drift_alert": "true"})
    mlflow_calls.set_tag.assert_any_call("artifact_upload", "failed")
    assert "Could not save artifact 'drift_report.html'" in caplog.text


def test_waiting_for_mlflow_is_capped_unless_the_operator_says_otherwise(monkeypatch):

    from src.sales_anomaly_tracking import MLFLOW_WAIT_LIMITS, limit_waiting

    for name in MLFLOW_WAIT_LIMITS:
        monkeypatch.delenv(name, raising=False)

    monkeypatch.setenv("MLFLOW_HTTP_REQUEST_TIMEOUT", "99")

    limit_waiting()

    import os

    assert os.environ["MLFLOW_HTTP_REQUEST_MAX_RETRIES"] == "1"
    assert os.environ["MLFLOW_HTTP_REQUEST_TIMEOUT"] == "99"


def test_an_mlflow_outage_does_not_hold_the_run_up_for_minutes(monkeypatch):

    import time

    from src.sales_anomaly_tracking import MLFLOW_WAIT_LIMITS

    for name in MLFLOW_WAIT_LIMITS:
        monkeypatch.delenv(name, raising=False)

    monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://127.0.0.1:9")
    monkeypatch.setenv("MLFLOW_DISABLE_TELEMETRY", "true")

    started = time.monotonic()
    result = safe_log_run("outage")

    assert result is None
    assert time.monotonic() - started < 60


def test_the_hash_follows_the_detector_code_as_well_as_the_thresholds(
    tmp_path, monkeypatch
):

    import src.sales_anomaly_tracking as tracking

    source = tmp_path / "detector.py"
    monkeypatch.setattr(tracking, "DETECTOR_SOURCE", source)

    source.write_bytes(b"def detect():\n    return 1\n")
    first = config_hash()

    assert first == config_hash()

    # Windows line endings give the same hash.
    source.write_bytes(b"def detect():\r\n    return 1\r\n")
    assert config_hash() == first

    # A detector fix gives a new hash, so a new registered version.
    source.write_bytes(b"def detect():\n    return 2\n")
    assert config_hash() != first


def test_register_that_cannot_log_is_reported_by_the_evaluation(mlflow_calls, registry):

    registry.log_model.side_effect = RuntimeError("No module named 'boto3'")

    result = sales_eval.evaluate(log_mlflow=True, register=True)

    assert "boto3" in str(result.attrs["registration_error"])


def test_register_without_a_tracking_uri_is_reported_by_the_evaluation(monkeypatch):

    monkeypatch.delenv("MLFLOW_TRACKING_URI", raising=False)

    result = sales_eval.evaluate(log_mlflow=True, register=True)

    assert "MLFLOW_TRACKING_URI" in str(result.attrs["registration_error"])


def test_routine_logging_that_fails_is_still_only_a_warning(mlflow_calls):

    mlflow_calls.log_params.side_effect = RuntimeError("mlflow down")

    result = sales_eval.evaluate(log_mlflow=True)

    assert result.attrs["registration_error"] is None


def test_the_evaluation_exits_non_zero_when_register_failed(
    monkeypatch, tmp_path, capsys
):

    def failed(**kwargs):
        frame = pd.DataFrame([{"part": "overall"}])
        frame.attrs["registration_error"] = RuntimeError("no boto3")
        return frame

    monkeypatch.setattr(sales_eval, "evaluate", failed)
    monkeypatch.setattr(sales_eval, "results_dir", tmp_path)

    with pytest.raises(SystemExit) as stop:
        sales_eval.main(["--register"])

    assert stop.value.code == 1
    assert "REGISTRATION FAILED" in capsys.readouterr().err
    # The results are still written before it exits.
    assert (tmp_path / "sales_anomaly_eval.csv").exists()


def test_the_evaluation_exits_zero_when_register_worked(monkeypatch, tmp_path):

    monkeypatch.setattr(
        sales_eval, "evaluate", lambda **kwargs: pd.DataFrame([{"part": "overall"}])
    )
    monkeypatch.setattr(sales_eval, "results_dir", tmp_path)

    sales_eval.main(["--register"])


def test_a_real_registration_round_trip_loads_back_and_predicts(tmp_path, monkeypatch):

    import numpy as np

    uri = "sqlite:///" + (tmp_path / "mlflow.db").as_posix()

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MLFLOW_TRACKING_URI", uri)
    monkeypatch.setenv("MLFLOW_DISABLE_TELEMETRY", "true")

    first = log_run("eval-1", metrics={"precision": 0.8, "recall": 0.5}, register=True)
    second = log_run("eval-2", metrics={"precision": 0.8, "recall": 0.5}, register=True)

    assert first["model_version"] == 1
    assert second["model_version"] == 1  # same thresholds and code: no second version

    setup = registered_setup()

    assert setup == {"version": 1, "precision": 0.8, "recall": 0.5}

    model = mlflow.pyfunc.load_model(f"models:/{MODEL_NAME}/1")

    days = pd.date_range("2026-01-01", periods=90, freq="D")
    quantity = np.full(90, 50)
    quantity[70] = 400
    sales = pd.DataFrame(
        {
            "sale_date": days,
            "sku_id": "SKU-000001",
            "warehouse_id": "WH-BLR-01",
            "quantity_sold": quantity,
        }
    )

    scored = model.predict(sales)

    assert bool(scored["is_anomaly"].any())