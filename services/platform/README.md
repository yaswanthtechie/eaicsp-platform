# Platform Service

## Overview

The **Platform Service** is the authentication and authorization foundation of the EAICSP Supply Chain Management Platform.

The Platform Service centralizes authentication, authorization, user management, security auditing, session management, and service-to-service authentication so that every microservice does not need to implement its own security logic.

### Base URL

```text
http://127.0.0.1:8005
```

### API Prefix

```text
/api/v1
```
---

## Key Responsibilities

* User registration and secure password management
* Login with mock MFA (password + OTP)
* JWT access and refresh token management
* Refresh token rotation and revocation
* Role-Based Access Control (RBAC)
* Fine-grained permission management
* Account lockout and login brute-force protection
* Rate limiting and abuse detection
* Mock enterprise SSO integration
* Authentication audit logging
* Compliance-ready audit export
* Service-to-service JWT verification
* Service API-key authentication
* Token introspection caching
* Security and abuse monitoring dashboards

---

# Technology Stack

| Technology  | Purpose                         |
| ----------- | ------------------------------- |
| FastAPI     | REST API framework              |
| Python      | Backend language                |
| Pydantic    | Request/response validation     |
| SQLAlchemy  | ORM/database access             |
| Uvicorn     | ASGI server                     |
| PostgreSQL  | Production database             |
| SQLite      | Local development/demo database |
| python-jose | JWT creation and verification   |
| Passlib     | Password hashing utilities      |
| BCrypt      | Secure password hashing         |
| Pytest      | Automated testing               |

---

# Project Structure

```text
app/
├── main.py
├── database.py
├── seed.py
│
├── routes/
│   ├── auth_routes.py
│   ├── user_routes.py
│   └── admin_routes.py
│
├── schemas/
│   ├── auth.py
│   ├── user.py
│   └── admin.py
│
├── services/
│   ├── auth_service.py
│   ├── audit_service.py
│   ├── email_service.py
│   ├── audit_export_service.py
│   ├── mfa_service.py
│   ├── rate_limit_service.py
│   ├── sso_service.py
│
├── core/
│   ├── config.py
│   ├── security.py
│   ├── dependencies.py
│   ├── password_validator.py
│   ├── service_auth.py
│   ├── token_cache.py
│   ├── permissions.py
│   ├── verify_rate_limiter.py
│
├── models/
│   ├── auth_audit_logs.py
│   ├── abuse_event.py
│   ├── password_reset_tokens.py
│   ├── failed_login_attempts.py
│   ├── refresh_token.py
│   ├── roles.py
│   ├── users.py
│   ├── role_change_history.py
│   └── service_api_keys.py
│
└── middleware/
    └── logging.py

tests/
├── test_auth.py
├── test_integration.py
├── test_verify_load.py
```
---

# Configuration

Create a `.env` file for local development.

Example:

```env
SECRET_KEY=<strong-secret-key>
DATABASE_URL=sqlite:///./platform.db
TRUST_PROXY=false
```

# /verify load-test configuration
PLATFORM_BASE_URL=http://127.0.0.1:8005
ACCESS_TOKEN="<your-token>"
TOTAL_REQUESTS=150
CONCURRENCY=20
TIMEOUT_SECONDS=10

Production should use PostgreSQL and a securely managed secret.
The JWT signing secret must never be hardcoded in source code.
The ACCESS_TOKEN must be a valid user access token obtained after
successful MFA verification. Do not commit a real access token or
other secrets to source control.

The remaining load-test variables have the following defaults:

TOTAL_REQUESTS=150
CONCURRENCY=20
TIMEOUT_SECONDS=10
---

# Roles

The Platform Service supports organizational roles such as:

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

Roles are used for coarse-grained authorization.

For example:

```text
CEO
 └── VP Operations
      ├── Procurement Manager
      ├── Logistics Manager
      ├── Compliance Officer
      └── Warehouse Manager
```

The role hierarchy allows higher-level roles to inherit appropriate access where configured.

---

# Database

- The development environment uses SQLite.
- Production should use PostgreSQL.
Main tables include:

```text
users
roles
refresh_tokens
failed_login_attempts
password_reset_tokens
auth_audit_logs
role_change_history
service_api_keys
abuse_event
```
---

---


## Authentication Flow

```text
Client
  │
  │ username + password
  ▼
POST /api/v1/auth/login
  │
  ├── Validate credentials
  ├── Check account status / lockout
  └── Create MFA challenge
          │
          ▼
POST /api/v1/auth/mfa/verify
  │
  ├── Validate challenge
  ├── Validate OTP
  └── Issue JWT tokens
          │
          ├── Access Token
          └── Refresh Token
```

The login endpoint does not directly issue JWT tokens when MFA is enabled. It first creates an MFA challenge. After successful OTP verification, the Platform Service issues the access and refresh tokens.

---

# User Registration

## POST `/api/v1/auth/register`

to protected endpoints.

---

# User Registration

## POST `/api/v1/auth/register`

