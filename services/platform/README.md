# Platform Service

## Overview

The **Platform Service** is the authentication and authorization foundation for the Supply Chain Management System.

It provides centralized authentication, JWT token management, role-based access control (RBAC), user management, session management, password reset, authentication audit logging, and a dedicated service-to-service token verification endpoint.

Other backend services such as Inventory, Logistics, Compliance, Supplier Portal, and API Gateway can use the Platform Service to validate authenticated requests.

---

# Features

* User authentication
* User registration
* JWT access tokens
* JWT refresh tokens
* Refresh token storage in database
* Refresh token rotation
* Refresh token revocation
* Logout
* Protected APIs
* Role-Based Access Control (RBAC)
* Role hierarchy support
* Login rate limiting
* Failed login tracking
* Password policy validation
* BCrypt password hashing
* Database-backed users and roles
* Admin user management
* User activation/deactivation
* Role assignment
* Role-change history
* Per-session management
* Session revocation
* Admin force password reset
* Password reset flow
* Authentication audit logging
* Dedicated service-to-service token verification
* Caller-service request identification
* Request-ID tracing
* Consistent authentication error responses
* Real HTTP integration tests
* Concurrent service-to-service verification tests
* API-key authentication sketch for pure service-to-service communication

---

# Tech Stack

* FastAPI
* Python
* Pydantic
* Uvicorn
* SQLAlchemy
* python-jose
* Passlib
* BCrypt
* SQLite for development
* PostgreSQL for production

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
│   └── password_validator.py
│   └── service_auth.py 
│
├── models/
│   ├── auth_audit_logs.py
│   ├── password_reset_tokens.py
│   ├── failed_login_attempts.py
│   ├── refresh_token.py
│   ├── roles.py
│   ├── users.py
│   └── role_change_history.py
│
└── middleware/
    └── logging.py

tests/
├── test_auth.py
└── test_integration.py
```

---

# Service Configuration

## Platform Service Port

The Platform Service runs on:

```text
http://127.0.0.1:8005
```

API prefix:

```text
/api/v1
```

Therefore the complete API base URL is:

```text
http://127.0.0.1:8005/api/v1
```

Swagger:

```text
http://127.0.0.1:8005/docs
```

---

# Roles

The following roles are implemented:

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

---

# Database

## Development

SQLite is used for local development.

## Production

PostgreSQL is the target production database.

## Current Tables

```text
users
roles
refresh_token
failed_login_attempts
role_change_history
password_reset_tokens
auth_audit_logs
```

Users and roles are stored in the database.

Seeded users are inserted into the database through `seed.py`. They are not maintained in an in-memory user dictionary.

---

# API Endpoints

## Authentication

### Register

```http
POST /api/v1/auth/register
```

Registers a new user.

### Request

```json
{
  "email": "newregisteruser@company.com",
  "full_name": "New Register User",
  "password": "NewRegister@123"
}
```

### Registration Flow

```text
Registration
     |
     v
Check existing email
     |
     v
Validate password
     |
     v
Hash password using BCrypt
     |
     v
Create user
     |
     v
role_id = NULL
```

Self-registration intentionally creates the user without a role.

The user must be assigned a role by an authorized administrator before they can log in.

---

# Login

```http
POST /api/v1/auth/login
```

Authenticates a user using email/username and password.

The endpoint uses OAuth2 password-form authentication.

### Request

The request uses:

```text
Content-Type: application/x-www-form-urlencoded
```

Example:

```text
username=supplier@company.com
password=supplier@123
```

### Successful Response

```json
{
  "access_token": "<access_token>",
  "refresh_token": "<refresh_token>",
  "token_type": "bearer"
}
```

The user must:

* Exist in the database
* Have a valid password
* Be active
* Have an assigned role

If the user does not have a role assigned, login is rejected.

---

# JWT Tokens

## Access Token

Access tokens are short-lived.

```text
Expiration: 15 minutes
```

Used to access protected APIs.

Example:

```http
Authorization: Bearer <access_token>
```

## Refresh Token

Refresh tokens are long-lived.

```text
Expiration: 7 days
```

Refresh tokens are stored in the database.

They are checked for:

* Token validity
* Token type
* Revocation status
* Expiration

---

# Refresh Token

```http
POST /api/v1/auth/refresh
```

### Request

```json
{
  "refresh_token": "<refresh_token>"
}
```

### Response

```json
{
  "access_token": "<new_access_token>",
  "refresh_token": "<new_refresh_token>",
  "token_type": "bearer"
}
```

Refresh-token rotation is used.

The old refresh token is revoked before the new refresh token is issued.

---

# Refresh Token Replay Protection

The refresh-token flow is:

```text
Refresh Token A
       |
       v
