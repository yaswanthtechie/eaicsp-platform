
import logging

import pandas as pd
import pytest

from src.client_data import adapt_client_shipments


def make_shipments():
    return pd.DataFrame({
        "shipment_id": ["SHP001", "SHP002"],
        "po_number": ["PO001", "PO002"],
        "origin_city": ["Hyderabad", "Mumbai"],
        "destination_warehouse_code": [
            "WH-HYD-01",
            "WH-BOM-01",
        ],
        "carrier_name": ["BlueDart", "Delhivery"],
        "dispatch_date": ["2026-01-01", "2026-01-02"],
        "planned_delivery_date": [
            "2026-01-05",
            "2026-01-07",
        ],
        "actual_delivery_date": [
            "2026-01-06",
            "2026-01-08",
        ],
        "weight_kg": [10.0, 15.0],
        "volume_m3": [0.5, 0.8],
    })


def test_adapter_preserves_all_shipments():
    result = adapt_client_shipments(make_shipments())

    assert len(result) == 2
    assert result["shipment_id"].is_unique
    assert result.attrs["duplicate_shipment_count"] == 0


@pytest.mark.parametrize(
    "optional_column",
    ["weight_kg", "volume_m3"],
)
def test_missing_optional_column_is_supported(optional_column):
    shipments = make_shipments().drop(columns=[optional_column])

    result = adapt_client_shipments(shipments)

    assert len(result) == 2
    assert optional_column in result.columns
    assert result[optional_column].isna().all()


def test_missing_required_column_raises_error():
    shipments = make_shipments().drop(columns=["carrier_name"])

    with pytest.raises(ValueError, match="carrier_name"):
        adapt_client_shipments(shipments)


def test_duplicate_shipment_id_keeps_last_occurrence(caplog):
    shipments = make_shipments()
    shipments.loc[1, "shipment_id"] = "SHP001"
    shipments.loc[1, "carrier_name"] = "Updated Carrier"

    with caplog.at_level(logging.WARNING):
        result = adapt_client_shipments(shipments)

    assert len(result) == 1
    assert result.loc[0, "shipment_id"] == "SHP001"
    assert result.loc[0, "carrier_name"] == "Updated Carrier"
    assert result.attrs["duplicate_shipment_count"] == 1
    assert "Dropping 1 duplicate shipment_id rows" in caplog.text


def test_multiple_duplicate_rows_are_counted():
    shipments = make_shipments()
    shipments = pd.concat(
        [
            shipments,
            shipments.iloc[[0]],
            shipments.iloc[[0]],
        ],
        ignore_index=True,
    )

    result = adapt_client_shipments(shipments)

    assert len(result) == 2
    assert result["shipment_id"].is_unique
    assert result.attrs["duplicate_shipment_count"] == 2


def test_invalid_date_does_not_drop_shipment():
    shipments = make_shipments()
    shipments.loc[0, "dispatch_date"] = "invalid-date"

    result = adapt_client_shipments(shipments)

    assert len(result) == 2
    assert pd.isna(result.loc[0, "dispatch_date"])


def test_alternative_date_format_is_rejected():
    shipments = make_shipments()
    shipments.loc[0, "dispatch_date"] = "13/11/2025"

    result = adapt_client_shipments(shipments)

    assert len(result) == 2
    assert pd.isna(result.loc[0, "dispatch_date"])
    assert result.loc[1, "dispatch_date"] == pd.Timestamp("2026-01-02")


def test_valid_iso_date_format_is_accepted():
    result = adapt_client_shipments(make_shipments())

    assert result.loc[0, "dispatch_date"] == pd.Timestamp("2026-01-01")
    assert result.loc[0, "planned_delivery_date"] == pd.Timestamp(
        "2026-01-05"
    )
    assert result.loc[0, "actual_delivery_date"] == pd.Timestamp(
        "2026-01-06"
    )


def test_both_optional_columns_missing():
    shipments = make_shipments().drop(
        columns=["weight_kg", "volume_m3"]
    )

    result = adapt_client_shipments(shipments)

    assert len(result) == 2
    assert "weight_kg" in result.columns
    assert "volume_m3" in result.columns
    assert result["weight_kg"].isna().all()
    assert result["volume_m3"].isna().all()

def test_duplicate_keeps_latest_dispatch_date_even_if_earlier_line():
    shipments = make_shipments()

    # The first CSV row has the latest dispatch date.
    shipments.loc[0, "shipment_id"] = "SHP001"
    shipments.loc[0, "dispatch_date"] = "2026-01-20"
    shipments.loc[0, "carrier_name"] = "Latest Carrier"

    # The second CSV row has an earlier dispatch date.
    shipments.loc[1, "shipment_id"] = "SHP001"
    shipments.loc[1, "dispatch_date"] = "2026-01-10"
    shipments.loc[1, "carrier_name"] = "Older Carrier"

    result = adapt_client_shipments(shipments)

    assert len(result) == 1
    assert result.loc[0, "shipment_id"] == "SHP001"
    assert result.loc[0, "dispatch_date"] == pd.Timestamp("2026-01-20")
    assert result.loc[0, "carrier_name"] == "Latest Carrier"
    assert result.attrs["duplicate_shipment_count"] == 1

def test_duplicate_keeps_valid_date_over_invalid_date():
    shipments = make_shipments()

    shipments.loc[0, "shipment_id"] = "SHP001"
    shipments.loc[0, "dispatch_date"] = "invalid-date"
    shipments.loc[0, "carrier_name"] = "Invalid Date Carrier"

    shipments.loc[1, "shipment_id"] = "SHP001"
    shipments.loc[1, "dispatch_date"] = "2026-01-10"
    shipments.loc[1, "carrier_name"] = "Valid Date Carrier"

    result = adapt_client_shipments(shipments)

    assert len(result) == 1
    assert result.loc[0, "carrier_name"] == "Valid Date Carrier"
    assert result.loc[0, "dispatch_date"] == pd.Timestamp("2026-01-10")
