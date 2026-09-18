"""
Trend calculation module for the Supplier Risk NLP pipeline.

Provides date-aware risk trend aggregation across headlines over time,
reusing the core predict() scoring pipeline without modifying scoring logic.
"""

from collections import defaultdict
from datetime import datetime, timedelta
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
    as_of_date: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Calculate real entity-level risk trend aggregation over time for a supplier.

    Groups multiple dated articles by supplier, computes article-level risk scores
    using the core predict() engine, aggregates articles across a configurable
    rolling window (default 30 days) with exponential recency decay weighting,
    compares against a previous historical window, and algorithmically classifies
    trend direction as 'rising', 'falling', or 'stable'.

    Articles outside the current rolling window do NOT contribute to current_risk_score.

    Args:
        supplier_name: Name of the supplier.
        records: List of date-aware headline records, each containing 'date' and 'headline'.
        config: Optional Settings configuration.
        as_of_date: Optional reference date (YYYY-MM-DD). Defaults to the latest article date.

    Returns:
        Dict containing:
        - supplier: str
        - current_risk_score: float
        - previous_risk_score: float | None
        - trend_direction: 'rising' | 'falling' | 'stable'
        - article_count: int (total valid articles)
        - current_window_article_count: int
        - historical_article_count: int
        - window_days: int
        - window_start: str | None (YYYY-MM-DD)
        - window_end: str | None (YYYY-MM-DD)
        - previous_window_start: str | None (YYYY-MM-DD)
        - previous_window_end: str | None (YYYY-MM-DD)
        - overall_confidence: float
        - top_evidence: List[Dict[str, Any]]
        - risk_trend: List[Dict[str, Any]] (chronological per-date points)
    """
    cfg = config if config is not None else get_settings()

    if not supplier_name or not supplier_name.strip():
        raise ValueError("supplier_name cannot be blank or whitespace-only")

    cleaned_supplier = supplier_name.strip()
    window_days = cfg.trend_window_days
    half_life = cfg.recency_half_life_days
    threshold = cfg.trend_direction_threshold

    if not records:
        return {
            "supplier": cleaned_supplier,
            "current_risk_score": 0.0,
            "previous_risk_score": None,
            "trend_direction": "stable",
            "article_count": 0,
            "current_window_article_count": 0,
            "historical_article_count": 0,
            "window_days": window_days,
            "window_start": None,
            "window_end": None,
            "previous_window_start": None,
            "previous_window_end": None,
            "overall_confidence": 0.0,
            "top_evidence": [],
            "risk_trend": [],
        }

    # 1. Validate records and enforce supplier isolation
    valid_records: List[Dict[str, Any]] = []
    seen_articles = set()

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

        stripped_hl = headline.strip()
        if not stripped_hl:
            continue

        # Enforce supplier isolation: if record specifies a supplier, it must match
        if "supplier" in record and record["supplier"]:
            record_supplier = str(record["supplier"]).strip()
            if record_supplier.lower() != cleaned_supplier.lower():
                continue

        # Deduplicate identical (date, headline) pairs
        norm_key = (validated_date, stripped_hl.lower())
        if norm_key in seen_articles:
            continue
        seen_articles.add(norm_key)

        valid_records.append({
            "date": validated_date,
            "headline": stripped_hl,
        })

    if not valid_records:
        return {
            "supplier": cleaned_supplier,
            "current_risk_score": 0.0,
            "previous_risk_score": None,
            "trend_direction": "stable",
            "article_count": 0,
            "current_window_article_count": 0,
            "historical_article_count": 0,
            "window_days": window_days,
            "window_start": None,
            "window_end": None,
            "previous_window_start": None,
            "previous_window_end": None,
            "overall_confidence": 0.0,
            "top_evidence": [],
            "risk_trend": [],
        }

    # 2. Determine reference date and window boundaries
    date_objs = [datetime.strptime(r["date"], "%Y-%m-%d").date() for r in valid_records]
    if as_of_date is not None:
        ref_date = datetime.strptime(validate_date(as_of_date), "%Y-%m-%d").date()
    else:
        ref_date = max(date_objs)

    current_window_start = ref_date - timedelta(days=window_days)

    # 3. Partition articles into current rolling window and previous historical window
    current_articles: List[Dict[str, Any]] = []
    current_article_dates: List[Any] = []
    for r, d in zip(valid_records, date_objs):
        delta_days = (ref_date - d).days
        if 0 <= delta_days <= window_days:
            current_articles.append(r)
            current_article_dates.append(d)

    # Immediate preceding window of equal length (window_days)
    prev_articles: List[Dict[str, Any]] = []
    prev_article_dates: List[Any] = []
    for r, d in zip(valid_records, date_objs):
        delta_days = (ref_date - d).days
        if window_days < delta_days <= 2 * window_days:
            prev_articles.append(r)
            prev_article_dates.append(d)

    # If the immediately preceding window is empty, fall back to all prior historical articles
    if not prev_articles:
        for r, d in zip(valid_records, date_objs):
            delta_days = (ref_date - d).days
            if delta_days > window_days:
                prev_articles.append(r)
                prev_article_dates.append(d)

    # 4. Calculate article-level risk scores using predict() with caching
    article_score_cache: Dict[str, float] = {}

    def _get_article_risk(hl: str) -> float:
        if hl not in article_score_cache:
            p = predict(supplier_name=cleaned_supplier, headlines=[hl], config=cfg)
            article_score_cache[hl] = float(p["risk_score"])
        return article_score_cache[hl]

    # Current window aggregate score (recency-weighted)
    if current_articles:
        curr_weights: List[float] = []
        curr_scores: List[float] = []
        for r, d in zip(current_articles, current_article_dates):
            age_days = (ref_date - d).days
            weight = 2.0 ** (-float(age_days) / half_life)
            score = _get_article_risk(r["headline"])
            curr_weights.append(weight)
            curr_scores.append(score)

        total_curr_weight = sum(curr_weights)
        if total_curr_weight > 0:
            current_risk_score = round(
                sum(s * w for s, w in zip(curr_scores, curr_weights)) / total_curr_weight,
                2,
            )
        else:
            current_risk_score = 0.0

        current_window_start_str = current_window_start.strftime("%Y-%m-%d")
        current_window_end_str = ref_date.strftime("%Y-%m-%d")
    else:
        current_risk_score = 0.0
        current_window_start_str = None
        current_window_end_str = None

    # Previous window aggregate score (recency-weighted relative to previous window anchor)
    if prev_articles:
        prev_anchor_date = ref_date - timedelta(days=window_days)
        prev_weights: List[float] = []
        prev_scores: List[float] = []
        for r, d in zip(prev_articles, prev_article_dates):
            age_days = max(0, (prev_anchor_date - d).days)
            weight = 2.0 ** (-float(age_days) / half_life)
            score = _get_article_risk(r["headline"])
            prev_weights.append(weight)
            prev_scores.append(score)

        total_prev_weight = sum(prev_weights)
        if total_prev_weight > 0:
            previous_risk_score = round(
                sum(s * w for s, w in zip(prev_scores, prev_weights)) / total_prev_weight,
                2,
            )
        else:
            previous_risk_score = None

        prev_window_start_str = min(prev_article_dates).strftime("%Y-%m-%d")
        prev_window_end_str = max(prev_article_dates).strftime("%Y-%m-%d")
    else:
        previous_risk_score = None
        prev_window_start_str = None
        prev_window_end_str = None

    # 5. Determine trend direction algorithmically from current vs previous aggregate
    if previous_risk_score is None:
        trend_direction = "stable"
    else:
        score_diff = current_risk_score - previous_risk_score
        if score_diff > threshold:
            trend_direction = "rising"
        elif score_diff < -threshold:
            trend_direction = "falling"
        else:
            trend_direction = "stable"

    # 6. Chronological risk_trend points (backward compatible timeline)
    date_grouped: Dict[str, List[str]] = defaultdict(list)
    for r in valid_records:
        date_grouped[r["date"]].append(r["headline"])

    sorted_dates = sorted(
        date_grouped.keys(),
        key=lambda d: datetime.strptime(d, "%Y-%m-%d").date(),
    )

    risk_trend: List[Dict[str, Any]] = []
    for date_str in sorted_dates:
        unique_date_headlines = list(dict.fromkeys(date_grouped[date_str]))
        if not unique_date_headlines:
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
                headlines=unique_date_headlines,
                config=cfg,
            )
            headline_count = len(unique_date_headlines)
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

    # Aggregate timeline-level top evidence
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
        half_life_days=half_life,
    )

    return {
        "supplier": cleaned_supplier,
        "current_risk_score": current_risk_score,
        "previous_risk_score": previous_risk_score,
        "trend_direction": trend_direction,
        "article_count": len(valid_records),
        "current_window_article_count": len(current_articles),
        "historical_article_count": len(prev_articles),
        "window_days": window_days,
        "window_start": current_window_start_str,
        "window_end": current_window_end_str,
        "previous_window_start": prev_window_start_str,
        "previous_window_end": prev_window_end_str,
        "overall_confidence": overall_confidence,
        "top_evidence": top_evidence,
        "risk_trend": risk_trend,
    }


def aggregate_supplier_trends(
    records: List[Dict[str, Any]],
    config: Optional[Settings] = None,
    as_of_date: Optional[str] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Group multiple dated articles by supplier and calculate entity-level
    risk trend aggregation for each supplier.

    Args:
        records: List of article dictionaries with 'supplier', 'date', 'headline'.
        config: Optional Settings instance.
        as_of_date: Optional reference date string (YYYY-MM-DD).

    Returns:
        Dict mapping supplier name to its trend summary dictionary.
    """
    supplier_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for idx, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f"Record at index {idx} must be a dictionary")
        supplier = record.get("supplier")
        if not supplier or not isinstance(supplier, str) or not supplier.strip():
            raise ValueError(f"Record at index {idx} is missing required 'supplier' field")
        supplier_groups[supplier.strip()].append(record)

    results: Dict[str, Dict[str, Any]] = {}
    for supplier, supp_records in supplier_groups.items():
        results[supplier] = calculate_supplier_trend(
            supplier_name=supplier,
            records=supp_records,
            config=config,
            as_of_date=as_of_date,
        )
    return results
