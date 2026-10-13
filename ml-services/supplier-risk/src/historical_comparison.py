"""
Historical comparison and replay module for Supplier Risk Score-Change Events.

Replays the 25-supplier, 300-article benchmark dataset (2026-01-05 through 2026-03-23)
chronologically across 12 weekly intervals to compare:
1. Baseline tier transitions without hysteresis.
2. Accepted tier transitions with hysteresis and minimum supporting evidence.

Generates reproducible analysis metrics and the comparison markdown report under docs/.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import copy
import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.config import MODEL_NAME, Settings, get_settings
from src.evaluate import assign_risk_tier
from src.events import (
    EVENT_TYPE,
    InMemoryEventPublisher,
    build_score_changed_event,
    map_tier_to_event_tier,
)
from src.hysteresis import HysteresisConfig, SupplierHysteresisTracker
from src.predict import predict
from src.sentiment import analyze_sentiment

logger = logging.getLogger(__name__)

DEFAULT_DATASET_PATH = Path(__file__).parent / "supplier_trend_headlines_25.json"
DEFAULT_REPORT_PATH = Path(__file__).resolve().parent.parent / "docs" / "HISTORICAL_COMPARISON_REPORT.md"
DEFAULT_SENTIMENT_CACHE_PATH = Path(__file__).parent / "historical_sentiment_cache.json"
# The committed sentiment cache was produced by this model; any other model must re-score.
SENTIMENT_CACHE_MODEL = "ProsusAI/finbert"

# Safe in-memory timeline cache keyed by dataset identity and scoring configuration
_TIMELINE_CACHE: Dict[tuple, Dict[str, List[Dict[str, Any]]]] = {}
# Safe in-memory headline sentiment cache
_SENTIMENT_CACHE: Dict[str, Dict[str, Any]] = {}


def clear_timeline_cache() -> None:
    """Clear in-memory timeline cache."""
    _TIMELINE_CACHE.clear()


def clear_sentiment_cache() -> None:
    """Clear in-memory sentiment cache."""
    _SENTIMENT_CACHE.clear()


def load_headline_sentiment_cache(
    cache_path: Optional[str | Path] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Load persistent headline sentiment cache from JSON file.
    Returns in-memory cache if already loaded.
    """
    if _SENTIMENT_CACHE:
        return _SENTIMENT_CACHE

    if MODEL_NAME != SENTIMENT_CACHE_MODEL:
        logger.warning(
            "Sentiment cache was built with %s but MODEL_NAME is %s; ignoring cache.",
            SENTIMENT_CACHE_MODEL,
            MODEL_NAME,
        )
        return _SENTIMENT_CACHE

    target = Path(cache_path) if cache_path else DEFAULT_SENTIMENT_CACHE_PATH
    if target.is_file():
        try:
            with open(target, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                _SENTIMENT_CACHE.update(loaded)
        except Exception as exc:
            logger.warning("Could not load sentiment cache from %s: %s", target, exc)

    return _SENTIMENT_CACHE


def _timeline_cache_key_hash(cache_key: tuple) -> str:
    """Return deterministic SHA-256 hash of timeline cache key."""
    serialized = json.dumps([str(x) for x in cache_key], sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _make_timeline_cache_key(
    dataset_path: Path,
    config: Settings,
) -> tuple:
    """
    Construct a deterministic cache key containing every input affecting scores.
    Ensures cache misses if the dataset content or any scoring parameter changes.
    """
    try:
        stat = dataset_path.stat()
        mtime = stat.st_mtime_ns
        size = stat.st_size
    except OSError:
        mtime = 0
        size = 0

    return (
        str(dataset_path.resolve()),
        mtime,
        size,
        MODEL_NAME,
        config.aggregation_strategy,
        config.aggregation_top_k,
        config.volume_weight,
        config.mitigation_weight,
        config.trend_window_days,
        config.max_risk_score,
        config.confidence_divisor,
        config.negative_sentiment_penalty,
        config.neutral_sentiment_penalty,
        config.positive_sentiment_penalty,
        config.recency_half_life_days,
        config.tier_low_ceiling,
        config.tier_medium_ceiling,
        config.tier_high_ceiling,
        tuple(sorted(config.signal_weights.items())),
    )


def load_trend_dataset(filepath: Optional[str | Path] = None) -> List[Dict[str, Any]]:
    """
    Load the 25-supplier date-aware trend dataset.
    """
    target = Path(filepath) if filepath else DEFAULT_DATASET_PATH
    if not target.is_file():
        raise FileNotFoundError(f"Trend dataset not found at: {target}")

    with open(target, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError(f"Expected list of records, got {type(data).__name__}")

    return data


def get_current_window_articles(
    supplier_records: List[Dict[str, Any]],
    as_of_date_str: str,
    window_days: int = 30,
    config: Optional[Settings] = None,
    article_score_cache: Optional[Dict[tuple, float]] = None,
    sentiment_fn: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """
    Extract and score articles falling strictly within the rolling window
    [as_of_date - window_days, as_of_date].
    """
    cfg = config or get_settings()
    ref_date = datetime.strptime(as_of_date_str, "%Y-%m-%d").date()

    window_records = []
    for r in supplier_records:
        r_date = datetime.strptime(r["date"], "%Y-%m-%d").date()
        delta = (ref_date - r_date).days
        if 0 <= delta <= window_days:
            window_records.append(r)

    if not window_records:
        return []

    # Score each article to provide headline, date, and score (cached to prevent re-scoring)
    scored_articles: List[Dict[str, Any]] = []
    for r in window_records:
        cache_key = (str(r.get("supplier", "")), r["headline"])
        if article_score_cache is not None and cache_key in article_score_cache:
            score_val = article_score_cache[cache_key]
        else:
            p = predict(
                supplier_name=str(r.get("supplier", "")),
                headlines=[r["headline"]],
                config=cfg,
                sentiment_fn=sentiment_fn,
            )
            score_val = p["risk_score"]
            if article_score_cache is not None:
                article_score_cache[cache_key] = score_val

        scored_articles.append(
            {
                "headline": r["headline"],
                "date": r["date"],
                "score": score_val,
            }
        )

    return scored_articles


def _replay_with_tracker(
    timeline_cache: Dict[str, List[Dict[str, Any]]],
    all_dates: List[str],
    suppliers: List[str],
    h_cfg: HysteresisConfig,
) -> Dict[str, Any]:
    """Replay the timeline through a fresh tracker and collect events and suppressions."""
    publisher = InMemoryEventPublisher()
    tracker = SupplierHysteresisTracker(config=h_cfg, publisher=publisher)
    events: Dict[str, List[Dict[str, Any]]] = {s: [] for s in suppliers}

    for dt_idx, dt in enumerate(all_dates):
        for s in suppliers:
            entry = timeline_cache[s][dt_idx]
            # No articles in the window means no score: nothing to evaluate this week.
            if entry["score"] is None:
                continue
            event = tracker.process_update(
                supplier=s,
                risk_score=entry["score"],
                supporting_articles=entry["supporting_articles"],
                occurred_at=f"{dt}T00:00:00+00:00",
            )
            if event is not None:
                events[s].append(event)

    suppressed: Dict[str, int] = {}
    for state in tracker.get_all_states().values():
        for item in state.history:
            if item["action"] == "suppressed":
                suppressed[item["reason"]] = suppressed.get(item["reason"], 0) + 1

    return {
        "events": events,
        "total": sum(len(v) for v in events.values()),
        "suppressed": suppressed,
        "tracker": tracker,
        "published": publisher.get_events(),
    }


def _percent_reduction(before: int, after: int) -> float:
    return round(((before - after) / before) * 100.0, 2) if before > 0 else 0.0


def run_historical_comparison(
    dataset_path: Optional[str | Path] = None,
    hysteresis_config: Optional[HysteresisConfig] = None,
    config: Optional[Settings] = None,
    precomputed_scores: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    use_cache: bool = True,
    use_sentiment_cache: bool = True,
) -> Dict[str, Any]:
    """
    Replay records chronologically and compare three runs:
    1. Baseline: nominal tier boundaries, no hysteresis, no evidence rule.
    2. Hysteresis only: enter/exit thresholds, evidence rule disabled (min_evidence=0).
    3. Hysteresis + evidence: thresholds plus the minimum supporting-evidence rule.
    """
    cfg = config or get_settings()
    h_cfg = hysteresis_config or HysteresisConfig.from_settings(cfg)
    h_only_cfg = replace(h_cfg, min_evidence=0)

    records = load_trend_dataset(dataset_path)

    all_dates = sorted(set(r["date"] for r in records))
    suppliers = sorted(set(r["supplier"] for r in records))

    grouped_records: Dict[str, List[Dict[str, Any]]] = {
        s: [r for r in records if r["supplier"] == s] for s in suppliers
    }

    target_dataset_path = Path(dataset_path) if dataset_path else DEFAULT_DATASET_PATH
    cache_key = _make_timeline_cache_key(target_dataset_path, cfg)

    if precomputed_scores:
        timeline_cache = copy.deepcopy(precomputed_scores)
    elif use_cache and cache_key in _TIMELINE_CACHE:
        timeline_cache = copy.deepcopy(_TIMELINE_CACHE[cache_key])
    else:
        timeline_cache = {}
        article_score_cache: Dict[tuple, float] = {}
        sentiment_cache: Dict[str, Dict[str, Any]] = (
            dict(load_headline_sentiment_cache()) if use_sentiment_cache else {}
        )
        window_score_cache: Dict[tuple, Dict[str, Any]] = {}

        def cached_analyze_sentiment(text: str) -> Dict[str, Any]:
            cleaned = text.strip()
            if cleaned not in sentiment_cache:
                sentiment_cache[cleaned] = analyze_sentiment(text)
            return sentiment_cache[cleaned]

        for s in suppliers:
            s_recs = grouped_records[s]
            s_dates = [datetime.strptime(r["date"], "%Y-%m-%d").date() for r in s_recs]
            timeline_cache[s] = []

            for dt in all_dates:
                ref_d = datetime.strptime(dt, "%Y-%m-%d").date()
                current_articles = [
                    r for r, d in zip(s_recs, s_dates)
                    if 0 <= (ref_d - d).days <= cfg.trend_window_days
                ]

                if current_articles:
                    win_headlines = tuple(a["headline"] for a in current_articles)
                    win_cache_key = (s, win_headlines)
                    if win_cache_key in window_score_cache:
                        pred = window_score_cache[win_cache_key]
                    else:
                        pred = predict(
                            supplier_name=s,
                            headlines=list(win_headlines),
                            config=cfg,
                            sentiment_fn=cached_analyze_sentiment,
                        )
                        window_score_cache[win_cache_key] = pred

                    score = round(float(pred["risk_score"]), 2)
                    raw_tier = assign_risk_tier(score, cfg)
                    count = len(current_articles)
                else:
                    score = None
                    raw_tier = None
                    count = 0

                win_articles = get_current_window_articles(
                    supplier_records=s_recs,
                    as_of_date_str=dt,
                    window_days=cfg.trend_window_days,
                    config=cfg,
                    article_score_cache=article_score_cache,
                    sentiment_fn=cached_analyze_sentiment,
                )
                timeline_cache[s].append(
                    {
                        "date": dt,
                        "score": score,
                        "raw_tier": raw_tier,
                        "evidence_count": count,
                        "supporting_articles": win_articles,
                    }
                )

        if use_cache:
            _TIMELINE_CACHE[cache_key] = copy.deepcopy(timeline_cache)

    # 1. Baseline replay (no hysteresis, no evidence rule)
    baseline_transitions: Dict[str, List[Dict[str, Any]]] = {s: [] for s in suppliers}
    baseline_states: Dict[str, Optional[str]] = {s: None for s in suppliers}

    for dt_idx, dt in enumerate(all_dates):
        for s in suppliers:
            entry = timeline_cache[s][dt_idx]
            # Same rule as the tracker replays: no score this week, no evaluation.
            if entry["raw_tier"] is None:
                continue
            mapped_tier = map_tier_to_event_tier(entry["raw_tier"])

            curr_state = baseline_states[s]
            if curr_state is None:
                baseline_states[s] = mapped_tier
            elif mapped_tier != curr_state:
                baseline_transitions[s].append(
                    {
                        "date": dt,
                        "previous_tier": curr_state,
                        "new_tier": mapped_tier,
                        "risk_score": entry["score"],
                        "evidence_count": entry["evidence_count"],
                    }
                )
                baseline_states[s] = mapped_tier

    total_baseline_events = sum(len(trans) for trans in baseline_transitions.values())

    # 2. Hysteresis only, and 3. Hysteresis + minimum evidence
    h_only = _replay_with_tracker(timeline_cache, all_dates, suppliers, h_only_cfg)
    h_full = _replay_with_tracker(timeline_cache, all_dates, suppliers, h_cfg)
    total_hysteresis_events = h_full["total"]

    per_supplier_summary: Dict[str, Dict[str, Any]] = {}
    for s in suppliers:
        b_cnt = len(baseline_transitions[s])
        ho_cnt = len(h_only["events"][s])
        h_cnt = len(h_full["events"][s])
        final_state = h_full["tracker"].get_state(s)

        per_supplier_summary[s] = {
            "baseline_count": b_cnt,
            "hysteresis_only_count": ho_cnt,
            "hysteresis_count": h_cnt,
            "reduction_count": b_cnt - h_cnt,
            "reduction_percent": round(((b_cnt - h_cnt) / b_cnt) * 100.0, 1) if b_cnt > 0 else 0.0,
            "final_tier": final_state.accepted_tier if final_state else None,
            "baseline_transitions": baseline_transitions[s],
            "hysteresis_events": h_full["events"][s],
        }

    return {
        "dataset_path": str(dataset_path or DEFAULT_DATASET_PATH),
        "total_suppliers": len(suppliers),
        "total_articles": len(records),
        "date_range": {"start": min(all_dates), "end": max(all_dates)},
        "all_dates": all_dates,
        "config": {
            "tier_low_ceiling": h_cfg.tier_low_ceiling,
            "tier_medium_ceiling": h_cfg.tier_medium_ceiling,
            "enter_medium_threshold": h_cfg.enter_medium_threshold,
            "exit_medium_threshold": h_cfg.exit_medium_threshold,
            "enter_high_threshold": h_cfg.enter_high_threshold,
            "exit_high_threshold": h_cfg.exit_high_threshold,
            "min_evidence": h_cfg.min_evidence,
            "require_min_evidence_for_initial": h_cfg.require_min_evidence_for_initial,
            "top_articles": h_cfg.top_articles,
            "trend_window_days": cfg.trend_window_days,
        },
        "total_baseline_events": total_baseline_events,
        "total_hysteresis_only_events": h_only["total"],
        "total_hysteresis_events": total_hysteresis_events,
        "reduction_from_hysteresis": total_baseline_events - h_only["total"],
        "reduction_from_evidence": h_only["total"] - total_hysteresis_events,
        "reduction_count": total_baseline_events - total_hysteresis_events,
        "reduction_percent": _percent_reduction(total_baseline_events, total_hysteresis_events),
        "suppressed_by_reason": h_full["suppressed"],
        "per_supplier_summary": per_supplier_summary,
        "all_published_events": h_full["published"],
    }


def _supplier_note(data: Dict[str, Any]) -> str:
    """Describe what happened to one supplier, derived only from the counts."""
    b_c = data["baseline_count"]
    ho_c = data["hysteresis_only_count"]
    h_c = data["hysteresis_count"]
    if b_c == 0 and h_c == 0:
        return "No tier changes in any run"
    if h_c == b_c and ho_c == b_c:
        return "All baseline transitions kept"
    if h_c == 0:
        return "All baseline transitions suppressed"
    parts = []
    if b_c != ho_c:
        parts.append(f"hysteresis {b_c} -> {ho_c}")
    if ho_c != h_c:
        parts.append(f"evidence rule {ho_c} -> {h_c}")
    return ", ".join(parts)


def generate_markdown_report(
    results: Dict[str, Any],
    output_path: Optional[str | Path] = None,
) -> str:
    """Generate the comparison report from `results` only (no hand-written numbers) and save it."""
    target = Path(output_path) if output_path else DEFAULT_REPORT_PATH
    target.parent.mkdir(parents=True, exist_ok=True)

    cfg = results["config"]
    dt_range = results["date_range"]
    baseline_tot = results["total_baseline_events"]
    h_only_tot = results["total_hysteresis_only_events"]
    hyst_tot = results["total_hysteresis_events"]
    suppliers_summary = results["per_supplier_summary"]
    suppressed = results["suppressed_by_reason"]
    published = results["all_published_events"]

    lines: List[str] = [
        "# Supplier Risk Score-Change Events: Hysteresis Historical Comparison Report",
        "",
        "> **Event-count reduction measures stability, not accuracy.** "
        "Do not claim hysteresis improved accuracy merely because it reduced event counts.",
        "",
        "> **Data provenance:** the replay dataset (`supplier_trend_headlines_25.json`) is synthetic, "
        "authored in Round 9 for trend regression testing. These numbers show how the rules behave on "
        "that data; they are not evidence from real news.",
        "",
        "## 1. Summary",
        "",
        f"- Dates replayed: `{dt_range['start']}` to `{dt_range['end']}` "
        f"({len(results['all_dates'])} evaluation dates, {cfg['trend_window_days']}-day rolling window)",
        f"- Suppliers: {results['total_suppliers']}; articles: {results['total_articles']}",
        "",
        "| Run | Events | Reduction vs baseline |",
        "| :--- | :---: | :---: |",
        f"| Baseline (nominal boundaries, no rules) | {baseline_tot} | - |",
        f"| Hysteresis only (`min_evidence=0`) | {h_only_tot} | "
        f"{baseline_tot - h_only_tot} ({_percent_reduction(baseline_tot, h_only_tot)}%) |",
        f"| Hysteresis + evidence (`min_evidence={cfg['min_evidence']}`) | {hyst_tot} | "
        f"{baseline_tot - hyst_tot} ({_percent_reduction(baseline_tot, hyst_tot)}%) |",
        "",
        "Suppressed attempts in the hysteresis + evidence run, by reason: "
        + (", ".join(f"`{k}`: {v}" for k, v in sorted(suppressed.items())) or "none"),
        "",
        "## 2. Configuration",
        "",
        "| Parameter | Value | Rule |",
        "| :--- | :---: | :--- |",
        f"| `enter_medium_threshold` | `{cfg['enter_medium_threshold']}` | low -> medium when score >= {cfg['enter_medium_threshold']} |",
        f"| `exit_medium_threshold` | `{cfg['exit_medium_threshold']}` | medium -> low when score < {cfg['exit_medium_threshold']} |",
        f"| `enter_high_threshold` | `{cfg['enter_high_threshold']}` | -> high when score >= {cfg['enter_high_threshold']} |",
        f"| `exit_high_threshold` | `{cfg['exit_high_threshold']}` | high -> medium when score < {cfg['exit_high_threshold']} |",
        f"| `min_evidence` | `{cfg['min_evidence']}` | at least {cfg['min_evidence']} window article(s) whose own score points toward the new tier |",
        f"| `require_min_evidence_for_initial` | `{cfg['require_min_evidence_for_initial']}` | first tier needs at least {cfg['min_evidence']} article(s) in the window |",
        f"| `top_articles` | `{cfg['top_articles']}` | supporting articles carried in each event |",
        "",
        "## 3. Per-Supplier Counts",
        "",
        "| Supplier | Baseline | Hysteresis only | Hysteresis + evidence | Final tier | What changed |",
        "| :--- | :---: | :---: | :---: | :---: | :--- |",
    ]

    for s, data in sorted(suppliers_summary.items(), key=lambda x: (-x[1]["baseline_count"], x[0])):
        lines.append(
            f"| **{s}** | {data['baseline_count']} | {data['hysteresis_only_count']} | "
            f"{data['hysteresis_count']} | `{data['final_tier']}` | {_supplier_note(data)} |"
        )

    lines.extend(["", "## 4. Largest Reductions: Baseline vs Accepted Transitions", ""])
    top_reduced = sorted(
        (item for item in suppliers_summary.items() if item[1]["reduction_count"] > 0),
        key=lambda x: (-x[1]["reduction_count"], x[0]),
    )[:3]
    if not top_reduced:
        lines.append("No supplier had fewer events with hysteresis.")
    for s, data in top_reduced:
        lines.extend(
            [f"### {s}", "", "| Date | Score | Baseline | Accepted |", "| :--- | :---: | :--- | :--- |"]
        )
        accepted = {
            e["occurred_at"][:10]: f"{e['payload']['previous_tier']} -> {e['payload']['new_tier']}"
            for e in data["hysteresis_events"]
        }
        baseline = {t["date"]: t for t in data["baseline_transitions"]}
        for d in sorted(set(accepted) | set(baseline)):
            b = baseline.get(d)
            score = f"{b['risk_score']:.2f}" if b else "-"
            b_txt = f"{b['previous_tier']} -> {b['new_tier']}" if b else "-"
            lines.append(f"| {d} | {score} | {b_txt} | {accepted.get(d, 'no event')} |")
        lines.append("")

    lines.extend(["## 5. Representative Event Envelopes", ""])
    for idx, ev in enumerate(published[:3], start=1):
        payload = ev["payload"]
        lines.extend(
            [
                f"### Example {idx}: `{payload['supplier']}` "
                f"({payload['previous_tier']} -> {payload['new_tier']})",
                "",
                "```json",
                json.dumps(ev, indent=2),
                "```",
                "",
            ]
        )

    lines.extend(
        [
            "## 6. Limitations",
            "",
            "1. Hysteresis delays transitions for scores that stop between a nominal boundary and its enter threshold.",
            "2. Suppliers with too few articles pointing toward a new tier keep their current tier until more arrive.",
            "3. Article-level scores come from scoring each headline on its own, so a headline can count as "
            "evidence even when the aggregated score moved for a different reason.",
            "",
            "---",
            "*Generated by `python -m src.historical_comparison`. Every number above comes from the replay results.*",
        ]
    )

    content = "\n".join(lines) + "\n"
    with open(target, "w", encoding="utf-8") as f:
        f.write(content)

    return content


if __name__ == "__main__":
    print(f"Running historical comparison replay ({DEFAULT_DATASET_PATH.name})...")
    report_results = run_historical_comparison()
    generate_markdown_report(report_results, DEFAULT_REPORT_PATH)
    print(f"Report generated at: {DEFAULT_REPORT_PATH}")
    print(f"Baseline events:              {report_results['total_baseline_events']}")
    print(f"Hysteresis only events:       {report_results['total_hysteresis_only_events']}")
    print(f"Hysteresis + evidence events: {report_results['total_hysteresis_events']}")
    print(f"Suppressed by reason:         {report_results['suppressed_by_reason']}")
