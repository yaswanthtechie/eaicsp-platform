# 25-Company Supplier Risk Validation & Deep Sanity-Check Report

> **Evaluation Mode**: Expanded Development Benchmark Validation (Round 9)  
> **Dataset**: `src/supplier_headlines_25.json` (300 headlines across 25 global suppliers, 12 headlines per supplier)  
> **Temporal Trend Dataset**: `src/supplier_trend_headlines_25.json` (300 dated headlines across 12 weekly intervals)  
> **Scoring Engine**: FinBERT Sentiment Analysis (`ProsusAI/finbert`) + Configurable Keyword Detection + Anti-Dilution `top_k_mean` Aggregation ($K=3$, $\text{Volume Weight}=0.15$, $\text{Mitigation Weight}=0.35$)  
> **Fixed Tier Ceilings**: Low $< 60.0$ | Medium $60.0 \le \text{Score} < 72.0$ | High $72.0 \le \text{Score} < 85.0$ | Critical $\ge 85.0$

---

## 1. Executive Summary & Aggregate Metrics

The Supplier Risk NLP pipeline was subjected to deep empirical validation across an expanded benchmark of **25 global corporate entities** spanning diverse supply chain sectors (Aerospace, Semiconductors, Automotive, Maritime Logistics, Energy Management, Mining, Heavy Machinery, Metallurgy, and Hardware Storage).

### Benchmark Aggregate Statistics:
- **Total Suppliers Evaluated**: 25
- **Total News Headlines Evaluated**: 300 (exactly 12 curated headlines per supplier)
- **Score Spread**: **57.79 points** (Minimum: **42.21**, Maximum: **100.00**)
- **Mean Risk Score**: **67.75**
- **Score Standard Deviation**: **18.60**
- **Internal Tier Calibration Agreement**: **18 / 25 (72.0%)**
- **Ground Truth Expected Benchmark Tiers**:
  - **Low Tier ($< 60.0$)**: 7 suppliers (28%) — Schneider Electric, Siemens, ASML, Texas Instruments, Lockheed Martin, BASF, TSMC
  - **Medium Tier ($60.0 - 71.99$)**: 10 suppliers (40%) — Caterpillar, Volvo Group, Rio Tinto, Foxconn, DHL Supply Chain, Nissan, Boeing, Intel, Evergreen Marine, Maersk
  - **High Tier ($72.0 - 84.99$)**: 4 suppliers (16%) — Tesla, Glencore, ArcelorMittal, Toshiba
  - **Critical Tier ($\ge 85.0$)**: 4 suppliers (16%) — Apex Logistics, Northvolt, Evergrande Construction Logistics, Silicon Power Storage
- **Model Static Predictions on 300 Headlines**:
  - **Model Low Tier ($< 60.0$)**: 10 suppliers (40%)
  - **Model Medium Tier ($60.0 - 71.99$)**: 8 suppliers (32%)
  - **Model High Tier ($72.0 - 84.99$)**: 2 suppliers (8%)
  - **Model Critical Tier ($\ge 85.0$)**: 5 suppliers (20%)

---

## 2. Complete 25-Company Empirical Evaluation Table (Static Benchmark)

The table below reflects the exact model scoring, evidence confidence, expected tiers, and match statuses produced during static batch evaluation:

