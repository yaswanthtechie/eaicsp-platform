# Implementation Plan - Milestone 3: Served Config-Driven Weights & 15-Company Benchmark Validation (Revised)

> [!IMPORTANT]
> **Status**: REVISED PLAN ONLY for user review. Implementation has NOT started.
> No code, configuration, or dataset modifications will take place until user review and explicit approval.

---

## A. Current Architecture Understanding

The Supplier Risk service is an independent FastAPI microservice running on Python 3.11+ that evaluates supplier news headlines without external database dependencies, external APIs, or inter-service business couplings.

The service architecture consists of:
1. **Model Lifespan (`src/analyze.py`)**: Automatic startup initialization of Hugging Face FinBERT (`ProsusAI/finbert`) for domain financial sentiment inference.
2. **Text Normalization (`src/preprocess.py`)**: Lowercasing, punctuation boundary isolation, whitespace normalization.
3. **Signal Detection (`src/signals.py`)**: Keyword matching with mitigation windows and variant inflections covering Financial, Operational, and Reputational risks.
4. **Scoring Engine (`src/predict.py`)**: Integrates FinBERT sentiment penalties and detected keyword signal weights with anti-dilution aggregation (`top_k_mean`, `max`, `blend`, `mean`) and mathematical confidence saturation (`_calculate_confidence`).
5. **Time-Series Trend Engine (`src/trend.py`)**: Date validation (`validate_date`), entity-level date-grouped prediction (`calculate_supplier_trend`), per-date evidence explanation, timeline top evidence, and exponential recency decay (`calculate_recency_weighted_confidence`).
6. **Configuration Management (`src/config.py`)**: Centralized `Settings` class with defaults, validation helpers, and environment variable overrides (`SIGNAL_WEIGHTS_JSON`, `NEGATIVE_SENTIMENT_PENALTY`, `RECENCY_HALF_LIFE_DAYS`, etc.).
7. **Current Baseline**: **90 passed, 2 deselected, 1 warning** via `pytest -q`.

---

## B. Existing Scoring and Weight Flow

Configuration is **strictly server-side** and config-driven. The scoring and weight configuration flows through the service as follows:

```text
.env / OS Environment Variables
  (e.g., SIGNAL_WEIGHTS_JSON, NEGATIVE_SENTIMENT_PENALTY, RECENCY_HALF_LIFE_DAYS, AGGREGATION_STRATEGY)
        ↓
src/config.py: Settings() & get_settings() (cached singleton)
  - Validates weights via validate_numeric_weight() & validate_signal_weights()
  - Falls back to DEFAULT_SIGNAL_WEIGHTS (18 calibrated keywords) if not overridden
        ↓
src/predict.py: predict(supplier_name, headlines, config=cfg)
  - cfg defaults to get_settings()
  - Headline Scoring: headline_score = sentiment_penalty + sum(signal_weights)
  - Risk Aggregation: _aggregate_risk_score(scores, config=cfg) (default: top_k_mean, K=3)
  - Evidence Confidence: _calculate_confidence(processed_headlines, divisor=cfg.confidence_divisor)
        ↓
src/trend.py: calculate_supplier_trend(supplier_name, records, config=cfg)
  - Date-grouped predict(supplier_name, headlines_for_date, config=cfg)
  - Recency Confidence: calculate_recency_weighted_confidence(risk_trend, half_life_days=cfg.recency_half_life_days)
  - Timeline Top Evidence: extracted & ranked descending across all dates
        ↓
src/analyze.py: FastAPI Endpoints
  - GET /api/v1/supplier-risk/config  <-- Exposes active server configuration
  - POST /predict (and aliases /api/v1/supplier-risk/predict, /api/v1/supplier-risk/analyze)
  - GET /api/v1/supplier-risk/trend/{supplier_name}
  - POST /api/v1/supplier-risk/trend
        ↓
Client HTTP Response (JSON)
```

