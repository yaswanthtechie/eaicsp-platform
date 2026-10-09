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
* Optional mock MFA (password + OTP)
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
├── services/
│   ├── auth_service.py
│   ├── audit_service.py
│   ├── email_service.py
│   ├── audit_export_service.py
│   ├── mfa_service.py
│   ├── rate_limit_service.py
│   ├── sso_service.py
│   ├── abuse_dashboard_service.py
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
├── fixtures/
│   ├──role_hierarchy_v1.json
│   ├──permissions_v1.json
├── test_auth.py
├── test_integration.py
├── test_security.py
├── test_rbac_snapshot.py
├── test_roles_and_permissions.py
├── test_new_roles_assignable.py
├── test_readme_permission_matrix.py

scripts/
├── load_test_verify.py
├── dump_permissions.py

```
---

# Configuration

Create a `.env` file for local development.

Example:

```env
SECRET_KEY=<strong-secret-key>
DATABASE_URL=sqlite:///./platform.db
TRUST_PROXY=false
# MFA
MFA_ENABLED=false
MFA_MOCK_OTP=
# Mock enterprise SSO
MOCK_SSO_ENABLED=false
# Required only when MOCK_SSO_ENABLED=true: at least 32 random characters.
# Generate one with:  python -c "import secrets; print(secrets.token_urlsafe(48))"
# Never commit a real value, and never reuse an example value.
MOCK_SSO_SECRET=
```

# /verify load-test configuration
PLATFORM_BASE_URL=http://127.0.0.1:8005
# For real testing, provide 5-10 different valid access tokens locally.
ACCESS_TOKENS="token1,token2,token3,token4,token5"
# Used by the sustained load-test script
DURATION_SECONDS=120
CONCURRENCY=20
REQUESTS_PER_SECOND=5
TIMEOUT_SECONDS=10

Mock SSO is disabled by default.

When MOCK_SSO_ENABLED=true, MOCK_SSO_SECRET is required and must be at least
32 characters long. The application fails at startup if the secret is missing,
blank, or shorter than 32 characters.

The SSO verification path also rejects a weak secret at runtime with HTTP 503.
This prevents forged assertions from being accepted with an empty or weak key.

Example:

MOCK_SSO_ENABLED=true
MOCK_SSO_SECRET=

Production should use PostgreSQL and a securely managed secret.
The JWT signing secret must never be hardcoded in source code.
The ACCESS_TOKENS must be a valid user access token obtained after
successful MFA verification. Do not commit a real access token or
other secrets to source control.

The remaining load-test variables have the following defaults:

CONCURRENCY=20
TIMEOUT_SECONDS=10
DURATION_SECONDS=120
REQUESTS_PER_SECOND=5
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

When MFA_ENABLED=false:

POST /api/v1/auth/login
  │
  ├── Validate credentials
  └── Issue JWT access + refresh tokens
```

The login endpoint does not directly issue JWT tokens when MFA is enabled. It first creates an MFA challenge. After successful OTP verification, the Platform Service issues the access and refresh tokens.

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

The login flow supports optional mock MFA. MFA is enabled only when MFA_ENABLED=true.

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
MFA_FAILED
MFA_VERIFIED
SSO_REJECTED
SSO_LOGIN
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
  "service": "compliance-service",
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
X-Caller-Service: compliance
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
  -H "X-Caller-Service: compliance-service" \
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

## MFA Tests
* test_login_without_mfa_still_returns_tokens
* test_mfa_end_to_end_and_audited
* test_challenge_destroyed_after_max_wrong_attempts
* test_otp_is_random_when_no_mock_otp

## Rate Limiting Tests
* test_rate_limit_is_per_ip_not_global
* test_changing_caller_header_does_not_reset_the_limit
* test_rejected_requests_write_one_audit_row_per_window
* test_login_brute_force_shows_on_abuse_dashboard
* test_login_request_does_not_clear_an_active_mfa_bucket

