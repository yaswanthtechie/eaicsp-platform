from pathlib import Path


CONTRACT_PATH = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "ETA_SHIPMENT_PREDICTED_CONTRACT.md"
)


REQUIRED_FIELDS = [
    "shipment_id",
    "po_number",
    "eta_days",
    "confidence_low",
    "confidence_high",
    "model_version",
    "predicted_at",
]


def test_eta_shipment_predicted_contract_exists():
    assert CONTRACT_PATH.is_file()


def test_eta_shipment_predicted_contract_contains_required_fields():
    content = CONTRACT_PATH.read_text(encoding="utf-8")

    for field in REQUIRED_FIELDS:
        assert f"`{field}`" in content


def test_eta_shipment_predicted_contract_contains_event_name():
    content = CONTRACT_PATH.read_text(encoding="utf-8")

    assert "eta.shipment.predicted" in content


def test_eta_shipment_predicted_contract_contains_example():
    content = CONTRACT_PATH.read_text(encoding="utf-8")

    assert "SHIP-12345" in content
    assert "PO-98765" in content
    assert "eta-model-v1" in content
    assert "2026-10-23T10:30:00Z" in content


def test_eta_shipment_predicted_contract_contains_validation_rules():
    content = CONTRACT_PATH.read_text(encoding="utf-8")

    assert "must be present and non-empty" in content
    assert "must be numeric and non-negative" in content
    assert "confidence_low" in content
    assert "confidence_high" in content
    assert "valid ISO-8601 UTC timestamp" in content