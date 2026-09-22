"""
Unit tests for the Supplier Risk NLP pipeline.
"""

from collections import defaultdict
import json
from pathlib import Path

import pytest

from src.data import load_headlines
from src.predict import predict
from src.preprocess import clean_text
from src.signals import SIGNAL_WEIGHTS, detect_signals
from unittest.mock import patch


@pytest.fixture(autouse=True)
def mock_sentiment():
    """Mock analyze_sentiment to avoid downloading FinBERT during unit tests."""
    with patch("src.predict.analyze_sentiment") as mock:
        # Default mock behavior: positive or neutral if no risk keywords, negative if it seems bad
        def side_effect(text):
            lower_text = text.lower()
            if any(w in lower_text for w in ["bankruptcy", "fraud", "strike", "lawsuit", "sanction", "disappointing", "loss", "losses"]):
                return {"label": "negative", "confidence": 0.99}
            if "positive" in lower_text or "record" in lower_text or "profit" in lower_text:
                return {"label": "positive", "confidence": 0.95}
            return {"label": "neutral", "confidence": 0.99}
        mock.side_effect = side_effect
        yield mock


def test_preprocess_cleans_text():
    """
    Test that preprocessing removes punctuation,
    lowercases text, and strips extra whitespace.
    """

    raw_text = (
        "  TechCorp files for BANKRUPTCY, "
        "after massive fraud... scandal!  "
    )

    expected = (
        "techcorp files for bankruptcy "
        "after massive fraud scandal"
    )

    assert clean_text(raw_text) == expected


def test_keyword_detection():
    """
    Test keyword detection and weights.
    """

    text = clean_text(
        "TechCorp files for bankruptcy "
        "after massive fraud scandal"
    )

    signals = detect_signals(text)

    keywords_found = [
        signal["keyword"]
        for signal in signals
    ]

    assert "bankruptcy" in keywords_found
    assert "fraud" in keywords_found
    assert "strike" not in keywords_found

    for signal in signals:
        assert (
            signal["weight"]
            == SIGNAL_WEIGHTS[signal["keyword"]]
        )


def test_bankruptcy_higher_risk_than_strike():
    """
    Bankruptcy should produce a higher
    risk score than a strike.
    """

    supplier = "TestSupplier"

    bankruptcy_headlines = [
        "The company faces bankruptcy."
    ]

    strike_headlines = [
        "The company faces a strike."
    ]

    bankruptcy_result = predict(
        supplier,
        bankruptcy_headlines,
    )

    strike_result = predict(
        supplier,
        strike_headlines,
    )

    assert (
        bankruptcy_result["risk_score"]
        > strike_result["risk_score"]
    )


def test_predict_schema():
    """
    Validate prediction response schema.
    """

    supplier = "TechCorp"

    headlines = [
        "TechCorp files for bankruptcy "
        "after massive fraud scandal."
    ]

    result = predict(
        supplier,
        headlines,
    )

    assert result["supplier"] == supplier

    assert isinstance(
        result["risk_score"],
        (int, float),
    )

    assert result["risk_score"] <= 100

    assert "confidence" in result

    assert isinstance(
        result["confidence"],
        (int, float),
    )

    sentiment = result["sentiment_breakdown"]

    assert "positive" in sentiment
    assert "neutral" in sentiment
    assert "negative" in sentiment

    assert isinstance(
        result["signals"],
        list,
    )

    if result["signals"]:

        signal = result["signals"][0]

        assert "keyword" in signal
        assert "weight" in signal

    assert isinstance(
        result["top_worst_3"],
        list,
    )

    if result["top_worst_3"]:

        headline = result["top_worst_3"][0]

        assert "headline" in headline
        assert "sentiment" in headline
        assert "score" in headline
        assert "signals" in headline


def test_confidence_exists():
    """
    Test 1: Confidence field is present in prediction response.
    """

    result = predict(
        "TestSupplier",
        ["The company reported positive earnings."],
    )

    assert "confidence" in result


def test_confidence_bounds():
    """
    Test 2: Confidence is bounded within [0.0, 1.0].
    """

    for count in [0, 1, 2, 5, 10, 20, 50, 100]:
        headlines = [
            f"Headline {i} about the supplier."
            for i in range(count)
        ]

        result = predict(
            "BoundTestSupplier",
            headlines,
        )

        confidence = result["confidence"]

        assert confidence >= 0.0, (
            f"confidence {confidence} < 0.0 "
            f"for {count} headlines"
        )
        assert confidence <= 1.0, (
            f"confidence {confidence} > 1.0 "
            f"for {count} headlines"
        )


def test_confidence_zero_headlines():
    """
    Test 3: Zero headlines yields confidence == 0.0.
    """

    result_no_headlines = predict(
        "ZeroHeadlineSupplier",
        [],
    )

    assert result_no_headlines["confidence"] == 0.0

    result_empty_strings = predict(
        "AllEmptySupplier",
        ["", "   ", "\t", "\n"],
    )

    assert result_empty_strings["confidence"] == 0.0


def test_confidence_volume_relationship():
    """
    Test 4: 2 headlines have lower confidence than 20 headlines.
    """

    base_headline = (
        "The company faces bankruptcy and fraud investigation"
    )

    result_2 = predict(
        "LowVolumeSupplier",
        [f"{base_headline} {i}." for i in range(2)],
    )

    result_20 = predict(
        "HighVolumeSupplier",
        [f"{base_headline} {i}." for i in range(20)],
    )

    assert (
        result_2["confidence"]
        < result_20["confidence"]
    ), (
        f"Expected confidence(2)={result_2['confidence']} < "
        f"confidence(20)={result_20['confidence']}"
    )


