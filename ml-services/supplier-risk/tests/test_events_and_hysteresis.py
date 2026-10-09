"""
Comprehensive tests for Supplier Risk Score-Change Events and Hysteresis.

Covers:
- Event envelope fields and timezone-aware UTC ISO timestamp.
- Correct event type ('supplierrisk.score.changed') and tier mapping (Low->low, Medium->medium, High->high, Critical->high).
- No event when tier remains unchanged.
- Upward and downward tier transitions.
- Scores oscillating around boundaries do not cause repeated events.
- Exact threshold behavior.
- Insufficient evidence blocks a transition (retains previous accepted tier).
- Sufficient evidence allows a transition.
- State isolation between suppliers.
- Supporting articles and explanation included in event payload.
- In-memory and mock Kafka publisher abstractions.
- Custom tier threshold adaptation and regression tests.
- Invalid hysteresis configurations raising ValueError.
- Historical comparison deterministic replay and valid report generation.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
from unittest.mock import patch
import uuid

import pytest

from src.config import (
    DEFAULT_HYSTERESIS_ENTER_HIGH,
    DEFAULT_HYSTERESIS_ENTER_MEDIUM,
    DEFAULT_HYSTERESIS_EXIT_HIGH,
    DEFAULT_HYSTERESIS_EXIT_MEDIUM,
    DEFAULT_HYSTERESIS_MIN_EVIDENCE,
    DEFAULT_TIER_LOW_CEILING,
    DEFAULT_TIER_MEDIUM_CEILING,
    Settings,
    validate_hysteresis_thresholds,
)
from src.evaluate import assign_risk_tier
from src.events import (
    EVENT_TYPE,
    EVENT_VERSION,
    InMemoryEventPublisher,
    KafkaEventPublisher,
    MockKafkaProducer,
    build_score_changed_event,
    map_tier_to_event_tier,
)
from src.hysteresis import (
    HysteresisConfig,
    SupplierHysteresisTracker,
    SupplierState,
    evaluate_transition,
    initial_tier_for_score,
)


# ------------------------------------------------------------------
# 1. Event Contract & Envelope Tests
# ------------------------------------------------------------------


def test_event_envelope_fields_and_utc_timestamp():
    """Verify event envelope has standard fields and timezone-aware UTC ISO timestamp."""
    event = build_score_changed_event(
        supplier="Acme Corp",
        previous_tier="low",
        new_tier="medium",
        risk_score=64.5,
        supporting_articles=[
            {"headline": "Acme faces labor strike", "date": "2026-02-01", "score": 65.0}
        ],
    )

    # Standard envelope fields
    assert "event_id" in event
    # Verify valid UUID
    uuid_obj = uuid.UUID(event["event_id"])
    assert str(uuid_obj) == event["event_id"]

    assert event["event_type"] == "supplierrisk.score.changed"
    assert event["event_version"] == 1
    assert event["producer"] == "supplier-risk-service"

    # Verify timezone-aware UTC ISO timestamp
    assert "occurred_at" in event
    dt = datetime.fromisoformat(event["occurred_at"])
    assert dt.tzinfo is not None, "Timestamp must be timezone-aware"

    # Payload fields
    payload = event["payload"]
    assert payload["supplier"] == "Acme Corp"
    assert payload["previous_tier"] == "low"
    assert payload["new_tier"] == "medium"
    assert payload["risk_score"] == 64.5
    assert payload["evidence_count"] == 1
    assert len(payload["supporting_articles"]) == 1
    assert "explanation" in payload and len(payload["explanation"]) > 0


def test_tier_mapping_correctness():
    """Verify mapping internal 4-tier model to standard 3-tier event schema."""
    assert map_tier_to_event_tier("Low") == "low"
    assert map_tier_to_event_tier("low") == "low"
    assert map_tier_to_event_tier("Medium") == "medium"
    assert map_tier_to_event_tier("medium") == "medium"
    assert map_tier_to_event_tier("High") == "high"
    assert map_tier_to_event_tier("high") == "high"
    assert map_tier_to_event_tier("Critical") == "high"
    assert map_tier_to_event_tier("critical") == "high"

    with pytest.raises(ValueError):
        map_tier_to_event_tier("Extreme")

    with pytest.raises(ValueError):
        map_tier_to_event_tier(123)  # type: ignore


# ------------------------------------------------------------------
# 2. Hysteresis Transitions & Boundary Tests
# ------------------------------------------------------------------


def test_no_event_when_tier_remains_unchanged():
    """Verify no event is emitted when score changes within the same tier."""
    tracker = SupplierHysteresisTracker()

    # Initial update establishes accepted tier (default 'low' for score 45.0)
    ev1 = tracker.process_update(
        supplier="Supplier A",
        risk_score=45.0,
        supporting_articles=[{"headline": "Normal report", "date": "2026-01-01"}],
    )
    assert ev1 is None

    # Score moves to 52.0 (still low, below enter_medium 62.0)
    ev2 = tracker.process_update(
        supplier="Supplier A",
        risk_score=52.0,
        supporting_articles=[
            {"headline": "Normal report 1", "date": "2026-01-08"},
            {"headline": "Normal report 2", "date": "2026-01-08"},
        ],
    )
    assert ev2 is None
    state = tracker.get_state("Supplier A")
    assert state is not None
    assert state.accepted_tier == "low"
    assert state.transition_count == 0


def test_upward_and_downward_tier_transitions():
    """Verify upward and downward transitions emit valid events when criteria are met."""
    tracker = SupplierHysteresisTracker(config=HysteresisConfig(min_evidence=2))

    # 1. Initialize in Low
    tracker.process_update(supplier="Alpha", risk_score=40.0)

    # 2. Upward transition: Low -> Medium (score 65.0 >= enter_medium 62.0)
    ev_up = tracker.process_update(
        supplier="Alpha",
        risk_score=65.0,
        supporting_articles=[
            {"headline": "Article 1", "date": "2026-01-10", "score": 64.0},
            {"headline": "Article 2", "date": "2026-01-11", "score": 66.0},
        ],
    )
    assert ev_up is not None
    assert ev_up["payload"]["previous_tier"] == "low"
    assert ev_up["payload"]["new_tier"] == "medium"
    assert ev_up["payload"]["risk_score"] == 65.0
    assert tracker.get_state("Alpha").accepted_tier == "medium"

    # 3. Upward transition: Medium -> High (score 76.0 >= enter_high 74.0)
    ev_high = tracker.process_update(
        supplier="Alpha",
        risk_score=76.0,
        supporting_articles=[
            {"headline": "Lawsuit filed", "date": "2026-01-15", "score": 75.0},
            {"headline": "Recall issued", "date": "2026-01-16", "score": 77.0},
        ],
    )
    assert ev_high is not None
    assert ev_high["payload"]["previous_tier"] == "medium"
    assert ev_high["payload"]["new_tier"] == "high"

    # 4. Downward transition: High -> Medium (score 68.0 < exit_high 70.0)
    ev_down_med = tracker.process_update(
        supplier="Alpha",
        risk_score=68.0,
        supporting_articles=[
            {"headline": "Recall resolved", "date": "2026-01-22", "score": 67.0},
            {"headline": "Production resumed", "date": "2026-01-23", "score": 69.0},
        ],
    )
    assert ev_down_med is not None
    assert ev_down_med["payload"]["previous_tier"] == "high"
    assert ev_down_med["payload"]["new_tier"] == "medium"

    # 5. Downward transition: Medium -> Low (score 55.0 < exit_medium 58.0)
    ev_down_low = tracker.process_update(
        supplier="Alpha",
        risk_score=55.0,
        supporting_articles=[
            {"headline": "Profitable quarter", "date": "2026-01-29", "score": 54.0},
            {"headline": "New contracts signed", "date": "2026-01-30", "score": 56.0},
        ],
    )
    assert ev_down_low is not None
    assert ev_down_low["payload"]["previous_tier"] == "medium"
    assert ev_down_low["payload"]["new_tier"] == "low"
    assert tracker.get_state("Alpha").accepted_tier == "low"


def test_scores_oscillating_around_boundaries_do_not_cause_repeated_events():
    """Verify hysteresis deadbands eliminate chatter near nominal boundaries 60 and 72."""
    tracker = SupplierHysteresisTracker(
        config=HysteresisConfig(
            enter_medium_threshold=62.0,
            exit_medium_threshold=58.0,
            enter_high_threshold=74.0,
            exit_high_threshold=70.0,
            min_evidence=2,
        )
    )

    # Establish supplier in Medium
    tracker.set_state("Beta", tier="medium", score=65.0)

    articles = [
        {"headline": "News 1", "date": "2026-02-01"},
        {"headline": "News 2", "date": "2026-02-02"},
    ]

    # Oscillate around 60 boundary: 59.5, 60.5, 58.5, 61.5, 59.0
    # In baseline, each crossing of 60.0 would flip between Low and Medium.
    # In hysteresis (deadband [58.0, 62.0)), all these remain Medium!
    oscillations_low_med = [59.5, 60.5, 58.5, 61.5, 59.0]
    for score in oscillations_low_med:
        ev = tracker.process_update(supplier="Beta", risk_score=score, supporting_articles=articles)
        assert ev is None, f"Expected no event for oscillating score {score} in deadband"
        assert tracker.get_state("Beta").accepted_tier == "medium"

    # Move to High
    ev_high = tracker.process_update(
        supplier="Beta",
        risk_score=75.0,
        supporting_articles=articles,
    )
    assert ev_high is not None
    assert tracker.get_state("Beta").accepted_tier == "high"

    # Oscillate around 72 boundary: 71.5, 72.5, 70.5, 73.0, 71.0
    # In baseline, each crossing of 72.0 would flip between Medium and High.
    # In hysteresis (deadband [70.0, 74.0)), all these remain High!
    oscillations_med_high = [71.5, 72.5, 70.5, 73.0, 71.0]
    for score in oscillations_med_high:
        ev = tracker.process_update(supplier="Beta", risk_score=score, supporting_articles=articles)
        assert ev is None, f"Expected no event for oscillating score {score} near 72 boundary"
        assert tracker.get_state("Beta").accepted_tier == "high"


def test_exact_threshold_behavior():
    """Verify exact boundary values and strict inequality semantics."""
    cfg = HysteresisConfig(
        enter_medium_threshold=62.0,
        exit_medium_threshold=58.0,
        enter_high_threshold=74.0,
        exit_high_threshold=70.0,
    )

    # 1. Low -> Medium (>= 62.00)
    assert evaluate_transition("low", 61.99, cfg) == "low"
    assert evaluate_transition("low", 62.00, cfg) == "medium"

    # 2. Medium -> Low (< 58.00)
    assert evaluate_transition("medium", 58.00, cfg) == "medium"
    assert evaluate_transition("medium", 57.99, cfg) == "low"

    # 3. Medium -> High (>= 74.00)
    assert evaluate_transition("medium", 73.99, cfg) == "medium"
    assert evaluate_transition("medium", 74.00, cfg) == "high"

    # 4. High -> Medium (< 70.00)
    assert evaluate_transition("high", 70.00, cfg) == "high"
    assert evaluate_transition("high", 69.99, cfg) == "medium"

    # 5. Direct jumps
    assert evaluate_transition("low", 74.00, cfg) == "high"
    assert evaluate_transition("high", 57.99, cfg) == "low"


# ------------------------------------------------------------------
# 3. Minimum Evidence Gating Tests
# ------------------------------------------------------------------


def test_insufficient_evidence_blocks_transition():
    """Verify insufficient supporting articles retains previous accepted tier."""
    tracker = SupplierHysteresisTracker(config=HysteresisConfig(min_evidence=3))
    tracker.set_state("Gamma", tier="low", score=30.0)

    # Score jumps to 80.0 (High), but only 2 articles provided (requires 3)
    ev = tracker.process_update(
        supplier="Gamma",
        risk_score=80.0,
        supporting_articles=[
            {"headline": "Article 1", "date": "2026-03-01"},
            {"headline": "Article 2", "date": "2026-03-02"},
        ],
    )
    assert ev is None
    state = tracker.get_state("Gamma")
    assert state.accepted_tier == "low", "Must retain previous accepted tier when evidence is insufficient"
    assert state.transition_count == 0


def test_sufficient_evidence_allows_transition():
    """Verify transition is accepted once corroborating evidence reaches min_evidence."""
    tracker = SupplierHysteresisTracker(config=HysteresisConfig(min_evidence=3))
    tracker.set_state("Delta", tier="low", score=30.0)

    # 3 articles provided for score 80.0
    ev = tracker.process_update(
        supplier="Delta",
        risk_score=80.0,
        supporting_articles=[
            {"headline": "Investigation 1", "date": "2026-03-01"},
            {"headline": "Investigation 2", "date": "2026-03-02"},
            {"headline": "Sanction warning", "date": "2026-03-03"},
        ],
    )
    assert ev is not None
    assert ev["payload"]["previous_tier"] == "low"
    assert ev["payload"]["new_tier"] == "high"
    assert ev["payload"]["evidence_count"] == 3
    assert tracker.get_state("Delta").accepted_tier == "high"


# ------------------------------------------------------------------
# 4. Supplier Isolation & State Independence Tests
# ------------------------------------------------------------------


def test_state_isolation_between_suppliers():
    """Verify updates to one supplier do not impact any other supplier's state."""
    tracker = SupplierHysteresisTracker(config=HysteresisConfig(min_evidence=2))

    tracker.set_state("Supplier X", tier="low", score=40.0)
    tracker.set_state("Supplier Y", tier="medium", score=65.0)

    # Transition Supplier X to High
    tracker.process_update(
        supplier="Supplier X",
        risk_score=85.0,
        supporting_articles=[
            {"headline": "A", "date": "2026-01-01"},
            {"headline": "B", "date": "2026-01-02"},
        ],
    )

    state_x = tracker.get_state("Supplier X")
    state_y = tracker.get_state("Supplier Y")

    assert state_x.accepted_tier == "high"
    assert state_x.transition_count == 1

    # Supplier Y must remain completely untouched
    assert state_y.accepted_tier == "medium"
    assert state_y.transition_count == 0
    assert state_y.last_score == 65.0


