# Client Supplier Risk Scoring (GitHub Issue #350 — R15-M7)

## 1. Overview & Architecture

The **Client Supplier Risk Scoring** module integrates client-provided operational master data and incident records into the canonical Supplier Risk scoring workflow. It bridges internal client ERP/procurement operational metrics with external adverse media intelligence (FinBERT NLP headline sentiment) and compliance sanctions screening.

### Key Objectives
- Support client supplier master data (`supplier_code`, `legal_name`, `country`, `city`, `category`, and optional `on_time_delivery_pct`).
- Support operational incident history (`Quality`, `Delay`, `Dispute`, `Other`).
- Resolve `supplier_code` to canonical `supplier_id` using explicit mapping only (no fuzzy matching, guessing, or invented IDs).
- Calculate 12-month rolling operational features, days since last incident, and delivery metrics relative to an injectable `as_of_date`.
- Safely handle missing on-time delivery data without penalizing suppliers as zero-delivery, maintaining an explicit integration TODO for Issue #325.
- Generate top 3 grounded, factual reasons for the assessed risk score.
- Blend client operational risk with NLP news sentiment, while maintaining strict backward compatibility with existing API endpoints, aliases, MongoDB caching, and sanctions enforcement.

```
                              ┌───────────────────────────────────┐
                              │     Client Master Data Store      │
                              │       (client_suppliers)          │
                              └─────────────────┬─────────────────┘
                                                │
                                                ▼
┌─────────────────────────────────┐   ┌───────────────────┐   ┌────────────────────────────────┐
│    Client Incidents Store       ├──►│  Operational Risk │◄──┤ Explicit Supplier Mapping      │
│     (client_incidents)          │   │  Feature Engine   │   │ (supplier_mappings / master)   │
└─────────────────────────────────┘   └─────────┬─────────┘   └────────────────────────────────┘
                                                │
                                                ▼
┌─────────────────────────────────┐   ┌───────────────────┐   ┌────────────────────────────────┐
│   FinBERT Adverse Media NLP     ├──►│  Composite Risk   │◄──┤  Sanctions & Compliance Check  │
│   (headlines / news articles)   │   │  Scoring Engine   │   │  (OFAC / Watchlist Hard-Block) │
└─────────────────────────────────┘   └─────────┬─────────┘   └────────────────────────────────┘
                                                │
                                                ▼
                                      ┌───────────────────┐
                                      │ Top-3 Grounded    │
                                      │ Reason Generator  │
                                      └─────────┬─────────┘
                                                │
                                                ▼
                                      ┌───────────────────┐
                                      │ Cached Assessment │
                                      │   (assessments)   │
                                      └───────────────────┘
```

---

## 2. Client Supplier Input Schemas

### Client Supplier Master (`client_suppliers`)
Represents the client's internal vendor master record.

| Field | Type | Required | Description |
| :--- | :--- | :---: | :--- |
| `supplier_code` | `string` | Optional* | Client internal code (e.g., `ACME-001`, `SUP-2231`). *At least one of `supplier_code` or `supplier_id` must be present. |
| `supplier_id` | `string` | Optional* | Canonical supplier ID in `SUP-#####` format (e.g., `SUP-00045`, `SUP-90001`). |
| `legal_name` | `string` | **Yes** | Registered corporate legal entity name. Non-empty string required. |
| `country` | `string` | **Yes** | ISO 3166-1 alpha-2 or country name (e.g., `US`, `DE`). |
| `city` | `string` | **Yes** | Registered municipal location. Non-empty string required. |
| `category` | `string` | **Yes** | Procurement domain (e.g., `Electronics`, `Logistics`, `Raw Materials`). |
| `on_time_delivery_pct` | `float` | No | Operational on-time delivery rate (`0.0` - `100.0`). Missing or null when client ERP does not track delivery. |

### Supplier Incident Record (`client_incidents`)
Represents recorded operational infractions or disruptions.

