"""
Data loading module for the Supplier Risk NLP pipeline.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from src.db import fetch_headlines_grouped, fetch_trend_headlines_grouped

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Sample Supplier Headlines (fallback when JSON dataset unavailable)
# ------------------------------------------------------------------

HEADLINES_DATA = [
    {
        "supplier": "TechCorp",
        "headline": "TechCorp files for bankruptcy after massive fraud scandal.",
    },
    {
        "supplier": "AutoMaker Inc",
        "headline": (
            "AutoMaker Inc announces major recall of 1 million "
            "vehicles due to brake failure."
        ),
    },
    {
        "supplier": "Logistics Co",
        "headline": (
            "Logistics Co workers go on strike demanding better pay "
            "and conditions."
        ),
    },
    {
        "supplier": "Global Trade",
        "headline": (
            "Global Trade faces severe sanction from international "
            "regulatory bodies."
        ),
    },
    {
        "supplier": "TechCorp",
        "headline": "TechCorp appoints new CEO to restructure the company.",
    },
    {
        "supplier": "AutoMaker Inc",
        "headline": "AutoMaker Inc reports record profits for the third quarter.",
    },
    {
        "supplier": "FoodSupplies",
        "headline": (
            "FoodSupplies investigates alleged fraud in their "
            "accounting department."
        ),
    },
    {
        "supplier": "Logistics Co",
        "headline": "Logistics Co resolves strike, operations return to normal.",
    },
    {
        "supplier": "Global Trade",
        "headline": "Global Trade expands operations into the Asian market.",
    },
    {
        "supplier": "MetalWorks",
        "headline": (
            "MetalWorks hit with unexpected sanction over "
            "environmental violations."
        ),
    },
    {
        "supplier": "MetalWorks",
        "headline": (
            "MetalWorks secures a large government contract "
            "for infrastructure."
        ),
    },
    {
        "supplier": "FoodSupplies",
        "headline": (
            "Massive recall of FoodSupplies products due to "
            "contamination fears."
        ),
    },
    {
        "supplier": "BuildIt",
        "headline": (
            "BuildIt declares bankruptcy amidst rising interest "
            "rates and falling demand."
        ),
    },
    {
        "supplier": "BuildIt",
        "headline": (
            "BuildIt receives a bailout package from investors "
            "to stay afloat."
        ),
    },
    {
        "supplier": "TechCorp",
        "headline": (
            "TechCorp shares plummet as fraud investigation deepens."
        ),
    },
]


def _load_from_json() -> List[Dict[str, str]]:
    """
    Try to load the calibration dataset from supplier_headlines.json.

    Returns the list of headline records, or an empty list if the
    JSON file cannot be found or parsed.
    """
    json_path = Path(__file__).parent / "supplier_headlines.json"

    if not json_path.exists():
        return []

    try:
        with json_path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, list):
            raise ValueError("supplier_headlines.json must contain a list of records")

        if len(data) == 0:
            raise ValueError("supplier_headlines.json is empty")

        for idx, record in enumerate(data):
            if not isinstance(record, dict) or "supplier" not in record or "headline" not in record:
                raise ValueError(f"Invalid record at index {idx} in supplier_headlines.json")

        return data

    except json.JSONDecodeError as exc:
        raise ValueError("supplier_headlines.json is malformed") from exc
    except FileNotFoundError:
        return []

    return []


BASELINE_TREND_PATH = Path(__file__).parent / "supplier_trend_headlines.json"
ACTIVE_TREND_PATH = Path(__file__).parent / "supplier_trend_headlines_25.json"


def load_headlines_from_json() -> Dict[str, List[str]]:
    """
    Read the committed baseline dataset directly from JSON (never MongoDB).
    Used by tests, benchmarks and the Mongo-vs-JSON equivalence check.
    """
    grouped: Dict[str, List[str]] = {}
    for item in _load_from_json() or HEADLINES_DATA:
        supplier = item.get("supplier")
        headline = item.get("headline")
        if supplier and headline:
            grouped.setdefault(supplier, []).append(headline)
    return grouped


def load_headlines(
    use_fallback: bool = False,
) -> Dict[str, List[str]]:
    """
    Load supplier news headlines grouped by supplier.

    MongoDB is the authoritative runtime data source.
    If MongoDB is unreachable or the collection is empty:
    - If use_fallback=True (test mode or explicit override), loads from
      supplier_headlines.json or inline HEADLINES_DATA.
    - Otherwise raises RuntimeError.

    Returns:
        Dict[str, List[str]]:
            Dictionary where the key is the supplier name and
            the value is a list of associated news headlines.
    """
    try:
        mongo_data = fetch_headlines_grouped()
        if mongo_data:
            return mongo_data
    except Exception as exc:
        logger.warning("Failed to load headlines from MongoDB: %s", exc)
        if not use_fallback:
            raise RuntimeError(
                f"MongoDB is the authoritative runtime data source for supplier risk scoring, "
                f"but querying failed: {exc}. Ensure the supplier-risk-mongo container is running "
                f"and run 'python -m src.migrate' to populate the collection."
            ) from exc

    if not use_fallback:
        raise RuntimeError(
            "MongoDB is the authoritative runtime data source for supplier risk scoring, "
            "but the headlines collection is empty. Run 'python -m src.migrate' to import articles."
        )

    return load_headlines_from_json()


# ------------------------------------------------------------------
# Sample Supplier Trend Headlines (fallback when trend dataset unavailable)
# ------------------------------------------------------------------

TREND_HEADLINES_DATA = [
    {
        "supplier": "Tesla",
        "date": "2026-01-05",
        "headline": "Tesla announces a major recall of 2 million vehicles over autopilot software issues.",
    },
    {
        "supplier": "Tesla",
        "date": "2026-01-12",
        "headline": "Tesla faces a class-action lawsuit from investors over self-driving claims.",
    },
    {
        "supplier": "Tesla",
        "date": "2026-01-19",
        "headline": "Tesla reports a surprise drop in quarterly vehicle deliveries.",
    },
    {
        "supplier": "Tesla",
        "date": "2026-01-26",
        "headline": "Tesla announces another round of layoff affecting its sales teams globally.",
    },
    {
        "supplier": "Tesla",
        "date": "2026-02-02",
        "headline": "Tesla expands its Gigafactory operations in Texas and Berlin.",
    },
    {
        "supplier": "Tesla",
        "date": "2026-02-09",
        "headline": "Tesla secures a new partnership for lithium supply in Australia.",
    },
    {
        "supplier": "Tesla",
        "date": "2026-02-16",
        "headline": "Tesla stock suffers a downgrade amid concerns over increasing competition.",
    },
    {
        "supplier": "Tesla",
        "date": "2026-02-23",
        "headline": "Regulators open an investigation into Tesla over battery fire incidents.",
    },
    {
        "supplier": "Tesla",
        "date": "2026-03-02",
        "headline": "Tesla reports record positive earnings driven by strong Model Y sales.",
    },
    {
        "supplier": "Tesla",
        "date": "2026-03-09",
        "headline": "Tesla faces production disruption in Shanghai due to supply chain shortage.",
    },
    {
        "supplier": "Tesla",
        "date": "2026-03-16",
        "headline": "Tesla reaches milestone of 5 million vehicles produced globally.",
    },
    {
        "supplier": "Tesla",
        "date": "2026-03-23",
        "headline": "Tesla experiences minor supply disruption due to port closure.",
    },
]


def _load_trend_from_json(json_path: Path | None = None) -> List[Dict[str, str]]:
    """
    Try to load the date-aware trend dataset from supplier_trend_headlines.json.

    Returns the list of date-aware records, or an empty list if the
    JSON file cannot be found.
    """
    from src.trend import validate_date

    target_path = json_path or (Path(__file__).parent / "supplier_trend_headlines.json")

    if not target_path.exists():
        return []

    try:
        with target_path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, list):
            raise ValueError("Trend headlines JSON must contain a list of records")

        if len(data) == 0:
            raise ValueError("Trend headlines JSON is empty")

        for idx, record in enumerate(data):
            if not isinstance(record, dict) or "supplier" not in record or "headline" not in record:
                raise ValueError(f"Invalid record at index {idx} in trend headlines JSON")
            if "date" not in record:
                raise ValueError(f"Missing 'date' field at index {idx} in trend headlines JSON")
            validate_date(record["date"])

        return data

    except json.JSONDecodeError as exc:
        raise ValueError("Trend headlines JSON is malformed") from exc
    except FileNotFoundError:
        return []

    return []


def load_trend_headlines(
    json_path: Path | None = None,
    use_fallback: bool = False,
) -> Dict[str, List[Dict[str, str]]]:
    """
    Load date-aware supplier news headlines grouped by supplier.

    When json_path is provided, loads directly from that JSON file (used for benchmark
    datasets and test fixtures).
    Otherwise, MongoDB is the authoritative runtime data source.
    If MongoDB is unreachable or empty:
    - If use_fallback=True, falls back to supplier_trend_headlines.json.
    - Otherwise raises RuntimeError.

    Returns:
        Dict[str, List[Dict[str, str]]]:
            Dictionary where the key is supplier name and value is a list of
            date-aware records: [{'date': 'YYYY-MM-DD', 'headline': '...'}]
    """
    if json_path is not None:
        source_data = _load_trend_from_json(json_path)
        grouped: Dict[str, List[Dict[str, str]]] = {}
        for item in source_data:
            supplier = item.get("supplier")
            date_str = item.get("date")
            headline = item.get("headline")
            if not supplier or not date_str or not headline:
                continue
            grouped.setdefault(supplier, []).append(
                {
                    "date": date_str,
                    "headline": headline,
                }
            )
        return grouped

    try:
        mongo_trend = fetch_trend_headlines_grouped()
        if mongo_trend:
            return mongo_trend
    except Exception as exc:
        logger.warning("Failed to load trend headlines from MongoDB: %s", exc)
        if not use_fallback:
            raise RuntimeError(
                f"MongoDB is the authoritative runtime data source for supplier risk trend scoring, "
                f"but querying failed: {exc}. Ensure the supplier-risk-mongo container is running "
                f"and run 'python -m src.migrate' to populate the collection."
            ) from exc

    if not use_fallback:
        raise RuntimeError(
            "MongoDB is the authoritative runtime data source for supplier risk trend scoring, "
            "but the headlines collection contains no date-aware records. "
            "Run 'python -m src.migrate' to import articles."
        )

    source_data = _load_trend_from_json(None) or TREND_HEADLINES_DATA

    grouped = {}

    for item in source_data:
        supplier = item.get("supplier")
        date_str = item.get("date")
        headline = item.get("headline")

        if not supplier or not date_str or not headline:
            continue

        grouped.setdefault(supplier, []).append(
            {
                "date": date_str,
                "headline": headline,
            }
        )

    return grouped


def load_15_company_dataset(json_path: Path | None = None) -> Dict[str, List[str]]:
    """
    Load the 15-company calibration benchmark dataset grouped by supplier.

    Returns:
        Dict[str, List[str]]:
            Dictionary where the key is the supplier name and
            the value is a list of associated news headlines.
    """
    target_path = json_path or (Path(__file__).parent / "supplier_headlines_15.json")

    if not target_path.exists():
        return {}

    with target_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    grouped: Dict[str, List[str]] = {}
    for item in data:
        supplier = item.get("supplier")
        headline = item.get("headline")
        if supplier and headline:
            grouped.setdefault(supplier, []).append(headline)

    return grouped


def load_15_company_trend_dataset(
    json_path: Path | None = None,
) -> Dict[str, List[Dict[str, str]]]:
    """
    Load the 15-company date-aware trend dataset grouped by supplier.

    Returns:
        Dict[str, List[Dict[str, str]]]:
            Dictionary where the key is supplier name and value is a list of
            date-aware records: [{'date': 'YYYY-MM-DD', 'headline': '...'}]
    """
    target_path = json_path or (Path(__file__).parent / "supplier_trend_headlines_15.json")
    return load_trend_headlines(target_path)


def load_25_company_dataset(json_path: Path | None = None) -> Dict[str, List[str]]:
    """
    Load the 25-company calibration benchmark dataset grouped by supplier.

    Returns:
        Dict[str, List[str]]:
            Dictionary where the key is the supplier name and
            the value is a list of associated news headlines.
    """
    target_path = json_path or (Path(__file__).parent / "supplier_headlines_25.json")

    if not target_path.exists():
        return {}

    with target_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    grouped: Dict[str, List[str]] = {}
    for item in data:
        supplier = item.get("supplier")
        headline = item.get("headline")
        if supplier and headline:
            grouped.setdefault(supplier, []).append(headline)

    return grouped


def load_25_company_trend_dataset(
    json_path: Path | None = None,
) -> Dict[str, List[Dict[str, str]]]:
    """
    Load the 25-company date-aware trend dataset grouped by supplier.

    Returns:
        Dict[str, List[Dict[str, str]]]:
            Dictionary where the key is supplier name and value is a list of
            date-aware records: [{'date': 'YYYY-MM-DD', 'headline': '...'}]
    """
    target_path = json_path or (Path(__file__).parent / "supplier_trend_headlines_25.json")
    return load_trend_headlines(target_path)


def load_active_trend_headlines() -> Dict[str, List[Dict[str, str]]]:
    """
    Runtime trend data for the API. MongoDB is the only source.
    Populate it with: python -m src.migrate
    (For the committed benchmark files, use load_25_company_trend_dataset()
    or load_15_company_trend_dataset() explicitly.)
    """
    return load_trend_headlines()
