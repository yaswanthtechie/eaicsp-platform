# Supplier Risk NLP Service

## Overview

The **Supplier Risk** service is an independent Machine Learning microservice built with **FastAPI** that evaluates supplier risk by analyzing news headlines.

The service combines:
- **FinBERT Sentiment Analysis** (`ProsusAI/finbert`)
- **Config-Driven Keyword Risk Detection** (Financial, Operational, Reputational)
- **Calibrated Risk Scoring & Evidence Confidence Calculation**
- **REST API Serving** via FastAPI (`/predict`, `/health`, `/api/v1/supplier-risk/*`)
- **Automated Unit & Integration Testing** with Pytest
- **10-Company Calibration & Benchmark Dataset**

---

# Features

- **FinBERT Sentiment Analysis**: Domain-adapted financial sentiment classification (`positive`, `neutral`, `negative`).
- **Configurable Signal Weights**: Weights and penalties driven by `src/config.py` and environment variables without changing source code.
- **Evidence Confidence Metric**: Saturating confidence score ($1 - e^{-n/8}$) reflecting headline observation volume.
- **REST API Serving**: FastAPI `/predict` endpoint for direct ML predictions without authentication requirements.
- **10-Company Benchmark Dataset**: 120 curated headlines spanning low, medium, and high risk suppliers.
- **Automated Unit Testing**: Complete test suite covering preprocessing, scoring, configuration overrides, schema validation, and HTTP endpoints.

---

# Project Structure

```text
supplier-risk/
│
├── src/
│   ├── __init__.py
│   ├── analyze.py                 # FastAPI application and /predict endpoint
│   ├── config.py                  # Config-driven weights, penalties, and validation
│   ├── data.py                    # Dataset loading and fallback handling
│   ├── evaluate.py                # Batch evaluation runner across benchmark dataset
│   ├── predict.py                 # Core scoring orchestration and confidence logic
│   ├── preprocess.py              # Text normalization and cleaning
│   ├── sentiment.py              # FinBERT pipeline integration
│   ├── signals.py                # Keyword signal detection logic
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
| **Confidence Divisor**| `CONFIDENCE_DIVISOR` | `8.0` | Saturation divisor in $1 - e^{-n/8}$ |
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
      "risk_score": 75.33,
      "confidence": 0.3127,
      "sentiment_breakdown": {
        "positive": 0,
        "neutral": 0,
        "negative": 3
      },
      "signals": [
        {
          "keyword": "downgrade",
          "weight": 20
        },
        {
          "keyword": "insolvency",
          "weight": 45
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
          "keyword": "restructuring",
          "weight": 20
        },
        {
          "keyword": "default",
          "weight": 40
        }
      ],
      "top_worst_3": [
        {
          "headline": "Analysts issue major downgrade on Apex Logistics amid insolvency fears.",
          "sentiment": "negative",
          "score": 103.54,
          "signals": [
            {
              "keyword": "downgrade",
              "weight": 20
            },
            {
              "keyword": "insolvency",
              "weight": 45
            }
          ]
        },
        {
          "headline": "Apex Logistics files for emergency restructuring following severe debt default.",
          "sentiment": "negative",
          "score": 98.71,
          "signals": [
            {
              "keyword": "restructuring",
              "weight": 20
            },
            {
              "keyword": "default",
              "weight": 40
            }
          ]
        },
        {
          "headline": "Regulators launch fraud investigation into Apex Logistics accounting practices.",
          "sentiment": "negative",
          "score": 97.88,
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
        }
      ]
    }
  }
}
```

---

# Scoring Calculation

1. **Text Preprocessing**: Raw headline is cleaned (lowercased, punctuation stripped, whitespace normalized).
2. **Sentiment Analysis**: Raw text evaluated via FinBERT $\rightarrow$ `label` and `confidence`.
3. **Sentiment Penalty**:
   $$\text{penalty} = \begin{cases} \text{NEGATIVE\_PENALTY} \times \text{confidence} & \text{if negative} \\ \text{NEUTRAL\_PENALTY} \times \text{confidence} & \text{if neutral} \\ \text{POSITIVE\_PENALTY} \times \text{confidence} & \text{if positive} \end{cases}$$
