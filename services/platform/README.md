# Platform Service

## Overview

The **Platform Service** is the authentication and authorization foundation of the EAICSP Supply Chain Management Platform.

It is one microservice within EAICSP and provides common security capabilities that are consumed by other backend services such as:

* Inventory Service
* Logistics Service
* Compliance Service
* Supplier Portal Service

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

# Key Responsibilities

The Platform Service provides:

* User registration and login
* JWT access-token authentication
* Refresh-token rotation and revocation
* Role-Based Access Control (RBAC)
* Fine-grained permissions
* User session management
* Password validation and reset
* Login rate limiting
* Account lockout
* Forced password rotation
* User activation/deactivation
* Security audit logging
* Security dashboard
* JWT-based service-to-service verification
* API-key-based service authentication
* Service API-key issuance, tracking and revocation
* Token introspection caching

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
│   └── email_service.py
│
├── core/
│   ├── config.py
│   ├── security.py
│   ├── dependencies.py
│   ├── password_validator.py
│   └── service_auth.py
│   └── token_cache.py
│   └── permissions.py
│
├── models/
│   ├── auth_audit_logs.py
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
└── test_integration.py
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

Production should use PostgreSQL and a securely managed secret.

The JWT signing secret must never be hardcoded in source code.

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

The development environment uses SQLite.

Production should use PostgreSQL.

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
```

---

# Authentication Flow

The normal user authentication flow is:

```text
Client
  |
  | Register
  v
Platform Service
  |
  | Validate request
  | Hash password
  v
Database
```

After registration:

```text
Client
  |
  | username + password
  v
POST /api/v1/auth/login
  |
  | Validate credentials
  | Check account status
  | Check role assignment
  v
JWT Access Token + Refresh Token
```

The client then sends:

```http
Authorization: Bearer <access_token>
```

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

After logout, the revoked refresh token cannot be used to obtain another access token.

---

# Login

## POST `/api/v1/auth/login`

Login uses username/email and password.

The login process is:

```text
Request
   |
   v
Pydantic validation
   |
   v
Find user
   |
   v
Check account status
   |
   v
Check role assignment
   |
   v
Verify BCrypt password hash
   |
   v
Generate JWT access token
   |
   v
Generate refresh token
   |
   v
Store refresh-token information
   |
   v
Return tokens
```

### JWT generation

`python-jose` is used for JWT creation and verification.

The access token contains information such as:

```text
sub
email
role
type
exp
```

The access token is short-lived.

Current configuration:

```text
Access token: 15 minutes
Refresh token: 7 days
```

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

---

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

This allows other services to use the same authorization pattern.

For example:

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

```json
{
  "valid": true,
  "user_id": 123,
  "email": "supplier@company.com",
  "full_name": "Supplier User",
  "role": "supplier",
  "supplier_id": "101",
  "is_active": true
}
```

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

---

# Inventory and Compliance Integration

Inventory and Compliance can use separate Platform-issued service API keys.

They should **not share the same key**.

Example:

```text
Platform Service
       |
       +---- Inventory API Key
       |
       +---- Compliance API Key
```

Inventory configuration:

```env
PLATFORM_URL=http://127.0.0.1:8005
INVENTORY_PLATFORM_API_KEY=<inventory-secret>
```

Compliance configuration:

```env
PLATFORM_URL=http://127.0.0.1:8005
COMPLIANCE_PLATFORM_API_KEY=<compliance-secret>
```

The values must be stored as environment secrets.

---

# Compliance Nightly Job

For a scheduled machine-to-machine operation:

```text
Compliance Nightly Job
        |
        | X-API-Key
        v
Platform Service
        |
        | Validate Compliance API Key
        v
Authenticated Service
        |
        v