Validate Token A
       |
       v
Revoke Token A
       |
       v
Generate Token B
       |
       v
Store Token B
       |
       v
Return Token B
```

If an attacker attempts to reuse Token A:

```text
Token A
   |
   v
Database lookup
   |
   v
is_revoked = True
   |
   v
401 Unauthorized
```

The previously rotated refresh token cannot be reused.

---

# Logout

```http
POST /api/v1/auth/logout
```

### Request

```json
{
  "refresh_token": "<refresh_token>"
}
```

The refresh token is marked as revoked in the database.

After logout, the revoked refresh token cannot be used to obtain another access token.

---

# Current User

```http
GET /api/v1/users/me
```

Returns the currently authenticated user's information.

### Header

```http
Authorization: Bearer <access_token>
```

---

# User Permissions

```http
GET /api/v1/auth/me/permissions
```

Requires:

```http
Authorization: Bearer <access_token>
```

Returns effective permissions based on the user's role and configured role hierarchy.

---

# Role-Based Access Control

## RBAC Test

```http
GET /api/v1/admin/test
```

Protected using the configured role hierarchy.

Higher-level roles inherit permissions from lower-level roles according to the hierarchy.

---

# Role Hierarchy

Current hierarchy:

```text
ceo
└── vp_operations
    └── procurement_manager
        └── logistics_manager
            └── warehouse_manager
```

Higher roles automatically inherit permissions from lower roles defined in the hierarchy.

For example:

```text
CEO
 ├── CEO permissions
 ├── VP Operations permissions
 ├── Procurement permissions
 ├── Logistics permissions
 └── Warehouse permissions
```

VP Operations does not inherit CEO-only permissions.

The RBAC dependencies use the configured hierarchy as applicable:

```text
require_role()
require_any_role()
require_all_roles()
```

---

# Password Policy

Passwords must contain:

* Minimum 12 characters
* At least one number
* At least one special character

Password validation happens before password hashing.

```text
Registration
     |
     v
validate_password()
     |
     v
hash_password()
     |
     v
Store BCrypt hash
```

The same validator can be reused for password reset and password change operations.

---

# Force Reset Password

```http
POST /api/v1/admin/users/{user_id}/force-reset-password
```

### Request

```json
{
  "new_password": "NewPassword@12345"
}
```

The new password must satisfy the configured password policy before it is hashed and stored.

Only authorized administrators can perform this operation.

---

# Login Rate Limiting

Failed login attempts are stored in the database using the:

```text
failed_login_attempts
```

table.

Current limit:

```text
5 failed attempts within 15 minutes
```

Rate limiting is checked using two dimensions.

## Per Email

Protects an individual account from credential-stuffing attacks.

## Per IP

Protects against password spraying from a single IP address across multiple accounts.

When the limit is reached:

```http
429 Too Many Requests
```

is returned.

The rate limiter uses database-backed tracking rather than an in-memory Python dictionary, allowing it to work across multiple service workers more reliably.

---

# Admin User Management

Administrative endpoints are available under:

```text
/api/v1/admin
```

---

## List Users

```http
GET /api/v1/admin/users
```

Authorized roles:

```text
ceo
vp_operations
```

Returns users stored in the database.

---

## Create User

```http
POST /api/v1/admin/users
```

### Request

```json
{
  "email": "r4testuser@company.com",
  "full_name": "R4 Test User",
  "password": "TestUser@12345",
  "role": "analyst"
}
```

The administrator:

1. Checks whether the user exists.
2. Validates the password.
3. Looks up the requested role.
4. Hashes the password.
5. Creates the user.
6. Assigns the role.
7. Records the role assignment in role-change history.

---

## Deactivate User

```http
PATCH /api/v1/admin/users/{user_id}/deactivate
```

Authorized roles:

```text
ceo
vp_operations
```

An administrator cannot deactivate their own account.

---

## Change User Role

```http
PATCH /api/v1/admin/users/{user_id}/role
```

### Request

```json
{
  "role": "analyst"
}
```

The system:

* Updates the user's role.
* Records the previous role.
* Records the new role.
* Records the administrator who made the change.
* Creates an authentication audit log.

---

## Role Change History

```http
GET /api/v1/admin/users/{user_id}/role-history
```

Returns:

* History ID
* User ID
* Previous role
* New role
* User who made the change
* Timestamp

---

# Per-Session Management

Refresh tokens represent individual user sessions.

Multiple logins create separate sessions.

```text
Login 1
   |
   v
