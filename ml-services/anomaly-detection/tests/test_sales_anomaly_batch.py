"""
The sales anomaly batch job: one event per new incident, and a re-run
publishes nothing new.
"""

import json
import logging
import sys
import types
from pathlib import Path
from typing import ClassVar
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest
from jsonschema import FormatChecker
from jsonschema.validators import validator_for
from referencing import Registry, Resource

from src.sales_anomaly_batch import (
    FanOutPublisher,
    KafkaSalesEventPublisher,
    PublishedLedger,
    main,
    read_sales,
    run,
)
from src.sales_anomaly_events import anomaly_key

REPO_ROOT = Path(__file__).resolve().parents[3]
EVENTS_DIR = REPO_ROOT / "contracts" / "events"


@pytest.fixture(autouse=True)
def no_mlflow_server(monkeypatch):
    """These tests never talk to MLflow unless a test sets the URI itself."""

    monkeypatch.delenv("MLFLOW_TRACKING_URI", raising=False)


START = "2026-06-01"
SPIKE_DAY = 70
STOP_DAY = 75


class ListPublisher:
    def __init__(self):
        self.events = []

    def publish(self, event):
        self.events.append(event)


class FailingPublisher(ListPublisher):
    """Delivers the first `ok` events, then fails."""

    def __init__(self, ok):
        super().__init__()
        self._ok = ok

    def publish(self, event):

        if len(self.events) >= self._ok:
            raise RuntimeError("broker down")

        super().publish(event)


def make_sales(days=90, extra_spike_day=None, sku_a="SKU-000001", sku_b="SKU-000002"):
    """
    Flat 50 units a day at WH-BLR-01. sku_a spikes to 400 on SPIKE_DAY.
    sku_b stops selling at STOP_DAY while sku_a keeps reporting, so it gets
    zero days (one drop incident that lasts for weeks).
    """

    rows = []

    for i, day in enumerate(pd.date_range(START, periods=days, freq="D")):
        spike = i == SPIKE_DAY or i == extra_spike_day
        rows.append((day, sku_a, "WH-BLR-01", 400 if spike else 50))

        if i < STOP_DAY:
            rows.append((day, sku_b, "WH-BLR-01", 50))

    return pd.DataFrame(
        rows, columns=["sale_date", "sku_id", "warehouse_id", "quantity_sold"]
    )


@pytest.fixture
def ledger_path(tmp_path):
    return tmp_path / "ledger.jsonl"


@pytest.fixture(scope="module")
def contract_validator():

    schema = json.loads(
        (EVENTS_DIR / "anomaly.sales.detected.v1.json").read_text(encoding="utf-8")
    )
    envelope = json.loads((EVENTS_DIR / "envelope.v1.json").read_text(encoding="utf-8"))
    registry = (
        Registry()
        .with_resource("envelope.v1.json", Resource.from_contents(envelope))
        .with_resource(envelope["$id"], Resource.from_contents(envelope))
    )

    return validator_for(schema)(
        schema, registry=registry, format_checker=FormatChecker()
    )


def run_once(sales, ledger_path, publisher=None, **kwargs):
    """One job run with its own ledger object, like a fresh process."""

    publisher = publisher or ListPublisher()
    ledger = PublishedLedger(ledger_path)

    try:
        summary = run(sales, publisher, ledger, **kwargs)
    finally:
        ledger.close()

    return summary, publisher


# ---------------------------------------------------------------------
# first run
# ---------------------------------------------------------------------


def test_first_run_publishes_one_event_per_incident(ledger_path):

    summary, publisher = run_once(make_sales(), ledger_path)

    published = {
        (e["payload"]["sku_id"], e["payload"]["date"]) for e in publisher.events
    }

    # The spike on SKU-000001, and the day SKU-000002 stopped selling.
    assert published == {
        ("SKU-000001", "2026-08-10"),
        ("SKU-000002", "2026-08-15"),
    }
    assert summary["incidents"] == 2
    assert summary["new"] == 2
    assert summary["already_published"] == 0


def test_a_run_of_flagged_days_gives_one_event(ledger_path):
    """SKU-000002 is flagged every day from the stop day on, but is one event."""

    from src.sales_anomaly import detect

    scores, _ = detect(make_sales())
    flagged = scores[(scores["product"] == "SKU-000002") & scores["is_anomaly"]]

    assert len(flagged) > 5

    _, publisher = run_once(make_sales(), ledger_path)

    assert sum(e["payload"]["sku_id"] == "SKU-000002" for e in publisher.events) == 1