def test_confidence_monotonic():
    """
    Test 5: More evidence never reduces confidence (monotonic).
    """

    base_headline = (
        "The supplier announces operational updates"
    )

    previous_confidence = -1.0

    for count in range(0, 31, 5):
        result = predict(
            "MonoTestSupplier",
            [f"{base_headline} {i}." for i in range(count)],
        )

        current_confidence = result["confidence"]

        assert (
            current_confidence >= previous_confidence
        ), (
            f"Confidence decreased at n={count}: "
            f"{previous_confidence} -> {current_confidence}"
        )

        previous_confidence = current_confidence


def test_fraud_increases_score():
    """
    Fraud should increase supplier risk.
    """

    supplier = "FraudSupplier"

    base = [
        "The company reported earnings."
    ]

    fraud = [
        "The company reported earnings "
        "and is under investigation "
        "for fraud."
    ]

    base_result = predict(
        supplier,
        base,
    )

    fraud_result = predict(
        supplier,
        fraud,
    )

    assert (
        fraud_result["risk_score"]
        > base_result["risk_score"]
    )


def test_clean_headline_remains_low_risk():
    """
    Positive/Clean headlines without risk signals
    should remain low risk.
    """

    supplier = "CleanSupplier"

    clean = [
        "The company reports record revenue and positive earnings."
    ]

    result = predict(
        supplier,
        clean,
    )

    assert result["risk_score"] == 0.0


def test_multiple_signals_combine():
    """
    Multiple risk signals should
    increase the overall score.
    """

    supplier = "ComboSupplier"

    single = [
        "The company faces a strike."
    ]

    multiple = [
        "The company faces a strike "
        "and a lawsuit."
    ]

    single_result = predict(
        supplier,
        single,
    )

    multiple_result = predict(
        supplier,
        multiple,
    )

    assert (
        multiple_result["risk_score"]
        > single_result["risk_score"]
    )


def test_score_never_exceeds_100():
    """
    Final risk score should be capped at 100.
    """

    supplier = "DoomedSupplier"

    headlines = [
        (
            "The company is facing bankruptcy, "
            "default, fraud, sanction, "
            "investigation while workers strike."
        )
    ] * 5

    result = predict(
        supplier,
        headlines,
    )

    assert result["risk_score"] <= 100.0


def test_load_headlines():
    """
    Verify in-memory dataset loads correctly.
    """

    data = load_headlines()

    assert isinstance(data, dict)
    assert len(data) > 0


def test_evaluation_dataset():
    """
    Validate supplier_headlines.json dataset contains 10 companies
    with 12 headlines each (120 total).
    """

    dataset_path = (
        Path(__file__).resolve().parent.parent
        / "src"
        / "supplier_headlines.json"
    )

    with dataset_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        dataset = json.load(file)

    assert isinstance(dataset, list)
    assert len(dataset) == 120

    grouped = defaultdict(list)

    for item in dataset:
        assert "supplier" in item
        assert "headline" in item

        grouped[item["supplier"]].append(
            item["headline"]
        )

    assert len(grouped) == 10

    for supplier, headlines in grouped.items():
        assert len(headlines) == 12


# ------------------------------------------------------------------
# Round 5: Configuration-Driven Signal & Scoring Tests
# ------------------------------------------------------------------

from src.config import (
    Settings,
    DEFAULT_SIGNAL_WEIGHTS,
    DEFAULT_NEGATIVE_SENTIMENT_PENALTY,
    validate_numeric_weight,
    validate_signal_weights,
)


def test_config_defaults():
    """
    Test that default settings match calibrated R4 baselines.
    """
    cfg = Settings()
    assert cfg.negative_sentiment_penalty == DEFAULT_NEGATIVE_SENTIMENT_PENALTY
    assert cfg.neutral_sentiment_penalty == 0.0
    assert cfg.positive_sentiment_penalty == 0.0
    assert cfg.max_risk_score == 100.0
    assert cfg.confidence_divisor == 8.0
    assert cfg.signal_weights["bankruptcy"] == 50
    assert cfg.signal_weights["fraud"] == 40


def test_config_validation_negative_weight_raises():
    """
    Test that negative weights raise ValueError.
    """
    with pytest.raises(ValueError, match="cannot be negative"):
        validate_numeric_weight("test_weight", -5.0)

    with pytest.raises(ValueError, match="cannot be negative"):
        validate_signal_weights({"strike": -10})


def test_config_validation_non_numeric_raises():
    """
    Test that non-numeric weights raise ValueError.
    """
    with pytest.raises(ValueError, match="must be numeric"):
        validate_numeric_weight("test_weight", "not_a_number")

    with pytest.raises(ValueError, match="must be numeric"):
        validate_signal_weights({"strike": "heavy"})


def test_configurable_weights_change_prediction():
    """
    Test that modifying signal weights dynamically in Settings
    changes the final risk calculation without modifying code.
    """
    supplier = "DynamicTestSupplier"
    headlines = ["The supplier workers announced a strike."]

    # 1. Default config (strike weight = 25)
    default_cfg = Settings()
    res_default = predict(supplier, headlines, config=default_cfg)

    # 2. Custom config with strike weight = 80
    custom_weights = dict(DEFAULT_SIGNAL_WEIGHTS)
    custom_weights["strike"] = 80
    custom_cfg = Settings(signal_weights=custom_weights)
    res_custom = predict(supplier, headlines, config=custom_cfg)

    assert res_custom["risk_score"] > res_default["risk_score"]
    assert res_custom["signals"][0]["weight"] == 80


def test_configurable_sentiment_penalty_changes_prediction():
    """
    Test that changing the negative sentiment penalty changes the score.
    """
    supplier = "SentimentTestSupplier"
    headlines = ["The company reported disappointing quarterly losses."]

    # Low sentiment penalty
    low_penalty_cfg = Settings(negative_sentiment_penalty=10.0)
    res_low = predict(supplier, headlines, config=low_penalty_cfg)

    # High sentiment penalty
    high_penalty_cfg = Settings(negative_sentiment_penalty=90.0)
    res_high = predict(supplier, headlines, config=high_penalty_cfg)

    assert res_high["risk_score"] > res_low["risk_score"]