## SSO Tests
* test_sso_accepts_signed_assertion_and_is_audited
* test_sso_rejects_assertion_signed_with_wrong_secret
* test_sso_rejects_plain_client_fields
* test_sso_disabled_by_default
* test_sso_refuses_blank_secret
* test_env_example_does_not_ship_a_usable_sso_secret
* test_sso_refuses_a_locked_account

## Audit Export / Abuse Dashboard Tests
* test_audit_export_has_compliance_columns
* test_supplier_cannot_export_or_view_abuse_dashboard
* test_audit_export_limit_is_applied
* test_audit_export_json_format
* test_audit_export_csv_neutralises_formulas
* test_login_brute_force_shows_on_abuse_dashboard

## Account Lockout Security Tests

* test_locked_user_with_valid_token_gets_401_not_500
* test_sso_refuses_a_locked_account
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


## Running the Dev Stack

Run these commands from the `services/platform/` directory.

Start Redis and Kafka:

```bash
docker compose -f docker-compose.dev.yml up -d
```

Run unit tests (no Docker services required):

```bash
pytest -q
```

Run integration tests (Redis and Kafka containers required):

```bash
pytest -m integration -rs
```

Run the Milestone 1 cross-instance revocation proof:

```bash
python scripts/two_instance_revocation_check.py
```

**M1 completion evidence:** Save the successful proof-script output and include it in the README and pull request. Mark M1 complete only after the script passes.

---

## End-to-End Service Flow

```text
1. User registers with the Platform Service
        ↓
2. User submits username/password to /auth/login
        ↓
3. Platform validates credentials
        ↓
4.MFA_ENABLED?
      /       \
    YES        NO
     ↓          ↓
 Create MFA    Issue JWT
 Challenge
     ↓
 OTP Verify
     ↓
 Issue JWT
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

### Redis-backed authentication state

The verification cache, rate-limit counters, and token-revocation state use Redis so that multiple Platform Service instances can share authentication state. All instances must be configured with the same `REDIS_URL`.

Redis availability and connectivity remain operational dependencies. The service must handle Redis errors appropriately, especially for security-sensitive revocation checks.

### MFA challenge storage

If MFA challenges are still stored in process memory, they are not shared between instances and are lost when the service restarts. A shared Redis or database-backed challenge store is needed to provide cross-instance persistence for MFA challenges.


### SQLite

SQLite is intended for development/testing.

Production should use PostgreSQL.

### Email delivery

Password-reset email delivery may use a mock/local implementation during development.

Production should integrate with a secure email provider.

* **MFA challenge storage:** MFA challenges are currently stored in memory. They are lost when the Platform Service restarts and are not shared between multiple Platform Service instances. A production deployment should use a shared store such as Redis or a database-backed challenge store.
* **SSO trust model:** The current SSO implementation uses a signed mock enterprise assertion for development/testing. It does not integrate with a real enterprise Identity Provider (IdP). Production SSO should use a properly configured and validated enterprise IdP with appropriate issuer, audience, signature, expiry, and MFA/assurance (`amr`) validation.
* **`MFA_MOCK_OTP`:** `MFA_MOCK_OTP` is provided only for local development/testing. It must not be used as a fixed OTP mechanism in production. Production MFA should use a real secure OTP generation and delivery mechanism.
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

## Round 9 to 11 Status

| Milestone                           | Status   | Notes                                                                                               |
| ----------------------------------- | -------- | --------------------------------------------------------------------------------------------------- |
| **M1 MFA (mock)**                   | **Done** | MFA is opt-in via `MFA_ENABLED`; OTP delivery is mocked                                             |
| **M2 SSO stub**                     | **Done** | Signed short-lived mock assertion; no real IdP                                                      |
| **M3 Audit export**                 | **Done** | CSV export includes outcome and supports paging                                                     |
| **M4 Rate limit + abuse dashboard** | **Done** | Rate-limit violations plus MFA/SSO/login abuse signals are tracked                                  |
| **M5 /verify load test**            | **Done** | Sustained 120-second run with multiple tokens, real caller services, and 429 threshold demonstrated |

**M5 Load Test Note:** `/verify` was also tested at **2, 3, 5, and 10 requests/sec**. The 5 req/sec test achieved **98.83% success**, while the 10 req/sec test confirmed the rate limiter by returning controlled **429 responses** after the configured limit was reached.


# Summary

The Platform Service provides a centralized security foundation for EAICSP.

It handles:

```text
Registration
     |
     v