| Field | Type | Required | Description |
| :--- | :--- | :---: | :--- |
| `supplier_id` | `string` | Optional* | Canonical supplier ID in `SUP-#####` format. |
| `supplier_code` | `string` | Optional* | Client internal vendor code. |
| `incident_date` | `string` / `date` | **Yes** | ISO 8601 calendar date (`YYYY-MM-DD`). Validated strictly against calendar rules. |
| `incident_type` | `string` | **Yes** | Infraction classification. Must strictly match one of: `Quality`, `Delay`, `Dispute`, `Other`. |
| `description` | `string` | No | Detailed description of the event. Defaults to empty string if missing or null. |

---

## 3. Canonical Supplier Resolution & Identity Mapping

The system enforces strict identity resolution rules to prevent data contamination:
1. **Explicit Mappings Only**:
   - `supplier_code` is resolved against the `supplier_mappings` collection where `supplier_codes` contains the code.
   - If not found in `supplier_mappings`, the system checks `client_suppliers` for a record where `supplier_code` maps to a canonical `supplier_id`.
2. **Never Guess or Invent**:
   - Fuzzy string matching, soundex, edit-distance guessing, and synthetic canonical ID generation are **strictly prohibited**.
3. **Unknown Supplier Handling**:
   - If an unmapped `supplier_code` is requested, the service raises a standard HTTP `404 Not Found` with a descriptive message (`"No canonical mapping found for supplier code: ..."`).

---

## 4. Client-Based Risk Feature Extraction

Features are computed dynamically relative to a deterministic `as_of_date` (defaults to current UTC date or user-provided query parameter `?as_of_date=YYYY-MM-DD`):

### Extracted Feature Set
- **`quality_incidents_12m`**: Count of valid `Quality` incidents occurring within the 365-day rolling window:
  $$\text{as\_of\_date} - 365 \le \text{incident\_date} \le \text{as\_of\_date}$$
- **`delay_incidents_12m`**: Count of valid `Delay` incidents within the 365-day rolling window.
- **`dispute_incidents_12m`**: Count of valid `Dispute` incidents within the 365-day rolling window.
- **`other_incidents_12m`**: Count of valid `Other` incidents within the 365-day rolling window.
- **`total_incidents_12m`**: Total incident count across all categories in the 12-month window.
- **`days_since_last_incident`**: Calendar day count between the most recent eligible incident ($\text{incident\_date} \le \text{as\_of\_date}$) and $\text{as\_of_date}$. Returns `null` if the supplier has zero eligible incidents.
- **`on_time_delivery_pct`**: Value directly from supplier master (`0.0` - `100.0`), or `null` if absent.
- **`country`**: Supplier country code / name from master data.

### Temporal Rules
1. **Future Incident Exclusion**:
   - Any incident dated strictly in the future ($\text{incident\_date} > \text{as\_of\_date}$) is **excluded** from all counts and days-since-incident calculations.
2. **Windowed vs. Lifetime Calculations**:
   - Incidents older than 365 days ($\text{incident\_date} < \text{as\_of\_date} - 365$) do **not** contribute to 12-month counts (`quality_incidents_12m`, etc.).
   - However, if an older incident is the most recent recorded incident, it correctly informs `days_since_last_incident`.

---

## 5. Missing On-Time Delivery Behavior & Issue #325 Integration

### Safe Handling of Missing On-Time Delivery
When `on_time_delivery_pct` is missing (`null` or omitted):
- Operational scoring **continues safely** without failure.
- The system **never treats missing data as 0.0%**. Treating missing data as zero would impose an erroneous 95-point penalty on uninstrumented suppliers.
- When `on_time_delivery_pct` is `null`, the delivery penalty is set to `0.0`.
- The feature dictionary explicitly exposes `"on_time_delivery_pct": null` so analysts and downstream systems clearly see that delivery tracking is absent.

### Integration TODO for GitHub Issue #325
An explicit architectural placeholder is established in `src/client_supplier.py`:
```python
# TODO(Issue #325 - Balaji): Ingest on-time delivery metric from Balaji's
# Issue #325 delivery tracking endpoint when published.
# Do NOT call or integrate endpoint yet.
```
No external network calls or unauthorized integrations are made prior to contract finalization.

