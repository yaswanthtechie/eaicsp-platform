# Combined Round 12+13 — Pod 1

# Platform Service — Backend Microservice

## Scope

Round 12+13 upgrades the Platform Service in three areas:

1. **Milestone 1 — Redis-backed shared authentication state**
2. **Milestone 2 — Expanded RBAC role model**
3. **Milestone 3 — Shared event publishing and structured logging**

The implementation is designed to preserve existing authentication and `/verify` contracts while adding shared runtime state, new roles and permissions, and common event/logging conventions.

---

# Milestone 1 — Redis-backed Shared Authentication State

## Objective

The Platform Service previously stored some runtime authentication state in process memory.

That approach is safe only for a single service instance.

With multiple Platform Service instances:

```text
                    +------------------+
                    |      Redis       |
                    |     :6379        |
                    +--------+---------+
                             |
                +------------+------------+
                |                         |
        +-------v-------+         +-------v-------+
        | Platform      |         | Platform      |
        | Instance A    |         | Instance B    |
        | :8005         |         | :8007         |
        +---------------+         +---------------+
```

Both instances now use Redis for shared runtime authentication state.

This prevents security state from becoming inconsistent between instances.

---

## Runtime State Stored in Redis

The following state is backed by Redis:

* `/api/v1/auth/verify` verification cache
* `/api/v1/auth/verify` rate-limit counters
* Access-token revocation state
* Session/revocation-related runtime state

The relational database remains the source of truth for persistent application data.

Redis is used for shared, short-lived runtime state.

---

## Redis Configuration

Local development:

```env
REDIS_URL=redis://localhost:6379/0
REDIS_VERIFY_CACHE_TTL=60
```

Start Redis:

```powershell
docker compose -f docker-compose.dev.yml up -d redis
```

Check:

```powershell
docker compose -f docker-compose.dev.yml ps
```

Expected local endpoint:

```text
localhost:6379
```

---

## Verify Cache

Successful `/api/v1/auth/verify` results are cached in Redis.

The access token itself is not used directly as a Redis key.

A SHA-256 token hash is used conceptually as:

```text
platform:verify:<token-hash>
```

The cache TTL is bounded by both:

```text
REDIS_VERIFY_CACHE_TTL
```

and the remaining JWT lifetime.

Therefore:

```text
cache TTL = min(configured TTL, remaining JWT lifetime)
```

The default configured TTL is:

```text
60 seconds
```

---

## User Cache Index

The verification cache maintains a user-to-token index for user-specific invalidation.

Conceptually:

```text
platform:verify:user:<user-id>
```

This allows cached verification entries to be removed when a user's authentication state changes.

---

## Token Revocation

Revoked access tokens are represented in Redis using a token hash.

Conceptually:

```text
platform:revoked:<token-hash>
```

The revocation entry is retained only for the remaining lifetime of the token.

If Redis cannot safely determine revocation state, protected verification fails closed instead of treating the token as valid.

---

# Redis-backed Rate Limiting

Rate-limit counters are shared through Redis.

Current limits:

| Endpoint                  |        Limit |      Window |
| ------------------------- | -----------: | ----------: |
| `/api/v1/auth/login`      |  20 requests |  60 seconds |
| `/api/v1/auth/mfa/verify` |   5 requests | 300 seconds |
| `/api/v1/auth/verify`     | 100 requests |  60 seconds |
| `/api/v1/auth/sso/login`  |  20 requests |  60 seconds |

For `/verify`, the rate-limit bucket includes the caller-service context.

The rate limiter executes before the verification-cache response is returned.

```text
Request
   |
   v
Redis rate limiter
   |
   v
Verify cache
   |
   +---- hit ----> cached verification result
   |
   +---- miss ---> JWT/database verification
```

Therefore, a cached `/verify` response cannot bypass the configured rate limit.

---

# `/verify` Contract

The existing `/api/v1/auth/verify` contract remains unchanged.

Example request:

```http
POST /api/v1/auth/verify
Authorization: Bearer <access_token>
X-Caller-Service: inventory
```

Example response:

```json
{
  "valid": true,
  "user_id": 1,
  "email": "user@example.com",
  "full_name": "Example User",
  "role": "analyst",
  "supplier_id": null,
  "is_active": true,
  "permissions": [
    "inventory:read",
    "compliance:read"
  ]
}
```

Existing consuming services do not need to change their `/verify` request/response integration.

