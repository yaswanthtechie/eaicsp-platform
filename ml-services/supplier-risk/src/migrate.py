"""
Migration utility to import raw supplier headlines from JSON datasets into MongoDB.

Safely re-runnable (idempotent), deduplicates stories deterministically via story_hash,
never alters or deletes source JSON files, and reports detailed migration metrics:
total, inserted, skipped, and failed records.
"""

import argparse
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

import pymongo
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError

from src.db import ensure_indexes, generate_story_hash, get_collection, ping_mongodb

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def migrate_dataset(
    json_path: Path,
    collection: Optional[Collection] = None,
) -> Dict[str, int]:
    """
    Import a JSON dataset into MongoDB with deduplication.

    Args:
        json_path: Path to source JSON file.
        collection: Target MongoDB collection.

    Returns:
        Dict[str, int]: Summary with keys: total, inserted, skipped, failed.
    """
    if not json_path.exists():
        raise FileNotFoundError(f"Dataset file not found: {json_path}")

    with json_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise ValueError(f"Expected a list of article records in {json_path.name}")

    col = collection if collection is not None else get_collection()

    # Pre-create indexes so unique constraint on story_hash is active
    ensure_indexes(col)

    stats = {
        "total": len(data),
        "inserted": 0,
        "skipped": 0,
        "failed": 0,
    }

    for idx, item in enumerate(data):
        if not isinstance(item, dict):
            logger.warning("Skipping non-dict record at index %d", idx)
            stats["failed"] += 1
            continue

        supplier = item.get("supplier")
        headline = item.get("headline")
        date_str = item.get("date")
        source = item.get("source")

        if not supplier or not isinstance(supplier, str) or not supplier.strip():
            logger.warning("Record at index %d missing valid supplier", idx)
            stats["failed"] += 1
            continue

        if not headline or not isinstance(headline, str) or not headline.strip():
            logger.warning("Record at index %d missing valid headline", idx)
            stats["failed"] += 1
            continue

        story_hash = generate_story_hash(supplier, headline)

        # Check if record already exists by deterministic story_hash
        existing = col.find_one({"story_hash": story_hash})
        if existing:
            # If incoming has a date and existing is missing date, enrich it
            if date_str and not existing.get("date"):
                col.update_one(
                    {"_id": existing["_id"]},
                    {"$set": {"date": date_str.strip()}},
                )
            stats["skipped"] += 1
            continue

        doc: Dict[str, Any] = {
            "supplier": supplier.strip(),
            "headline": headline.strip(),
            "story_hash": story_hash,
            "created_at": datetime.now(timezone.utc),
        }
        if date_str and isinstance(date_str, str) and date_str.strip():
            doc["date"] = date_str.strip()
        if source and isinstance(source, str) and source.strip():
            doc["source"] = source.strip()

        try:
            col.insert_one(doc)
            stats["inserted"] += 1
        except DuplicateKeyError:
            # Caught unique constraint race or collision
            stats["skipped"] += 1
        except Exception as exc:
            logger.exception("Failed to insert record at index %d: %s", idx, exc)
            stats["failed"] += 1

    return stats


def run_migration(
    json_path: Optional[Path] = None,
    collection: Optional[Collection] = None,
) -> Dict[str, int]:
    """
    Execute migration with connectivity check and default dataset resolution.
    By default, migrates supplier_trend_headlines.json (10 baseline suppliers with dates).
    """
    ping_mongodb()

    default_path = Path(__file__).parent / "supplier_trend_headlines.json"
    target_path = json_path or default_path

    logger.info("Starting migration from %s ...", target_path)
    summary = migrate_dataset(target_path, collection=collection)
    logger.info(
        "Migration complete: Total=%d | Inserted=%d | Skipped=%d | Failed=%d",
        summary["total"],
        summary["inserted"],
        summary["skipped"],
        summary["failed"],
    )
    return summary


def main():
    parser = argparse.ArgumentParser(description="Migrate supplier headlines to MongoDB.")
    parser.add_argument(
        "--file",
        type=str,
        default=None,
        help="Path to JSON file to migrate (default: src/supplier_trend_headlines.json)",
    )
    args = parser.parse_args()

    json_file = Path(args.file) if args.file else None
    try:
        summary = run_migration(json_path=json_file)
        print(f"\nMigration Summary for {json_file.name if json_file else 'supplier_trend_headlines.json'}:")
        print(f"  Total records:    {summary['total']}")
        print(f"  Inserted records: {summary['inserted']}")
        print(f"  Skipped (dups):   {summary['skipped']}")
        print(f"  Failed records:   {summary['failed']}\n")
    except Exception as exc:
        logger.error("Migration failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