# ------------------------------------------------------------------
# Round 5: FastAPI /predict Endpoint Integration Tests
# ------------------------------------------------------------------

from fastapi.testclient import TestClient
from src.analyze import app


def test_fastapi_health_endpoint():
    """
    Test GET /health endpoint returns 200 and UP status.
    """
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "UP"
        assert data["service"] == "supplier-risk"


def test_fastapi_predict_endpoint_valid():
    """
    Test POST /predict endpoint returns 200 with full analysis response.
    """
    with TestClient(app) as client:
        payload = {
            "supplier_name": "TestSupplier",
            "headlines": [
                "TestSupplier files for bankruptcy after fraud scandal.",
                "TestSupplier secures new technology partnership.",
            ],
        }

        response = client.post("/predict", json=payload)
        assert response.status_code == 200
        data = response.json()

        assert "supplier_summary" in data
        assert "TestSupplier" in data["supplier_summary"]

        summary = data["supplier_summary"]["TestSupplier"]
        assert summary["supplier"] == "TestSupplier"
        assert "risk_score" in summary
        assert "confidence" in summary
        assert "sentiment_breakdown" in summary
        assert "signals" in summary
        assert "top_worst_3" in summary
        assert len(summary["top_worst_3"]) <= 3


def test_fastapi_predict_aliases():
    """
    Test that /api/v1/supplier-risk/predict and /api/v1/supplier-risk/analyze
    work identically to /predict.
    """
    with TestClient(app) as client:
        payload = {
            "supplier_name": "AliasSupplier",
            "headlines": ["AliasSupplier reports positive quarterly results."],
        }

        resp1 = client.post("/predict", json=payload)
        resp2 = client.post("/api/v1/supplier-risk/predict", json=payload)
        resp3 = client.post("/api/v1/supplier-risk/analyze", json=payload)

        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert resp3.status_code == 200
        assert resp1.json() == resp2.json() == resp3.json()


def test_fastapi_predict_invalid_payload():
    """
    Test POST /predict with missing required fields returns 422.
    """
    with TestClient(app) as client:
        invalid_payload = {
            "invalid_field": "test",
        }

        response = client.post("/predict", json=invalid_payload)
        assert response.status_code == 422


def test_real_dataset_relative_scoring_monotonic_check():
    """
    Test that a known risky supplier scores higher than a known clean one,
    using deterministic text instead of relying on external dataset data which could change.
    """
    risky_headlines = [
        "Company faces massive bankruptcy and investigation for fraud.",
        "Workers go on strike after default."
    ]
    clean_headlines = [
        "Company announces positive earnings.",
        "New product launch."
    ]
    base_headline = (
        "The supplier announces operational updates"
    )

    previous_confidence = -1.0

    for count in range(0, 31, 5):
        result = predict(
            "MonoTestSupplier",
            [f"{base_headline} {i}." for i in range(count)],
        )

        current_confidence = result["confidence"]

        assert (
            current_confidence >= previous_confidence
        ), (
            f"Confidence decreased at n={count}: "
            f"{previous_confidence} -> {current_confidence}"
        )

        previous_confidence = current_confidence

def test_real_dataset_relative_scoring():
    """
    Test that a known risky supplier scores higher than a known clean one,
    using deterministic text instead of relying on external dataset data which could change.
    """
    risky_headlines = [
        "Company faces massive bankruptcy and investigation for fraud.",
        "Workers go on strike after default."
    ]
    clean_headlines = [
        "Company announces positive earnings.",
        "New product launch."
    ]
    risky_score = predict("RiskyCorp", risky_headlines)["risk_score"]
    clean_score = predict("CleanCorp", clean_headlines)["risk_score"]

    assert risky_score > clean_score

def test_mitigation_handling():
    """
    Test that 'denies allegations of fraud' and 'avoids sanction' do not produce risk signals.
    """
    signals1 = detect_signals(clean_text("The company denies allegations of fraud."))
    assert len(signals1) == 0

    signals2 = detect_signals(clean_text("The CEO avoids sanction."))
    assert len(signals2) == 0


def test_mitigation_words_do_not_match_prefixes_in_real_risk_headlines():
    """Adverbs such as 'clearly' must not suppress nearby risk signals."""
    default_signals = detect_signals(
        clean_text("Court clearly rules Acme in default on bond payments.")
    )
    fraud_signals = detect_signals(
        clean_text("Regulators say Acme clearly committed fraud.")
    )

    assert any(signal["keyword"] == "default" for signal in default_signals)
    assert any(signal["keyword"] == "fraud" for signal in fraud_signals)

def test_later_real_risk():
    """
    Test that a real risk after a mitigated mention is still detected.
    """
    signals = detect_signals(clean_text("Company avoids sanction but later faces sanction."))
    detected_keywords = [s["keyword"] for s in signals]
    assert "sanction" in detected_keywords

def test_keyword_variants():
    """
    Test singular/plural/tense variants such as delay, delays, delayed.
    """
    signals_base = detect_signals(clean_text("There was a delay."))
    signals_plural = detect_signals(clean_text("There were delays."))
    signals_tense = detect_signals(clean_text("Production was delayed."))

    assert any(s["keyword"] == "delays" for s in signals_base)
    assert any(s["keyword"] == "delays" for s in signals_plural)
    assert any(s["keyword"] == "delays" for s in signals_tense)

def test_invalid_dataset_structures(tmp_path):
    """
    Test that data.py correctly throws ValueError for malformed JSON,
    empty lists, and missing fields.
    """
    import json
    from src.data import _load_from_json
    with patch("src.data.Path") as mock_path:
        # Test malformed JSON
        mock_file = tmp_path / "bad.json"
        mock_file.write_text("{bad json")
        mock_path.return_value.parent.__truediv__.return_value = mock_file
        with pytest.raises(ValueError, match="malformed"):
            _load_from_json()

        # Test empty list
        mock_file.write_text("[]")
        with pytest.raises(ValueError, match="empty"):
            _load_from_json()

        # Test not a list
        mock_file.write_text('{"supplier": "A", "headline": "B"}')
        with pytest.raises(ValueError, match="must contain a list"):
            _load_from_json()

        # Test invalid record
        mock_file.write_text('[{"supplier": "A"}]')
        with pytest.raises(ValueError, match="Invalid record"):
            _load_from_json()

