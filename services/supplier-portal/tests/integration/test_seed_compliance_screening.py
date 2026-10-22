
"""Screen seed suppliers against the real Compliance Service.

Requires Compliance running at COMPLIANCE_SERVICE_URL with sanctions
lists loaded, including the EU list.

Run:
    python -m pytest -m integration tests/integration/test_seed_compliance_screening.py -v
"""

from pathlib import Path

import pytest

from app.services.compliance_client import check_supplier_compliance
from app.services.supplier_seed_loader import load_supplier_csv

pytestmark = pytest.mark.integration

SEED_PATH = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "seed"
    / "suppliers.csv"
)

SANCTIONED_IDS = ["SUP-00007", "SUP-00023", "SUP-00045"]

# Control: a clean supplier must NOT be blocked.
CLEAN_ID = "SUP-00001"


@pytest.fixture(scope="module")
def seed_by_id():
    records = load_supplier_csv(SEED_PATH)
    return {record["supplier_id"]: record for record in records}


def screen(record):
    return check_supplier_compliance(
        supplier_id=record["supplier_id"],
        supplier_name=record["name"],
        country=record["country"],
    )


@pytest.mark.parametrize("supplier_id", SANCTIONED_IDS)
def test_sanctioned_seed_supplier_is_blocked(seed_by_id, supplier_id):
    result = screen(seed_by_id[supplier_id])

    assert result["decision"] == "BLOCK"
    assert result["cleared"] is False


def test_clean_seed_supplier_is_not_blocked(seed_by_id):
    result = screen(seed_by_id[CLEAN_ID])

    assert result["decision"] != "BLOCK"