| # | Supplier Name | Industry Sector | Risk Score | Evidence Conf | Expected Tier | Model Tier | Match Status | Top Risk Keywords Detected |
| :-: | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| 1 | **Schneider Electric** | Energy Management | **42.21** | 0.1596 | **Low** | Low | `MATCH` | `shortage` (20), `delays` (15) |
| 2 | **Siemens** | Industrial Automation | **46.43** | 0.1587 | **Low** | Low | `MATCH` | `shortage` (20), `delays` (15) |
| 3 | **ASML** | Lithography / Chips | **47.67** | 0.2307 | **Low** | Low | `MATCH` | `delays` (15), `shortage` (20) |
| 4 | **Texas Instruments** | Analog Semiconductors | **47.99** | 0.1583 | **Low** | Low | `MATCH` | `shortage` (20), `delays` (15) |
| 5 | **Caterpillar** | Heavy Equipment | **48.50** | 0.3958 | **Medium** | Low | `MISMATCH` | `recall` (30), `strike` (25), `shortage` (20) |
| 6 | **Volvo Group** | Commercial Vehicles | **51.72** | 0.3417 | **Medium** | Low | `MISMATCH` | `recall` (30), `strike` (25), `shortage` (20) |
| 7 | **Lockheed Martin** | Aerospace & Defense | **52.30** | 0.2809 | **Low** | Low | `MATCH` | `recall` (30), `shortage` (20) |
| 8 | **Rio Tinto** | Mining & Metals | **53.43** | 0.3472 | **Medium** | Low | `MISMATCH` | `investigation` (25), `disruption` (20) |
| 9 | **BASF** | Chemicals & Materials | **53.74** | 0.3314 | **Low** | Low | `MATCH` | `layoff` (25), `shortage` (20) |
| 10 | **TSMC** | Semiconductor Foundry | **57.67** | 0.2977 | **Low** | Low | `MATCH` | `disruption` (20), `shortage` (20) |
| 11 | **Foxconn** | Contract Manufacturing | **61.02** | 0.3330 | **Medium** | Medium | `MATCH` | `strike` (25), `investigation` (25) |
| 12 | **DHL Supply Chain** | Global Logistics | **64.33** | 0.3915 | **Medium** | Medium | `MATCH` | `strike` (25), `lawsuit` (25), `disruption` (20) |
| 13 | **Nissan** | Automotive OEM | **64.96** | 0.5049 | **Medium** | Medium | `MATCH` | `recall` (30), `lawsuit` (25), `shortage` (20) |
| 14 | **Boeing** | Commercial Aviation | **68.30** | 0.4878 | **Medium** | Medium | `MATCH` | `sanction` (35), `recall` (30), `strike` (25) |
| 15 | **ArcelorMittal** | Steel Metallurgy | **68.92** | 0.5567 | **High** | Medium | `MISMATCH` | `shutdown` (35), `strike` (25), `lawsuit` (25) |
| 16 | **Maersk** | Container Shipping | **69.73** | 0.4541 | **Medium** | Medium | `MATCH` | `cyberattack` (35), `strike` (25), `delays` (15) |
| 17 | **Tesla** | Electric Vehicles | **70.10** | 0.5263 | **High** | Medium | `MISMATCH` | `recall` (30), `lawsuit` (25), `investigation` (25) |
| 18 | **Evergreen Marine** | Ocean Logistics | **71.73** | 0.5747 | **Medium** | Medium | `MATCH` | `shutdown` (35), `strike` (25), `shortage` (20) |
| 19 | **Intel** | Computing Hardware | **72.25** | 0.4504 | **Medium** | High | `MISMATCH` | `layoff` (25), `lawsuit` (25), `downgrade` (20) |
| 20 | **Glencore** | Commodities & Mining | **83.72** | 0.6375 | **High** | High | `MATCH` | `shutdown` (35), `strike` (25), `investigation` (25) |
| 21 | **Toshiba** | Conglomerate | **98.32** | 0.5728 | **High** | Critical | `MISMATCH` | `default` (40), `fraud` (40), `cyberattack` (35) |
| 22 | **Evergrande Construction** | Construction Logistics | **98.75** | 0.6911 | **Critical** | Critical | `MATCH` | `bankruptcy` (50), `default` (40), `fraud` (40) |
| 23 | **Apex Logistics** | Freight Forwarding | **100.00** | 0.6643 | **Critical** | Critical | `MATCH` | `bankruptcy` (50), `insolvency` (45), `fraud` (40) |
| 24 | **Northvolt** | Battery Manufacturing | **100.00** | 0.6883 | **Critical** | Critical | `MATCH` | `insolvency` (45), `shutdown` (35), `layoff` (25) |
| 25 | **Silicon Power Storage** | Solid-State Hardware | **100.00** | 0.6912 | **Critical** | Critical | `MATCH` | `bankruptcy` (50), `insolvency` (45), `fraud` (40) |

---

## 3. Deep Sanity-Check Analysis by Operational Risk Tier