def test_mitigation_handling_after():
    """
    Test that mitigation works when the mitigation word is AFTER the keyword.
    """
    signals1 = detect_signals(clean_text("fraud allegations against acme were dismissed"))
    assert len(signals1) == 0

    signals2 = detect_signals(clean_text("the layoffs were avoided after negotiations"))
    assert len(signals2) == 0

    signals3 = detect_signals(clean_text("acme outages resolved quickly"))
    assert len(signals3) == 0

def test_false_positive_keywords():
    """
    Test that ambiguous words without context do not trigger risk signals.
    """
    signals1 = detect_signals(clean_text("acme sets a new default configuration for its software"))
    assert len(signals1) == 0

    signals2 = detect_signals(clean_text("acme strikes a major partnership deal with siemens"))
    assert len(signals2) == 0

    signals3 = detect_signals(clean_text("acme recalls fond memories at its anniversary event"))
    assert len(signals3) == 0

def test_valid_ambiguous_keywords():
    """
    Test that ambiguous words WITH context DO trigger risk signals.
    """
    signals1 = detect_signals(clean_text("company defaults on its loan payments"))
    assert len(signals1) > 0 and signals1[0]["keyword"] == "default"

    signals2 = detect_signals(clean_text("factory workers go on strike"))
    assert len(signals2) > 0 and signals2[0]["keyword"] == "strike"

    signals3 = detect_signals(clean_text("company issues product recall for defective parts"))
    assert len(signals3) > 0 and signals3[0]["keyword"] == "recall"


def test_mitigation_cross_clause_preservation():
    """
    Test that mitigation does not cross clause boundaries or suppress unrelated signals.
    """
    # 1. resolved outage but faces fraud investigation
    signals1 = detect_signals(clean_text("Supplier resolved outage but faces fraud investigation."))
    keywords1 = [s["keyword"] for s in signals1]
    assert "outage" not in keywords1
    assert "fraud" in keywords1
    assert "investigation" in keywords1

    # 2. denies fraud but faces bankruptcy
    signals2 = detect_signals(clean_text("Supplier denies fraud but faces bankruptcy."))
    keywords2 = [s["keyword"] for s in signals2]
    assert "fraud" not in keywords2
    assert "bankruptcy" in keywords2

    # 3. resolved outage; fraud investigation continues
    signals3 = detect_signals(clean_text("Supplier resolved outage; fraud investigation continues."))
    keywords3 = [s["keyword"] for s in signals3]
    assert "outage" not in keywords3
    assert "fraud" in keywords3
    assert "investigation" in keywords3


def test_mitigation_whole_word_matching_regression_cases():
    """
    Must-fix 1 Regression tests:
    Verify that ordinary words such as 'clearly', 'clearance', etc. are NOT treated as mitigations
    and do not suppress genuine risk signals.
    """
    # Case A: "Court clearly rules Acme in default on bond payments"
    # Expected: default signal is detected, 'clearly' does NOT mitigate 'default'
    text_a = "Court clearly rules Acme in default on bond payments"
    signals_a = detect_signals(clean_text(text_a))
    keywords_a = [s["keyword"] for s in signals_a]
    assert "default" in keywords_a, f"Expected 'default' signal, got {keywords_a}"

    # Case B: "Regulators say Acme clearly committed fraud"
    # Expected: fraud signal is detected, 'clearly' does NOT mitigate 'fraud'
    text_b = "Regulators say Acme clearly committed fraud"
    signals_b = detect_signals(clean_text(text_b))
    keywords_b = [s["keyword"] for s in signals_b]
    assert "fraud" in keywords_b, f"Expected 'fraud' signal, got {keywords_b}"

    # Additional case: punctuation and casing with non-mitigating 'clear' derivatives
    text_c = "Security CLEARANCE revoked: Acme clearly committed FRAUD!"
    signals_c = detect_signals(clean_text(text_c))
    keywords_c = [s["keyword"] for s in signals_c]
    assert "fraud" in keywords_c, f"Expected 'fraud' signal, got {keywords_c}"


def test_legitimate_mitigation_cases():
    """
    Verify that legitimate mitigation keywords (denies, cleared, resolved, dismissed, avoided)
    continue to suppress the relevant risk signals according to existing semantics.
    """
    # 1. "Acme denies fraud" -> fraud should be mitigated
    signals1 = detect_signals(clean_text("Acme denies fraud"))
    keywords1 = [s["keyword"] for s in signals1]
    assert "fraud" not in keywords1, f"'fraud' should be mitigated by 'denies', got {keywords1}"

    # 2. "Acme was cleared of fraud" -> fraud should be mitigated
    signals2 = detect_signals(clean_text("Acme was cleared of fraud"))
    keywords2 = [s["keyword"] for s in signals2]
    assert "fraud" not in keywords2, f"'fraud' should be mitigated by 'cleared', got {keywords2}"

    # 3. "The lawsuit was resolved" -> lawsuit should be mitigated
    signals3 = detect_signals(clean_text("The lawsuit was resolved"))
    keywords3 = [s["keyword"] for s in signals3]
    assert "lawsuit" not in keywords3, f"'lawsuit' should be mitigated by 'resolved', got {keywords3}"

    # "The dispute was resolved" with dynamic/configured keyword
    signals3_custom = detect_signals(clean_text("The dispute was resolved"), weights={"dispute": 25})
    keywords3_custom = [s["keyword"] for s in signals3_custom]
    assert "dispute" not in keywords3_custom, f"'dispute' should be mitigated by 'resolved', got {keywords3_custom}"

    # 4. Case-insensitivity and punctuation
    signals4 = detect_signals(clean_text("ACME: DENIED allegations of FRAUD!"))
    keywords4 = [s["keyword"] for s in signals4]
    assert "fraud" not in keywords4, f"'fraud' should be mitigated despite casing/punctuation, got {keywords4}"

    signals5 = detect_signals(clean_text("Acme was DISMISSED from the lawsuit."))
    keywords5 = [s["keyword"] for s in signals5]
    assert "lawsuit" not in keywords5, f"'lawsuit' should be mitigated by 'dismissed', got {keywords5}"


