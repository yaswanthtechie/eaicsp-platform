"""
Batch job: run sales anomaly detection over the staging sales files and
publish one anomaly.sales.detected event per new anomaly incident.

Only run_start days are published (the first day of an incident), so a
product that stops selling gives one event, not one a day for five weeks.

Re-running is safe. Every published anomaly is written to a ledger file
(sku_id|warehouse_id|date); a run skips anything already in the ledger.
The ledger entry is written after the event was delivered, so a crash between
the two can re-publish one event on the next run (at-least-once). Consumers
de-duplicate on (sku_id, warehouse_id, date), as the contract says.

Run (from ml-services/anomaly-detection):
    python -m src.sales_anomaly_batch --input ../../data-platform/etl/data/staging/sales
    python -m src.sales_anomaly_batch --input <sales.csv> --dry-run
    python -m src.sales_anomaly_batch --input <sales.csv> --no-kafka --events-log output/sales_events.jsonl

Kafka settings come from KAFKA_BOOTSTRAP_SERVERS (default localhost:9092) and
KAFKA_SALES_ANOMALY_TOPIC (default anomaly.sales.detected).
"""

import argparse
from datetime import UTC, datetime, timedelta
import json
import logging
import os
from pathlib import Path
import time

import pandas as pd

from .sales_anomaly import detect
from .sales_anomaly_events import (
    EVENT_TYPE,
    SKU_PATTERN,
    WAREHOUSE_PATTERN,
    anomaly_key,
    build_sales_anomaly_event,
    event_key,
)


log = logging.getLogger("sales_anomaly_batch")

DEFAULT_LEDGER = Path("output") / "sales_anomaly_published.jsonl"


class PublishedLedger:
    """Append-only record of the anomalies already published."""

    def __init__(self, path):

        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._seen = set()

        if self._path.exists():
            with open(self._path, encoding="utf-8") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    try:
                        self._seen.add(json.loads(line)["key"])
                    except (ValueError, KeyError, TypeError):
                        continue

        self._file = open(self._path, "a", encoding="utf-8")

    def __contains__(self, key):
        return key in self._seen

    def __len__(self):
        return len(self._seen)

    def add(self, key, event_id):

        self._seen.add(key)
        self._file.write(json.dumps({"key": key, "event_id": event_id}) + "\n")
        self._file.flush()
        os.fsync(self._file.fileno())

    def close(self):
        self._file.close()


class JsonlEventLog:
    """Writes events to a JSON-lines file instead of Kafka."""

    def __init__(self, path):

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._file = open(path, "a", encoding="utf-8")

    def publish(self, event):
        self._file.write(json.dumps(event) + "\n")
        self._file.flush()

    def close(self):
        self._file.close()


class KafkaSalesEventPublisher:

    def __init__(self, bootstrap_servers, topic, flush_timeout=10.0):

        from confluent_kafka import Producer

        self._producer = Producer(
            {
                "bootstrap.servers": bootstrap_servers,
                "enable.idempotence": True,
            }
        )
        self._topic = topic
        self._timeout = flush_timeout

    def publish(self, event, attempts=3, backoff_seconds=2.0):

        last_error = None

        for attempt in range(1, attempts + 1):

            errors = []

            def on_delivery(err, msg):
                if err is not None:
                    errors.append(str(err))

            self._producer.produce(
                self._topic,
                key=event_key(event),
                value=json.dumps(event).encode("utf-8"),
                on_delivery=on_delivery,
            )

            remaining = self._producer.flush(self._timeout)

            if not remaining and not errors:
                return

            last_error = f"{remaining} unacknowledged, {errors}"
            time.sleep(backoff_seconds * attempt)

        raise RuntimeError(
            f"Event delivery failed after {attempts} attempts: {last_error}"
        )

    def close(self):
        self._producer.flush(self._timeout)


class FanOutPublisher:
    """Sends each event to every publisher, in order."""

    def __init__(self, publishers):
        self._publishers = list(publishers)

    def publish(self, event):
        for publisher in self._publishers:
            publisher.publish(event)