def test_event_values_come_from_the_detector(ledger_path):

    _, publisher = run_once(make_sales(), ledger_path)
    spike = next(e for e in publisher.events if e["payload"]["sku_id"] == "SKU-000001")
    drop = next(e for e in publisher.events if e["payload"]["sku_id"] == "SKU-000002")

    assert spike["payload"]["actual_quantity"] == 400
    assert spike["payload"]["expected_quantity"] == 50
    assert spike["payload"]["score"] > 10
    assert spike["payload"]["severity"] == "high"

    assert drop["payload"]["actual_quantity"] == 0
    assert drop["payload"]["expected_quantity"] == 50
    assert drop["payload"]["score"] < 0
    assert drop["payload"]["severity"] == "high"


def test_every_published_event_matches_the_contract(ledger_path, contract_validator):

    _, publisher = run_once(make_sales(), ledger_path)

    assert publisher.events

    for event in publisher.events:
        assert [e.message for e in contract_validator.iter_errors(event)] == []


def test_no_anomalies_publishes_nothing(ledger_path):

    flat = make_sales()
    flat.loc[flat["quantity_sold"] == 400, "quantity_sold"] = 50
    flat = flat[flat["sale_date"] < pd.Timestamp(START) + pd.Timedelta(days=STOP_DAY)]

    summary, publisher = run_once(flat, ledger_path)

    assert publisher.events == []
    assert summary["incidents"] == 0


# ---------------------------------------------------------------------
# re-running
# ---------------------------------------------------------------------


def test_rerun_publishes_nothing_new(ledger_path):

    _first, first_publisher = run_once(make_sales(), ledger_path)
    second, second_publisher = run_once(make_sales(), ledger_path)

    assert len(first_publisher.events) == 2
    assert second_publisher.events == []
    assert second["new"] == 0
    assert second["already_published"] == 2


def test_rerun_in_the_same_process_publishes_nothing_new(ledger_path):

    ledger = PublishedLedger(ledger_path)
    publisher = ListPublisher()

    run(make_sales(), publisher, ledger)
    run(make_sales(), publisher, ledger)
    ledger.close()

    assert len(publisher.events) == 2


def test_only_the_new_anomaly_is_published_on_the_next_run(ledger_path):

    run_once(make_sales(days=90), ledger_path)

    summary, publisher = run_once(make_sales(days=100, extra_spike_day=90), ledger_path)

    assert [
        (e["payload"]["sku_id"], e["payload"]["date"]) for e in publisher.events
    ] == [("SKU-000001", "2026-08-30")]
    assert summary["already_published"] == 2
    assert summary["new"] == 1


def test_a_failed_delivery_is_retried_and_nothing_is_lost_or_doubled(ledger_path):

    with pytest.raises(RuntimeError):
        run_once(make_sales(), ledger_path, publisher=FailingPublisher(ok=1))

    # Only the delivered event is in the ledger.
    assert len(PublishedLedger(ledger_path)) == 1

    _, publisher = run_once(make_sales(), ledger_path)

    assert len(publisher.events) == 1


def test_ledger_survives_a_restart(ledger_path):

    ledger = PublishedLedger(ledger_path)
    ledger.add("SKU-000001|WH-BLR-01|2026-08-10", "id-1")
    ledger.close()

    again = PublishedLedger(ledger_path)

    assert "SKU-000001|WH-BLR-01|2026-08-10" in again
    assert "SKU-000001|WH-BLR-01|2026-08-11" not in again
    assert len(again) == 1

    again.close()


def test_ledger_ignores_blank_and_damaged_lines(ledger_path):

    ledger_path.write_text(
        '{"key": "a|b|2026-01-01", "event_id": "x"}\n\nnot json\n{"no_key": 1}\n',
        encoding="utf-8",
    )

    ledger = PublishedLedger(ledger_path)

    assert len(ledger) == 1
    assert "a|b|2026-01-01" in ledger

    ledger.close()


# ---------------------------------------------------------------------
# options
# ---------------------------------------------------------------------


