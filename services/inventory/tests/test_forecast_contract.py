from datetime import date, datetime, timedelta, timezone
from statistics import NormalDist

import pytest
from pydantic import ValidationError

from app.schemas.forecast import ForecastContract
from app.services.forecast_adapter import (
    daily_demand_from_forecast,
    resolve_daily_demand,
)


NOW = datetime(2026, 10, 5, tzinfo=timezone.utc)


def forecast_payload(**overrides):
    payload = {
        "contract_version": "v1",
        "sku_id": "SKU-000001",
        "warehouse_id": "WH-BLR-01",
        "granularity": "daily",
        "horizon": 30,
        "interval_level": 0.8,
        "model_version": "prophet-xgb-r5",
        "generated_at": "2026-10-01T06:00:00Z",
        "latency_ms": 42.1,
        "forecast": [
            {
                "date": "2026-10-05",
                "predicted": 10.0,
                "lower_bound": 8.0,
                "upper_bound": 12.0,
            },
            {
                "date": "2026-10-06",
                "predicted": 12.0,
                "lower_bound": 9.0,
                "upper_bound": 15.0,
            },
        ],
    }
    payload.update(overrides)
    return payload


# ============================================================
# CONTRACT VALIDATION
# ============================================================

def test_contract_accepts_daily_forecast_service_output():
    contract = ForecastContract.model_validate(forecast_payload())

    assert contract.sku_id == "SKU-000001"
    assert contract.granularity == "daily"
    assert contract.horizon == 30
    assert contract.forecast[0].predicted == 10.0
    assert contract.forecast[1].date == date(2026, 10, 6)


def test_contract_ignores_extra_fields():
    contract = ForecastContract.model_validate(
        forecast_payload(debug_info={"x": 1})
    )

    assert not hasattr(contract, "latency_ms")
    assert not hasattr(contract, "debug_info")


@pytest.mark.parametrize(
    "field",
    [
        "sku_id",
        "warehouse_id",
        "granularity",
        "horizon",
        "interval_level",
        "generated_at",
        "forecast",
    ],
)
def test_contract_requires_fields_inventory_depends_on(field):
    payload = forecast_payload()
    del payload[field]

    with pytest.raises(ValidationError):
        ForecastContract.model_validate(payload)


@pytest.mark.parametrize(
    "overrides",
    [
        {"contract_version": "v2"},
        {"granularity": "monthly"},
        {"horizon": 0},
        {"horizon": 91},
        {"interval_level": 1.0},
        {"interval_level": 0},
        {"forecast": []},
    ],
)
def test_contract_rejects_invalid_header(overrides):
    with pytest.raises(ValidationError):
        ForecastContract.model_validate(forecast_payload(**overrides))


@pytest.mark.parametrize(
    "point",
    [
        {
            "date": "2026-10-05",
            "predicted": -1.0,
            "lower_bound": 0.0,
            "upper_bound": 5.0,
        },
        {
            "date": "2026-10-05",
            "predicted": 20.0,
            "lower_bound": 8.0,
            "upper_bound": 12.0,
        },
        {
            "date": "2026-10-05",
            "predicted": 10.0,
            "lower_bound": 12.0,
            "upper_bound": 8.0,
        },
    ],
)
def test_contract_rejects_invalid_points(point):
    with pytest.raises(ValidationError):
        ForecastContract.model_validate(
            forecast_payload(forecast=[point])
        )


def test_contract_rejects_out_of_order_or_duplicate_dates():
    first = forecast_payload()["forecast"][0]
    second = forecast_payload()["forecast"][1]

    for points in ([second, first], [first, first]):
        with pytest.raises(ValidationError):
            ForecastContract.model_validate(
                forecast_payload(forecast=points)
            )


# ============================================================
# DAILY FORECAST ADAPTER
# ============================================================

def test_daily_forecast_returns_daily_mean_and_std():
    contract = ForecastContract.model_validate(forecast_payload())

    daily = daily_demand_from_forecast(
        contract,
        date(2026, 10, 5),
    )

    z80 = NormalDist().inv_cdf(0.9)

    assert daily["daily_demand"] == pytest.approx(10.0)
    assert daily["daily_std"] == pytest.approx(4.0 / (2 * z80))


def test_daily_forecast_returns_none_when_date_not_covered():
    contract = ForecastContract.model_validate(forecast_payload())

    daily = daily_demand_from_forecast(
        contract,
        date(2026, 10, 20),
    )

    assert daily is None


def test_uses_forecast_when_fresh_and_matching():
    contract = ForecastContract.model_validate(forecast_payload())

    result = resolve_daily_demand(
        contract,
        "SKU-000001",
        "WH-BLR-01",
        date(2026, 10, 5),
        NOW,
        history_daily_demand=8.0,
    )

    assert result["source"] == "forecast"
    assert result["daily_demand"] == pytest.approx(10.0)


@pytest.mark.parametrize(
    "contract_overrides, sku, warehouse, on_date, expected_reason",
    [
        (
            {},
            "OTHER-SKU",
            "WH-BLR-01",
            date(2026, 10, 5),
            "different SKU or warehouse",
        ),
        (
            {},
            "SKU-000001",
            "WH-OTHER-01",
            date(2026, 10, 5),
            "different SKU or warehouse",
        ),
        (
            {
                "generated_at": (
                    NOW - timedelta(days=60)
                ).isoformat()
            },
            "SKU-000001",
            "WH-BLR-01",
            date(2026, 10, 5),
            "stale",
        ),
        (
            {},
            "SKU-000001",
            "WH-BLR-01",
            date(2026, 10, 20),
            "does not cover",
        ),
        (
            {
                "generated_at": (
                    NOW + timedelta(days=1)
                ).isoformat()
            },
            "SKU-000001",
            "WH-BLR-01",
            date(2026, 10, 5),
            "future",
        ),
    ],
)
def test_falls_back_to_history_when_forecast_unusable(
    contract_overrides,
    sku,
    warehouse,
    on_date,
    expected_reason,
):
    contract = ForecastContract.model_validate(
        forecast_payload(**contract_overrides)
    )

    result = resolve_daily_demand(
        contract,
        sku,
        warehouse,
        on_date,
        NOW,
        history_daily_demand=8.0,
    )

    assert result["source"] == "history"
    assert result["daily_demand"] == 8.0
    assert expected_reason in result["reason"]


def test_falls_back_to_history_without_forecast():
    result = resolve_daily_demand(
        None,
        "SKU-000001",
        "WH-BLR-01",
        date(2026, 10, 5),
        NOW,
        history_daily_demand=8.0,
    )

    assert result["source"] == "history"
    assert result["daily_demand"] == 8.0
