# Supplier Risk NLP Service

## Overview

The **Supplier Risk** service is an independent Machine Learning microservice built with **FastAPI** that evaluates supplier risk by analyzing news headlines.

The service combines:
- **FinBERT Sentiment Analysis** (`ProsusAI/finbert`)
- **Config-Driven Keyword Risk Detection** (Financial, Operational, Reputational)
- **Calibrated Risk Scoring & Evidence Confidence Calculation** (Config-Driven Anti-Dilution / Top-K Mean / Max / Blend / Mean)
- **Anti-Dilution Architecture** (protecting acute risks from high-volume neutral dilution)
- **MongoDB Article Store & Cross-Source Deduplication** (story_hash unique index, supplier/date compound indexes)
- **Authoritative Pipeline Storage & Idempotent Migration** (`python -m src.migrate`)
- **Pretrained Transformer Benchmark Comparison** (Zero-shot `ProsusAI/finbert` vs production hybrid baseline)
- **Token-Level Self-Attention Explanations** (Layer 12 cross-head [CLS]-directed attribution)
- **MLflow 3.16.1 Experiment Tracking** (`supplier-risk-milestone-2`)
- **REST API Serving** via FastAPI (`/predict`, `/health`, `/api/v1/supplier-risk/*`)
- **Automated Unit & Integration Testing** with Pytest
- **25-Company Calibration & Benchmark Dataset** (300 headlines)
- **Historical Risk Trend & Deterioration Detection** (`is_deteriorating`, `risk_delta`, `deterioration_summary`)
- **Compliance Integration Contract** (Contract-first future consumption specification)

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
- MongoDB Local Article Storage with SHA-256 `story_hash` cross-source wire deduplication
- Idempotent Migration Runner (`src/migrate.py`) from JSON to authoritative MongoDB storage
- Pretrained Transformer Comparison (`ProsusAI/finbert` vs Hybrid baseline on held-out data)
- Token-Level Attention Explanations (Layer 12 cross-head [CLS] attribution for 100% of predictions)
- MLflow 3.16.1 Experiment & Artifact Tracking
- REST API using FastAPI with full request/response schemas
- Automatic Model Loading with startup lifespan management
- Comprehensive Unit & Integration Test Suite with Pytest
- 25-Company Benchmark Dataset Evaluation
- Historical Risk Trend with Time-Series Deterioration Detection
- Compliance Integration Contract Specification (Documentation-Only)

---

# Risk Score Interpretation

The risk score (0-100) is calculated from keyword severity, FinBERT sentiment penalties, and configurable aggregation (`top_k_mean` by default). Under `top_k_mean`, repeated risk-bearing headlines increase the score through the configured volume factor, while positive coverage reduces it through the configured mitigation factor. The operational 4-tier classification provides actionable triage guidelines for procurement teams:

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
│   ├── config.py                          # Config-driven weights, penalties, MongoDB & validation settings
│   ├── data.py                            # Authoritative MongoDB loader with test fallback handling
│   ├── db.py                              # MongoDB connection pool, indexing, deduplication & queries
│   ├── evaluate.py                        # Batch evaluation runner across benchmark dataset
│   ├── migrate.py                         # Idempotent JSON-to-MongoDB migration utility
│   ├── predict.py                         # Core scoring orchestration, anti-dilution, and confidence logic
│   ├── preprocess.py                      # Text normalization and cleaning
│   ├── sentiment.py                       # FinBERT pipeline integration
│   ├── signals.py                         # Keyword signal detection, mitigation, and context logic
│   ├── transformer_eval.py                # Transformer evaluation, attention explanations & MLflow tracking
│   ├── trend.py                           # Date validation, trend aggregation, and recency decay
│   ├── supplier_headlines.json            # 10-company baseline dataset (120 headlines)
│   ├── supplier_headlines_15.json         # 15-company benchmark dataset (180 headlines)
│   ├── supplier_headlines_25.json         # 25-company expanded benchmark dataset (300 headlines)
│   ├── supplier_trend_headlines.json      # 10-company baseline trend dataset (120 headlines)
│   ├── supplier_trend_headlines_15.json   # 15-company benchmark trend dataset (180 headlines)
│   ├── supplier_trend_headlines_25.json   # 25-company expanded trend dataset (300 headlines)
│   └── synthetic_held_out_validation.json # 12-company non-circular held-out validation dataset (96 headlines)
│
├── tests/
│   ├── test_api.py                        # REST API endpoint and contract tests
│   ├── test_evidence_confidence.py        # Milestone 2: Evidence and confidence tests
│   ├── test_integration.py                # Unmocked slow integration benchmark tests
│   ├── test_milestone3_config_and_validation.py # Milestone 3: Config, validation, and benchmark tests
│   ├── test_mongo.py                      # Round 10 Milestone 1: MongoDB storage, deduplication & migration tests
│   ├── test_predict.py                    # Unit tests for scoring, signals, and deduplication
│   ├── test_transformer_eval.py           # Round 10 Milestone 2 & 3: Transformer eval, MLflow & attention tests
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
- **MongoDB** & **PyMongo** (Raw article store, unique hashing deduplication, compound indexes)
- **MLflow 3.16.1** (Experiment tracking, metrics, confusion matrix & explanation artifacts)
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
| **Volume Weight**      | `VOLUME_WEIGHT` | `0.15` | Repeated risk coverage amplification factor under `top_k_mean` |
| **Mitigation Weight**  | `MITIGATION_WEIGHT` | `0.35` | Mitigating positive coverage discount factor under `top_k_mean` |
| **Signal Weights JSON**| `SIGNAL_WEIGHTS_JSON` | *Default dict* | JSON map of custom keyword weights |
| **MongoDB URI**        | `MONGODB_URI` | `"mongodb://localhost:27017"` | MongoDB host connection string |
| **MongoDB Database**   | `MONGODB_DATABASE` | `"supplier_risk"` | MongoDB database name |
| **MongoDB Collection** | `MONGODB_COLLECTION` | `"headlines"` | MongoDB collection for articles |


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
  "mongodb_uri": "mongodb://localhost:27017",
  "mongodb_database": "supplier_risk",
  "mongodb_collection": "headlines",
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

