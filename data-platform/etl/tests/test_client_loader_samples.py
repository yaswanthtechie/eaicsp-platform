import csv
import importlib.util
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
LOADER_PATH = ROOT / "client_ingest" / "load_client_data.py"
SAMPLES = ROOT / "client_ingest" / "samples" / "client_format"

spec = importlib.util.spec_from_file_location("client_loader", LOADER_PATH)
loader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(loader)

EXPECTED_BAD = {
    "product_master": 2,
    "warehouse_master": 2,
    "supplier_master": 2,
    "carriers": 2,
    "sales_history": 4,
    "inventory_snapshot": 2,
    "supplier_lead_times": 2,
    "supplier_incidents": 2,
    "purchase_order_history": 3,
    "shipment_history": 3,
}


def inspect_samples():
    contract = yaml.safe_load(loader.SPEC.read_text(encoding="utf-8"))
    known = {entity: set() for entity, _ in loader.MASTER_KEYS.values()}
    rejected = Counter()
    reasons = []

    for key in loader.ORDER:
        path = SAMPLES / f"{key}.csv"
        rules = contract["files"][key]["columns"]

        with path.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            assert not (set(rules) - set(reader.fieldnames or [])), key

            for raw in reader:
                row = {k: (v.strip() if v else "") for k, v in raw.items()}
                errors = (
                    loader.validate(row, rules)
                    + loader.reference_errors(key, row, known)
                )
                if errors:
                    rejected[key] += 1
                    reasons.extend(errors)
                else:
                    loader.remember(key, row, known)

    return rejected, reasons


def test_all_planted_bad_rows_are_rejected():
    rejected, _ = inspect_samples()
    assert dict(rejected) == EXPECTED_BAD


def test_unknown_product_codes_are_rejected():
    _, reasons = inspect_samples()
    assert any("unknown product PRD-99999" in r for r in reasons)
    assert any("unknown product PRD-99903" in r for r in reasons)


def test_unknown_supplier_codes_are_rejected():
    _, reasons = inspect_samples()
    assert any("unknown supplier SUP-9993" in r for r in reasons)
    assert any("unknown supplier SUP-9994" in r for r in reasons)


def test_negative_unit_price_is_rejected():
    contract = yaml.safe_load(loader.SPEC.read_text(encoding="utf-8"))
    rules = contract["files"]["product_master"]["columns"]
    row = {
        "product_code": "PRD-12345",
        "product_name": "Test product",
        "unit_price": "-10.00",
    }
    errors = loader.validate(row, rules)
    assert any("unit_price: must not be negative" in e for e in errors)
def test_shipment_preserves_client_id_and_reuses_po_mapping(monkeypatch):
    calls = []

    def fake_get_id(conn, entity, code, prefix, width=6, year=None, city_code=None):
        calls.append((entity, code, year, city_code))
        if entity == "shipment":
            return "SHP-2026-000001"
        if entity == "warehouse":
            return "WH-BLR-01"
        raise AssertionError(f"Unexpected ID generation: {entity}")

    def fake_lookup_id(conn, entity, code):
        assert entity == "purchase_order"
        assert code == "PO-000007"
        return "PO-2025-000007"

    monkeypatch.setattr(loader, "get_id", fake_get_id)
    monkeypatch.setattr(loader, "lookup_id", fake_lookup_id)

    row = {
        "shipment_id": "SH-000123",
        "dispatch_date": "2026-03-10",
        "po_number": "PO-000007",
        "destination_warehouse_code": "WH1",
    }

    result = loader.add_ids(
        None, "shipment_history", row, {"WH1": "Bengaluru"}
    )

    assert result["client_shipment_id"] == "SH-000123"
    assert result["shipment_id"] == "SHP-2026-000001"
    assert result["po_id"] == "PO-2025-000007"
    assert result["warehouse_id"] == "WH-BLR-01"
