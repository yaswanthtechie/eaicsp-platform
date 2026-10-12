"""
Tests for Milestone 2 & 3: Pretrained Transformer Evaluation, Metric Computation,
MLflow 3.16.1 Tracking, Token-Level Attention Explanations, and Reproducible Benchmarking.
"""

import json
from pathlib import Path
from unittest.mock import patch
import pytest
import mlflow

from src.config import Settings, get_settings
from src.evaluate import HUMAN_BENCHMARK_EXPECTATIONS, VALID_TIERS, load_validation_dataset
from src.transformer_eval import (
    DEFAULT_EXPERIMENT_NAME,
    TRANSFORMER_MODEL_IDENTIFIER,
    build_observed_limitations,
    compute_classification_metrics,
    evaluate_baseline_held_out,
    evaluate_transformer_held_out,
    explain_headline_attention,
    init_explanation_model,
    log_evaluation_to_mlflow,
    run_milestone2_evaluation,
    score_supplier_pure_transformer,
)


# ------------------------------------------------------------------
# 1. Metric Calculation Tests
# ------------------------------------------------------------------

def test_compute_classification_metrics_perfect():
    """Verify metrics calculation when predictions match expected tiers perfectly."""
    expected = {"S1": "Low", "S2": "Medium", "S3": "High", "S4": "Critical"}
    predicted = {"S1": "Low", "S2": "Medium", "S3": "High", "S4": "Critical"}
    scores = [20.0, 65.0, 75.0, 95.0]

    metrics = compute_classification_metrics(expected, predicted, scores)

    assert metrics["total_samples"] == 4
    assert metrics["matches"] == 4
    assert metrics["accuracy"] == 1.0
    assert metrics["accuracy_percentage"] == 100.0
    assert metrics["macro_precision"] == 1.0
    assert metrics["macro_recall"] == 1.0
    assert metrics["macro_f1"] == 1.0
    assert metrics["weighted_f1"] == 1.0

    for tier in VALID_TIERS:
        tm = metrics["per_tier_metrics"][tier]
        assert tm["support"] == 1
        assert tm["predicted"] == 1
        assert tm["true_positives"] == 1
        assert tm["precision"] == 1.0
        assert tm["recall"] == 1.0
        assert tm["f1"] == 1.0

    assert metrics["score_metrics"]["min_score"] == 20.0
    assert metrics["score_metrics"]["max_score"] == 95.0
    assert metrics["score_metrics"]["spread"] == 75.0


def test_compute_classification_metrics_imperfect():
    """Verify metrics calculation with known classification errors and asymmetric confusion matrix."""
    expected = {
        "S1": "Low",
        "S2": "Low",
        "S3": "Medium",
        "S4": "High",
    }
    predicted = {
        "S1": "Low",       # TP for Low
        "S2": "Medium",    # Low predicted as Medium
        "S3": "Medium",    # TP for Medium
        "S4": "Critical",  # High predicted as Critical
    }
    scores = [10.0, 62.0, 68.0, 90.0]

    metrics = compute_classification_metrics(expected, predicted, scores)

    assert metrics["total_samples"] == 4
    assert metrics["matches"] == 2
    assert metrics["accuracy"] == 0.5
    assert metrics["accuracy_percentage"] == 50.0

    # Low: support 2, pred 1, tp 1 -> prec 1.0, rec 0.5, f1 0.6667
    assert metrics["per_tier_metrics"]["Low"]["support"] == 2
    assert metrics["per_tier_metrics"]["Low"]["predicted"] == 1
    assert metrics["per_tier_metrics"]["Low"]["true_positives"] == 1
    assert metrics["per_tier_metrics"]["Low"]["precision"] == 1.0
    assert metrics["per_tier_metrics"]["Low"]["recall"] == 0.5

    # Medium: support 1, pred 2, tp 1 -> prec 0.5, rec 1.0, f1 0.6667
    assert metrics["per_tier_metrics"]["Medium"]["support"] == 1
    assert metrics["per_tier_metrics"]["Medium"]["predicted"] == 2
    assert metrics["per_tier_metrics"]["Medium"]["true_positives"] == 1
    assert metrics["per_tier_metrics"]["Medium"]["precision"] == 0.5
    assert metrics["per_tier_metrics"]["Medium"]["recall"] == 1.0

    # High: support 1, pred 0, tp 0 -> prec 0.0, rec 0.0, f1 0.0
    assert metrics["per_tier_metrics"]["High"]["support"] == 1
    assert metrics["per_tier_metrics"]["High"]["predicted"] == 0
    assert metrics["per_tier_metrics"]["High"]["f1"] == 0.0

    # Critical: support 0, pred 1, tp 0 -> prec 0.0, rec 0.0, f1 0.0
    assert metrics["per_tier_metrics"]["Critical"]["support"] == 0
    assert metrics["per_tier_metrics"]["Critical"]["predicted"] == 1


