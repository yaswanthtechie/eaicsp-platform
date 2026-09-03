# Inventory Service – Task 5: Authentication Integration

## 1. Overview

The Inventory Service is a FastAPI microservice responsible for inventory management, reorder planning, demand simulation, ABC classification, and stock-related operations.

### Task 5 – Authentication Integration

Task 5 integrates the Inventory Service with the shared **Platform/Auth Service**.

The Inventory Service does **not** validate JWT tokens independently for protected endpoints. Instead, it makes a real HTTP request to Rahul's Platform Service to verify the supplied access token and obtain the user's role.

### Services

| Service               |   Port | Purpose                               |
| --------------------- | -----: | ------------------------------------- |
| Inventory Service     | `8001` | Inventory APIs                        |
| Platform/Auth Service | `8005` | Authentication and token verification |

---

# 2. Architecture

```text
Client
  |
  | Authorization: Bearer <access_token>
  v
Inventory Service :8001
  |
  | POST /api/v1/auth/verify
  | Authorization: Bearer <access_token>
  v
Rahul's Platform/Auth Service :8005
  |
  | Token validation
  | User lookup
  | Role lookup
  v
Inventory Service
  |
  | Role authorization
  v
Protected Inventory Endpoint
```

The important point is that **Inventory depends on Rahul's Platform Service for authentication verification**.

---

# 3. Rahul's Platform Service Dependency

The Inventory Service requires Rahul's Platform/Auth Service to be available for real authentication.

The expected verification endpoint is:

```text
POST http://127.0.0.1:8005/api/v1/auth/verify
```

The Inventory Service sends the user's bearer token to this endpoint.

### Required environment variable

```env
PLATFORM_AUTH_URL=http://127.0.0.1:8005
```

The final verification URL is:

```text
{PLATFORM_AUTH_URL}/api/v1/auth/verify
```

### Important

Rahul's Platform/Auth Service is a **shared dependency**.

If Rahul's service is not running:

* authentication cannot be verified;
* the Inventory Service should return `503 Service Unavailable`;
* the Inventory Service should **not crash**.

At the moment, end-to-end authentication testing requires Rahul's Platform/Auth Service branch/service containing the `/api/v1/auth/verify` endpoint.

**Rahul should push/merge the Platform/Auth changes to the shared team repository so other developers can test the complete integration.**

---

# 4. Environment Configuration

Create a `.env` file inside the Inventory Service.

Example:

```env
DATABASE_URL=postgresql+psycopg2://USER:PASSWORD@localhost:5432/inventory
TEST_DATABASE_URL=postgresql+psycopg2://USER:PASSWORD@localhost:5432/inventory_test
PLATFORM_AUTH_URL=http://127.0.0.1:8005
```

A `.env.example` file should also be provided:

```env
DATABASE_URL=postgresql+psycopg2://USER:PASSWORD@localhost:5432/inventory
TEST_DATABASE_URL=postgresql+psycopg2://USER:PASSWORD@localhost:5432/inventory_test
PLATFORM_AUTH_URL=http://127.0.0.1:8005
```

Do **not** commit real database credentials or secrets.

---

# 5. Authentication Flow

For a protected Inventory endpoint:

### Step 1 – Client sends a request

```http
Authorization: Bearer <access_token>
```

### Step 2 – Inventory extracts the token

FastAPI's authentication dependency reads the bearer token.

### Step 3 – Inventory calls Platform/Auth

Inventory makes a real HTTP request:

```http
POST /api/v1/auth/verify
Authorization: Bearer <access_token>
```

### Step 4 – Platform/Auth validates the token

Rahul's service validates the token and returns the authentication result and user role.

Example successful response:

```json
{
  "valid": true,
  "role": "warehouse_manager",
  "user_id": 1
}
```

### Step 5 – Inventory checks the role

After authentication succeeds, Inventory checks whether the returned role is allowed to access the requested endpoint.

---

# 6. Authentication Error Handling

The Inventory Service converts authentication failures into appropriate HTTP responses.

