# Supplier Risk NLP Service

## Overview

The **Supplier Risk** service is an independent Machine Learning microservice built with **FastAPI** that evaluates supplier risk by analyzing news headlines.

The service combines:
- **FinBERT Sentiment Analysis** (`ProsusAI/finbert`)
- **Config-Driven Keyword Risk Detection** (Financial, Operational, Reputational)
- **Calibrated Risk Scoring & Evidence Confidence Calculation** (`blend` 80/20 aggregation by default; `top_k_mean`, `max`, and `mean` supported as alternatives)
- **Anti-Dilution Architecture** (protecting acute risks from high-volume neutral dilution)
- **REST API Serving** via FastAPI (`/predict`, `/health`, `/api/v1/supplier-risk/*`)
- **Automated Unit & Integration Testing** with Pytest
- **10-Company Calibration & Benchmark Dataset** (120 headlines)

---

# Features

- FinBERT Sentiment Analysis for financial news domain
- Supplier Risk Prediction with configurable scoring parameters
- Financial Risk Detection (bankruptcy, insolvency, default, layoff, etc.)
- Operational Risk Detection (strike, recall, disruption, shortage, etc.)
- Reputational & Security Risk Detection (fraud, investigation, lawsuit, cyberattack, etc.)
- Context Disambiguation & NLP Mitigation Detection
- Evidence Confidence Scoring using exponential saturation
- Configurable Risk Score Aggregation (`blend` default applying 80% average / 20% peak weighting; `top_k_mean`, `max`, and `mean` supported as configurable alternatives)
- REST API using FastAPI with full request/response schemas
- Automatic Model Loading with startup lifespan management
- Comprehensive Unit & Integration Test Suite with Pytest
- 10-Company Benchmark Dataset Evaluation

---

# Risk Score Interpretation

The risk score (0-100) is calculated based on keyword severity, FinBERT sentiment analysis, and configurable aggregation. By default, `blend` is the aggregation strategy, combining 80% average headline score and 20% peak headline score to provide a calibrated, discriminating risk spread. Alternative strategies (`top_k_mean`, `max`, and `mean`) are supported via configuration. These bands provide actionable operational guidelines for procurement teams:

| Score Range | Risk Level | Interpretation & Recommended Procurement Action |
| :--- | :--- | :--- |
| **0.0 - 25.0** | **Low** | Routine operational updates, clean or positive news, and minimal risk signals. Continue normal procurement operations. |
| **25.1 - 35.0** | **Medium** | Predominantly stable operations with isolated disruptions or minor friction. Standard supplier monitoring, verify resilience plans. |
| **35.1 - 45.0** | **High** | Significant operational, supply chain, legal, labor, or restructuring disruptions across multiple headlines. Review supplier contracts, monitor lead times, establish secondary supplier contingencies. |
| **45.1 - 100.0** | **Critical** | Severe structural, legal, or terminal risks; persistent negative sentiment (>65% of volume), massive recalls, lawsuits, layoffs, investigations. Immediate procurement intervention and risk committee escalation. |

---

# Project Structure

