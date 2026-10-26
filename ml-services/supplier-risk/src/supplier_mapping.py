"""
Canonical Supplier ID mapping and resolution module.

Provides deterministic mapping from supplier names and canonical identifiers
to canonical supplier IDs (SUP-XXXXX) per Integration Blueprint Section 2.
Persists mappings in MongoDB with uniqueness constraints and indexes.
"""

from __future__ import annotations

from collections import defaultdict
import csv
from datetime import datetime, timezone
import logging
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Set

import pymongo
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError

from src.db import get_collection, get_database

logger = logging.getLogger(__name__)

CANONICAL_SUPPLIER_ID_PATTERN: str = r"^SUP-\d{5}$"
CANONICAL_ID_REGEX = re.compile(CANONICAL_SUPPLIER_ID_PATTERN)
LEGACY_INVENTORY_ID_REGEX = re.compile(r"^SUP\d{3}$")


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
    3. idx_aliases: Index on aliases for exact reviewed alias lookup.

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

    # 3. Exact reviewed aliases index
    idx_alias = col.create_index(
        [("aliases", pymongo.ASCENDING)],
        name="idx_aliases",
    )
    created.append(idx_alias)

    return created


def get_seed_csv_path() -> Path:
    """
    Get the configured Path to the canonical suppliers seed CSV.

    Default: <repository-root>/data-platform/seed/out/suppliers.csv
    Can be overridden via the SUPPLIER_SEED_CSV environment variable.
    """
    env_override = os.environ.get("SUPPLIER_SEED_CSV")
    if env_override:
        return Path(env_override).resolve()
    repo_root = Path(__file__).resolve().parents[3]
    return (repo_root / "data-platform" / "seed" / "out" / "suppliers.csv").resolve()


def parse_suppliers_csv(csv_path: Path) -> List[Dict[str, Any]]:
    """
    Parse a suppliers CSV file from the shared seed dataset.

    Validates:
    - Non-empty records
    - Presence of canonical 'supplier_id' matching 'SUP-XXXXX'
    - Presence of 'name'

    Safely rejects rows missing canonical IDs.

    Raises:
        FileNotFoundError: If the configured seed file does not exist.
    """
    path = Path(csv_path).resolve()
    if not path.exists():
        raise FileNotFoundError(
            f"Suppliers seed CSV file not found at '{path}'. "
            "Please generate the seed file using: "
            "python -m seed.generate --out out/ "
            "(or override the path using the SUPPLIER_SEED_CSV environment variable)."
        )

    records: List[Dict[str, Any]] = []
    seen_ids = set()

    with open(path, "r", encoding="utf-8-sig") as f:
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
            records.append(record)

    return records


def get_default_seed_suppliers(csv_path: Optional[Path | str] = None) -> List[Dict[str, Any]]:
    """
    Get full list of seed suppliers from the generated seed CSV.

    Uses SUPPLIER_SEED_CSV env var if set, otherwise <repository-root>/data-platform/seed/out/suppliers.csv.
    Raises FileNotFoundError with generation instructions if the seed CSV is missing.
    """
    target_path = Path(csv_path).resolve() if csv_path is not None else get_seed_csv_path()
    return parse_suppliers_csv(target_path)


def get_aliases_csv_path() -> Path:
    """
    Get the configured Path to the reviewed supplier aliases CSV.

    Default: <repo-root>/data/supplier_aliases.csv or <service-root>/data/supplier_aliases.csv.
    Can be overridden via the SUPPLIER_ALIASES_CSV environment variable.
    """
    env_override = os.environ.get("SUPPLIER_ALIASES_CSV")
    if env_override:
        return Path(env_override).resolve()
    repo_root = Path(__file__).resolve().parents[3]
    repo_data = repo_root / "data" / "supplier_aliases.csv"
    if repo_data.exists():
        return repo_data.resolve()
    service_root = Path(__file__).resolve().parents[1]
    service_data = service_root / "data" / "supplier_aliases.csv"
    if service_data.exists():
        return service_data.resolve()
    return repo_data.resolve()


