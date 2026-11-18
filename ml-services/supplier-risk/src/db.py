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


def get_risk_assessments_collection(
    collection_name: str = "risk_assessments",
    db_name: Optional[str] = None,
    uri: Optional[str] = None,
) -> Collection:
    """Retrieve the risk_assessments MongoDB collection instance."""
    db = get_database(db_name, uri)
    return db[collection_name]


def ensure_risk_assessment_indexes(collection: Optional[Collection] = None) -> List[str]:
    """
    Create required indexes on the risk_assessments collection:
    1. unique_assessment_supplier_id: unique index on supplier_id.
    2. idx_assessment_computed_at: index on computed_at for audit queries.
    """
    col = collection if collection is not None else get_risk_assessments_collection()
    created: List[str] = []

    idx_sid = col.create_index(
        [("supplier_id", pymongo.ASCENDING)],
        unique=True,
        name="unique_assessment_supplier_id",
    )
    created.append(idx_sid)

    idx_computed = col.create_index(
        [("computed_at", pymongo.DESCENDING)],
        name="idx_assessment_computed_at",
    )
    created.append(idx_computed)

    return created


def save_risk_assessment(
    doc: Dict[str, Any],
    collection: Optional[Collection] = None,
) -> str:
    """
    Upsert a computed supplier risk assessment into MongoDB.
    """
    col = collection if collection is not None else get_risk_assessments_collection()
    ensure_risk_assessment_indexes(col)

    supplier_id = doc.get("supplier_id")
    if not supplier_id:
        raise ValueError("Risk assessment document must contain 'supplier_id'")

    record = dict(doc)
    record["updated_at"] = datetime.now(timezone.utc)

    col.update_one(
        {"supplier_id": supplier_id},
        {
            "$set": record,
            "$setOnInsert": {"created_at": datetime.now(timezone.utc)},
        },
        upsert=True,
    )
    return supplier_id


def fetch_risk_assessment(
    supplier_id: str,
    collection: Optional[Collection] = None,
) -> Optional[Dict[str, Any]]:
    """
    Retrieve the latest computed risk assessment for a canonical supplier ID.
    """
    col = collection if collection is not None else get_risk_assessments_collection()
    return col.find_one({"supplier_id": supplier_id}, {"_id": 0})


# ------------------------------------------------------------------
# Client Supplier Master and Incident Collections (Issue #350)
# ------------------------------------------------------------------

def get_client_suppliers_collection(
    collection_name: Optional[str] = None,
    db_name: Optional[str] = None,
    uri: Optional[str] = None,
) -> Collection:
    """Retrieve the client_suppliers MongoDB collection instance."""
    db = get_database(db_name, uri)
    target = collection_name or get_settings().mongodb_client_suppliers_collection
    return db[target]


def get_client_incidents_collection(
    collection_name: Optional[str] = None,
    db_name: Optional[str] = None,
    uri: Optional[str] = None,
) -> Collection:
    """Retrieve the client_incidents MongoDB collection instance."""
    db = get_database(db_name, uri)
    target = collection_name or get_settings().mongodb_client_incidents_collection
    return db[target]


def ensure_client_data_indexes(
    suppliers_col: Optional[Collection] = None,
    incidents_col: Optional[Collection] = None,
) -> Dict[str, List[str]]:
    """
    Create required indexes on client supplier master and incident collections:
    - client_suppliers:
        1. idx_client_supplier_id: index on supplier_id
        2. idx_client_supplier_code: index on supplier_code
    - client_incidents:
        1. idx_incident_supplier_id: index on supplier_id
        2. idx_incident_supplier_code: index on supplier_code
        3. idx_incident_date: index on incident_date
        4. idx_incident_supplier_date: compound index on (supplier_id, incident_date)
        5. idx_incident_code_date: compound index on (supplier_code, incident_date)
    """
    scol = suppliers_col if suppliers_col is not None else get_client_suppliers_collection()
    icol = incidents_col if incidents_col is not None else get_client_incidents_collection()

    created_suppliers: List[str] = []
    created_incidents: List[str] = []

    # Supplier master indexes
    idx_sid = scol.create_index([("supplier_id", pymongo.ASCENDING)], name="idx_client_supplier_id")
    created_suppliers.append(idx_sid)

    idx_scode = scol.create_index([("supplier_code", pymongo.ASCENDING)], name="idx_client_supplier_code")
    created_suppliers.append(idx_scode)

    # Incident indexes
    idx_isid = icol.create_index([("supplier_id", pymongo.ASCENDING)], name="idx_incident_supplier_id")
    created_incidents.append(idx_isid)

    idx_iscode = icol.create_index([("supplier_code", pymongo.ASCENDING)], name="idx_incident_supplier_code")
    created_incidents.append(idx_iscode)

    idx_idate = icol.create_index([("incident_date", pymongo.ASCENDING)], name="idx_incident_date")
    created_incidents.append(idx_idate)

    idx_icomp = icol.create_index(
        [("supplier_id", pymongo.ASCENDING), ("incident_date", pymongo.ASCENDING)],
        name="idx_incident_supplier_date",
    )
    created_incidents.append(idx_icomp)

    idx_icode_comp = icol.create_index(
        [("supplier_code", pymongo.ASCENDING), ("incident_date", pymongo.ASCENDING)],
        name="idx_incident_code_date",
    )
    created_incidents.append(idx_icode_comp)

    return {"suppliers": created_suppliers, "incidents": created_incidents}


