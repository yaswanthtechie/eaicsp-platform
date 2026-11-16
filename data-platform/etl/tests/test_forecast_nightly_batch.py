"""Docker-free tests for the nightly forecast batch helpers."""

import json
import os
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import jsonschema
import pytest
from referencing import Registry, Resource

DAGS_DIR = Path(__file__).resolve().parents[1] / "dags"
sys.path.insert(0, str(DAGS_DIR))

from forecast_batch_helpers import build_event, build_rows, forecast_pairs, write_batch


REPO_ROOT = Path(__file__).resolve().parents[3]
CONTRACTS_DIR = REPO_ROOT / "contracts" / "events"


def load_contract(name):
    return json.loads((CONTRACTS_DIR / name).read_text(encoding="utf-8"))


def sample_forecast(start="2026-11-13", count=30):
    start_date = date.fromisoformat(start)
    return [
        {
            "date": (start_date + timedelta(days=index)).isoformat(),
            "predicted": 100.0 + index,
            "lower_bound": 90.0 + index,
            "upper_bound": 110.0 + index,
        }
        for index in range(count)
    ]


def sample_rows(pairs, horizon=30, version=None):
    generated_at = datetime(2026, 11, 12, 1, 0, tzinfo=timezone.utc)
    version = version or generated_at

    forecasts = [
        (sku, warehouse, sample_forecast(count=horizon))
        for sku, warehouse in pairs
    ]

    return build_rows(
        batch_date=date(2026, 11, 12),
        forecasts_by_pair=forecasts,
        model_version="demand_forecast/1",
        generated_at=generated_at,
        version=version,
        horizon=horizon,
    )


def test_event_matches_forecast_contract_and_uses_uuid_v4():
    pairs = {
        ("SKU-000001", "WH-HYD-01"),
        ("SKU-000002", "WH-BOM-01"),
    }

    event = build_event(
        run_id="BATCH-20261112-01",
        model_version="demand_forecast/1",
        pairs=pairs,
        horizon=30,
        completed_at=datetime(2026, 11, 12, 2, 0, tzinfo=timezone.utc),
        duration_seconds=12.5,
    )

    schema = load_contract("forecast.batch.completed.v1.json")
    envelope_schema = load_contract("envelope.v1.json")

    registry = Registry().with_resource(
        "https://eaicsp.internal/contracts/events/envelope.v1.json",
        Resource.from_contents(envelope_schema),
    )

    jsonschema.validate(
        event,
        schema,
        registry=registry,
        format_checker=jsonschema.FormatChecker(),
    )

    assert uuid.UUID(event["event_id"]).version == 4


class FakeClickHouse:
    """Simulate ReplacingMergeTree(version) and SELECT FINAL."""

    def __init__(self):
        self.inserted_rows = []

    def insert(self, table, rows, column_names):
        assert table == "demand_forecast_history"
        self.inserted_rows.extend(rows)

    def final_rows(self, batch_date):
        latest = {}

        for row in self.inserted_rows:
            if row[0] != batch_date:
                continue

            key = (row[0], row[2], row[3], row[1])
            if key not in latest or row[10] > latest[key][10]:
                latest[key] = row

        return list(latest.values())


class FakeRedisPipeline:
    def __init__(self, redis_client):
        self.redis_client = redis_client
        self.pending = []

    def set(self, key, value, ex=None):
        self.pending.append((key, value, ex))
        return self

    def execute(self):
        for key, value, _ in self.pending:
            self.redis_client.values[key] = value
        self.redis_client.pipeline_executions += 1
        return [True] * len(self.pending)


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.pipeline_executions = 0

    def get(self, key):
        return self.values.get(key)

    def pipeline(self):
        return FakeRedisPipeline(self)