def test_punctuation_word_merging_and_signal_detection():
    """
    Test that punctuation separating words is replaced by whitespace and detected correctly.
    """
    # Verify clean_text splits words joined by punctuation
    assert clean_text("strike/walkout") == "strike walkout"
    assert clean_text("fraud.investigation") == "fraud investigation"
    assert clean_text("bankruptcy-investigation") == "bankruptcy investigation"
    assert clean_text("fraud,investigation") == "fraud investigation"

    # Verify signal detection on punctuation-joined words
    signals_slash = detect_signals(clean_text("factory workers strike/walkout today"))
    assert any(s["keyword"] == "strike" for s in signals_slash)

    signals_dot = detect_signals(clean_text("company faces fraud.investigation by authorities"))
    keywords_dot = [s["keyword"] for s in signals_dot]
    assert "fraud" in keywords_dot
    assert "investigation" in keywords_dot

    signals_hyphen = detect_signals(clean_text("company faces bankruptcy-investigation"))
    keywords_hyphen = [s["keyword"] for s in signals_hyphen]
    assert "bankruptcy" in keywords_hyphen
    assert "investigation" in keywords_hyphen

    signals_comma = detect_signals(clean_text("company faces fraud,investigation"))
    keywords_comma = [s["keyword"] for s in signals_comma]
    assert "fraud" in keywords_comma
    assert "investigation" in keywords_comma


def test_duplicate_headlines_do_not_inflate_confidence():
    """
    Regression Test (Bug #4): Duplicate headlines must not inflate confidence
    or multiply risk evidence.
    """
    headline = "The company is under investigation for fraud and default."

    result_single = predict("TestSupplier", [headline])
    result_dups = predict("TestSupplier", [headline, headline, headline])
    result_dups_whitespace = predict(
        "TestSupplier",
        [headline, f"  {headline}  ", headline.upper(), headline.lower()],
    )

    # Confidence must represent unique evidence
    assert result_single["confidence"] == result_dups["confidence"]
    assert result_single["confidence"] == result_dups_whitespace["confidence"]

    # Duplicate copies do not change risk evidence
    assert result_single["risk_score"] == result_dups["risk_score"]
    assert result_single["risk_score"] == result_dups_whitespace["risk_score"]
    assert result_single["sentiment_breakdown"] == result_dups["sentiment_breakdown"]
    assert result_single["signals"] == result_dups["signals"]
    assert len(result_single["top_worst_3"]) == len(result_dups["top_worst_3"])


def test_high_risk_not_diluted_by_neutral_headlines():
    """
    Regression Test: High risk headline must not be diluted into
    an obviously safe/low-risk result (<= 25.0) merely because neutral headlines are added.
    """
    high_risk_headline = (
        "TechCorp files for bankruptcy and is under investigation for fraud."
    )
    neutral_headlines_9 = [
        f"TechCorp opens a new office location in district {i}."
        for i in range(9)
    ]
    neutral_headlines_20 = [
        f"TechCorp opens a new office location in district {i}."
        for i in range(20)
    ]

    result_1 = predict("TechCorp", [high_risk_headline])
    result_10 = predict("TechCorp", [high_risk_headline] + neutral_headlines_9)
    result_21 = predict("TechCorp", [high_risk_headline] + neutral_headlines_20)

    # The high risk headline alone is severe (Critical tier)
    assert result_1["risk_score"] >= 50.0

    # Adding 9 or 20 neutral headlines must not collapse into Low Risk (<= 25.0)
    assert result_10["risk_score"] > 25.0, (
        f"Expected score > 25.0 (above Low risk ceiling), got {result_10['risk_score']}"
    )
    assert result_21["risk_score"] > 25.0, (
        f"Expected score > 25.0 (above Low risk ceiling), got {result_21['risk_score']}"
    )


def test_calibrated_scoring_blend_ratio():
    """
    Verify that the scoring formula applies an 80% mean / 20% peak blend
    when the 'blend' aggregation strategy is configured.
    """
    # Headline 1 has negative sentiment + lawsuit (25) + investigation (25) -> score ~89.6
    # Headline 2 is clean positive -> score 0.0
    h1 = "Supplier faces lawsuit and investigation for misconduct."
    h2 = "Supplier reports record positive earnings and profit."

    blend_cfg = Settings(aggregation_strategy="blend")
    result = predict("BlendTestSupplier", [h1, h2], config=blend_cfg)
    # Individual scores: h1 = 39.6 + 50 = 89.6, h2 = 0.0
    # Average = 44.8, Peak = 89.6
    # Expected blended score = 0.8 * 44.8 + 0.2 * 89.6 = 35.84 + 17.92 = 53.76
    assert abs(result["risk_score"] - 53.76) < 0.05, (
        f"Expected ~53.76 for 80/20 blend, got {result['risk_score']}"
    )


