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
    assert len(dataset) == 96

    grouped = defaultdict(list)

    for item in dataset:

        assert "supplier" in item
        assert "headline" in item

        grouped[item["supplier"]].append(
            item["headline"]
        )

    assert len(grouped) == 8

    for supplier, headlines in grouped.items():
        assert len(headlines) == 12