# ------------------------------------------------------------------
# 5. Publisher Abstraction Tests
# ------------------------------------------------------------------


def test_in_memory_and_mock_kafka_publishers():
    """Verify in-memory publisher and mock Kafka publisher work properly."""
    in_memory = InMemoryEventPublisher()
    tracker = SupplierHysteresisTracker(publisher=in_memory)

    tracker.set_state("PublisherTest", tier="low", score=40.0)
    ev = tracker.process_update(
        supplier="PublisherTest",
        risk_score=75.0,
        supporting_articles=[
            {"headline": "H1", "date": "2026-01-01"},
            {"headline": "H2", "date": "2026-01-02"},
        ],
    )
    assert ev is not None
    assert in_memory.count() == 1
    assert in_memory.get_events()[0] == ev

    # Test MockKafkaProducer with KafkaEventPublisher
    mock_producer = MockKafkaProducer()
    kafka_pub = KafkaEventPublisher(producer=mock_producer)

    success = kafka_pub.publish(ev)
    assert success is True
    assert len(mock_producer.messages) == 1
    assert mock_producer.messages[0]["topic"] == EVENT_TYPE

    # Test mock failure handling
    mock_producer.fail_delivery = True
    fail_res = kafka_pub.publish(ev)
    assert fail_res is False


