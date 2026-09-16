"""
Data loading module for the Supplier Risk NLP pipeline.
"""

import json
from pathlib import Path
from typing import Dict, List

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


def load_headlines() -> Dict[str, List[str]]:
    """
    Load supplier news headlines grouped by supplier.

    Priority:
        1. Load the 120-headline / 10-company Round 5 calibration
           dataset from ``supplier_headlines.json`` when available.
        2. Fall back to the smaller inline ``HEADLINES_DATA`` sample.

    Returns:
        Dict[str, List[str]]:
            Dictionary where the key is the supplier name and
            the value is a list of associated news headlines.
    """

    source_data = _load_from_json() or HEADLINES_DATA

    grouped_headlines: Dict[str, List[str]] = {}

    for item in source_data:

        supplier = item.get("supplier")
        headline = item.get("headline")

        if not supplier or not headline:
            continue

        grouped_headlines.setdefault(
            supplier,
            [],
        ).append(headline)

    return grouped_headlines
