"""Live contract monitor (R15-T5).

Reads every topic in the event catalog (blueprint section 5) from the shared
Kafka, checks each message against contracts/events/<event_type>.v<N>.json,
and prints a Markdown report of violations grouped by producer.

Read-only: it uses its own throwaway consumer group, assigns partitions
directly and never commits, so it cannot move any real consumer's offsets.

    python live_monitor.py --bootstrap localhost:29092
"""
import argparse
import json
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from jsonschema import FormatChecker
from jsonschema.validators import validator_for

from contract_check import FILENAME_RE, NON_EVENT_FILES, _load_registry

EVENTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "events")

# Blueprint section 5: topic -> owning service. Topic name == event_type.
CATALOG = {
    "inventory.po.approved": "Inventory",
    "inventory.goods.received": "Inventory",
    "inventory.stock.low": "Inventory",
    "supplierportal.po.acknowledged": "Supplier Portal",
    "supplierportal.shipment.dispatched": "Supplier Portal",
    "eta.shipment.predicted": "ETA",
    "forecast.batch.completed": "Forecasting",
    "compliance.supplier.status_changed": "Compliance",
    "supplierrisk.score.changed": "Supplier Risk",
    "iot.anomaly.detected": "Anomaly",
    "data.pipeline.completed": "ETL",
}

UNKNOWN_PRODUCER = "(unknown producer)"
MAX_SHOWN_PER_PRODUCER = 20


def load_validators(events_dir=EVENTS_DIR):
    """Return {(event_type, version): validator} for every event schema."""
    registry = _load_registry(events_dir)
    validators = {}
    for filename in sorted(os.listdir(events_dir)):
        match = FILENAME_RE.match(filename)
        if match is None or filename in NON_EVENT_FILES:
            continue
        with open(os.path.join(events_dir, filename), encoding="utf-8") as f:
            schema = json.load(f)
        validator_class = validator_for(schema)
        validators[(match.group("event_type"), int(match.group("version")))] = (
            validator_class(schema, registry=registry, format_checker=FormatChecker())
        )
    return validators


@dataclass
class CheckResult:
    producer: str
    event_id: str
    problems: list


def check_message(topic, value, validators):
    """Check one raw Kafka message value from `topic` against its contract."""
    if value is None:
        return CheckResult(UNKNOWN_PRODUCER, "-", ["empty message value (tombstone)"])

    try:
        event = json.loads(value)
    except (UnicodeDecodeError, ValueError) as exc:
        return CheckResult(UNKNOWN_PRODUCER, "-", [f"not valid JSON: {exc}"])

    if not isinstance(event, dict):
        return CheckResult(UNKNOWN_PRODUCER, "-", ["message is not a JSON object"])

    producer = event.get("producer")
    producer = producer if isinstance(producer, str) and producer else UNKNOWN_PRODUCER
    event_id = str(event.get("event_id", "-"))
    problems = []

    if event.get("event_type") != topic:
        problems.append(
            f"event_type {event.get('event_type')!r} does not match topic {topic!r}"
        )

    version = event.get("event_version")
    validator = None
    if isinstance(version, int) and not isinstance(version, bool):
        validator = validators.get((topic, version))
    if validator is None:
        problems.append(f"no schema contracts/events/{topic}.v{version}.json")
        return CheckResult(producer, event_id, problems)

    for error in sorted(validator.iter_errors(event), key=lambda e: [str(p) for p in e.path]):
        path = "->".join(str(p) for p in error.path) or "root"
        problems.append(f"{path}: {error.message}")

    return CheckResult(producer, event_id, problems)


