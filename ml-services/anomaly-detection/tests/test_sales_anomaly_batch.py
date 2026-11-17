"""
The sales anomaly batch job: one event per new incident, and a re-run
publishes nothing new.
"""

import json
from pathlib import Path

import pandas as pd
import pytest
from jsonschema import FormatChecker
from jsonschema.validators import validator_for
from referencing import Registry, Resource

from src.sales_anomaly_batch import PublishedLedger, main, read_sales, run
from src.sales_anomaly_events import anomaly_key

REPO_ROOT = Path(__file__).resolve().parents[3]
EVENTS_DIR = REPO_ROOT / "contracts" / "events"

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

    return validator_for(schema)(schema, registry=registry, format_checker=FormatChecker())


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

    published = {(e["payload"]["sku_id"], e["payload"]["date"]) for e in publisher.events}

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

    first, first_publisher = run_once(make_sales(), ledger_path)
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

    assert [(e["payload"]["sku_id"], e["payload"]["date"]) for e in publisher.events] == [
        ("SKU-000001", "2026-08-30")
    ]
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


def test_last_days_leaves_old_incidents_out_and_they_are_not_recorded(ledger_path):

    summary, publisher = run_once(make_sales(), ledger_path, last_days=10)

    assert publisher.events == []
    assert summary["outside_window"] == 2
    assert len(PublishedLedger(ledger_path)) == 0

    # Without the window they are still new.
    _, later = run_once(make_sales(), ledger_path)

    assert len(later.events) == 2


def test_last_days_keeps_recent_incidents(ledger_path):

    summary, publisher = run_once(make_sales(days=100, extra_spike_day=90), ledger_path, last_days=10)

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
        "--input", str(csv),
        "--ledger", str(tmp_path / "ledger.jsonl"),
        "--no-kafka",
        "--events-log", str(tmp_path / "events.jsonl"),
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

    main([
        "--input", str(folder),
        "--ledger", str(tmp_path / "ledger.jsonl"),
        "--no-kafka",
        "--events-log", str(tmp_path / "events.jsonl"),
    ])

    assert len((tmp_path / "events.jsonl").read_text(encoding="utf-8").splitlines()) == 2


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