Registers a new user.

The request is validated using Pydantic.

Example:

```json
{
  "email": "supplier@company.com",
  "password": "StrongPassword@123",
  "full_name": "Supplier User"
}
```

Password requirements include:

* Minimum 12 characters
* At least one number
* At least one special character

The password is never stored as plain text.

It is hashed using Passlib/BCrypt before being stored in the database.

### Role assignment

A newly registered user can initially have:

```text
role_id = NULL
```

An administrator can assign the appropriate role later.

This prevents users from assigning privileged roles to themselves during registration.

The refresh token is marked as revoked in the database.

## Login and Multi-Factor Authentication

The current login flow uses MFA.

### Step 1 – Login

```text
POST /api/v1/auth/login
```

The user provides:

* Email
* Password

The Platform Service:

1. Validates the request.
2. Checks whether the account is active or locked.
3. Applies login rate limiting.
4. Verifies the password.
5. Creates an MFA challenge.
6. Sends a mock OTP.
7. Returns the MFA challenge ID.

Example response:

```json
{
  "mfa_required": true,
  "challenge_id": "<challenge-id>",
  "message": "OTP sent for verification"
}
```

At this stage, access and refresh tokens are **not returned yet**.

### Step 2 – MFA Verification

```text
POST /api/v1/auth/mfa/verify
```

The client sends:

```json
{
  "challenge_id": "<challenge-id>",
  "otp": "<mock-otp>"
}
```

After successful OTP verification, the Platform Service generates:

* Access token
* Refresh token

Example:

```json
{
  "access_token": "<access-token>",
  "refresh_token": "<refresh-token>",
  "token_type": "bearer"
}
```

### MFA Configuration

```text
OTP expiration: 5 minutes
MFA rate limit: 5 requests / 300 seconds
Abuse event: MFA_ABUSE
```

The current OTP implementation is a **mock MFA flow for development/testing**.

---

# Password Hashing

Passwords are not encrypted and stored for later decryption.

Instead:

```text
Plain Password
      |
      v
BCrypt hashing
      |
      v
Password Hash
      |
      v
Database
```

During login:

```text
Entered Password
      |
      v
BCrypt verification
      |
      v
Stored Hash
```

Passlib provides the password-hashing interface while BCrypt performs the password hashing.

Protected endpoints use FastAPI dependencies to extract and validate the JWT.

# JWT Authentication

Protected endpoints use FastAPI dependencies to extract and validate the JWT.

Example:

```http
Authorization: Bearer <access_token>
```

The service verifies:

* Signature
* Token expiration
* Token type
* User identity
* User account status

Invalid or expired tokens return:

```text
401 Unauthorized
```
---

# Refresh Tokens

## POST `/api/v1/auth/refresh`

Refresh tokens allow a client to obtain a new access token without requiring the user to log in again.

Flow:

```text
Refresh Token
      |
      v
Validate token
      |
      v
Check expiration
      |
      v
Check revocation
      |
      v
Revoke old refresh token
      |
      v
Generate new access token
      |
      v
Generate new refresh token
```

This is called **refresh-token rotation**.

The old refresh token cannot be reused after successful rotation.
---

# Refresh Token Replay Protection

If an already-used refresh token is presented again, the service treats it as a possible replay attack.

Example:

```text
Original Refresh Token
        |
        v
Used successfully
        |
        v
Old token revoked
```

If the same token is used again:

```text
Refresh Token
      |
      v
Already revoked
      |
      v
401 Unauthorized
```

This protects against stolen refresh-token reuse.
---

# Logout

## POST `/api/v1/auth/logout`

Logout invalidates the user's active refresh session/token.

The event is also recorded in the audit log.

Example audit event:

```text
TOKEN_REVOKED
```
---

# Current User

## GET `/api/v1/users/me`

Returns the currently authenticated user's information.

Example:

```json
{
  "id": 123,
  "email": "supplier@company.com",
  "full_name": "Supplier User",
  "role": "supplier",
  "is_active": true
}
```
---

# Role-Based Access Control

The Platform Service provides reusable role dependencies.

Examples:

```python
require_role("ceo")
```

```python
require_any_role("ceo", "vp_operations")
```

```python
require_all_roles(...)
```
a service can check:

This allows other services to use the same authorization pattern.

The authorization model becomes:

```text
GET /admin/users
        |
        v
require_any_role(
    "ceo",
    "vp_operations"
)
        |
        v
Allow / Deny
```

If the user is authenticated but does not have permission:

```text
403 Forbidden
```
---

# Fine-Grained Permissions

##  Permission Granularity

Roles provide coarse-grained authorization, but some operations require more specific permissions.

For example, instead of checking only:

```text
inventory_manager
```
a service can check:

```text
inventory:read
inventory:write
compliance:read
compliance:write
logistics:read
logistics:write
supplier:read
supplier:write
```

The authorization model becomes:

```text
User
  |
  v
Role
  |
  v
Permissions
  |
  +--> inventory:read
  +--> inventory:write
  +--> compliance:read
  +--> compliance:write
```

A permission dependency can be used conceptually as:

```python
require_permission("inventory:write")
```

# User Permissions

## GET `/api/v1/auth/me/permissions`

Returns the effective permissions available to the authenticated user.

Example:

```json
{
  "role": "warehouse_manager",
  "permissions": [
    "inventory:read",
    "inventory:write"
  ]
}
```
This endpoint is useful when a frontend or another service needs to understand what the current user is allowed to do.
---

# Login Rate Limiting

Repeated failed login attempts are restricted to reduce brute-force attacks.

Current policy:

```text
5 failed attempts
within 15 minutes
```

Rate limiting is tracked using:

* User/email
* Client IP address

The service records failed attempts in:

```text
failed_login_attempts
```

The request IP can use `X-Forwarded-For` when trusted proxy configuration is enabled.

After the configured threshold is reached, login requests can return:

```text
429 Too Many Requests
```
---

# Account Lifecycle

## Full Account Lifecycle

The Platform Service manages the complete user account lifecycle.

### Account Lockout

After repeated failed login attempts, an account can be locked.

Current policy:

```text
5 failed attempts
15-minute lockout period
```

The lockout event is recorded in the audit log.

Example:

```text
LOGIN_FAILED
LOGIN_FAILED
LOGIN_FAILED
LOGIN_FAILED
LOGIN_FAILED
       |
       v
ACCOUNT_LOCKED
```
---

# Forced Password Rotation

The Platform Service supports a forced password-change workflow.

This can be used when:

* An administrator forces a password reset
* A security incident occurs
* A password rotation policy requires a new password

The user must change their password before continuing normal authentication where the policy requires it.

---

# User Activation and Deactivation

Administrators can activate or deactivate accounts.

### Deactivation

```text
Admin
  |
  v
Deactivate User
  |
  +--> User becomes inactive
  |
  +--> Active refresh sessions revoked
  |
  +--> Security event recorded
```

This is the **deactivation cascade**.

The purpose is to ensure that disabling an account also invalidates its active sessions.

A deactivated user cannot continue normal access through protected endpoints.

---

# Admin User Management

Administrative operations are restricted to:

```text
ceo
vp_operations
```

Available operations include:

```text
GET    /api/v1/admin/test

GET    /api/v1/admin/users

POST   /api/v1/admin/users

PATCH  /api/v1/admin/users/{user_id}/deactivate

PATCH  /api/v1/admin/users/{user_id}/activate

PATCH  /api/v1/admin/users/{user_id}/role

GET    /api/v1/admin/users/{user_id}/role-history

POST   /api/v1/admin/users/{user_id}/force-reset-password
```

---

# Role Change History

Role changes are recorded for accountability.

Example:

```text
Admin
  |
  | Change role
  v
supplier
  |
  v
logistics_manager
```

The change is recorded with information such as:

```text
User
Previous role
New role
Administrator
Timestamp
```

Endpoint:

```text
GET /api/v1/admin/users/{user_id}/role-history
```

---

# Session Management

Administrators can view and revoke active refresh sessions.

Endpoints:

```text
GET
/api/v1/admin/users/{user_id}/sessions
```

```text
DELETE
/api/v1/admin/users/{user_id}/sessions/{session_id}
```

A revoked refresh session cannot be used to obtain new access tokens.

---

# Password Reset

Password reset uses a controlled reset-token workflow.

Endpoints:

```text
POST /api/v1/auth/password-reset/request
```

```text
POST /api/v1/auth/password-reset/reset
```

Reset tokens should be:

* Expiring
* Single-use
* Stored securely
* Invalidated after successful use

For local development, the reset token can be logged/mock-delivered instead of sending a real email.

---

# Audit Logging

Security-sensitive events are recorded in:

```text
auth_audit_logs
```

Examples include:

```text
LOGIN_SUCCESS
LOGIN_FAILED
LOGOUT
TOKEN_REVOKED
PASSWORD_RESET
PASSWORD_CHANGED
ACCOUNT_LOCKED
ROLE_CHANGED
USER_DEACTIVATED
USER_ACTIVATED
```

Audit logs help answer:

```text
Who performed the action?
What action happened?
Which user was affected?
When did it happen?
```

A revoked refresh session cannot be used to obtain new access tokens.

---

# Security Dashboard

##  Audit and Security Dashboard

Administrative security information is exposed through:

```text
GET /api/v1/admin/security-dashboard
```

Only authorized administrators can access the dashboard.

The dashboard provides security information such as:

* Failed login trends
* Active sessions
* Recent role changes
* Account lockout events
* Recent security activity

Conceptually:

```text
                 Security Dashboard
                         |
        +----------------+----------------+
        |                |                |
   Failed Logins   Active Sessions   Role Changes
        |
   Lockout Events
```

This gives administrators a central view of authentication-related activity.

---

# JWT Service-to-Service Verification

