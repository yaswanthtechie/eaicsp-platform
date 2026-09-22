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
    1. A high-risk distressed supplier (Apex Logistics) scores higher than
       moderate (Tesla) and low-risk (Siemens) suppliers.
    2. Clean / low-risk reference supplier (Siemens) scores within the Low-Risk tier (< 60.0).
    3. Moderate-risk supplier (Tesla) scores within the Medium-Risk tier (60.0 <= score < 72.0).
    4. Catastrophic supplier (Apex Logistics) reaches the Critical-Risk tier (>= 85.0).
    5. All scores and confidences are validly bounded within [0.0, 100.0] and [0.0, 1.0].
    """
    # Load real dataset
    data = load_headlines()

    # We must ensure we have headlines for all required suppliers in the dataset
    assert "Apex Logistics" in data, "Apex Logistics not found in dataset"
    assert "Tesla" in data, "Tesla not found in dataset"
    assert "Siemens" in data, "Siemens not found in dataset"

    apex_result = predict("Apex Logistics", data["Apex Logistics"])
    tesla_result = predict("Tesla", data["Tesla"])
    siemens_result = predict("Siemens", data["Siemens"])

    apex_score = apex_result["risk_score"]
    tesla_score = tesla_result["risk_score"]
    siemens_score = siemens_result["risk_score"]

    # Relative ordering: Apex Logistics (distressed) > Tesla (moderate) > Siemens (low-risk)
    assert apex_score > tesla_score > siemens_score, (
        f"Expected Apex ({apex_score}) > Tesla ({tesla_score}) > Siemens ({siemens_score})"
    )

    # Absolute calibrated threshold assertions under 4-tier operational classification:
    # 1. Low-risk supplier (Siemens) must score in Low tier (< 60.0)
    assert siemens_score < 60.0, (
        f"Expected Siemens score in Low tier (< 60.0), got {siemens_score}"
    )

    # 2. Moderate-risk supplier (Tesla) must score in Medium tier (60.0 <= score < 72.0)
    assert 60.0 <= tesla_score < 72.0, (
        f"Expected Tesla score in Medium tier (60.0 - 72.0), got {tesla_score}"
    )

    # 3. High-distress supplier (Apex Logistics) must score in Critical tier (>= 85.0)
    assert apex_score >= 85.0, (
        f"Expected Apex Logistics score in Critical tier (>= 85.0), got {apex_score}"
    )

    # Invariant: Scores and confidences bounded
    for res in [apex_result, tesla_result, siemens_result]:
        assert 0.0 <= res["risk_score"] <= 100.0
        assert 0.0 <= res["confidence"] <= 1.0


@pytest.mark.slow
def test_full_dataset_calibrated_distribution():
    """
    Validate the score distribution across all 10 suppliers in the baseline calibrated dataset.
    Protects against score compression, ordering inversions, and stale thresholds.
    """
    data = load_headlines()
    assert len(data) == 10, f"Expected 10 suppliers in baseline dataset, got {len(data)}"

    supplier_scores = {}
    supplier_confidences = {}
    for supplier, headlines in data.items():
        result = predict(supplier, headlines)
        score = result["risk_score"]
        conf = result["confidence"]
        assert 0.0 <= score <= 100.0, f"Score for {supplier} out of bounds: {score}"
        assert 0.0 <= conf <= 1.0, f"Confidence for {supplier} out of bounds: {conf}"
        supplier_scores[supplier] = score
        supplier_confidences[supplier] = conf

    # Verify ranking extremes in 10-company baseline
    sorted_suppliers = sorted(supplier_scores.items(), key=lambda x: x[1])
    lowest_supplier, lowest_score = sorted_suppliers[0]
    highest_supplier, highest_score = sorted_suppliers[-1]

    assert lowest_supplier == "Siemens", f"Expected Siemens as lowest risk, got {lowest_supplier} ({lowest_score})"
    assert highest_supplier == "Apex Logistics", f"Expected Apex Logistics as highest risk, got {highest_supplier} ({highest_score})"

    # Verify score spread: must not be compressed into a narrow range
    score_spread = highest_score - lowest_score
    assert score_spread >= 40.0, (
        f"Expected score spread >= 40.0 points across 10 suppliers, got {score_spread:.2f}"
    )

    # Verify signal-aware confidence variance: confidence must not be constant
    min_conf = min(supplier_confidences.values())
    max_conf = max(supplier_confidences.values())
    assert max_conf - min_conf >= 0.3, (
        f"Expected dynamic confidence range >= 0.3 across diverse suppliers, got {max_conf - min_conf:.4f}"
    )
    # Explicitly protect against the old constant 0.7769 across all suppliers
    unique_confidences = set(supplier_confidences.values())
    assert len(unique_confidences) > 1, "Confidence must not be constant across all suppliers"
    assert not all(c == 0.7769 for c in supplier_confidences.values()), "Stale 0.7769 detected"