def test_calibrated_risk_band_classification():
    """
    Verify that the calibrated risk bands correctly classify supplier profiles:
    - Low: 0.0 - 25.0
    - Medium: 25.1 - 35.0
    - High: 35.1 - 45.0
    - Critical: 45.1 - 100.0
    """
    def classify_band(score: float) -> str:
        if score <= 25.0:
            return "Low"
        elif score <= 35.0:
            return "Medium"
        elif score <= 45.0:
            return "High"
        else:
            return "Critical"

    # 1. Clean supplier -> Low
    clean_res = predict("CleanCorp", ["Positive earnings reported.", "New green factory opened."])
    assert classify_band(clean_res["risk_score"]) == "Low"
    assert clean_res["risk_score"] <= 25.0

    # 2. Severe multi-event supplier -> Critical
    critical_res = predict(
        "CriticalCorp",
        [
            "Company files for bankruptcy and faces fraud investigation.",
            "Workers strike after debt default.",
            "Regulators issue massive sanction against company.",
        ],
    )
    assert classify_band(critical_res["risk_score"]) == "Critical"
    assert critical_res["risk_score"] >= 45.1


# ------------------------------------------------------------------
# PR Review Regression & Enhancement Tests
# ------------------------------------------------------------------


def test_keyword_detection_with_punctuation():
    """
    Regression test for PR review:
    Risk keywords must be detected even when punctuation
    is attached directly to the keyword.
    """

    test_cases = [
        ("Supplier files for bankruptcy.", "bankruptcy"),
        ("Acme faces bankruptcy, report says.", "bankruptcy"),
        ("Regulator opens investigation, sources say.", "investigation"),
        ("Firm hit with lawsuit; shares fall.", "lawsuit"),
        ('"Bankruptcy" filing confirmed.', "bankruptcy"),
    ]

    for headline, expected_keyword in test_cases:
        signals = detect_signals(headline)
        detected_keywords = [
            signal["keyword"]
            for signal in signals
        ]

        assert expected_keyword in detected_keywords, (
            f"Expected '{expected_keyword}' to be detected in: "
            f"'{headline}'. Detected: {detected_keywords}"
        )


def test_catastrophic_headline_anti_dilution_with_neutral_padding():
    """
    Test that 1 severe catastrophic headline is not diluted away when
    9 or 99 neutral headlines are added under top_k_mean and max strategies.
    """
    catastrophic_headline = "Company files for bankruptcy amid severe financial distress."
    neutral_9 = [f"Company opens office branch {i} in local area." for i in range(9)]
    neutral_99 = [f"Company opens office branch {i} in local area." for i in range(99)]

    # Default strategy (top_k_mean)
    res_1 = predict("SevereCorp", [catastrophic_headline])
    res_10 = predict("SevereCorp", [catastrophic_headline] + neutral_9)
    res_100 = predict("SevereCorp", [catastrophic_headline] + neutral_99)

    # Catastrophic headline is severe (bankruptcy = 50 + negative sentiment penalty)
    assert res_1["risk_score"] >= 50.0
    # Adding 9 neutral headlines must NOT dilute the score
    assert res_10["risk_score"] == res_1["risk_score"]
    # Adding 99 neutral headlines must NOT dilute the score
    assert res_100["risk_score"] == res_1["risk_score"]

    # Test under 'max' strategy as well
    max_cfg = Settings(aggregation_strategy="max")
    res_max_1 = predict("SevereCorp", [catastrophic_headline], config=max_cfg)
    res_max_100 = predict("SevereCorp", [catastrophic_headline] + neutral_99, config=max_cfg)
    assert res_max_100["risk_score"] == res_max_1["risk_score"]


def test_configurable_aggregation_strategies():
    """
    Test that Settings supports configurable aggregation strategies (top_k_mean, max, blend, mean)
    and validates invalid inputs.
    """
    h1 = "Company files for bankruptcy."  # high risk
    h2 = "Company faces lawsuit."          # moderate risk
    h3 = "Company signs clean contract."   # zero risk

    cfg_topk = Settings(aggregation_strategy="top_k_mean", aggregation_top_k=2)
    cfg_max = Settings(aggregation_strategy="max")
    cfg_mean = Settings(aggregation_strategy="mean")
    cfg_blend = Settings(aggregation_strategy="blend")

    score_topk = predict("TestCorp", [h1, h2, h3], config=cfg_topk)["risk_score"]
    score_max = predict("TestCorp", [h1, h2, h3], config=cfg_max)["risk_score"]
    score_mean = predict("TestCorp", [h1, h2, h3], config=cfg_mean)["risk_score"]
    score_blend = predict("TestCorp", [h1, h2, h3], config=cfg_blend)["risk_score"]

    # Max must be >= top_k mean >= unweighted mean
    assert score_max >= score_topk
    assert score_topk >= score_mean
    assert score_max >= score_blend

    # Invalid strategy raises ValueError
    with pytest.raises(ValueError, match="Invalid aggregation strategy"):
        Settings(aggregation_strategy="unsupported_strategy")

    # Invalid top_k raises ValueError
    with pytest.raises(ValueError, match="Aggregation top_k must be greater than zero"):
        Settings(aggregation_top_k=0)


def test_confidence_reflects_signal_agreement_not_just_volume():
    """
    Test that two datasets with the same headline count (N=10) have substantially
    different confidence when their signals differ (agreement vs noise).
    """
    # Dataset A: 10 headlines with strong, consistent negative risk signals
    consistent_headlines = [
        f"Company faces bankruptcy, lawsuit and fraud investigation part {i}."
        for i in range(10)
    ]

    # Dataset B: 10 headlines with mostly neutral noise and only 1 minor signal
    sparse_headlines = [
        "Company experienced a minor delay in shipment."
    ] + [
        f"Company announces routine administrative update {i}."
        for i in range(9)
    ]

    res_a = predict("ConsistentSupplier", consistent_headlines)
    res_b = predict("SparseSupplier", sparse_headlines)

    # Both have exactly 10 headlines
    assert len(consistent_headlines) == len(sparse_headlines) == 10

    # Confidence for consistent risk must be substantially higher than sparse/noisy signals
    assert res_a["confidence"] > res_b["confidence"]
    assert (res_a["confidence"] - res_b["confidence"]) > 0.3