## POST `/api/v1/auth/verify`

This endpoint is specifically intended for service-to-service validation of a **user access JWT**.

It is different from:

```text
GET /api/v1/auth/me/permissions
```

because `/me/permissions` answers:

> "What permissions does the currently authenticated user have?"

while `/auth/verify` answers:

> "Is this access token valid, and who does it represent?"

Example request:

```http
POST /api/v1/auth/verify

Authorization: Bearer <access_token>
X-Caller-Service: inventory-service
X-Request-ID: <unique-request-id>
```

Example response:

### `/verify` Response

```json
{
  "valid": true,
  "user_id": 1,
  "email": "user@company.com",
  "full_name": "Example User",
  "role": "warehouse_manager",
  "supplier_id": null,
  "is_active": true,
  "permissions": [
    "inventory:read",
    "inventory:write"
  ]
}
```

The `/verify` endpoint validates the access token, checks the user's account status, and returns the authenticated user's identity, role, account status, and permissions.


This allows another service to validate a user token without implementing JWT verification logic independently.

---

# Example Microservice Interaction

```text
                     API Gateway
                          |
                          v
                    Platform Service
                    Authentication
                          |
          +---------------+---------------+
          |               |               |
          v               v               v
      Inventory       Logistics       Compliance
          |                               |
          +---------------+---------------+
                          |
                    Supplier Portal
```

Example:

```text
User
 |
 | Request inventory data
 v
API Gateway
 |
 v
Inventory Service
 |
 | Authorization: Bearer <user JWT>
 |
 | POST /auth/verify
 v
Platform Service
 |
 | Validate JWT
 | Return user identity + role
 v
Inventory Service
 |
 | Check inventory permission
 v
Return response
```

---

# API-Key Authentication

##  Service-to-Service API Keys

Pure machine-to-machine calls do not always need a user JWT.

The Platform Service therefore supports service API keys.

The two authentication mechanisms have different purposes:

| Authentication  | Used for                                    |
| --------------- | ------------------------------------------- |
| User JWT        | User-driven requests                        |
| Service API Key | Machine-to-machine/service-account requests |

---

# Service API-Key Model

Service keys are stored in:

```text
service_api_keys
```

The database stores the **hash**, not the raw API key.

Important fields include:

```text
id
service_name
key_hash
is_active
created_at
expires_at
last_used_at
created_by
```

A revoked key is represented by:

```text
is_active = false
```

not `is_revoked`.

---

# Creating a Service API Key

## POST `/api/v1/admin/service-keys`

Only:

```text
ceo
vp_operations
```

can issue service API keys.

Example request:

```json
{
  "service_name": "inventory-service",
  "expires_at": null
}
```

The Platform Service generates a key similar to:

```text
sk_<generated-secret>
```

The raw key is returned at creation time.

The database stores only its hash.

```text
Raw API Key
     |
     v
SHA-256 Hash
     |
     v
Database
```

The raw API key should be stored by the consuming service as a secret and should never be committed to source control.

---

# Listing Service API Keys

## GET `/api/v1/admin/service-keys`

Administrators can view service-key metadata.

The response should contain information such as:

```text
id
service_name
is_active
created_at
expires_at
last_used_at
```

The raw API key is **never returned again** after creation.

The key hash is also never exposed through the API.

---

# Revoking a Service API Key

## DELETE `/api/v1/admin/service-keys/{key_id}`

An administrator can revoke a service API key.

Flow:

```text
Admin
  |
  v
Revoke API Key
  |
  v
is_active = false
  |
  v
Future requests rejected
```

Example response:

```json
{
  "message": "Service API key revoked successfully",
  "key_id": 10
}
```

The revocation event is recorded in the audit log.

---

# Service API-Key Verification

## POST `/api/v1/auth/service-verify`

This endpoint validates a service API key.

Request:

```http
X-API-Key: sk_<service-secret>
```

Verification flow:

```text
X-API-Key
    |
    v
Hash API Key
    |
    v
Find matching key
    |
    v
Check is_active
    |
    v
Check expiration
    |
    v
Update last_used_at
    |
    v
Authenticate service
```

Example successful response:

```json
{
  "authenticated": true,
  "service": "inventory-service",
  "auth_type": "api_key"
}
```

Invalid or missing keys return:

```text
401 Unauthorized
```

## `/verify` Rate Limiting

Rate limiting is implemented for the `/api/v1/auth/verify` endpoint.

Current configuration:

| Endpoint              |        Limit |     Window |
| --------------------- | -----------: | ---------: |
| `/api/v1/auth/verify` | 100 requests | 60 seconds |

The caller service is identified using the `X-Caller-Service` header.

```text
service_api_keys
```

```text
X-Caller-Service: inventory
```

The rate-limit bucket is maintained per:

```text
caller_service + endpoint
```

If the `X-Caller-Service` header is missing, the caller is recorded as `unknown`.

When the limit is exceeded:

* HTTP `429 Too Many Requests` is returned.
* A `RATE_LIMIT_EXCEEDED` audit event is created.
* An abuse event is recorded.
* The response includes a `Retry-After` header.

Example:

```text
HTTP/1.1 429 Too Many Requests
Retry-After: 60
```


---
# Token Verification Caching

Multiple services may repeatedly call:

```text
POST /api/v1/auth/verify
```

for the same access token.

Without caching:

```text
Inventory
   |
   +--> /verify
   +--> /verify
   +--> /verify
   +--> /verify
           |
           v
      Platform Service
           |
           v
      JWT verification
```

This creates unnecessary repeated verification work.

A short-TTL in-memory cache can be used for repeated token introspection.

Example:

```text
Token
  |
  v
Cache lookup
  |
  +---- Cache hit ----> Return cached verification result
  |
  +---- Cache miss ---> Verify JWT
                           |
                           v
                       Store result
```
### Rate-Limit and Cache Ordering

The `/verify` rate limiter executes before the cache lookup.

Therefore, cached verification results cannot bypass `/verify`
rate limits.

The request flow is:

Request
   |
   v
/verify rate limiter
   |
   v
Cache lookup
   |
   +---- Cache hit ----> Return cached result
   |
   +---- Cache miss ---> JWT verification
                              |
                              v
                         Cache result

Current target TTL:

```text
60 seconds
```

The cache should be designed carefully around security-sensitive changes such as:

* Account deactivation
* Role changes
* Token revocation
* Expiration

A cache implementation must not allow stale authorization information to bypass important security controls.


- Token verification caching: /verify caches successful token verification results for up to 60 seconds, bounded by the JWT expiration time. Cache hits avoid re-decoding the JWT and repeating the database lookup. End-to-end latency improvement at single-request scale may be within measurement noise because HTTP/request-processing overhead can dominate the small in-process operation.

- Verified by test: Repeated cache hits skip JWT decoding, demonstrating that the cache removes repeated token-decoding work.

- Rate limiting: The /verify rate limiter runs before the cache lookup, so cache hits are still subject to per-service rate limiting through X-Caller-Service. This ensures caching cannot bypass /verify request protection.

# Admin Endpoints

Complete administrative endpoint set:

```text
GET    /api/v1/admin/test

GET    /api/v1/admin/users

POST   /api/v1/admin/users

PATCH  /api/v1/admin/users/{user_id}/activate

PATCH  /api/v1/admin/users/{user_id}/deactivate

PATCH  /api/v1/admin/users/{user_id}/role

GET    /api/v1/admin/users/{user_id}/role-history

POST   /api/v1/admin/users/{user_id}/force-reset-password

GET    /api/v1/admin/users/{user_id}/sessions

DELETE /api/v1/admin/users/{user_id}/sessions/{session_id}

GET    /api/v1/admin/audit-logs

GET    /api/v1/admin/security-dashboard

POST   /api/v1/admin/service-keys

GET    /api/v1/admin/service-keys

DELETE /api/v1/admin/service-keys/{key_id}

GET /api/v1/admin/audit/export

GET /api/v1/admin/abuse/dashboard
```
---

# Authentication Endpoints

```text
POST /api/v1/auth/register

POST /api/v1/auth/login

POST /api/v1/auth/refresh

POST /api/v1/auth/logout

POST /api/v1/auth/verify

POST /api/v1/auth/service-verify

GET  /api/v1/auth/me/permissions

POST /api/v1/auth/password-reset/request

POST /api/v1/auth/password-reset/reset

POST /api/v1/auth/mfa/verify

POST /api/v1/auth/sso/login
```
---

# User Endpoints

```text
GET /api/v1/users/me
```
---

# Request and Error Contract

The Platform Service uses standard HTTP status codes.

| Status | Meaning                               |
| ------ | ------------------------------------- |
| 200    | Successful request                    |
| 201    | Resource created                      |
| 400    | Invalid request/business condition    |
| 401    | Authentication failed/missing/expired |
| 403    | Authenticated but not authorized      |
| 404    | Resource not found                    |
| 409    | Resource conflict                     |
| 422    | Request validation failed             |
| 429    | Rate limit exceeded                   |
| 500    | Internal server error                 |
| 503    | Service unavailable                   |

The limit can be adjusted through configuration without changing the rate-limiting logic. For example:

```json
{
  "detail": "Invalid credentials"
}
```

Authentication failures should avoid revealing whether a specific account exists.

---
# Token Introspection Caching

# Integration Headers

For user-token service-to-service verification:

```http
Authorization: Bearer <access_token>
X-Caller-Service: inventory-service
X-Request-ID: <unique-request-id>
```

For service-account API-key authentication:

```http
X-API-Key: sk_<service-secret>
```

`X-Request-ID` helps correlate requests across microservices.

```text
Inventory
   |
   +--> /verify
   +--> /verify
   +--> /verify
   +--> /verify
           |
           v
      Platform Service
           |
           v
      JWT verification
```

# Example cURL

### Login

