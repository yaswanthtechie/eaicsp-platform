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

- Python 3.11+
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

Example Response

```json
{
  "supplier_summary": {
    "TechCorp": {
      "supplier": "TechCorp",
      "risk_score": 74.25,
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

---

# Risk Score Calculation

The final supplier risk score is calculated using:

- FinBERT sentiment confidence
- Keyword signal weights
- Average headline score
- Maximum score capped at **100**

---

# Dataset

The project includes a sample dataset:

```
src/supplier_headlines.json
```

Dataset contains:

- 5 suppliers
- 10 headlines per supplier
- Total 50 headlines

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
9 passed in 66.39s
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
