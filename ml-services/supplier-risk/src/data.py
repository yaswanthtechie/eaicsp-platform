"""
Data loading module for the Supplier Risk NLP pipeline.
"""

from typing import Dict, List


def load_headlines() -> Dict[str, List[str]]:
    """
    Load supplier news headlines and return them grouped by supplier.

    Returns:
        Dict[str, List[str]]
    """

    headlines_raw = [
        {
            "supplier": "TechCorp",
            "headline": "TechCorp files for bankruptcy after massive fraud scandal.",
        },
        {
            "supplier": "AutoMaker Inc",
            "headline": "AutoMaker Inc announces major recall of 1 million vehicles due to brake failure.",
        },
        {
            "supplier": "Logistics Co",
            "headline": "Logistics Co workers go on strike demanding better pay and conditions.",
        },
        {
            "supplier": "Global Trade",
            "headline": "Global Trade faces severe sanction from international regulatory bodies.",
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
            "headline": "FoodSupplies investigates alleged fraud in their accounting department.",
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
            "headline": "MetalWorks hit with unexpected sanction over environmental violations.",
        },
        {
            "supplier": "MetalWorks",
            "headline": "MetalWorks secures a large government contract for infrastructure.",
        },
        {
            "supplier": "FoodSupplies",
            "headline": "Massive recall of FoodSupplies products due to contamination fears.",
        },
        {
            "supplier": "BuildIt",
            "headline": "BuildIt declares bankruptcy amidst rising interest rates and falling demand.",
        },
        {
            "supplier": "BuildIt",
            "headline": "BuildIt receives a bailout package from investors to stay afloat.",
        },
        {
            "supplier": "TechCorp",
            "headline": "TechCorp shares plummet as fraud investigation deepens.",
        },
    ]

    grouped_headlines: Dict[str, List[str]] = {}

    for item in headlines_raw:

        supplier = item.get("supplier")
        headline = item.get("headline")

        # Skip invalid records
        if not supplier or not headline:
            continue

        grouped_headlines.setdefault(supplier, []).append(headline)

    return grouped_headlines