def test_same_batch_rerun_is_idempotent_for_clickhouse_and_redis():
    pairs = {
        ("SKU-000001", "WH-HYD-01"),
        ("SKU-000002", "WH-BOM-01"),
    }

    ch = FakeClickHouse()
    cache = FakeRedis()

    columns = [
        "batch_date",
        "forecast_date",
        "sku_id",
        "warehouse_id",
        "predicted",
        "lower_bound",
        "upper_bound",
        "interval_level",
        "model_version",
        "generated_at",
        "version",
    ]

    first_version = datetime(2026, 11, 12, 1, 0, tzinfo=timezone.utc)
    second_version = first_version + timedelta(minutes=5)

    for version in (first_version, second_version):
        rows = sample_rows(pairs, version=version)
        cache_entries = [
            (
                f"forecast_cache:2026-11-12:{sku}:{warehouse}",
                {
                    "run_id": "BATCH-20261112-01",
                    "sku_id": sku,
                    "warehouse_id": warehouse,
                    "model_version": "demand_forecast/1",
                },
            )
            for sku, warehouse in pairs
        ]

        write_batch(
            ch=ch,
            cache=cache,
            rows=rows,
            cache_entries=cache_entries,
            columns=columns,
            ttl=86400,
            batch_date_text="2026-11-12",
        )

    final_rows = ch.final_rows(date(2026, 11, 12))

    assert len(final_rows) == len(pairs) * 30
    assert len(ch.inserted_rows) == len(pairs) * 30 * 2
    assert len(cache.values) == len(pairs) + 1
    assert cache.values["forecast_cache:latest_batch_date"] == "2026-11-12"
    assert cache.pipeline_executions == 2
    expected_keys = {
        f"forecast_cache:2026-11-12:{sku}:{warehouse}"
        for sku, warehouse in pairs
    }
    expected_keys.add("forecast_cache:latest_batch_date")
    assert set(cache.values) == expected_keys


def test_invalid_forecast_values_raise_value_error():
    invalid_forecasts = [
        {
            "date": "2026-11-13",
            "predicted": 100,
            "lower_bound": 110,
            "upper_bound": 120,
        },
        {
            "date": "2026-11-13",
            "predicted": -1,
            "lower_bound": 0,
            "upper_bound": 120,
        },
    ]

    for point in invalid_forecasts:
        with pytest.raises(ValueError):
            build_rows(
                batch_date=date(2026, 11, 12),
                forecasts_by_pair=[("SKU-000001", "WH-HYD-01", [point])],
                model_version="demand_forecast/1",
                generated_at=datetime.now(timezone.utc),
                version=datetime.now(timezone.utc),
                horizon=1,
            )


def test_build_rows_returns_pairs_times_horizon_rows():
    pairs = {
        ("SKU-000001", "WH-HYD-01"),
        ("SKU-000002", "WH-BOM-01"),
        ("SKU-000003", "WH-VIZ-01"),
    }

    rows = sample_rows(pairs, horizon=30)

    assert len(rows) == len(pairs) * 30



def test_invalid_sku_and_warehouse_ids_are_rejected():
    from forecast_batch_helpers import validate_pair

    with pytest.raises(ValueError):
        validate_pair("SKU-001", "WH-HYD-01")

    with pytest.raises(ValueError):
        validate_pair("SKU-000001", "warehouse-01")


def test_partial_event_matches_contract():
    event = build_event(
        run_id="BATCH-20261112-01",
        model_version="demand_forecast/1",
        pairs={("SKU-000001", "WH-HYD-01")},
        horizon=30,
        completed_at=datetime(
            2026, 11, 12, 2, 0, tzinfo=timezone.utc
        ),
        status="PARTIAL",
        message="One SKU/warehouse pair failed.",
    )

    schema = load_contract("forecast.batch.completed.v1.json")
    envelope_schema = load_contract("envelope.v1.json")

    registry = Registry().with_resource(
        "https://eaicsp.internal/contracts/events/envelope.v1.json",
        Resource.from_contents(envelope_schema),
    )

    jsonschema.validate(
        event,
        schema,
        registry=registry,
        format_checker=jsonschema.FormatChecker(),
    )

    assert event["payload"]["status"] == "PARTIAL"
    assert event["payload"]["message"] == "One SKU/warehouse pair failed."



class _FailingModel:
    def predict(self, sku, warehouse, horizon):
        raise ValueError("model output invalid")


class _MixedModel:
    def predict(self, sku, warehouse, horizon):
        if sku == "SKU-000002":
            raise ValueError("model output invalid")
        return sample_forecast(count=horizon)