Login
     |
     +---- MFA enabled ----> MFA/OTP
     |                         |
     |                         v
     +---- MFA disabled ----> JWT
                               |
                               v
                    Access + Refresh Tokens
                               |
                               v
                             RBAC
                               |
                               v
                    Fine-Grained Permissions
                               |
                               v
                         Session Management
                               |
                               v
                       Account Lifecycle
                               |
                               v
                         Audit Logging
                               |
                               v
                     Security Monitoring
                               |
                               v
                  Service-to-Service Verification
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
Signed Short-Lived SSO Assertion
       ↓
Platform verifies signature
       ↓
Validate issuer + audience + expiry
       ↓
Extract identity from verified assertion
       ↓
Cross-check EAICSP User
       ↓
EAICSP JWT Tokens
```

Endpoint:

```text
POST /api/v1/auth/sso/login
```

The Platform Service does not trust client-supplied email, full_name, or external_id values. Identity information is derived only from the verified signed assertion. The assertion is short-lived and validated for signature, issuer, audience, and expiration before the EAICSP user is identified.

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
limit
offset
```

The export contains:

```text
timestamp
actor_id
actor_email
action
outcome
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
MFA_FAILED
MFA_VERIFIED
SSO_REJECTED
SSO_LOGIN
```
The abuse/security dashboard also monitors authentication failure
signals such as repeated MFA_FAILED and SSO_REJECTED events per IP,
in addition to explicit rate-limit abuse events.
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
API-Gateway    ──→ Platform /verify
Supplier-Portal   ──→ Platform /verify
Compliance  ──→ Platform /verify
```
---

Each dependent service sends the user's access token to the Platform Service for centralized JWT verification.

### Test Configuration

```text
Duration       : 120 seconds
Concurrency    : 20
Tokens         : 5
Callers        : api gateway, supplier portal, compliance
Target rate    : 5 requests/sec

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
$env:ACCESS_TOKENS="token1,token2,token3,token4,token5"
```

To verify that the environment variable is set:

```powershell
echo $env:ACCESS_TOKENS
```

Then call the Platform `/verify` endpoint:

```powershell
curl.exe -X POST "http://127.0.0.1:8005/api/v1/auth/verify" `
  -H "Authorization: Bearer $env:ACCESS_TOKENS" `
  -H "Content-Type: application/json" `
  -H "X-Caller-Service: compliance"
```

The `X-Caller-Service` header identifies the dependent service making the verification request.

Example callers:

```text
X-Caller-Service: api-gateway
X-Caller-Service: supplier-portal
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
scripts/load_test_verify.py
```

Run it with:

```powershell
python scripts/load_test_verify.py
```

The Platform Service must be running on:

```text
http://127.0.0.1:8005
```

The load test sends requests using the three current callers:

```text
Api-Gateway
Supplier-Portal
Compliance
```

The caller is identified through:

```http
X-Caller-Service
```

Starting sustained /verify load test...
----------------------------------------
Platform URL       : http://127.0.0.1:8005
Verify endpoint    : http://127.0.0.1:8005/api/v1/auth/verify
Duration            : 120 seconds
Concurrency         : 20
Target rate         : 5.00 requests/sec
User tokens         : 5
Caller services     : supplier-portal, compliance, api-gateway
----------------------------------------

======================================================================
/VERIFY SUSTAINED LOAD TEST REPORT
======================================================================

TEST CONFIGURATION
----------------------------------------------------------------------
Endpoint              : http://127.0.0.1:8005/api/v1/auth/verify
Duration              : 120.00 seconds
Configured duration   : 120 seconds
Concurrency           : 20
Target request rate   : 5.00 requests/sec
Different tokens      : 5
Caller services       : supplier-portal, compliance, api-gateway

