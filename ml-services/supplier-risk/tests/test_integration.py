"""
Integration tests for the Supplier Risk NLP pipeline.
"""

import pytest
from src.predict import predict
from src.data import load_headlines


@pytest.mark.slow
def test_real_sentiment_integration():
    """
    Test using the real sentiment model and real dataset.
    Asserts that:
    1. A known risky supplier (Tesla) scores higher than a clean reference supplier (TSMC).
    2. The clean reference supplier (TSMC) is pinned below the High-Risk threshold (<= 35.0).
    3. The lowest-risk supplier (BASF) is pinned within the Low-Risk tier (<= 25.0).
    4. The highest-risk supplier (Tesla) reaches the Critical-Risk tier (>= 45.1).
    5. All scores are bounded within [0.0, 100.0].
    """
    # Load real dataset
    data = load_headlines()

    # We must ensure we have headlines for all required suppliers in the dataset
    assert "Tesla" in data, "Tesla not found in dataset"
    assert "TSMC" in data, "TSMC not found in dataset"
    assert "BASF" in data, "BASF not found in dataset"

    tesla_result = predict("Tesla", data["Tesla"])
    tsmc_result = predict("TSMC", data["TSMC"])
    basf_result = predict("BASF", data["BASF"])

    tesla_score = tesla_result["risk_score"]
    tsmc_score = tsmc_result["risk_score"]
    basf_score = basf_result["risk_score"]

    # Relative ordering assertion: Tesla > TSMC
    assert tesla_score > tsmc_score, f"Expected Tesla risk ({tesla_score}) > TSMC risk ({tsmc_score})"

    # Absolute calibrated threshold assertions:
    # 1. Clean reference supplier (TSMC) must score within Medium tier and strictly below High Risk (<= 35.0)
    assert tsmc_score <= 35.0, (
        f"Expected TSMC reference score <= 35.0 (calibrated Medium ceiling), got {tsmc_score}"
    )

    # 2. Lowest-risk supplier (BASF) must score within Low tier (<= 25.0)
    assert basf_score <= 25.0, (
        f"Expected BASF score <= 25.0 (calibrated Low ceiling), got {basf_score}"
    )

    # 3. Highest-risk supplier (Tesla) must score in Critical tier (>= 45.1)
    assert tesla_score >= 45.1, (
        f"Expected Tesla score >= 45.1 (calibrated Critical threshold), got {tesla_score}"
    )


@pytest.mark.slow
def test_full_dataset_calibrated_distribution():
    """
    Validate the score distribution across all 8 suppliers in the calibrated dataset.
    Protects against score compression, ordering inversions, and stale thresholds.
    """
    data = load_headlines()
    assert len(data) == 8, f"Expected 8 suppliers, got {len(data)}"

    supplier_scores = {}
    for supplier, headlines in data.items():
        result = predict(supplier, headlines)
        score = result["risk_score"]
        assert 0.0 <= score <= 100.0, f"Score for {supplier} out of bounds: {score}"
        assert 0.0 <= result["confidence"] <= 1.0, f"Confidence for {supplier} out of bounds: {result['confidence']}"
        supplier_scores[supplier] = score

    # Verify ranking extremes
    sorted_suppliers = sorted(supplier_scores.items(), key=lambda x: x[1])
    lowest_supplier, lowest_score = sorted_suppliers[0]
    highest_supplier, highest_score = sorted_suppliers[-1]

    assert lowest_supplier == "BASF", f"Expected BASF as lowest risk, got {lowest_supplier} ({lowest_score})"
    assert highest_supplier == "Tesla", f"Expected Tesla as highest risk, got {highest_supplier} ({highest_score})"

    # Verify spread: must not be compressed into a narrow range
    score_spread = highest_score - lowest_score
    assert score_spread >= 25.0, (
        f"Expected score spread >= 25.0 points across 8 suppliers, got {score_spread:.2f}"
    )