Session A

Login 2
   |
   v
Session B
```

Each session has a separate refresh token.

---

## List Active Sessions

```http
GET /api/v1/admin/users/{user_id}/sessions
```

Authorized roles:

```text
ceo
vp_operations
```

Returns:

* Session ID
* User ID
* Created timestamp
* Expiration timestamp
* Revocation status

Refresh tokens themselves are never exposed.

---

## Revoke Session

```http
DELETE /api/v1/admin/users/{user_id}/sessions/{session_id}
```

Revokes an individual session.

The associated refresh token is marked as revoked.

A `TOKEN_REVOKED` authentication audit event is recorded.

### Response

```json
{
  "message": "Session revoked successfully"
}
```

---

# Password Reset Flow

The password reset flow is:

```text
Request Password Reset
        |
        v
Generate secure random token
        |
        v
Store token in database
        |
        v
Mock email/log output
        |
        v
Reset Password
        |
        v
Validate token
        |
        v
Validate expiration
        |
        v
Validate password
        |
        v
Hash password
        |
        v
Mark token as used
```

---

# Request Password Reset

```http
POST /api/v1/auth/request-password-reset
```

The system:

1. Accepts the user's email.
2. Generates a secure random token.
3. Stores the token in the database.
4. Stores the expiration time.
5. Sends/logs a mock email for development.

The response does not reveal whether the supplied email exists.

---

# Reset Password

```http
POST /api/v1/auth/reset-password
```

The reset operation validates:

* Token exists
* Token has not been used
* Token has not expired
* User exists
* New password satisfies the password policy

After successful reset:

```text
token.used = True
```

The same reset token cannot be reused.

---

# Authentication Audit Logging

Authentication-sensitive actions are recorded using the audit service.

Supported events include:

```text
LOGIN_SUCCESS
LOGIN_FAILED
ROLE_CHANGED
TOKEN_REVOKED
```

Audit logs can be accessed by authorized administrators.

```http
GET /api/v1/admin/audit-logs
```

Optional filters:

```text
user_id
event_type
```

Audit records contain information such as:

* Event type
* User ID
* Email
* IP address
* Details
* Timestamp

---

#Service-to-Service Integration

Introduces a dedicated integration contract for dependent services.

The goal is to allow services such as Inventory, Logistics, Compliance, Supplier Portal, and API Gateway to communicate with Platform without using browser-oriented authentication flows.

The main service-to-service endpoint is:

```http
POST /api/v1/auth/verify
```

---

# Integration Contract

## Base URL

Local development:

```text
http://127.0.0.1:8005
```

API prefix:

```text
/api/v1
```

Full verification endpoint:

```text
POST http://127.0.0.1:8005/api/v1/auth/verify
```

---

# Service-to-Service Verification

## Endpoint

```http
POST /api/v1/auth/verify
```

This endpoint is specifically designed for backend services.

A dependent service sends a JWT access token to Platform.

Platform:

1. Extracts the Bearer token.
2. Validates the JWT.
3. Checks token expiration.
4. Identifies the user.
5. Retrieves the user's role.
6. Verifies the account is active.
7. Returns authenticated user information and role.

Services do not need to call user-facing endpoints such as `/users/me` just to validate a token.

---

# Verify Request

### Headers

```http
Authorization: Bearer <access_token>
X-Caller-Service: inventory-service
X-Request-ID: <unique-request-id>
```

The request body is not required.

Example:

```http
POST /api/v1/auth/verify
Authorization: Bearer eyJ...
X-Caller-Service: inventory-service
X-Request-ID: 550e8400-e29b-41d4-a716-446655440000
```

---

# Verify Successful Response

HTTP status:

```text
200 OK
```

Example:

```json
{
  "valid":true,
  "user_id": 123,
  "email": "supplier@company.com",
  "full_name": "Supplier User",
  "role": "supplier",
  "supplier_id":"101",
  "is_active": true
}
```

Dependent services can use the returned role to perform their own authorization checks.

---

# Verify Error Contract

All authentication and authorization failures use the same JSON structure:

```json
{
  "detail": "clear message"
}
```

## 401 Unauthorized

Returned when authentication fails.

Examples:

* Missing token
* Empty token
* Invalid token
* Expired token
* Tampered token
* Revoked/invalid authentication credential

Example:

```json
{
  "detail": "Invalid or expired token"
}
```

The important distinction is:

```text
401 = Authentication failed
```

The service could not establish a valid authenticated identity.

---

## 403 Forbidden

Returned when the token is valid but the authenticated user does not have permission to perform the requested operation.

Example:

```json
{
  "detail": "Forbidden: insufficient permissions"
}
```

The distinction is:

```text
403 = Authentication succeeded,
      but authorization failed