def load_supplier_aliases(csv_path: Optional[Path | str] = None) -> Dict[str, str]:
    """
    Load reviewed supplier alias mappings from CSV.

    Validates:
    - File existence (raises FileNotFoundError if missing)
    - Valid headers ('alias,supplier_id')
    - Canonical supplier_id matching 'SUP-XXXXX'
    - Non-empty, non-malformed rows
    - Duplicate alias detection (raises ValueError on ambiguity)

    Returns:
        Dict[str, str]: Mapping from exact alias to canonical supplier_id.
    """
    target_path = Path(csv_path).resolve() if csv_path is not None else get_aliases_csv_path()
    if not target_path.exists():
        raise FileNotFoundError(
            f"Supplier aliases CSV file not found at '{target_path}'. "
            "Please ensure 'data/supplier_aliases.csv' exists (or configure SUPPLIER_ALIASES_CSV)."
        )

    aliases_map: Dict[str, str] = {}
    seen_aliases: Set[str] = set()

    with open(target_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:

            raise ValueError(f"Malformed alias CSV at '{target_path}': empty file without headers.")

        normalized_fieldnames = [fn.strip() for fn in reader.fieldnames if fn]
        if "alias" not in normalized_fieldnames or "supplier_id" not in normalized_fieldnames:
            raise ValueError(
                f"Malformed alias CSV at '{target_path}': required headers 'alias,supplier_id' missing. "
                f"Got headers: {reader.fieldnames}"
            )

        for row_idx, row in enumerate(reader, start=2):
            if None in row or any(k is None for k in row.keys()):
                raise ValueError(
                    f"Malformed row {row_idx} in '{target_path}': extra or unaligned columns detected: {row}"
                )

            raw_alias = row.get("alias")
            raw_id = row.get("supplier_id")

            if raw_alias is None or not raw_alias.strip():
                raise ValueError(
                    f"Malformed row {row_idx} in '{target_path}': alias cannot be empty."
                )

            if raw_id is None or not raw_id.strip():
                raise ValueError(
                    f"Malformed row {row_idx} in '{target_path}': supplier_id cannot be empty for alias '{raw_alias}'."
                )

            clean_alias = raw_alias.strip()
            clean_id = raw_id.strip().upper()

            if not is_canonical_supplier_id(clean_id):
                raise ValueError(
                    f"Invalid canonical supplier_id '{clean_id}' for alias '{clean_alias}' "
                    f"at row {row_idx} in '{target_path}'. Must match format 'SUP-XXXXX'."
                )

            if clean_alias in seen_aliases:
                raise ValueError(
                    f"Duplicate alias '{clean_alias}' at row {row_idx} in '{target_path}'. "
                    "Ambiguous supplier alias mappings are strictly rejected."
                )

            seen_aliases.add(clean_alias)
            aliases_map[clean_alias] = clean_id

    return aliases_map


def seed_supplier_mappings(
    records: Optional[List[Dict[str, Any]]] = None,
    aliases: Optional[Dict[str, str] | List[Dict[str, str]] | Path | str] = None,
    collection: Optional[Collection] = None,
) -> Dict[str, int]:
    """
    Persist canonical supplier mappings and reviewed aliases to MongoDB with idempotency.

    Repeated runs safely update metadata without generating duplicates or altering IDs.

    Args:
        records: Optional list of mapping dictionaries. Defaults to get_default_seed_suppliers().
        aliases: Optional alias mappings (dict, list, or CSV path). Defaults to load_supplier_aliases().
        collection: Optional MongoDB collection.

    Returns:
        Dict[str, int]: Summary stats (total, inserted, updated, skipped, failed).
    """
    to_insert = records if records is not None else get_default_seed_suppliers()

    # Determine reviewed aliases
    alias_map: Dict[str, str] = {}
    if isinstance(aliases, dict):
        alias_map = aliases
    elif isinstance(aliases, list):
        for item in aliases:
            a = item.get("alias")
            s = item.get("supplier_id")
            if a and s:
                clean_alias = a.strip()
                clean_sid = s.strip().upper()
                if clean_alias in alias_map and alias_map[clean_alias] != clean_sid:
                    raise ValueError(
                        f"Duplicate alias '{clean_alias}' assigned to conflicting suppliers "
                        f"('{alias_map[clean_alias]}' vs '{clean_sid}')."
                    )
                alias_map[clean_alias] = clean_sid
    elif isinstance(aliases, (str, Path)):
        alias_map = load_supplier_aliases(aliases)
    elif aliases is None:
        alias_path = get_aliases_csv_path()
        if alias_path.exists():
            alias_map = load_supplier_aliases(alias_path)

    # Group aliases by canonical supplier_id
    supplier_aliases_map: Dict[str, List[str]] = defaultdict(list)
    for alias_name, sid in alias_map.items():
        supplier_aliases_map[sid].append(alias_name)

    stats = {
        "total": len(to_insert),
        "inserted": 0,
        "updated": 0,
        "skipped": 0,
        "failed": 0,
    }

    col = collection if collection is not None else get_supplier_mapping_collection()
    ensure_mapping_indexes(col)

    seen_batch_aliases: Dict[str, str] = {}
    for doc in to_insert:
        sid = doc.get("supplier_id")
        if not sid or not is_canonical_supplier_id(sid):
            stats["failed"] += 1
            continue

        doc_aliases = list(doc.get("aliases", []))
        csv_aliases = supplier_aliases_map.get(sid, [])
        combined_aliases = list(dict.fromkeys(doc_aliases + csv_aliases))

        # Avoid adding duplicate aliases or overwriting an alias that belongs to another supplier
        valid_aliases = []
        for cand in combined_aliases:
            if cand in seen_batch_aliases and seen_batch_aliases[cand] != sid:
                logger.warning(
                    "Alias '%s' already registered to supplier '%s' in current batch, skipping for '%s'",
                    cand,
                    seen_batch_aliases[cand],
                    sid,
                )
                continue
            conflict = col.find_one(
                {"aliases": cand, "supplier_id": {"$ne": sid}},
                {"supplier_id": 1},
            )
            if conflict and isinstance(conflict, dict) and conflict.get("supplier_id") != sid:
                logger.warning(
                    "Alias '%s' already registered to supplier '%s', skipping for '%s'",
                    cand,
                    conflict.get("supplier_id"),
                    sid,
                )
                continue
            seen_batch_aliases[cand] = sid
            valid_aliases.append(cand)

        update_doc = {
            "supplier_id": sid,
            "name": doc.get("name", ""),
            "normalized_name": doc.get("normalized_name") or normalize_supplier_name(doc.get("name", "")),
            "country": doc.get("country", ""),
            "city": doc.get("city", ""),
            "state": doc.get("state", ""),
            "sanctions_flag": bool(doc.get("sanctions_flag", False)),
            "sanctions_list": doc.get("sanctions_list", ""),
            "aliases": valid_aliases,
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

    return stats


def resolve_canonical_supplier(
    identifier_or_name: str,
    collection: Optional[Collection] = None,
) -> Optional[Dict[str, Any]]:
    """
    Resolve any supplier identifier or name to its canonical supplier record.

    Enforces exact resolution order:
    1. Canonical supplier ID (e.g. 'SUP-00045').
    2. Exact seed supplier name (e.g. 'ALPHA SANCTIONS CORP', 'Apex Industries Pvt Ltd').
    3. Exact reviewed alias (e.g. 'Foxconn' -> record for SUP-00019).

    Do not use fuzzy matching, guessed mappings, generated IDs, legacy-name fallbacks, or MD5-based IDs.
    Does not swallow MongoDB errors or use in-memory fallback data; PyMongoError propagates
    to the caller to ensure database outages result in HTTP 503 rather than false HTTP 404.

    Returns:
        Dict[str, Any] with canonical record if found, else None.
    """
    if not identifier_or_name or not isinstance(identifier_or_name, str):
        return None

    raw = identifier_or_name.strip()
    if not raw:
        return None

    upper_raw = raw.upper()

    col = collection if collection is not None else get_supplier_mapping_collection()

    # 1. Canonical supplier ID
    if CANONICAL_ID_REGEX.match(upper_raw):
        doc = col.find_one({"supplier_id": upper_raw}, {"_id": 0})
        if doc:
            return doc
        return None

    # 2. Exact seed supplier name
    normalized = normalize_supplier_name(raw)
    doc = col.find_one(
        {"$or": [{"name": raw}, {"normalized_name": normalized}]},
        {"_id": 0},
    )
    if doc:
        return doc

    # 3. Exact reviewed alias
    doc = col.find_one({"aliases": raw}, {"_id": 0})
    if doc:
        return doc

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
