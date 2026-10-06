"""
MongoDB data access module for the Supplier Risk NLP pipeline.

Provides client connection management, index creation, story identity hashing,
article insertion with deduplication enforcement, and querying for scoring pipelines.
"""

from datetime import datetime, timezone
import hashlib
import logging
from typing import Any, Dict, List, Optional

import pymongo
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import ConnectionFailure, DuplicateKeyError, ServerSelectionTimeoutError

from src.config import get_settings

logger = logging.getLogger(__name__)

_CLIENT_CACHE: Dict[str, pymongo.MongoClient] = {}


def get_mongo_client(
    uri: Optional[str] = None,
    server_selection_timeout_ms: int = 3000,
) -> pymongo.MongoClient:
    """
    Get or create a cached MongoClient instance for the given URI.
    Uses short serverSelectionTimeoutMS to fail fast when MongoDB is unreachable.
    """
    target_uri = uri or get_settings().mongodb_uri
    if target_uri not in _CLIENT_CACHE:
        _CLIENT_CACHE[target_uri] = pymongo.MongoClient(
            target_uri,
            serverSelectionTimeoutMS=server_selection_timeout_ms,
        )
    return _CLIENT_CACHE[target_uri]


def get_database(
    db_name: Optional[str] = None,
    uri: Optional[str] = None,
) -> Database:
    """
    Retrieve the MongoDB Database instance.
    """
    client = get_mongo_client(uri)
    target_db = db_name or get_settings().mongodb_database
    return client[target_db]


def get_collection(
    collection_name: Optional[str] = None,
    db_name: Optional[str] = None,
    uri: Optional[str] = None,
) -> Collection:
    """
    Retrieve the headlines collection instance.
    """
    db = get_database(db_name, uri)
    target_collection = collection_name or get_settings().mongodb_collection
    return db[target_collection]


def ping_mongodb(uri: Optional[str] = None) -> bool:
    """
    Ping the MongoDB instance to verify connectivity.
    Returns True if reachable; raises ConnectionError if unreachable.
    """
    client = get_mongo_client(uri)
    try:
        res = client.admin.command("ping")
        return bool(res.get("ok", 0.0) == 1.0)
    except (ConnectionFailure, ServerSelectionTimeoutError) as exc:
        raise ConnectionError(
            f"Failed to connect to MongoDB at '{uri or get_settings().mongodb_uri}': {exc}"
        ) from exc


def generate_story_hash(supplier: str, headline: str) -> str:
    """
    Generate a deterministic SHA-256 identity for deduplication.

    Normalizes:
    - supplier: lowercase, strip, collapsed whitespace
    - headline: lowercase, strip, collapsed whitespace

    Note: The story source (e.g. 'Reuters' vs 'Bloomberg') is deliberately excluded
    from the hash so the same story reported from different sources counts only once.
    """
    norm_supplier = " ".join(supplier.strip().lower().split())
    norm_headline = " ".join(headline.strip().lower().split())
    composite = f"{norm_supplier}::{norm_headline}"
    return hashlib.sha256(composite.encode("utf-8")).hexdigest()


def ensure_indexes(collection: Optional[Collection] = None) -> List[str]:
    """
    Create required indexes on the headlines collection:
    1. unique_story_hash: unique index on story_hash for deduplication
    2. idx_supplier: index on supplier for supplier lookups
    3. idx_date: index on date for timeline/trend filtering
    4. idx_supplier_date: compound index on (supplier, date) for chronological queries

    Returns:
        List[str]: Names of created or existing indexes.
    """
    col = collection if collection is not None else get_collection()

    created: List[str] = []

    # 1. Deduplication Unique Index
    idx_story = col.create_index(
        [("story_hash", pymongo.ASCENDING)],
        unique=True,
        name="unique_story_hash",
    )
    created.append(idx_story)

    # 2. Supplier Index
    idx_sup = col.create_index(
        [("supplier", pymongo.ASCENDING)],
        name="idx_supplier",
    )
    created.append(idx_sup)

    # 3. Date Index
    idx_dt = col.create_index(
        [("date", pymongo.ASCENDING)],
        name="idx_date",
    )
    created.append(idx_dt)

    # 4. Compound Supplier + Date Index
    idx_sup_dt = col.create_index(
        [("supplier", pymongo.ASCENDING), ("date", pymongo.ASCENDING)],
        name="idx_supplier_date",
    )
    created.append(idx_sup_dt)

    return created


