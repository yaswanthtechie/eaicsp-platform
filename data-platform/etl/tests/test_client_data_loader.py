import importlib.util
from pathlib import Path

MODULE = Path(__file__).parents[1] / "client_ingest" / "load_client_data.py"
spec = importlib.util.spec_from_file_location("client_loader", MODULE)
loader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(loader)


def test_rejects_invalid_product_code():
    errors = loader.validate(
        {"product_code": "BAD-123"},
        {"product_code": {"type": "string", "required": True, "format": "PRD-#####"}},
    )
    assert errors


def test_accepts_valid_product_code():
    errors = loader.validate(
        {"product_code": "PRD-00123"},
        {"product_code": {"type": "string", "required": True, "format": "PRD-#####"}},
    )
    assert errors == []


def test_rejects_missing_required_value():
    errors = loader.validate(
        {"quantity_sold": ""},
        {"quantity_sold": {"type": "integer", "required": True, "format": "non-negative"}},
    )
    assert errors


def test_rejects_negative_quantity():
    errors = loader.validate(
        {"quantity_sold": "-2"},
        {"quantity_sold": {"type": "integer", "required": True, "format": "non-negative"}},
    )
    assert errors


def test_record_key_is_stable():
    row = {
        "sale_date": "2026-01-01",
        "order_number": "ORD-1",
        "product_code": "PRD-00001",
        "warehouse_code": "MUM-01",
    }
    assert loader.make_record_key("sales_history", row) == loader.make_record_key("sales_history", row)


def test_record_key_distinguishes_sales_rows():
    first = {"sale_date": "2026-01-01", "order_number": "ORD-1",
             "product_code": "PRD-00001", "warehouse_code": "MUM-01"}
    second = {**first, "product_code": "PRD-00002"}
    assert loader.make_record_key("sales_history", first) != loader.make_record_key("sales_history", second)