# ------------------------------------------------------------------
# 6. Regression: Custom Tier Ceilings & Invalid Hysteresis Configs
# ------------------------------------------------------------------


def test_custom_tier_thresholds_compatibility():
    """
    Regression test: Verify Settings adapts hysteresis defaults dynamically
    when custom tier ceilings are passed (such as 40, 65, 80), without ValueError.
    """
    custom_cfg = Settings(
        tier_low_ceiling=40.0,
        tier_medium_ceiling=65.0,
        tier_high_ceiling=80.0,
    )
    # Hysteresis thresholds should have dynamically adapted around 40.0 and 65.0
    assert custom_cfg.hysteresis_exit_medium < custom_cfg.tier_low_ceiling <= custom_cfg.hysteresis_enter_medium
    assert custom_cfg.hysteresis_enter_medium < custom_cfg.hysteresis_exit_high
    assert custom_cfg.hysteresis_exit_high <= custom_cfg.tier_medium_ceiling <= custom_cfg.hysteresis_enter_high

    # Verify assign_risk_tier behavior is preserved
    assert assign_risk_tier(50.0, config=custom_cfg) == "Medium"
    assert assign_risk_tier(35.0, config=custom_cfg) == "Low"
    assert assign_risk_tier(75.0, config=custom_cfg) == "High"
    assert assign_risk_tier(85.0, config=custom_cfg) == "Critical"