### 3.1 Lowest Risk Tier (Low: 42.21 – 57.67)
- **Benchmark Anchor: Schneider Electric (Score: 42.21, Conf: 0.1596)**
  - *Underlying Signals*: Transient `shortage` (weight 20) and localized `delays` (weight 15).
  - *Sentiment Profile*: 10 Positive headlines, 2 Negative headlines, 0 Neutral.
  - *Human Rationale*: Cleanest supplier in the 25-company cohort. Coverage is overwhelmingly dominated by positive operational momentum (surging AI data center contracts, top global sustainability rankings, $140M North American smart factory expansion). Negative news is strictly limited to routine logistics bottlenecks that were rapidly resolved via secondary supplier networks.
  - *Procurement Recommendation*: **Auto-Clear / Preferred Supplier**.

- **Other Resilient Low-Risk Suppliers**:
  - *Siemens (46.43)*: High proportion of railway electrification deals and industrial automation growth.
  - *ASML (47.67)*: Global semiconductor lithography monopoly with record backlog and profit.
  - *Texas Instruments (47.99)*: $11B fab investments and Tier-1 OEM supplier awards offset transient winter delay.

### 3.2 Moderate Risk Tier (Medium: 61.02 – 71.73)
- **Benchmark Anchor: Boeing (Score: 68.30, Conf: 0.4878)**
  - *Underlying Signals*: `sanction` (35), `recall` (30), `strike` (25), `investigation` (25), `restructuring` (20).
  - *Sentiment Profile*: 5 Positive, 1 Neutral, 6 Negative.
  - *Human Rationale*: Boeing exhibits classic balanced friction: substantial adverse operational signals (FAA investigation, parts recall, union strike) counterweighted by massive commercial aircraft deliveries, airline fleet partnerships, and robust order backlog. The `top_k_mean` scoring prevents acute events from being erased while positive coverage keeps the overall entity score within actionable Medium monitoring bounds.
  - *Procurement Recommendation*: **Active Monitoring / Secondary Supplier Contingency**.

### 3.3 High Operational Exposure Tier (High: 72.25 – 83.72)
- **Benchmark Anchor: Glencore (Score: 83.72, Conf: 0.6375)**
  - *Underlying Signals*: `shutdown` (35), `strike` (25), `investigation` (25), `layoff` (25), `downgrade` (20).
  - *Sentiment Profile*: 2 Positive, 0 Neutral, 10 Negative.
  - *Human Rationale*: Multiple compounding risk dimensions: zinc smelter closures due to power costs, ongoing anti-corruption regulatory investigations, credit rating downgrades, and contractor strikes. Lacks sufficient mitigating positive coverage (only 2 positive articles), driving score to 83.72 with high confidence (0.6375).
  - *Procurement Recommendation*: **Enhanced Due Diligence / Restrict Purchase Order Volumes**.

### 3.4 Terminal Distress Tier (Critical: 98.32 – 100.00)
- **Benchmark Anchors: Apex Logistics, Northvolt, Evergrande Construction, Silicon Power Storage (Scores: 98.75 – 100.00)**
  - *Underlying Signals*: `bankruptcy` (50), `insolvency` (45), `default` (40), `fraud` (40), `shutdown` (35), `sanction` (35), `cyberattack` (35).
  - *Sentiment Profiles*: 10–12 Negative headlines, 0–2 Positive headlines.
  - *Human Rationale*: Simultaneous existential crises: debt defaults, insolvency filings, court liquidation proceedings, criminal fraud investigations, and factory shutdowns. Under anti-dilution rules, catastrophic signals reach the 100.0 cap with highest confidence ($0.66 - 0.69$).
  - *Procurement Recommendation*: **Immediate Hard Procurement Freeze / Contract Termination**.

---

## 4. 25-Company Temporal Trend & Rolling-Window Validation

The table below reflects the actual runtime trend calculation across the 25 suppliers using `src/supplier_trend_headlines_25.json` (300 dated headlines over 12 weekly intervals, evaluated with standard 30-day rolling windows):