```text
supplier-risk/
│
├── src/
│   ├── __init__.py
│   ├── analyze.py                 # FastAPI application and /predict endpoint
│   ├── config.py                  # Config-driven weights, penalties, and validation
│   ├── data.py                    # Dataset loading, validation, and fallback handling
│   ├── evaluate.py                # Batch evaluation runner across benchmark dataset
│   ├── predict.py                 # Core scoring orchestration, aggregation, and confidence logic
│   ├── preprocess.py              # Text normalization and cleaning
│   ├── sentiment.py              # FinBERT pipeline integration
│   ├── signals.py                # Keyword signal detection, mitigation, and context logic
│   └── supplier_headlines.json   # 10-company benchmark dataset (120 headlines)
│
├── tests/
│   └── test_predict.py           # Unit, integration, config, and endpoint tests
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
| **Aggregation Strategy**| `AGGREGATION_STRATEGY` | `"blend"` | Aggregation strategy: `blend` (default), `top_k_mean`, `max`, or `mean` |
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

### 2. Predict Supplier Risk

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

# Risk Scoring & Anti-Dilution Architecture

## Scoring Pipeline

The scoring pipeline operates as follows:
`sentiment` + `risk signals` → `headline score` → `configurable aggregation (blend / top_k_mean / max / mean)` → `0–100 risk score`

1. **Individual Headline Scoring**:
   $$\text{headline\_score} = (\text{penalty} \times \text{confidence}) + \sum_{k \in \text{detected}} \text{weight}(k)$$

2. **Configurable Risk Aggregation**:
   The service provides configurable aggregation strategies to translate headline-level scores into an overall supplier risk score:
   - **`blend` (default)**: Calibrated $0.80 \times \text{average\_score} + 0.20 \times \text{peak\_score}$. Combines the overall average risk posture across all headlines with a 20% weighting on the worst-case acute event, ensuring a discriminating spread across diverse supplier profiles.
   - **`top_k_mean` ($K=3$)**: Anti-dilution strategy that averages the top-$K$ risk-bearing headline scores ($s_i > 0$). Severe acute events (such as bankruptcy, fraud, or lawsuits) maintain their severity even when surrounded by numerous neutral headlines.
   - **`max`**: Evaluates supplier risk by the single worst-case headline score ($\text{peak\_score}$).
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

# 10-Company Benchmark Dataset

The dataset is located in `src/supplier_headlines.json` and contains **120 realistic headlines across 10 global suppliers** (12 headlines per supplier):

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

### Evaluation Benchmark Results

| Supplier | Headlines | Positive | Neutral | Negative | Final Risk Score | Evidence Confidence | Risk Tier |
|----------|-----------|----------|---------|----------|------------------|---------------------|-----------|
| Boeing | 12 | 5 | 1 | 6 | 40.83 | 0.4878 | High |
| Intel | 12 | 3 | 3 | 6 | 42.30 | 0.4504 | High |
| Tesla | 12 | 4 | 0 | 8 | 48.37 | 0.5263 | Critical |
| Nissan | 12 | 5 | 0 | 7 | 43.72 | 0.5049 | High |
| Foxconn | 12 | 4 | 4 | 4 | 30.24 | 0.3330 | Medium |
| TSMC | 12 | 7 | 1 | 4 | 31.30 | 0.2977 | Medium |
| Maersk | 12 | 5 | 1 | 6 | 42.65 | 0.4541 | High |
| BASF | 12 | 8 | 0 | 4 | 32.09 | 0.3314 | Medium |
| Siemens | 12 | 8 | 2 | 2 | 19.27 | 0.1587 | Low |
| Apex Logistics | 12 | 1 | 1 | 10 | 74.91 | 0.6643 | Critical |

---

# Human Sanity Check

### Scoring Context & Aggregation Behavior
- The default `blend` strategy (80% average, 20% peak) produces a highly discriminating, calibrated distribution across the real 10-company benchmark dataset, spanning all four operational risk tiers (Low, Medium, High, and Critical).
- Siemens scores in the **Low** risk tier (19.27) reflecting its predominantly positive news profile, while distressed suppliers such as Tesla (48.37) and Apex Logistics (74.91) are appropriately escalated to **Critical**.
- `top_k_mean`, `max`, and `mean` remain fully supported as configurable alternative strategies via environment variables or runtime settings.

### Highest Risk Supplier: Apex Logistics (Score: 74.91, Evidence Confidence: 0.6643)
- **Underlying Signals**: `strike` (25), `cyberattack` (35), `default` (40), `restructuring` (20), `fraud` (40), `investigation` (25), `lawsuit` (25), `recall` (30), `insolvency` (45), `downgrade` (20), `shutdown` (35), `delays` (15), `layoff` (25), `bankruptcy` (50).
- **Sentiment Breakdown**: 10 Negative, 1 Neutral, 1 Positive.
- **Evidence Confidence**: **0.6643** (highest evidence confidence among these suppliers).
- **Top 3 Highest Risk Headlines**:
  1. *"Analysts issue major downgrade on Apex Logistics amid insolvency fears."*
  2. *"Regulators launch fraud investigation into Apex Logistics accounting practices."*
  3. *"Apex Logistics files for emergency restructuring following severe debt default."*
- **Human Rationale**: Apex Logistics has the highest risk score at **74.91** and also the highest evidence confidence among these suppliers at **0.6643**. The company suffers from multiple catastrophic financial signals (debt default, insolvency, bankruptcy), operational shutdowns, and fraud investigations, with 10 out of 12 headlines negative. A human evaluator would immediately classify Apex Logistics as Critical risk.

### Lowest Risk Supplier: Siemens (Score: 19.27, Evidence Confidence: 0.1587)
- **Underlying Signals**: `delays` (15), `shortage` (20).
- **Sentiment Breakdown**: 8 Positive, 2 Neutral, 2 Negative.
- **Evidence Confidence**: **0.1587** (lowest evidence confidence among these suppliers).
- **Top 3 Highest Risk Headlines**:
  1. *"Siemens faces temporary component shortage for specialized circuit breakers."*
  2. *"Supply chain delays cause minor shipment backlog for Siemens medical devices."*
  3. *"Siemens reports robust revenue growth driven by industrial automation orders."*
- **Human Rationale**: Siemens has the lowest risk score at **19.27** (placing it squarely in the Low tier) and lowest evidence confidence at **0.1587**. Negative events are limited to minor transient supply issues (circuit breaker shortage and medical device shipping delays), with 8 of 12 headlines positive. Under the default `blend` strategy, Siemens appropriately reflects a healthy operational posture rather than being artificially escalated into Critical.

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
