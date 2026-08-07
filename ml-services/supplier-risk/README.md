# Supplier Risk NLP Service

A FastAPI-based Machine Learning microservice that analyzes supplier-related news headlines and calculates a supplier risk score using NLP sentiment analysis (FinBERT) and keyword-based risk detection.

---

# Features

- FastAPI REST API
- HuggingFace FinBERT Sentiment Analysis
- Financial Risk Detection
- Operational Risk Detection
- Reputational Risk Detection
- Supplier Risk Score Calculation
- Pydantic Response Models
- Health Check Endpoint
- Unit Testing with Pytest

---

# Technology Stack

- Python 3.11+
- FastAPI
- Uvicorn
- HuggingFace Transformers
- PyTorch
- Pydantic
- Pytest

---

# Installation

## 1. Create Virtual Environment

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

## 2. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## 3. Run Tests

```bash
pytest tests/
```

---

## 4. Start the API

```bash
uvicorn analyze:app --reload --port 8006
```

---

## 5. Open Swagger Documentation

```
http://localhost:8006/docs
```

---

# Project Structure

```
supplier-risk/
│
├── analyze.py
├── data.py
├── evaluate.py
├── predict.py
├── preprocess.py
├── sentiment.py
├── signals.py
├── supplier_headlines.json
├── requirements.txt
├── README.md
└── tests/
```

---

# Module Description

## data.py

Loads and groups supplier news headlines.

---

## preprocess.py

Performs text preprocessing.

- Lowercase conversion
- Remove punctuation
- Remove extra whitespace

---

## sentiment.py

Loads the HuggingFace FinBERT model and performs sentiment analysis.

Returns

- Positive
- Neutral
- Negative

with confidence score.

---

## signals.py

Detects predefined supplier risk keywords.

Categories include

### Financial

- Bankruptcy
- Insolvency
- Default
- Downgrade
- Restructuring
- Layoff

### Operational

- Strike
- Recall
- Disruption
- Shortage

### Reputational

- Fraud
- Investigation
- Lawsuit
- Sanction

---

## predict.py

Combines

- Sentiment Analysis
- Signal Detection

to calculate

- Risk Score
- Sentiment Breakdown
- Top 3 Worst Headlines
- Unique Risk Signals

---

## analyze.py

FastAPI application.

Endpoints

### Health

```
GET /health
```

### Risk Analysis

```
GET /api/v1/supplier-risk/analyze
```

---

## evaluate.py

Runs the NLP pipeline locally using the JSON dataset.

---

# Example Response

```json
{
  "supplier": "Tesla",
  "risk_score": 52.75,
  "sentiment_breakdown": {
    "positive": 2,
    "neutral": 3,
    "negative": 5
  },
  "signals": [
    {
      "keyword": "recall",
      "weight": 20
    }
  ],
  "top_worst_3": [
    {
      "headline": "Tesla announces major recall...",
      "score": 51.42
    }
  ]
}
```

---

# Example Usage

```python
from sentiment import analyze_sentiment

result = analyze_sentiment(
    "The supplier announced a major breakthrough in logistics."
)

print(result)
```

Example Output

```python
{
    "label": "positive",
    "confidence": 0.95
}
```

---

# Risk Scoring Method

Each headline receives a score based on

- FinBERT sentiment
- Keyword weights

The final supplier risk score is calculated using the average of all headline scores.

This prevents suppliers with a large number of news articles from being unfairly penalized because of higher news volume.

---

# Sample Suppliers

The evaluation dataset contains realistic headlines for

- Boeing
- Intel
- Tesla
- Nissan
- Foxconn

The service analyzes every supplier independently and generates a complete supplier risk summary.

---

# Run Evaluation

```bash
python evaluate.py
```

---

# Run API

```bash
uvicorn analyze:app --reload --port 8006
```

---

# Run Tests

```bash
pytest tests/
```

---

# Author

Supplier Risk NLP Microservice

Built using

- FastAPI
- HuggingFace Transformers
- FinBERT
- PyTorch
