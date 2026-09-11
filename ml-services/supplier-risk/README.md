# Supplier Risk NLP Service

## Overview

The **Supplier Risk** service is an independent Machine Learning microservice built with **FastAPI** that evaluates supplier risk by analyzing news headlines.

The service combines:
- **FinBERT Sentiment Analysis** (`ProsusAI/finbert`)
- **Config-Driven Keyword Risk Detection** (Financial, Operational, Reputational)
- **Calibrated Risk Scoring & Evidence Confidence Calculation** (Config-Driven Anti-Dilution / Top-K Mean / Max / Blend / Mean)
- **Anti-Dilution Architecture** (protecting acute risks from high-volume neutral dilution)
- **REST API Serving** via FastAPI (`/predict`, `/health`, `/api/v1/supplier-risk/*`)
- **Automated Unit & Integration Testing** with Pytest
- **15-Company Calibration & Benchmark Dataset** (180 headlines)

---

# Features

- FinBERT Sentiment Analysis for financial news domain
- Supplier Risk Prediction with configurable scoring parameters
- Financial Risk Detection (bankruptcy, insolvency, default, layoff, etc.)
- Operational Risk Detection (strike, recall, disruption, shortage, etc.)
- Reputational & Security Risk Detection (fraud, investigation, lawsuit, cyberattack, etc.)
- Context Disambiguation & NLP Mitigation Detection
- Evidence Confidence Scoring using exponential saturation
- Configurable Anti-Dilution Risk Aggregation (`top_k_mean` default, `max`, `blend`, `mean`)
- REST API using FastAPI with full request/response schemas
- Automatic Model Loading with startup lifespan management
- Comprehensive Unit & Integration Test Suite with Pytest
- 15-Company Benchmark Dataset Evaluation

---

# Risk Score Interpretation

The risk score (0-100) is calculated based on keyword severity, FinBERT sentiment penalties, and configurable anti-dilution aggregation (`top_k_mean` by default). The operational 4-tier classification provides actionable triage guidelines for procurement teams:

| Score Range | Risk Level | Interpretation & Recommended Procurement Action |
| :--- | :--- | :--- |
| **0.0 - 59.9** | **Low** | Routine operational updates, clean or predominantly positive news, and minimal or transient friction (e.g., Siemens at 56.33, ASML at 56.52, Lockheed Martin at 56.98). Continue normal procurement operations. |
| **60.0 - 71.9** | **Medium** | Stable operations counterbalanced by isolated supply chain, labor, or legal friction (e.g., BASF at 60.30, Foxconn at 61.68, Nissan at 65.01, TSMC at 65.13, Boeing at 68.35, Evergreen Marine at 69.36, Maersk at 69.95, Tesla at 70.15, Intel at 70.16). Standard supplier monitoring; verify business continuity plans. |
| **72.0 - 84.9** | **High** | Significant operational, legal, labor, or financial disruptions across multiple risk-bearing events (e.g., Glencore at 78.33). Review supplier contracts, establish secondary supplier contingencies. |
| **85.0 - 100.0** | **Critical** | Acute terminal, structural, or existential distress: debt defaults, ransomware attacks, insolvency, production shutdowns, or active bankruptcy proceedings (e.g., Northvolt at 90.47, Apex Logistics at 100.00). Immediate procurement intervention and emergency mitigation. |

---

# Project Structure

```text
supplier-risk/
│
├── src/
│   ├── __init__.py
│   ├── analyze.py                         # FastAPI application and prediction/trend endpoints
│   ├── config.py                          # Config-driven weights, penalties, and validation
│   ├── data.py                            # Dataset loading, validation, and fallback handling
│   ├── evaluate.py                        # Batch evaluation runner across benchmark dataset
│   ├── predict.py                         # Core scoring orchestration, anti-dilution, and confidence logic
│   ├── preprocess.py                      # Text normalization and cleaning
│   ├── sentiment.py                       # FinBERT pipeline integration
│   ├── signals.py                         # Keyword signal detection, mitigation, and context logic
│   ├── trend.py                           # Date validation, trend aggregation, and recency decay
│   ├── supplier_headlines.json            # 10-company baseline dataset (120 headlines)
│   ├── supplier_headlines_15.json         # 15-company benchmark dataset (180 headlines)
│   ├── supplier_trend_headlines.json      # 10-company baseline trend dataset (120 headlines)
│   └── supplier_trend_headlines_15.json   # 15-company benchmark trend dataset (180 headlines)
│
├── tests/
│   ├── test_api.py                        # REST API endpoint and contract tests
│   ├── test_evidence_confidence.py        # Milestone 2: Evidence and confidence tests
│   ├── test_integration.py                # Unmocked slow integration benchmark tests
│   ├── test_milestone3_config_and_validation.py # Milestone 3: Config, validation, and benchmark tests
│   ├── test_predict.py                    # Unit tests for scoring, signals, and deduplication
│   └── test_trend.py                      # Time-series trend and date validation tests
│
├── pytest.ini
├── requirements.txt
└── README.md
```

