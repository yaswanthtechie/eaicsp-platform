# Compliance Service — Handover

## 1. Purpose

The Compliance Service performs internal supplier compliance checks and returns a decision that other services can use before allowing supplier activation or other protected operations.

This handover documents the current implementation, how to run the service and its tests, known issues, and items that still require verification.

## 2. Current Status

### Working

- The Compliance Service starts successfully using Uvicorn.
- The internal compliance endpoint is available at `POST /api/v1/compliance/internal-check`.
- Internal service-to-service authentication uses the `X-Caller-Service` and `X-Service-Key` headers.
- The endpoint accepts supplier details and returns a compliance decision.
- The internal check returns a structured response containing `supplier_id`, `company_name`, `country`, `cleared`, `decision`, and `reason`.
- An authenticated request for `SUP-00001` returned HTTP `200 OK` with decision `CLEAR` during manual verification on 22 October 2026.
- Requests without the required authentication headers are rejected with HTTP `401 Unauthorized`.
- Internal compliance-check logging and SLA monitoring startup messages were observed during local execution.
- Clean-venv test run on 23 October 2026: **332 passed, 3 deselected**.
- `tests/test_contract.py` (the `/internal-check` contract test): **4 passed**.

### Broken / known issues

- **EU sanctions list has no working download URL.** `eu.xml` is required for live screening, but `EU_DOWNLOAD_URL` is empty because the EU endpoint needs an access token we do not have (the tokenless URL returns `403 Forbidden`). With `USE_FIXTURES=false`, startup logs `Skipping eu.xml: no download URL configured.` and every `/internal-check` call returns **503 Compliance service unavailable**. This blocks #209: the three sanctioned seed suppliers `SUP-00007`, `SUP-00023`, and `SUP-00045` cannot be screened live.
- **Workaround for local work only:** `USE_FIXTURES=true` screens against bundled samples in `app/data/fixtures/` (`ofac_sample.csv`, `un_sample.xml`, `eu_sample.xml`). These are not real sanctions lists; a `CLEAR` result only proves the API works, not that a supplier is clean.
- **No service keys out of the box.** `INTERNAL_SERVICE_KEYS` is empty in `.env.example`. Every caller receives `401` until real keys are configured in `.env`; this is deliberate fail-closed behavior.
- **Not in the shared environment yet.** `infra/docker-compose.yml` creates the Compliance DB user but does not run the Compliance Service. This is pending with Ajith (#208).
- **Minor:** `datetime.utcnow()` deprecation warnings occur in tests; `tests/test_contract.py` uses the non-canonical ID `SUP-CONTRACT-001`.

## 3. API Contract

### Endpoint

`POST /api/v1/compliance/internal-check`

### Required authentication headers

| Header             | Purpose                                                   |
| ------------------ | --------------------------------------------------------- |
| `X-Caller-Service` | Identifies the calling service, such as `supplier-portal` |
| `X-Service-Key`    | Shared secret configured for the calling service          |

### Example request

```json
{
  "supplier_id": "SUP-00001",
  "supplier_name": "ABC Supplies",
  "country": "India"
}
```

### Example successful response

```json
{
  "supplier_id": "SUP-00001",
  "company_name": "ABC Supplies",
  "country": "India",
  "cleared": true,
  "decision": "CLEAR",
  "reason": "No sanctions or watchlist match found."
}
```

The example above records the observed response from local manual verification. Actual decisions depend on the service's screening logic and configured data sources.

### Expected decision handling

- `CLEAR`: The supplier passed the internal compliance check.
- `BLOCK`: The supplier must not be treated as cleared.
- `REVIEW`: The supplier requires further review and must not be treated as cleared.

The calling service must handle these decisions according to its own integration contract.

### Authentication failure

Requests with missing or invalid service authentication return HTTP `401 Unauthorized`.

## 4. Prerequisites

- Python version supported by the repository and its dependency files.
- Git.
- Access to the EAICSP repository.
- Required environment variables configured in `.env`.
- PostgreSQL and Kafka, if required by the selected configuration and test suite.
- Network access to any external screening data sources required by the selected configuration.

Do not commit `.env` files, passwords, API keys, or shared service secrets.

## 5. Environment Configuration

Start from the service's example configuration:

```powershell
Copy-Item .env.example .env
```

Review the actual `.env.example` and application settings before running the service. Configure all required values for the selected environment.

Important configuration areas include:

- Database connection settings.
- Platform authentication settings.
- Internal service authentication keys.
- Sanctions data-source URLs.
- Kafka bootstrap servers.
- Screening thresholds and scoring weights.
- SLA monitoring settings.

The `INTERNAL_SERVICE_KEYS` setting must follow the format expected by the application: caller-service names mapped to their corresponding secrets.

Example format only:

```dotenv
INTERNAL_SERVICE_KEYS=inventory-service:<INVENTORY_SHARED_KEY>,supplier-portal:<SUPPLIER_PORTAL_SHARED_KEY>
```

Replace placeholders with valid local secrets. Do not copy placeholder values into a working configuration.

## 6. How to Run the Service

Run the following commands from the `services/compliance` directory.

### Create and activate a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### Install dependencies

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Configure `.env`

```powershell
Copy-Item .env.example .env
```

Then edit `.env`:
- `INTERNAL_SERVICE_KEYS=supplier-portal:<your-local-key>,inventory-service:<another-local-key>` (choose your own values; callers send the same values in `X-Service-Key`).
- For local work without the EU list, set `USE_FIXTURES=true` (see Broken / known issues).

### Start the service

```powershell
python -m uvicorn app.main:app --reload --port 8003
```

### Verify startup

Open:

- Swagger UI: `http://127.0.0.1:8003/docs`
- OpenAPI schema: `http://127.0.0.1:8003/openapi.json`

Check the startup logs for successful application initialization and any dependency errors.

## 7. How to Run Tests

Run commands from `services/compliance` with the virtual environment activated.

### Run the complete test suite

```powershell
python -m pytest -q
# 332 passed, 3 deselected

python -m pytest -q tests/test_contract.py
# 4 passed
```

Unit tests need no `.env`, Postgres or Kafka. Tests marked integration (deselected by default) need `docker-compose.dev.yml` or live sanctions downloads:

```powershell
python -m pytest -m integration -q
```

### Clean-environment verification

1. Create a fresh virtual environment.
2. Install dependencies using the repository's dependency files.
3. Configure test environment variables and any required test services.
4. Run the complete test suite.
5. Run the internal-check contract test explicitly.
6. Record the commands, results, and any skipped tests.

Record the final test counts and results in the pull request description.

## 8. Manual Internal-Check Verification

With the service running, an authenticated request can be sent using Python and `httpx`.

Use a locally configured service key; do not place secrets in source code or commit them.

Example request:

```python
import httpx

response = httpx.post(
    "http://127.0.0.1:8003/api/v1/compliance/internal-check",
    headers={
        "X-Caller-Service": "supplier-portal",
        "X-Service-Key": "<configured-local-secret>",
    },
    json={
        "supplier_id": "SUP-00001",
        "supplier_name": "ABC Supplies",
        "country": "India",
    },
    timeout=15,
)

print(response.status_code)
print(response.text)
```

Expected verification:

- A correctly authenticated, valid request returns HTTP `200` and a structured decision response.
- A request missing authentication headers returns HTTP `401`.
- Invalid request bodies should return the validation response defined by the API contract.

A successful manual request alone does not establish that all automated tests pass.

## 9. What's Untested / Must Be Verified

Before the handover is considered complete, verify and document:

- [x] Internal-check contract test passes.
- [x] Missing and invalid internal service credentials are rejected.
- [ ] `CLEAR`, `BLOCK`, and `REVIEW` decisions match the API contract.
- [ ] Invalid request bodies return the expected validation response.
- [ ] Required database and Kafka integrations work in the intended environment.
- [ ] External screening data sources work with the configured URLs and credentials.
- [ ] Service starts successfully in the shared environment.
- [ ] Ajith has confirmed shared-environment configuration and integration readiness.

Items should be marked complete only after evidence has been collected.

## 10. Shared Environment and Coordination

Coordinate with Ajith before validating or changing shared-environment configuration.

Confirm:

- Environment variable names and values are configured securely.
- Database and Kafka endpoints are reachable.
- Service ports and deployment commands are correct.
- Internal service keys match between callers and the Compliance Service.
- The internal-check contract works from the intended calling service.
- Logs do not expose secrets or sensitive information.

Do not overwrite shared credentials or change shared infrastructure without coordination.

## 11. Handover Completion Checklist

- [ ] `HANDOVER.md` reviewed and committed.
- [x] Full test suite green from a clean virtual environment.
- [x] Internal-check contract test green.
- [x] Known issues and untested items documented accurately.
- [x] Pull request opened against the intended base branch.


## 12. Maintenance Notes

This round focuses on maintaining the existing Compliance Service, not introducing new features.

Preserve the current API contract unless a contract change is explicitly approved. If a change is required, update the contract, tests, and affected consumers together.