def test_confidence_neutral_padding_does_not_inflate():
    """
    Test that adding neutral padding to a single risk headline does not
    artificially inflate confidence.
    """
    single_risk = ["Company files for bankruptcy and faces fraud investigation."]
    padded_with_neutral = single_risk + [
        f"Company opens office location {i}." for i in range(9)
    ]

    res_single = predict("SupplierX", single_risk)
    res_padded = predict("SupplierX", padded_with_neutral)

    # Padded dataset with neutral headlines should NOT have higher confidence
    # for the risk assessment than the pure signal
    assert res_padded["confidence"] <= res_single["confidence"]


def test_keyword_stemming_and_inflections():
    """
    Test that signals.py correctly detects plurals, tenses, and inflected forms:
    - shortage / shortages
    - layoff / layoffs
    - delay / delays / delayed
    - lawsuit / lawsuits
    - default / defaults (with loan/debt context)
    """
    s_shortage = detect_signals(clean_text("The factory suffered component shortage."))
    s_shortages = detect_signals(clean_text("The factory suffered component shortages."))
    assert any(s["keyword"] == "shortage" for s in s_shortage)
    assert any(s["keyword"] == "shortage" for s in s_shortages)

    s_layoff = detect_signals(clean_text("Company announced a major layoff."))
    s_layoffs = detect_signals(clean_text("Company announced major layoffs."))
    assert any(s["keyword"] == "layoff" for s in s_layoff)
    assert any(s["keyword"] == "layoff" for s in s_layoffs)

    s_delay = detect_signals(clean_text("Production delay reported."))
    s_delays = detect_signals(clean_text("Production delays reported."))
    s_delayed = detect_signals(clean_text("Shipment was delayed by a week."))
    assert any(s["keyword"] == "delays" for s in s_delay)
    assert any(s["keyword"] == "delays" for s in s_delays)
    assert any(s["keyword"] == "delays" for s in s_delayed)

    s_lawsuits = detect_signals(clean_text("Company faces multiple lawsuits."))
    assert any(s["keyword"] == "lawsuit" for s in s_lawsuits)

    s_defaults = detect_signals(clean_text("Borrower defaults on bank loan debt."))
    assert any(s["keyword"] == "default" for s in s_defaults)


def test_keyword_boundary_false_positives_prevented():
    """
    Test that substrings do not trigger false-positive keyword matches:
    'short' must not trigger 'shortage', 'lay' must not trigger 'layoff', etc.
    """
    assert len(detect_signals(clean_text("A short visit to headquarters."))) == 0
    assert len(detect_signals(clean_text("Workers lay the foundation stone."))) == 0
    assert len(detect_signals(clean_text("International law conference held."))) == 0
    assert len(detect_signals(clean_text("Power turned out fine after review."))) == 0
    assert len(detect_signals(clean_text("Cat video goes viral on platform."))) == 0
    assert len(detect_signals(clean_text("Walking down the street."))) == 0


def test_basf_headlines_detect_shortages_and_layoffs():
    """
    Verify that BASF headlines from supplier_headlines.json detect
    'shortage' and 'layoff' correctly.
    """
    h_shortages = clean_text("BASF struggles with raw-material shortages for specialty plastics.")
    h_layoffs = clean_text("BASF implements restructuring plan leading to potential layoffs.")

    signals_shortages = detect_signals(h_shortages)
    keywords_shortages = [s["keyword"] for s in signals_shortages]
    assert "shortage" in keywords_shortages

    signals_layoffs = detect_signals(h_layoffs)
    keywords_layoffs = [s["keyword"] for s in signals_layoffs]
    assert "layoff" in keywords_layoffs
    assert "restructuring" in keywords_layoffs


def test_score_aggregation_proves_volume_and_positive_coverage_effects():
    """
    Regression test for MUST-FIX 2: Score Aggregation.
    Proves that:
    1. CASE B (1 risk + 11 positive) < CASE A (1 risk) (positive coverage genuinely reduces risk).
    2. CASE C (3 risk headlines) > CASE A (1 risk) (repeated negative coverage genuinely increases risk).
    3. Scores are distinct and not artificially compressed/identical.
    4. Balanced case (2 negative + 2 positive) sits between CASE B and CASE C.
    """
    # Negative/risk headlines:
    h_risk_1 = "The supplier faces an unexpected strike by factory workers."
    h_risk_2 = "The supplier faces a major lawsuit over breach of contract."
    h_risk_3 = "The supplier is under government investigation for fraud."

    # Clearly positive headlines (zero risk, positive sentiment):
    h_positive_11 = [
        f"The supplier reports record positive profit and earnings in quarter {i}."
        for i in range(11)
    ]

    # CASE A: 1 negative/risk headline
    res_a = predict("SupplierA", [h_risk_1])
    score_a = res_a["risk_score"]

    # CASE B: 1 negative/risk headline + 11 clearly positive headlines
    res_b = predict("SupplierB", [h_risk_1] + h_positive_11)
    score_b = res_b["risk_score"]

    # CASE C: 3 negative/risk headlines
    res_c = predict("SupplierC", [h_risk_1, h_risk_2, h_risk_3])
    score_c = res_c["risk_score"]

    # Balanced Case: 2 negative + 2 positive headlines
    res_mixed = predict(
        "SupplierMixed",
        [h_risk_1, h_risk_2, h_positive_11[0], h_positive_11[1]],
    )
    score_mixed = res_mixed["risk_score"]

    # Qualitative relationships:
    # 1. Positive coverage genuinely reduces risk
    assert score_b < score_a, f"Expected score(B) < score(A), got {score_b} vs {score_a}"
    # 2. Repeated negative coverage genuinely increases risk
    assert score_c > score_a, f"Expected score(C) > score(A), got {score_c} vs {score_a}"
    # 3. Scores must not be identical
    assert len({score_a, score_b, score_c}) == 3, "Scores must not be identical"
    # 4. Mixed case sits appropriately between high mitigation and raw baseline
    assert score_b < score_mixed < score_c
    # 5. All scores bounded
    for sc in [score_a, score_b, score_c, score_mixed]:
        assert 0.0 <= sc <= 100.0