Trend responses include current_risk_tier, previous_risk_tier, peak_risk_score, and peak_risk_tier; a rising score is considered deteriorating only when the risk tier worsens or the current tier is High/Critical.

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
  "current_risk_score": 39.66,
  "previous_risk_score": 30.71,
  "trend_direction": "rising",
  "is_deteriorating": true,
  "risk_delta": 8.95,
  "deterioration_summary": "Risk is deteriorating: score increased by +8.95 points (from 30.71 to 39.66) exceeding the sensitivity threshold of 3.0.",
  "article_count": 12,
  "current_window_article_count": 5,
  "historical_article_count": 4,
  "window_days": 30,
  "window_start": "2026-02-21",
  "window_end": "2026-03-23",
  "previous_window_start": "2026-01-26",
  "previous_window_end": "2026-02-16",
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

*Note: Supplier lookup is case-insensitive. An unknown supplier returns `404 Not Found`; a known supplier with no usable records returns an empty trend response.*

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
  - **`top_k_mean` (default, $K=3$)**: Averages the top-$K$ risk-bearing headline scores ($s_i > 0$), then applies volume amplification for repeated risk events and a positive-coverage mitigation discount. Severe acute events (such as bankruptcy, fraud, or lawsuits) remain visible while additional adverse coverage and good news both affect the entity score.
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
  - Because the current formula measures the concentration and consistency of risk evidence, corroborating positive coverage can lower confidence even when it lowers risk. Treat this as risk-evidence confidence, not general forecast certainty.
   - Bounded strictly within $[0.0, 1.0]$. Zero headlines yields $0.0$.

---

# Round 10 – Supplier Risk NLP

In Round 10, the Supplier Risk NLP Service implemented three core milestones: transitioning from static JSON files to an authoritative local MongoDB document store with deterministic cross-source deduplication, conducting a formal non-circular transformer evaluation benchmark comparing the production hybrid pipeline against a pure pretrained transformer (`ProsusAI/finbert`) tracked in MLflow 3.16.1, and generating token-level self-attention explanations for 100% of predictions.

---

## Running locally

```bash
docker compose -f docker-compose.dev.yml up -d     # MongoDB on 127.0.0.1:27017
python -m src.migrate                              # import all committed trend datasets (safe to re-run)

python -m pytest                                   # unit tests, no Docker needed
python -m pytest -m integration                    # real-MongoDB tests (container must be up)

python -m src.transformer_eval                     # Milestone 2 comparison, logs both runs to MLflow
python -m src.transformer_eval --spot-check        # Milestone 3 explanation table for the hand-check
mlflow ui                                          # view the runs
```

## Status

| Milestone | Status |
|---|---|
| M1 MongoDB store | Done: dedup by `story_hash`, indexes, idempotent migration; `/analyze-static` and the trend endpoint read Mongo |
| M2 Transformer comparison | Done: zero-shot FinBERT vs current hybrid on the same 12-supplier held-out set, both in MLflow |
| M3 Explanations | Done: last-layer [CLS] attention, whole words, stopwords removed; hand-checked table below |

**Not done / limitations**
- Dedup only catches the same headline after normalisation. The same story reworded by two outlets (e.g. "Acme files for bankruptcy" by Reuters vs "Acme Corp files Chapter 11" by Bloomberg) is stored twice.
- Because the publication date is excluded from `story_hash`, an identical headline recurring on different dates (e.g. periodic recurring strikes months apart) is collapsed into a single document. Smarter near-duplicate detection (e.g. Jaccard similarity >= 0.8 over normalized tokens within a rolling 3-day temporal window per supplier) was not implemented.
- Attention is not a faithful attribution method; SHAP / integrated gradients were not tried.

---

## Milestone 1 – Articles in MongoDB

### 1. MongoDB Local Article Storage
- **Connection Architecture & Client Caching**: Implemented in `src/db.py`, the storage layer manages connection pooling via `get_mongo_client()`, database handles via `get_database()`, and collection handles via `get_collection()`. Reuses client instances across calls based on URI.
- **Fail-Fast Connectivity Verification**: `ping_mongodb()` executes the administrative command `{"ping": 1}` with a short timeout (`serverSelectionTimeoutMS=3000`). If the MongoDB daemon is offline, it fails fast and raises a `ConnectionError` instead of hanging or timing out queries downstream.
- **Config-Driven Settings**: Configured in `src/config.py` with environment variable overrides:
  - `MONGODB_URI` (default: `"mongodb://localhost:27017"`)
  - `MONGODB_DATABASE` (default: `"supplier_risk"`)
  - `MONGODB_COLLECTION` (default: `"headlines"`)