def test_invalid_hysteresis_configurations_raise_value_error():
    """Verify invalid threshold orderings or negative bounds raise clear ValueError."""
    # 1. exit_medium > low_ceiling
    with pytest.raises(ValueError):
        validate_hysteresis_thresholds(
            enter_medium=62.0,
            exit_medium=65.0,  # Invalid: 65 > 60
            enter_high=74.0,
            exit_high=70.0,
            low_ceiling=60.0,
            medium_ceiling=72.0,
        )

    # 2. enter_medium < low_ceiling
    with pytest.raises(ValueError):
        validate_hysteresis_thresholds(
            enter_medium=55.0,  # Invalid: 55 < 60
            exit_medium=50.0,
            enter_high=74.0,
            exit_high=70.0,
            low_ceiling=60.0,
            medium_ceiling=72.0,
        )

    # 3. enter_medium >= exit_high (deadbands overlap)
    with pytest.raises(ValueError):
        validate_hysteresis_thresholds(
            enter_medium=72.0,  # Invalid: 72 >= 70
            exit_medium=58.0,
            enter_high=74.0,
            exit_high=70.0,
            low_ceiling=60.0,
            medium_ceiling=72.0,
        )

    # 4. HysteresisConfig with invalid min_evidence
    with pytest.raises(ValueError):
        HysteresisConfig(min_evidence=0)

    # 5. Settings with invalid min_evidence
    with pytest.raises(ValueError):
        Settings(hysteresis_min_evidence=0)


