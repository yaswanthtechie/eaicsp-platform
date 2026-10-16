"""
Canonical Supplier ID mapping and resolution module.

Provides deterministic mapping from supplier names and legacy identifiers
to canonical supplier IDs (SUP-XXXXX) per Integration Blueprint Section 2.
Persists mappings in MongoDB with uniqueness constraints and indexes.
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import logging
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple

import pymongo
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError

from src.db import get_collection, get_database

logger = logging.getLogger(__name__)

CANONICAL_SUPPLIER_ID_PATTERN: str = r"^SUP-\d{5}$"
CANONICAL_ID_REGEX = re.compile(CANONICAL_SUPPLIER_ID_PATTERN)
LEGACY_INVENTORY_ID_REGEX = re.compile(r"^SUP\d{3}$")

# ------------------------------------------------------------------
# Deterministic Master Seed Catalog (60 canonical suppliers)
# Exactly matching Vivek's data-platform/seed generator (seed=42).
# Ensures deterministic fallback availability even when CSVs are absent.
# ------------------------------------------------------------------
DETERMINISTIC_SEED_SUPPLIERS: List[Dict[str, Any]] = [
    {"supplier_id": "SUP-00001", "name": "Orion Supplies Inc", "country": "Thailand"},
    {"supplier_id": "SUP-00002", "name": "Driftwood Sourcing Pvt Ltd", "country": "India"},
    {"supplier_id": "SUP-00003", "name": "Quartz Sourcing Co", "country": "Taiwan"},
    {"supplier_id": "SUP-00004", "name": "Evergreen Wholesale Pvt Ltd", "country": "India"},
    {"supplier_id": "SUP-00005", "name": "Zenith Manufacturing Co", "country": "Malaysia"},
    {"supplier_id": "SUP-00006", "name": "Orion Exports LLP", "country": "India"},
    {"supplier_id": "SUP-00007", "name": "ALPHA SANCTIONS CORP", "country": "Russia", "sanctions_flag": True, "sanctions_list": "OFAC-SDN"},
    {"supplier_id": "SUP-00008", "name": "Tidal Industries Inc", "country": "UAE"},
    {"supplier_id": "SUP-00009", "name": "Meridian Enterprises Pvt Ltd", "country": "India"},
    {"supplier_id": "SUP-00010", "name": "Willow Traders Co", "country": "Thailand"},
    {"supplier_id": "SUP-00011", "name": "Vertex Exports Ltd", "country": "Germany"},
    {"supplier_id": "SUP-00012", "name": "Ironwood Exports Co", "country": "Thailand"},
    {"supplier_id": "SUP-00013", "name": "Meridian Wholesale Pvt Ltd", "country": "India"},
    {"supplier_id": "SUP-00014", "name": "Apex Distribution LLP", "country": "Taiwan"},
    {"supplier_id": "SUP-00015", "name": "Falcon Supplies LLP", "country": "Malaysia"},
    {"supplier_id": "SUP-00016", "name": "Summit Sourcing Ltd", "country": "India"},
    {"supplier_id": "SUP-00017", "name": "Granite Logistics LLP", "country": "India"},
    {"supplier_id": "SUP-00018", "name": "Lotus Wholesale Co", "country": "India"},
    {"supplier_id": "SUP-00019", "name": "Unity Manufacturing GmbH", "country": "India"},
    {"supplier_id": "SUP-00020", "name": "Harbor Wholesale GmbH", "country": "India"},
    {"supplier_id": "SUP-00021", "name": "Evergreen Supplies GmbH", "country": "Thailand"},
    {"supplier_id": "SUP-00022", "name": "Bluepeak Enterprises Inc", "country": "Taiwan"},
    {"supplier_id": "SUP-00023", "name": "TEST EU ENTITY 01", "country": "Iran", "sanctions_flag": True, "sanctions_list": "EU-CONSOLIDATED"},
    {"supplier_id": "SUP-00024", "name": "Cedar Traders Inc", "country": "India"},
    {"supplier_id": "SUP-00025", "name": "Redwood Manufacturing Ltd", "country": "China"},
    {"supplier_id": "SUP-00026", "name": "Pioneer Logistics Co", "country": "India"},
    {"supplier_id": "SUP-00027", "name": "Juniper Sourcing LLP", "country": "China"},
    {"supplier_id": "SUP-00028", "name": "Ironwood Sourcing LLP", "country": "India"},
    {"supplier_id": "SUP-00029", "name": "Keystone Sourcing Ltd", "country": "China"},
    {"supplier_id": "SUP-00030", "name": "Summit Manufacturing Inc", "country": "India"},
    {"supplier_id": "SUP-00031", "name": "Apex Industries Pvt Ltd", "country": "India"},
    {"supplier_id": "SUP-00032", "name": "Falcon Wholesale Inc", "country": "India"},
    {"supplier_id": "SUP-00033", "name": "Bluepeak Traders Co", "country": "China"},
    {"supplier_id": "SUP-00034", "name": "Meridian Sourcing Pvt Ltd", "country": "India"},
    {"supplier_id": "SUP-00035", "name": "Quartz Traders Co", "country": "India"},
    {"supplier_id": "SUP-00036", "name": "Summit Industries Inc", "country": "India"},
    {"supplier_id": "SUP-00037", "name": "Vertex Sourcing Pvt Ltd", "country": "India"},
    {"supplier_id": "SUP-00038", "name": "Lotus Logistics Inc", "country": "India"},
    {"supplier_id": "SUP-00039", "name": "Willow Manufacturing Co", "country": "Germany"},
    {"supplier_id": "SUP-00040", "name": "Harbor Sourcing Co", "country": "India"},
    {"supplier_id": "SUP-00041", "name": "Granite Distribution Ltd", "country": "India"},
    {"supplier_id": "SUP-00042", "name": "Zenith Wholesale Inc", "country": "India"},
    {"supplier_id": "SUP-00043", "name": "Cedar Logistics Inc", "country": "India"},
    {"supplier_id": "SUP-00044", "name": "Pioneer Exports Co", "country": "India"},
    {"supplier_id": "SUP-00045", "name": "TEST UN ENTITY 01", "country": "Belarus", "sanctions_flag": True, "sanctions_list": "UN-SC"},
    {"supplier_id": "SUP-00046", "name": "Driftwood Wholesale Co", "country": "India"},
    {"supplier_id": "SUP-00047", "name": "Orion Traders Co", "country": "India"},
    {"supplier_id": "SUP-00048", "name": "Bluepeak Supplies Pvt Ltd", "country": "India"},
    {"supplier_id": "SUP-00049", "name": "Falcon Logistics Ltd", "country": "Vietnam"},
    {"supplier_id": "SUP-00050", "name": "Lotus Manufacturing Co", "country": "India"},
    {"supplier_id": "SUP-00051", "name": "Keystone Manufacturing Pvt Ltd", "country": "India"},
    {"supplier_id": "SUP-00052", "name": "Quartz Supplies Co", "country": "India"},
    {"supplier_id": "SUP-00053", "name": "Apex Logistics Co", "country": "India"},
    {"supplier_id": "SUP-00054", "name": "Willow Supplies Pvt Ltd", "country": "India"},
    {"supplier_id": "SUP-00055", "name": "Vertex Supplies Co", "country": "India"},
    {"supplier_id": "SUP-00056", "name": "Tidal Industries LLP", "country": "UAE"},
    {"supplier_id": "SUP-00057", "name": "Zenith Traders Co", "country": "India"},
    {"supplier_id": "SUP-00058", "name": "Granite Sourcing Co", "country": "India"},
    {"supplier_id": "SUP-00059", "name": "Nimbus Sourcing Co", "country": "India"},
    {"supplier_id": "SUP-00060", "name": "Redwood Traders Ltd", "country": "India"},
]

# Legacy inventory supplier name compatibility mapping
LEGACY_INVENTORY_NAME_MAPPINGS: Dict[str, str] = {
    "abc supplies": "SUP-00001",
    "global traders": "SUP-00002",
    "prime distributors": "SUP-00003",
    "fast supply co": "SUP-00004",
    "office supply partners": "SUP-00005",
    "reliable wholesale": "SUP-00006",
    "national suppliers": "SUP-00007",
    "metro distributors": "SUP-00008",
    "universal traders": "SUP-00009",
    "best source ltd": "SUP-00010",
}


def is_canonical_supplier_id(supplier_id: Any) -> bool:
    """Return True if supplier_id strictly matches '^SUP-[0-9]{5}$'."""
    if not isinstance(supplier_id, str):
        return False
    return bool(CANONICAL_ID_REGEX.match(supplier_id.strip()))


def validate_canonical_supplier_id(supplier_id: Any) -> str:
    """
    Validate canonical supplier identifier.

    Raises:
        ValueError: If identifier does not match '^SUP-[0-9]{5}$'.
    """
    if not isinstance(supplier_id, str):
        raise ValueError(f"Supplier ID must be a string, got {type(supplier_id).__name__}")
    clean = supplier_id.strip().upper()
    if not CANONICAL_ID_REGEX.match(clean):
        if LEGACY_INVENTORY_ID_REGEX.match(clean):
            raise ValueError(
                f"Legacy supplier ID '{clean}' is not canonical. "
                f"Canonical IDs require 'SUP-' followed by 5 digits (e.g. 'SUP-{int(clean[3:]):05d}')."
            )
        raise ValueError(
            f"Invalid supplier ID '{clean}'. Must match canonical format 'SUP-XXXXX' (pattern: {CANONICAL_SUPPLIER_ID_PATTERN})."
        )
    return clean


def normalize_supplier_name(name: Any) -> str:
    """Normalize supplier name for deterministic case- and whitespace-insensitive matching."""
    if not name or not isinstance(name, str):
        return ""
    # Strip trailing punctuation from words (e.g. Corp. -> corp, Ltd. -> ltd)
    cleaned = re.sub(r"[.,]+(?=\s|$)", "", name.strip().lower())
    return " ".join(cleaned.split())


def legacy_id_to_canonical(legacy_id: str) -> Optional[str]:
    """
    Convert a legacy inventory supplier ID (e.g. 'SUP001') to canonical ('SUP-00001')
    without inventing or competing with the master. If already canonical, returns as-is.
    """
    if not legacy_id or not isinstance(legacy_id, str):
        return None
    clean = legacy_id.strip().upper()
    if CANONICAL_ID_REGEX.match(clean):
        return clean
    m = LEGACY_INVENTORY_ID_REGEX.match(clean)
    if m:
        num = int(clean[3:])
        if 1 <= num <= 99999:
            return f"SUP-{num:05d}"
    return None


def get_supplier_mapping_collection(
    collection_name: str = "supplier_mappings",
    db_name: Optional[str] = None,
    uri: Optional[str] = None,
) -> Collection:
    """Retrieve the MongoDB collection for canonical supplier mappings."""
    db = get_database(db_name, uri)
    return db[collection_name]


def ensure_mapping_indexes(collection: Optional[Collection] = None) -> List[str]:
    """
    Create required indexes on the supplier_mappings collection:
    1. unique_canonical_supplier_id: Unique index on supplier_id.
    2. idx_normalized_name: Index on normalized_name for name lookup.
    3. idx_legacy_supplier_id: Sparse index on legacy_supplier_id for compatibility.

    Returns:
        List[str]: Names of created or existing indexes.
    """
    col = collection if collection is not None else get_supplier_mapping_collection()
    created = []

    # 1. Unique canonical supplier ID index
    idx_sid = col.create_index(
        [("supplier_id", pymongo.ASCENDING)],
        unique=True,
        name="unique_canonical_supplier_id",
    )
    created.append(idx_sid)

    # 2. Normalized name index
    idx_name = col.create_index(
        [("normalized_name", pymongo.ASCENDING)],
        name="idx_normalized_name",
    )
    created.append(idx_name)

    # 3. Sparse index for legacy supplier ID compatibility
    idx_legacy = col.create_index(
        [("legacy_supplier_id", pymongo.ASCENDING)],
        sparse=True,
        name="idx_legacy_supplier_id",
    )
    created.append(idx_legacy)

    return created


def parse_suppliers_csv(csv_path: Path) -> List[Dict[str, Any]]:
    """
    Parse a suppliers CSV file from the shared seed dataset.

    Validates:
    - Non-empty records
    - Presence of canonical 'supplier_id' matching 'SUP-XXXXX'
    - Presence of 'name'

    Safely rejects rows missing canonical IDs.
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"Suppliers CSV file not found: {csv_path}")

    records: List[Dict[str, Any]] = []
    seen_ids = set()

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row_idx, row in enumerate(reader, start=2):
            raw_id = (row.get("supplier_id") or "").strip().upper()
            raw_name = (row.get("name") or "").strip()

            if not raw_id:
                logger.warning("Row %d: missing supplier_id, skipping", row_idx)
                continue

            if not CANONICAL_ID_REGEX.match(raw_id):
                logger.warning("Row %d: supplier_id '%s' is not canonical, skipping", row_idx, raw_id)
                continue

            if not raw_name:
                logger.warning("Row %d: supplier '%s' missing name, skipping", row_idx, raw_id)
                continue

            if raw_id in seen_ids:
                logger.debug("Duplicate supplier_id '%s' in CSV, keeping first occurrence", raw_id)
                continue
            seen_ids.add(raw_id)

            sanctions_flag_val = str(row.get("sanctions_flag", "")).strip().lower()
            sanctions_flag = sanctions_flag_val in ("true", "1", "yes")

            record: Dict[str, Any] = {
                "supplier_id": raw_id,
                "name": raw_name,
                "normalized_name": normalize_supplier_name(raw_name),
                "country": (row.get("country") or "").strip(),
                "city": (row.get("city") or "").strip(),
                "state": (row.get("state") or "").strip(),
                "sanctions_flag": sanctions_flag,
                "sanctions_list": (row.get("sanctions_list") or "").strip(),
            }

            # Optional compatibility legacy ID
            try:
                num = int(raw_id.split("-")[1])
                record["legacy_supplier_id"] = f"SUP{num:03d}"
            except Exception:
                pass

            records.append(record)

    return records


