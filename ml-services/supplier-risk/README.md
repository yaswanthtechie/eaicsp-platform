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

# Round 4 Calibrated Scoring

## Current scoring pipeline

The scoring pipeline operates as follows:
`sentiment` + `risk signals` → `headline score` → `average` → `0–100 risk score`

Each headline is first scored by evaluating its sentiment penalty and adding weights from any detected predefined risk signals. The scores across all evaluated headlines are averaged, and the final risk score is capped at a maximum of 100.

## Weight table

The following table summarizes the calibration adjustments made to the scoring components:

| Component          | Old Value | New Value | Reason |
| ------------------ | --------: | --------: | ------ |
| Negative sentiment |      30.0 |      40.0 | Increased to ensure negative headlines without explicit keywords still reflect elevated risk. |
| Neutral sentiment  |      10.0 |       0.0 | Neutral headlines (e.g., routine business updates) should not artificially inflate risk. |
| Bankruptcy signal  |        40 |        50 | Bankruptcy is a severe financial event and should dominate the headline risk score. |
| Strike signal      |        10 |        25 | A strike is highly disruptive to operations and was previously undervalued. |
| Shortage signal    |        10 |        20 | Raw-material shortages directly impact production and require higher penalty. |
| Recall signal      |        20 |        30 | Product recalls cause massive financial and reputational damage. |
| Fraud signal       |        30 |        40 | Fraud investigations indicate critical reputational risk. |

*(Note: New keywords such as 'shutdown' [35], 'outage' [25], 'cyberattack' [35], and 'delays' [15] were also added based on empirical dataset patterns).*

## Calibration reasoning

The weight adjustments were motivated by human review of the expanded 96-headline dataset:
1. **Neutral Penalty Reduction**: Clean headlines like *"Maersk launches new fleet of green methanol-powered container ships"* were receiving an accumulated 10.0 risk purely for being neutral. Neutral sentiment now correctly contributes 0 risk.
2. **Operational Risk Increase**: Headlines like *"TSMC faces temporary production shutdown after minor earthquake"* and *"Boeing machinists go on strike..."* represent tangible supply chain threats. Raising operational keywords ("strike", "shortage") and adding new ones ("shutdown", "outage") ensures these events produce appropriately medium-to-high scores (e.g., ~65-75 when combined with negative sentiment).
3. **Severe Financial/Reputational Risks**: Events like bankruptcy or fraud are terminal or catastrophic risks for suppliers. Boosting their weights ensures that any supplier with these headlines will trigger a high overall risk score, even if mixed with routine positive news.

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

Execute all unit tests:

```bash
python -m pytest -v
```

Example Output

```
23 passed, 1 warning in 31.75s
```

The test suite validates:

- Text preprocessing
- Keyword detection
- Sentiment pipeline
- Risk prediction
- Response schema
- Dataset validation
- Score calculation
- Maximum score cap

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