---

# Cross-instance Revocation

The required multi-instance security behavior is:

```text
1. User receives access token
          |
          v
2. Token verified on Instance A
          |
          v
      valid = true
          |
          v
3. Token revoked on Instance A
          |
          v
4. Revocation stored in Redis
          |
          v
5. Same token verified on Instance B
          |
          v
      401 Unauthorized
```

Revocation is checked before returning a cached successful verification result.

This prevents an old cached verification result from bypassing a newly created revocation.

---

# M1 Acceptance Criteria

| Requirement                                      | Status    |
| ------------------------------------------------ | --------- |
| Verify cache backed by Redis                     | Completed |
| Rate-limit counters backed by Redis              | Completed |
| Revocation/session runtime state backed by Redis | Completed |
| Shared state available across instances          | Completed |
| Cross-instance revocation proof                  | Completed |
| `/verify` contract preserved                     | Completed |
| `/verify` regression tests                       | Completed |

---

# Milestone 2 — Expanded RBAC Role Model

## Objective

The original Platform Service contained 8 roles.

Round 12+13 adds 10 specialized roles while preserving the existing role names and V1 permission mappings.

Total supported roles:

```text
8 V1 roles
+
10 V2 roles
=
18 roles
```

---

# Existing V1 Roles

These 8 roles are frozen for backward compatibility:

```text
ceo
vp_operations
procurement_manager
logistics_manager
compliance_officer
warehouse_manager
analyst
supplier
```

Their existing permission mappings must remain unchanged.

The frozen permission snapshot is:

```text
tests/fixtures/permissions_v1.json
```

The hierarchy snapshot is:

```text
tests/fixtures/role_hierarchy_v1.json
```

These snapshots protect the original behavior from accidental changes.

---

# New V2 Roles

The 10 new roles are:

```text
platform_admin
procurement_officer
inventory_planner
demand_planner
finance_manager
risk_analyst
data_scientist
auditor
warehouse_operator
carrier
```

---

# Role Definitions

| Role                  | Purpose                                        |
| --------------------- | ---------------------------------------------- |
| `ceo`                 | Existing executive role                        |
| `vp_operations`       | Existing operations leadership role            |
| `procurement_manager` | Existing procurement management role           |
| `logistics_manager`   | Existing logistics management role             |
| `compliance_officer`  | Existing compliance role                       |
| `warehouse_manager`   | Existing warehouse management role             |
| `analyst`             | Existing read-oriented analytical role         |
| `supplier`            | Existing external supplier role                |
| `platform_admin`      | Platform user and role administration          |
| `procurement_officer` | Purchase-order and supplier read operations    |
| `inventory_planner`   | Inventory planning                             |
| `demand_planner`      | Demand planning                                |
| `finance_manager`     | Invoice and payment approval                   |
| `risk_analyst`        | Supplier and risk analysis                     |
| `data_scientist`      | Model access, retraining and staging promotion |
| `auditor`             | Read-only audit and business-data access       |
| `warehouse_operator`  | Inventory movement                             |
| `carrier`             | External shipment visibility                   |

---

# Permission Catalogue

The executable permission catalogue is maintained in:

```text
app/core/permissions.py
```

The Platform Service provides permission information and authorization dependencies.

The consuming business service is responsible for enforcing the permission on its own endpoints.