def test_compute_classification_metrics_empty():
    """Verify empty input handling."""
    metrics = compute_classification_metrics({}, {}, [])
    assert metrics["total_samples"] == 0
    assert metrics["matches"] == 0
    assert metrics["accuracy"] == 0.0


# ------------------------------------------------------------------
# 2. Pure Transformer Scoring Component Tests
# ------------------------------------------------------------------

def test_score_supplier_pure_transformer_empty():
    """Verify scoring with empty headlines list returns zero risk."""
    score, tier, details, sup_exp = score_supplier_pure_transformer([])
    assert score == 0.0
    assert tier == "Low"
    assert details == []
    assert "No headlines" in sup_exp["tier_reasoning"]


def test_score_supplier_pure_transformer_mocked_sentiment():
    """Verify deterministic calculation of score and tier from mocked sentiment outputs."""
    headlines = [
        "Company reports record profits and revenue expansion.",
        "Minor shipment delay resolved quickly.",
        "Supplier files for emergency bankruptcy and liquidates assets.",
    ]

    mock_responses = [
        {"label": "positive", "confidence": 0.98},
        {"label": "neutral", "confidence": 0.90},
        {"label": "negative", "confidence": 0.96},
    ]

    with patch("src.transformer_eval.analyze_sentiment", side_effect=mock_responses):
        score, tier, details, sup_exp = score_supplier_pure_transformer(headlines, include_explanations=False)

        # positive: 0.0, neutral: 15.0, negative: 0.96 * 100 = 96.0
        # mean: (0.0 + 15.0 + 96.0) / 3 = 111.0 / 3 = 37.0 -> Low tier (< 60.0)
        assert score == 37.0
        assert tier == "Low"
        assert len(details) == 3
        assert details[0]["label"] == "positive"
        assert details[0]["headline_score"] == 0.0
        assert details[1]["label"] == "neutral"
        assert details[1]["headline_score"] == 15.0
        assert details[2]["label"] == "negative"
        assert details[2]["headline_score"] == 96.0
        assert "Low" in sup_exp["tier_reasoning"]


def test_score_supplier_pure_transformer_critical_tier():
    """Verify pure transformer reaches Critical tier when negative sentiment dominates."""
    headlines = [
        "Severe insolvency threat triggers debt default.",
        "All factories shut down following regulator injunction.",
    ]
    mock_responses = [
        {"label": "negative", "confidence": 0.92},
        {"label": "negative", "confidence": 0.90},
    ]

    with patch("src.transformer_eval.analyze_sentiment", side_effect=mock_responses):
        score, tier, details, sup_exp = score_supplier_pure_transformer(headlines, include_explanations=False)
        # (92.0 + 90.0) / 2 = 91.0 -> Critical tier (>= 85.0)
        assert score == 91.0
        assert tier == "Critical"
        assert "Critical" in sup_exp["tier_reasoning"]


# ------------------------------------------------------------------
# 3. Milestone 3: Attention-Based Explanation Tests
# ------------------------------------------------------------------

