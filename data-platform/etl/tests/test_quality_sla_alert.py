from etl.src.sla_monitor import check_quality_sla


def test_quality_sla_alert_contains_required_evidence(monkeypatch):
    alerts = []

    monkeypatch.setattr(
        "etl.src.sla_monitor.write_alert",
        lambda **kwargs: alerts.append(kwargs),
    )

    result = check_quality_sla(
        run_id=123,
        source_name="sales",
        rows_inserted=80,
        rows_updated=0,
        rows_rejected=20,
        environment="dev",
        table="sales_fact",
        batch_files=[
            "sales_2024-01-05.csv",
            "sales_2024-01-06_degraded.csv",
        ],
        pipeline_name="sales_etl",
        min_pass_rate=0.95,
    )

    assert result["breached"] is True
    assert result["pass_rate"] == 0.8
    assert len(alerts) == 1
    assert alerts[0]["severity"] == "CRITICAL"
    assert "Data-quality SLA breached" in alerts[0]["message"]
    assert "environment=dev" in alerts[0]["message"]
    assert "table=sales_fact" in alerts[0]["message"]
    assert "sales_2024-01-06_degraded.csv" in alerts[0]["message"]


def test_quality_sla_no_alert_when_threshold_is_met(monkeypatch):
    alerts = []

    monkeypatch.setattr(
        "etl.src.sla_monitor.write_alert",
        lambda **kwargs: alerts.append(kwargs),
    )

    result = check_quality_sla(
        run_id=124,
        source_name="sales",
        rows_inserted=95,
        rows_updated=0,
        rows_rejected=5,
        environment="dev",
        table="sales_fact",
        batch_files=["sales_2024-01-06.csv"],
        pipeline_name="sales_etl",
        min_pass_rate=0.95,
    )

    assert result["breached"] is False
    assert result["pass_rate"] == 0.95
    assert alerts == []