| Permission               | Meaning                             | Expected Consumer            |
| ------------------------ | ----------------------------------- | ---------------------------- |
| `inventory:read`         | Read inventory                      | Inventory Service            |
| `inventory:write`        | Modify inventory                    | Inventory Service            |
| `inventory:plan`         | Perform inventory planning          | Inventory Service            |
| `inventory:move`         | Move inventory between locations    | Inventory Service            |
| `compliance:read`        | Read compliance data                | Compliance Service           |
| `compliance:write`       | Modify compliance data              | Compliance Service           |
| `supplier:read`          | Read supplier data                  | Supplier/Procurement Service |
| `supplier:write`         | Modify supplier data                | Supplier/Procurement Service |
| `logistics:read`         | Read logistics data                 | Logistics Service            |
| `logistics:write`        | Modify logistics data               | Logistics Service            |
| `purchase_order:create`  | Create purchase orders              | Procurement Service          |
| `purchase_order:read`    | Read purchase orders                | Procurement Service          |
| `purchase_order:approve` | Approve purchase orders             | Procurement Service          |
| `demand:read`            | Read demand data                    | Planning Service             |
| `demand:write`           | Modify demand data                  | Planning Service             |
| `invoice:read`           | Read invoices                       | Finance Service              |
| `invoice:approve`        | Approve invoices                    | Finance Service              |
| `payment:approve`        | Approve payments                    | Finance Service              |
| `risk:read`              | Read risk information               | Risk/Compliance Service      |
| `model:read`             | Read model information              | AI/Analytics Service         |
| `model:retrain`          | Retrain models                      | AI/Analytics Service         |
| `model:promote_staging`  | Promote a model to staging          | AI/Analytics Service         |
| `audit:read`             | Read audit information              | Platform/Audit consumers     |
| `user:read`              | Read platform users                 | Platform Service             |
| `user:manage`            | Create/update/manage platform users | Platform Service             |
| `role:assign`            | Assign roles to users               | Platform Service             |
| `shipment:read`          | Read shipment information           | Logistics/Shipment Service   |
| `inventory:move`         | Move inventory                      | Inventory Service            |

> **Note:** `model:promote_production` is a planned governance permission. It is **not assigned to any current role**. If it is not present in the executable `PERMISSIONS` set, it should remain documentation-only until implementation is added.

---

# Complete Role-Permission Matrix

The authoritative executable mapping is:

```text
app/core/permissions.py
```

The README matrix must remain synchronized with that implementation.

| Role                  | Permissions                                                                                                                                                           |
| --------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ceo`                 | `inventory:read`, `inventory:write`, `compliance:read`, `compliance:write`, `supplier:read`, `supplier:write`, `logistics:read`, `logistics:write`                    |
| `vp_operations`       | `inventory:read`, `inventory:write`, `compliance:read`, `compliance:write`, `supplier:read`, `supplier:write`, `logistics:read`, `logistics:write`                    |
| `procurement_manager` | `supplier:read`, `supplier:write`                                                                                                                                     |
| `logistics_manager`   | `logistics:read`, `logistics:write`                                                                                                                                   |
| `compliance_officer`  | `compliance:read`, `compliance:write`                                                                                                                                 |
| `warehouse_manager`   | `inventory:read`, `inventory:write`                                                                                                                                   |
| `analyst`             | `inventory:read`, `compliance:read`, `supplier:read`, `logistics:read`                                                                                                |
| `supplier`            | `supplier:read`, `supplier:write`                                                                                                                                     |
| `platform_admin`      | `audit:read`, `user:read`, `user:manage`, `role:assign`                                                                                                               |
| `procurement_officer` | `purchase_order:create`, `purchase_order:read`, `supplier:read`                                                                                                       |
| `inventory_planner`   | `inventory:read`, `inventory:plan`                                                                                                                                    |
| `demand_planner`      | `demand:read`, `demand:write`, `inventory:read`                                                                                                                       |
| `finance_manager`     | `invoice:read`, `invoice:approve`, `payment:approve`                                                                                                                  |
| `risk_analyst`        | `supplier:read`, `risk:read`                                                                                                                                          |
| `data_scientist`      | `model:read`, `model:retrain`, `model:promote_staging`                                                                                                                |
| `auditor`             | `audit:read`, `inventory:read`, `compliance:read`, `supplier:read`, `logistics:read`, `purchase_order:read`, `invoice:read`, `risk:read`, `model:read`, `demand:read` |
| `warehouse_operator`  | `inventory:read`, `inventory:move`                                                                                                                                    |
| `carrier`             | `shipment:read`                                                                                                                                                       |

---

# Platform Administrator

`platform_admin` is a platform-management role.

Permissions:

```text
audit:read
user:read
user:manage
role:assign
```

It intentionally has no business-data permissions.

For example, it does not automatically receive:

```text
inventory:*
supplier:*
logistics:*
purchase_order:*
invoice:*
payment:*
risk:*
model:*
shipment:*
```

Platform administration and business-data access remain separate responsibilities.

Any existing administrative endpoint protected by a V1 role such as:

```python
require_role("ceo")
```

must be reviewed explicitly before allowing `platform_admin`.

A new role does not automatically inherit V1 administrative privileges.

---

# Backward Compatibility

The following role strings remain unchanged:

```text
ceo
vp_operations
procurement_manager
logistics_manager
compliance_officer
warehouse_manager
analyst
supplier
```

Existing V1 permission mappings are frozen.

The V1 snapshot test compares the executable mappings against:

```text
tests/fixtures/permissions_v1.json
```

The hierarchy is separately protected by:

```text
tests/fixtures/role_hierarchy_v1.json
```

Adding V2 roles does not modify the V1 snapshot.

---

# Role Hierarchy

The existing hierarchy remains unchanged:

```text
CEO
 |
 +-- VP Operations
      |
      +-- Procurement Manager
      +-- Logistics Manager
      +-- Compliance Officer
      +-- Warehouse Manager
      +-- Analyst
      +-- Supplier
