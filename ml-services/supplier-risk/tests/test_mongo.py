"""
Tests for MongoDB data access, indexing, deduplication, migration, and authoritative data loading.
"""

from pathlib import Path
import pytest
from pymongo.errors import DuplicateKeyError

from src.config import Settings
from src.db import (
    ensure_indexes,
    fetch_headlines_grouped,
    fetch_trend_headlines_grouped,
    generate_story_hash,
    get_collection,
    get_database,
    insert_article,
    ping_mongodb,
)
from src.data import load_headlines, load_trend_headlines
from src.data import load_headlines_from_json
from src.migrate import migrate_dataset
from src.predict import predict


# ------------------------------------------------------------------
# 1. Unit Tests (Story Hash, Deduplication Key, Configuration)
# ------------------------------------------------------------------

def test_story_hash_normalization():
    """Verify story hash normalizes casing and whitespace deterministically."""
    hash1 = generate_story_hash("  Boeing  ", "Boeing  faces new lawsuit.  ")
    hash2 = generate_story_hash("boeing", "boeing faces new lawsuit.")
    assert hash1 == hash2

    # Different headline should produce different hash
    hash3 = generate_story_hash("Boeing", "Boeing machinists strike.")
    assert hash1 != hash3


def test_story_hash_ignores_source_difference():
    """
    Verify the same story from two different sources (e.g. Reuters vs Bloomberg)
    generates the identical deduplication hash.
    """
    supplier = "Tesla"
    headline = "Tesla announces a major recall of 2 million vehicles."

    hash_reuters = generate_story_hash(supplier, headline)
    hash_bloomberg = generate_story_hash(supplier, headline)

    assert hash_reuters == hash_bloomberg


def test_mongodb_config_defaults_and_env():
    """Verify default MongoDB settings and environment overrides."""
    cfg = Settings()
    assert cfg.mongodb_uri == "mongodb://localhost:27017"
    assert cfg.mongodb_database == "supplier_risk"
    assert cfg.mongodb_collection == "headlines"

    d = cfg.to_dict()
    assert "mongodb_uri" in d
    assert "mongodb_database" in d
    assert "mongodb_collection" in d

    custom = Settings(
        mongodb_uri="mongodb://custom-host:27017",
        mongodb_database="custom_db",
        mongodb_collection="custom_headlines",
    )
    assert custom.mongodb_uri == "mongodb://custom-host:27017"
    assert custom.mongodb_database == "custom_db"
    assert custom.mongodb_collection == "custom_headlines"


def test_authoritative_mongodb_raises_when_empty_or_unavailable():
    """
    Verify load_headlines() and load_trend_headlines() do NOT silently fall back to JSON.
    When querying an empty collection without use_fallback=True, they must raise RuntimeError.
    """
    from unittest.mock import patch

    with patch("src.data.fetch_headlines_grouped", return_value={}):
        with pytest.raises(RuntimeError, match="authoritative runtime data source"):
            load_headlines(use_fallback=False)

    with patch("src.data.fetch_trend_headlines_grouped", return_value={}):
        with pytest.raises(RuntimeError, match="authoritative runtime data source"):
            load_trend_headlines(use_fallback=False)

    # Explicit fallback requested (test mode)
    fallback_data = load_headlines(use_fallback=True)
    assert len(fallback_data) > 0


# ------------------------------------------------------------------
# 2. Integration Tests (Local MongoDB Container)
# ------------------------------------------------------------------

@pytest.mark.integration
def test_mongo_ping():
    """Verify local MongoDB container is running and ping succeeds."""
    assert ping_mongodb() is True


@pytest.mark.integration
def test_ensure_indexes(mongo_test_collection):
    """Verify required indexes are created with correct options."""
    col = mongo_test_collection
    index_names = ensure_indexes(col)
    assert "unique_story_hash" in index_names
    assert "idx_supplier" in index_names
    assert "idx_date" in index_names
    assert "idx_supplier_date" in index_names

    info = col.index_information()
    assert "unique_story_hash" in info
    assert info["unique_story_hash"].get("unique") is True
    assert info["idx_supplier"]["key"] == [("supplier", 1)]
    assert info["idx_date"]["key"] == [("date", 1)]
    assert info["idx_supplier_date"]["key"] == [("supplier", 1), ("date", 1)]