OVERALL RESULTS
----------------------------------------------------------------------
Total requests        : 600
Successful requests   : 593
Failed requests       : 7
Success rate          : 98.83%
Failure rate          : 1.17%
Total test time       : 120.00 seconds
Actual throughput     : 5.00 requests/sec

HTTP STATUS CODES
----------------------------------------------------------------------
200        : 593
429        : 7

429 RATE-LIMIT ANALYSIS
----------------------------------------------------------------------
Total 429 responses   : 7
First 429 after       : 60.07 seconds
First 429 request     : #301
First 429 caller      : supplier-portal
First 429 token       : token-1

CALLER SERVICE DISTRIBUTION
----------------------------------------------------------------------
supplier-portal    requests=200    success=197    failed=3      429=3      success_rate=98.50%
compliance         requests=200    success=198    failed=2      429=2      success_rate=99.00%
api-gateway        requests=200    success=198    failed=2      429=2      success_rate=99.00%

TOKEN DISTRIBUTION
----------------------------------------------------------------------
token-1   : 120 requests
token-2   : 120 requests
token-3   : 120 requests
token-4   : 120 requests
token-5   : 120 requests

LATENCY
----------------------------------------------------------------------
Min latency           : 4.66 ms
Average latency       : 16.96 ms
Median latency        : 17.43 ms
P95 latency           : 29.46 ms
P99 latency           : 54.79 ms
Max latency           : 128.32 ms

FAILURE DETAILS
----------------------------------------------------------------------
Request #301 | caller=supplier-portal | token=token-1 | status=429 | time=60.07s | error={"detail":"Too many requests. Please try again later."}
Request #302 | caller=compliance | token=token-2 | status=429 | time=60.26s | error={"detail":"Too many requests. Please try again later."}
Request #303 | caller=api-gateway | token=token-3 | status=429 | time=60.44s | error={"detail":"Too many requests. Please try again later."}
Request #304 | caller=supplier-portal | token=token-4 | status=429 | time=60.62s | error={"detail":"Too many requests. Please try again later."}
Request #305 | caller=compliance | token=token-5 | status=429 | time=60.83s | error={"detail":"Too many requests. Please try again later."}
Request #306 | caller=api-gateway | token=token-1 | status=429 | time=61.02s | error={"detail":"Too many requests. Please try again later."}
Request #307 | caller=supplier-portal | token=token-2 | status=429 | time=61.24s | error={"detail":"Too many requests. Please try again later."}

FINAL RESULT
----------------------------------------------------------------------
ATTENTION: Rate limiting was triggered.
Use the first-429 timing and per-caller 429 counts when evaluating the /verify limit.
======================================================================
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
api gateway + /api/v1/auth/verify
supplier portal  + /api/v1/auth/verify
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
$env:ACCESS_TOKENS="token1,token2,token3,token4,token5"
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




# Round 12+13

| Milestone                                |          Status         |
| ---------------------------------------- | -------------- |
| M1 Redis-backed shared auth state        |Done (see M1 proof below)|
| M2 15+ role model                        |    Done        |
| M3 Event publishing / structured logging |    Done       |

# Round 12+13 Status

| Milestone | Status |
|---|---|
| M1 Redis-backed shared auth state | Done (see M1 proof below) |
| M2 15+ role model | Done |
| M3 Event publishing / structured logging | Done (see M1 proof below) |

# Milestone 1 - Redis-Backed Shared Authentication State

The Platform Service moves security-sensitive runtime state from process-local
memory to Redis so that multiple Platform Service instances can share the
same authentication state.

## Redis Responsibilities

The following state is backed by Redis:

```text
Verify-token cache
Rate-limit counters
Session/revocation state
User-level token invalidation state
```

Redis provides shared state across Platform Service instances. This prevents
an authentication decision from depending on which instance receives the
request.

### Verify Cache

The `/api/v1/auth/verify` endpoint uses the Redis-backed verification cache.

The cache stores the verification result for a token with a bounded TTL.
The TTL does not exceed the remaining lifetime of the JWT.

The `/verify` response contract remains unchanged.

### Rate Limiting

Security-sensitive rate-limit counters are stored in Redis so that limits
are shared across instances.