| Situation                                  |                  Response |
| ------------------------------------------ | ------------------------: |
| Authorization header missing               |        `401 Unauthorized` |
| Invalid/expired token                      |        `401 Unauthorized` |
| User authenticated but role is not allowed |           `403 Forbidden` |
| Auth service times out                     | `503 Service Unavailable` |
| Auth service is unavailable                | `503 Service Unavailable` |
| Unexpected auth-service response           | `503 Service Unavailable` |

The authentication HTTP client uses a timeout so that the Inventory Service does not wait indefinitely for the Platform/Auth Service.

---

# 7. Protected Endpoint Authorization

Endpoints that require authentication use the authentication dependency.

Conceptually:

```python
current_user = Depends(verify_token)
```

Role-protected endpoints additionally verify that the authenticated user's role is permitted.

For example:

```text
CEO
VP Operations
Warehouse Manager
```

may have different permissions depending on the endpoint.

The exact allowed roles should be defined with the endpoint's authorization requirement rather than assuming every authenticated user has access.

---

# 8. Inventory API

Base URL:

```text
http://127.0.0.1:8001
```

Swagger documentation:

```text
http://127.0.0.1:8001/docs
```

Main inventory operations include:

| Method   | Endpoint                                    | Purpose                      |
| -------- | ------------------------------------------- | ---------------------------- |
| `POST`   | `/api/v1/inventory/`                        | Create inventory             |
| `GET`    | `/api/v1/inventory/`                        | List inventory               |
| `GET`    | `/api/v1/inventory/{sku_id}`                | Get inventory by SKU         |
| `PUT`    | `/api/v1/inventory/{sku_id}/{warehouse_id}` | Update inventory             |
| `DELETE` | `/api/v1/inventory/{sku_id}/{warehouse_id}` | Delete inventory             |
| `GET`    | `/api/v1/inventory/reorder-plan`            | Get reorder recommendations  |
| `GET`    | `/api/v1/inventory/low-stock`               | Get low-stock items          |
| `POST`   | `/api/v1/inventory/what-if`                 | Demand what-if analysis      |
| `POST`   | `/api/v1/inventory/simulate`                | Simulate demand growth/spike |
| `POST`   | `/api/v1/inventory/bulk-upload`             | Upload inventory CSV         |
| `POST`   | `/api/v1/inventory/bulk-update`             | Bulk update inventory        |

> Keep the HTTP method in this section synchronized with the actual route implementation. In particular, the reviewer identified a previous `POST` → `PUT` change for `/bulk-update`.

---

# 9. R4 Features

## Demand-Driven Reorder Point

Reorder points are calculated using demand, lead time, and safety stock.

```text
Reorder Point =
Average Daily Demand × Lead Time
+ Safety Stock
```

---

## ABC Classification

SKUs are classified based on sales volume.

```text
A → Top 20%
B → Next 30%
C → Remaining 50%
```

ABC classification is calculated using sales history grouped by SKU and warehouse.

### Tier-Based Safety Stock

ABC is not only a label. Each tier has a different safety-stock multiplier.

```text
A → 1.5 × base safety stock
B → 1.2 × base safety stock
C → 1.0 × base safety stock
```

Therefore, high-volume A items receive higher safety-stock protection than B and C items.

---

## Demand Growth Simulation

The `/simulate` endpoint allows a future demand-growth scenario to be evaluated.

Example:

```text
Current demand
      ↓
Apply demand growth/spike %
      ↓
Calculate simulated demand
      ↓
Evaluate inventory/reorder requirement
```

Example request:

```json
{
  "demand_spike_percent": 30
}
```

This allows the inventory team to understand how inventory requirements change when demand increases.

---

# 10. Testing

Run the complete test suite from the Inventory Service directory:

```bash
pytest -v
```

Authentication-related tests should cover at least:

### Invalid token

Expected:

```text
401 Unauthorized
```

### Wrong role

Expected:

```text
403 Forbidden
```

### Correct role

Expected:

```text
Successful endpoint response
```

### Auth service timeout/down

Expected:

```text
503 Service Unavailable
```

---

# 11. Testing Without Rahul's Service

Unit/integration tests should not depend entirely on Rahul's service being available.

Authentication tests can mock the HTTP call to:

```text
POST /api/v1/auth/verify
```

This allows the tests to simulate:

```text
401 → invalid token
200 + wrong role → 403
200 + correct role → success
Timeout → 503
```

The test suite should also retain tests that use the real Platform/Auth Service where end-to-end verification is required.

---

# 12. Test Database

Tests must use the test database rather than the production database.

Configure:

```env
TEST_DATABASE_URL=postgresql+psycopg2://USER:PASSWORD@localhost:5432/inventory_test
```

The test configuration overrides the application's normal database dependency so that test execution does not modify production data.

---

# 13. Running the Services

## Start Rahul's Platform/Auth Service

Run Rahul's service on:

```text
127.0.0.1:8005
```

Verify that:

```text
POST /api/v1/auth/verify
```

is available.

## Start Inventory Service

From the Inventory Service directory:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

Open:

```text
http://127.0.0.1:8001/docs
```

---

# 14. Swagger Authentication Testing

1. Start Rahul's Platform/Auth Service on port `8005`.
2. Start Inventory Service on port `8001`.
3. Obtain a valid access token from the Platform/Auth Service.
4. Open Inventory Swagger:

```text
http://127.0.0.1:8001/docs
```

5. Click **Authorize**.
6. Enter the bearer token.
7. Call a protected Inventory endpoint.
8. Inventory sends the token to Rahul's `/api/v1/auth/verify`.
9. The returned role is checked.
10. The request is allowed or rejected according to the endpoint's authorization rules.

---

# 15. Troubleshooting

### `401 Missing authentication token`

The request did not contain:

```http
Authorization: Bearer <token>
```

Check Swagger's **Authorize** button or the request headers.

---

### `401 Unauthorized`

The Platform/Auth Service rejected the supplied token.

Check:

* token validity;
* token expiration;
* Platform/Auth Service logs;
* `/api/v1/auth/verify` response.

---

### `403 Forbidden`

The token is valid, but the authenticated user's role does not have permission for that endpoint.

Check the user's role in the Platform/Auth Service.

---

### `503 Authentication service unavailable`

Inventory could not communicate with Rahul's Platform/Auth Service.

Check:

```text
Platform/Auth Service → port 8005
Inventory Service     → port 8001
```

Also verify:

```env
PLATFORM_AUTH_URL=http://127.0.0.1:8005
```

---

### `503 Authentication service timed out`

The Platform/Auth Service did not respond within the configured timeout.

Check whether Rahul's service is running correctly and responding to:

```text
POST /api/v1/auth/verify
```

---

# 16. Important Developer Notes

### Shared authentication dependency

Inventory authentication depends on Rahul's Platform/Auth Service.

Do **not** replace the real HTTP call with local JWT validation unless the team changes the agreed authentication architecture.

### Role response contract

The Inventory Service expects the Platform/Auth verification response to provide the user's role in the agreed format, for example:

```json
{
  "valid": true,
  "role": "ceo",
  "user_id": 1
}
```

This contract should remain consistent between both services.

### Do not commit secrets

Never commit:

```text
.env
database passwords
JWT secrets
access tokens
```

Use `.env.example` for setup documentation.

---

# 17. Task 5 Completion

Task 5 includes:

* ✅ Real HTTP authentication integration with Platform/Auth Service
* ✅ `POST /api/v1/auth/verify` integration
* ✅ Bearer-token forwarding
* ✅ Authentication timeout handling
* ✅ Authentication-service failure handling
* ✅ `401` handling for authentication failures
* ✅ `403` handling for role authorization
* ✅ Role-based endpoint protection
* ✅ Authentication test coverage
* ✅ Test database isolation
* ✅ `.env.example` configuration
* ✅ R4 demand simulation
* ✅ ABC classification
* ✅ Tier-specific safety-stock sizing

### Dependency

The only external runtime dependency for authentication is **Rahul's Platform/Auth Service on port `8005`**.

For complete end-to-end testing, both services must be running:

```text
Platform/Auth Service → 8005
Inventory Service     → 8001
```

If the Platform/Auth Service is unavailable, Inventory safely returns `503 Service Unavailable` rather than crashing.