def test_hysteresis_thresholds_edge_cases_and_type_validation():
    """
    Regression test: verify non-numeric types raise TypeError,
    out-of-bounds thresholds (> 100 or < 0) raise ValueError,
    and extreme narrow / high ceilings derive mathematically sound thresholds.
    """
    # 1. Non-numeric types raise TypeError
    with pytest.raises(TypeError):
        validate_hysteresis_thresholds(
            enter_medium="invalid",  # type: ignore
            exit_medium=58.0,
            enter_high=74.0,
            exit_high=70.0,
        )

    with pytest.raises(TypeError):
        validate_hysteresis_thresholds(
            enter_medium=62.0,
            exit_medium=None,  # type: ignore
            enter_high=74.0,
            exit_high=70.0,
        )

    with pytest.raises(TypeError):
        validate_hysteresis_thresholds(
            enter_medium=62.0,
            exit_medium=58.0,
            enter_high=True,  # type: ignore
            exit_high=70.0,
        )

    # 2. Out-of-bounds (> 100 or < 0)
    with pytest.raises(ValueError):
        validate_hysteresis_thresholds(
            enter_medium=62.0,
            exit_medium=58.0,
            enter_high=105.0,  # Invalid: > 100
            exit_high=70.0,
        )

    with pytest.raises(ValueError):
        validate_hysteresis_thresholds(
            enter_medium=62.0,
            exit_medium=-1.0,  # Invalid: < 0
            enter_high=74.0,
            exit_high=70.0,
        )

    # 3. exit_high > medium_ceiling or enter_high < medium_ceiling
    with pytest.raises(ValueError):
        validate_hysteresis_thresholds(
            enter_medium=62.0,
            exit_medium=58.0,
            enter_high=74.0,
            exit_high=75.0,  # Invalid: exit_high 75 > medium_ceiling 72
            low_ceiling=60.0,
            medium_ceiling=72.0,
        )

    with pytest.raises(ValueError):
        validate_hysteresis_thresholds(
            enter_medium=62.0,
            exit_medium=58.0,
            enter_high=71.0,  # Invalid: enter_high 71 < medium_ceiling 72
            exit_high=70.0,
            low_ceiling=60.0,
            medium_ceiling=72.0,
        )

    # 4. Extreme narrow ceilings: 1.0, 2.0, 3.0
    s_narrow = Settings(tier_low_ceiling=1.0, tier_medium_ceiling=2.0, tier_high_ceiling=3.0)
    assert 0.0 <= s_narrow.hysteresis_exit_medium <= 1.0 <= s_narrow.hysteresis_enter_medium
    assert s_narrow.hysteresis_enter_medium < s_narrow.hysteresis_exit_high
    assert s_narrow.hysteresis_exit_high <= 2.0 <= s_narrow.hysteresis_enter_high <= 100.0

    # 5. Extreme high ceilings: 90.0, 95.0, 99.0
    s_high = Settings(tier_low_ceiling=90.0, tier_medium_ceiling=95.0, tier_high_ceiling=99.0)
    assert 0.0 <= s_high.hysteresis_exit_medium <= 90.0 <= s_high.hysteresis_enter_medium
    assert s_high.hysteresis_enter_medium < s_high.hysteresis_exit_high
    assert s_high.hysteresis_exit_high <= 95.0 <= s_high.hysteresis_enter_high <= 100.0