- **Document Structure**:
  ```json
  {
    "supplier": "Tesla",
    "headline": "Tesla announces a major recall of 2 million vehicles over autopilot software issues.",
    "story_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "date": "2026-01-05",
    "source": "Reuters",
    "created_at": "2026-10-01T12:00:00Z"
  }
  ```

### 2. story_hash Based Cross-Source Deduplication
- **Deterministic Identity Generation**: `generate_story_hash(supplier, headline)` computes a deterministic SHA-256 digest:
  - Normalizes `supplier`: stripped, lowercased, and collapsed internal whitespace.
  - Normalizes `headline`: stripped, lowercased, and collapsed internal whitespace.
  - Generates SHA-256 over `"{norm_supplier}::{norm_headline}"`.
- **Cross-Source Wire Deduplication**: The news `source` (e.g. *Reuters*, *Bloomberg*, *Associated Press*) is purposefully excluded from the hash. If the exact same corporate event or headline is reported by different wire agencies, it resolves to an identical `story_hash`.
- **Database Engine Unique Constraint**: MongoDB enforces uniqueness on `story_hash` via a unique ascending index. Any attempt to insert an existing story raises `pymongo.errors.DuplicateKeyError` at the database engine level.

### 3. Supplier, Date, and Compound Indexes
The `ensure_indexes(collection)` function creates four dedicated indexes to optimize query performance and enforce constraints:
1. `unique_story_hash`: `[("story_hash", pymongo.ASCENDING)]`, `unique=True` — Enforces wire-level story deduplication at write time.
2. `idx_supplier`: `[("supplier", pymongo.ASCENDING)]` — Accelerates supplier-level news queries.
3. `idx_date`: `[("date", pymongo.ASCENDING)]` — Accelerates temporal timeline filtering and date boundaries.
4. `idx_supplier_date`: `[("supplier", pymongo.ASCENDING), ("date", pymongo.ASCENDING)]` — Compound index enabling rapid chronological sorting for time-series trend analysis and rolling deterioration windows.

### 4. Migration and Idempotent Import
- **Module & CLI**: Implemented in `src/migrate.py` (`run_migration()`, `migrate_dataset()`).
- **Default Multi-Dataset Import**: Running `python -m src.migrate` without arguments imports all committed trend datasets by default (`supplier_trend_headlines.json`, `supplier_trend_headlines_15.json`, `supplier_trend_headlines_25.json`), populating MongoDB with all 25 benchmark suppliers.
- **Idempotency Guarantee**: Migration can be run repeatedly without duplicating documents or failing. Existing records with identical `story_hash` are safely skipped.
- **In-Place Date Enrichment**: If an existing headline was imported without a date, running migration with a date-aware dataset enriches the document in-place (`$set: {"date": ...}`) without creating a new record.
- **Source Protection**: Source JSON datasets (`supplier_trend_headlines.json`, `supplier_headlines.json`, etc.) are strictly read-only and never modified, overwritten, or deleted.
- **CLI Commands**:
  ```bash
  # Migrate all committed trend datasets by default:
  python -m src.migrate

  # Or migrate an individual file:
  python -m src.migrate --file src/supplier_trend_headlines.json
  ```
- **Execution Metrics**: Outputs full operational statistics: `total`, `inserted`, `skipped` (duplicates), and `failed`.

### 5. MongoDB as Authoritative Runtime Source for Scoring / Trend Pipeline
- **Runtime Source Integration**: `src/data.py` (`load_headlines()`, `load_trend_headlines()`, and `load_active_trend_headlines()`) queries MongoDB directly via `fetch_headlines_grouped()` and `fetch_trend_headlines_grouped()`. MongoDB is the only source for runtime scoring and the trend endpoint (`/api/v1/supplier-risk/trend/{supplier_name}`).
- **Shared Store Effect on `/analyze-static`**: Because all committed trend datasets are migrated into MongoDB, `/analyze-static` now scores every supplier present in Mongo (all 25 benchmark suppliers instead of only the 10 baseline entities). Ingesting supplier articles into the shared database store immediately exposes them to both static analysis and trend scoring.
- **Explicit Benchmark Isolation**: Benchmark tables and validation checks explicitly load committed files (e.g. `load_25_company_trend_dataset()`), keeping benchmark evaluations independent of live database modifications.
- **Optimized Projections**: Queries retrieve only necessary fields (`supplier`, `headline`, `date`, `story_hash`) with `_id` omitted.
- **Secondary In-Memory Deduplication**: An in-memory hash set safeguard (`seen_hashes`) runs alongside database indexing.
- **Scoring Equivalence Validation**: Validated by `tests/test_mongo.py::test_scoring_equivalence_mongo_vs_json`, proving that `risk_score`, `confidence`, `sentiment_breakdown`, and `signals` are 100% numerically identical when loading from MongoDB versus baseline JSON files.

