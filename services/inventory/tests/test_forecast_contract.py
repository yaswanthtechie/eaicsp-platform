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
    """
    What the Forecast Service returns today (forecast,
    model_version, latency_ms) plus the fields Inventory
    needs added.
    """

    payload = {
        "contract_version": "v1",
        "sku_id": "SKU001",
        "warehouse_id": "WH001",
        "granularity": "monthly",
        "interval_level": 0.8,
        "model_version": "prophet-xgb-r5",
        "generated_at": "2026-10-01T06:00:00Z",
        "latency_ms": 42.1,
        "forecast": [
            {"date": "2026-10-01", "predicted": 310.0, "lower": 250.0, "upper": 370.0},
            {"date": "2026-11-01", "predicted": 300.0, "lower": 240.0, "upper": 360.0},
        ],
    }
    payload.update(overrides)
    return payload


# ============================================================
# CONTRACT VALIDATION
# ============================================================

def test_contract_accepts_forecast_service_output():
    contract = ForecastContract.model_validate(forecast_payload())

    assert contract.sku_id == "SKU001"
    assert contract.forecast[0].predicted == 310.0
    assert contract.forecast[1].date == date(2026, 11, 1)


def test_contract_ignores_extra_fields():
    # latency_ms is in the payload; new service fields must not
    # break Inventory (tolerant reader).
    contract = ForecastContract.model_validate(
        forecast_payload(debug_info={"x": 1})
    )

    assert not hasattr(contract, "latency_ms")


@pytest.mark.parametrize(
    "field",
    ["sku_id", "warehouse_id", "interval_level", "generated_at", "forecast"],
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
        {"granularity": "daily"},
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
        {"date": "2026-10-01", "predicted": -1.0, "lower": -5.0, "upper": 5.0},
        {"date": "2026-10-01", "predicted": 400.0, "lower": 250.0, "upper": 370.0},
        {"date": "2026-10-01", "predicted": 300.0, "lower": 370.0, "upper": 250.0},
        {"date": "2026-10-15", "predicted": 300.0, "lower": 250.0, "upper": 370.0},
    ],
)
def test_contract_rejects_invalid_points(point):
    with pytest.raises(ValidationError):
        ForecastContract.model_validate(forecast_payload(forecast=[point]))


def test_contract_rejects_out_of_order_or_duplicate_months():
    october = {"date": "2026-10-01", "predicted": 300.0, "lower": 250.0, "upper": 370.0}
    november = {"date": "2026-11-01", "predicted": 300.0, "lower": 240.0, "upper": 360.0}

    for points in ([november, october], [october, october]):
        with pytest.raises(ValidationError):
            ForecastContract.model_validate(forecast_payload(forecast=points))


# ============================================================
# HOW INVENTORY USES IT (not wired yet)
# ============================================================

def test_monthly_forecast_becomes_daily_mean_and_std():
    contract = ForecastContract.model_validate(forecast_payload())

    daily = daily_demand_from_forecast(contract, date(2026, 10, 20))

    z80 = NormalDist().inv_cdf(0.9)
    assert daily["daily_demand"] == pytest.approx(310 / 31)
    assert daily["daily_std"] == pytest.approx(
        ((370 - 250) / (2 * z80)) / 31 ** 0.5
    )


def test_uses_forecast_when_fresh_and_matching():
    contract = ForecastContract.model_validate(forecast_payload())

    result = resolve_daily_demand(
        contract, "SKU001", "WH001", date(2026, 10, 20), NOW,
        history_daily_demand=8.0,
    )

    assert result["source"] == "forecast"
    assert result["daily_demand"] == pytest.approx(10.0)


@pytest.mark.parametrize(
    "contract_overrides, sku, on_date, expected_reason",
    [
        ({}, "OTHER-SKU", date(2026, 10, 20), "different SKU"),
        (
            {"generated_at": (NOW - timedelta(days=60)).isoformat()},
            "SKU001",
            date(2026, 10, 20),
            "stale",
        ),
        ({}, "SKU001", date(2027, 3, 1), "does not cover"),
    ],
)
def test_falls_back_to_history_when_forecast_unusable(
    contract_overrides, sku, on_date, expected_reason
):
    contract = ForecastContract.model_validate(
        forecast_payload(**contract_overrides)
    )

    result = resolve_daily_demand(
        contract, sku, "WH001", on_date, NOW,
        history_daily_demand=8.0,
    )

    assert result["source"] == "history"
    assert result["daily_demand"] == 8.0
    assert expected_reason in result["reason"]


def test_falls_back_to_history_without_forecast():
    result = resolve_daily_demand(
        None, "SKU001", "WH001", date(2026, 10, 20), NOW,
        history_daily_demand=8.0,
    )

    assert result["source"] == "history"