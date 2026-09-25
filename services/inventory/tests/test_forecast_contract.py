from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.forecast import ForecastContract


def test_forecast_contract_accepts_valid_output():
    forecast = ForecastContract(
        contract_version="v1",
        sku_id="SKU001",
        warehouse_id="WH001",
        forecast_date=date(2026, 10, 1),
        forecast_quantity=125.5,
        horizon_days=30,
        generated_at=datetime.now(timezone.utc),
        confidence=0.92,
    )

    assert forecast.contract_version == "v1"
    assert forecast.sku_id == "SKU001"
    assert forecast.warehouse_id == "WH001"
    assert forecast.forecast_quantity == 125.5
    assert forecast.horizon_days == 30
    assert forecast.confidence == 0.92


def test_forecast_contract_rejects_negative_quantity():
    with pytest.raises(ValidationError):
        ForecastContract(
            contract_version="v1",
            sku_id="SKU001",
            warehouse_id="WH001",
            forecast_date=date(2026, 10, 1),
            forecast_quantity=-10,
            horizon_days=30,
            generated_at=datetime.now(timezone.utc),
        )


def test_forecast_contract_rejects_invalid_confidence():
    with pytest.raises(ValidationError):
        ForecastContract(
            contract_version="v1",
            sku_id="SKU001",
            warehouse_id="WH001",
            forecast_date=date(2026, 10, 1),
            forecast_quantity=100,
            horizon_days=30,
            generated_at=datetime.now(timezone.utc),
            confidence=1.5,
        )


def test_forecast_contract_rejects_invalid_horizon():
    with pytest.raises(ValidationError):
        ForecastContract(
            contract_version="v1",
            sku_id="SKU001",
            warehouse_id="WH001",
            forecast_date=date(2026, 10, 1),
            forecast_quantity=100,
            horizon_days=0,
            generated_at=datetime.now(timezone.utc),
        )


def test_forecast_contract_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        ForecastContract(
            contract_version="v1",
            sku_id="SKU001",
            warehouse_id="WH001",
            forecast_date=date(2026, 10, 1),
            forecast_quantity=100,
            horizon_days=30,
            generated_at=datetime.now(timezone.utc),
            unexpected_field="not_allowed",
        )