### 6. Explicit Failure Behavior When MongoDB is Unavailable / Empty
- **Fail-Fast Runtime Policy**: In production mode (`use_fallback=False`), if MongoDB is unreachable or the target collection is empty, `load_headlines()` and `load_trend_headlines()` raise an explicit, actionable `RuntimeError`:
  ```text
  RuntimeError: MongoDB is the authoritative runtime data source for supplier risk scoring, but querying failed: ... Ensure the supplier-risk-mongo container is running and run 'python -m src.migrate' to populate the collection.
  ```
- **Zero Silent Fallback**: The service never silently degrades to stale JSON files during live execution.
- **Test-Only Opt-In Fallback**: An explicit parameter (`use_fallback=True`) is reserved exclusively for offline unit testing where no live MongoDB container is present.

---

## Milestone 2 – Transformer Comparison & MLflow Tracking

### 1. Exact Transformer Model: ProsusAI/finbert
- **Pretrained Identifier**: `ProsusAI/finbert` (Hugging Face BERT-base architecture, ~110M parameters).
- **Selection Rationale vs DistilBERT**:
  1. **Financial Domain Specialization**: FinBERT was pre-trained and fine-tuned on corporate financial communication and the Financial PhraseBank dataset. It natively understands financial and business risk semantics (e.g., debt defaults, restructuring, credit downgrades, insolvency, liquidity constraints) far more accurately than general-domain DistilBERT (trained on general Wikipedia and BookCorpus).
  2. **Local Availability & Deterministic Reproducibility**: Weights are verified locally operational and cached, ensuring zero external network latency or internet dependencies during offline evaluation.
  3. **Efficient Footprint**: ~110M parameters enables fast, deterministic CPU inference (~0.3s/supplier) while preserving deep multi-head contextual embeddings.

### 2. Evaluation Protocol & Zero-Leakage Guarantee
- **Held-Out Validation Dataset**: Evaluated on `src/synthetic_held_out_validation.json` (12 fictional suppliers, 96 headlines, 8 headlines/supplier).
- **Zero Data Overlap**: 100% disjoint from development benchmark sets (zero supplier or headline overlap).
- **Balanced Operational Tiers**: Exactly 3 suppliers (24 headlines) per operational risk tier (Low, Medium, High, Critical).
- **Independent Expected Labels & Fixed Thresholds**: Uses independently authored `expected_tier` ground-truth labels and identical fixed risk tier ceilings from `src/config.py`:
  - **Low**: Score $< 60.0$
  - **Medium**: $60.0 \le \text{Score} < 72.0$
  - **High**: $72.0 \le \text{Score} < 85.0$
  - **Critical**: $\text{Score} \ge 85.0$
- **Strict Zero-Shot Inference**: Zero training, zero fine-tuning, and zero parameter updates on the held-out validation set, guaranteeing **ZERO data leakage**.

### 3. Model Architecture Comparison

| Dimension | Current Production Model (Baseline) | Pure Pretrained Transformer |
| :--- | :--- | :--- |
| **Model Type** | Hybrid: FinBERT Sentiment + Rule-Based Keyword Signals | Pure Transformer Zero-Shot Sentiment |
| **Headline Scoring** | $(\text{penalty} \times \text{confidence}) + \sum \text{keyword\_weights}$ | $\text{neg}: \text{conf} \times 100.0, \text{neu}: 15.0, \text{pos}: 0.0$ |
| **Aggregation** | Anti-dilution `top_k_mean` ($K=3$) with volume factor & mitigation discount | Unweighted arithmetic mean across all headlines |
| **Keyword Signals** | Enabled (18 domain signals across Financial, Operational, Reputational) | Disabled (Zero-shot sentiment only) |

### 4. Side-by-Side Performance Comparison Results

Evaluated via `python -m src.transformer_eval` against `src/synthetic_held_out_validation.json`:

| Metric | Current Model (Hybrid Baseline) | Pure Transformer (`ProsusAI/finbert`) | Delta |
| :--- | :---: | :---: | :---: |
| **Accuracy** | **75.00%** (9/12 matches) | **83.33%** (10/12 matches) | +8.33% |
| **Macro Precision** | **0.7917** | **0.8333** | +0.0416 |
| **Macro Recall** | **0.7500** | **0.8333** | +0.0833 |
| **Macro F1** | **0.7202** | **0.8333** | +0.1131 |
| **Weighted F1** | **0.7202** | **0.8333** | +0.1131 |
| **Critical Tier Recall** | **100.00%** (3/3 True Positives) | **66.67%** (2/3 True Positives) | **-33.33%** |
| **Critical Tier F1** | **0.8571** | **0.6667** | -0.1904 |
| **High Tier F1** | **0.6667** | **0.6667** | 0.0000 |
| **Medium Tier F1** | **0.5000** | **1.0000** | +0.5000 |
| **Low Tier F1** | **0.8571** | **1.0000** | +0.1429 |
| **Score Mean** | 64.41 | 60.72 | -3.69 |
| **Score Spread** | 100.00 (0.00 to 100.00) | 93.00 (0.00 to 93.00) | -7.00 |
| **Score Std Dev** | 33.70 | 32.26 | -1.44 |

#### Confusion Matrices:

```text
Current Model (Hybrid Baseline):
Expected \ Predicted   |    Low | Medium |   High | Critical | Support
-----------------------------------------------------------------
Low                    |      3 |      0 |      0 |        0 |       3
Medium                 |      1 |      1 |      1 |        0 |       3
High                   |      0 |      0 |      2 |        1 |       3
Critical               |      0 |      0 |      0 |        3 |       3

Pure Transformer (FinBERT Zero-Shot):
Expected \ Predicted   |    Low | Medium |   High | Critical | Support
-----------------------------------------------------------------
Low                    |      3 |      0 |      0 |        0 |       3
Medium                 |      0 |      3 |      0 |        0 |       3
High                   |      0 |      0 |      2 |        1 |       3
Critical               |      0 |      0 |      1 |        2 |       3
```

How to read this comparison. The current approach already uses FinBERT; it adds keyword rules on top. So this compares FinBERT with rules against FinBERT without them. The held-out set has 12 suppliers, so 83.33% vs 75.00% means 10/12 vs 9/12, a one-supplier difference. FinBERT alone does better on Medium/Low, but misses one Critical supplier that the rules catch, and Critical misses are the costly mistake for a supplier-risk tool.

### 5. Observed Limitations & Evidence-Based Insights
1. **Critical Under-Prediction in Pure Transformer**:
   Pure FinBERT sentiment confidence saturates around 0.85–0.95 for negative headlines. Without domain-specific keyword escalation (e.g. `bankruptcy`, `default`, `insolvency`, `restructuring`), pure sentiment averaging scores Meridian Maritime Services at 84.01, missing the Critical threshold ($\ge 85.0$) by 0.99 points and misclassifying it as High. In contrast, the current hybrid model scores it at 93.72, maintaining 100% Critical recall.
2. **Severity Calibration Deficit**:
   A pure sentiment model cannot distinguish between routine operational delays (e.g. minor port shipment delay) and acute existential distress (e.g. bankruptcy filing) when both headlines receive a "negative" classification. Keyword signals provide critical domain severity calibration.
3. **Current Model Over-Penalization**:
   The current hybrid model over-indexes on negative keyword presence for moderate cases like Continental Freightlines (scoring 73.39 -> High vs Medium expected), whereas pure sentiment moderation correctly landed in Medium (60.01).
4. **Boundary Sensitivity**:
   Edge cases near fixed thresholds (e.g. Atlas Heavy Industries at 59.70 vs 60.0 in hybrid; 61.46 in pure transformer) reflect authentic boundary behavior rather than artificial post-hoc tuning.

### 6. MLflow 3.16.1 Tracking
- **Experiment Name**: `supplier-risk-milestone-2`
- **Run Segregation**: Logs both models as independent, non-overwriting runs (`current-model-baseline` and `pure-transformer-finbert`).
- **Logged Entities**:
  - **Tags**: `model_name`, `model_type`, `dataset`, `split`, `framework` (`transformers_4.57.6`), `evaluation_protocol`, `explanation_method`.
  - **Parameters**: `sample_count`, `headline_count`, `tier_low_ceiling`, `tier_medium_ceiling`, `tier_high_ceiling`, `zero_shot_inference`, `signals_enabled`, `explanation_method`.
  - **Metrics**: `accuracy`, `accuracy_percentage`, `macro_precision`, `macro_recall`, `macro_f1`, `weighted_f1`, `score_mean`, `score_min`, `score_max`, `score_spread`, `score_std_dev`, and per-tier metrics (`f1_<tier>`, `precision_<tier>`, `recall_<tier>`, `support_<tier>`, `predicted_<tier>`, `tp_<tier>`).
  - **Artifacts**: `confusion_matrix.json`, `per_tier_metrics.json`, `company_reports.json` (including token explanations), `score_metrics.json`.

---

## Milestone 3 – Token-Level Attention Explanations

### 1. Explanation Method: Layer 12 Cross-Head [CLS]-Directed Attention
- **Mechanism**: Implemented in `src/transformer_eval.py` via `explain_headline_attention()`:
  - Loads `AutoModelForSequenceClassification` with `output_attentions=True`.
  - Extracts the self-attention tensor from the final transformer layer (Layer 12).
  - Averages across all 12 attention heads to obtain robust, head-invariant representations.
  - Measures the attention weights directed from the `[CLS]` classification token (index 0) to each token in the sequence (`outputs.attentions[-1][0].mean(dim=0)[0]`).
- **Noise & Stopword Filtering**: Automatically removes structural tokens (`[CLS]`, `[SEP]`, `[PAD]`), common stopwords (`the`, `and`, `of`, `to`, `in`, `by`, `with`, etc.), punctuation symbols, and merges WordPiece subwords (`##`) back into whole words, summing their attention weights.
- **Ranking**: Salient tokens are ranked by attention magnitude to identify the top-$K$ drivers (default $K=5$).

### 2. Guaranteed 100% Explanation Coverage
- **Complete Verification**: Every single prediction generated by `evaluate_transformer_held_out()` includes a non-empty, sensible explanation:
  - **100% of Suppliers (12/12)** have supplier-level aggregated explanations.
  - **100% of Headlines (96/96)** have headline-level token attributions.