def get_default_seed_suppliers() -> List[Dict[str, Any]]:
    """
    Get full list of seed suppliers.
    Tries reading from data-platform/seed/samples/suppliers.csv or data-platform/seed/suppliers.csv.
    Falls back to the deterministic 60-supplier seed catalog.
    """
    # 1. Search common seed file locations relative to repository
    candidates = [
        Path(__file__).resolve().parent.parent.parent.parent / "data-platform" / "seed" / "samples" / "suppliers.csv",
        Path(__file__).resolve().parent.parent.parent.parent / "data-platform" / "seed" / "suppliers.csv",
        Path(__file__).resolve().parent / "data" / "suppliers.csv",
    ]

    for p in candidates:
        if p.exists():
            try:
                parsed = parse_suppliers_csv(p)
                if parsed:
                    return parsed
            except Exception as exc:
                logger.warning("Failed parsing seed CSV %s: %s", p, exc)

    # 2. Return built-in deterministic seed catalog
    records = []
    for item in DETERMINISTIC_SEED_SUPPLIERS:
        raw_id = item["supplier_id"]
        raw_name = item["name"]
        num = int(raw_id.split("-")[1])
        rec = {
            "supplier_id": raw_id,
            "name": raw_name,
            "normalized_name": normalize_supplier_name(raw_name),
            "country": item.get("country", ""),
            "sanctions_flag": item.get("sanctions_flag", False),
            "sanctions_list": item.get("sanctions_list", ""),
            "legacy_supplier_id": f"SUP{num:03d}",
        }
        records.append(rec)
    return records