def insert_article(
    doc: Dict[str, Any],
    collection: Optional[Collection] = None,
) -> str:
    """
    Insert a raw article record into MongoDB with deterministic deduplication key.

    Args:
        doc: Dict containing at least 'supplier' and 'headline'.
             May also contain 'date' and 'source'.
        collection: Optional target collection.

    Returns:
        str: String representation of inserted ObjectId.

    Raises:
        DuplicateKeyError: If an article with the same story_hash already exists.
        ValueError: If 'supplier' or 'headline' is missing or empty.
    """
    col = collection if collection is not None else get_collection()

    supplier = doc.get("supplier")
    headline = doc.get("headline")

    if not supplier or not isinstance(supplier, str) or not supplier.strip():
        raise ValueError("Article record must contain non-empty 'supplier'")
    if not headline or not isinstance(headline, str) or not headline.strip():
        raise ValueError("Article record must contain non-empty 'headline'")

    record = dict(doc)
    record["story_hash"] = generate_story_hash(supplier, headline)

    if "created_at" not in record:
        record["created_at"] = datetime.now(timezone.utc)

    result = col.insert_one(record)
    return str(result.inserted_id)


def fetch_headlines_grouped(
    supplier: Optional[str] = None,
    collection: Optional[Collection] = None,
) -> Dict[str, List[str]]:
    """
    Fetch raw headlines from MongoDB grouped by supplier.
    Used by normal scoring pipelines.

    Args:
        supplier: Optional supplier name filter.
        collection: Optional target collection.

    Returns:
        Dict[str, List[str]]: Mapping from supplier name to list of headlines.
    """
    col = collection if collection is not None else get_collection()
    query: Dict[str, Any] = {}
    if supplier:
        query["supplier"] = supplier

    cursor = col.find(
        query,
        {"supplier": 1, "headline": 1, "story_hash": 1, "_id": 0},
    ).sort([("created_at", pymongo.ASCENDING), ("_id", pymongo.ASCENDING)])

    grouped: Dict[str, List[str]] = {}
    seen_hashes: set = set()

    for doc in cursor:
        sup = doc.get("supplier")
        head = doc.get("headline")
        shash = doc.get("story_hash")

        if not sup or not head:
            continue

        # In-memory safeguard for deduplication
        if shash and shash in seen_hashes:
            continue
        if shash:
            seen_hashes.add(shash)

        grouped.setdefault(sup, []).append(head)

    return grouped


def fetch_trend_headlines_grouped(
    supplier: Optional[str] = None,
    collection: Optional[Collection] = None,
) -> Dict[str, List[Dict[str, str]]]:
    """
    Fetch date-aware headlines from MongoDB grouped by supplier, ordered chronologically.
    Used by trend scoring pipelines.

    Args:
        supplier: Optional supplier name filter.
        collection: Optional target collection.

    Returns:
        Dict[str, List[Dict[str, str]]]:
            Mapping from supplier name to list of [{'date': ..., 'headline': ...}].
    """
    col = collection if collection is not None else get_collection()
    query: Dict[str, Any] = {"date": {"$ne": None, "$exists": True}}
    if supplier:
        query["supplier"] = supplier

    cursor = col.find(
        query,
        {"supplier": 1, "date": 1, "headline": 1, "story_hash": 1, "_id": 0},
    ).sort([("date", pymongo.ASCENDING), ("_id", pymongo.ASCENDING)])

    grouped: Dict[str, List[Dict[str, str]]] = {}
    seen_hashes: set = set()

    for doc in cursor:
        sup = doc.get("supplier")
        date_val = doc.get("date")
        head = doc.get("headline")
        shash = doc.get("story_hash")

        if not sup or not date_val or not head:
            continue

        if shash and shash in seen_hashes:
            continue
        if shash:
            seen_hashes.add(shash)

        grouped.setdefault(sup, []).append(
            {
                "date": str(date_val),
                "headline": str(head),
            }
        )

    return grouped