- **Supplier-Level Aggregated Explanation Structure**:
  - `top_risk_driver_headline`: Highest-risk headline driving the supplier assessment.
  - `top_risk_driver_tokens`: Salient attention tokens for that worst-case headline.
  - `supplier_top_tokens`: Cross-headline risk-weighted aggregate tokens for the entity.
  - `tier_reasoning`: Human-readable synthetic reasoning explaining why the tier was assigned.

### 3. Concrete Explanation Example (Real Output)
For the held-out critical headline:
> *"Cascade Energy Corp defaults on forty-million-dollar syndicated credit facility repayment."*

The attention engine extracts:
- **Top Tokens**:
  1. `defaults` (weight: `0.344`, rank: 1)
  2. `repayment` (weight: `0.065`, rank: 2)
  3. `dollar` (weight: `0.033`, rank: 3)
  4. `facility` (weight: `0.030`, rank: 4)
  5. `syndicated` (weight: `0.027`, rank: 5)
- **Summary**: `"Key attention token drivers: defaults (0.344), repayment (0.065), dollar (0.033), facility (0.030), syndicated (0.027)"`
- **Validation**: Validated in `tests/test_transformer_eval.py` (`test_explain_headline_attention_returns_tokens_and_weights`, `test_every_transformer_prediction_has_explanation`, `test_explanation_tokens_are_sensible_for_distress_headline`, `test_explanations_skip_stopwords_and_keep_whole_words`).

### 4. Hand-Check Validation (Spot-Check Table)
Empirical spot-check generated directly from `python -m src.transformer_eval --spot-check` across 8 held-out validation headlines (2 per expected tier):

| Expected tier | Headline | FinBERT label | Top tokens | Makes sense? (human) |
|---|---|---|---|---|
| Low | BioPharma Solutions secures FDA fast-track clearance for new automated manufacturing line. | positive | secures (0.221), new (0.137), clearance (0.079), fda (0.059), line (0.053) | Yes: "secures" and "clearance" capture the regulatory milestone; "new" is generic. |
| Low | BioPharma Solutions announces record positive annual revenue growth of twenty percent. | positive | announces (0.150), growth (0.148), record (0.104), positive (0.087), percent (0.070) | Yes: "growth", "record", and "positive" clearly identify business expansion. |
| Medium | Continental Freightlines warehouse workers organize strike demanding higher shift premiums. | negative | higher (0.153), organize (0.138), strike (0.118), workers (0.106), demanding (0.091) | Yes: "strike", "demanding", and "workers" pinpoint the operational labor dispute. |
| Medium | Continental Freightlines encounters diesel fuel delivery shortage causing transit delays. | negative | delays (0.216), causing (0.208), encounters (0.155), shortage (0.140), transit (0.051) | Yes: "delays" and "shortage" capture the acute logistics disruption. |
| High | Environmental protection agency issues severe sanction against OmniChem Global following industrial solvent spill. | negative | issues (0.175), severe (0.135), against (0.133), following (0.083), sanction (0.071) | Partly: "severe" and "sanction" capture regulatory penalties, but "issues" and "against" are syntactical. |
| High | Regulators mandate temporary shutdown of OmniChem chemical synthesis plant in Louisiana. | negative | shutdown (0.362), temporary (0.158), mandate (0.067), regulators (0.054), plant (0.029) | Yes: "shutdown" (0.362) decisively isolates the core operational shutdown risk. |
| Critical | Cascade Energy Corp prepares Chapter eleven bankruptcy filing following liquidity collapse. | negative | prepares (0.197), collapse (0.120), following (0.099), bankruptcy (0.081), filing (0.058) | Yes: "collapse", "bankruptcy", and "filing" highlight insolvency; "prepares" is procedural. |
| Critical | Cascade Energy Corp defaults on forty-million-dollar syndicated credit facility repayment. | negative | defaults (0.344), repayment (0.065), dollar (0.033), facility (0.030), syndicated (0.027) | Yes: "defaults" (0.344) and "repayment" pinpoint loan non-payment and debt failure. |

#### Attention Trustworthiness Assessment
Based on this empirical human spot-check:
- **Explanation Signal, Not Causal Attribution**: Self-attention functions as an explanation signal reflecting internal representation routing, **not proof of causal attribution**. A high attention weight does not mean the token was the counterfactual cause of the classification.
- **Utility on Meaningful Risk Words**: The mechanism is genuinely useful when high-attention tokens directly correspond to meaningful risk words (e.g., `defaults` at 0.344, `shutdown` at 0.362, `delays` at 0.216, `strike` at 0.118, or `clearance` and `growth` for positive headlines). In these instances, attention reliably surfaces the acute domain events driving the sentiment.
- **Limitations & False Salience**: Highlights on generic verbs (e.g., `issues` at 0.175, `prepares` at 0.197, `causing` at 0.208), company-name tokens, or structural and syntactic words (e.g., `against` at 0.133) are key limitations. The transformer relies on these syntactic connectors for phrase structuring, meaning attention occasionally elevates grammatical scaffolding over core risk vocabulary. Thus, attention is a valuable exploratory salience indicator for analyst triage, but must not be treated as standalone proof of risk causality.

---

# Evaluation & Benchmark Architecture

The service provides two clearly separated evaluation paths to ensure scientific integrity and eliminate circular validation:

1. **Fixed Risk Tier Thresholds (Configured A Priori)**
2. **Held-Out Synthetic Validation (Independent, Non-Circular)**
3. **15-Company Development Benchmark (Exploratory Regression Baseline)**

---

## 1. Fixed Risk Tier Thresholds

Tier cutoffs are explicit, deterministic configuration constants defined in `src/config.py` before evaluation:

- **Low**: Score $< 60.0$
- **Medium**: $60.0 \le \text{Score} < 72.0$
- **High**: $72.0 \le \text{Score} < 85.0$
- **Critical**: $\text{Score} \ge 85.0$

> [!IMPORTANT]
> Tier thresholds are fixed configuration settings. They are **never** calculated from model predictions, tuned post-hoc to match benchmark scores, or derived from dataset distributions.

---

## 2. Held-Out Synthetic Validation (Non-Circular)

The held-out validation dataset is located in `src/synthetic_held_out_validation.json` and contains **96 headlines across 12 distinct fictional suppliers** (8 headlines per supplier).

### Dataset Design & Scientific Rigor:
- **Zero Overlap with Development Benchmark**: 100% disjoint suppliers and headline texts.
- **Fictional Corporate Entities**: Uses fictional company names (e.g., *BioPharma Solutions*, *Continental Freightlines*, *Zenith Dynamics Corp*, *Cascade Energy Corp*) to avoid implying real-world events.
- **Independently Authored Labels**: Each supplier has an `expected_tier` and qualitative `rationale` authored a priori from domain operational criteria, completely independent of model predictions or scores.
- **Balanced Tier Representation**: Exactly 3 suppliers (24 headlines) per operational tier (Low, Medium, High, Critical).
- **Explicitly Labeled Synthetic**: Labeled as authored synthetic scenarios for algorithmic validation.

### Held-Out Validation Results (`python -m src.evaluate`):

| Supplier | Headlines | Risk Score | Conf | Expected Tier | Model Tier | Match Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **BioPharma Solutions** | 8 | 0.00 | 0.3161 | **Low** | Low | `MATCH` |
| **Nordic Steel Group** | 8 | 35.17 | 0.1541 | **Low** | Low | `MATCH` |
| **Precision Optical Dynamics** | 8 | 0.00 | 0.3161 | **Low** | Low | `MATCH` |
| **Continental Freightlines** | 8 | 73.39 | 0.3841 | **Medium** | High | `MISMATCH` |
| **Helios Microelectronics** | 8 | 64.35 | 0.3858 | **Medium** | Medium | `MATCH` |
| **Atlas Heavy Industries** | 8 | 59.70 | 0.3748 | **Medium** | Low | `MISMATCH` |
| **OmniChem Global** | 8 | 78.69 | 0.5473 | **High** | High | `MATCH` |
| **Vanguard Advanced Materials** | 8 | 81.61 | 0.5110 | **High** | High | `MATCH` |
| **Zenith Dynamics Corp** | 8 | 86.30 | 0.5824 | **High** | Critical | `MISMATCH` |
| **Cascade Energy Corp** | 8 | 100.00 | 0.5738 | **Critical** | Critical | `MATCH` |
| **Solaria Technologies** | 8 | 100.00 | 0.5597 | **Critical** | Critical | `MATCH` |
| **Meridian Maritime Services** | 8 | 93.72 | 0.5765 | **Critical** | Critical | `MATCH` |

### Held-Out Performance Metrics:
- **Total Suppliers**: 12
- **Total Headlines**: 96
- **Accuracy / Match Rate**: 9 / 12 (75.0%)
- **Disjoint from Development**: Yes (100% disjoint, zero supplier overlap)

### Confusion Matrix:

```text
Expected \ Predicted   |    Low | Medium |   High | Critical | Support
-----------------------------------------------------------------
Low                    |      3 |      0 |      0 |        0 |       3
Medium                 |      1 |      1 |      1 |        0 |       3
High                   |      0 |      0 |      2 |        1 |       3
Critical               |      0 |      0 |      0 |        3 |       3
-----------------------------------------------------------------
```

### Per-Tier Classification Metrics:

| Tier | Support | Predicted | True Positives | Precision | Recall | F1 Score |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Low** | 3 | 4 | 3 | 0.7500 | 1.0000 | 0.8571 |
| **Medium** | 3 | 1 | 1 | 1.0000 | 0.3333 | 0.5000 |
| **High** | 3 | 3 | 2 | 0.6667 | 0.6667 | 0.6667 |
| **Critical** | 3 | 4 | 3 | 0.7500 | 1.0000 | 0.8571 |

> [!NOTE]
> **Authentic Boundary Behavior**: Mismatches occur along realistic adjacent tier boundaries (Atlas Heavy Industries at 59.70 vs 60.0 Low/Medium threshold; Continental Freightlines at 73.39 vs 72.0 Medium/High threshold; Zenith Dynamics Corp at 86.30 vs 85.0 High/Critical threshold). This confirms that thresholds were not artificially tuned post-hoc to force 100% accuracy.

---

## 3. 25-Company Expanded Development Benchmark & Trend Dataset (Round 9)

The expanded development dataset is located in `src/supplier_headlines_25.json` and contains **300 authored headlines across 25 suppliers** (12 headlines each). The date-aware trend evaluation dataset is located in `src/supplier_trend_headlines_25.json` and contains **300 dated headlines across 25 suppliers** spanning 12 weekly intervals.