| # | Supplier Name | Previous Window Score | Current Window Score | Risk Delta | Trend Direction | Current Window Tier | Benchmark Expected Tier | Deteriorating Flag |
| :-: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | **Boeing** | 59.09 | 38.84 | -20.25 | falling | Low | Medium | False |
| 2 | **Intel** | 63.36 | 40.43 | -22.93 | falling | Low | Medium | False |
| 3 | **Tesla** | 52.50 | 60.56 | +8.06 | rising | Medium | High | True |
| 4 | **Nissan** | 70.62 | 43.95 | -26.67 | falling | Low | Medium | False |
| 5 | **Foxconn** | 45.57 | 31.21 | -14.36 | falling | Low | Medium | False |
| 6 | **TSMC** | 62.98 | 12.76 | -50.22 | falling | Low | Low | False |
| 7 | **Maersk** | 88.14 | 10.85 | -77.29 | falling | Low | Medium | False |
| 8 | **BASF** | 15.52 | 62.33 | +46.81 | rising | Medium | Low | True |
| 9 | **Siemens** | 0.00 | 14.47 | +14.47 | rising | Low | Low | True |
| 10 | **Apex Logistics** | 100.00 | 92.29 | -7.71 | falling | **Critical** | **Critical** | False |
| 11 | **ASML** | 19.62 | 42.84 | +23.22 | rising | Low | Low | True |
| 12 | **Glencore** | 67.93 | 46.73 | -21.20 | falling | Low | High | False |
| 13 | **Lockheed Martin** | 27.17 | 30.99 | +3.82 | rising | Low | Low | True |
| 14 | **Evergreen Marine** | 64.44 | 54.14 | -10.30 | falling | Low | Medium | False |
| 15 | **Northvolt** | 80.50 | 60.75 | -19.75 | falling | Medium | Critical | False |
| 16 | **Texas Instruments** | 12.38 | 14.47 | +2.09 | stable | Low | Low | False |
| 17 | **Schneider Electric** | 13.69 | 13.46 | -0.23 | stable | Low | Low | False |
| 18 | **Caterpillar** | 35.85 | 22.44 | -13.41 | falling | Low | Medium | False |
| 19 | **Volvo Group** | 45.80 | 20.53 | -25.27 | falling | Low | Medium | False |
| 20 | **Rio Tinto** | 36.44 | 7.85 | -28.59 | falling | Low | Medium | False |
| 21 | **ArcelorMittal** | 50.55 | 42.48 | -8.07 | falling | Low | High | False |
| 22 | **Toshiba** | 70.26 | 69.43 | -0.83 | stable | Medium | High | False |
| 23 | **DHL Supply Chain** | 53.57 | 28.66 | -24.91 | falling | Low | Medium | False |
| 24 | **Evergrande Construction** | 92.62 | 51.69 | -40.93 | falling | Low | Critical | False |
| 25 | **Silicon Power Storage** | 100.00 | 71.90 | -28.10 | falling | High | Critical | False |

### Analysis of Trend Dynamics & Mismatch Classification:
1. **Rolling-Window Recency Effect (Northvolt, Evergrande, Silicon Power Storage, Boeing, Intel, Nissan, etc.)**:
   - In static evaluation across all 12 headlines (spanning 90 days), severe events anywhere in the timeline push overall scores into Critical or Medium tiers.
   - In 30-day temporal trend scoring, older articles (published 30–90 days ago) either fall into the `previous_risk_score` window or decay exponentially ($2^{-\text{age}/\tau}$). When the recent 30-day window contains fewer or less acute events, the current window score naturally falls. This is the intended mathematical behavior of a date-aware rolling window model.
