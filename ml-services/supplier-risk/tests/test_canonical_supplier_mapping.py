"""
Tests for Canonical Supplier ID mapping, normalization, and MongoDB persistence.
Validates requirements from Integration Blueprint and Issue #222:
- Canonical supplier ID pattern ^SUP-\\d{5}$
- Deterministic resolution of names and legacy IDs to canonical IDs
- Idempotent MongoDB persistence and index creation
- Rejection of invalid or invented IDs
"""

from unittest.mock import MagicMock, patch
import pytest

from src.supplier_mapping import (
    CANONICAL_ID_REGEX,
    DETERMINISTIC_SEED_SUPPLIERS,
    ensure_mapping_indexes,
    get_default_seed_suppliers,
    is_canonical_supplier_id,
    legacy_id_to_canonical,
    normalize_supplier_name,
    resolve_canonical_supplier,
    resolve_canonical_supplier_id,
    seed_supplier_mappings,
    validate_canonical_supplier_id,
)


def test_canonical_supplier_id_regex():
    assert is_canonical_supplier_id("SUP-00045")
    assert is_canonical_supplier_id("SUP-00001")
    assert is_canonical_supplier_id("SUP-00007")
    assert is_canonical_supplier_id("SUP-99999")

    # Invalid IDs
    assert not is_canonical_supplier_id("SUP001")
    assert not is_canonical_supplier_id("SUP045")
    assert not is_canonical_supplier_id("sup-00045")
    assert not is_canonical_supplier_id("SUP-45")
    assert not is_canonical_supplier_id("SUP-000045")
    assert not is_canonical_supplier_id("SUP-ABCDE")
    assert not is_canonical_supplier_id("")
    assert not is_canonical_supplier_id(None)


def test_validate_canonical_supplier_id_raises_value_error():
    assert validate_canonical_supplier_id("SUP-00045") == "SUP-00045"
    with pytest.raises(ValueError, match=r"(not canonical|Invalid supplier ID)"):
        validate_canonical_supplier_id("SUP001")
    with pytest.raises(ValueError, match=r"(not canonical|Invalid supplier ID)"):
        validate_canonical_supplier_id("invalid")


def test_legacy_inventory_id_to_canonical():
    assert legacy_id_to_canonical("SUP001") == "SUP-00001"
    assert legacy_id_to_canonical("SUP007") == "SUP-00007"
    assert legacy_id_to_canonical("SUP045") == "SUP-00045"
    assert legacy_id_to_canonical("SUP123") == "SUP-00123"
    assert legacy_id_to_canonical("SUP-00045") == "SUP-00045"
    assert legacy_id_to_canonical("INVALID") is None
    assert legacy_id_to_canonical("") is None


def test_normalize_supplier_name():
    assert normalize_supplier_name("  ALPHA   SANCTIONS  CORP. ") == "alpha sanctions corp"
    assert normalize_supplier_name("Apex Industries Pvt. Ltd.") == "apex industries pvt ltd"
    assert normalize_supplier_name("Unity Manufacturing GmbH") == "unity manufacturing gmbh"
    assert normalize_supplier_name("Evergreen Supplies Inc") == "evergreen supplies inc"


def test_deterministic_seed_catalog_integrity():
    assert len(DETERMINISTIC_SEED_SUPPLIERS) == 60

    # Check known critical suppliers from seed dataset
    by_id = {s["supplier_id"]: s for s in DETERMINISTIC_SEED_SUPPLIERS}

    # SUP-00007
    assert by_id["SUP-00007"]["name"] == "ALPHA SANCTIONS CORP"
    assert by_id["SUP-00007"]["sanctions_flag"] is True
    assert by_id["SUP-00007"]["sanctions_list"] == "OFAC-SDN"

    # SUP-00023
    assert by_id["SUP-00023"]["name"] == "TEST EU ENTITY 01"
    assert by_id["SUP-00023"]["sanctions_flag"] is True
    assert by_id["SUP-00023"]["sanctions_list"] == "EU-CONSOLIDATED"

    # SUP-00045
    assert by_id["SUP-00045"]["name"] == "TEST UN ENTITY 01"
    assert by_id["SUP-00045"]["sanctions_flag"] is True
    assert by_id["SUP-00045"]["sanctions_list"] == "UN-SC"


def test_resolve_canonical_supplier_by_id():
    rec = resolve_canonical_supplier("SUP-00045")
    assert rec is not None
    assert rec["supplier_id"] == "SUP-00045"
    assert rec["name"] == "TEST UN ENTITY 01"
    assert rec["sanctions_flag"] is True


def test_resolve_canonical_supplier_by_normalized_name():
    rec = resolve_canonical_supplier("ALPHA SANCTIONS CORP")
    assert rec is not None
    assert rec["supplier_id"] == "SUP-00007"

    rec2 = resolve_canonical_supplier("alpha sanctions corp")
    assert rec2 is not None
    assert rec2["supplier_id"] == "SUP-00007"


def test_resolve_canonical_supplier_by_legacy_id():
    # Legacy SUP045 should resolve to canonical SUP-00045
    rec = resolve_canonical_supplier("SUP045")
    assert rec is not None
    assert rec["supplier_id"] == "SUP-00045"
    assert rec["name"] == "TEST UN ENTITY 01"


def test_resolve_unknown_supplier_returns_none():
    assert resolve_canonical_supplier("SUP-99999") is None
    assert resolve_canonical_supplier("Nonexistent Supplier Corp") is None
    assert resolve_canonical_supplier_id("Nonexistent Supplier Corp") is None


def test_mongodb_seed_mappings_idempotency_with_mock_collection():
    """Verify MongoDB persistence, index creation, and idempotent upserts."""
    storage = {}

    mock_col = MagicMock()

    def mock_create_index(keys, **kwargs):
        return "index_created"

    def mock_update_one(filter_dict, update_dict, upsert=False):
        sid = filter_dict.get("supplier_id")
        is_new = sid not in storage
        storage[sid] = update_dict.get("$set", {})
        res = MagicMock()
        if is_new:
            res.upserted_id = sid
            res.modified_count = 0
        else:
            res.upserted_id = None
            res.modified_count = 1
        return res

    mock_col.create_index.side_effect = mock_create_index
    mock_col.update_one.side_effect = mock_update_one

    # First run: inserts
    stats1 = seed_supplier_mappings(collection=mock_col)
    assert stats1["inserted"] > 0
    assert stats1["failed"] == 0
    total_inserted = stats1["inserted"]

    # Second run: updates idempotently without creating duplicate keys
    stats2 = seed_supplier_mappings(collection=mock_col)
    assert stats2["inserted"] == 0
    assert stats2["updated"] == total_inserted
    assert stats2["failed"] == 0


def test_seed_rejects_invented_or_invalid_ids():
    mock_col = MagicMock()
    bad_records = [
        {"supplier_id": "SUP001", "name": "Legacy ID Record"},
        {"supplier_id": "INVALID", "name": "Bad ID Record"},
        {"supplier_id": "SUP-00099", "name": "Valid Canonical Record"},
    ]
    mock_col.update_one.return_value = MagicMock(upserted_id="SUP-00099", modified_count=0)

    stats = seed_supplier_mappings(records=bad_records, collection=mock_col)
    assert stats["total"] == 3
    assert stats["failed"] == 2
    assert stats["inserted"] == 1