```bash
curl -X POST \
  http://127.0.0.1:8005/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=supplier@company.com&password=StrongPassword@123"
```

### Verify User JWT

```bash
curl -X POST \
  http://127.0.0.1:8005/api/v1/auth/verify \
  -H "Authorization: Bearer <access_token>" \
  -H "X-Caller-Service: inventory-service" \
  -H "X-Request-ID: request-123"
```

### Verify Service API Key

```bash
curl -X POST \
  http://127.0.0.1:8005/api/v1/auth/service-verify \
  -H "X-API-Key: sk_<service-secret>"
```

Example:

```env
SECRET_KEY=<generated-secret>
```

Never commit the real `.env` file or production secrets.

---

# Testing

Tests should cover both normal and security-sensitive scenarios.

## Authentication Tests

* Registration success
* Invalid registration data
* Duplicate email
* Successful login
* Wrong password
* Unknown user
* Inactive user
* Missing role
* Password validation
* JWT generation
* JWT expiration
* Tampered JWT
* Invalid token type

## Refresh Token Tests

* Valid refresh
* Expired refresh
* Revoked refresh
* Refresh-token rotation
* Replay of old refresh token
* Logout revocation

## RBAC Tests

* Authorized role
* Unauthorized role
* CEO hierarchy
* VP Operations access
* Multiple-role checks

## Permission Tests

* Permission granted
* Permission denied
* `inventory:read`
* `inventory:write`
* `compliance:read`
* `compliance:write`
* Role-to-permission mapping
* Backward-compatible role checks

## Account Lifecycle Tests 

* Failed-login counting
* Account lockout
* Lockout expiration
* Forced password reset
* Forced password rotation
* User deactivation
* Refresh-session revocation after deactivation
* Activated account behavior

## Security Dashboard Tests 

* Admin access
* Non-admin rejection
* Failed-login statistics
* Active sessions
* Role changes
* Lockout events

## Service API-Key Tests 

* API-key creation
* API-key hashing
* API-key verification
* Invalid API key
* Missing API key
* Expired API key
* Revoked API key
* `last_used_at` tracking
* API-key listing
* API-key revocation
* Service identity response

## Cache Tests

* Cache miss
* Cache hit
* TTL expiration
* Repeated-token verification
* Cache performance measurement
* Security-sensitive invalidation behavior where applicable

---

# Integration Testing

The integration test environment uses:

```text
http://127.0.0.1:8005
```

Run normal tests:

```bash
pytest -q
```

Run integration tests:

```bash
pytest -m integration -q
```

The default configuration excludes integration tests:

```toml
[tool.pytest.ini_options]
addopts = "-m 'not integration'"
```
---

## End-to-End Service Flow

```text
1. User registers with the Platform Service
        ↓
2. User submits username/password to /auth/login
        ↓
3. Platform validates credentials and creates MFA challenge
        ↓
4. User submits OTP to /auth/mfa/verify
        ↓
5. Platform issues Access Token + Refresh Token
        ↓
6. Client calls Inventory / Logistics / Compliance / Supplier services
        ↓
7. Calling service sends the Access Token to Platform /auth/verify
        ↓
8. Platform validates the token and returns user identity,
   role, account status, and permissions
        ↓
9. Calling service performs its business operation
```
---

# Logging

Application logging should include useful operational information such as:

```text
timestamp
request ID
endpoint
calling service
user ID where applicable
authentication result
event type
latency
```

Sensitive information must not be logged.

Do not log:

```text
Passwords
Raw JWTs
Raw API keys
Password reset secrets
```
---

# Concurrency and Performance

FastAPI/Uvicorn supports asynchronous request handling and concurrent connections.

The Platform Service should avoid unnecessary blocking operations in request paths.

Database connection management should be configured appropriately for production PostgreSQL deployments.

SQLite is suitable for local development but should not be treated as the production database for high-concurrency deployments.

---

# Completion Summary

The Platform Service evolves through the following improvements:

### Token Introspection Caching

```text
Repeated /verify calls
        |
        v
Short-TTL cache
        |
        v
Reduced repeated JWT verification work
```

### Fine-Grained Permissions

```text
Role
  |
  v
Permissions
  |
  +--> inventory:read
  +--> inventory:write
  +--> compliance:read
  +--> compliance:write
```

### Full Account Lifecycle

```text
Failed Login
     |
     v
Account Lockout
     |
     v
Password Rotation
     |
     v
Account Active/Inactive
     |
     v
Session Revocation
```

### Audit and Security Dashboard

```text
Audit Logs
    |
    v
Security Dashboard
    |
    +--> Failed Logins
    +--> Active Sessions
    +--> Role Changes
    +--> Lockouts
```

### Service-to-Service API Keys

```text
Admin
  |
  v
Issue Service Key
  |
  +--> Inventory
  |
  +--> Compliance
```
---

# Setup

Install dependencies:

Unit tests — run without requiring the Platform Service to be running.
Integration tests — make real HTTP requests to the running Platform Service on port 8005.
Run the default test suite
```bash
pip install -r requirements.txt
```