@dataclass
class Report:
    messages: dict = field(default_factory=lambda: defaultdict(int))
    bad: dict = field(default_factory=lambda: defaultdict(int))
    violations: dict = field(default_factory=lambda: defaultdict(list))
    empty_topics: list = field(default_factory=list)
    missing_topics: list = field(default_factory=list)
    unfinished_topics: list = field(default_factory=list)

    def add(self, topic, partition, offset, result):
        self.messages[result.producer] += 1
        if result.problems:
            self.bad[result.producer] += 1
            self.violations[result.producer].append(
                (topic, partition, offset, result.event_id, result.problems)
            )

    @property
    def total_bad(self):
        return sum(self.bad.values())

    def to_markdown(self, bootstrap, validators):
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        lines = [
            f"## Live contract monitor: {now}",
            "",
            f"Kafka `{bootstrap}`. Messages checked: {sum(self.messages.values())}. "
            f"Violations: {self.total_bad}.",
            "",
            "| Producer | Messages | Violations |",
            "|---|---|---|",
        ]
        for producer in sorted(self.messages):
            lines.append(f"| {producer} | {self.messages[producer]} | {self.bad[producer]} |")

        for producer in sorted(self.violations):
            shown = self.violations[producer][:MAX_SHOWN_PER_PRODUCER]
            lines += ["", f"### {producer}", ""]
            for topic, partition, offset, event_id, problems in shown:
                lines.append(
                    f"- `{topic}` partition {partition} offset {offset}, "
                    f"event_id `{event_id}`: " + "; ".join(problems)
                )
            hidden = len(self.violations[producer]) - len(shown)
            if hidden > 0:
                lines.append(f"- ...and {hidden} more")

        schema_topics = {event_type for event_type, _ in validators}
        no_schema = [t for t in CATALOG if t not in schema_topics]
        sections = [
            ("Catalog topics with no schema in contracts/events/", no_schema),
            ("Topics that do not exist yet", self.missing_topics),
            ("Topics with no messages yet", self.empty_topics),
            ("Topics not read to the end (timed out)", self.unfinished_topics),
        ]
        for title, topics in sections:
            if topics:
                lines += ["", f"### {title}", ""]
                lines += [f"- `{t}` ({CATALOG.get(t, '?')})" for t in topics]

        return "\n".join(lines) + "\n"


def read_topic(consumer, topic, timeout, status):
    """Yield every message currently in `topic`, from the earliest offset up to
    the end offset at the moment we start. Sets status[0] to one of
    "missing", "empty", "done" or "timed_out"."""
    from confluent_kafka import KafkaException, TopicPartition

    metadata = consumer.list_topics(topic, timeout=timeout)
    topic_metadata = metadata.topics.get(topic)
    if topic_metadata is None or topic_metadata.error is not None:
        status[0] = "missing"
        return

    assignments, end_offsets = [], {}
    for partition in topic_metadata.partitions:
        low, high = consumer.get_watermark_offsets(
            TopicPartition(topic, partition), timeout=timeout
        )
        if high > low:
            assignments.append(TopicPartition(topic, partition, low))
            end_offsets[partition] = high

    if not assignments:
        status[0] = "empty"
        return

    consumer.assign(assignments)
    try:
        while end_offsets:
            message = consumer.poll(timeout)
            if message is None:
                status[0] = "timed_out"
                return
            if message.error():
                raise KafkaException(message.error())
            yield message
            partition = message.partition()
            if partition in end_offsets and message.offset() >= end_offsets[partition] - 1:
                del end_offsets[partition]
        status[0] = "done"
    finally:
        consumer.unassign()


def run(bootstrap, events_dir=EVENTS_DIR, timeout=10.0):
    from confluent_kafka import Consumer

    validators = load_validators(events_dir)
    consumer = Consumer(
        {
            "bootstrap.servers": bootstrap,
            # Throwaway group: we never commit, so no real consumer is affected.
            "group.id": f"contract-monitor-{uuid4()}",
            "enable.auto.commit": False,
            "allow.auto.create.topics": False,
        }
    )
    report = Report()
    try:
        for topic in CATALOG:
            status = [None]
            for message in read_topic(consumer, topic, timeout, status):
                result = check_message(topic, message.value(), validators)
                report.add(topic, message.partition(), message.offset(), result)
            if status[0] == "missing":
                report.missing_topics.append(topic)
            elif status[0] == "empty":
                report.empty_topics.append(topic)
            elif status[0] == "timed_out":
                report.unfinished_topics.append(topic)
    finally:
        consumer.close()

    return report, validators


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check live Kafka messages against contracts/events/.")
    parser.add_argument(
        "--bootstrap",
        default=os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:29092"),
        help="Kafka bootstrap servers (default: $KAFKA_BOOTSTRAP_SERVERS or localhost:29092).",
    )
    parser.add_argument("--timeout", type=float, default=10.0, help="Seconds to wait for Kafka.")
    parser.add_argument("--out", help="Also write the Markdown report to this file.")
    args = parser.parse_args(argv)

    from confluent_kafka import KafkaException

    try:
        report, validators = run(args.bootstrap, timeout=args.timeout)
    except KafkaException as exc:
        print(f"Cannot read from Kafka at {args.bootstrap}: {exc}", file=sys.stderr)
        print("Is the stack up? Run `make up` first.", file=sys.stderr)
        return 2

    markdown = report.to_markdown(args.bootstrap, validators)
    print(markdown)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(markdown)
    return 1 if report.total_bad else 0


if __name__ == "__main__":
    sys.exit(main())