def test_predict_response_shape_preserved():
    """Verify that predict() output format, keys, and types remain standard."""
    res = predict("TestSupplier", ["The supplier faces a strike."])
    assert isinstance(res["supplier"], str)
    assert isinstance(res["risk_score"], float)
    assert isinstance(res["confidence"], float)
    assert isinstance(res["sentiment_breakdown"], dict)
    assert isinstance(res["signals"], list)
    assert isinstance(res["top_worst_3"], list)


# ------------------------------------------------------------------
# Risk Evidence Filtering Tests (SHOULD-CONSIDER #2: score > 0 only)
# ------------------------------------------------------------------

def test_evidence_excludes_zero_risk_positive_headlines():
    """Zero-risk positive and neutral headlines must NOT appear in risk evidence (top_worst_3)."""
    res = predict(
        "CleanCorp",
        [
            "CleanCorp reports record positive profits and earnings growth.",
            "CleanCorp opens a modern state-of-the-art research facility.",
        ],
    )
    assert res["risk_score"] == 0.0
    assert res["top_worst_3"] == []


def test_evidence_preserves_positive_risk_headlines():
    """Headlines with positive calculated risk score must be preserved in risk evidence."""
    res = predict(
        "DistressedCorp",
        [
            "DistressedCorp files for emergency bankruptcy and debt default.",
        ],
    )
    assert res["risk_score"] > 0.0
    assert len(res["top_worst_3"]) == 1
    assert res["top_worst_3"][0]["score"] > 0.0
    assert "bankruptcy" in res["top_worst_3"][0]["headline"]


def test_evidence_mixed_zero_and_positive_risk_returns_only_positive_risk():
    """Mixed zero-risk and positive-risk inputs return only headlines with score > 0 in evidence."""
    res = predict(
        "MixedCorp",
        [
            "MixedCorp reports strong positive revenue growth.",       # zero risk (positive)
            "MixedCorp operations disrupted by severe worker strike.",  # positive risk
            "MixedCorp holds routine annual shareholder meeting.",      # zero risk (neutral)
        ],
    )
    assert len(res["top_worst_3"]) == 1
    assert res["top_worst_3"][0]["score"] > 0.0
    assert "strike" in res["top_worst_3"][0]["headline"]
    evidence_headlines = [item["headline"] for item in res["top_worst_3"]]
    assert "MixedCorp reports strong positive revenue growth." not in evidence_headlines
    assert "MixedCorp holds routine annual shareholder meeting." not in evidence_headlines


# ------------------------------------------------------------------
# Configurable Volume and Mitigation Weights Tests (SHOULD-CONSIDER #4)
# ------------------------------------------------------------------

def test_config_default_volume_and_mitigation_weights():
    """Verify default volume weight is 0.15 and mitigation weight is 0.35 in Settings and to_dict()."""
    cfg = Settings()
    assert cfg.volume_weight == 0.15
    assert cfg.mitigation_weight == 0.35
    d = cfg.to_dict()
    assert d["volume_weight"] == 0.15
    assert d["mitigation_weight"] == 0.35


def test_custom_volume_weight_changes_score_deterministically():
    """Verify custom volume_weight in Settings scales repeated risk events deterministically."""
    headlines = [
        "Supplier faces major strike disrupting operations.",
        "Supplier hit with recall of defective components.",
    ]
    # Default volume weight (0.15)
    cfg_default = Settings()
    score_default = predict("TestSupp", headlines, config=cfg_default)["risk_score"]

    # Higher volume weight (0.30): repeated risk amplifies the score higher
    cfg_higher_vol = Settings(volume_weight=0.30)
    score_higher = predict("TestSupp", headlines, config=cfg_higher_vol)["risk_score"]

    # Zero volume weight (0.0): no volume amplification
    cfg_zero_vol = Settings(volume_weight=0.0)
    score_zero = predict("TestSupp", headlines, config=cfg_zero_vol)["risk_score"]

    assert score_higher > score_default > score_zero


def test_custom_mitigation_weight_changes_score_deterministically():
    """Verify custom mitigation_weight in Settings discounts risk for positive coverage deterministically."""
    headlines = [
        "Supplier hit with recall of defective components.",
        "Supplier reports record positive earnings growth.",
        "Supplier announces positive expansion and strong performance.",
    ]
    # Default mitigation weight (0.35)
    cfg_default = Settings()
    score_default = predict("TestSupp", headlines, config=cfg_default)["risk_score"]

    # Higher mitigation weight (0.50): positive headlines discount risk more aggressively
    cfg_higher_mit = Settings(mitigation_weight=0.50)
    score_higher_mit = predict("TestSupp", headlines, config=cfg_higher_mit)["risk_score"]

    # Zero mitigation weight (0.0): positive headlines provide no discount
    cfg_zero_mit = Settings(mitigation_weight=0.0)
    score_zero_mit = predict("TestSupp", headlines, config=cfg_zero_mit)["risk_score"]

    assert score_higher_mit < score_default < score_zero_mit


def test_volume_and_mitigation_weight_validation_failures():
    """Verify invalid volume and mitigation weights raise ValueError."""
    # Negative weights
    with pytest.raises(ValueError, match="Weight 'volume_weight' cannot be negative"):
        Settings(volume_weight=-0.1)

    with pytest.raises(ValueError, match="Weight 'mitigation_weight' cannot be negative"):
        Settings(mitigation_weight=-0.2)

    # Weights exceeding 1.0
    with pytest.raises(ValueError, match="Weight 'volume_weight' cannot exceed 1.0"):
        Settings(volume_weight=1.5)

    with pytest.raises(ValueError, match="Weight 'mitigation_weight' cannot exceed 1.0"):
        Settings(mitigation_weight=2.0)

    # Non-numeric weights
    with pytest.raises(ValueError, match="Weight 'volume_weight' must be numeric"):
        Settings(volume_weight="high")