4. **Keyword Signals**: All matching keyword weights summed for the headline:
   $$\text{signal\_score} = \sum_{k \in \text{detected}} \text{weight}(k)$$
5. **Headline Score**: $\text{headline\_score} = \text{penalty} + \text{signal\_score}$
6. **Final Risk Score**:
   $$\text{risk\_score} = \min\left(\text{MAX\_RISK\_SCORE}, \frac{1}{N} \sum_{i=1}^{N} \text{headline\_score}_i\right)$$
7. **Evidence Confidence**:
   $$\text{confidence} = 1.0 - e^{-\frac{N}{\text{DIVISOR}}}$$

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

| Supplier | Headlines | Sentiment (Pos / Neu / Neg) | Final Risk Score | Evidence Confidence | Risk Tier |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Siemens** | 12 | 8 / 2 / 2 | **9.39** | 0.7769 | **Low Risk** |
| **BASF** | 12 | 8 / 0 / 4 | **17.29** | 0.7769 | **Low Risk** |
| **TSMC** | 12 | 7 / 1 / 4 | **20.75** | 0.7769 | **Low-Medium Risk** |
| **Foxconn** | 12 | 4 / 4 / 4 | **28.23** | 0.7769 | **Medium Risk** |
| **Maersk** | 12 | 5 / 1 / 6 | **28.27** | 0.7769 | **Medium Risk** |
| **Intel** | 12 | 3 / 3 / 6 | **33.19** | 0.7769 | **Medium Risk** |
| **Boeing** | 12 | 5 / 1 / 6 | **34.96** | 0.7769 | **Medium Risk** |
| **Nissan** | 12 | 5 / 0 / 7 | **37.54** | 0.7769 | **Medium-High Risk** |
| **Tesla** | 12 | 4 / 0 / 8 | **40.80** | 0.7769 | **Medium-High Risk** |
| **Apex Logistics** | 12 | 1 / 1 / 10 | **67.73** | 0.7769 | **High Risk** |

---

# Human Sanity Check

### Highest Risk Supplier: Apex Logistics (Score: 67.73)
- **Underlying Signals**: `bankruptcy` (50), `insolvency` (45), `default` (40), `fraud` (40), `cyberattack` (35), `shutdown` (35), `recall` (30), `strike` (25), `layoff` (25), `investigation` (25), `lawsuit` (25).
- **Sentiment Breakdown**: 10 Negative, 1 Neutral, 1 Positive.
- **Top Risk Headlines**:
  1. *"Analysts issue major downgrade on Apex Logistics amid insolvency fears."*
  2. *"Regulators launch fraud investigation into Apex Logistics accounting practices."*
  3. *"Apex Logistics files for emergency restructuring following severe debt default."*
- **Human Rationale**: The high score (67.73) accurately reflects critical distress. The company suffers simultaneous operational paralysis (strike, ransomware cyberattack, port shutdown), reputational crises (fraud investigation, client lawsuits), and catastrophic financial failure (debt default, insolvency, bankruptcy proceedings). A human evaluator reviewing these events would immediately classify this supplier as high risk.

### Lowest Risk Supplier: Siemens (Score: 9.39)
- **Underlying Signals**: `shortage` (20), `delays` (15) — no severe financial or reputational triggers.
- **Sentiment Breakdown**: 8 Positive, 2 Neutral, 2 Negative.
- **Top Headlines**:
  1. *"Siemens reports robust revenue growth driven by industrial automation orders."*
  2. *"Siemens secures multi-billion dollar railway electrification deal."*
  3. *"Siemens receives top environmental and sustainability rating from industry auditors."*
- **Human Rationale**: The low score (9.39) accurately captures an operationally healthy, financially strong supplier. Negative events are limited to minor transient supply bottlenecks (circuit breaker shortage and medical device shipping delays) that were quickly managed, while the majority of news reflects record order backlog, new infrastructure contracts, and positive earnings. A human procurement officer would confidently consider this supplier low risk.

---

# Running Tests & Evaluation

### Run Test Suite:

```bash
python -m pytest ml-services/supplier-risk/tests -v
```

### Run Batch Evaluation:

```bash
python -m src.evaluate
```

---

# Logging

The service logs:
- Model loading on startup lifespan
- Service shutdown events
- Prediction and request processing exceptions
- Validation errors