This prevents a caller from bypassing a rate limit by sending requests to
different Platform Service instances.

### Token Revocation and User Invalidation

Token and user-level invalidation state is shared through Redis.

For example:

```text
Platform Instance A
       |
       | revoke / invalidate
       v
     Redis
       |
       v
Platform Instance B
       |
       | /api/v1/auth/verify
       v
    Token rejected
```

A token revoked or invalidated through one Platform Service instance must
therefore be rejected when the same token is verified by another instance
using the same Redis backend.

### Cross-Instance Revocation Proof

The R12+13 validation includes a two-instance test:

1. Start Platform Service instance A.
2. Start Platform Service instance B.
3. Authenticate and obtain a valid access token.
4. Confirm the token can be verified.
5. Revoke/invalidate the token through instance A.
6. Send the same token to `/api/v1/auth/verify` through instance B.
7. Confirm that instance B rejects the revoked token.

This proves that revocation state is shared through Redis rather than stored
only in the memory of one Platform Service process.

### `/verify` Contract

Redis is an implementation detail and does not change the existing `/verify`
API contract.

The endpoint continues to return the existing verification response and
authentication errors while using Redis for shared runtime state.

## M1 Tests

The Redis-backed authentication state is protected by tests covering:

* `tests/test_redis_auth_state.py`: logout revokes the token for /verify AND
  the platform's own endpoints; logout returns 503 (not 200) when Redis
  cannot store the revocation; account lock publishes one
  platform.user.locked event; a failed publish does not undo the lock.
* `tests/test_event_publisher.py`: standard envelope (event_id ...),
  topic == event_type, never raises when Kafka is down.
* `tests/test_two_instance_revocation.py` (integration): two real
  instances, one Redis; a token logged out on A is rejected by B.

## Milestone 1 Acceptance

Milestone 1 is complete when:

```text
Verify cache uses Redis
        +
Rate-limit state uses Redis
        +
Revocation/invalidation state uses Redis
        +
Instance A revokes a token
        +
Instance B rejects the same token
        +
/verify contract remains unchanged
        +
Redis-backed tests pass
```

18 passed

50.86 seconds · 0 failures

PASS
Account-lock event publishing

Passed

Kafka event publisher

Passed

HTTP authentication and verification

15 passed

Cross-instance revocation

Passed

python scripts/two_instance_revocation_check.py
Database seeded successfully.
B /verify before logout (expect 200): 200
A /logout (expect 200): 200
B /verify after logout on A (expect 401): 401
B /me/permissions after logout on A (expect 401): 401
PASS: revocation is shared across instances

---

# Milestone 2 - Expanded RBAC Role Model

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

This milestone focuses on the RBAC role model. Redis-backed authentication state is covered by Milestone 1, and shared event publishing and structured logging are covered by Milestone 3.

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

Their existing permission mappings remain unchanged.

The frozen permission snapshot is:

```text
tests/fixtures/permissions_v1.json
```

The frozen hierarchy snapshot is:

```text
tests/fixtures/role_hierarchy_v1.json
```

These snapshots protect the original V1 behavior from accidental changes.

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

All 10 new roles are included in the executable role model and are seeded into the `roles` table.

For existing databases, run once:

```bash
python -m app.seed --roles-only
```

This adds any missing roles without recreating the existing seed users.

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

`model:promote_production` is a planned governance permission. It is not part of the current executable `PERMISSIONS` set and is not assigned to any current role. It should not be added to the role-permission matrix until its implementation and authorization workflow are introduced.

---

# Complete Role-Permission Matrix

The executable mapping is maintained in:

```text
app/core/permissions.py
```

The following matrix documents all 18 executable roles and must remain synchronized with that mapping.

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

Its permissions are:

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

Administrative endpoints protected by existing V1 role checks must be reviewed explicitly before allowing `platform_admin`.

A new role does not automatically inherit V1 administrative privileges.

Where appropriate, administrative endpoints can use permission-aware authorization so that:

* existing `ceo` and `vp_operations` access is preserved through the existing role hierarchy;
* `platform_admin` access is granted through `user:manage` or `role:assign`;
* unrelated roles remain denied.

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

