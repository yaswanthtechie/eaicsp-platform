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
            if any(w in lower_text for w in ["bankruptcy", "fraud", "strike", "lawsuit", "sanction"]):
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
        "The company faces bankruptcy and fraud investigation."
    )

    result_2 = predict(
        "LowVolumeSupplier",
        [base_headline] * 2,
    )

    result_20 = predict(
        "HighVolumeSupplier",
        [base_headline] * 20,
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
        "The supplier announces operational updates."
    )

    previous_confidence = -1.0

    for count in range(0, 31, 5):
        result = predict(
            "MonoTestSupplier",
            [base_headline] * count,
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
    Validate supplier_headlines.json dataset.
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
    assert len(dataset) == 80

    grouped = defaultdict(list)

    for item in dataset:

        assert "supplier" in item
        assert "headline" in item

        grouped[item["supplier"]].append(
            item["headline"]
        )

    assert len(grouped) == 8

    for supplier, headlines in grouped.items():
        if supplier in ["Foxconn", "BASF"]:
            assert len(headlines) == 4
        else:
            assert len(headlines) == 12



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