---

## 6. Scoring Methodology & Configuration

The composite risk score combines operational risk with adverse media NLP sentiment and regulatory sanctions:

### 1. Client Operational Risk Formula
$$\text{Incident Score} = \min(75.0, 15.0 \cdot N_{\text{quality}} + 10.0 \cdot N_{\text{delay}} + 12.0 \cdot N_{\text{dispute}} + 8.0 \cdot N_{\text{other}})$$

$$\text{Recency Modifier} = \begin{cases}
+10.0 & \text{if } \text{days\_since\_last\_incident} \le 30 \\
+5.0 & \text{if } 30 < \text{days\_since\_last\_incident} \le 90 \\
-5.0 & \text{if } \text{days\_since\_last\_incident} > 180 \text{ and Incident Score} > 0 \\
0.0 & \text{otherwise}
\end{cases}$$

$$\text{Delivery Modifier} = \begin{cases}
(95.0 - \text{on\_time\_delivery\_pct}) \times 1.0 & \text{if present and } \text{on\_time\_delivery\_pct} < 95.0 \\
-5.0 & \text{if present and } \text{on\_time\_delivery\_pct} \ge 95.0 \\
0.0 & \text{if } \text{on\_time\_delivery\_pct is null / missing}
\end{cases}$$

$$\text{Client Operational Score} = \text{round}\left(\min(100.0, \max(0.0, \text{Incident Score} + \text{Recency Modifier} + \text{Delivery Modifier})), 2\right)$$

### 2. Combining Client and News Scores

When both client operational data and adverse news headlines exist, the final score is the higher of the two:

$$\text{Composite Score} = \max(\text{Client Score}, \text{NLP Score})$$

Both sources are evidence of risk, so neither may lower the other: clean client data does not reduce a news-based score, and weak news does not reduce a client-based score. When the NLP score decides the result, its hysteresis tier is kept. `client_risk_weight` and `nlp_risk_weight` are still validated in `src/config.py` but no longer change the score.

### 3. Sanctions & Risk Tiers
- **Sanctions Override**: Any active sanctions designation in seed master data sets `score = 85.0` and `tier = "Critical"` (preserving exact baseline behavior from `origin/develop`).
- **Operational Tiers**:
  - `Low`: Score $< 60.0$
  - `Medium`: $60.0 \le \text{Score} < 72.0$
  - `High`: $72.0 \le \text{Score} < 85.0$
  - `Critical`: $\text{Score} \ge 85.0$

### 4. Configurable Parameters (`src/config.py`)
All parameters are configurable via environment variables:

| Setting | Env Var | Default | Description |
| :--- | :--- | :---: | :--- |
| `client_quality_incident_weight` | `CLIENT_QUALITY_INCIDENT_WEIGHT` | `15.0` | Weight per Quality incident in last 12m |
| `client_delay_incident_weight` | `CLIENT_DELAY_INCIDENT_WEIGHT` | `10.0` | Weight per Delay incident in last 12m |
| `client_dispute_incident_weight` | `CLIENT_DISPUTE_INCIDENT_WEIGHT` | `12.0` | Weight per Dispute incident in last 12m |
| `client_other_incident_weight` | `CLIENT_OTHER_INCIDENT_WEIGHT` | `8.0` | Weight per Other incident in last 12m |
| `client_target_on_time_delivery_pct` | `CLIENT_TARGET_ON_TIME_DELIVERY_PCT` | `95.0` | Benchmark target on-time delivery percentage |
| `client_late_delivery_penalty_weight` | `CLIENT_LATE_DELIVERY_PENALTY_WEIGHT` | `1.0` | Penalty points per percentage point below target |
| `client_risk_weight` | `CLIENT_RISK_WEIGHT` | `0.5` | Weight of client operational score in composite score |
| `nlp_risk_weight` | `NLP_RISK_WEIGHT` | `0.5` | Weight of NLP news score in composite score |
| `client_max_incident_score` | `CLIENT_MAX_INCIDENT_SCORE` | `75.0` | Cap on operational incident subscore |
| `mongodb_client_suppliers_collection` | `MONGODB_CLIENT_SUPPLIERS_COLLECTION` | `"client_suppliers"` | MongoDB collection for client master records |
| `mongodb_client_incidents_collection` | `MONGODB_CLIENT_INCIDENTS_COLLECTION` | `"client_incidents"` | MongoDB collection for supplier incidents |