---

# Technology Stack

- **Python 3.11+**
- **FastAPI** & **Uvicorn**
- **Transformers (Hugging Face)** & **PyTorch**
- **FinBERT (`ProsusAI/finbert`)**
- **Pydantic**
- **Pytest**

---

# Installation

### 1. Navigate to the project directory:

```bash
cd ml-services/supplier-risk
```

### 2. Create and activate a Virtual Environment:

```bash
# Windows
python -m venv .venv
.\.venv\Scripts\activate

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies:

```bash
pip install -r requirements.txt
```

---

# Configuration

The scoring engine is **configuration-driven** via `src/config.py`. All parameters can be customized via environment variables at startup or dynamically via the `Settings` class without modifying source code.

### Configuration Variables & Defaults

| Parameter | Environment Variable | Default Value | Description |
| :--- | :--- | :--- | :--- |
| **Model Name** | `SUPPLIER_RISK_MODEL_NAME` | `"ProsusAI/finbert"` | HuggingFace pretrained model identifier |
| **Negative Penalty** | `NEGATIVE_SENTIMENT_PENALTY` | `40.0` | Penalty multiplier for negative headlines |
| **Neutral Penalty** | `NEUTRAL_SENTIMENT_PENALTY` | `0.0` | Penalty for neutral headlines |
| **Positive Penalty** | `POSITIVE_SENTIMENT_PENALTY` | `0.0` | Penalty for positive headlines |
| **Max Risk Score** | `MAX_RISK_SCORE` | `100.0` | Maximum cap on final risk score |
| **Confidence Divisor**| `CONFIDENCE_DIVISOR` | `8.0` | Saturation divisor in evidence confidence formula |
| **Aggregation Strategy**| `AGGREGATION_STRATEGY` | `"top_k_mean"` | Anti-dilution strategy: `top_k_mean`, `max`, `blend`, or `mean` |
| **Aggregation Top-K**  | `AGGREGATION_TOP_K` | `3` | Top risk-bearing headlines to average under `top_k_mean` |
| **Signal Weights JSON**| `SIGNAL_WEIGHTS_JSON` | *Default dict* | JSON map of custom keyword weights |

### Default Signal Weights Table

| Category | Keyword | Default Weight | Description / Rationale |
| :--- | :--- | :---: | :--- |
| **Financial** | `bankruptcy` | 50 | Terminal corporate insolvency risk |
| | `insolvency` | 45 | Severe inability to pay debts |
| | `default` | 40 | Failure to meet debt obligations |
| | `layoff` | 25 | Significant workforce reduction |
| | `restructuring`| 20 | Operational or financial restructuring |
| | `downgrade` | 20 | Credit or equity rating reduction |
| **Operational** | `shutdown` | 35 | Production or facility cessation |
| | `recall` | 30 | Product defect or safety recall |
| | `strike` | 25 | Labor walkout disrupting supply chain |
| | `outage` | 25 | Utility or plant power outage |
| | `disruption` | 20 | General logistics/supply interruption |
| | `shortage` | 20 | Critical raw-material component deficit |
| | `delays` | 15 | Minor shipment or milestone lag |
| **Reputational / Security** | `fraud` | 40 | Criminal deception or financial malpractice |
| | `sanction` | 35 | Trade restrictions or legal sanctions |
| | `cyberattack` | 35 | Ransomware or system intrusion |
| | `investigation` | 25 | Regulatory or judicial investigation |
| | `lawsuit` | 25 | Civil litigation or liability claim |

---

# Starting the API

Run the FastAPI application with Uvicorn:

```bash
uvicorn src.analyze:app --host 0.0.0.0 --port 8006 --reload
```

The service will be available at:
```
http://127.0.0.1:8006
```

Interactive Swagger documentation is available at:
```
http://127.0.0.1:8006/docs
```

---

# API Endpoints & Usage

### 1. Health Check

```http
GET /health
```

**Response:**
```json
{
  "status": "UP",
  "service": "supplier-risk"
}
```

---

### 2. Inspect Active Configuration

```http
GET /api/v1/supplier-risk/config
```

Retrieve active server-side risk scoring configuration parameters, sentiment penalties, aggregation rules, recency decay half-life, and keyword signal weights.

**Response:**
```json
{
  "model_name": "ProsusAI/finbert",
  "negative_sentiment_penalty": 40.0,
  "neutral_sentiment_penalty": 0.0,
  "positive_sentiment_penalty": 0.0,
  "max_risk_score": 100.0,
  "confidence_divisor": 8.0,
  "aggregation_strategy": "top_k_mean",
  "aggregation_top_k": 3,
  "recency_half_life_days": 30.0,
  "signal_weights": {
    "bankruptcy": 50,
    "insolvency": 45,
    "default": 40,
    "restructuring": 20,
    "layoff": 25,
    "downgrade": 20,
    "strike": 25,
    "recall": 30,
    "disruption": 20,
    "shortage": 20,
    "delays": 15,
    "shutdown": 35,
    "outage": 25,
    "fraud": 40,
    "investigation": 25,
    "lawsuit": 25,
    "sanction": 35,
    "cyberattack": 35
  }
}
```

---

### 3. Predict Supplier Risk

```http
POST /predict
```
*(Aliases: `/api/v1/supplier-risk/predict`, `/api/v1/supplier-risk/analyze`)*

**Request Body:**
```json
{
  "supplier_name": "Apex Logistics",
  "headlines": [
    "Analysts issue major downgrade on Apex Logistics amid insolvency fears.",
    "Regulators launch fraud investigation into Apex Logistics accounting practices.",
    "Apex Logistics files for emergency restructuring following severe debt default."
  ]
}
```

**Example Response:**
```json
{
  "supplier_summary": {
    "Apex Logistics": {
      "supplier": "Apex Logistics",
      "risk_score": 100.0,
      "confidence": 0.3096,
      "sentiment_breakdown": {
        "positive": 0,
        "neutral": 0,
        "negative": 3
      },
      "signals": [
        {
          "keyword": "insolvency",
          "weight": 45
        },
        {
          "keyword": "downgrade",
          "weight": 20
        },
        {
          "keyword": "fraud",
          "weight": 40
        },
        {
          "keyword": "investigation",
          "weight": 25
        },
        {
          "keyword": "default",
          "weight": 40
        },
        {
          "keyword": "restructuring",
          "weight": 20
        }
      ],
      "top_worst_3": [
        {
          "headline": "Analysts issue major downgrade on Apex Logistics amid insolvency fears.",
          "sentiment": "negative",
          "score": 103.62,
          "signals": [
            {
              "keyword": "insolvency",
              "weight": 45
            },
            {
              "keyword": "downgrade",
              "weight": 20
            }
          ]
        },
        {
          "headline": "Regulators launch fraud investigation into Apex Logistics accounting practices.",
          "sentiment": "negative",
          "score": 101.0,
          "signals": [
            {
              "keyword": "fraud",
              "weight": 40
            },
            {
              "keyword": "investigation",
              "weight": 25
            }
          ]
        },
        {
          "headline": "Apex Logistics files for emergency restructuring following severe debt default.",
          "sentiment": "negative",
          "score": 98.68,
          "signals": [
            {
              "keyword": "default",
              "weight": 40
            },
            {
              "keyword": "restructuring",
              "weight": 20
            }
          ]
        }
      ]
    }
  }
}
```

---

### 3. Get Supplier Risk Trend (Milestone 1)

Retrieve chronologically ordered risk trend points for a supplier over time.

```http
GET /api/v1/supplier-risk/trend/{supplier_name}
```

**Example Request:**
```http
GET /api/v1/supplier-risk/trend/Tesla
```

**Example Response (200 OK):**
```json
{
  "supplier": "Tesla",
  "overall_confidence": 0.4468,
  "top_evidence": [
    {
      "headline": "Tesla announces a major recall of 2 million vehicles over autopilot software issues.",
      "sentiment": "negative",
      "score": 69.6,
      "signals": [
        {
          "keyword": "recall",
          "weight": 30
        }
      ]
    },
    {
      "headline": "Tesla faces a class-action lawsuit from investors over self-driving claims.",
      "sentiment": "negative",
      "score": 64.6,
      "signals": [
        {
          "keyword": "lawsuit",
          "weight": 25
        }
      ]
    }
  ],
  "risk_trend": [
    {
      "date": "2026-01-05",
      "risk_score": 69.6,
      "confidence": 0.4468,
      "headline_count": 1,
      "evidence": [
        {
          "headline": "Tesla announces a major recall of 2 million vehicles over autopilot software issues.",
          "sentiment": "negative",
          "score": 69.6,
          "signals": [
            {
              "keyword": "recall",
              "weight": 30
            }
          ]
        }
      ]
    },
    {
      "date": "2026-03-02",
      "risk_score": 0.0,
      "confidence": 0.0588,
      "headline_count": 1,
      "evidence": [
        {
          "headline": "Tesla reports record positive earnings driven by strong Model Y sales.",
          "sentiment": "positive",
          "score": 0.0,
          "signals": []
        }
      ]
    }
  ]
}
```

*Note: If the supplier is unknown or has no recorded headlines, the endpoint returns a `200 OK` with an empty `risk_trend: []`, `top_evidence: []`, and `overall_confidence: 0.0`.*

---

### 4. Dynamic Risk Trend Analysis (Milestone 1 & 2)

Calculate risk trend dynamically for user-provided date-aware articles. Dates are strictly validated to ISO format (`YYYY-MM-DD`). Articles on the same date are aggregated together into a single chronological trend point with supporting evidence.

```http
POST /api/v1/supplier-risk/trend
```

**Request Body:**
```json
{
  "supplier_name": "Tesla",
  "articles": [
    {
      "date": "2026-02-15",
      "headline": "Tesla faces supply disruption in Shanghai."
    },
    {
      "date": "2026-01-10",
      "headline": "Tesla reports record positive earnings."
    }
  ]
}
```

**Example Response (200 OK):**
```json
{
  "supplier": "Tesla",
  "overall_confidence": 0.4468,
  "top_evidence": [
    {
      "headline": "Tesla faces supply disruption in Shanghai.",
      "sentiment": "negative",
      "score": 59.6,
      "signals": [
        {
          "keyword": "disruption",
          "weight": 20
        }
      ]
    }
  ],
  "risk_trend": [
    {
      "date": "2026-01-10",
      "risk_score": 0.0,
      "confidence": 0.0588,
      "headline_count": 1,
      "evidence": [
        {
          "headline": "Tesla reports record positive earnings.",
          "sentiment": "positive",
          "score": 0.0,
          "signals": []
        }
      ]
    },
    {
      "date": "2026-02-15",
      "risk_score": 59.6,
      "confidence": 0.4468,
      "headline_count": 1,
      "evidence": [
        {
          "headline": "Tesla faces supply disruption in Shanghai.",
          "sentiment": "negative",
          "score": 59.6,
          "signals": [
            {
              "keyword": "disruption",
              "weight": 20
            }
          ]
        }
      ]
    }
  ]
}
```

---

# Risk Scoring & Anti-Dilution Architecture

## Scoring Pipeline

The scoring pipeline operates as follows:
`sentiment` + `risk signals` → `headline score` → `configurable aggregation (top_k_mean / max / blend / mean)` → `0–100 risk score`

1. **Individual Headline Scoring**:
   $$\text{headline\_score} = (\text{penalty} \times \text{confidence}) + \sum_{k \in \text{detected}} \text{weight}(k)$$

2. **Configurable Risk Aggregation (Anti-Dilution)**:
   The service provides configurable aggregation strategies to prevent catastrophic risk signals from being diluted by neutral news:
   - **`top_k_mean` (default, $K=3$)**: Averages the top-$K$ risk-bearing headline scores ($s_i > 0$). Severe acute events (such as bankruptcy, fraud, or lawsuits) maintain their true severity even when surrounded by 10, 50, or 100 neutral routine headlines.
   - **`max`**: Evaluates supplier risk by the single worst-case headline score ($\text{peak\_score}$).
   - **`blend`**: Backward-compatible $0.80 \times \text{average\_score} + 0.20 \times \text{peak\_score}$.
   - **`mean`**: Unweighted arithmetic average of all unique headline scores.

   Final score is capped at `cfg.max_risk_score` (default $100.0$).

3. **Signal-Aware Evidence Confidence**:
   Confidence reflects evidence characteristics rather than solely headline volume:
   - **Meaningful Signal Proportion ($p_{\text{signal}}$)**: Ratio of risk-bearing headlines to total headlines.
   - **Signal Agreement & Dispersion**: Consistency of headline scores ($1.0 - \text{dispersion}$).
   - **Signal Strength**: Severity of the peak detected risk signal.
   - **Evidence Volume**: Evaluated over meaningful risk signals, ensuring neutral padding cannot artificially inflate confidence.
   - Bounded strictly within $[0.0, 1.0]$. Zero headlines yields $0.0$.

---

# 15-Company Benchmark Dataset & Evaluation

The benchmark dataset is located in `src/supplier_headlines_15.json` and contains **180 realistic headlines across 15 global suppliers** across aerospace, semiconductors, automotive, electronics, logistics, energy, defense, and chemicals:

1. **Boeing** (Aerospace & Defense)
2. **Intel** (Semiconductors)
3. **Tesla** (Automotive & Clean Energy)
4. **Nissan** (Automotive)
5. **Foxconn** (Electronics Manufacturing)
6. **TSMC** (Semiconductor Foundry)
7. **Maersk** (Maritime Logistics)
8. **BASF** (Chemicals)
9. **Siemens** (Industrial Automation & Infrastructure)
10. **Apex Logistics** (Freight & Supply Chain Services)
11. **ASML** (Semiconductor Lithography)
12. **Glencore** (Natural Resources & Mining)
13. **Lockheed Martin** (Defense & Aerospace)
14. **Evergreen Marine** (Container Shipping)
15. **Northvolt** (EV Battery Cell Manufacturing)

### Evaluation Benchmark Results (Standalone `src.evaluate`)

| Supplier | Headlines | Score | Conf | Top Signals | Human Expected Tier | Model Tier | Match Status |
| :--- | :---: | :---: | :---: | :--- | :---: | :---: | :---: |
| **Siemens** | 12 | 56.33 | 0.1587 | `delays`, `shortage` | **Low** | Low | `MATCH` |
| **ASML** | 12 | 56.52 | 0.2307 | `delays`, `shortage`, `disruption` | **Low** | Low | `MATCH` |
| **Lockheed Martin** | 12 | 56.98 | 0.2809 | `shortage`, `delays`, `disruption` | **Low** | Low | `MATCH` |
| **BASF** | 12 | 60.30 | 0.3314 | `shortage`, `lawsuit`, `restructuring` | **Low** | Medium | `MISMATCH` |
| **Foxconn** | 12 | 61.68 | 0.3330 | `disruption`, `strike`, `investigation` | **Medium** | Medium | `MATCH` |
| **Nissan** | 12 | 65.01 | 0.5049 | `restructuring`, `recall`, `disruption` | **Medium** | Medium | `MATCH` |
| **TSMC** | 12 | 65.13 | 0.2977 | `shutdown`, `shortage`, `outage` | **Low** | Medium | `MISMATCH` |
| **Boeing** | 12 | 68.35 | 0.4878 | `lawsuit`, `investigation`, `delays` | **Medium** | Medium | `MATCH` |
| **Evergreen Marine** | 12 | 69.36 | 0.5747 | `strike`, `disruption`, `lawsuit` | **Medium** | Medium | `MATCH` |
| **Maersk** | 12 | 69.95 | 0.4541 | `delays`, `strike`, `disruption` | **Medium** | Medium | `MATCH` |
| **Tesla** | 12 | 70.15 | 0.5263 | `recall`, `lawsuit`, `layoff` | **High** | Medium | `MISMATCH` |
| **Intel** | 12 | 70.16 | 0.4504 | `lawsuit`, `layoff`, `disruption` | **Medium** | Medium | `MATCH` |
| **Glencore** | 12 | 78.33 | 0.6375 | `strike`, `investigation`, `lawsuit` | **High** | High | `MATCH` |
| **Northvolt** | 12 | 90.47 | 0.6883 | `shutdown`, `insolvency`, `strike` | **Critical** | Critical | `MATCH` |
| **Apex Logistics** | 12 | 100.00 | 0.6643 | `strike`, `cyberattack`, `default` | **Critical** | Critical | `MATCH` |

### Distribution Summary & Root Cause Analysis

- **Total Evaluated**: 15 suppliers
- **Human Matches**: 12 / 15 (80.0%)
- **Min Score**: 56.33 (Siemens)
- **Max Score**: 100.00 (Apex Logistics)
- **Score Spread**: 43.67 *(Target >= 50.0: BELOW BENCHMARK TARGET)*
- **Mean Score**: 69.25
- **Standard Deviation**: 11.93 *(Target >= 12.0: BELOW BENCHMARK TARGET)*
- **Tier Distribution (All 4 Tiers Populated)**:
  - Low: 3 suppliers (Siemens, ASML, Lockheed Martin)
  - Medium: 9 suppliers (BASF, Foxconn, Nissan, TSMC, Boeing, Evergreen Marine, Maersk, Tesla, Intel)
  - High: 1 supplier (Glencore)
  - Critical: 2 suppliers (Northvolt, Apex Logistics)
- **Root Cause & Benchmark Analysis**: The active configuration utilizes `top_k_mean` ($K=3$) aggregation with a `negative_sentiment_penalty` of 40.0. When suppliers have 3 or more negative headlines, their overall risk score is calculated exclusively from the top 3 worst events. Under the calibrated 4-tier operational classification (Low <60, Medium 60–72, High 72–85, Critical >=85), the distribution cleanly populates all 4 operational tiers and achieves an 80.0% match rate against grounded human expectations without synthetic weight manipulation. Per strict governance rules, weights and algorithms were not artificially altered to force synthetic compliance with the statistical targets.

---

# Human Sanity Check

### Highest Risk Supplier: Apex Logistics (Score: 100.00)
- **Underlying Signals**: `bankruptcy` (50), `insolvency` (45), `default` (40), `fraud` (40), `cyberattack` (35), `shutdown` (35), `recall` (30), `strike` (25), `layoff` (25), `investigation` (25), `lawsuit` (25).
- **Sentiment Breakdown**: 10 Negative, 1 Neutral, 1 Positive.
- **Top Risk Headlines**:
  1. *"Analysts issue major downgrade on Apex Logistics amid insolvency fears."*
  2. *"Regulators launch fraud investigation into Apex Logistics accounting practices."*
  3. *"Apex Logistics files for emergency restructuring following severe debt default."*
- **Human Rationale**: The maximum score (100.00) accurately reflects critical distress. The company suffers simultaneous operational paralysis (strike, ransomware cyberattack, port shutdown), reputational crises (fraud investigation, client lawsuits), and catastrophic financial failure (debt default, insolvency, bankruptcy proceedings). A human evaluator reviewing these events would immediately classify this supplier as critical risk.

### Lowest Risk Supplier: Siemens (Score: 56.33)
- **Underlying Signals**: `shortage` (20), `delays` (15) — no severe financial or reputational triggers.
- **Sentiment Breakdown**: 8 Positive, 2 Neutral, 2 Negative.
- **Top Headlines**:
  1. *"Siemens reports robust revenue growth driven by industrial automation orders."*
  2. *"Siemens secures multi-billion dollar railway electrification deal."*
  3. *"Siemens receives top environmental and sustainability rating from industry auditors."*
- **Human Rationale**: The score (56.33, Low tier) accurately captures an operationally healthy, financially strong supplier. Negative events are limited to minor transient supply bottlenecks (circuit breaker shortage and medical device shipping delays) that were quickly managed, while the majority of news reflects record order backlog, new infrastructure contracts, and positive earnings. A human procurement officer would confidently consider this supplier low risk.

---

# Running Tests & Evaluation

### Run Batch Evaluation:

```bash
python -m src.evaluate
```

The script prints:
- Supplier Name
- Risk Score & Confidence
- Sentiment Breakdown
- Detected Signals
- Top 3 Highest Risk Headlines

### Run Test Suite:

```bash
python -m pytest ml-services/supplier-risk/tests -v
```

The test suite validates:
- Text preprocessing and punctuation boundary isolation
- Keyword detection, mitigation windows, and variant stemming
- Sentiment pipeline integration
- Configurable risk score aggregation (`blend` default, `top_k_mean`, `max`, `mean`)
- Calibrated risk band classification (Low, Medium, High, Critical)
- Response schema validation and API endpoints (`/predict`, `/health`, aliases)
- Configuration defaults, overrides, and input validation
- Duplicate headline handling and anti-dilution guarantees
- Date validation (ISO YYYY-MM-DD enforcement, invalid date rejection)
- Entity-level risk trend aggregation and chronological ordering
- Trend API endpoints (`GET /api/v1/supplier-risk/trend/{supplier_name}`, `POST /api/v1/supplier-risk/trend`)

---

# Model

The service uses the Hugging Face FinBERT model:

```
ProsusAI/finbert
```

The model is loaded once during application startup lifespan and reused for all prediction requests.

---

# Logging

The service logs:
- Model loading on startup lifespan
- Service shutdown events
- Prediction and request processing exceptions
- Validation errors
