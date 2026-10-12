
import os
from types import SimpleNamespace

import pytest

from etl.src.config_loader import load_pipeline_config, environment_config_path
from etl.src.sla_monitor import evaluate_quality_sla


def test_environment_switch_changes_config_without_code_change(monkeypatch):
    monkeypatch.setenv("ETL_ENV", "staging")
    config = load_pipeline_config()
    assert config.environment == "staging"
    assert config.schedule == "0 3 * * *"
    assert all(s.path.startswith("data/staging/") for s in config.sources)
    assert all(s.table.startswith("staging_") for s in config.sources)


def test_prod_profile(monkeypatch):
    monkeypatch.setenv("ETL_ENV", "prod")
    config = load_pipeline_config()
    assert config.environment == "prod"
    assert config.schedule == "0 1 * * *"
    assert all(s.path.startswith("data/prod/") for s in config.sources)
    assert all(s.table.startswith("prod_") for s in config.sources)


def test_invalid_environment_fails_clearly(monkeypatch):
    monkeypatch.setenv("ETL_ENV", "qa")
    with pytest.raises(ValueError, match="Unsupported ETL_ENV"):
        load_pipeline_config()


def test_explicit_config_path_overrides_environment(monkeypatch):
    monkeypatch.setenv("ETL_ENV", "prod")
    config = load_pipeline_config(environment_config_path("dev"))
    assert config.environment == "dev"
    assert config.schedule == "0 2 * * *"


def test_quality_sla_breaches_when_pass_rate_drops():
    result = evaluate_quality_sla(80, 0, 20, min_pass_rate=0.95)
    assert result["evaluable"] is True
    assert result["breached"] is True
    assert result["pass_rate"] == 0.8


def test_quality_sla_does_not_breach_at_threshold():
    result = evaluate_quality_sla(95, 0, 5, min_pass_rate=0.95)
    assert result["breached"] is False


def test_quality_sla_ignores_empty_run():
    result = evaluate_quality_sla(0, 0, 0)
    assert result["evaluable"] is False
    assert result["breached"] is False
