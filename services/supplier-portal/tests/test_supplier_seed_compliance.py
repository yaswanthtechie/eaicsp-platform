from pathlib import Path
from unittest.mock import MagicMock, patch

from app.services.compliance_client import check_supplier_compliance
from app.services.supplier_seed_loader import load_supplier_csv


SEED_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "seed"
    / "suppliers.csv"
)

SANCTIONED_IDS = {
    "SUP-00007",
    "SUP-00023",
    "SUP-00045",
}


def test_sanctioned_seed_suppliers_are_blocked_by_compliance_response():
    records = load_supplier_csv(SEED_PATH)
    sanctioned = [
        record
        for record in records
        if record["supplier_id"] in SANCTIONED_IDS
    ]

    assert len(sanctioned) == 3

    for record in sanctioned:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "supplier_id": record["supplier_id"],
            "supplier_name": record["name"],
            "country": record["country"],
            "decision": "BLOCK",
            "cleared": False,
            "reason": "Matched sanctioned seed record",
        }

        mock_client = MagicMock()
        mock_client.__enter__.return_value.post.return_value = mock_response

        with patch(
            "app.services.compliance_client.httpx.Client",
            return_value=mock_client,
        ):
            result = check_supplier_compliance(
                supplier_id=record["supplier_id"],
                supplier_name=record["name"],
                country=record["country"],
            )

        assert result["decision"] == "BLOCK"
        assert result["cleared"] is False

        request = mock_client.__enter__.return_value.post.call_args
        assert request.kwargs["json"] == {
            "supplier_id": record["supplier_id"],
            "supplier_name": record["name"],
            "country": record["country"],
        }