Continue scheduled operation
```

Example:

```http
POST /api/v1/auth/service-verify
X-API-Key: sk_<compliance-secret>
```

The API key authenticates the **Compliance service account**.

If Compliance subsequently calls another service, that target service must independently support and validate the appropriate credential.

---

# API-Key Rate Limiting

An optional extension for service authentication is rate limiting `/verify` requests by calling service.

For example:

```http
X-Caller-Service: inventory-service
```

can be used to identify the calling service.

This can prevent a compromised service credential from generating unlimited verification traffic.

---

# Token Introspection Caching

## Milestone 1 — Token Introspection Caching

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

---

# Cache Performance Measurement

The M1 task requires measuring the difference between:

```text
Cache disabled
```

and:

```text
Cache enabled
```

A benchmark should record:

```text
Cold verification latency
Cache-hit latency
Percentage improvement
```

Example format:

```text
Without cache: <measured-value> ms
With cache:    <measured-value> ms

Improvement:
((without_cache - with_cache) / without_cache) * 100
```

Actual measurements should be recorded from the test/benchmark environment rather than hardcoded into this documentation.

---

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

Example:

```json
{
  "detail": "Invalid credentials"
}
```

Authentication failures should avoid revealing whether a specific account exists.

---

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

---

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

# End-to-End Service Flow

A realistic EAICSP flow can look like this:

```text
                    User
                     |
                     v
                API Gateway
                     |
                     v
              Platform Service
                     |
              Login / JWT
                     |
          +----------+----------+
          |                     |
          v                     v
     Inventory              Compliance
          |                     |
          |                     |
          +----------+----------+
                     |
                     v
                 Logistics
```

For a user request:

```text
1. User logs in
2. Platform generates JWT
3. Gateway receives request
4. Gateway/service sends JWT
5. Platform verifies JWT when required
6. Service checks role/permission
7. Service performs business operation
8. Response returns to client
```

For a scheduled service-account request:

```text
Compliance Nightly Job
        |
        | X-API-Key
        v
Platform Service
        |
        | Validate service key
        v
Compliance authenticated
        |
        v
Scheduled operation continues
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

# Production Security Considerations

Before production deployment:

* Use PostgreSQL
* Use a strong secret key
* Store secrets in a secret manager/environment
* Use HTTPS
* Configure trusted proxies correctly
* Restrict CORS
* Rotate service API keys
* Monitor authentication failures
* Monitor account lockouts
* Monitor suspicious token activity
* Use centralized logging
* Use appropriate database connection pooling
* Use Redis/shared infrastructure where distributed caching is required

---

# Milestone Completion Summary

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

Definition of done:

* Short-TTL token cache implemented
* Cache hit/miss behavior tested
* TTL behavior tested
* Latency measured
* Improvement demonstrated

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

Definition of done:

* Permission model implemented
* Permissions mapped to roles
* Permission-level checks available
* Existing role checks remain supported

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

Definition of done:

* Account lockout demonstrated
* Forced password rotation supported
* Deactivation cascade implemented
* Active sessions invalidated after deactivation

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

Definition of done:

* Security dashboard available
* Admin-only access
* Failed login trends available
* Active sessions visible
* Role changes visible
* Lockout events visible

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

Definition of done:

* API keys can be issued
* API keys are hashed before storage
* API keys can be verified
* API keys can expire
* API keys can be revoked
* Key usage can be tracked
* Service identity is returned
* Inventory and Compliance can use separate service credentials

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

# Security Boundary

The Platform Service is the central security foundation, but it does not own the business logic of the other microservices.

```text
Platform Service
    |
    +--> Who is the user?
    +--> Is the token valid?
    +--> What role does the user have?
    +--> What permissions does the user have?
    +--> Is the service authenticated?
    +--> Is the account active?
```

The consuming microservice decides:

```text
What business operation should happen?
```

and uses the identity/authorization information supplied by Platform.

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

# Reference

## Authentication

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
```

## Users

```text
GET /api/v1/users/me
```

## Administration

```text
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
```

---

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