def test_last_days_records_old_incidents_as_skipped_so_they_are_never_published(
    ledger_path,
):

    summary, publisher = run_once(make_sales(), ledger_path, last_days=10)

    assert publisher.events == []
    assert summary["outside_window"] == 2

    ledger = PublishedLedger(ledger_path)
    assert len(ledger) == 0
    assert ledger.was_skipped("SKU-000001|WH-BLR-01|2026-08-10")
    ledger.close()

    # A later run without the window does not publish the old history.
    later_summary, later = run_once(make_sales(), ledger_path)

    assert later.events == []
    assert later_summary["outside_window"] == 2
    assert later_summary["already_published"] == 0


def test_last_days_dry_run_records_nothing(ledger_path):

    run_once(make_sales(), ledger_path, last_days=10, dry_run=True)

    assert PublishedLedger(ledger_path).is_empty()


def test_last_days_keeps_recent_incidents(ledger_path):

    summary, publisher = run_once(
        make_sales(days=100, extra_spike_day=90), ledger_path, last_days=10
    )

    assert [e["payload"]["date"] for e in publisher.events] == ["2026-08-30"]
    assert summary["outside_window"] == 2


def test_dry_run_publishes_nothing_and_records_nothing(ledger_path):

    summary, publisher = run_once(make_sales(), ledger_path, dry_run=True)

    assert publisher.events == []
    assert summary["new"] == 2
    assert len(PublishedLedger(ledger_path)) == 0


def test_non_canonical_ids_are_counted_and_never_published(ledger_path):

    summary, publisher = run_once(
        make_sales(sku_a="PRD-10482", sku_b="PRD-10483"), ledger_path
    )

    assert publisher.events == []
    assert summary["skipped_ids"] == 2
    assert len(PublishedLedger(ledger_path)) == 0


# ---------------------------------------------------------------------
# command line
# ---------------------------------------------------------------------


def test_command_line_writes_events_once(tmp_path, capsys):

    csv = tmp_path / "sales.csv"
    make_sales().to_csv(csv, index=False)

    args = [
        "--input",
        str(csv),
        "--ledger",
        str(tmp_path / "ledger.jsonl"),
        "--no-kafka",
        "--events-log",
        str(tmp_path / "events.jsonl"),
        "--last-days",
        "30",
    ]

    main(args)
    first = capsys.readouterr().out

    main(args)
    second = capsys.readouterr().out

    lines = (tmp_path / "events.jsonl").read_text(encoding="utf-8").splitlines()

    assert len(lines) == 2
    assert "published: 2" in first
    assert "published: 0" in second
    assert "already published: 2" in second


def test_command_line_reads_a_folder_of_files(tmp_path):

    sales = make_sales()
    folder = tmp_path / "staging"
    folder.mkdir()

    cut = pd.Timestamp(START) + pd.Timedelta(days=45)
    sales[sales["sale_date"] < cut].to_csv(folder / "a.csv", index=False)
    sales[sales["sale_date"] >= cut].to_csv(folder / "b.csv", index=False)

    assert len(read_sales(folder)) == len(sales)

    main(
        [
            "--input",
            str(folder),
            "--ledger",
            str(tmp_path / "ledger.jsonl"),
            "--no-kafka",
            "--events-log",
            str(tmp_path / "events.jsonl"),
            "--last-days",
            "30",
        ]
    )

    assert (
        len((tmp_path / "events.jsonl").read_text(encoding="utf-8").splitlines()) == 2
    )


def test_empty_folder_is_an_error(tmp_path):

    with pytest.raises(FileNotFoundError):
        read_sales(tmp_path)


def test_command_line_dry_run_writes_nothing(tmp_path, capsys):

    csv = tmp_path / "sales.csv"
    make_sales().to_csv(csv, index=False)

    main(["--input", str(csv), "--ledger", str(tmp_path / "ledger.jsonl"), "--dry-run"])

    assert "would publish: 2" in capsys.readouterr().out
    assert (tmp_path / "ledger.jsonl").read_text(encoding="utf-8") == ""


def test_command_line_needs_somewhere_to_publish(tmp_path):

    csv = tmp_path / "sales.csv"
    make_sales().to_csv(csv, index=False)

    with pytest.raises(SystemExit):
        main(["--input", str(csv), "--ledger", str(tmp_path / "l.jsonl"), "--no-kafka"])