def test_historical_comparison_deterministic():
    """Verify historical replay produces deterministic metrics and generates valid report."""
    from src.historical_comparison import generate_markdown_report, run_historical_comparison

    # Run replay using default dataset
    results = run_historical_comparison()

    assert results["total_suppliers"] == 25
    assert results["total_articles"] == 300
    assert results["total_baseline_events"] == 43
    assert results["total_hysteresis_events"] == 30
    assert results["reduction_count"] == 13
    assert results["reduction_percent"] == 30.23

    # Generate markdown report to temporary path
    tmp_report = Path(__file__).resolve().parent.parent / "docs" / "HISTORICAL_COMPARISON_REPORT.md"
    report_content = generate_markdown_report(results, output_path=tmp_report)

    assert "Supplier Risk Score-Change Events: Hysteresis Historical Comparison Report" in report_content
    assert "Do not claim hysteresis improved accuracy merely because it reduced event counts." in report_content
    assert "43" in report_content
    assert "30" in report_content
    assert tmp_report.is_file()


def test_historical_comparison_cached_and_uncached_identical():
    """
    Verify that cached and uncached replay executions yield 100% identical outputs.

    Ensures zero drift in event counts, metrics, per-supplier summaries,
    baseline transitions, and hysteresis event payloads across cached vs uncached runs.
    """
    from src.historical_comparison import run_historical_comparison

    cached_res = run_historical_comparison(use_cache=True)
    uncached_res = run_historical_comparison(use_cache=False)

    # 1. Top-level replay counts
    assert cached_res["total_suppliers"] == uncached_res["total_suppliers"] == 25
    assert cached_res["total_articles"] == uncached_res["total_articles"] == 300
    assert cached_res["total_baseline_events"] == uncached_res["total_baseline_events"] == 43
    assert cached_res["total_hysteresis_events"] == uncached_res["total_hysteresis_events"] == 30
    assert cached_res["reduction_count"] == uncached_res["reduction_count"] == 13
    assert cached_res["reduction_percent"] == uncached_res["reduction_percent"] == 30.23

    # 2. Per-supplier summary identity
    assert set(cached_res["per_supplier_summary"].keys()) == set(uncached_res["per_supplier_summary"].keys())
    for s in cached_res["per_supplier_summary"]:
        c_sup = cached_res["per_supplier_summary"][s]
        u_sup = uncached_res["per_supplier_summary"][s]

        assert c_sup["baseline_count"] == u_sup["baseline_count"]
        assert c_sup["hysteresis_count"] == u_sup["hysteresis_count"]
        assert c_sup["reduction_count"] == u_sup["reduction_count"]
        assert c_sup["reduction_percent"] == u_sup["reduction_percent"]
        assert c_sup["final_tier"] == u_sup["final_tier"]
        assert c_sup["baseline_transitions"] == u_sup["baseline_transitions"]

        # Hysteresis event payloads must match identically (ignoring random UUID event_id)
        assert len(c_sup["hysteresis_events"]) == len(u_sup["hysteresis_events"])
        for e_c, e_u in zip(c_sup["hysteresis_events"], u_sup["hysteresis_events"]):
            assert e_c["event_type"] == e_u["event_type"]
            assert e_c["event_version"] == e_u["event_version"]
            assert e_c["producer"] == e_u["producer"]
            assert e_c["occurred_at"] == e_u["occurred_at"]
            assert e_c["payload"] == e_u["payload"]

    # 3. All published events payload identity
    c_events = cached_res["all_published_events"]
    u_events = uncached_res["all_published_events"]
    assert len(c_events) == len(u_events) == 30
    for e_c, e_u in zip(c_events, u_events):
        assert e_c["payload"] == e_u["payload"]