Start the service:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8005
```

Open Swagger:

```text
http://127.0.0.1:8005/docs
```

Open ReDoc:

```text
http://127.0.0.1:8005/redoc
```
---

# Startup Flow

The application startup process is approximately:

```text
Uvicorn
   |
   v
FastAPI
   |
   v
Load configuration
   |
   v
Initialize database
   |
   v
Create/load required data
   |
   v
Register routes
   |
   v
Service ready
```
---

# Service Dependency Model
Other EAICSP services should depend on the Platform Service for shared authentication capabilities rather than duplicating authentication logic.

```text
                 Platform Service
                 /              \
                /                \
         User Authentication   Service Authentication
                |                    |
                v                    v
          User JWT/RBAC        API Key Auth
                |                    |
       +--------+--------+           |
       |        |        |           |
   Inventory Logistics Compliance    |
                         |            |
                         +------------+
```
The business services remain responsible for their own domain logic.
For example:
```text
Platform
    -> Authentication / Authorization

Inventory
    -> Inventory stock/business logic

Logistics
    -> Shipment/logistics logic

Compliance
    -> Compliance screening/rules

Supplier Portal
    -> Supplier workflows
```
---

# Known Limitations

### In-memory token cache

The M1 cache is process-local when implemented in memory.

In a multi-worker or multi-instance production deployment, a shared cache such as Redis may be preferred.

The cache TTL and invalidation strategy must also account for security-sensitive events.

### SQLite

SQLite is intended for development/testing.

Production should use PostgreSQL.

### Email delivery

Password-reset email delivery may use a mock/local implementation during development.

Production should integrate with a secure email provider.
---

## Database Schema Update

The Platform Service introduced the following new columns to the `users` table:

* `locked_until`
* `password_changed_at`
* `password_expires_at`

These columns are required for the account lifecycle features, including:

* Account lockout
* Password expiration
* Forced password rotation

### Important: Existing Development Database

`Base.metadata.create_all()` creates missing tables, but it **does not alter an existing table** to add new columns.

Therefore, an existing `platform.db` created before these fields were introduced may fail with an error such as:

```text
sqlite3.OperationalError: no such column: users.locked_until
```

### Fresh Development Setup

If you are using the local SQLite development database and do not need to preserve its data, delete the existing database and restart the Platform Service.

For example:

```bash
del platform.db
```

Then start the service again:

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8005
```

The application will recreate the database schema with the latest `users` columns.

### If You Need to Preserve Existing Data

**Do not delete `platform.db`.**

A proper database migration should be used to add the new columns while preserving existing users and data.

For production or shared environments, a real migration tool such as Alembic should be used instead of deleting and recreating the database.

### Developer Checklist

After pulling the latest Platform Service changes:

1. Check whether your local database was created before the account-lifecycle changes.
2. If it is disposable development data, delete `platform.db`.
3. Restart the Platform Service.
4. Run the seed/setup process if required.
5. Run the test suite:

```bash
pytest -q
```

For integration tests:

```bash
pytest -m integration -q
```

> **Do not delete the database in shared, staging, or production environments. Use a database migration instead.**


# Summary

The Platform Service provides a centralized security foundation for EAICSP.

It handles:

```text
Registration
     |
     v
Login
     |
     v
MFA/OTP
     |
     v
JWT Access + Refresh Tokens
     |
     v
RBAC
     |
     v
Fine-Grained Permissions
     |
     v
Sessions
     |
     v
Account Lifecycle
     |
     v
Audit Logging
     |
     v
Security Dashboard
     |
     v
Service-to-Service JWT Verification
     |
     v
Service API-Key Authentication
     |
     v
Token Introspection Caching
```

This allows the other EAICSP microservices to focus on their business responsibilities while using a common authentication and authorization foundation.


## 1. Mock Enterprise SSO

A mock enterprise SSO integration has been added:

```text
Enterprise Identity
       ↓
Platform SSO
       ↓
Validate Provider + External ID
       ↓
Cross-check EAICSP User
       ↓
EAICSP JWT Tokens
```

Endpoint:

```text
POST /api/v1/auth/sso/login
```

Only identities matching the configured mock enterprise directory and an existing EAICSP user are allowed to authenticate.

SSO rate-limit violations are recorded as `SSO_ABUSE`.

---

## 2. Compliance-Ready Audit Export

Authentication and security events can be exported as CSV.

Endpoint:

```text
GET /api/v1/admin/audit/export
```

Supported filters:

```text
from_date
to_date
event_type
```

The export contains:

```text
timestamp
actor_id
actor_email
action
ip_address
details
```

Audit records are stored in:

```text
auth_audit_logs
```

Examples of tracked events include:

```text
LOGIN_SUCCESS
LOGIN_FAILED
TOKEN_REVOKED
PASSWORD_RESET
ACCOUNT_LOCKED
ROLE_CHANGED
SERVICE_KEY_CREATED
SERVICE_KEY_REVOKED
```
Audit export access is restricted to:

```text
ceo
vp_operations
```
---

## 3. Abuse Detection and Rate Limiting

This introduces centralized abuse-event tracking through:

```text
abuse_event
```

Tracked abuse types include:

```text
RATE_LIMIT_EXCEEDED
LOGIN_BRUTE_FORCE
MFA_ABUSE
SSO_ABUSE
```
---

### Abuse Dashboard

Endpoint:

```text
GET /api/v1/admin/abuse/dashboard
```
---

The dashboard provides:

```text
Total abuse events
Rate-limit violations
MFA abuse events
Login abuse events
SSO abuse events
Suspicious IPs
Top IP addresses
Top endpoints
```

## 4. `/verify` Combined Call-Graph Load Test

The load test represents the current dependent-service call graph:

```text
Inventory   ──→ Platform /verify
Supplier    ──→ Platform /verify
Compliance  ──→ Platform /verify
```
---

Each dependent service sends the user's access token to the Platform Service for centralized JWT verification.

### Test Configuration

```text
Total requests : 150
Concurrency    : 20
Callers        : inventory, supplier, compliance
Endpoint       : POST /api/v1/auth/verify
```

The test measures:

```text
Success/failure rate
HTTP status codes
Throughput
Average latency
Median latency
P95 latency
P99 latency
Maximum latency
Per-service results
```

### Manual `/verify` Testing

First, obtain an access token after successful MFA verification.

Set the token in PowerShell:

```powershell
$env:ACCESS_TOKEN="<your_access_token>"
```

To verify that the environment variable is set:

```powershell
echo $env:ACCESS_TOKEN
```

Then call the Platform `/verify` endpoint:

```powershell
curl.exe -X POST "http://127.0.0.1:8005/api/v1/auth/verify" `
  -H "Authorization: Bearer $env:ACCESS_TOKEN" `
  -H "Content-Type: application/json" `
  -H "X-Caller-Service: inventory"
```

The `X-Caller-Service` header identifies the dependent service making the verification request.

Example callers:

```text
X-Caller-Service: inventory
X-Caller-Service: supplier
X-Caller-Service: compliance
```

Expected response:

```json
{
  "valid": true,
  "user_id": 1,
  "email": "user@company.com",
  "full_name": "Example User",
  "role": "warehouse_manager",
  "supplier_id": null,
  "is_active": true,
  "permissions": [
    "inventory:read",
    "inventory:write"
  ]
}
```

### Automated Load Test

The automated load test is implemented in:

```text
tests/test_verify_load.py
```

Run it with:

```powershell
pytest tests/test_verify_load.py -s
```

The Platform Service must be running on:

```text
http://127.0.0.1:8005
```

The load test sends requests using the three current callers:

```text
Inventory
Supplier
Compliance
```

The caller is identified through:

```http
X-Caller-Service
```

### Latest Test Result

```text
Total requests      : 150
Successful          : 150
Failed              : 0
Success rate        : 100.00%
Total test time     : 1.598 sec
Throughput          : 93.86 requests/sec
Average latency     : 122.72 ms
Median latency      : 90.68 ms
P95 latency         : 321.97 ms
P99 latency         : 385.78 ms
Maximum latency     : 437.66 ms
HTTP 200            : 150
```
### Caller Results

```text
Inventory   : 50/50 successful
Supplier    : 50/50 successful
Compliance  : 50/50 successful
```

These results were obtained in the local development environment using the configured test parameters. They provide a functional and baseline performance measurement and should not be interpreted as production capacity benchmarks.

### Security and Rate-Limit Behavior

The `/verify` endpoint is rate-limited to:

```text
100 requests / 60 seconds
```

The rate-limit bucket is maintained per:

```text
caller_service + endpoint
```

For example:

```text
inventory + /api/v1/auth/verify
supplier  + /api/v1/auth/verify
compliance + /api/v1/auth/verify
```

If a caller exceeds its configured limit, the Platform Service returns:

```text
HTTP 429 Too Many Requests
```

and records the corresponding security/abuse event.

The rate limiter executes before the token-cache lookup, so cached verification results cannot bypass `/verify` rate limiting.

### Access Token Security

Use a valid access token obtained after successful MFA verification when performing manual tests.

For documentation, use only a placeholder or clearly fake/truncated token:

```powershell
$env:ACCESS_TOKEN="<your_access_token>"
```

Do not commit a real access token to GitHub or any other source-control repository. A valid unexpired token could potentially be used to authenticate requests.

---

## 5. Swagger Authentication

Swagger/OpenAPI uses the configured FastAPI authentication scheme.

For protected endpoints such as `/auth/verify`, provide the issued access token using:

Authorization: Bearer <access_token>

The access token must be obtained after successful MFA verification.

The Swagger authentication configuration must match the security dependency used by the Platform Service.

**Centralized authentication, authorization, security, auditing, and service-to-service identity verification.**
