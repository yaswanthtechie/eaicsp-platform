# Walkthrough - Milestone 3: Config-Driven Weights & Benchmark Validation

## Overview
Successfully implemented **Milestone 3: Served Config-Driven Weights, Benchmark Expansion, and Honest Human Sanity Validation** for the Supplier Risk NLP microservice.

All 10 user constraints were strictly honored:
1. **Server-Side Config**: Scoring parameters are strictly config-driven via `Settings` and environment variables. No per-request custom scoring overrides were added to `/predict` or `/trend`.
2. **Additive Inspection Endpoint**: Implemented `GET /api/v1/supplier-risk/config` exposing model name, sentiment penalties, aggregation strategy, recency half-life, and keyword weights.
3. **Honest Benchmark Reporting**: Did not force 15/15 human matches or manipulate weights/datasets. Real model outputs are audited and reported with clear `MATCH` / `MISMATCH` statuses and reasons.
4. **Unmodified Weights**: Did not alter weights merely to satisfy arbitrary spread (>= 50) or standard deviation (>= 12) targets. The actual distribution is reported along with root-cause analysis.
5. **Factual Grounding**: Human expectations are grounded directly in the 12 actual headlines per company.
6. **Granular Reporting**: Every company report includes Supplier, Headline Count, Risk Score, Confidence, Top Signals, Human Expected Tier, Model Tier, Match Status, and Reason.
7. **Independent Standalone Evaluation**: `src/evaluate.py` directly uses `predict()` without requiring the FastAPI HTTP daemon to be running.
8. **Dataset Preservation**: The 10-company dataset (`supplier_headlines.json`) and all 90 existing tests remain intact.
9. **Algorithm Preservation**: No modifications to `predict()`, `_calculate_confidence()`, `_aggregate_risk_score()`, `detect_signals()`, `analyze_sentiment()`, or `clean_text()`.
10. **Zero Regressions**: Total test count expanded from 90 to 108 tests; 108 passed, 0 failed.

---

## Key Changes Implemented

