# Supplier Risk NLP Service

## Overview

The **Supplier Risk** service is a Machine Learning microservice built with **FastAPI** that evaluates supplier risk by analyzing news headlines.

The service combines:

- FinBERT Sentiment Analysis
- Keyword-based Risk Detection
- Supplier Risk Scoring
- REST API
- Automated Unit Testing

It is designed to integrate seamlessly with the API Gateway in a microservices architecture.

---

# Features

- FinBERT Sentiment Analysis
- Supplier Risk Prediction
- Financial Risk Detection
- Operational Risk Detection
- Reputational Risk Detection
- REST API using FastAPI
- Automatic Model Loading
- Unit Tested with Pytest
- JSON Dataset Evaluation

---

# Risk Score Interpretation

The risk score (0-100) is calculated based on keyword severity and sentiment analysis. These bands are heuristic, operational guidelines to help procurement teams understand the practical risk level of a supplier based on current system calibration (where calibrated scores across real-world news fall between 20.23 and 48.37).

| Score Range | Risk Level | Interpretation & Recommended Procurement Action |
| :--- | :--- | :--- |
| **0.0 - 25.0** | **Low** | Routine operational updates, clean or positive news, and minimal risk signals. Continue normal procurement operations (e.g., BASF at 20.23). |
| **25.1 - 35.0** | **Medium** | Predominantly stable operations with isolated disruptions or minor friction. Standard supplier monitoring, verify resilience plans (e.g., TSMC at 31.30). |
| **35.1 - 45.0** | **High** | Significant operational, supply chain, legal, labor, or restructuring disruptions across multiple headlines. Review supplier contracts, monitor lead times, establish secondary supplier contingencies (e.g., Foxconn 36.93, Maersk 37.32, Boeing 40.83, Intel 42.30, Nissan 43.72). |
| **45.1 - 100.0** | **Critical** | Severe structural, legal, or terminal risks; persistent negative sentiment (>65% of volume), massive recalls, lawsuits, layoffs, investigations. Immediate procurement intervention and risk committee escalation (e.g., Tesla at 48.37). |

---

# Project Structure

```text
supplier-risk/
│
├── src/
│   ├── __init__.py
│   ├── analyze.py
│   ├── data.py
│   ├── evaluate.py
│   ├── predict.py
│   ├── preprocess.py
│   ├── sentiment.py
│   ├── signals.py
│   └── supplier_headlines.json
│
├── tests/
│   └── test_predict.py
│
├── requirements.txt
└── README.md
```

---

# Technology Stack

- Python 3.11
- FastAPI
- Uvicorn
- Transformers (Hugging Face)
- FinBERT (ProsusAI/finbert)
- PyTorch
- Pydantic
- Pytest

---

# Installation

## 1. Navigate to the project

```bash
cd ml-services/supplier-risk
```

---

## 2. Create a Virtual Environment

### Windows

```bash
python -m venv .venv
.\.venv\Scripts\activate
```

### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
```

---

## 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

# Run the FastAPI Server

```bash
uvicorn src.analyze:app --reload --port 8006
```

The service will start at:

```
http://127.0.0.1:8006
```

---

# API Documentation

Swagger UI

```
http://127.0.0.1:8006/docs
```

OpenAPI JSON

```
http://127.0.0.1:8006/openapi.json
```

---

# API Endpoints

## Health Check

```
GET /health
```

Example Response

```json
{
  "status": "UP",
  "service": "supplier-risk"
}
```

---

## Analyze Supplier Risk

```
POST /api/v1/supplier-risk/analyze
```

**Note:** `supplier_name` cannot be blank (returns 400 Bad Request). Empty strings in `headlines` are ignored and do not contribute to risk scoring or confidence calculation.

Example Response

```json
{
  "supplier_summary": {
    "TechCorp": {
      "supplier": "TechCorp",
      "risk_score": 74.25,
      "confidence": 0.7135,
      "sentiment_breakdown": {
        "positive": 1,
        "neutral": 0,
        "negative": 2
      },
      "signals": [
        {
          "keyword": "fraud",
          "weight": 30
        }
      ],
      "top_worst_3": [
        {
          "headline": "TechCorp files for bankruptcy after massive fraud scandal.",
          "sentiment": "negative",
          "score": 92.4,
          "signals": [
            {
              "keyword": "bankruptcy",
              "weight": 40
            },
            {
              "keyword": "fraud",
              "weight": 30
            }
          ]
        }
      ]
    }
  }
}
```

---

# Risk Signals

The service detects predefined supplier risk keywords.

| Category     | Keywords                                                          |
| ------------ | ----------------------------------------------------------------- |
| Financial    | bankruptcy, insolvency, default, restructuring, layoff, downgrade |
| Operational  | strike, recall, disruption, shortage                              |
| Reputational | fraud, investigation, lawsuit, sanction                           |

Each keyword contributes a predefined weight toward the overall supplier risk score.

**Keyword Matching Limitations:**
- The engine matches on stems (e.g., `delays` hits `delay`).
- Mitigators such as `denies`, `avoids`, `cleared`, `resolved`, or `dismissed` occurring within a 4-word window before a keyword will neutralize it, avoiding false positives (e.g., "denies allegations of fraud" ignores the "fraud" signal).
- The pipeline does not currently perform full-sentence semantic negation beyond this window.

# Calibrated Scoring & Blend Architecture

## Scoring Pipeline

The scoring pipeline operates as follows:
`sentiment` + `risk signals` → `headline score` → `80% mean + 20% peak blend` → `0–100 risk score`

1. **Individual Headline Scoring**: Each headline receives a baseline sentiment penalty (`_sentiment_penalty`) plus cumulative weights from any detected risk signals (`detect_signals`).
2. **Peak / Mean Blending**:
   ```python
   final_risk_score = min(100.0, 0.80 * average_score + 0.20 * peak_score)
   ```
   - **Average Score (80% weight)**: Captures the supplier's volume-weighted baseline behavior across the news corpus.
   - **Peak Score (20% weight)**: Acts as a severity floor / shock-absorber so catastrophic acute events (e.g., bankruptcy or fraud) cannot be completely diluted by high volumes of routine neutral/positive news.

## Why the 80/20 Blend Was Chosen

Earlier iterations utilized a 50/50 blend (`0.5 * average + 0.5 * peak`). Empirical analysis of the 96-headline calibration dataset revealed critical shortcomings:
- **Score Clustering**: 6 of 8 suppliers were compressed into a narrow 12.6-point cluster (47.14 – 59.72).
- **False Alarms on Clean Reference Suppliers**: TSMC (which has 7 of 12 positive headlines) received a score of 47.14 ("High" risk) solely because a single earthquake shutdown headline yielded a peak score of 73.53.
- **Excessive Critical Classifications**: 5 of 8 suppliers were classified as "Critical" (>50.0).

By rebalancing the blend to **80% Mean / 20% Peak**:
1. **Meaningful Separation**: The score distribution widens from 12.6 points to **28.14 points** (20.23 to 48.37), restoring clear, graduated differentiation between suppliers.
2. **Proper Reference Positioning**: TSMC (31.30) sits cleanly in the **Medium** tier (25.1–35.0), well below the High-Risk boundary.
3. **Robust Dilution Protection**: Acute crises (e.g., bankruptcy + fraud with peak 100.0) still maintain an absolute risk floor (>25.0), preventing dilution into the safe Low tier even when surrounded by 20+ neutral articles.
4. **Principled Ordering**: Tesla (48.37) remains the highest-risk supplier, and BASF (20.23) remains the lowest-risk supplier.

## Calibrated 8-Supplier Evaluation Table

| Supplier | Headlines | Mean Score | Peak Score | Calibrated Score | Risk Band | Primary Drivers |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Tesla** | 12 | 40.80 | 78.63 | **48.37** | **Critical** | 8/12 negative; 2M vehicle recall, class-action lawsuit, global layoffs, Shanghai disruption |
| **Nissan** | 12 | 37.54 | 68.42 | **43.72** | **High** | 7/12 negative; 1M vehicle recall, North American layoffs, executive lawsuit, credit downgrade |
| **Intel** | 12 | 34.44 | 73.74 | **42.30** | **High** | 6/12 negative; 15% global layoff, raw-material fab shortages, processor launch delays |
| **Boeing** | 12 | 32.87 | 72.66 | **40.83** | **High** | 6/12 negative; FAA sanction threats, aircraft part recalls, 737 MAX lawsuit |
| **Maersk** | 12 | 28.27 | 73.52 | **37.32** | **High** | 6/12 negative; cyberattack disruption, Red Sea shipping delays, warehouse strike threats |
| **Foxconn** | 4 | 30.42 | 62.94 | **36.93** | **High** | 2/4 negative; major iPhone plant production disruption, worker bonus strikes |
| **TSMC** | 12 | 20.75 | 73.53 | **31.30** | **Medium** | 7/12 positive; strong AI chip demand and expansion, with isolated earthquake shutdown & power outage |
| **BASF** | 4 | 16.60 | 34.75 | **20.23** | **Low** | 2/4 positive; sustainable battery breakthroughs, with mild emission scrutiny |

## Component Weights

| Component          | Value | Operational Rationale |
| :--- | :---: | :--- |
| Negative sentiment | 40.0 | Negative tone reflects elevated baseline operational risk even without specific keywords. |
| Neutral sentiment  |  0.0 | Routine business updates do not artificially inflate risk. |
| Bankruptcy signal  |  50  | Severe financial insolvency dominates headline risk score. |
| Strike signal      |  25  | Significant operational and labor disruption. |
| Shortage signal    |  20  | Material bottlenecks directly impacting throughput. |
| Recall signal      |  30  | Major financial and safety reputational exposure. |
| Fraud signal       |  40  | Critical legal and reputational integrity risk. |
| Shutdown signal    |  35  | Immediate plant or facility stoppage. |
| Outage signal      |  25  | Power or utility infrastructure failure. |
| Cyberattack signal |  35  | Severe digital and supply chain security breach. |
| Delays signal      |  15  | Logistics and delivery bottlenecks. |

---

## Confidence / Evidence Strength

### What confidence means

Confidence represents the **volume-based strength of evidence** supporting the risk score. It answers the question: "How many headlines went into this assessment?"

A supplier with only 2 headlines could receive an identical risk score to a supplier with 20 headlines, but the 20-headline result rests on substantially more observational evidence. Confidence quantifies this difference.

### Why it is based on headline volume

- More headlines = more independent observations of the supplier's public activity.
- A single negative headline might be a one-off media blip; 20 negative headlines describe a sustained pattern.
- Volume is a transparent, defensible proxy for evidence reliability that does not require a statistical training set.

Confidence is **NOT** a statistical model probability. It does not quantify the probability that the risk score is "correct." It is a heuristic evidence-strength indicator.

### Formula implemented

```
confidence = 1 - exp(-n / 8)
```

where:
- `n` = number of **valid, non-empty processed headlines** used in scoring.
- `exp()` = natural exponential function.
- Divisor `8` = chosen so the Round 4 dataset size of 12 headlines/company yields ~0.78 confidence (substantial but not absolute).

### Reference values

| Headlines (n) | Confidence | Interpretation |
| ------------: | ---------: | -------------- |
| 0             | 0.00       | No evidence — result is not meaningful |
| 1             | 0.1175     | Very low — a single observation |
| 2             | 0.2212     | Low — barely enough to form a tentative view |
| 5             | 0.4647     | Moderate — some supporting evidence |
| 10            | 0.7135     | High — substantial evidence base |
| 12            | 0.7769     | High — matches typical Round 4 dataset size |
| 20            | 0.9179     | Very high — strong evidence |
| 50            | 0.9980     | Near-maximal |

### Why 2 headlines vs 20 headlines differs

With 2 headlines, even if both are strongly negative, there is a real chance that the next 18 headlines would be neutral or positive, pulling the average risk score in the other direction. With 20 headlines, the law of large numbers begins to operate: the average risk score is far more stable and unlikely to swing dramatically if a few more headlines are added.

### Why confidence does not modify the risk score

Confidence describes **evidence strength**, not risk magnitude. A supplier with 2 strongly negative headlines has a high estimated risk — that estimate is simply fragile. Multiplying the risk score by confidence would incorrectly convert "we don't know enough" into "the supplier is safe," which is a harmful misinterpretation for downstream procurement decisions.

Instead, consumers of this API should treat:
- High `risk_score` + low `confidence` → **investigate further** before onboarding.
- High `risk_score` + high `confidence` → **real, stable risk** — reject or escalate.
- Low `risk_score` + low `confidence` → **insufficient data**, cannot green-light.
- Low `risk_score` + high `confidence` → **trusted low-risk** supplier.

### Range

- Minimum: **0.0** (zero headlines or all empty/invalid headlines)
- Maximum: **<1.0** (asymptotically approaches 1.0 as n → ∞; never exceeds it)
- Zero-headline response: **0.0** exactly

### Requirements satisfied

- `confidence(0) = 0.0`
- `confidence(2) < confidence(20)`
- Strictly **monotonic non-decreasing** with headline count
- Bounded on `[0.0, 1.0]`
- Computed independently from `risk_score`

---

# Dataset

The project includes a sample dataset:

```
src/supplier_headlines.json
```

Two datasets are used:

### Primary Calibration Dataset (used by default)

`src/supplier_headlines.json` — the Round 4 calibrated dataset:

- 8 real-world suppliers: Boeing, Intel, Tesla, Nissan, Foxconn, TSMC, Maersk, BASF
- 12 headlines per supplier (mix of positive / neutral / risky)
- **Total 96 headlines**
- Intentionally spans financial, operational, and reputational risk patterns
- Used by: `load_headlines()`, `src/evaluate.py`, and the `/analyze-static` endpoint

### Inline Fallback Dataset (HEADLINES_DATA in `src/data.py`)

Small synthetic dataset used **only if** `supplier_headlines.json` cannot be loaded due to a missing file (`OSError`).
- **Validation**: If `supplier_headlines.json` is present but malformed, empty, or incorrectly structured, the system throws a strict `ValueError` rather than silently failing over to this synthetic data.
- 7 suppliers (TechCorp, AutoMaker Inc, Logistics Co, Global Trade, FoodSupplies, MetalWorks, BuildIt)
- 1–3 headlines per supplier
- Total 15 headlines
- Useful for quick smoke tests when the JSON file is unavailable

---

# Running Evaluation

Run the evaluation script:

```bash
python src/evaluate.py
```

The script prints:

- Supplier Name
- Risk Score
- Sentiment Breakdown
- Detected Signals
- Top 3 Highest Risk Headlines

---

# Running Tests

Execute fast unit tests (with FinBERT mocked):

```bash
python -m pytest -v -m "not slow"
```

Execute integration tests (with live FinBERT model and calibrated dataset):

```bash
python -m pytest -v -m slow
```

The test suite validates:

- Text preprocessing and punctuation boundary isolation
- Keyword detection, mitigation windows, and variant stemming
- Sentiment pipeline integration
- Calibrated 80/20 peak/mean score blending
- Calibrated risk band classification (Low, Medium, High, Critical)
- Clean reference supplier (TSMC) absolute threshold pinning (<= 35.0)
- Highest/lowest supplier ordering (Tesla > TSMC, Tesla highest, BASF lowest)
- Score bounds `[0.0, 100.0]` and confidence saturation
- Dilution protection against high neutral headline volumes
- Response schema validation and API endpoints

---

# Model

The service uses the Hugging Face FinBERT model.

```
ProsusAI/finbert
```

The model is loaded once during application startup and reused for all prediction requests.

---

# Logging

The service logs:

- Model initialization
- API startup
- API shutdown
- Runtime exceptions

---

# Author

EAICSP Platform

Supplier Risk ML Service