def test_key_in_ledger_matches_the_event(ledger_path):

    _, publisher = run_once(make_sales(), ledger_path)
    ledger = PublishedLedger(ledger_path)

    for event in publisher.events:
        p = event["payload"]
        assert anomaly_key(p["sku_id"], p["warehouse_id"], p["date"]) in ledger

    ledger.close()


# ---------------------------------------------------------------------
# a replay after a crash reuses the event_id
# ---------------------------------------------------------------------


def test_a_replay_after_a_crash_reuses_the_event_id(ledger_path, monkeypatch):
    """Delivered, then crashed before the ledger confirmed it: same event_id."""

    first = ListPublisher()
    ledger = PublishedLedger(ledger_path)

    def crash(key, event_id):
        raise RuntimeError("killed after delivery")

    monkeypatch.setattr(ledger, "add", crash)

    with pytest.raises(RuntimeError):
        run(make_sales(), first, ledger)

    ledger.close()

    _, second = run_once(make_sales(), ledger_path)

    assert first.events[0]["payload"] == second.events[0]["payload"]
    assert first.events[0]["event_id"] == second.events[0]["event_id"]

    # Confirmed now, so a third run publishes nothing.
    _, third = run_once(make_sales(), ledger_path)
    assert third.events == []


def test_a_failed_delivery_is_retried_with_the_same_event_id(ledger_path):

    class FailOnce(ListPublisher):
        def __init__(self):
            super().__init__()
            self.attempted = []

        def publish(self, event):

            self.attempted.append(event)

            if len(self.attempted) == 2:
                raise RuntimeError("broker down")

            super().publish(event)

    failing = FailOnce()

    with pytest.raises(RuntimeError):
        run_once(make_sales(), ledger_path, publisher=failing)

    failed_event = failing.attempted[1]

    _, retry = run_once(make_sales(), ledger_path)

    assert len(retry.events) == 1
    assert retry.events[0]["event_id"] == failed_event["event_id"]
    assert retry.events[0]["payload"] == failed_event["payload"]


def test_pending_lines_are_not_counted_as_published(ledger_path):

    ledger = PublishedLedger(ledger_path)
    ledger.reserve("SKU-000001|WH-BLR-01|2026-08-10", "id-1")
    ledger.close()

    again = PublishedLedger(ledger_path)

    assert "SKU-000001|WH-BLR-01|2026-08-10" not in again
    assert again.pending_event_id("SKU-000001|WH-BLR-01|2026-08-10") == "id-1"
    assert len(again) == 0
    assert not again.is_empty()

    again.add("SKU-000001|WH-BLR-01|2026-08-10", "id-1")

    assert again.pending_event_id("SKU-000001|WH-BLR-01|2026-08-10") is None

    again.close()

    third = PublishedLedger(ledger_path)

    assert "SKU-000001|WH-BLR-01|2026-08-10" in third
    assert third.pending_event_id("SKU-000001|WH-BLR-01|2026-08-10") is None

    third.close()


def test_old_ledger_lines_without_a_status_count_as_published(ledger_path):

    ledger_path.write_text(
        '{"key": "SKU-000001|WH-BLR-01|2026-08-10", "event_id": "old"}\n',
        encoding="utf-8",
    )

    ledger = PublishedLedger(ledger_path)

    assert "SKU-000001|WH-BLR-01|2026-08-10" in ledger
    assert len(ledger) == 1

    ledger.close()


# ---------------------------------------------------------------------
# the ledger path does not depend on the working directory
# ---------------------------------------------------------------------


def test_default_ledger_does_not_depend_on_the_working_directory(tmp_path, monkeypatch):

    import src.sales_anomaly_batch as batch

    monkeypatch.chdir(tmp_path)

    assert batch.DEFAULT_LEDGER.is_absolute()
    assert (
        batch.DEFAULT_LEDGER.parent
        == Path(batch.__file__).resolve().parents[1] / "output"
    )


# ---------------------------------------------------------------------
# the first run needs a choice
# ---------------------------------------------------------------------


def first_run_args(tmp_path, *extra):

    csv = tmp_path / "sales.csv"

    if not csv.exists():
        make_sales().to_csv(csv, index=False)

    return [
        "--input",
        str(csv),
        "--ledger",
        str(tmp_path / "ledger.jsonl"),
        "--no-kafka",
        "--events-log",
        str(tmp_path / "events.jsonl"),
        *extra,
    ]