---

## 7. Grounded Top Three Reasons

Every risk score returns the **top three factual reasons** driving the score, ranked by severity impact:
- Derived strictly from input data (incidents, delivery metrics, news sentiment, sanctions).
- Free from hallucinations or unsupported speculation.

### Concrete Examples
- `"4 delay incidents in 12 months"`
- `"2 quality incidents in 12 months"`
- `"1 dispute incidents in 12 months"`
- `"On-time delivery rate of 82.5% is below target (95.0%)"`
- `"Recent adverse news headlines detected (FinBERT NLP)"`
- `"Active sanctions or watchlist hit detected"`
- `"No operational incidents or adverse signals recorded"`

---

## 8. API Compatibility & Endpoints

### 1. Canonical Supplier Risk Score Endpoint
```http
GET /api/v1/suppliers/{supplier_id}/risk-score?as_of_date=2026-11-16
```
*(Preserves existing alias `/api/v1/supplier-risk/{supplier_id}/risk-score`)*

#### Headers:
- `x-api-key`: Required (if configured).

#### Query Parameters:
- `as_of_date` (*optional*, `YYYY-MM-DD`): Deterministic calculation date for incident windows and age calculations. Defaults to current UTC date.

### 2. Client Supplier Code Risk Score Endpoint
```http
GET /api/v1/supplier-risk/client-suppliers/{supplier_code}/risk-score?as_of_date=2026-11-16
```
Resolves `supplier_code` to canonical `supplier_id` and executes scoring.

### Example Response Body (`200 OK`)
```json
{
  "supplier_id": "SUP-00045",
  "score": 67.5,
  "tier": "Medium",
  "top_factors": [
    {
      "factor": "delays",
      "category": "Operational",
      "weight": 40.0,
      "description": "4 delay incidents in the last 12 months."
    },
    {
      "factor": "recall",
      "category": "Operational",
      "weight": 15.0,
      "description": "1 quality incident in the last 12 months."
    }
  ],
  "top_evidence_articles": [],
  "computed_at": "2026-11-16T15:00:00Z",
  "top_reasons": [
    "4 delay incidents in 12 months",
    "1 quality incidents in 12 months",
    "On-time delivery rate of 87.5% is below target (95.0%)"
  ],
  "client_risk_features": {
    "quality_incidents_12m": 1,
    "delay_incidents_12m": 4,
    "dispute_incidents_12m": 0,
    "other_incidents_12m": 0,
    "days_since_last_incident": 14,
    "on_time_delivery_pct": 87.5,
    "on_time_delivery_missing": false,
    "country": "US",
    "city": null,
    "category": null
  }
}
```

---

## 9. MongoDB Persistence & Caching

1. **Storage Collections**:
   - `client_suppliers`: Stores master records with compound unique index on `supplier_code` and `supplier_id`.
   - `client_incidents`: Stores incidents with compound indexes on `(supplier_id, incident_date)` and `(supplier_code, incident_date)`.
   - `assessments`: Persists calculated risk scores, `client_risk_features`, and `top_reasons`.
2. **Backward-Compatible Cache Invalidation**:
   - When loading cached assessments, if new client master/incident records exist but the cached assessment lacks `client_risk_features`, the cache is automatically bypassed/refreshed.
   - Legacy cached assessment records without `client_risk_features` or `top_reasons` remain fully readable by older API clients.

---

## 10. Synthetic Test Scenarios & Instructions

The implementation includes 25 deterministic synthetic test scenarios in `tests/test_client_supplier_scoring.py`:

| # | Scenario Description | Tested Condition |
| :---: | :--- | :--- |
| **1** | Valid master data & multiple incidents | Multi-category feature aggregation and scoring |
| **2** | Supplier with no incidents | Clean supplier handling; 0 incidents; `days_since_last_incident: null` |
| **3** | Missing on-time delivery percentage | Null delivery rate without treating as zero penalty |
| **4** | On-time delivery percentage available | Late delivery penalty calculation below 95% target |
| **5** | Supplier with Quality incidents | Quality incident weight contribution (15.0 per incident) |
| **6** | Supplier with Delay incidents | Delay incident weight contribution (10.0 per incident) |
| **7** | Supplier with Dispute incidents | Dispute incident weight contribution (12.0 per incident) |
| **8** | Supplier with Other incidents | Other incident weight contribution (8.0 per incident) |
| **9** | Future incidents | Incidents with `incident_date > as_of_date` excluded |
| **10** | Incidents older than 12 months | Incidents $> 365$ days old excluded from 12m rolling counts |
| **11** | Days since last incident calculation | Correct calendar day delta calculation |
| **12** | Supplier identified using `supplier_code` | Resolution of client code to canonical supplier ID |
| **13** | Supplier identified using canonical `supplier_id` | Direct scoring by canonical supplier ID |
| **14** | Unknown supplier mapping | Non-existent supplier returns HTTP 404 |
| **15** | Invalid incident type | Malformed incident type fails validation |
| **16** | Invalid or missing incident date | Malformed date string fails validation |
| **17** | Missing optional fields | Default handling for null descriptions, codes, etc. |
| **18** | MongoDB / data loading failure | Graceful exception handling on database errors |
| **19** | Cached assessment with new fields | Persistence and retrieval of client features in cache |
| **20** | Old cached assessment without new fields | Backward-compatible retrieval of legacy cache records |
| **21** | Existing API authentication tests | Auth header validation preserved |
| **22** | Existing endpoint aliases | Both `/suppliers/` and `/supplier-risk/` aliases verified |
| **23** | Existing no-evidence behavior | Empty supplier history returns null score/tier baseline |
| **24** | Existing sanctions behavior | Sanctions hit triggers Critical tier (85.0) |
| **25** | Existing NLP scoring integration | Operational score correctly blended with FinBERT NLP score |

### How to Run Tests
```bash
# Run all client supplier scoring synthetic tests
python -m pytest ml-services/supplier-risk/tests/test_client_supplier_scoring.py -v

# Run existing canonical risk score API tests (zero regressions)
python -m pytest ml-services/supplier-risk/tests/test_risk_score_api.py -v

# Run canonical supplier mapping tests
python -m pytest ml-services/supplier-risk/tests/test_canonical_supplier_mapping.py -v
```

---

## 11. ETL Schema Compatibility & Integration Requirements

The service supports direct ingestion of client vendor master data and incident feeds with backward compatibility for the ETL staging specifications (`data-platform/etl/client_ingest/spec.yaml`):

1. **Field Name Aliases**:
   - `legal_name` supports `supplier_name` and `name` as aliases, allowing records from `stg_supplier_master` (`supplier_name`) to parse directly into `ClientSupplierMaster`.
2. **Safe Missing Field Handling**:
   - `country` and `category` are optional in `ClientSupplierMaster` and `ClientRiskFeatures`. When omitted by upstream staging tables, they default to `null` without fabricating hypothetical business values.
   - `city` is captured from `stg_supplier_master`.
3. **Remaining ETL Integration Requirements**:
   - **Country Enrichment**: `stg_supplier_master` only provides `city` and `state`. Full vendor country resolution should be joined from tax/registration metadata when available.
   - **Category Mapping**: `stg_supplier_master` does not include supplier commodity classification; category information may optionally be derived by aggregating `stg_product_master` category mappings for purchase orders issued to the supplier.
   - **Delivery Tracking Integration (GitHub Issue #325)**: `stg_supplier_master` does not track historical on-time delivery percentages. Dynamic on-time metrics will be ingested once Balaji's Issue #325 shipment history analytics endpoint/feed is integrated.