def test_explain_headline_attention_returns_tokens_and_weights():
    """Verify explain_headline_attention produces valid token attributions using Layer 12 attention."""
    headline = "BioPharma Solutions enters long-term commercial supply contract with leading oncology developer."
    exp = explain_headline_attention(headline, top_k=5)

    assert exp["explanation_method"] == "last_layer_cross_head_cls_attention"
    assert "top_tokens" in exp
    assert len(exp["top_tokens"]) > 0
    assert len(exp["top_tokens"]) <= 5

    for item in exp["top_tokens"]:
        assert "token" in item
        assert "attention_weight" in item
        assert "rank" in item
        assert isinstance(item["token"], str) and len(item["token"]) > 0
        assert isinstance(item["attention_weight"], float)
        assert item["attention_weight"] >= 0.0

    assert "Key attention token drivers:" in exp["explanation_summary"]


def test_explain_headline_attention_filters_special_tokens():
    """Verify [CLS], [SEP], [PAD], and punctuation tokens are excluded from top attributions."""
    headline = "Supplier announces record positive annual revenue growth of twenty percent."
    exp = explain_headline_attention(headline, top_k=5)

    tokens = [t["token"] for t in exp["top_tokens"]]
    assert "[CLS]" not in tokens
    assert "[SEP]" not in tokens
    assert "[PAD]" not in tokens
    for p in [".", ",", "-", ":", ";"]:
        assert p not in tokens


def test_explain_headline_attention_empty_headline():
    """Verify empty or whitespace headlines return an empty explanation safely."""
    exp = explain_headline_attention("")
    assert exp["top_tokens"] == []
    assert "Empty headline" in exp["explanation_summary"]

    exp_ws = explain_headline_attention("   ")
    assert exp_ws["top_tokens"] == []


def test_every_transformer_prediction_has_explanation():
    """
    Verify that in evaluate_transformer_held_out, EVERY supplier and EVERY headline
    has a non-empty, sensible explanation attached.
    """
    results = evaluate_transformer_held_out(include_explanations=True)

    assert results["total_suppliers"] == 12
    assert results["total_headlines"] == 96

    supplier_count_with_explanations = 0
    headline_count_with_explanations = 0

    for rep in results["company_reports"]:
        # 1. Supplier-level explanation verification
        assert "explanation" in rep, f"Supplier {rep['supplier']} missing 'explanation' field"
        sup_exp = rep["explanation"]
        assert sup_exp["explanation_method"] == "last_layer_cross_head_cls_attention"
        assert len(sup_exp["supplier_top_tokens"]) > 0, f"Supplier {rep['supplier']} has empty supplier_top_tokens"
        assert len(sup_exp["tier_reasoning"]) > 10, f"Supplier {rep['supplier']} has empty tier_reasoning"
        supplier_count_with_explanations += 1

        # 2. Headline-level explanation verification
        assert "headline_details" in rep, f"Supplier {rep['supplier']} missing headline_details"
        for h_detail in rep["headline_details"]:
            assert "explanation" in h_detail, f"Headline '{h_detail['headline']}' missing explanation"
            h_exp = h_detail["explanation"]
            assert h_exp["explanation_method"] == "last_layer_cross_head_cls_attention"
            assert len(h_exp["top_tokens"]) > 0, f"Headline '{h_detail['headline']}' has empty top_tokens"
            assert "Key attention token drivers:" in h_exp["explanation_summary"]
            headline_count_with_explanations += 1

    assert supplier_count_with_explanations == 12
    assert headline_count_with_explanations == 96


def test_explanation_tokens_are_sensible_for_distress_headline():
    """At least two real distress words must be in the top 5."""
    headline = (
        "Cascade Energy Corp faces emergency bankruptcy filing and debt default."
    )

    tokens = [
        t["token"].lower()
        for t in explain_headline_attention(headline, top_k=5)["top_tokens"]
    ]

    distress_words = {
        "emergency",
        "bankruptcy",
        "default",
        "debt",
        "filing",
    }

    assert len(distress_words.intersection(tokens)) >= 2, tokens