def test_first_run_without_a_choice_is_refused_and_publishes_nothing(tmp_path):

    with pytest.raises(SystemExit):
        main(first_run_args(tmp_path))

    assert not (tmp_path / "events.jsonl").exists() or (
        (tmp_path / "events.jsonl").read_text(encoding="utf-8") == ""
    )
    assert PublishedLedger(tmp_path / "ledger.jsonl").is_empty()


def test_publish_all_sends_the_whole_history_on_purpose(tmp_path):

    main(first_run_args(tmp_path, "--publish-all"))

    lines = (tmp_path / "events.jsonl").read_text(encoding="utf-8").splitlines()

    assert len(lines) == 2


def test_later_runs_need_no_flag(tmp_path, capsys):

    main(first_run_args(tmp_path, "--last-days", "30"))
    capsys.readouterr()

    main(first_run_args(tmp_path))

    assert "published: 0" in capsys.readouterr().out


def test_dry_run_needs_no_flag(tmp_path, capsys):

    csv = tmp_path / "sales.csv"
    make_sales().to_csv(csv, index=False)

    main(["--input", str(csv), "--ledger", str(tmp_path / "l.jsonl"), "--dry-run"])

    assert "would publish: 2" in capsys.readouterr().out


def test_last_days_and_publish_all_together_are_refused(tmp_path):

    with pytest.raises(SystemExit):
        main(first_run_args(tmp_path, "--last-days", "7", "--publish-all"))


def test_second_run_after_last_days_publishes_only_new_incidents(tmp_path, capsys):

    main(first_run_args(tmp_path, "--last-days", "30"))
    capsys.readouterr()

    longer = tmp_path / "sales.csv"
    make_sales(days=100, extra_spike_day=90).to_csv(longer, index=False)

    main(first_run_args(tmp_path))

    out = capsys.readouterr().out
    lines = (tmp_path / "events.jsonl").read_text(encoding="utf-8").splitlines()

    assert "published: 1" in out
    assert len(lines) == 3


# ---------------------------------------------------------------------
# Kafka publisher: a slow message is not queued twice
# ---------------------------------------------------------------------


class FakeProducer:
    """Stands in for confluent_kafka.Producer. `script` has one step per flush."""

    script: ClassVar[list] = []
    instances: ClassVar[list] = []

    def __init__(self, config):
        self.config = config
        self.produced = []
        self._callbacks = []
        self.flushes = 0
        FakeProducer.instances.append(self)

    def produce(self, topic, key=None, value=None, on_delivery=None):
        self.produced.append((topic, key, value))
        self._callbacks.append(on_delivery)

    def flush(self, timeout):

        step = FakeProducer.script[self.flushes]
        self.flushes += 1

        if step == "timeout":
            return len(self._callbacks)

        error = None if step == "ok" else "broker said no"

        for callback in self._callbacks:
            callback(error, None)

        self._callbacks = []

        return 0


@pytest.fixture
def kafka(monkeypatch):

    FakeProducer.instances = []
    monkeypatch.setitem(
        sys.modules, "confluent_kafka", types.SimpleNamespace(Producer=FakeProducer)
    )
    monkeypatch.setattr("src.sales_anomaly_batch.time.sleep", lambda seconds: None)

    def make(*script):
        FakeProducer.script = list(script)
        return KafkaSalesEventPublisher("localhost:9092")

    return make


def an_event():

    from src.sales_anomaly_events import build_sales_anomaly_event

    return build_sales_anomaly_event(
        sku_id="SKU-000123",
        warehouse_id="WH-BLR-01",
        date="2026-11-14",
        expected_quantity=52,
        actual_quantity=214,
        score=8.2,
        severity="medium",
    )


def test_kafka_publish_sends_once_to_the_event_type_topic_with_the_series_key(kafka):

    publisher = kafka("ok")
    publisher.publish(an_event())

    producer = FakeProducer.instances[0]

    assert len(producer.produced) == 1
    assert producer.produced[0][0] == "anomaly.sales.detected"
    assert producer.produced[0][1] == "SKU-000123|WH-BLR-01"
    assert producer.config["enable.idempotence"] is True


def test_kafka_slow_acknowledgement_is_flushed_again_not_queued_twice(kafka):

    publisher = kafka("timeout", "ok")
    publisher.publish(an_event())

    producer = FakeProducer.instances[0]

    assert len(producer.produced) == 1
    assert producer.flushes == 2


