"""
Tests for Canonical Supplier ID mapping, normalization, and MongoDB persistence.
Validates Fix 1 requirements:
- Canonical supplier ID pattern ^SUP-\\d{5}$
- Rejection of invalid, legacy, or invented IDs
- An unknown supplier causes UnresolvedSupplierError
- No MD5-derived or fabricated supplier ID is returned
- Known suppliers continue resolving to their canonical IDs
- Hysteresis suppresses the transition and returns None when supplier is unresolved (reason: unresolved_supplier)
- Hysteresis suppresses the transition and returns None when MongoDB raises PyMongoError (reason: mapping_unavailable)
- A missing generated seed CSV raises FileNotFoundError with generation instructions
- No removed in-memory fallback or legacy mapping is still referenced
- Idempotent MongoDB persistence and index creation
"""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

from pymongo.errors import PyMongoError
import pytest

from src.events import (
    UnresolvedSupplierError,
    build_score_changed_event,
)
from src.hysteresis import (
    HysteresisConfig,
    SupplierHysteresisTracker,
)
from src.supplier_mapping import (
    CANONICAL_ID_REGEX,
    ensure_mapping_indexes,
    get_aliases_csv_path,
    get_default_seed_suppliers,
    is_canonical_supplier_id,
    load_supplier_aliases,
    normalize_supplier_name,
    parse_suppliers_csv,
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


def test_normalize_supplier_name():
    assert normalize_supplier_name("  ALPHA   SANCTIONS  CORP. ") == "alpha sanctions corp"
    assert normalize_supplier_name("Apex Industries Pvt. Ltd.") == "apex industries pvt ltd"
    assert normalize_supplier_name("Unity Manufacturing GmbH") == "unity manufacturing gmbh"
    assert normalize_supplier_name("Evergreen Supplies Inc") == "evergreen supplies inc"


def test_unknown_supplier_causes_unresolved_supplier_error():
    """An unknown supplier causes UnresolvedSupplierError in build_score_changed_event."""
    with pytest.raises(UnresolvedSupplierError, match=r"not in the seed supplier mapping"):
        build_score_changed_event(
            supplier="Unknown Supplier XYZ",
            previous_tier="low",
            new_tier="high",
            risk_score=85.0,
        )


def test_no_fabricated_or_md5_supplier_id():
    """No MD5-derived or fabricated supplier ID is returned for unseeded suppliers."""
    unseeded = [
        "Acme Corp",
        "Rank",
        "New",
        "Clock",
        "Noisy",
        "Boeing",
        "Tesla",
        "Random Fabricated Co",
        "SUP-99999",
    ]
    for name in unseeded:
        assert resolve_canonical_supplier_id(name) is None
        with pytest.raises(UnresolvedSupplierError):
            build_score_changed_event(
                supplier=name,
                previous_tier="low",
                new_tier="medium",
                risk_score=65.0,
            )


def test_known_suppliers_resolve_to_canonical_ids():
    """Known suppliers continue resolving to their canonical IDs."""
    # Direct canonical ID match in MongoDB
    rec = resolve_canonical_supplier("SUP-00045")
    assert rec is not None
    assert rec["supplier_id"] == "SUP-00045"
    assert rec["name"] == "TEST UN ENTITY 01"

    # Normalized name match in MongoDB
    assert resolve_canonical_supplier_id("ALPHA SANCTIONS CORP") == "SUP-00007"
    assert resolve_canonical_supplier_id("alpha sanctions corp") == "SUP-00007"
    assert resolve_canonical_supplier_id("Unity Manufacturing GmbH") == "SUP-00019"

    # build_score_changed_event succeeds for known supplier
    event = build_score_changed_event(
        supplier="ALPHA SANCTIONS CORP",
        previous_tier="low",
        new_tier="high",
        risk_score=85.0,
    )
    assert event["payload"]["supplier_id"] == "SUP-00007"


def test_resolve_unknown_supplier_returns_none():
    assert resolve_canonical_supplier("SUP-99999") is None
    assert resolve_canonical_supplier("Nonexistent Supplier Corp") is None
    assert resolve_canonical_supplier_id("Nonexistent Supplier Corp") is None


def test_hysteresis_suppresses_when_supplier_unresolved():
    """Hysteresis suppresses transition and returns None when supplier is unresolved (reason: unresolved_supplier)."""
    tracker = SupplierHysteresisTracker(config=HysteresisConfig(min_evidence=1))
    tracker.set_state("Unseeded Supplier Corp", tier="low", score=40.0)

    event = tracker.process_update(
        supplier="Unseeded Supplier Corp",
        risk_score=85.0,
        supporting_articles=[{"headline": "Major disruption", "score": 85.0}],
    )
    assert event is None
    state = tracker.get_state("Unseeded Supplier Corp")
    assert state.accepted_tier == "low"
    assert len(state.history) >= 2
    assert state.history[-1]["action"] == "suppressed"
    assert state.history[-1]["reason"] == "unresolved_supplier"
    assert state.history[-1]["candidate_tier"] == "high"


def test_hysteresis_suppresses_when_mongodb_raises_pymongo_error():
    """Hysteresis suppresses transition and returns None when MongoDB raises PyMongoError (reason: mapping_unavailable)."""
    tracker = SupplierHysteresisTracker(config=HysteresisConfig(min_evidence=1))
    tracker.set_state("ALPHA SANCTIONS CORP", tier="low", score=40.0)

    with patch(
        "src.supplier_mapping.get_supplier_mapping_collection",
        side_effect=PyMongoError("MongoDB connection lost"),
    ):
        event = tracker.process_update(
            supplier="ALPHA SANCTIONS CORP",
            risk_score=85.0,
            supporting_articles=[{"headline": "Sanctions update", "score": 85.0}],
        )
        assert event is None
        state = tracker.get_state("ALPHA SANCTIONS CORP")
        assert state.accepted_tier == "low"
        assert len(state.history) >= 2
        assert state.history[-1]["action"] == "suppressed"
        assert state.history[-1]["reason"] == "mapping_unavailable"
        assert state.history[-1]["candidate_tier"] == "high"


def test_missing_seed_csv_raises_file_not_found_with_instructions(tmp_path):
    """A missing generated seed CSV raises FileNotFoundError with generation instructions."""
    missing_path = tmp_path / "missing_suppliers.csv"

    with patch.dict(os.environ, {"SUPPLIER_SEED_CSV": str(missing_path)}):
        with pytest.raises(FileNotFoundError) as exc_info:
            get_default_seed_suppliers()

        msg = str(exc_info.value)
        assert "python -m seed.generate --out out/" in msg
        assert str(missing_path) in msg


def test_no_removed_in_memory_or_legacy_mapping_attributes():
    """Verify no removed in-memory fallback, cache, or legacy mapping is still referenced."""
    import src.supplier_mapping as sm
    import src.events as ev

    assert not hasattr(sm, "DETERMINISTIC_SEED_SUPPLIERS")
    assert not hasattr(sm, "LEGACY_INVENTORY_NAME_MAPPINGS")
    assert not hasattr(sm, "legacy_id_to_canonical")
    assert not hasattr(sm, "_IN_MEMORY_MAPPINGS")
    assert not hasattr(sm, "_IN_MEMORY_BY_NAME")
    assert not hasattr(sm, "_IN_MEMORY_BY_LEGACY")
    assert not hasattr(sm, "_populate_in_memory_cache")
    assert not hasattr(ev, "hashlib")
    assert not hasattr(ev, "test_known")


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

    sample_records = [
        {"supplier_id": "SUP-00001", "name": "Orion Supplies Inc", "country": "Thailand"},
        {"supplier_id": "SUP-00002", "name": "Driftwood Sourcing Pvt Ltd", "country": "India"},
    ]

    # First run: inserts
    stats1 = seed_supplier_mappings(records=sample_records, collection=mock_col)
    assert stats1["inserted"] == 2
    assert stats1["failed"] == 0

    # Second run: updates idempotently without creating duplicate keys
    stats2 = seed_supplier_mappings(records=sample_records, collection=mock_col)
    assert stats2["inserted"] == 0
    assert stats2["updated"] == 2
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


# ----------------------------------------------------------------------
# Fix 2: Explicit Supplier Alias Mapping Tests
# ----------------------------------------------------------------------

def test_alias_csv_loads_correctly(tmp_path):
    """Alias CSV with reviewed entries loads correctly."""
    csv_file = tmp_path / "supplier_aliases.csv"
    csv_file.write_text(
        "alias,supplier_id\n"
        "Foxconn,SUP-00019\n"
        "Hon Hai Precision,SUP-00019\n"
        "Apex Tech,SUP-00031\n",
        encoding="utf-8",
    )
    res = load_supplier_aliases(csv_file)
    assert res == {
        "Foxconn": "SUP-00019",
        "Hon Hai Precision": "SUP-00019",
        "Apex Tech": "SUP-00031",
    }


def test_header_only_alias_csv_produces_no_aliases_and_does_not_fail(tmp_path):
    """Header-only CSV produces no aliases and does not fail."""
    csv_file = tmp_path / "supplier_aliases.csv"
    csv_file.write_text("alias,supplier_id\n", encoding="utf-8")
    res = load_supplier_aliases(csv_file)
    assert res == {}


def test_invalid_canonical_ids_in_alias_csv_are_rejected(tmp_path):
    """Invalid canonical IDs in alias CSV are rejected with a clear error."""
    bad_csv_1 = tmp_path / "bad_1.csv"
    bad_csv_1.write_text("alias,supplier_id\nFoxconn,SUP019\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid canonical supplier_id"):
        load_supplier_aliases(bad_csv_1)

    bad_csv_2 = tmp_path / "bad_2.csv"
    bad_csv_2.write_text("alias,supplier_id\nFoxconn,INVALID-ID\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid canonical supplier_id"):
        load_supplier_aliases(bad_csv_2)


def test_malformed_and_duplicate_aliases_are_rejected(tmp_path):
    """Malformed rows and duplicate aliases in CSV are rejected."""
    # Empty alias
    empty_alias_csv = tmp_path / "empty_alias.csv"
    empty_alias_csv.write_text("alias,supplier_id\n,SUP-00019\n", encoding="utf-8")
    with pytest.raises(ValueError, match="alias cannot be empty"):
        load_supplier_aliases(empty_alias_csv)

    # Empty supplier_id
    empty_sid_csv = tmp_path / "empty_sid.csv"
    empty_sid_csv.write_text("alias,supplier_id\nFoxconn,\n", encoding="utf-8")
    with pytest.raises(ValueError, match="supplier_id cannot be empty"):
        load_supplier_aliases(empty_sid_csv)

    # Missing headers
    no_header_csv = tmp_path / "no_headers.csv"
    no_header_csv.write_text("name,id\nFoxconn,SUP-00019\n", encoding="utf-8")
    with pytest.raises(ValueError, match="required headers"):
        load_supplier_aliases(no_header_csv)

    # Duplicate alias
    dup_csv = tmp_path / "duplicate_alias.csv"
    dup_csv.write_text(
        "alias,supplier_id\n"
        "Foxconn,SUP-00019\n"
        "Foxconn,SUP-00021\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Duplicate alias"):
        load_supplier_aliases(dup_csv)


def test_canonical_id_resolution_takes_precedence():
    """Canonical supplier ID resolution takes precedence over name and aliases."""
    mock_col = MagicMock()
    doc_by_id = {"supplier_id": "SUP-00007", "name": "ALPHA SANCTIONS CORP", "aliases": []}
    mock_col.find_one.return_value = doc_by_id

    res = resolve_canonical_supplier("SUP-00007", collection=mock_col)
    assert res == doc_by_id
    mock_col.find_one.assert_called_with({"supplier_id": "SUP-00007"}, {"_id": 0})


def test_exact_seed_name_resolution_works():
    """Exact seed supplier name resolves cleanly."""
    mock_col = MagicMock()
    doc_by_name = {"supplier_id": "SUP-00019", "name": "Unity Manufacturing GmbH", "aliases": []}
    mock_col.find_one.return_value = doc_by_name

    res = resolve_canonical_supplier("Unity Manufacturing GmbH", collection=mock_col)
    assert res == doc_by_name


def test_exact_reviewed_alias_resolution_works():
    """Exact reviewed alias resolves to the canonical record."""
    mock_col = MagicMock()

    def mock_find_one(filter_dict, projection=None):
        if "aliases" in filter_dict and filter_dict["aliases"] == "Hon Hai Precision":
            return {"supplier_id": "SUP-00019", "name": "Unity Manufacturing GmbH", "aliases": ["Hon Hai Precision"]}
        return None

    mock_col.find_one.side_effect = mock_find_one

    res = resolve_canonical_supplier("Hon Hai Precision", collection=mock_col)
    assert res is not None
    assert res["supplier_id"] == "SUP-00019"
    assert res["name"] == "Unity Manufacturing GmbH"


def test_unknown_aliases_remain_unresolved_no_id_fabricated():
    """Unknown aliases remain unresolved; no supplier ID is fabricated or guessed."""
    mock_col = MagicMock()
    mock_col.find_one.return_value = None

    for unreviewed in ["Foxconn", "TSMC", "Maersk", "Unknown Article Vendor"]:
        res = resolve_canonical_supplier(unreviewed, collection=mock_col)
        assert res is None


def test_alias_persistence_and_idx_aliases_index_creation():
    """Verify alias persistence in document and idx_aliases index creation."""
    mock_col = MagicMock()
    created_indexes = []

    def mock_create_index(keys, **kwargs):
        name = kwargs.get("name", "idx")
        created_indexes.append(name)
        return name

    saved_docs = {}

    def mock_update_one(filter_dict, update_dict, upsert=False):
        sid = filter_dict["supplier_id"]
        saved_docs[sid] = update_dict["$set"]
        res = MagicMock()
        res.upserted_id = sid
        res.modified_count = 0
        return res

    mock_col.create_index.side_effect = mock_create_index
    mock_col.update_one.side_effect = mock_update_one

    sample_records = [
        {"supplier_id": "SUP-00019", "name": "Unity Manufacturing GmbH"},
    ]
    aliases = {"Foxconn": "SUP-00019", "Hon Hai": "SUP-00019"}

    ensure_mapping_indexes(mock_col)
    assert "idx_aliases" in created_indexes

    stats = seed_supplier_mappings(records=sample_records, aliases=aliases, collection=mock_col)
    assert stats["inserted"] == 1
    assert "SUP-00019" in saved_docs
    assert sorted(saved_docs["SUP-00019"]["aliases"]) == ["Foxconn", "Hon Hai"]


def test_unresolved_transitions_suppressed_and_retried():
    """Unresolved transitions are suppressed with reason unresolved_supplier, and later run retries."""
    tracker = SupplierHysteresisTracker(config=HysteresisConfig(min_evidence=1))
    tracker.set_state("Unreviewed Company", tier="low", score=40.0)

    # 1. Unreviewed company -> transition suppressed
    event1 = tracker.process_update(
        supplier="Unreviewed Company",
        risk_score=85.0,
        supporting_articles=[{"headline": "Critical event", "score": 85.0}],
    )
    assert event1 is None
    state = tracker.get_state("Unreviewed Company")
    assert state.accepted_tier == "low"
    assert state.history[-1]["reason"] == "unresolved_supplier"

    # 2. Later, company is reviewed or has valid canonical supplier_id provided -> succeeds
    event2 = tracker.process_update(
        supplier="Unreviewed Company",
        supplier_id="SUP-00019",
        risk_score=85.0,
        supporting_articles=[{"headline": "Critical event", "score": 85.0}],
    )
    assert event2 is not None
    assert event2["payload"]["supplier_id"] == "SUP-00019"
    assert event2["payload"]["new_tier"] == "high"


def test_missing_alias_csv_raises_file_not_found(tmp_path):
    """Missing alias CSV file raises FileNotFoundError explicitly."""
    missing_csv = tmp_path / "nonexistent_aliases.csv"
    with pytest.raises(FileNotFoundError, match="not found"):
        load_supplier_aliases(missing_csv)


def test_seed_supplier_mappings_rejects_conflicting_aliases_in_list():
    """Conflicting supplier IDs for the same alias in input list raise ValueError."""
    mock_col = MagicMock()
    conflicting_aliases = [
        {"alias": "Foxconn", "supplier_id": "SUP-00019"},
        {"alias": "Foxconn", "supplier_id": "SUP-00020"},
    ]
    with pytest.raises(ValueError, match="Duplicate alias 'Foxconn' assigned to conflicting suppliers"):
        seed_supplier_mappings(records=[], aliases=conflicting_aliases, collection=mock_col)


def test_seed_supplier_mappings_propagates_mongodb_errors():
    """PyMongoError during seed_supplier_mappings is not swallowed and bubbles up."""
    mock_col = MagicMock()
    mock_col.create_index.side_effect = PyMongoError("Index creation failed")

    with pytest.raises(PyMongoError, match="Index creation failed"):
        seed_supplier_mappings(records=[], collection=mock_col)


def test_seed_supplier_mappings_batch_duplicate_alias_skipped():
    """Duplicate alias within the same seeding batch is skipped for conflicting supplier."""
    mock_col = MagicMock()
    saved_docs = {}

    def mock_update_one(filter_dict, update_dict, upsert=False):
        sid = filter_dict["supplier_id"]
        saved_docs[sid] = update_dict["$set"]
        res = MagicMock()
        res.upserted_id = sid
        res.modified_count = 0
        return res

    mock_col.update_one.side_effect = mock_update_one
    mock_col.find_one.return_value = None

    records = [
        {"supplier_id": "SUP-00001", "name": "Company One", "aliases": ["SharedAlias"]},
        {"supplier_id": "SUP-00002", "name": "Company Two", "aliases": ["SharedAlias"]},
    ]

    seed_supplier_mappings(records=records, collection=mock_col)
    assert "SharedAlias" in saved_docs["SUP-00001"]["aliases"]
    assert "SharedAlias" not in saved_docs["SUP-00002"]["aliases"]


def test_mongodb_errors_not_swallowed():
    """PyMongoError in resolve_canonical_supplier is not swallowed and bubbles up."""
    mock_col = MagicMock()
    mock_col.find_one.side_effect = PyMongoError("MongoDB timeout")

    with pytest.raises(PyMongoError, match="MongoDB timeout"):
        resolve_canonical_supplier("Any Supplier", collection=mock_col)


@pytest.mark.parametrize("unresolved_value", ["National Suppliers", "ABC Supplies", "SUP045"])
def test_unresolved_values_do_not_resolve(unresolved_value):
    """Confirm National Suppliers, ABC Supplies, and SUP045 do not resolve."""
    assert resolve_canonical_supplier(unresolved_value) is None
    assert resolve_canonical_supplier_id(unresolved_value) is None


def test_resolve_canonical_supplier_propagates_mongodb_errors():
    """MongoDB errors propagate from resolve_canonical_supplier()."""
    with patch("src.supplier_mapping.get_supplier_mapping_collection") as mock_get_col:
        mock_col = MagicMock()
        mock_col.find_one.side_effect = PyMongoError("MongoDB read timeout")
        mock_get_col.return_value = mock_col
        with pytest.raises(PyMongoError, match="MongoDB read timeout"):
            resolve_canonical_supplier("SUP-00019")


def test_seed_supplier_mappings_propagates_mongodb_errors_from_operation():
    """MongoDB errors propagate from the seed operation."""
    with patch("src.supplier_mapping.get_supplier_mapping_collection") as mock_get_col:
        mock_col = MagicMock()
        mock_col.create_index.side_effect = PyMongoError("Index creation failed")
        mock_get_col.return_value = mock_col
        with pytest.raises(PyMongoError, match="Index creation failed"):
            seed_supplier_mappings(records=[])


def test_missing_seed_csv_raises_appropriate_error(tmp_path):
    """A missing seed CSV raises FileNotFoundError with appropriate generation instructions."""
    missing_csv = tmp_path / "nonexistent_seed.csv"
    with pytest.raises(FileNotFoundError, match=r"(Suppliers seed CSV file not found|python -m seed\.generate)"):
        parse_suppliers_csv(missing_csv)
    with pytest.raises(FileNotFoundError, match=r"(Suppliers seed CSV file not found|python -m seed\.generate)"):
        get_default_seed_suppliers(missing_csv)
    with patch.dict(os.environ, {"SUPPLIER_SEED_CSV": str(missing_csv)}):
        with pytest.raises(FileNotFoundError, match=r"(Suppliers seed CSV file not found|python -m seed\.generate)"):
            seed_supplier_mappings()


def test_csv_with_utf8_bom_parsed_correctly(tmp_path):
    """CSV files saved with UTF-8 BOM are cleanly parsed without mangled column headers."""
    seed_file = tmp_path / "suppliers_bom.csv"
    seed_content = "\ufeffsupplier_id,name,country,city,state,sanctions_flag,sanctions_list\nSUP-00099,BOM Supplier,US,Austin,TX,false,\n"
    seed_file.write_text(seed_content, encoding="utf-8")

    records = parse_suppliers_csv(seed_file)
    assert len(records) == 1
    assert records[0]["supplier_id"] == "SUP-00099"
    assert records[0]["name"] == "BOM Supplier"

    alias_file = tmp_path / "aliases_bom.csv"
    alias_content = "\ufeffalias,supplier_id\nBOM Alias,SUP-00099\n"
    alias_file.write_text(alias_content, encoding="utf-8")

    aliases = load_supplier_aliases(alias_file)
    assert aliases["BOM Alias"] == "SUP-00099"