_client_indexes_ensured: bool = False


def ensure_client_data_indexes_once(
    suppliers_col: Optional[Collection] = None,
    incidents_col: Optional[Collection] = None,
) -> Dict[str, List[str]]:
    """
    Ensure client data indexes are created once per process lifetime,
    avoiding unnecessary repeated index creation calls.
    """
    global _client_indexes_ensured
    if not _client_indexes_ensured:
        res = ensure_client_data_indexes(suppliers_col=suppliers_col, incidents_col=incidents_col)
        _client_indexes_ensured = True
        return res
    return {"suppliers": [], "incidents": []}


def fetch_client_supplier(
    identifier: str,
    collection: Optional[Collection] = None,
) -> Optional[Dict[str, Any]]:
    """
    Fetch a client supplier master record by canonical supplier_id or supplier_code.
    """
    if not identifier or not isinstance(identifier, str):
        return None
    clean = identifier.strip()
    col = collection if collection is not None else get_client_suppliers_collection()
    return col.find_one(
        {"$or": [{"supplier_id": clean.upper()}, {"supplier_code": clean}, {"supplier_code": clean.upper()}]},
        {"_id": 0},
    )


def fetch_client_incidents(
    identifier: str,
    collection: Optional[Collection] = None,
) -> List[Dict[str, Any]]:
    """
    Fetch all incidents for a given supplier by supplier_id or supplier_code.
    """
    if not identifier or not isinstance(identifier, str):
        return []
    clean = identifier.strip()
    col = collection if collection is not None else get_client_incidents_collection()
    cursor = col.find(
        {"$or": [{"supplier_id": clean.upper()}, {"supplier_code": clean}, {"supplier_code": clean.upper()}]},
        {"_id": 0},
    )
    return list(cursor)


def save_client_supplier(
    doc: Dict[str, Any],
    collection: Optional[Collection] = None,
) -> str:
    """
    Upsert a client supplier master record into MongoDB.
    """
    col = collection if collection is not None else get_client_suppliers_collection()
    supplier_id = doc.get("supplier_id")
    supplier_code = doc.get("supplier_code")
    if not supplier_id and not supplier_code:
        raise ValueError("Client supplier record must contain 'supplier_id' or 'supplier_code'")

    record = dict(doc)
    record["updated_at"] = datetime.now(timezone.utc)

    filter_query: Dict[str, Any]
    if supplier_id and supplier_code:
        filter_query = {"$or": [{"supplier_id": supplier_id}, {"supplier_code": supplier_code}]}
    elif supplier_id:
        filter_query = {"supplier_id": supplier_id}
    else:
        filter_query = {"supplier_code": supplier_code}

    col.update_one(
        filter_query,
        {"$set": record, "$setOnInsert": {"created_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    return str(supplier_id or supplier_code)


def save_client_incident(
    doc: Dict[str, Any],
    collection: Optional[Collection] = None,
) -> str:
    """
    Insert a client supplier incident into MongoDB.
    """
    col = collection if collection is not None else get_client_incidents_collection()
    record = dict(doc)
    if "created_at" not in record:
        record["created_at"] = datetime.now(timezone.utc)
    res = col.insert_one(record)
    return str(res.inserted_id)


def save_client_incidents(
    docs: List[Dict[str, Any]],
    collection: Optional[Collection] = None,
) -> int:
    """
    Batch insert client supplier incidents into MongoDB.
    """
    if not docs:
        return 0
    col = collection if collection is not None else get_client_incidents_collection()
    now = datetime.now(timezone.utc)
    records = []
    for d in docs:
        rec = dict(d)
        if "created_at" not in rec:
            rec["created_at"] = now
        records.append(rec)
    res = col.insert_many(records)
    return len(res.inserted_ids)
