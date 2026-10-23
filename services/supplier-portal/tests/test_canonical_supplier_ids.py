import re

import pytest

from app.schemas.ids import SUPPLIER_ID_PATTERN
from app.schemas.invoice import InvoiceCreate
from app.schemas.purchase_order import PurchaseOrderCreate
from app.schemas.supplier_contract import SupplierContractCreate
from app.schemas.supplier_onboarding import SupplierRegistration


@pytest.mark.parametrize(
    "model",
    [
        InvoiceCreate,
        PurchaseOrderCreate,
        SupplierContractCreate,
        SupplierRegistration,
    ],
)
def test_request_models_require_canonical_supplier_id(model):
    schema = model.model_json_schema()
    assert (
        schema["properties"]["supplier_id"]["pattern"]
        == SUPPLIER_ID_PATTERN
    )


@pytest.mark.parametrize(
    "good",
    ["SUP-00001", "SUP-00045", "SUP-99999"],
)
def test_pattern_accepts_canonical_ids(good):
    assert re.fullmatch(SUPPLIER_ID_PATTERN, good)


@pytest.mark.parametrize(
    "bad",
    [
        "SUP001",
        "SUP-001",
        "SUP-000001",
        "sup-00001",
        "SUP-0000A",
        "",
    ],
)
def test_pattern_rejects_legacy_ids(bad):
    assert not re.fullmatch(SUPPLIER_ID_PATTERN, bad)
