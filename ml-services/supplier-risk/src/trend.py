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
from src.evaluate import assign_risk_tier
from src.predict import predict

_TIER_RANK = {"Low": 0, "Medium": 1, "High": 2, "Critical": 3}

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
            "current_risk_tier": assign_risk_tier(0.0, cfg),
            "previous_risk_tier": None,
            "peak_risk_score": 0.0,
            "peak_risk_tier": assign_risk_tier(0.0, cfg),
            "trend_direction": "stable",
            "is_deteriorating": False,
            "risk_delta": None,
            "deterioration_summary": "No headline records provided.",
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
            raise ValueError(f"Record at index {idx} contains an empty or whitespace-only headline")

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
        ref_end = None
        ref_start = None
        if as_of_date is not None:
            try:
                r_date = datetime.strptime(validate_date(as_of_date), "%Y-%m-%d").date()
                ref_end = r_date.strftime("%Y-%m-%d")
                ref_start = (r_date - timedelta(days=window_days)).strftime("%Y-%m-%d")
            except Exception:
                pass
        return {
            "supplier": cleaned_supplier,
            "current_risk_score": 0.0,
            "previous_risk_score": None,
            "current_risk_tier": assign_risk_tier(0.0, cfg),
            "previous_risk_tier": None,
            "peak_risk_score": 0.0,
            "peak_risk_tier": assign_risk_tier(0.0, cfg),
            "trend_direction": "stable",
            "is_deteriorating": False,
            "risk_delta": None,
            "deterioration_summary": "No valid headline records found for supplier.",
            "article_count": 0,
            "current_window_article_count": 0,
            "historical_article_count": 0,
            "window_days": window_days,
            "window_start": ref_start,
            "window_end": ref_end,
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
        kept = [(r, d) for r, d in zip(valid_records, date_objs) if d <= ref_date]
        valid_records = [r for r, _ in kept]
        date_objs = [d for _, d in kept]
    else:
        ref_date = max(date_objs)

    if not valid_records:
        return {
            "supplier": cleaned_supplier,
            "current_risk_score": 0.0,
            "previous_risk_score": None,
            "current_risk_tier": assign_risk_tier(0.0, cfg),
            "previous_risk_tier": None,
            "peak_risk_score": 0.0,
            "peak_risk_tier": assign_risk_tier(0.0, cfg),
            "trend_direction": "stable",
            "is_deteriorating": False,
            "risk_delta": None,
            "deterioration_summary": "No valid headline records found for supplier.",
            "article_count": 0,
            "current_window_article_count": 0,
            "historical_article_count": 0,
            "window_days": window_days,
            "window_start": (ref_date - timedelta(days=window_days)).strftime("%Y-%m-%d") if as_of_date is not None else None,
            "window_end": ref_date.strftime("%Y-%m-%d") if as_of_date is not None else None,
            "previous_window_start": None,
            "previous_window_end": None,
            "overall_confidence": 0.0,
            "top_evidence": [],
            "risk_trend": [],
        }

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

    # 4. Score each window with exactly the same aggregation /predict uses
    #    (top_k_mean anti-dilution). The window itself is the recency control,
    #    so scores are NOT decayed inside a window - decaying before taking the
    #    peak is what let a 4-week-old default shrink to "Low".
    def _window_score(articles: List[Dict[str, Any]]) -> float:
        if not articles:
            return 0.0
        result = predict(
            supplier_name=cleaned_supplier,
            headlines=[a["headline"] for a in articles],
            config=cfg,
        )
        return round(float(result["risk_score"]), 2)

    current_risk_score = _window_score(current_articles)
    current_window_start_str = current_window_start.strftime("%Y-%m-%d")
    current_window_end_str = ref_date.strftime("%Y-%m-%d")

    if prev_articles:
        previous_risk_score = _window_score(prev_articles)
        prev_window_start_str = min(prev_article_dates).strftime("%Y-%m-%d")
        prev_window_end_str = max(prev_article_dates).strftime("%Y-%m-%d")
    else:
        previous_risk_score = None
        prev_window_start_str = None
        prev_window_end_str = None

    current_risk_tier = assign_risk_tier(current_risk_score, cfg)
    previous_risk_tier = (
        assign_risk_tier(previous_risk_score, cfg)
        if previous_risk_score is not None else None
    )

    # Worst score across both windows (~60 days). Compliance gates on this so a
    # supplier that was Critical last month isn't auto-cleared the moment its
    # latest month is quieter.
    peak_risk_score = max(current_risk_score, previous_risk_score or 0.0)
    peak_risk_tier = assign_risk_tier(peak_risk_score, cfg)

    # 5. Determine trend direction and deterioration flag algorithmically
    if previous_risk_score is None:
        trend_direction = "stable"
        is_deteriorating = False
        risk_delta = None
        deterioration_summary = (
            f"Insufficient historical data to establish trend direction. "
            f"Current window score is {current_risk_score:.2f} across {len(current_articles)} articles."
        )
    else:
        score_diff = round(current_risk_score - previous_risk_score, 2)
        risk_delta = score_diff
        if score_diff > threshold:
            trend_direction = "rising"

            # A rise only counts as deterioration if it moves the supplier into a
            # worse tier, or it is already High/Critical.
            tier_worsened = (
                _TIER_RANK[current_risk_tier]
                > _TIER_RANK[previous_risk_tier]
            )
            already_elevated = (
                _TIER_RANK[current_risk_tier] >= _TIER_RANK["High"]
            )

            is_deteriorating = tier_worsened or already_elevated

            if is_deteriorating:
                deterioration_summary = (
                    f"Risk is deteriorating: score increased by +{score_diff:.2f} points "
                    f"(from {previous_risk_score:.2f} {previous_risk_tier} to "
                    f"{current_risk_score:.2f} {current_risk_tier})."
                )
            else:
                deterioration_summary = (
                    f"Risk is rising by +{score_diff:.2f} points but remains "
                    f"{current_risk_tier} (from {previous_risk_score:.2f} to "
                    f"{current_risk_score:.2f}); not flagged as deteriorating."
                )
        elif score_diff < -threshold:
            trend_direction = "falling"
            is_deteriorating = False
            deterioration_summary = (
                f"Risk is improving: score decreased by {score_diff:.2f} points "
                f"(from {previous_risk_score:.2f} to {current_risk_score:.2f})."
            )
        else:
            trend_direction = "stable"
            is_deteriorating = False
            deterioration_summary = (
                f"Risk is stable: score delta of {score_diff:+.2f} points "
                f"(from {previous_risk_score:.2f} to {current_risk_score:.2f}) "
                f"is within the steady-state margin of ±{threshold}."
            )

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
        "current_risk_tier": current_risk_tier,
        "previous_risk_tier": previous_risk_tier,
        "peak_risk_score": peak_risk_score,
        "peak_risk_tier": peak_risk_tier,
        "trend_direction": trend_direction,
        "is_deteriorating": is_deteriorating,
        "risk_delta": risk_delta,
        "deterioration_summary": deterioration_summary,
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


def detect_deteriorating_suppliers(
    records: List[Dict[str, Any]],
    config: Optional[Settings] = None,
    as_of_date: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Scan records across multiple suppliers, compute risk trends, and detect/flag
    all suppliers whose risk profile is deteriorating over time.

    Returns a list of trend summary dictionaries for deteriorating suppliers, sorted by
    risk_delta descending (highest deteriorating increase first).
    """
    all_trends = aggregate_supplier_trends(records, config=config, as_of_date=as_of_date)
    deteriorating = [
        summary for summary in all_trends.values()
        if summary.get("is_deteriorating")
    ]
    deteriorating.sort(key=lambda s: s.get("risk_delta") or 0.0, reverse=True)
    return deteriorating