The V1 permission snapshot is:

```text
tests/fixtures/permissions_v1.json
```

The V1 hierarchy snapshot is:

```text
tests/fixtures/role_hierarchy_v1.json
```

Adding V2 roles does not modify either V1 snapshot.

The frozen permission-generation script refuses to overwrite the existing V1 baseline unless explicitly invoked with its force option.

---

# Role Hierarchy

The existing V1 hierarchy remains unchanged.

The executable implementation uses an explicit set-based hierarchy in:

```text
app/core/dependencies.py
```

Conceptually, the existing V1 role scopes are:

```text
ceo
  -> ceo
  -> vp_operations
  -> procurement_manager
  -> logistics_manager
  -> compliance_officer
  -> warehouse_manager
  -> analyst
  -> supplier

vp_operations
  -> vp_operations
  -> procurement_manager
  -> logistics_manager
  -> compliance_officer
  -> warehouse_manager
  -> analyst
  -> supplier

procurement_manager
  -> procurement_manager

logistics_manager
  -> logistics_manager

compliance_officer
  -> compliance_officer

warehouse_manager
  -> warehouse_manager

analyst
  -> analyst

supplier
  -> supplier
```

The new V2 roles are intentionally not inserted into this V1 hierarchy.

Therefore, a V2 role such as:

```text
carrier
warehouse_operator
finance_manager
```

does not automatically satisfy an existing V1 higher-level role check.

Likewise, adding a permission to a V2 role does not automatically grant that role a V1 hierarchical position.

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

A new role must be explicitly added to the role model and permission mapping before it can authorize an operation.

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

can be introduced if the workflow requires it. It is not part of the current executable R12+13 role mapping.

---

# Auditor

The `auditor` role is read-only.

Current permissions are:

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

The auditor does not receive write, approval, movement, creation, retraining, staging-promotion, or platform-administration permissions.

In particular, the auditor does not receive:

```text
inventory:write
compliance:write
supplier:write
logistics:write
purchase_order:create
purchase_order:approve
invoice:approve
payment:approve
inventory:move
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

This is the explicit R12+13 mapping.

Separating invoice approval from payment approval is a potential future separation-of-duties enhancement.

For example, future roles could distinguish:

```text
invoice approval
```

from:

```text
payment approval
```

For this milestone, the current mapping remains explicit and does not modify the frozen V1 model.

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

Existing V1 roles are not automatically expanded to receive new permissions.

For example, `ceo` continues to use its frozen V1 mapping even though the new RBAC model contains:

```text
purchase_order:approve
invoice:approve
payment:approve
```

Consuming services can adopt the new permissions when the corresponding business workflows are implemented and approved.

Examples of future adoption include:

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

These are adoption considerations only and do not change the frozen V1 mappings.

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

## V1 Compatibility

Tests verify:

* All 8 V1 roles exist.
* V1 role strings are unchanged.
* V1 permission mappings are unchanged.
* V1 hierarchy is unchanged.
* New roles are not inserted into the V1 hierarchy.

## V2 Role Model

Tests verify:

* All 10 new roles exist.
* At least 18 roles exist.
* Every enum role has a permission mapping.
* Every mapped role exists in the role enum.
* Every permission assigned to a role is known.
* Each new role has an allowed permission.
* Each new role has a denied permission.
* Each new role can be seeded, assigned and verified.

## Security Boundaries

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

## /verify Contract

The `/api/v1/auth/verify` response contract remains unchanged.

The response continues to provide:

```text
valid
user_id
email
full_name
role
supplier_id
is_active
permissions
```

The contract is protected by a dedicated test so future RBAC changes cannot silently rename or remove fields used by consuming services.

## Test Files

The RBAC tests are consolidated into:

```text
tests/test_rbac_snapshot.py
tests/test_roles_and_permissions.py
tests/test_new_roles_assignable.py
tests/test_readme_permission_matrix.py
```

The snapshot fixtures are:

```text
tests/fixtures/permissions_v1.json
tests/fixtures/role_hierarchy_v1.json
```

The README permission matrix is automatically checked against the executable `ROLE_PERMISSIONS` mapping.

---

## Milestone 2 Acceptance

Milestone 2 is complete when:

```text
18 roles are defined
        +