> [!NOTE]
> Per user constraint, **no per-request custom scoring overrides** (such as `custom_signal_weights` or `custom_negative_penalty`) will be added to request bodies. Configuration remains purely server-side via environment variables and `Settings`.

---

## C. Files That Need Modification

1. **[`src/config.py`](file:///c:/Users/lenovo/Desktop/eaicsp-platform/ml-services/supplier-risk/src/config.py)**:
   - Add a `to_dict()` serialization method on `Settings` to export the currently active parameters and weights cleanly for the `/config` endpoint.
2. **[`src/data.py`](file:///c:/Users/lenovo/Desktop/eaicsp-platform/ml-services/supplier-risk/src/data.py)**:
   - Add `load_15_company_dataset()` and `load_15_company_trend_dataset()` to load the extended 15-company benchmark files.
   - Keep existing `load_headlines()` and `load_trend_headlines()` **strictly unchanged** to protect all existing 10-company tests.
3. **[`src/analyze.py`](file:///c:/Users/lenovo/Desktop/eaicsp-platform/ml-services/supplier-risk/src/analyze.py)**:
   - Add the `GET /api/v1/supplier-risk/config` endpoint exposing active serving configuration.
   - Keep `AnalyzeRequest` and `TrendAnalysisRequest` schemas strictly unchanged (no per-request overrides).
4. **[`src/evaluate.py`](file:///c:/Users/lenovo/Desktop/eaicsp-platform/ml-services/supplier-risk/src/evaluate.py)**:
   - Update evaluation script to evaluate the 15-company benchmark dataset directly using scoring functions (independent of FastAPI HTTP serving).
   - Print individual supplier risk evaluations, human match determinations, and distribution metrics (min, max, spread, standard deviation, tier distribution).
5. **[`README.md`](file:///c:/Users/lenovo/Desktop/eaicsp-platform/ml-services/supplier-risk/README.md)**:
   - Document the new `GET /api/v1/supplier-risk/config` endpoint.
   - Document the 15-company benchmark results and distribution analysis.

---

## D. New Files That Need to Be Created

1. **[`src/supplier_headlines_15.json`](file:///c:/Users/lenovo/Desktop/eaicsp-platform/ml-services/supplier-risk/src/supplier_headlines_15.json)**:
   - Exactly 15 companies, 180 headlines (12 headlines per supplier).
   - Retains all 120 original headlines for the first 10 suppliers, and adds 60 realistic headlines for 5 new diverse suppliers.
2. **[`src/supplier_trend_headlines_15.json`](file:///c:/Users/lenovo/Desktop/eaicsp-platform/ml-services/supplier-risk/src/supplier_trend_headlines_15.json)**:
   - Date-aware version of the 15-company dataset with deterministic ISO `YYYY-MM-DD` dates across Jan–Mar 2026.
3. **[`tests/test_milestone3_config_and_validation.py`](file:///c:/Users/lenovo/Desktop/eaicsp-platform/ml-services/supplier-risk/tests/test_milestone3_config_and_validation.py)**:
   - Dedicated test suite for served configuration, weight validation, 15-company distribution, human sanity-check matching, and failure paths.

---

## E. Exact Data-Model Changes

### New Model: `ConfigResponse` (`src/analyze.py`)
```python
class ConfigResponse(BaseModel):
    negative_sentiment_penalty: float
    neutral_sentiment_penalty: float
    positive_sentiment_penalty: float
    max_risk_score: float
    confidence_divisor: float
    aggregation_strategy: str
    aggregation_top_k: int
    recency_half_life_days: float
    signal_weights: Dict[str, int]
```

### Request Models: Strictly Unchanged
- `AnalyzeRequest` / `PredictRequest`: retains `{ "supplier_name": str, "headlines": List[str] }`.
- `TrendAnalysisRequest`: retains `{ "supplier_name": str, "articles": List[TrendArticleInput] }`.

---

## F. Configuration Design

1. **Environment Variables**:
   - `SIGNAL_WEIGHTS_JSON`: JSON string override for keyword weights (e.g. `{"strike": 40, "bankruptcy": 60}`).
   - `NEGATIVE_SENTIMENT_PENALTY`: Float penalty for negative sentiment (default: `40.0`).
   - `NEUTRAL_SENTIMENT_PENALTY`: Float penalty for neutral sentiment (default: `0.0`).
   - `POSITIVE_SENTIMENT_PENALTY`: Float penalty for positive sentiment (default: `0.0`).
   - `MAX_RISK_SCORE`: Maximum risk score cap (default: `100.0`).
   - `CONFIDENCE_DIVISOR`: Saturation divisor in confidence calculation (default: `8.0`).
   - `RECENCY_HALF_LIFE_DAYS`: Float half-life for trend confidence decay (default: `30.0`).
   - `AGGREGATION_STRATEGY`: Strategy name (`top_k_mean`, `max`, `blend`, `mean`).
   - `AGGREGATION_TOP_K`: Integer K for top-K averaging (default: `3`).
2. **Validation Rules**:
   - Weights must be positive numbers; negative weights or non-numeric values immediately raise `ValueError`.
   - Empty keyword names raise `ValueError`.
   - Malformed `SIGNAL_WEIGHTS_JSON` raises `ValueError` with clear diagnostics.
3. **Serving Integration**:
   - `GET /api/v1/supplier-risk/config` returns `ConfigResponse` representing the active `get_settings()` instance.

---

## G. API Changes

| Endpoint | Method | Status | Description |
| :--- | :--- | :--- | :--- |
| `/api/v1/supplier-risk/config` | `GET` | **NEW** | Exposes currently active signal weights and scoring thresholds. |
| `/predict` | `POST` | Preserved | Request and response contracts strictly unchanged. |
| `/api/v1/supplier-risk/predict` | `POST` | Preserved | Gateway alias for `/predict`. |
| `/api/v1/supplier-risk/analyze` | `POST` | Preserved | Legacy alias for `/predict`. |
| `/api/v1/supplier-risk/trend/{supplier_name}` | `GET` | Preserved | Returns risk trend, `overall_confidence`, `top_evidence`. |
| `/api/v1/supplier-risk/trend` | `POST` | Preserved | Dynamic trend calculation; request and response contracts unchanged. |
| `/health` | `GET` | Preserved | Returns `{"status": "UP", "service": "supplier-risk"}`. |

---

## H. 15-Company Validation Design

The dataset will contain **15 global companies** (12 headlines per supplier, 180 headlines total) representing critical global manufacturing, logistics, tech, energy, and defense supply chains:

### Original 10 Suppliers
1. **Boeing** (Aerospace & Defense) — Labor strike, safety recalls, FAA investigations, deliveries.
2. **Intel** (Semiconductors) — $20B fab expansion, 15% layoff, EU antitrust probe, material shortage.
3. **Tesla** (EV & Clean Energy) — 2M vehicle recall, investor lawsuit, delivery drop, layoffs.
4. **Nissan** (Automotive) — Cost restructuring, 1M recall, supply disruption, executive lawsuit.
5. **Foxconn** (Electronics Manufacturing) — iPhone plant disruption, labor strike, India expansion.
6. **TSMC** (Semiconductor Foundry) — Record AI revenue, earthquake shutdown, power outage.
7. **Maersk** (Maritime Logistics) — Red Sea delays, cyberattack, canal grounding, green ships.
8. **BASF** (Chemicals) — Force majeure explosion, emissions scrutiny, restructuring/layoffs.
9. **Siemens** (Industrial Automation) — Smart grid contracts, order backlog, gas turbines.
10. **Apex Logistics** (Freight & Supply Chain) — Ransomware attack, debt default, bankruptcy filing.

### 5 New Suppliers & Inclusion Rationale
11. **ASML** (Photolithography / Semiconductor Equipment):
    - *Why Included*: Monopoly single-point-of-failure in global semiconductor supply chain.
    - *Profile*: Strong financial fundamentals, but exposed to trade export sanctions and equipment shipment delays.
    - *Expected Risk Tier*: **Low-Medium Risk** (20.0 - 30.0).
12. **Glencore** (Mining & Industrial Commodities):
    - *Why Included*: Upstream raw-materials supplier essential for metals, battery materials, and energy.
    - *Profile*: High commodity earnings offset by environmental sanctions, mining strike walkouts, and regulatory fraud/bribery probes.
    - *Expected Risk Tier*: **High Risk** (36.0 - 45.0).
13. **Lockheed Martin** (Defense & Aerospace Prime):
    - *Why Included*: Critical defense contractor subject to defense audit scrutiny, specialized circuit component shortages, and delivery milestones.
    - *Profile*: Ultra-stable sovereign backing, zero bankruptcy risk, but moderate operational and supply delays.
    - *Expected Risk Tier*: **Low-Medium Risk** (22.0 - 32.0).
14. **Evergreen Marine** (Container Shipping & Logistics):
    - *Why Included*: Direct maritime counterpart to Maersk, providing comparative logistics risk calibration.
    - *Profile*: Vessel groundings, port congestion delays, crew disputes, but strong fleet modernization.
    - *Expected Risk Tier*: **Medium-High Risk** (30.0 - 40.0).
15. **Northvolt** (European Battery Cell Manufacturing):
    - *Why Included*: High-distress capital-intensive green tech supplier facing liquidity crisis, customer contract cancellations, factory halts, and layoffs.
    - *Profile*: Acute distress trajectory, testing pre-insolvency crisis detection.
    - *Expected Risk Tier*: **Critical Risk** (50.0 - 75.0).

---

## I. Human Sanity-Check Methodology

### Objectivity & Independence Guarantee
- Human evaluation criteria are formulated **directly from the actual factual events described in the 12 headlines** for each supplier.
- The model will run against the **existing scoring configuration** (no weight tweaking or headline manipulation to force arbitrary matches).
- Output will honestly report **MATCH** or **MISMATCH** for every supplier based on whether the model score lands inside the expected tier.

### Reporting Structure per Company
For every company in the benchmark:
- **Supplier**: Company name
- **Number of headlines**: Total articles analyzed (12)
- **Risk score**: Final calculated score (0.0 - 100.0)
- **Confidence**: Evidence confidence (0.0 - 1.0)
- **Top signals**: Key detected risk keywords and weights
- **Human expected tier**: Human-assigned operational band (Low, Medium, High, Critical)
- **Model tier**: Assigned band based on score:
  - Low: $0.0 - 25.0$
  - Medium: $25.1 - 35.0$
  - High: $35.1 - 45.0$
  - Critical: $45.1 - 100.0$
- **MATCH / MISMATCH**: Objective comparison result
- **Reason**: Factual justification explaining the match or variance

### Benchmark Reference Table

| # | Supplier | Sector | Factual Headline Profile | Expected Human Tier | Expected Score Range |
| :---: | :--- | :--- | :--- | :---: | :---: |
| 1 | **Siemens** | Automation | Solid revenue, smart grid deals, minor delays | **Low** | 0.0 - 25.0 |
| 2 | **BASF** | Chemicals | Sustainable materials, force majeure, layoffs | **Low** | 0.0 - 25.0 |
| 3 | **TSMC** | Semi Foundry | AI chip demand, temporary earthquake shutdown | **Low-Medium** | 15.0 - 30.0 |
| 4 | **Lockheed Martin** | Defense | Multi-billion awards, parts delays, shortage | **Low-Medium** | 20.0 - 32.0 |
| 5 | **ASML** | Semi Equipment | EUV bookings, export sanctions, shipment delay | **Medium** | 22.0 - 34.0 |
| 6 | **Foxconn** | Electronics | India expansion, strike, component shortage | **Medium** | 25.1 - 35.0 |
| 7 | **Maersk** | Logistics | Green ships, Red Sea crisis delays, cyberattack | **Medium** | 25.1 - 35.0 |
| 8 | **Intel** | Semiconductors | Ohio fab expansion, 15% layoff, antitrust probe | **Medium** | 28.0 - 38.0 |
| 9 | **Boeing** | Aerospace | New aircraft deliveries, strike, lawsuit, FAA probe | **Medium-High** | 30.0 - 40.0 |
| 10 | **Evergreen Marine**| Logistics | Vessel grounding, canal delays, port congestion | **Medium-High** | 30.0 - 42.0 |
| 11 | **Nissan** | Automotive | EV partnership, 1M recall, supply disruption | **High** | 35.1 - 45.0 |
| 12 | **Glencore** | Commodities | Raw materials expansion, bribery probe, strike | **High** | 35.1 - 48.0 |
| 13 | **Tesla** | EV / Clean Tech | Record sales, 2M vehicle recall, autopilot lawsuit | **High** | 35.1 - 48.0 |
| 14 | **Northvolt** | Clean Tech | Contract cancellations, cash crisis, factory halt | **Critical** | 45.1 - 75.0 |
| 15 | **Apex Logistics** | Freight | Debt default, ransomware, strike, bankruptcy | **Critical** | 45.1 - 100.0 |

---

## J. Benchmark / Distribution Methodology

The existing scoring parameters will be executed directly. The resulting distribution will be analyzed across standard statistical criteria:

1. **Score Spread**:
   $$\text{Spread} = \max(\text{scores}) - \min(\text{scores})$$
   Target: Spread $\ge 50.0$ points to ensure broad operational dynamic range.
2. **Standard Deviation**:
   $$\sigma_{\text{scores}} = \sqrt{\frac{1}{15}\sum_{i=1}^{15} (s_i - \bar{s})^2}$$
   Target: $\sigma \ge 12.0$ points to avoid clustering or score compression.
3. **Four-Tier Distribution**:
   Evaluate representation across all 4 calibrated operational risk tiers:
   - Low: $\le 25.0$
   - Medium: $25.1 - 35.0$
   - High: $35.1 - 45.0$
   - Critical: $> 45.0$
4. **Monotonic Severity Check**:
   Confirm that operationally stable suppliers score strictly lower than distressed suppliers.
5. **Reporting**:
   If the actual distribution falls short of any target under existing weights, the evaluation will **honestly report the variance and explain why**, without silently tuning weights to artificially force statistical targets.

---

## K. Failure-Path Test Plan

The new test suite [`tests/test_milestone3_config_and_validation.py`](file:///c:/Users/lenovo/Desktop/eaicsp-platform/ml-services/supplier-risk/tests/test_milestone3_config_and_validation.py) will cover:

1. **Configuration Failure Paths**:
   - `Settings(signal_weights={"strike": -10})` raises `ValueError` (negative weight).
   - `Settings(signal_weights={"strike": "high"})` raises `ValueError` (non-numeric).
   - `Settings(signal_weights={"": 20})` raises `ValueError` (empty keyword).
   - `Settings(max_risk_score=-5.0)` raises `ValueError`.
   - `Settings(confidence_divisor=0)` raises `ValueError`.
   - `Settings(aggregation_strategy="unsupported")` raises `ValueError`.
   - `Settings(aggregation_top_k=0)` raises `ValueError`.
   - `Settings(recency_half_life_days=-1.0)` raises `ValueError`.
   - Malformed `SIGNAL_WEIGHTS_JSON` environment variable raises `ValueError`.
2. **Serving & API Failure Paths**:
   - `GET /api/v1/supplier-risk/config` returns 200 with all parameters and weights dictionary.
   - `POST /predict` with blank/whitespace supplier returns 422.
   - `POST /predict` with empty headlines returns score 0.0, confidence 0.0, empty signals.
   - `POST /predict` with missing payload returns 422.
3. **15-Company Validation Tests**:
   - Dataset file integrity: exactly 15 suppliers, exactly 12 headlines each, 180 records total.
   - Batch evaluation executes without errors.
   - Honest assertion of human sanity-check matches.
4. **Backward Compatibility Tests**:
   - All 90 existing tests across `test_predict.py`, `test_api.py`, `test_trend.py`, and `test_evidence_confidence.py` continue to pass.

---

## L. Backward-Compatibility Strategy

1. **Dedicated Dataset File**: Create `supplier_headlines_15.json` and keep `supplier_headlines.json` (10 companies, 120 headlines) untouched so that existing tests in `test_predict.py` never break.
2. **No Request Body Mutation**: Existing request models retain their exact structure without custom override fields.
3. **Additive Config Endpoint**: `GET /api/v1/supplier-risk/config` is purely additive.

---

## M. Expected Test Count & Results

- Current tests passing: **90**
- Deselected (slow): **2**
- Warnings: **1** (Starlette testclient deprecation)
- New Milestone 3 tests to add: **16 - 18 tests**
- Expected post-implementation result: **106 - 108 passed, 2 deselected, 1 warning, 0 failures**.

---

## N. Runtime Verification Commands

```powershell
# 1. Run all unit & integration tests
.\.venv\Scripts\pytest -q

# 2. Run dedicated Milestone 3 suite
.\.venv\Scripts\pytest tests\test_milestone3_config_and_validation.py -q

# 3. Query the served config endpoint
Invoke-RestMethod http://127.0.0.1:8006/api/v1/supplier-risk/config | ConvertTo-Json -Depth 5

# 4. Verify existing /predict backward compatibility
$body = @{ supplier_name = "Tesla"; headlines = @("Tesla recalls 2 million vehicles") } | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:8006/predict" -Method POST -ContentType "application/json" -Body $body | ConvertTo-Json -Depth 5

# 5. Run independent 15-company batch evaluation script
.\.venv\Scripts\python -m src.evaluate
```

---

## O. Risks and Possible Regression Points

| Risk | Mitigation |
| :--- | :--- |
| Modifying `supplier_headlines.json` breaks existing 10-company assertions in `test_predict.py`. | Keep `supplier_headlines.json` intact. Put 15 companies in `supplier_headlines_15.json`. |
| Environment variable override tests mutate global settings state. | Use `get_settings.cache_clear()` in test teardown fixtures. |
| Evaluation script coupling to FastAPI server. | Keep `evaluate.py` independent, calling `predict()` directly. |

---

## P. Explicit List of Files / Functions That Should NOT Be Changed

1. **[`src/predict.py`](file:///c:/Users/lenovo/Desktop/eaicsp-platform/ml-services/supplier-risk/src/predict.py)**:
   - `predict()`: scoring calculation, sentiment penalties, signal detection.
   - `_calculate_confidence()`: evidence volume saturation, agreement, dispersion.
   - `_aggregate_risk_score()`: `top_k_mean`, `max`, `blend`, `mean` anti-dilution.
2. **[`src/signals.py`](file:///c:/Users/lenovo/Desktop/eaicsp-platform/ml-services/supplier-risk/src/signals.py)**:
   - `detect_signals()`: regex matching and mitigation windows.
3. **[`src/sentiment.py`](file:///c:/Users/lenovo/Desktop/eaicsp-platform/ml-services/supplier-risk/src/sentiment.py)**:
   - `analyze_sentiment()`: FinBERT model inference.
4. **[`src/preprocess.py`](file:///c:/Users/lenovo/Desktop/eaicsp-platform/ml-services/supplier-risk/src/preprocess.py)**:
   - `clean_text()`: text normalization and cleaning.
5. **[`src/supplier_headlines.json`](file:///c:/Users/lenovo/Desktop/eaicsp-platform/ml-services/supplier-risk/src/supplier_headlines.json)**:
   - Untouched 10-company calibration dataset.
6. **[`src/supplier_trend_headlines.json`](file:///c:/Users/lenovo/Desktop/eaicsp-platform/ml-services/supplier-risk/src/supplier_trend_headlines.json)**:
   - Untouched 10-company trend dataset.
7. **Existing Test Files**:
   - `tests/test_predict.py`
   - `tests/test_api.py`
   - `tests/test_trend.py`
   - `tests/test_evidence_confidence.py`