```

---

## 422 Unprocessable Entity

Used for request validation errors where the API contract requires a request body or specific fields.

For the OAuth2 login endpoint, the expected fields are:

```text
username
password
```

For example, a malformed login request can return:

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": [
        "body",
        "username"
      ],
      "msg": "Field required"
    }
  ]
}
```

---

## 429 Too Many Requests

Returned when login rate limiting is triggered.

Example:

```json
{
  "detail": "Too many failed login attempts"
}
```

---

# cURL Examples

## Login

Because `/auth/login` uses OAuth2 password-form authentication:

```bash
curl -X POST "http://127.0.0.1:8005/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=supplier@company.com" \
  -d "password=supplier@123"
```

Example response:

```json
{
  "access_token": "<access_token>",
  "refresh_token": "<refresh_token>",
  "token_type": "bearer"
}
```

---

# Call Protected Endpoint

Example:

```bash
curl -X GET "http://127.0.0.1:8005/api/v1/users/me" \
  -H "Authorization: Bearer <access_token>"
```

---

# Call Service-to-Service Verify Endpoint

Example:

```bash
curl -X POST "http://127.0.0.1:8005/api/v1/auth/verify" \
  -H "Authorization: Bearer <access_token>" \
  -H "X-Caller-Service: inventory-service" \
  -H "X-Request-ID: 550e8400-e29b-41d4-a716-446655440000"
```

Expected:

```json
{
  "user_id": 123,
  "email": "supplier@company.com",
  "full_name": "Supplier User",
  "role": "supplier",
  "is_active": true
}
```

---

# Dependent Service Integration

Example architecture:

```text
                  API Gateway
                       |
        +--------------+--------------+
        |              |              |
        v              v              v
   Inventory       Logistics      Supplier Portal
        |               |                |
        |               |                |
        +---------------+----------------+
                        |
                        | POST /auth/verify
                        | Bearer JWT
                        v
                Platform Service
                
```

For example, Inventory can send:

```http
POST http://127.0.0.1:8005/api/v1/auth/verify
```

with:

```http
Authorization: Bearer <access_token>
X-Caller-Service: inventory-service
X-Request-ID: <request-id>
```

Platform validates the token and returns the user's identity and role.

---

# Request Logging

Platform records service-to-service requests so authentication failures can be diagnosed.

The logging information includes:

```text
Caller service
Request ID
Timestamp
HTTP method
Request path
Response status
```

Example conceptual log:

```text
timestamp=2026-09-04T10:30:15
caller=inventory-service
method=POST
path=/api/v1/auth/verify
request_id=550e8400-e29b-41d4-a716-446655440000
status=200
```