```

The actual implementation uses an explicit role-hierarchy mapping rather than automatically deriving hierarchy from the new permissions.

The new V2 roles are not automatically inserted into the existing V1 hierarchy.

Therefore, adding:

```text
carrier
warehouse_operator
finance_manager
```

does not automatically make those roles eligible for existing higher-level role checks.

---

# Unknown Roles

Unknown roles are denied by default.

Conceptually:

```text
Unknown role
     |
     v
No explicit role mapping
     |
     v
No permission
     |
     v
403 Forbidden
```

A new role must be explicitly added to both the role model and permission mapping before it can authorize an operation.

---

# External Roles and Data Scoping

Two roles represent external actors:

```text
supplier
carrier
```

RBAC permissions alone are not sufficient for external data isolation.

The consuming service must also enforce record-level scoping.

## Supplier

The existing supplier permissions are:

```text
supplier:read
supplier:write
```

The Supplier/Procurement service must ensure that a supplier can access only records belonging to its permitted supplier scope.

## Carrier

The current carrier permission is:

```text
shipment:read
```

The Logistics/Shipment service must restrict the carrier to shipments associated with that carrier.

The carrier must not automatically receive visibility into all platform shipments.

A future permission such as:

```text
shipment:update_status
```

can be introduced if the workflow requires it. It is not part of the current R12–13 executable role mapping.

---

# Auditor

The `auditor` role is read-only.

Current permissions:

```text
audit:read
inventory:read
compliance:read
supplier:read
logistics:read
purchase_order:read
invoice:read
risk:read
model:read
demand:read
```

The auditor does not receive:

```text
*:write
*:approve
inventory:move
purchase_order:create
model:retrain
model:promote_staging
user:manage
role:assign
```

This provides broad visibility without granting modification authority.

---

# Finance Separation of Duties

`finance_manager` currently has:

```text
invoice:read
invoice:approve
payment:approve
```

This intentionally keeps invoice and payment approval under one role for the current round.

This is a potential separation-of-duties concern for a future finance-control enhancement.

A future implementation may separate:

```text
invoice approval
```

from:

```text
payment approval
```

into distinct roles.

For R12–13, the current mapping remains explicit and documented rather than silently changing the V1 model.

---

# Model Governance

The current data-science workflow supports:

```text
model:read
model:retrain
model:promote_staging
```

Production promotion is treated as a governance-sensitive operation.

The planned permission is:

```text
model:promote_production
```

No current role receives this permission.

The intended future workflow is:

```text
Data Scientist
      |
      +--> model:retrain
      |
      +--> model:promote_staging
      |
      v
Governance Approval
      |
      v
model:promote_production
```

Production promotion should therefore not be automatically granted to `data_scientist`.

---

# Adoption Plan

The new permissions are additive.

Existing V1 roles are **not automatically expanded** to receive new permissions.

For example:

```text
ceo
```

continues to use the existing frozen V1 mapping even though the new RBAC model contains:

```text
purchase_order:approve
invoice:approve
payment:approve
```

The consuming services can adopt the new permissions when the corresponding business workflows are implemented and approved.

Examples:

| Existing Role         | Possible Future Permission               | Reason                     |
| --------------------- | ---------------------------------------- | -------------------------- |
| `ceo`                 | Selected approval/governance permissions | Executive workflows        |
| `vp_operations`       | Selected planning permissions            | Operations workflows       |
| `procurement_manager` | `purchase_order:*`                       | Procurement workflow       |
| `logistics_manager`   | `shipment:*`                             | Logistics workflow         |
| `compliance_officer`  | `audit:read`, `risk:read`                | Compliance workflow        |
| `warehouse_manager`   | `inventory:plan`, `inventory:move`       | Warehouse workflow         |
| `analyst`             | Additional read permissions              | Analytics                  |
| `supplier`            | Existing supplier permissions            | External supplier workflow |

These are adoption considerations, not changes to the frozen V1 mappings.

---

# Permission Enforcement

Fine-grained authorization uses:

```python
require_permission("permission:name")
```

Example:

```python
@router.post("/...")
def endpoint(
    current_user=Depends(
        require_permission("inventory:write")
    )
):
    ...