def test_explanations_skip_stopwords_and_keep_whole_words():
    headline = (
        "Supplier reports record quarterly profit and new contract wins."
    )

    tokens = [
        t["token"].lower()
        for t in explain_headline_attention(headline, top_k=5)["top_tokens"]
    ]

    assert "and" not in tokens
    assert not any(tok.startswith("#") for tok in tokens)
    assert {"profit", "wins", "record"}.intersection(tokens)


# ------------------------------------------------------------------
# 4. Held-Out Dataset Non-Circular & Disjointness Tests
# ------------------------------------------------------------------

def test_held_out_dataset_disjoint_from_development():
    """Verify that synthetic held-out validation dataset has zero supplier overlap with dev benchmark."""
    dataset = load_validation_dataset()
    val_suppliers = {item["supplier"] for item in dataset}
    dev_suppliers = set(HUMAN_BENCHMARK_EXPECTATIONS.keys())

    assert len(val_suppliers) == 12
    assert len(dev_suppliers) == 25
    overlap = val_suppliers.intersection(dev_suppliers)
    assert len(overlap) == 0, f"Data leakage: validation suppliers overlap with dev: {overlap}"


def test_held_out_dataset_tier_balance():
    """Verify that held-out validation dataset has balanced representation across all 4 tiers."""
    dataset = load_validation_dataset()
    supplier_tiers = {}
    for item in dataset:
        supplier_tiers[item["supplier"]] = item["expected_tier"]

    tier_counts = {t: 0 for t in VALID_TIERS}
    for t in supplier_tiers.values():
        tier_counts[t] += 1

    # Exactly 3 suppliers per tier (3 * 4 = 12 suppliers)
    for tier in VALID_TIERS:
        assert tier_counts[tier] == 3, f"Tier {tier} has {tier_counts[tier]} suppliers, expected 3"


# ------------------------------------------------------------------
# 5. MLflow 3.16.1 Tracking Tests
# ------------------------------------------------------------------

def test_log_evaluation_to_mlflow_creates_run_and_logs_artifacts(tmp_path):
    """
    Verify that log_evaluation_to_mlflow creates an MLflow run with:
    - correct tags and parameters (including explanation_method)
    - aggregate and per-tier metrics
    - JSON artifacts without throwing errors.
    """
    test_experiment = "test-supplier-risk-milestone-2"

    eval_data = {
        "model_name": "test_model",
        "model_type": "pretrained_transformer_zero_shot",
        "total_suppliers": 4,
        "total_headlines": 32,
        "accuracy": 0.75,
        "accuracy_percentage": 75.0,
        "macro_precision": 0.8,
        "macro_recall": 0.75,
        "macro_f1": 0.77,
        "weighted_f1": 0.77,
        "per_tier_metrics": {
            "Low": {"support": 1, "predicted": 1, "true_positives": 1, "precision": 1.0, "recall": 1.0, "f1": 1.0},
            "Medium": {"support": 1, "predicted": 1, "true_positives": 1, "precision": 1.0, "recall": 1.0, "f1": 1.0},
            "High": {"support": 1, "predicted": 2, "true_positives": 1, "precision": 0.5, "recall": 1.0, "f1": 0.6667},
            "Critical": {"support": 1, "predicted": 0, "true_positives": 0, "precision": 0.0, "recall": 0.0, "f1": 0.0},
        },
        "confusion_matrix": {t: {p: 0 for p in VALID_TIERS} for t in VALID_TIERS},
        "score_metrics": {
            "min_score": 10.0,
            "max_score": 90.0,
            "mean_score": 50.0,
            "spread": 80.0,
            "std_dev": 25.0,
        },
        "tier_thresholds": {"Low": 60.0, "Medium": 72.0, "High": 85.0},
        "company_reports": [
            {
                "supplier": "Test Corp",
                "expected_tier": "Low",
                "model_tier": "Low",
                "explanation": {
                    "explanation_method": "last_layer_cross_head_cls_attention",
                    "tier_reasoning": "Test reasoning",
                },
            }
        ],
    }

    run_id = log_evaluation_to_mlflow(
        eval_results=eval_data,
        run_name="unit-test-run",
        experiment_name=test_experiment,
    )

    assert isinstance(run_id, str) and len(run_id) > 0

    client = mlflow.tracking.MlflowClient()
    run = client.get_run(run_id)

    assert run.data.tags.get("model_name") == "test_model"
    assert run.data.tags.get("explanation_method") == "last_layer_cross_head_cls_attention"
    assert run.data.params.get("sample_count") == "4"
    assert run.data.metrics.get("accuracy") == 0.75
    assert run.data.metrics.get("macro_f1") == 0.77