# In-memory lookup cache
_IN_MEMORY_MAPPINGS: Dict[str, Dict[str, Any]] = {}
_IN_MEMORY_BY_NAME: Dict[str, Dict[str, Any]] = {}
_IN_MEMORY_BY_LEGACY: Dict[str, Dict[str, Any]] = {}


def _populate_in_memory_cache(records: List[Dict[str, Any]]) -> None:
    """Populate in-memory cache for fast lookups and unit testing."""
    _IN_MEMORY_MAPPINGS.clear()
    _IN_MEMORY_BY_NAME.clear()
    _IN_MEMORY_BY_LEGACY.clear()

    for item in records:
        sid = item["supplier_id"]
        _IN_MEMORY_MAPPINGS[sid] = item
        norm = item.get("normalized_name") or normalize_supplier_name(item.get("name", ""))
        if norm and norm not in _IN_MEMORY_BY_NAME:
            _IN_MEMORY_BY_NAME[norm] = item
        leg = item.get("legacy_supplier_id")
        if leg and leg not in _IN_MEMORY_BY_LEGACY:
            _IN_MEMORY_BY_LEGACY[leg] = item


# Initialize in-memory cache at import time
_populate_in_memory_cache(get_default_seed_suppliers())


def seed_supplier_mappings(
    records: Optional[List[Dict[str, Any]]] = None,
    collection: Optional[Collection] = None,
) -> Dict[str, int]:
    """
    Persist canonical supplier mappings to MongoDB with idempotency.

    Repeated runs safely update metadata without generating duplicates or altering IDs.

    Args:
        records: Optional list of mapping dictionaries. Defaults to get_default_seed_suppliers().
        collection: Optional MongoDB collection.

    Returns:
        Dict[str, int]: Summary stats (total, inserted, updated, skipped, failed).
    """
    to_insert = records if records is not None else get_default_seed_suppliers()
    _populate_in_memory_cache(to_insert)

    stats = {
        "total": len(to_insert),
        "inserted": 0,
        "updated": 0,
        "skipped": 0,
        "failed": 0,
    }

    try:
        col = collection if collection is not None else get_supplier_mapping_collection()
        ensure_mapping_indexes(col)

        for doc in to_insert:
            sid = doc.get("supplier_id")
            if not sid or not is_canonical_supplier_id(sid):
                stats["failed"] += 1
                continue

            update_doc = {
                "supplier_id": sid,
                "name": doc.get("name", ""),
                "normalized_name": doc.get("normalized_name") or normalize_supplier_name(doc.get("name", "")),
                "country": doc.get("country", ""),
                "city": doc.get("city", ""),
                "state": doc.get("state", ""),
                "sanctions_flag": bool(doc.get("sanctions_flag", False)),
                "sanctions_list": doc.get("sanctions_list", ""),
                "legacy_supplier_id": doc.get("legacy_supplier_id") or legacy_id_to_canonical(sid),
                "updated_at": datetime.now(timezone.utc),
            }

            res = col.update_one(
                {"supplier_id": sid},
                {
                    "$set": update_doc,
                    "$setOnInsert": {"created_at": datetime.now(timezone.utc)},
                },
                upsert=True,
            )

            if res.upserted_id is not None:
                stats["inserted"] += 1
            elif res.modified_count > 0:
                stats["updated"] += 1
            else:
                stats["skipped"] += 1

    except Exception as exc:
        logger.warning("MongoDB seed_supplier_mappings deferred or failed (in-memory cache used): %s", exc)

    return stats


