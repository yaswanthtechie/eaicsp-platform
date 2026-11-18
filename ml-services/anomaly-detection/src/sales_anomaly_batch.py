"""
Batch job: run sales anomaly detection over the staging sales files and
publish one anomaly.sales.detected event per new anomaly incident.

Only run_start days are published (the first day of an incident), so a
product that stops selling gives one event, not one a day for five weeks.

Re-running is safe. Every anomaly is recorded in a ledger file
(sku_id|warehouse_id|date); a run skips anything already in it.

The ledger line "pending" (with the event_id) is written BEFORE the event is
published and the confirmed line AFTER delivery. If the job dies in between,
the next run publishes the same anomaly again with the SAME event_id, so
consumers de-duplicate on event_id like on every other topic (at-least-once
delivery, never a second alert).

Every run is also logged to MLflow (parameters, thresholds, data range, anomaly
count by severity, precision and recall of the registered setup) when
MLFLOW_TRACKING_URI is set, and with --reference (the setup window: the clean
data the thresholds were calibrated on) an Evidently drift report compares it
with the latest 28 days of the input. Drift above the configured threshold is
logged as a warning; it never stops the job, and neither does MLflow being
down.

The first run needs a choice: --last-days N publishes only the last N days
and records older incidents as skipped (they are never published later), or
--publish-all sends the whole history on purpose.

Run (from anywhere; the ledger path does not depend on the working directory):
    python -m src.sales_anomaly_batch --input <staging sales file or folder> --last-days 7
    python -m src.sales_anomaly_batch --input <sales.csv> --last-days 7 --reference <clean setup sales.csv>
    python -m src.sales_anomaly_batch --input <sales.csv> --dry-run
    python -m src.sales_anomaly_batch --input <sales.csv> --no-kafka --events-log output/sales_events.jsonl --last-days 7

Kafka comes from KAFKA_BOOTSTRAP_SERVERS (default localhost:9092). The topic
is the event type, anomaly.sales.detected, as for every other event.
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
from .sales_anomaly_drift import check_drift, latest_window
from .sales_anomaly_events import (
    EVENT_TYPE,
    SKU_PATTERN,
    WAREHOUSE_PATTERN,
    anomaly_key,
    build_sales_anomaly_event,
    event_key,
)
from .sales_anomaly_tracking import (
    date_range,
    registered_setup,
    safe_log_run,
    severity_counts,
    tracking_uri,
)


log = logging.getLogger("sales_anomaly_batch")

# Resolved from this file, not the working directory, so every run finds the
# same ledger wherever the job is started from.
SERVICE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEDGER = SERVICE_ROOT / "output" / "sales_anomaly_published.jsonl"


class PublishedLedger:
    """
    Append-only record of every anomaly the job has dealt with.

    published: delivered and confirmed.
    skipped:   older than --last-days on a run, never to be published.
    pending:   event_id reserved, delivery not confirmed (job died or the
               broker failed); the next run re-sends it with the same event_id.

    A line without a status is a confirmed one.
    """

    def __init__(self, path):

        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._seen = set()
        self._skipped = set()
        self._pending = {}

        if self._path.exists():
            with open(self._path, encoding="utf-8") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    try:
                        entry = json.loads(line)
                        key = entry["key"]
                        status = entry.get("status")
                        if status == "pending":
                            self._pending[key] = entry["event_id"]
                        elif status == "skipped":
                            self._skipped.add(key)
                        else:
                            self._seen.add(key)
                    except (ValueError, KeyError, TypeError, AttributeError):
                        continue

        for key in self._seen | self._skipped:
            self._pending.pop(key, None)

        self._file = open(self._path, "a", encoding="utf-8")

    def __contains__(self, key):
        return key in self._seen or key in self._skipped

    def __len__(self):
        """Number of confirmed (published) anomalies."""
        return len(self._seen)

    def is_empty(self):
        return not (self._seen or self._skipped or self._pending)

    def was_skipped(self, key):
        return key in self._skipped

    def pending_event_id(self, key):
        """event_id of an earlier run that did not confirm delivery."""
        return self._pending.get(key)

    def reserve(self, key, event_id):
        """Record the event_id before publishing, so a replay reuses it."""

        self._pending[key] = event_id
        self._write({"key": key, "event_id": event_id, "status": "pending"})

    def add(self, key, event_id):
        """Confirm delivery."""

        self._seen.add(key)
        self._pending.pop(key, None)
        self._write({"key": key, "event_id": event_id})

    def skip(self, key):
        """Record an incident that is too old to publish, now or later."""

        self._skipped.add(key)
        self._pending.pop(key, None)
        self._write({"key": key, "status": "skipped"})

    def _write(self, entry):

        self._file.write(json.dumps(entry) + "\n")
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

    def __init__(self, bootstrap_servers, topic=EVENT_TYPE, flush_timeout=10.0):

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
        """
        Send one event and wait for the broker to acknowledge it.

        A message that is only slow stays in the producer queue, so we flush
        again instead of queueing a second copy. We produce again only after
        the delivery callback reported an error.
        """

        errors = []

        def on_delivery(err, msg):
            if err is not None:
                errors.append(str(err))

        def send():
            self._producer.produce(
                self._topic,
                key=event_key(event),
                value=json.dumps(event).encode("utf-8"),
                on_delivery=on_delivery,
            )

        send()
        last_error = None

        for attempt in range(1, attempts + 1):

            remaining = self._producer.flush(self._timeout)

            if remaining == 0 and not errors:
                return

            if errors:
                last_error = errors[-1]
                errors.clear()

                if attempt < attempts:
                    time.sleep(backoff_seconds * attempt)
                    send()
            else:
                last_error = f"{remaining} message(s) still unacknowledged"

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


def _check_drift(reference, scores):
    """Compare the setup window with the latest load. Never raises."""

    try:
        reference_scores, _ = detect(reference)
        result = check_drift(reference_scores, latest_window(scores))
    except Exception as error:
        log.warning("Drift check skipped: %s", error)
        return None

    if result.alert:
        log.warning("DATA DRIFT: %s", result.message())
    else:
        log.info("No data drift: %s", result.message())

    return result


def _log_to_mlflow(args, summary):
    """Log this run to MLflow. Never raises."""

    drift = summary["drift"]

    metrics = {
        "incidents_found": summary["incidents"],
        "published": summary["new"],
        "already_published": summary["already_published"],
        "outside_window": summary["outside_window"],
        "skipped_ids": summary["skipped_ids"],
    }
    tags = {
        "run_kind": "batch",
        "drift_alert": "not checked" if drift is None else str(drift.alert).lower(),
    }

    if drift is not None:
        metrics.update(drift.metrics())

    if tracking_uri() is not None:
        try:
            setup = registered_setup()
        except Exception as error:
            log.warning("Could not look up the registered setup: %s", error)
            setup = None

        if setup is None:
            tags["setup_model_version"] = "not registered"
            log.warning(
                "The thresholds in force are not registered in MLflow; run "
                "python -m src.sales_anomaly_eval --register."
            )
        else:
            tags["setup_model_version"] = str(setup["version"])
            metrics["setup_precision"] = setup["precision"]
            metrics["setup_recall"] = setup["recall"]

    safe_log_run(
        "sales-anomaly-batch",
        params={
            "input": str(args.input),
            "reference": args.reference or "none",
            "last_days": args.last_days,
            "publish_all": args.publish_all,
        },
        data_start=summary["data_start"],
        data_end=summary["data_end"],
        severities=summary["severity_counts"],
        metrics=metrics,
        texts={"drift_report.html": drift.html} if drift is not None else None,
        tags=tags,
    )


def run(sales, publisher, ledger, last_days=None, dry_run=False, reference=None):
    """
    Detect anomalies in sales and publish the new ones.

    Returns a summary dict: incidents (run starts found), new (published, or
    that would be in a dry run), already_published, outside_window (older
    than last_days, now or on an earlier run) and skipped_ids (not canonical
    ids, never published), plus data_start, data_end, severity_counts (flagged
    days by severity) and drift (a DriftResult, or None when there is no
    reference or the check could not run).

    reference is a sales frame of the setup window. The drift check only warns;
    nothing in it can stop events from being published.
    """

    scores, _ = detect(sales)
    anomalies = scores[scores["is_anomaly"].astype(bool)]
    incidents = anomalies[anomalies["run_start"].astype(bool)]

    data_start, data_end = date_range(scores["date"])

    summary = {
        "incidents": len(incidents),
        "new": 0,
        "already_published": 0,
        "outside_window": 0,
        "skipped_ids": 0,
        "data_start": data_start,
        "data_end": data_end,
        "severity_counts": severity_counts(anomalies),
        "drift": None,
    }

    if reference is not None:
        summary["drift"] = _check_drift(reference, scores)

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

        key = anomaly_key(row.product, row.warehouse, row.date)

        if key in ledger:
            if ledger.was_skipped(key):
                summary["outside_window"] += 1
            else:
                summary["already_published"] += 1
            continue

        if cutoff is not None and row.date < cutoff:
            summary["outside_window"] += 1

            if not dry_run:
                ledger.skip(key)

            continue

        event = build_sales_anomaly_event(
            sku_id=row.product,
            warehouse_id=row.warehouse,
            date=row.date,
            expected_quantity=row.expected,
            actual_quantity=row.quantity,
            score=row.score,
            severity=row.severity,
            # A replay after a crash re-sends the same event_id, so consumers
            # de-duplicate on event_id as the blueprint says.
            event_id=ledger.pending_event_id(key),
        )

        if not dry_run:
            ledger.reserve(key, event["event_id"])
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
        help="Only publish incidents from the last N days of data; older ones "
        "are recorded as skipped and never published later. Needed on the "
        "first run, so history is not published as live alerts.",
    )
    parser.add_argument(
        "--publish-all",
        action="store_true",
        help="First run only: publish the whole history on purpose.",
    )
    parser.add_argument(
        "--reference",
        default=None,
        help="Sales file or folder of the setup window (the clean data the "
        "thresholds were calibrated on). Enables the drift check against the "
        "latest 28 days of --input.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-kafka", action="store_true")
    parser.add_argument("--events-log", default=None)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO)

    if args.last_days is not None and args.last_days < 1:
        parser.error("--last-days must be at least 1")

    if args.last_days is not None and args.publish_all:
        parser.error("Use either --last-days or --publish-all, not both.")

    publishers = []

    if not args.dry_run:

        if not args.no_kafka:
            publishers.append(
                KafkaSalesEventPublisher(
                    os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
                    EVENT_TYPE,
                )
            )

        if args.events_log:
            publishers.append(JsonlEventLog(args.events_log))

        if not publishers:
            parser.error("Nothing to publish to: drop --no-kafka or set --events-log.")

    ledger = PublishedLedger(args.ledger)

    if (
        ledger.is_empty()
        and args.last_days is None
        and not args.publish_all
        and not args.dry_run
    ):
        ledger.close()
        for publisher in publishers:
            publisher.close()
        parser.error(
            "The ledger is empty, so this would publish the whole history as "
            "live alerts. Pass --last-days N (recommended) or --publish-all."
        )

    reference = None

    if args.reference:
        try:
            reference = read_sales(args.reference)
        except Exception as error:
            log.warning("Drift check skipped: cannot read --reference: %s", error)

    try:
        summary = run(
            read_sales(args.input),
            FanOutPublisher(publishers),
            ledger,
            last_days=args.last_days,
            dry_run=args.dry_run,
            reference=reference,
        )
    finally:
        ledger.close()
        for publisher in publishers:
            publisher.close()

    if not args.dry_run:
        _log_to_mlflow(args, summary)

    drift = summary["drift"]
    drift_label = "not checked" if drift is None else ("ALERT" if drift.alert else "ok")

    label = "would publish" if args.dry_run else "published"

    print(
        f"{datetime.now(UTC):%Y-%m-%d %H:%M:%S} UTC  "
        f"incidents found: {summary['incidents']}  "
        f"{label}: {summary['new']}  "
        f"already published: {summary['already_published']}  "
        f"older than --last-days: {summary['outside_window']}  "
        f"not canonical ids: {summary['skipped_ids']}  "
        f"drift: {drift_label}"
    )


if __name__ == "__main__":
    main()