10 V2 roles are seedable and assignable
        +
V1 permissions remain unchanged
        +
V1 hierarchy remains unchanged
        +
new-role permission boundaries are tested
        +
README matrix matches executable permissions
        +
/verify response contract remains unchanged
        +
full test suite passes
```

# Milestone 3 - Shared Event and Logging Helper

The Platform Service owns the shared event-publishing and structured-logging
foundation for EAICSP services.

The helper is implemented inside the Platform Service so that other
microservices can adopt the same conventions in future rounds.

## Shared Event Publisher

The shared Kafka wrapper is implemented in:

```text
app/core/event_publisher.py
```

The public interface is:

```python
publish_event(event_type, payload)
```

The helper builds the standard EAICSP event envelope:

```text
event_id
event_type
event_version
occurred_at
producer
payload
```
State that publish_event never raises, returns None on failure, and delivers at most once.

Example:

```python
publish_event(
    "platform.user.locked",
    {
        "user_id": user.id,
    },
)
```

The Platform Service uses this event when an account is locked after repeated
failed login attempts.

The account-lock flow records the security state and audit information first.
Kafka publishing is performed afterward so a Kafka failure does not undo the
account-lock operation.

### Event Contract

The shared event envelope contains:

| Field           | Description                   |
| --------------- | ----------------------------- |
| `event_id`      | Unique event identifier       |
| `event_type`    | Event name and Kafka topic    |
| `event_version` | Version of the event contract |
| `occurred_at`   | UTC event timestamp           |
| `producer`      | Producing service             |
| `payload`       | Event-specific data           |

The current producer is `platform-service`.

The public publishing interface is:

```python
publish_event(event_type, payload)
```
The helper uses `event_type` as the Kafka topic and wraps the supplied payload in the standard event envelope.

**Failure behavior:** `publish_event` never raises to its caller. It returns `None` on failure and delivers at most once; it does not retry failed publications. The configured `KAFKA_PUBLISH_TIMEOUT_SECONDS` bounds the publishing attempt.

Account-lock state and its audit record are committed before the lock event is published. A Kafka publishing failure must not undo the account lock.


## Structured Logging

The shared JSON structured-logging configuration is implemented in:

```text
app/core/logging_config.py
```

Request logging is integrated through:

```text
app/middleware/logging.py
```

Structured logs provide a consistent format for operational and security
logging.

Each request is associated with a request ID so that activity can be
correlated across services.

The request ID can be supplied through:

```text
X-Request-ID
```

If a request does not provide an ID, the Platform Service generates one.

The service identity is:

```text
platform-service
```

Structured logs therefore provide the information required to correlate
requests and identify the service that produced each log entry.


### M3 tests

The shared event and logging implementation is validated for:

* Standard event envelope creation
* Unique event ID generation
* Event type validation
* Event version presence
* UTC timestamp generation
* Producer identity
* Payload preservation
* `publish_event(event_type, payload)` behavior
* `platform.user.locked` integration
* Account lock remains committed if Kafka publishing fails
* Request ID generation when `X-Request-ID` is missing
* Preservation of supplied `X-Request-ID`
* Structured JSON logging
* Platform service identity in logs
* Sensitive values are not logged

## Milestone 3 Acceptance

Milestone 3 is complete when:

```text
Shared Kafka wrapper exists
        +
Standard event envelope is implemented
        +
platform.user.locked is published
        +
Kafka failure does not undo account locking
        +
Structured JSON logging is configured
        +
X-Request-ID correlation works
        +
Sensitive authentication data is not logged
        +
Platform Service uses the shared helper
        +
M3 tests pass

## Future Service Adoption

The Platform Service owns the shared foundation in this round.

Future EAICSP services can adopt:

```text
publish_event(event_type, payload)
```

for cross-service events and the same structured logging conventions for
consistent request tracing and operational monitoring.

Other services are not required to migrate their existing logging or event
publishing during Round 12+13.
