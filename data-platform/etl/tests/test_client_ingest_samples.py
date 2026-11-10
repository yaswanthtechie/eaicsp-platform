import csv
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parents[1] / "client_ingest"
SAMPLES = ROOT / "samples" / "client_format"
SPEC = yaml.safe_load((ROOT / "spec.yaml").read_text(encoding="utf-8"))

def load(name):
    with (SAMPLES / f"{name}.csv").open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))

def test_spec_has_ten_files():
    assert len(SPEC["files"]) == 10

@pytest.mark.parametrize("name", list(SPEC["files"]))
def test_csv_headers_match_spec(name):
    with (SAMPLES / f"{name}.csv").open(encoding="utf-8", newline="") as f:
        headers = next(csv.reader(f))
    assert headers == list(SPEC["files"][name]["columns"])

def test_sales_row_count():
    assert len(load("sales_history")) == 27454

def test_sales_daily_series_is_complete():
    rows = load("sales_history")[:-4]
    counts = Counter((r["product_code"], r["warehouse_code"]) for r in rows)
    assert len(counts) == 50
    assert set(counts.values()) == {549}

def test_sales_zero_days_are_present():
    rows = load("sales_history")[:-4]
    assert any(int(r["quantity_sold"]) == 0 for r in rows)

def test_product_count():
    assert len(load("product_master")) == 52

def test_warehouse_count_and_country():
    rows = load("warehouse_master")
    assert len(rows) == 7
    assert all(r["country"] == "India" for r in rows[:5])

def test_warehouse_iata_mapping():
    assert set(SPEC["warehouse_city_to_iata"]) >= {
        "Hyderabad", "Bengaluru", "Mumbai", "New Delhi", "Chennai"
    }

def test_supplier_count():
    assert len(load("supplier_master")) == 22

def test_carrier_rates_differ():
    rates = [float(r["base_late_rate"]) for r in load("carriers")[:4]]
    assert len(set(rates)) > 1

def test_inventory_uses_reorder_point_and_safety_stock():
    rows = load("inventory_snapshot")
    assert "reorder_point" in rows[0]
    assert "safety_stock" in rows[0]
    assert any(r["safety_stock"] == "" for r in rows[:250])

def test_purchase_order_count():
    assert len(load("purchase_order_history")) == 368

def test_all_po_statuses_exist():
    statuses = {r["po_status"] for r in load("purchase_order_history")[:365]}
    assert statuses == {"Open", "Received", "Cancelled"}

def test_received_pos_have_received_date():
    rows = load("purchase_order_history")[:365]
    assert all(r["received_date"] for r in rows if r["po_status"] == "Received")

def test_open_and_cancelled_pos_have_no_received_date():
    rows = load("purchase_order_history")[:365]
    assert all(not r["received_date"] for r in rows if r["po_status"] in {"Open", "Cancelled"})

def test_shipment_count():
    assert len(load("shipment_history")) == 353

def test_twelve_shipments_are_in_transit():
    rows = load("shipment_history")[:350]
    assert sum(r["shipment_status"] == "In Transit" for r in rows) == 12

def test_in_transit_has_no_actual_delivery_date():
    rows = load("shipment_history")[:350]
    assert all(not r["actual_delivery_date"] for r in rows if r["shipment_status"] == "In Transit")

def test_cancelled_pos_have_no_shipments():
    pos = {r["po_number"] for r in load("purchase_order_history")[:365] if r["po_status"] == "Cancelled"}
    shipments = {r["po_number"] for r in load("shipment_history")[:350]}
    assert not pos.intersection(shipments)

def test_shipment_eta_columns_exist():
    rows = load("shipment_history")
    assert {"origin_city", "destination_warehouse_code", "carrier_name", "weight_kg", "volume_m3"} <= set(rows[0])

def test_bad_rows_have_unique_keys():
    checks = [
        ("product_master", "product_code"),
        ("warehouse_master", "warehouse_code"),
        ("supplier_master", "supplier_code"),
        ("carriers", "carrier_code"),
        ("sales_history", "order_number"),
        ("purchase_order_history", "po_number"),
        ("shipment_history", "shipment_id")
    ]
    for name, key in checks:
        values = [r[key] for r in load(name)]
        assert len(values) == len(set(values))

def test_all_ten_sample_files_exist():
    assert all((SAMPLES / f"{name}.csv").exists() for name in SPEC["files"])