def test_kafka_delivery_error_is_sent_again(kafka):

    publisher = kafka("error", "ok")
    publisher.publish(an_event())

    assert len(FakeProducer.instances[0].produced) == 2


def test_kafka_gives_up_after_three_attempts(kafka):

    publisher = kafka("error", "error", "error")

    with pytest.raises(RuntimeError, match="3 attempts"):
        publisher.publish(an_event())

    assert len(FakeProducer.instances[0].produced) == 3


def test_kafka_still_unacknowledged_at_the_end_is_an_error(kafka):

    publisher = kafka("timeout", "timeout", "timeout")

    with pytest.raises(RuntimeError, match="unacknowledged"):
        publisher.publish(an_event())

    assert len(FakeProducer.instances[0].produced) == 1


def test_fan_out_sends_to_every_publisher_in_order():

    a, b = ListPublisher(), ListPublisher()

    FanOutPublisher([a, b]).publish({"x": 1})

    assert a.events == b.events == [{"x": 1}]


# ---------------------------------------------------------------------
# MLflow tracking and the drift check (R15-K6)
# ---------------------------------------------------------------------


def noisy_sales(seed, days=120, mean=50, skus=8, shift_last_days=0, factor=3):
    """Synthetic sales with day-to-day noise; the last days can be scaled up."""

    rng = np.random.default_rng(seed)
    rows = []

    for i, day in enumerate(pd.date_range(START, periods=days, freq="D")):
        for sku in range(skus):
            quantity = int(rng.poisson(mean))

            if shift_last_days and i >= days - shift_last_days:
                quantity *= factor

            rows.append((day, f"SKU-{sku + 1:06d}", "WH-BLR-01", quantity))

    return pd.DataFrame(
        rows, columns=["sale_date", "sku_id", "warehouse_id", "quantity_sold"]
    )


def drift_run(ledger_path, sales, reference, publisher=None, **kwargs):

    publisher = publisher or ListPublisher()
    ledger = PublishedLedger(ledger_path)

    try:
        summary = run(
            sales, publisher, ledger, reference=reference, last_days=30, **kwargs
        )
    finally:
        ledger.close()

    return summary, publisher


def test_shifted_load_logs_a_drift_warning_and_the_job_still_publishes(
    ledger_path, caplog
):

    reference = noisy_sales(seed=1)
    shifted = noisy_sales(seed=2, shift_last_days=28)

    with caplog.at_level(logging.INFO):
        summary, publisher = drift_run(ledger_path, shifted, reference)

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]

    assert summary["drift"].alert
    assert any("DATA DRIFT" in r.getMessage() for r in warnings)
    assert summary["new"] > 0
    assert len(publisher.events) == summary["new"]


def test_the_same_data_gives_no_drift_warning(ledger_path, caplog):

    with caplog.at_level(logging.INFO):
        summary, _ = drift_run(ledger_path, noisy_sales(seed=2), noisy_sales(seed=1))

    assert not summary["drift"].alert
    assert not any("DATA DRIFT" in r.getMessage() for r in caplog.records)


def test_no_reference_means_no_drift_check(ledger_path):

    summary, _ = run_once(make_sales(), ledger_path, last_days=30)

    assert summary["drift"] is None


def test_a_broken_drift_check_does_not_stop_the_job(ledger_path, monkeypatch, caplog):

    def broken(*args, **kwargs):
        raise RuntimeError("evidently exploded")

    monkeypatch.setattr("src.sales_anomaly_batch.check_drift", broken)

    with caplog.at_level(logging.INFO):
        summary, publisher = drift_run(ledger_path, make_sales(), noisy_sales(seed=1))

    assert summary["drift"] is None
    assert len(publisher.events) == 2
    assert any("Drift check skipped" in r.getMessage() for r in caplog.records)


def test_summary_carries_the_data_range_and_severity_counts(ledger_path):

    summary, _ = run_once(make_sales(), ledger_path)

    assert summary["data_start"] == START
    assert summary["data_end"] == "2026-08-29"
    assert summary["severity_counts"]["high"] >= 2
    assert set(summary["severity_counts"]) == {"high", "medium", "low"}