def test_zero_successful_pairs_raises():
    with pytest.raises(RuntimeError, match="No SKU/warehouse pairs"):
        forecast_pairs(
            model=_FailingModel(),
            pairs={("SKU-000001", "WH-HYD-01")},
            horizon=30,
            batch_date=date(2026, 11, 12),
            model_version="demand_forecast/1",
            generated_at=datetime(2026, 11, 12, 1, tzinfo=timezone.utc),
            version=datetime(2026, 11, 12, 1, tzinfo=timezone.utc),
            interval_level=0.8,
            run_id="BATCH-20261112-01",
        )


def test_partial_success_returns_valid_pairs_and_failures():
    rows, cache_entries, successful, failed = forecast_pairs(
        model=_MixedModel(),
        pairs={
            ("SKU-000001", "WH-HYD-01"),
            ("SKU-000002", "WH-BOM-01"),
        },
        horizon=30,
        batch_date=date(2026, 11, 12),
        model_version="demand_forecast/1",
        generated_at=datetime(2026, 11, 12, 1, tzinfo=timezone.utc),
        version=datetime(2026, 11, 12, 1, tzinfo=timezone.utc),
        interval_level=0.8,
        run_id="BATCH-20261112-01",
    )

    assert len(successful) == 1
    assert len(failed) == 1
    assert len(rows) == 30
    assert len(cache_entries) == 1

def test_latest_pointer_does_not_move_backwards():
    cache = FakeRedis()
    cache.values["forecast_cache:latest_batch_date"] = "2026-11-16"
    entry = (
        "forecast_cache:2026-11-10:SKU-000001:WH-HYD-01",
        {"run_id": "x"},
    )

    write_batch(
        ch=FakeClickHouse(),
        cache=cache,
        rows=[],
        cache_entries=[entry],
        columns=[],
        ttl=60,
        batch_date_text="2026-11-10",
    )

    assert cache.values["forecast_cache:latest_batch_date"] == "2026-11-16"
    assert entry[0] in cache.values

@pytest.mark.integration
def test_rerun_is_idempotent_in_real_clickhouse():
    clickhouse_connect = pytest.importorskip("clickhouse_connect")
    if not os.getenv("CLICKHOUSE_PASSWORD"):
        pytest.skip("CLICKHOUSE_PASSWORD not set")

    client = clickhouse_connect.get_client(
        host=os.getenv("CLICKHOUSE_HOST", "localhost"),
        port=int(os.getenv("CLICKHOUSE_PORT", "8123")),
        username=os.getenv("CLICKHOUSE_USER", "default"),
        password=os.environ["CLICKHOUSE_PASSWORD"],
        database=os.getenv("CLICKHOUSE_DATABASE", "analytics"),
    )
    pairs = {("SKU-999991", "WH-HYD-01"), ("SKU-999992", "WH-BOM-01")}
    test_skus = sorted(sku for sku, _ in pairs)
    columns = [
        "batch_date", "forecast_date", "sku_id", "warehouse_id",
        "predicted", "lower_bound", "upper_bound", "interval_level",
        "model_version", "generated_at", "version",
    ]
    first_version = datetime(2026, 11, 12, 1, 0, tzinfo=timezone.utc)

    try:
        for version in (first_version, first_version + timedelta(minutes=5)):
            rows = sample_rows(pairs, version=version)
            write_batch(
                ch=client,
                cache=FakeRedis(),
                rows=rows,
                cache_entries=[],
                columns=columns,
                ttl=60,
                batch_date_text=rows[0][0].isoformat(),
            )

        count = client.query(
            "SELECT count() FROM demand_forecast_history FINAL "
            "WHERE batch_date = {d:Date} AND sku_id IN {skus:Array(String)}",
            parameters={"d": rows[0][0], "skus": test_skus},
        ).result_rows[0][0]

        assert count == len(pairs) * 30
    finally:
        client.command(
            "ALTER TABLE demand_forecast_history DELETE "
            "WHERE sku_id IN {skus:Array(String)}",
            parameters={"skus": test_skus},
        )
        client.close()