# ------------------------------------------------------------------
# 6. Full Pipeline & Comparison Consistency Tests
# ------------------------------------------------------------------

def test_full_milestone2_and_3_evaluation_runs_and_produces_comparison():
    """
    Verify run_milestone2_evaluation produces valid baseline and transformer results,
    creates two distinct MLflow run IDs, attaches explanations, and builds comparison.
    """
    res = run_milestone2_evaluation(experiment_name=DEFAULT_EXPERIMENT_NAME, include_explanations=True)

    assert "comparison" in res
    assert "baseline_results" in res
    assert "transformer_results" in res

    comp = res["comparison"]
    assert comp["dataset"] == "src/synthetic_held_out_validation.json"
    assert comp["sample_count_suppliers"] == 12
    assert comp["sample_count_headlines"] == 96

    base = comp["baseline"]
    tf = comp["transformer"]

    # Verify run IDs are distinct
    assert base["run_id"] != tf["run_id"]

    # Verify explanation method
    assert tf.get("explanation_method") == "last_layer_cross_head_cls_attention"

    # Verify critical support is present
    assert "critical_support" in base
    assert "critical_support" in tf
    assert base["critical_support"] == 3
    assert tf["critical_support"] == 3

    # Verify observed limitations were dynamically generated
    assert len(comp["observed_limitations"]) > 0
    assert any("indicative, not statistically significant" in line for line in comp["observed_limitations"])

    # Verify every company report in transformer_results has explanation
    for rep in res["transformer_results"]["company_reports"]:
        assert "explanation" in rep
        assert rep["explanation"]["explanation_method"] == "last_layer_cross_head_cls_attention"
        assert len(rep["headline_details"]) == 8
        for h in rep["headline_details"]:
            assert "explanation" in h


def test_build_observed_limitations():
    """Verify build_observed_limitations correctly identifies discrepancies between models."""
    base_res = {
        "total_suppliers": 2,
        "matches": 1,
        "company_reports": [
            {
                "supplier": "Company A",
                "risk_score": 90.0,
                "model_tier": "Critical",
                "expected_tier": "Critical",
            },
            {
                "supplier": "Company B",
                "risk_score": 50.0,
                "model_tier": "Low",
                "expected_tier": "Medium",
            },
        ],
    }
    tf_res = {
        "total_suppliers": 2,
        "matches": 1,
        "company_reports": [
            {
                "supplier": "Company A",
                "risk_score": 80.0,
                "model_tier": "High",
                "expected_tier": "Critical",
            },
            {
                "supplier": "Company B",
                "risk_score": 65.0,
                "model_tier": "Medium",
                "expected_tier": "Medium",
            },
        ],
    }
    lines = build_observed_limitations(base_res, tf_res)
    assert len(lines) == 3
    assert "Company A (expected Critical): current model 90.00 -> Critical, transformer 80.00 -> High. Only the current model got this one right." in lines[0]
    assert "Company B (expected Medium): current model 50.00 -> Low, transformer 65.00 -> Medium. Only the transformer got this one right." in lines[1]
    assert "Sample size: 2 suppliers. The accuracy gap is 0 supplier(s)" in lines[2]