def csv_args(tmp_path, *extra):

    csv = tmp_path / "sales.csv"
    noisy_sales(seed=2, shift_last_days=28).to_csv(csv, index=False)

    return [
        "--input",
        str(csv),
        "--ledger",
        str(tmp_path / "ledger.jsonl"),
        "--no-kafka",
        "--events-log",
        str(tmp_path / "events.jsonl"),
        "--last-days",
        "30",
        *extra,
    ]


def test_command_line_with_a_reference_reports_the_drift(tmp_path, capsys):

    reference = tmp_path / "setup.csv"
    noisy_sales(seed=1).to_csv(reference, index=False)

    main(csv_args(tmp_path, "--reference", str(reference)))

    assert "drift: ALERT" in capsys.readouterr().out


def test_command_line_without_a_reference_says_not_checked(tmp_path, capsys):

    main(csv_args(tmp_path))

    assert "drift: not checked" in capsys.readouterr().out


def test_an_unreadable_reference_does_not_stop_the_job(tmp_path, capsys):

    main(csv_args(tmp_path, "--reference", str(tmp_path / "missing.csv")))

    out = capsys.readouterr().out

    assert "drift: not checked" in out
    assert len((tmp_path / "events.jsonl").read_text(encoding="utf-8").splitlines()) > 0


@pytest.fixture
def logged(monkeypatch):
    """Replace safe_log_run in the batch module and record what it is given."""

    mock = MagicMock()
    monkeypatch.setattr("src.sales_anomaly_batch.safe_log_run", mock)

    return mock


def test_the_run_is_logged_with_drift_and_the_report(tmp_path, logged, monkeypatch):

    monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://mlflow.test:5000")
    monkeypatch.setattr(
        "src.sales_anomaly_batch.registered_setup",
        lambda: {"version": 4, "precision": 0.9, "recall": 0.8},
    )

    reference = tmp_path / "setup.csv"
    noisy_sales(seed=1).to_csv(reference, index=False)

    main(csv_args(tmp_path, "--reference", str(reference)))

    args, kwargs = logged.call_args

    assert args == ("sales-anomaly-batch",)
    assert kwargs["tags"]["run_kind"] == "batch"
    assert kwargs["tags"]["drift_alert"] == "true"
    assert kwargs["tags"]["setup_model_version"] == "4"
    assert kwargs["metrics"]["drift_alert"] == 1.0
    assert kwargs["metrics"]["setup_precision"] == 0.9
    assert kwargs["metrics"]["setup_recall"] == 0.8
    assert "drift_report.html" in kwargs["texts"]
    assert kwargs["data_start"] == START
    assert set(kwargs["severities"]) == {"high", "medium", "low"}
    assert kwargs["params"]["reference"] == str(reference)


def test_a_setup_that_is_not_registered_is_tagged_so(tmp_path, logged, monkeypatch):

    monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://mlflow.test:5000")
    monkeypatch.setattr("src.sales_anomaly_batch.registered_setup", lambda: None)

    main(csv_args(tmp_path))

    kwargs = logged.call_args.kwargs

    assert kwargs["tags"]["setup_model_version"] == "not registered"
    assert kwargs["tags"]["drift_alert"] == "not checked"
    assert kwargs["texts"] is None


def test_a_dry_run_is_not_logged(tmp_path, logged):

    csv = tmp_path / "sales.csv"
    make_sales().to_csv(csv, index=False)

    main(["--input", str(csv), "--ledger", str(tmp_path / "l.jsonl"), "--dry-run"])

    logged.assert_not_called()


def test_mlflow_being_down_does_not_stop_the_job(tmp_path, monkeypatch, capsys):

    monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://mlflow.test:5000")

    def down(*args, **kwargs):
        raise ConnectionError("mlflow is down")

    monkeypatch.setattr("mlflow.set_tracking_uri", down)
    monkeypatch.setattr("src.sales_anomaly_batch.registered_setup", down)

    main(csv_args(tmp_path))

    assert "published:" in capsys.readouterr().out
    assert len((tmp_path / "events.jsonl").read_text(encoding="utf-8").splitlines()) > 0


def test_a_failed_lookup_is_tagged_as_such_not_as_unregistered(
    tmp_path, logged, monkeypatch
):

    monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://mlflow.test:5000")

    def down():
        raise ConnectionError("mlflow is down")

    monkeypatch.setattr("src.sales_anomaly_batch.registered_setup", down)

    main(csv_args(tmp_path))

    assert logged.call_args.kwargs["tags"]["setup_model_version"] == "lookup failed"
