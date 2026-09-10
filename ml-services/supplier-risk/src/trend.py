"""
Trend calculation module for the Supplier Risk NLP pipeline.

Provides date-aware risk trend aggregation across headlines over time,
reusing the core predict() scoring pipeline without modifying scoring logic.
"""

from collections import defaultdict
from datetime import datetime
import re
from typing import Any, Dict, List, Optional

from src.config import Settings, get_settings
from src.predict import predict

_ISO_DATE_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def validate_date(date_str: Any) -> str:
    """
    Validate that date_str is a string in ISO format YYYY-MM-DD
    representing a valid calendar date.

    Raises:
        ValueError: If the date string is malformed, not a string,
                    or an invalid calendar date (e.g., 2026-99-99, 2026-02-30).
    """
    if not isinstance(date_str, str):
        raise ValueError(f"Date must be a string, got {type(date_str).__name__}")

    stripped = date_str.strip()
    if not _ISO_DATE_REGEX.match(stripped):
        raise ValueError(
            f"Invalid date format '{date_str}'. Expected ISO format YYYY-MM-DD."
        )

    try:
        parsed = datetime.strptime(stripped, "%Y-%m-%d").date()
        if parsed.strftime("%Y-%m-%d") != stripped:
            raise ValueError(f"Invalid calendar date '{date_str}'.")
    except ValueError as exc:
        raise ValueError(f"Invalid calendar date '{date_str}': {exc}") from exc

    return stripped


def calculate_recency_weighted_confidence(
    risk_trend: List[Dict[str, Any]],
    half_life_days: float = 30.0,
) -> float:
    """
    Calculate timeline-level overall confidence weighted by recency and evidence volume.

    Uses exponential half-life decay relative to the latest date in the timeline:
        weight_i = 2 ** (-age_days / half_life_days) * headline_count_i

    Args:
        risk_trend: List of trend points with 'date', 'confidence', and 'headline_count'.
        half_life_days: Half-life in days for exponential recency decay.

    Returns:
        float: Bounded confidence score in [0.0, 1.0], rounded to 4 decimals.
    """
    if not risk_trend:
        return 0.0

    parsed_dates = [
        datetime.strptime(p["date"], "%Y-%m-%d").date()
        for p in risk_trend
    ]
    latest_date = max(parsed_dates)
    safe_half_life = half_life_days if half_life_days > 0 else 30.0

    total_weight = 0.0
    weighted_conf_sum = 0.0

    for point, p_date in zip(risk_trend, parsed_dates):
        delta_days = (latest_date - p_date).days
        recency_factor = 2.0 ** (-float(delta_days) / safe_half_life)
        volume_weight = max(1, point.get("headline_count", 1))
        weight = recency_factor * volume_weight

        total_weight += weight
        weighted_conf_sum += weight * point.get("confidence", 0.0)

    if total_weight <= 0.0:
        return 0.0

    overall = weighted_conf_sum / total_weight
    return round(min(1.0, max(0.0, overall)), 4)


def calculate_supplier_trend(
    supplier_name: str,
    records: List[Dict[str, Any]],
    config: Optional[Settings] = None,
) -> Dict[str, Any]:
    """
    Calculate entity-level risk trend over time for a supplier, including
    per-date evidence explanation and timeline-level top evidence.

    Aggregates headlines by validated date, sorts them chronologically,
    and calculates risk score, confidence, headline count, and supporting evidence
    for each date using the existing predict() scoring engine.

    Args:
        supplier_name: Name of the supplier.
        records: List of date-aware headline records, each containing 'date' and 'headline'.
        config: Optional Settings configuration.

    Returns:
        Dict containing supplier name, timeline overall confidence, top evidence,
        and chronologically ordered risk_trend points:
        {
            "supplier": "Tesla",
            "overall_confidence": 0.7812,
            "top_evidence": [...],
            "risk_trend": [
                {
                    "date": "2026-01-01",
                    "risk_score": 20.0,
                    "confidence": 0.4,
                    "headline_count": 2,
                    "evidence": [...]
                }, ...
            ]
        }
    """
    cfg = config if config is not None else get_settings()

    if not supplier_name or not supplier_name.strip():
        raise ValueError("supplier_name cannot be blank or whitespace-only")

    cleaned_supplier = supplier_name.strip()

    if not records:
        return {
            "supplier": cleaned_supplier,
            "overall_confidence": 0.0,
            "top_evidence": [],
            "risk_trend": [],
        }

    # Group headlines by validated date
    date_grouped: Dict[str, List[str]] = defaultdict(list)

    for idx, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f"Record at index {idx} must be a dictionary")

        if "date" not in record or record["date"] is None:
            raise ValueError(f"Record at index {idx} is missing required 'date' field")

        validated_date = validate_date(record["date"])

        if "headline" not in record or record["headline"] is None:
            raise ValueError(f"Record at index {idx} is missing required 'headline' field")

        headline = record["headline"]
        if not isinstance(headline, str):
            raise ValueError(f"Headline at index {idx} must be a string")

        date_grouped[validated_date].append(headline)

    # Sort dates chronologically
    sorted_dates = sorted(
        date_grouped.keys(),
        key=lambda d: datetime.strptime(d, "%Y-%m-%d").date(),
    )

    risk_trend: List[Dict[str, Any]] = []

    for date_str in sorted_dates:
        raw_headlines = date_grouped[date_str]

        # Deduplicate headlines (case & whitespace insensitive) consistent with predict()
        seen = set()
        unique_headlines: List[str] = []
        for h in raw_headlines:
            if not h or not h.strip():
                continue
            norm = h.strip().lower()
            if norm not in seen:
                seen.add(norm)
                unique_headlines.append(h.strip())

        if not unique_headlines:
            prediction = predict(
                supplier_name=cleaned_supplier,
                headlines=[],
                config=cfg,
            )
            headline_count = 0
            date_evidence: List[Dict[str, Any]] = []
        else:
            prediction = predict(
                supplier_name=cleaned_supplier,
                headlines=unique_headlines,
                config=cfg,
            )
            headline_count = len(unique_headlines)
            # top_worst_3 contains the highest risk-driving headlines with sentiment and signals
            date_evidence = prediction.get("top_worst_3", [])

        risk_trend.append(
            {
                "date": date_str,
                "risk_score": prediction["risk_score"],
                "confidence": prediction["confidence"],
                "headline_count": headline_count,
                "evidence": date_evidence,
            }
        )

    # Aggregate timeline-level top evidence (highest risk headlines across all dates)
    all_evidence: List[Dict[str, Any]] = []
    for point in risk_trend:
        all_evidence.extend(point.get("evidence", []))

    seen_evidence_headlines = set()
    unique_top_evidence: List[Dict[str, Any]] = []
    sorted_all_evidence = sorted(all_evidence, key=lambda e: e["score"], reverse=True)
    for item in sorted_all_evidence:
        h_norm = item["headline"].strip().lower()
        if h_norm not in seen_evidence_headlines:
            seen_evidence_headlines.add(h_norm)
            unique_top_evidence.append(item)
    top_evidence = unique_top_evidence[:3]

    # Calculate overall timeline confidence with recency decay
    overall_confidence = calculate_recency_weighted_confidence(
        risk_trend,
        half_life_days=cfg.recency_half_life_days,
    )

    return {
        "supplier": cleaned_supplier,
        "overall_confidence": overall_confidence,
        "top_evidence": top_evidence,
        "risk_trend": risk_trend,
    }