def resolve_canonical_supplier(
    identifier_or_name: str,
    collection: Optional[Collection] = None,
) -> Optional[Dict[str, Any]]:
    """
    Resolve any supplier identifier or name to its canonical supplier record.

    Resolution Strategy:
    1. Direct match on canonical supplier ID (e.g. 'SUP-00045').
    2. Legacy inventory supplier ID match (e.g. 'SUP045' -> 'SUP-00045').
    3. Normalized exact name match (e.g. 'ALPHA SANCTIONS CORP', 'Apex Industries Pvt Ltd').
    4. Legacy inventory name compatibility match.

    Returns:
        Dict[str, Any] with canonical record if found, else None.
    """
    if not identifier_or_name or not isinstance(identifier_or_name, str):
        return None

    raw = identifier_or_name.strip()
    upper_raw = raw.upper()

    # 1. Exact Canonical ID match
    if CANONICAL_ID_REGEX.match(upper_raw):
        # Try Mongo first if available
        try:
            col = collection if collection is not None else get_supplier_mapping_collection()
            doc = col.find_one({"supplier_id": upper_raw}, {"_id": 0})
            if doc:
                return doc
        except Exception:
            pass
        return _IN_MEMORY_MAPPINGS.get(upper_raw)

    # 2. Legacy Inventory ID match (e.g. 'SUP007' -> 'SUP-00007')
    if LEGACY_INVENTORY_ID_REGEX.match(upper_raw):
        canonical_cand = legacy_id_to_canonical(upper_raw)
        if canonical_cand:
            try:
                col = collection if collection is not None else get_supplier_mapping_collection()
                doc = col.find_one(
                    {"$or": [{"supplier_id": canonical_cand}, {"legacy_supplier_id": upper_raw}]},
                    {"_id": 0},
                )
                if doc:
                    return doc
            except Exception:
                pass
            if canonical_cand in _IN_MEMORY_MAPPINGS:
                return _IN_MEMORY_MAPPINGS[canonical_cand]
            if upper_raw in _IN_MEMORY_BY_LEGACY:
                return _IN_MEMORY_BY_LEGACY[upper_raw]

    # 3. Normalized Name match
    normalized = normalize_supplier_name(raw)
    try:
        col = collection if collection is not None else get_supplier_mapping_collection()
        doc = col.find_one({"normalized_name": normalized}, {"_id": 0})
        if doc:
            return doc
    except Exception:
        pass

    if normalized in _IN_MEMORY_BY_NAME:
        return _IN_MEMORY_BY_NAME[normalized]

    # 4. Legacy inventory name compatibility
    if normalized in LEGACY_INVENTORY_NAME_MAPPINGS:
        target_id = LEGACY_INVENTORY_NAME_MAPPINGS[normalized]
        return _IN_MEMORY_MAPPINGS.get(target_id)

    return None


def resolve_canonical_supplier_id(
    identifier_or_name: str,
    collection: Optional[Collection] = None,
) -> Optional[str]:
    """
    Resolve identifier or name to canonical supplier_id string ('SUP-XXXXX').

    Returns:
        str canonical ID if found, else None.
    """
    res = resolve_canonical_supplier(identifier_or_name, collection=collection)
    return res["supplier_id"] if res else None