### 1. Configuration Layer & Inspection Endpoint
- **[`src/config.py`](file:///c:/Users/lenovo/Desktop/eaicsp-platform/ml-services/supplier-risk/src/config.py)**:
  - Added `to_dict()` helper method on `Settings` for JSON serialization.
  - Centralized validation rules for numeric weights, dictionary structures, aggregation strategies, and positive divisors.
- **[`src/analyze.py`](file:///c:/Users/lenovo/Desktop/eaicsp-platform/ml-services/supplier-risk/src/analyze.py)**:
  - Added Pydantic model `ConfigResponse`.
  - Added endpoint `GET /api/v1/supplier-risk/config` returning the active configuration.
  - Preserved `/predict`, `/trend`, and `/health` response schemas without modifications.

### 2. 15-Company Benchmark Datasets
- **[`src/supplier_headlines_15.json`](file:///c:/Users/lenovo/Desktop/eaicsp-platform/ml-services/supplier-risk/src/supplier_headlines_15.json)**:
  - Preserves all 10 original suppliers (120 headlines) and adds 5 new global suppliers across strategic industry sectors (60 new headlines, total 180):
    1. *ASML* (Semiconductor Lithography) — 8 Pos, 1 Neu, 3 Neg
    2. *Glencore* (Natural Resources & Mining) — 2 Pos, 0 Neu, 10 Neg
    3. *Lockheed Martin* (Defense Prime) — 6 Pos, 2 Neu, 4 Neg
    4. *Evergreen Marine* (Maritime Freight) — 3 Pos, 0 Neu, 9 Neg
    5. *Northvolt* (EV Battery Cells) — 1 Pos, 0 Neu, 11 Neg
- **[`src/supplier_trend_headlines_15.json`](file:///c:/Users/lenovo/Desktop/eaicsp-platform/ml-services/supplier-risk/src/supplier_trend_headlines_15.json)**:
  - Deterministic ISO `YYYY-MM-DD` date mappings for all 180 headlines across Jan–Mar 2026.
- **[`src/data.py`](file:///c:/Users/lenovo/Desktop/eaicsp-platform/ml-services/supplier-risk/src/data.py)**:
  - Added `load_15_company_dataset()` and `load_15_company_trend_dataset()`.

### 3. Standalone Benchmark Evaluation & Audit Engine
- **[`src/evaluate.py`](file:///c:/Users/lenovo/Desktop/eaicsp-platform/ml-services/supplier-risk/src/evaluate.py)**:
  - Grounded `HUMAN_BENCHMARK_EXPECTATIONS` derived from factual headline text.
  - Calibrated operational 4-tier reporting categorization (`assign_risk_tier`): Low (<60.0), Medium (60.0–71.99), High (72.0–84.99), Critical (>=85.0).
  - Standalone execution (`evaluate_dataset()` and `run_evaluation()`) independent from FastAPI.
  - Granular reporting per company with honest `MATCH` / `MISMATCH` verification and root-cause analysis.

### 4. Comprehensive Test Suite
- **[`tests/test_milestone3_config_and_validation.py`](file:///c:/Users/lenovo/Desktop/eaicsp-platform/ml-services/supplier-risk/tests/test_milestone3_config_and_validation.py)**:
  - Added 18 automated tests:
    - Endpoint schema inspection (`GET /api/v1/supplier-risk/config`)
    - Server-side config verification (`POST /predict` without request overrides)
    - Configuration validation failure paths (negative weights, non-numeric values, boolean weights, disallow zero, non-dict signals, empty signal keys, invalid aggregation strategies, invalid top-k, malformed JSON env vars)
    - 15-company dataset integrity (15 suppliers, 12 headlines each, 180 total records)
    - 15-company trend dataset integrity (valid ISO dates)
    - Calibrated 4-tier operational reporting categorization thresholds
    - Evaluation structure and report generation
    - Baseline 10-company dataset preservation

---

## Benchmark Evaluation Results (Option 3 Calibrated Reporting)

Running `python -m src.evaluate` outputs:

| Supplier | Headlines | Risk Score | Conf | Top Signals | Human Expected Tier | Model Tier | Match Status |
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

### Statistical Distribution Analysis & Explanation
- **Total Evaluated**: 15 suppliers
- **Human Matches**: 12 / 15 (80.0%)
- **Min Score**: 56.33 (Siemens)
- **Max Score**: 100.00 (Apex Logistics)
- **Score Spread**: 43.67 *(Target >= 50.0: BELOW TARGET)*
- **Mean Score**: 69.25
- **Standard Deviation**: 11.93 *(Target >= 12.0: BELOW TARGET)*
- **Tier Distribution (All 4 Tiers Populated)**:
  - Low: 3 suppliers (Siemens, ASML, Lockheed Martin)
  - Medium: 9 suppliers (BASF, Foxconn, Nissan, TSMC, Boeing, Evergreen Marine, Maersk, Tesla, Intel)
  - High: 1 supplier (Glencore)
  - Critical: 2 suppliers (Northvolt, Apex Logistics)
- **Root Cause & Benchmark Analysis**:
  Under Option 3 reporting thresholds (Low <60, Med 60–72, High 72–85, Critical >=85), the natural score distribution cleanly populates all 4 operational tiers and achieves an 80.0% match rate against human expectations without modifying underlying scoring weights.

---

## Test Verification Summary

```bash
.\.venv\Scripts\pytest -q
```
**Results**:
- Baseline suite: 90 passed
- Milestone 3 suite: 18 passed
- **Total: 108 passed, 2 deselected (slow integration benchmarks), 1 warning in 34.30s**
- **0 failures, zero regressions**

Live API Verification on port 8006:
- `GET /health` -> 200 OK (`{"status": "UP", "service": "supplier-risk"}`)
- `GET /api/v1/supplier-risk/config` -> 200 OK (Model, penalties, aggregation strategy, recency half-life, signal weights)
- `POST /predict` -> 200 OK (risk score, confidence, signals, top_worst_3)
- `POST /api/v1/supplier-risk/predict` -> 200 OK (Gateway alias verified)
- `GET /api/v1/supplier-risk/trend/{supplier_name}` -> 200 OK (`risk_trend`, `overall_confidence`, `top_evidence`)
- `POST /api/v1/supplier-risk/trend` -> 200 OK (Dynamic multi-article trend scoring)