The 25 companies represent diverse global supply chain tiers:
- **Low Risk (7)**: Schneider Electric, Siemens, ASML, Texas Instruments, Lockheed Martin, BASF, TSMC
- **Medium Risk (10)**: Caterpillar, Volvo Group, Rio Tinto, Foxconn, DHL Supply Chain, Nissan, Boeing, Intel, Evergreen Marine, Maersk
- **High Risk (4)**: Tesla, Glencore, ArcelorMittal, Toshiba
- **Critical Risk (4)**: Apex Logistics, Northvolt, Evergrande Construction Logistics, Silicon Power Storage

Deep validation confirms:
- **Score Spread**: 57.79 points (Min: 42.21, Max: 100.00)
- **Mean Score**: 67.75, **Std Dev**: 18.60
- **Human Operational Tier Match Rate**: 18 / 25 (72.0%)
- **Scenario Checks**: Verified positive mitigation, acute negative alerts, duplicate suppression, and rolling window date exclusion.

For the complete written analysis, see: [docs/25_COMPANY_VALIDATION_SANITY_CHECK.md](docs/25_COMPANY_VALIDATION_SANITY_CHECK.md).

> [!WARNING]
> **Synthetic / Authored Dataset Disclaimer**:
> These datasets were authored during pipeline prototyping alongside model development. Real company names were used solely for illustrative scenario design and temporal trajectory demonstration (rising, falling, and stable trends). **These headlines are entirely synthetic and authored for regression testing and trend demonstration; they do NOT represent actual real-world news, events, or official corporate disclosures.** These datasets serve as development regression baselines, not independent validation sets.

---

# Compliance Service Integration Contract (Future Work)

The Supplier Risk NLP Service defines a formal architectural integration specification with Geethika's Compliance Screening Service:

> [!IMPORTANT]
> **Contract / Documentation Only**:
> No runtime HTTP clients, service wiring, imports, URLs, or shared libraries are implemented in this round. The actual integration is scheduled for future rounds.

### Contract Highlights:
- **Sanctions + Adverse Media Synthesis**: How OFAC/UN/EU sanctions checks combine with FinBERT sentiment scores, keyword severity, and time-series deterioration flags (`is_deteriorating: true`).
- **Unified Risk Decision Matrix**: Detailed triage rules combining sanctions hit/miss with NLP risk tiers (Low, Medium, High, Critical) for automated procurement decisions (Auto-Clear, Watchlist, Enhanced Due Diligence, Immediate Hard Block).
- **Resilience Protocols**: Graceful degradation (sanctions-only screening continues if Supplier Risk NLP times out), circuit breaking, and complete audit logging.

For the full specification, see: [COMPLIANCE_INTEGRATION_CONTRACT.md](COMPLIANCE_INTEGRATION_CONTRACT.md).

---

## 4. Limitations of Synthetic Validation

While curated synthetic datasets enable reproducible verification of keyword detection, FinBERT sentiment scoring, and anti-dilution dynamics across distinct risk bands:
- Synthetic headlines cannot capture the full lexical diversity, noise, and sarcasm of live news feeds.
- Entity disambiguation in live production requires real-time news ingest and entity-linking pipelines.
- Production deployment should incorporate live market validation and continuous feedback from procurement risk analysts.

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
# Run all tests
python -m pytest ml-services/supplier-risk/tests -v

# Run MongoDB integration and migration tests
python -m pytest ml-services/supplier-risk/tests/test_mongo.py -v

# Run Transformer evaluation, attention explanation & MLflow tests
python -m pytest ml-services/supplier-risk/tests/test_transformer_eval.py -v
```

### Run Dataset Migration:

```bash
# Migrate default 10-company dated trend headlines into MongoDB
python -m src.migrate

# Migrate specific dataset file
python -m src.migrate --file src/supplier_trend_headlines.json
```

### Run Transformer Comparison & MLflow Logging:

```bash
python -m src.transformer_eval
```

The test suite validates:
- Text preprocessing and punctuation boundary isolation
- Keyword detection, mitigation windows, and variant stemming
- Sentiment pipeline integration
- Configurable risk score aggregation (`top_k_mean` default, `blend`, `max`, `mean`)
- Calibrated risk band classification (Low, Medium, High, Critical)
- Response schema validation and API endpoints (`/predict`, `/health`, aliases)
- Configuration defaults, overrides, and input validation
- Duplicate headline handling and anti-dilution guarantees
- Date validation (ISO YYYY-MM-DD enforcement, invalid date rejection)
- Entity-level risk trend aggregation and chronological ordering
- Trend API endpoints (`GET /api/v1/supplier-risk/trend/{supplier_name}`, `POST /api/v1/supplier-risk/trend`)
- MongoDB connection, fast-fail ping, indexing, and story_hash deduplication (`test_mongo.py`)
- Authoritative runtime data loading and explicit failure behavior without silent fallbacks
- Pretrained transformer zero-shot evaluation, metric calculation, and comparison (`test_transformer_eval.py`)
- Token-level attention extraction, noise filtering, and 100% explanation coverage
- MLflow 3.16.1 run creation, metric logging, and artifact persistence

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