def test_headline_sentiment_cache_integrity():
    """Verify integrity, validity, and coverage of the headline sentiment cache."""
    from src.historical_comparison import (
        DEFAULT_DATASET_PATH,
        load_headline_sentiment_cache,
        load_trend_dataset,
    )

    records = load_trend_dataset(DEFAULT_DATASET_PATH)
    unique_headlines = set(r["headline"] for r in records)

    sentiment_cache = load_headline_sentiment_cache()
    assert len(sentiment_cache) >= 300

    # Ensure every single headline in the 25-supplier dataset is covered
    for h in unique_headlines:
        assert h in sentiment_cache, f"Headline missing from sentiment cache: {h}"
        item = sentiment_cache[h]
        assert item["label"] in {"positive", "neutral", "negative"}
        assert 0.0 <= item["confidence"] <= 1.0


def test_timeline_cache_invalidation_on_config_change():
    """
    Verify that modifying scoring parameters changes the cache key,
    ensuring zero stale results or cross-configuration contamination.
    """
    from src.config import Settings
    from src.historical_comparison import (
        DEFAULT_DATASET_PATH,
        _make_timeline_cache_key,
        _timeline_cache_key_hash,
    )

    cfg_default = Settings()
    key_default = _make_timeline_cache_key(DEFAULT_DATASET_PATH, cfg_default)
    hash_default = _timeline_cache_key_hash(key_default)

    # 1. Alter ceiling
    cfg_altered_ceiling = Settings(tier_low_ceiling=55.0)
    key_altered_ceiling = _make_timeline_cache_key(DEFAULT_DATASET_PATH, cfg_altered_ceiling)
    hash_altered_ceiling = _timeline_cache_key_hash(key_altered_ceiling)
    assert key_default != key_altered_ceiling
    assert hash_default != hash_altered_ceiling

    # 2. Alter aggregation strategy
    cfg_altered_agg = Settings(aggregation_strategy="max")
    key_altered_agg = _make_timeline_cache_key(DEFAULT_DATASET_PATH, cfg_altered_agg)
    hash_altered_agg = _timeline_cache_key_hash(key_altered_agg)
    assert key_default != key_altered_agg
    assert hash_default != hash_altered_agg