```

A user without the required permission receives:

```text
403 Forbidden
```

The Platform Service determines whether the authenticated role has the required permission.

The consuming service remains responsible for:

1. Applying the permission check.
2. Enforcing record-level data scope where required.
3. Applying additional business rules.

---

# M2 Tests

The RBAC implementation is protected by focused tests.

## V1 compatibility

Tests verify:

* All 8 V1 roles exist.
* V1 role strings are unchanged.
* V1 permission mappings are unchanged.
* V1 hierarchy is unchanged.
* New roles are not inserted into the V1 hierarchy.

## V2 role model

Tests verify:

* All 10 new roles exist.
* At least 18 roles exist.
* Every enum role has a permission mapping.
* Every mapped role exists in the role enum.
* Every permission assigned to a role is known.
* Each new role has an allowed permission.
* Each new role has a denied permission.

## Security boundaries

Tests cover:

```text
platform_admin
    -> platform permissions allowed
    -> business permissions denied

auditor
    -> read permissions allowed
    -> write permissions denied

carrier
    -> shipment:read allowed
    -> unrelated internal permissions denied

supplier
    -> supplier permissions preserved
    -> internal platform permissions denied
```

## Test Files

The RBAC tests are intentionally consolidated into focused files:

```text
tests/test_rbac_snapshot.py
tests/test_roles_and_permissions.py
tests/test_readme_permission_matrix.py
```

The snapshot fixtures remain:

```text
tests/fixtures/permissions_v1.json
tests/fixtures/role_hierarchy_v1.json
```

The README permission matrix is automatically checked against the executable permission mapping.

---

# Milestone 3 — Shared Event Publisher

## Objective

The Platform Service provides a common event-publishing helper for security-related events.

Implementation:

```text
app/core/event_publisher.py
```

The helper provides a consistent event envelope.

Conceptually:

```json
{
  "id": "uuid",
  "event_type": "platform.user.locked",
  "event_version": 1,
  "occurred_at": "2026-09-30T10:30:00Z",
  "producer": "platform-service",
  "payload": {
    "user_id": 123
  }
}
```

---

# Event Envelope

| Field           | Purpose                 |
| --------------- | ----------------------- |
| `id`            | Unique event identifier |
| `event_type`    | Event type              |
| `event_version` | Event schema version    |
| `occurred_at`   | UTC event timestamp     |
| `producer`      | Producing service       |
| `payload`       | Event-specific data     |

The envelope provides a consistent contract for future event consumers.

---

# Kafka

For R12–13, the Platform Service acts as an event producer.

The account-lock event is published to:

```text
platform.user.locked
```

The event type is:

```text
platform.user.locked
```

Example:

```json
{
  "id": "<uuid>",
  "event_type": "platform.user.locked",
  "event_version": 1,
  "occurred_at": "<UTC timestamp>",
  "producer": "platform-service",
  "payload": {
    "user_id": 123
  }
}
```

The Platform Service does not implement a consumer workflow for another service's Kafka events in this round.

---

# Account Lock Event

When repeated failed login attempts cause an account lock:

```text
Failed Login
      |
      v
Lockout Threshold
      |
      v
ACCOUNT_LOCKED
      |
      +-------------------+
      |                   |
      v                   v
 Audit Log           Kafka Event
                         |
                         v
                platform.user.locked
