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
| **Volume Weight**      | `VOLUME_WEIGHT` | `0.15` | Repeated risk coverage amplification factor under `top_k_mean` |
| **Mitigation Weight**  | `MITIGATION_WEIGHT` | `0.35` | Mitigating positive coverage discount factor under `top_k_mean` |
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