This allows the team to determine:

```text
Who called?
When did they call?
Which endpoint did they call?
What request ID was used?
What status did Platform return?
```

---

# Concurrency

Platform is designed to support multiple dependent services calling `/verify`.

Example:

```text
Inventory Service       \
Logistics Service        \
Compliance Service       ---> Platform /auth/verify
Supplier Portal         /
API Gateway             /
```

The integration tests simulate:

* 5 services calling `/verify`
* 20 concurrent verification requests
* Multiple service callers
* Request IDs for tracing

---

# Integration Tests

R5 integration tests are maintained separately from unit/authentication tests.

```text
tests/
├── test_auth.py
└── test_integration.py
```

`test_auth.py` contains normal authentication and application tests.

`test_integration.py` contains **real HTTP tests against the running Platform Service**.

The integration tests do not mock the Platform API.

---

#  Integration Test Coverage

The integration suite verifies:

### Platform availability

```text
GET /
```

### Real HTTP login

```text
POST /api/v1/auth/login
```

### Dedicated verification endpoint

```text
POST /api/v1/auth/verify
```

### Role verification

Tests roles such as:

```text
supplier
warehouse_manager
vp_operations
```

### Authentication failures

Tests:

```text
Missing token       → 401
Invalid token       → 401
Empty token         → 401
Tampered token      → 401
Expired token       → 401
```

### Authorization failure

Valid token + wrong role:

```text
403
```

### Error response format

Expected structure:

```json
{
  "detail": "clear message"
}
```

### Caller service identification

Tests:

```text
X-Caller-Service
```

### Request tracing

Tests:

```text
X-Request-ID
```

### Concurrent service calls

Tests:

```text
5 concurrent service calls
20 concurrent verification requests
```

### End-to-end authentication

```text
Login
  |
  v
Receive JWT
  |
  v
Call /auth/verify
  |
  v
Validate JWT
  |
  v
Return user + role
```

---

# Integration Tests

The Platform Service must be running before executing the integration tests.

## Terminal 1 - Start Platform

```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8005
```

Verify:

```text
http://127.0.0.1:8005/docs
```

Confirm that the following endpoint is visible:

```text
POST /api/v1/auth/verify
```

## Terminal 2 - Run Integration Tests

```bash
pytest -v tests/test_integration.py
```

Or:

```bash
pytest -q tests/test_integration.py
```

These tests make real HTTP requests to:

```text
http://127.0.0.1:8005
```

Therefore, if the Platform Service is not running, tests will fail with a connection error such as:

```text
httpx.ConnectError
[WinError 10061]
No connection could be made because the target machine actively refused it
```

This indicates that the service is not listening on port `8005`, rather than an authentication assertion failure.

---

# Integration Test Examples

Example successful login:

```text
POST /api/v1/auth/login
             |
             v
          200 OK
             |
             v
       access_token
```

Example service verification:

```text
POST /api/v1/auth/verify
Authorization: Bearer <token>
X-Caller-Service: inventory-service
X-Request-ID: <id>
             |
             v
          200 OK
             |
             v
     user + role returned
```

Example invalid authentication:

```text
POST /api/v1/auth/verify
Authorization: Bearer invalid-token
             |
             v
          401
             |
             v
{
  "detail": "Invalid or expired token"
}
```

Example authorization failure:

```text
Valid JWT
   |
   v
Supplier
   |
   v
Admin-only endpoint
   |
   v
403 Forbidden
```

---

# API-Key Authentication

An API-key authentication mechanism can be used as an alternative for pure service-to-service communication.

Concept:

```text
Inventory Service
       |
       | X-API-Key
       v
Platform Service
       |
       v
Validate service credential
```

Example:

```http
X-API-Key: <api-key>
```

This is intended for machine-to-machine communication where forwarding a user JWT is not appropriate.

The API-key mechanism is a stretch feature and does not replace JWT authentication for user-context requests.

API keys must not be committed to source control.

Example environment configuration:

```env
INVENTORY_SERVICE_API_KEY=<secret>
```

---

# Seeded Users

Development and testing users are provided through:

```text
app/seed.py
```

The seed process creates:

1. Roles
2. Users
3. User-role relationships