```

The account lock remains authoritative in the database.

Kafka is used for asynchronous event notification.

If event publication fails, the security-critical account lock must not be rolled back merely because Kafka is unavailable.

---

# Kafka vs Database Audit Log

These serve different purposes.

| Database Audit Log               | Kafka Event                              |
| -------------------------------- | ---------------------------------------- |
| Persistent security/audit record | Asynchronous event notification          |
| Used for audit/export            | Used by future consumers                 |
| Queryable by Platform Service    | Distributed through event infrastructure |
| Source for compliance reporting  | Source for event-driven workflows        |

The two mechanisms complement each other.

---

# Event Testing

M3 tests cover:

* Event envelope fields
* Unique event IDs
* UTC timestamps
* Payload preservation
* Event type
* Kafka publishing
* Account-lock event integration

Integration tests require the corresponding Kafka infrastructure.

---

# Shared Structured Logging

Implementation:

```text
app/core/logging_config.py
```

The Platform Service uses structured JSON logging.

Minimum request-log fields:

```text
timestamp
level
service
request_id
message
```

Request-specific fields may include:

```text
method
path
status
duration_ms
caller
caller_endpoint
```

Example:

```json
{
  "timestamp": "2026-09-30T10:30:00Z",
  "level": "INFO",
  "service": "platform-service",
  "request_id": "abc-123",
  "message": "HTTP request completed",
  "method": "POST",
  "path": "/api/v1/auth/verify",
  "status": 200,
  "duration_ms": 18.4
}
```

---

# Request ID

The middleware accepts:

```http
X-Request-ID: <request-id>
```

If the caller does not provide one, the Platform Service generates a request ID.

The request ID is:

* available to structured logs
* returned through the response header
* used to correlate requests across services

Response:

```http
X-Request-ID: <request-id>
```

---

# Sensitive Logging

The logging implementation must not log sensitive authentication values such as:

```text
passwords
raw access tokens
raw refresh tokens
raw API keys
OTP secrets
password-reset secrets
```

Security-sensitive operations should log safe identifiers and metadata instead.

---

# M3 Test Coverage

Tests cover:

* Event envelope creation
* Kafka event publishing
* Account-lock event integration
* Structured JSON logging
* Required request ID
* Required service name
* Request metadata
* Sensitive-value protection

---

# Local Development Infrastructure

The R12–13 development compose file is:

```text
docker-compose.dev.yml
```

It provides the local infrastructure required for the new shared runtime/event functionality.

Typical services:

```text
Redis :6379
Kafka :9092
```

Start development infrastructure:

```powershell
docker compose -f docker-compose.dev.yml up -d
```

Check:

```powershell
docker compose -f docker-compose.dev.yml ps
```

---

# Testing

Run the normal test suite:

```powershell
pytest -q
```

Run RBAC tests:

```powershell
pytest tests/test_rbac_snapshot.py tests/test_roles_and_permissions.py tests/test_readme_permission_matrix.py -v
```

Run integration tests:

```powershell
pytest -m integration -q
```

---

# R12–13 Acceptance Summary

| Milestone | Requirement                                | Status               |
| --------- | ------------------------------------------ | -------------------- |
| M1        | Redis-backed verify cache                  | Completed            |
| M1        | Redis-backed rate limiting                 | Completed            |
| M1        | Redis-backed revocation state              | Completed            |
| M1        | Shared state between instances             | Completed            |
| M1        | Cross-instance revocation proof            | Completed            |
| M1        | `/verify` contract preserved               | Completed            |
| M2        | 15+ roles                                  | Completed — 18 roles |
| M2        | Original 8 roles preserved                 | Completed            |
| M2        | Original permission mappings preserved     | Completed            |
| M2        | V1 permission snapshot                     | Completed            |
| M2        | V1 hierarchy snapshot                      | Completed            |
| M2        | Permission catalogue                       | Completed            |
| M2        | Role-permission matrix                     | Completed            |
| M2        | New-role allow/deny tests                  | Completed            |
| M2        | Platform-admin separation                  | Tested               |
| M2        | Auditor read-only boundary                 | Tested               |
| M2        | Supplier/carrier boundaries                | Tested               |
| M2        | External record-scoping requirement        | Documented           |
| M2        | Finance separation-of-duties consideration | Documented           |
| M2        | Model-governance boundary                  | Documented           |
| M3        | Shared event envelope                      | Completed            |
| M3        | Kafka event publishing                     | Completed            |
| M3        | Account-lock event                         | Completed            |
| M3        | Structured JSON logging                    | Completed            |
| M3        | Request-ID correlation                     | Completed            |

---

# Backward Compatibility Principle

The central R12–13 rule is:

```text
Existing consumers
       |
       v
Existing API contracts
       |
       v
Existing role names
       |
       v
Existing V1 permissions
       |
       v
Existing behavior preserved
```

The new Redis state, V2 roles, permissions, event publishing, and structured logging are additive.

Existing consuming services should not need to change their existing `/verify` authentication contract because of the R12–13 changes.