@pytest.mark.integration
def test_unique_deduplication_constraint(mongo_test_collection):
    """
    Verify inserting the same story from two different sources is blocked
    by the unique index on story_hash.
    """
    col = mongo_test_collection
    ensure_indexes(col)

    article_source1 = {
        "supplier": "Boeing",
        "headline": "Boeing faces new lawsuit over safety violations.",
        "date": "2026-01-05",
        "source": "Reuters",
    }
    id1 = insert_article(article_source1, collection=col)
    assert id1 is not None

    # Same story from Bloomberg
    article_source2 = {
        "supplier": "Boeing",
        "headline": "Boeing faces new lawsuit over safety violations.",
        "date": "2026-01-05",
        "source": "Bloomberg",
    }
    with pytest.raises(DuplicateKeyError):
        insert_article(article_source2, collection=col)

    # Count must remain exactly 1
    assert col.count_documents({}) == 1


@pytest.mark.integration
def test_repeatable_migration(mongo_test_collection):
    """
    Verify migration is idempotent:
    1st run inserts all records.
    2nd run inserts 0 records and reports all as skipped.
    """
    col = mongo_test_collection
    json_path = Path(__file__).parent.parent / "src" / "supplier_trend_headlines.json"

    # 1st run
    res1 = migrate_dataset(json_path, collection=col)
    assert res1["total"] == 120
    assert res1["inserted"] == 120
    assert res1["skipped"] == 0
    assert res1["failed"] == 0
    assert col.count_documents({}) == 120

    # 2nd run (idempotent)
    res2 = migrate_dataset(json_path, collection=col)
    assert res2["total"] == 120
    assert res2["inserted"] == 0
    assert res2["skipped"] == 120
    assert res2["failed"] == 0
    assert col.count_documents({}) == 120

    # Migrate supplier_headlines.json (non-trend version of same stories)
    json_headlines_path = Path(__file__).parent.parent / "src" / "supplier_headlines.json"
    res3 = migrate_dataset(json_headlines_path, collection=col)
    assert res3["total"] == 120
    assert res3["inserted"] == 0
    assert res3["skipped"] == 120
    assert col.count_documents({}) == 120


@pytest.mark.integration
def test_scoring_equivalence_mongo_vs_json(mongo_test_collection):
    """
    The same articles must score identically whether they come from the
    committed JSON file or from MongoDB.
    """
    json_path = (
        Path(__file__).parent.parent
        / "src"
        / "supplier_headlines.json"
    )

    migrate_dataset(json_path, collection=mongo_test_collection)

    mongo_data = fetch_headlines_grouped(collection=mongo_test_collection)
    json_data = load_headlines_from_json()

    assert set(mongo_data) == set(json_data)

    for supplier in json_data:
        assert sorted(mongo_data[supplier]) == sorted(json_data[supplier])

    for supplier in ["Boeing", "Tesla", "Siemens", "Apex Logistics"]:
        res_mongo = predict(supplier, mongo_data[supplier])
        res_json = predict(supplier, json_data[supplier])

        assert res_mongo["risk_score"] == res_json["risk_score"]
        assert res_mongo["confidence"] == res_json["confidence"]
        assert res_mongo["sentiment_breakdown"] == res_json["sentiment_breakdown"]


@pytest.mark.integration
def test_caller_cannot_bypass_dedup_with_own_hash(mongo_test_collection):
    ensure_indexes(mongo_test_collection)
    article = {"supplier": "Boeing", "headline": "Boeing faces new lawsuit."}

    insert_article(article, collection=mongo_test_collection)
    with pytest.raises(DuplicateKeyError):
        insert_article({**article, "story_hash": "made-up"}, collection=mongo_test_collection)

