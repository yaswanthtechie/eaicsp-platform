import csv
import importlib.util
from collections import Counter
from pathlib import Path
from unittest.mock import MagicMock

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
                errors = loader.process_row(
                    key, raw, rules, known, load=lambda row: None
                )
                if errors:
                    rejected[key] += 1
                    reasons.extend(errors)

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
            return "WH-BLR-02"
        raise AssertionError(f"Unexpected ID generation: {entity}")

    def fake_lookup_id(conn, entity, code):
        if entity == "warehouse":
            raise LookupError("not mapped yet")
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
    assert result["warehouse_id"] == "WH-BLR-02"



def test_infinite_unit_price_is_rejected_not_a_crash():
    contract = yaml.safe_load(loader.SPEC.read_text(encoding="utf-8"))
    rules = contract["files"]["product_master"]["columns"]
    for value in ("Infinity", "-inf"):
        row = {
            "product_code": "PRD-12345",
            "product_name": "x",
            "unit_price": value,
        }
        errors = loader.validate(row, rules)
        assert "unit_price: invalid decimal value" in errors


def test_row_with_extra_fields_is_rejected_not_a_crash():
    raw = {
        "product_code": "PRD-12345",
        "product_name": "Bolt",
        None: ["steel"],
    }
    errors = loader.process_row(
        "product_master", raw, {}, {}, load=lambda row: None
    )
    assert errors == ["row has 1 more fields than the header"]


def test_existing_warehouse_mapping_needs_no_city(monkeypatch):
    monkeypatch.setattr(
        loader, "lookup_id",
        lambda conn, entity, code: "WH-BLR-01"
    )
    row = loader.add_ids(
        None, "sales_history", {"warehouse_code": "BLR-01"}, {}
    )
    assert row["warehouse_id"] == "WH-BLR-01"


class FakeMappingConn:
    def __init__(self):
        self.inserted = []

    def execute(self, statement, params=None):
        sql = str(statement)
        result = MagicMock()

        if "SELECT canonical_id FROM client_id_mapping" in sql:
            if "client_code=:code" in sql:
                result.scalar_one_or_none.return_value = None
            elif "WHERE entity_type=:entity" in sql:
                result.scalars.return_value.all.return_value = []

        if "INSERT INTO client_id_mapping" in sql:
            self.inserted.append(params)

        return result


def test_client_warehouse_ids_never_reuse_seed_warehouse_ids():
    conn = FakeMappingConn()

    warehouse_id = loader.get_id(
        conn,
        entity="warehouse",
        code="CLIENT-BLR-01",
        prefix="WH",
        city_code="BLR",
    )

    assert loader.SEED_WAREHOUSE_SITES["BLR"] == 1
    assert warehouse_id == "WH-BLR-02"
    assert conn.inserted[0]["canonical"] == "WH-BLR-02"


def test_lowercase_client_code_is_rejected():
    contract = yaml.safe_load(loader.SPEC.read_text(encoding="utf-8"))
    rules = contract["files"]["product_master"]["columns"]
    row = {
        "product_code": "prd-12345",
        "product_name": "x",
        "unit_price": "1.00",
    }
    assert "product_code: invalid format" in loader.validate(row, rules)

def test_duplicate_record_key_in_same_file_is_rejected(monkeypatch):
    seen = set()
    process = MagicMock(return_value=[])
    monkeypatch.setattr(loader, "process_row", process)

    row = {"product_code": "PRD-12345"}

    first = loader.process_unique_row(
        seen, "product_master", row, {}, {}, MagicMock()
    )
    second = loader.process_unique_row(
        seen, "product_master",
        {"product_code": " PRD-12345 "}, {}, {}, MagicMock()
    )

    assert first == []
    assert second == ["duplicate of an earlier row in this file"]
    assert process.call_count == 1