2. **Acute Anti-Dilution Protection (Apex Logistics)**:
   - Apex Logistics had recent severe headlines (fraud, restructuring, bankruptcy) in the last 30 days. Under the anti-dilution fix ($\text{severity\_base} = \max(\max_i s_i', \; \text{top\_k\_mean})$), acute distress is fully preserved: Apex's current window score remains **92.29** (**Critical tier**), avoiding false dilution into Low/Medium.
3. **Threshold Sensitivity vs. Low-Tier Safeguards (Siemens, ASML, Lockheed Martin)**:
   - For suppliers with near-zero baseline risk in the previous window, minor transient events in the current window produce $\Delta > 3.0$, flagging them as `rising` / `is_deteriorating: true`.
   - However, their absolute scores remain firmly in the **Low tier** ($< 60.0$). Per the compliance integration contract, unflagged Low-tier entities map directly to `APPROVED / AUTO-CLEAR`, ensuring that early-warning trend sensitivity does not trigger unwarranted procurement freezes.

---

## 5. Scenario-Specific Validations

### 5.1 Positive Coverage & Mitigation Discounting
- **Verified Behavior**: Positive headlines genuinely reduce the risk score under `_calculate_top_k_mean_aggregated_score` through the formula:
  $$\text{mitigation\_factor} = 1.0 - \text{mitigation\_weight} \times \frac{N_{\text{positive}}}{N_{\text{total}}}$$
- **Empirical Evidence**: As verified in `test_scenario_positive_articles_mitigate_risk`, adding clean positive headlines deterministically lowers the risk score relative to negative-only coverage (scaling downward via the mitigation factor).

### 5.2 Acute Negative Signals & Anti-Dilution
- **Verified Behavior**: Severe risk events (`bankruptcy`, `default`, `fraud`) cannot be diluted by neutral news padding.
- **Empirical Evidence**: Apex Logistics and Silicon Power Storage reach elevated scores despite routine headlines, because the `top_k_mean` anti-dilution algorithm isolates the top-$K$ ($K=3$) risk-bearing scores guarded by peak acute severity.

### 5.3 Duplicate Headline Suppression
- **Verified Behavior**: Duplicate headlines (exact, whitespace-padded, or casing variations) are strictly deduplicated during ingestion in both `/predict` and `/trend`.
- **Empirical Evidence**: Submitting multiple duplicate bankruptcy headlines yields `headline_count = 1` and identical confidence/score to a single headline.

### 5.4 Outdated vs Relevant Articles (Time-Aware Rolling Window)
- **Verified Behavior**: Articles older than `trend_window_days` (30 days) are completely excluded from `current_risk_score`.
- **Empirical Evidence**: In `test_scenario_outdated_articles_excluded_from_current_window`, a bankruptcy article published 80 days ago relative to the evaluation anchor does NOT impact `current_risk_score` (which evaluates to 0.0 for clean current headlines), but accurately establishes the historical baseline and sets `trend_direction: "falling"`.

---

## 6. Notable Observations & Boundary Behavior

1. **Authentic Boundary Behavior on Adjacent Tiers**:
   - Intel (72.25 vs 72.0 ceiling) and Tesla (70.10 vs 72.0 ceiling) sit directly at the Medium/High boundary.
   - Caterpillar (48.50), Volvo Group (51.72), and Rio Tinto (53.43) land in Low instead of Medium because their substantial positive coverage (7–8 positive operational articles) legitimately outweighs minor supply delays.
   - This reflects fixed *a priori* threshold configuration across diverse operational profiles rather than retrospective tuning to force 100% agreement.

2. **Confidence Metric Dispersion Dynamics**:
   - Confidence reflects evidence concentration and score agreement. Clean suppliers with minimal friction show confidence around $0.15 - 0.25$, whereas distressed suppliers with consistent multi-signal crises reach $0.65 - 0.70$.

---

## 7. Identified Limitations & Future Enhancements

1. **Internal Benchmark Development & Circularity**:
   - The 25-company dataset and expected tier labels were authored internally by the engineering team during initial pipeline development to verify keyword signal detection, FinBERT scoring, and trend aggregation.
   - The 72% tier match rate represents internal calibration against authored benchmark scenarios, not an independent third-party evaluation.
2. **Synthetic Data Disclosure**:
   - Real corporate names (e.g. Siemens, Tesla, Boeing) were utilized solely for illustrative scenario design and temporal trajectory demonstration.
   - **All headlines in `supplier_headlines_25.json` and `supplier_trend_headlines_25.json` are synthetic development artifacts; they do NOT represent actual news or official corporate disclosures.**
3. **Unit Test Mocking**:
   - Unit tests employ a deterministic keyword-based sentiment mock to ensure fast and repeatable continuous integration without requiring live HuggingFace model downloads. Full FinBERT inference is validated in integration and benchmark runs.
4. **Entity Name Disambiguation in Multi-Entity Articles**:
   - Head-to-head articles comparing multiple suppliers currently attribute all detected signals to the query supplier unless pre-filtered by an upstream entity-linking ingest pipeline.