Example users:

```text
ceo@company.com
vpoperations@company.com
procurementmanager@company.com
logisticsmanager@company.com
warehousemanager@company.com
compliance@company.com
analyst@company.com
supplier@company.com
```

Seeded users have roles assigned during the seeding process.

They are used for development and automated testing.

---

# Authentication Flow

```text
                 Seed Database
                       |
                       v
                 Roles + Users
                       |
                       v
                Register / Login
                       |
                       v
                 Validate User
                       |
                       v
                 Validate Role
                       |
                       v
                  Generate JWT
                       |
             +---------+---------+
             |                   |
             v                   v
       Access Token        Refresh Token
             |                   |
             v                   v
       Protected APIs       Database Storage
             |                   |
             v                   v
       JWT Validation      Validation/Rotation
             |                   |
             v                   v
        RBAC/Hierarchy       Revocation
             |
             v
         User Access
```

---

# Service-to-Service Authentication Flow

```text
Dependent Service
       |
       | Authorization: Bearer <JWT>
       | X-Caller-Service
       | X-Request-ID
       v
POST /api/v1/auth/verify
       |
       v
Platform Service
       |
       +--> Validate JWT
       |
       +--> Check expiration
       |
       +--> Identify user
       |
       +--> Get role
       |
       +--> Check active status
       |
       v
200 OK
{
  "valid":true,
  "user_id": 123,
  "email": "...",
  "full_name": "...",
  "role": "supplier",
  "supplier_id": "101",
  "is_active": true
}
```

---

# Newly Registered User Flow

```text
Register
   |
   v
User created
   |
   v
role_id = NULL
   |
   v
Cannot login
   |
   v
Admin assigns role
   |
   v
User can login
```

This is intentional RBAC behavior.

---

## Service-to-Service Authentication

The Platform Service supports API-key authentication for trusted service-to-service communication.

This is intended for **service-to-service calls**, not for normal user login.

### Endpoint

```text
POST /api/v1/auth/service-verify
```

### Authentication

The requesting service must provide its API key using the authentication header expected by `verify_service_api_key`.

Example:

```bash
curl -X POST http://127.0.0.1:8005/api/v1/auth/service-verify \
  -H "X-API-Key: <SERVICE_API_KEY>"
```

### Successful Response

```json
{
  "authenticated": true,
  "service": "inventory-service",
  "auth_type": "api_key"
}
```

The response confirms that:

* The service API key is valid.
* The requesting service has been identified.
* The authentication method is API key authentication.

### When to Use

API-key authentication is intended for trusted internal service-to-service communication where there is no end-user context.

Example:

```text
Inventory Service
       |
       | X-API-Key
       ▼
Platform Service
       |
       | Validate API key
       ▼
Authenticated Service
```

For requests made on behalf of a logged-in user, use JWT authentication and the normal token verification flow instead.

### Authentication Comparison

| Use case                          | Authentication                |
| --------------------------------- | ----------------------------- |
| User login                        | JWT                           |
| User accessing protected APIs     | Access JWT                    |
| Refreshing user session           | Refresh token                 |
| Service-to-service authentication | API key                       |
| Service token verification        | `/api/v1/auth/verify`         |
| Service API-key verification      | `/api/v1/auth/service-verify` |



# Setup

## Create Virtual Environment

```bash
python -m venv .venv
```

## Activate

PowerShell:

```powershell
.venv\Scripts\activate
```

## Install Dependencies

```bash
pip install -r requirements.txt
```

## Environment File

Create `.env` from `.env.example`.

PowerShell:

```powershell
Copy-Item .env.example .env
```

Set a secure `SECRET_KEY`.

Generate one using:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Example:

```env
SECRET_KEY=<generated-secret>
```

Never commit the real `.env` file or production secrets.

---

# Database Initialization

Start the application:

```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8005
```

The application creates database tables using:

```python
Base.metadata.create_all(bind=engine)
```

Then seed roles and development users:

```bash
python -m app.seed
```

Run the seed command after the database tables have been created.

The seed operation is designed to avoid duplicating existing roles and users.

---

# Swagger

Open:

```text
http://127.0.0.1:8005/docs
```

---

# Testing

The Platform Service has two types of tests:

Unit tests — run without requiring the Platform Service to be running.
Integration tests — make real HTTP requests to the running Platform Service on port 8005.
Run the default test suite
```bash
pytest -q
```

The default test command excludes integration tests, so the Platform Service does not need to be running.

Run integration tests

First start the Platform Service:

uvicorn app.main:app --host 0.0.0.0 --port 8005

Then, in another terminal, run:
```bash
pytest -m integration -q
```

Integration tests use real HTTP calls against:

http://127.0.0.1:8005
Run all tests

To run both the normal test suite and integration tests:
```bash
pytest -m "" -q

---

# Test Coverage

Implemented tests cover:

* Root endpoint
* Successful login
* Invalid credentials
* User registration
* Password policy
* JWT validation
* Expired JWT
* Tampered JWT rejection
* Refresh token validation
* Refresh token expiration
* Refresh token rotation
* Refresh token replay protection
* Logout
* Refresh token revocation
* Login rate limiting
* Failed-login tracking
* CEO role hierarchy
* Role hierarchy edge cases
* Wrong-role access
* Admin user management
* User activation/deactivation
* Role assignment
* Role-change history
* Per-session management
* Session revocation
* Password reset
* Authentication audit logging

Integration tests additionally cover:

* Real HTTP login
* Real HTTP `/auth/verify`
* Correct role returned
* Missing-token `401`
* Invalid-token `401`
* Expired-token `401`
* Tampered-token `401`
* Valid-token wrong-role `403`
* Consistent error response format
* `X-Caller-Service`
* `X-Request-ID`
* Concurrent service-to-service calls
* End-to-end login → JWT → `/verify`

---

# HTTP Status Code Summary

| Status | Meaning                                                                 |
| ------ | ----------------------------------------------------------------------- |
| `200`  | Request successful                                                      |
| `201`  | Resource created                                                        |
| `400`  | Bad request / invalid operation                                         |
| `401`  | Authentication failed: missing, invalid, expired, or revoked credential |
| `403`  | Authentication succeeded but user lacks permission                      |
| `404`  | Resource or endpoint not found                                          |
| `422`  | Request validation failed                                               |
| `429`  | Rate limit exceeded                                                     |
| `500`  | Internal server error                                                   |
| `503`  | Service/dependency temporarily unavailable                              |

For service-to-service authentication, dependent services should primarily handle:

```text
200 → Authentication successful
401 → Authentication failed
403 → Authenticated but not authorized
429 → Rate limited
503 → Platform/service availability problem
```

# Reference

Platform is assigned to:
```text
http://127.0.0.1:8005
```

Dependent services should configure their Platform URL accordingly.

Example Inventory configuration:

```env
PLATFORM_AUTH_URL=http://127.0.0.1:8005
```

The resulting service-to-service verification call is:

```text
Inventory
    |
    | POST
    v
http://127.0.0.1:8005/api/v1/auth/verify
    |
    v
Platform Service
```

---

# Summary

The Platform Service acts as the centralized authentication and authorization service for the Supply Chain Management System.

It provides:

```text
Authentication
      +
JWT
      +
Refresh Token Management
      +
RBAC
      +
Role Hierarchy
      +
User Management
      +
Session Management
      +
Password Reset
      +
Audit Logging
      +
Service-to-Service Verification
      +
Request Tracing
      +
Integration Testing
```

The dedicated `/api/v1/auth/verify` endpoint provides a lightweight contract for backend services to validate user tokens and retrieve the authenticated user's role without depending on browser-oriented authentication endpoints.

# Known Limitations

- No dependent service currently imports `require_role` /
`get_current_user`
from this service. The dependency works; the integration hasn't landed
yet.
- The API-key path (`/api/v1/auth/service-verify`,
`app/core/service_auth.py`)
is a sketch: no tests, no adopters, header name not finalised.
- Concurrency is SQLite-backed. The integration suite exercises 20
concurrent
verifications, which is well below what a shared database would need to
handle.
- Request logging captures caller/request-id/method/path/status, but
nothing
currently tests that those values are actually recorded.