def read_sales(path):
    """Read one sales CSV, or every CSV in a folder, as text."""

    path = Path(path)

    if path.is_dir():
        files = sorted(path.glob("*.csv"))

        if not files:
            raise FileNotFoundError(f"No .csv files in {path}")

        return pd.concat(
            [pd.read_csv(f, dtype=str) for f in files], ignore_index=True
        )

    return pd.read_csv(path, dtype=str)


def run(sales, publisher, ledger, last_days=None, dry_run=False):
    """
    Detect anomalies in sales and publish the new ones.

    Returns a summary dict: incidents (run starts found), new (published, or
    that would be in a dry run), already_published, outside_window (older
    than last_days) and skipped_ids (not canonical ids, never published).
    """

    scores, _ = detect(sales)
    anomalies = scores[scores["is_anomaly"].astype(bool)]
    incidents = anomalies[anomalies["run_start"].astype(bool)]

    summary = {
        "incidents": len(incidents),
        "new": 0,
        "already_published": 0,
        "outside_window": 0,
        "skipped_ids": 0,
    }

    if incidents.empty:
        return summary

    cutoff = None

    if last_days is not None:
        cutoff = scores["date"].max() - timedelta(days=last_days - 1)

    for row in incidents.sort_values(["date", "product", "warehouse"]).itertuples():

        if not (
            SKU_PATTERN.fullmatch(str(row.product))
            and WAREHOUSE_PATTERN.fullmatch(str(row.warehouse))
        ):
            log.warning(
                "Not published: %s / %s is not a canonical sku_id / warehouse_id.",
                row.product,
                row.warehouse,
            )
            summary["skipped_ids"] += 1
            continue

        if cutoff is not None and row.date < cutoff:
            summary["outside_window"] += 1
            continue

        key = anomaly_key(row.product, row.warehouse, row.date)

        if key in ledger:
            summary["already_published"] += 1
            continue

        event = build_sales_anomaly_event(
            sku_id=row.product,
            warehouse_id=row.warehouse,
            date=row.date,
            expected_quantity=row.expected,
            actual_quantity=row.quantity,
            score=row.score,
            severity=row.severity,
        )

        if not dry_run:
            publisher.publish(event)
            ledger.add(key, event["event_id"])

        summary["new"] += 1

    return summary


def main(argv=None):

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        required=True,
        help="Staging sales CSV, or a folder of CSV files.",
    )
    parser.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    parser.add_argument(
        "--last-days",
        type=int,
        default=None,
        help="Only publish incidents from the last N days of data "
        "(use on the first run so history is not published as alerts).",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-kafka", action="store_true")
    parser.add_argument("--events-log", default=None)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO)

    if args.last_days is not None and args.last_days < 1:
        parser.error("--last-days must be at least 1")

    publishers = []

    if not args.dry_run:

        if not args.no_kafka:
            publishers.append(
                KafkaSalesEventPublisher(
                    os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
                    os.environ.get("KAFKA_SALES_ANOMALY_TOPIC", EVENT_TYPE),
                )
            )

        if args.events_log:
            publishers.append(JsonlEventLog(args.events_log))

        if not publishers:
            parser.error("Nothing to publish to: drop --no-kafka or set --events-log.")

    ledger = PublishedLedger(args.ledger)

    try:
        summary = run(
            read_sales(args.input),
            FanOutPublisher(publishers),
            ledger,
            last_days=args.last_days,
            dry_run=args.dry_run,
        )
    finally:
        ledger.close()
        for publisher in publishers:
            publisher.close()

    label = "would publish" if args.dry_run else "published"

    print(
        f"{datetime.now(UTC):%Y-%m-%d %H:%M:%S} UTC  "
        f"incidents found: {summary['incidents']}  "
        f"{label}: {summary['new']}  "
        f"already published: {summary['already_published']}  "
        f"older than --last-days: {summary['outside_window']}  "
        f"not canonical ids: {summary['skipped_ids']}"
    )


if __name__ == "__main__":
    main()