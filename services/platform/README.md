# Platform Service

## Overview

Platform Service handles authentication and authorization for the Supply Chain Management System.

# Features

* User authentication
* User Registration
* JWT Access Token (15 minutes)
* JWT Refresh Token (7 days)
* Refresh token storage in database
* Refresh token revocation (Logout)
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
* Role assignment and role-change history
* Per-session management
* Session revocation
* Admin force password reset
* Authentication audit logging
* Password reset flow with single-use expiring tokens
---
## Tech Stack

- FastAPI
- Python
- Pydantic
- Uvicorn
- python-jose
- passlib
- bcrypt
- sqlalchemy

---
## Project Structure

```
app/
├── main.py
├── database.py
├── seed.py
├── routes/
│   ├── auth_routes.py
│   ├── user_routes.py
│   └── admin_routes.py
├── schemas/
│   ├── auth.py
│   └── user.py
│   └── admin.py
├── services/
│   └── auth_service.py
│   └── audit_service.py
│   └── email_service.py
├── core/
│   ├── config.py
│   ├── security.py
│   └── dependencies.py
│   └── password_validator.py
└── models/
│   ├── auth_audit_logs.py
│   ├── password_reset_tokens.py
│   ├── failed_login_attempts.py
│   ├── refresh_token.py
│   ├── roles.py
│   ├── users.py
│   ├── role_change_history.py
└── middleware/
│   ├── logging.py
```

## Roles

Implemented roles:

- ceo
- vp_operations
- procurement_manager
- logistics_manager
- compliance_officer
- warehouse_manager
- analyst
- supplier

# Database

Development Database

* SQLite

Production Database

* PostgreSQL

Current Tables

* users
* roles
* refresh_token
* failed_login_attempts
* role_change_history

---
Users and roles are stored in the database.
The seeded users are provided for development and testing purposes. They are inserted into the database by `seed.py`; they are not maintained in an in-memory user dictionary.

# API Endpoints

## Register

```
POST /api/v1/auth/register
```

Registers a new user.

Example request:

```json
{
    "email": "newregisteruser@company.com",
    "full_name": "New Register User",
    "password": "NewRegister@123"
}
```

The registration flow:

1. Checks whether the email already exists.
2. Validates the password against the password policy.
3. Hashes the password using BCrypt.
4. Creates the user in the database.
5. Creates the user without an assigned role.

The new user's `role_id` is initially `NULL`.

- Known limitation:
Registration behavior: Self-registration creates the account without a role. The account must be assigned a role by an authorized administrator before the user can log in. Until a role is assigned, login returns 401 User role is not assigned

Because this lock only protects threads inside the same Python process

- Known limitation: Login rate limiting currently uses an in-process threading.Lock, which is sufficient for the service's current single-process deployment. If the service is later deployed with multiple Uvicorn/Gunicorn workers or multiple replicas, the lock will not coordinate requests between processes. A database-level atomic counter or Redis-based INCR should then be used for distributed rate limiting.

---

## Login

```
POST /api/v1/auth/login
```

Authenticates a user using their email and password.

A user must:

* Exist in the database.
* Have a valid password.
* Be active.
* Have an assigned role.

If the user does not have a role assigned, login is rejected with:

```
User role has not been assigned
```

Successful login returns:

* JWT access token
* JWT refresh token

---

## Refresh Token

```
POST /api/v1/auth/refresh
```

Takes a JSON body:

```json
{
    "refresh_token": "<your refresh token>"
}
```

Returns a new access token.

Refresh tokens are stored in the database and checked for:

* Valid token
* Non-revoked status
* Expiration

---

## Current User

```
GET /api/v1/users/me
```

Returns the currently authenticated user's details.

Requires:

```
Authorization: Bearer <access_token>
```

---

## RBAC Test

```
GET /api/v1/admin/test
```

This endpoint is protected using the role hierarchy.

The endpoint requires:

```
ceo
vp_operations
```

Higher-level roles inherit permissions from lower-level roles according to the configured role hierarchy.

---

# Role Hierarchy

Current hierarchy:

```
ceo
└── vp_operations
    └── procurement_manager
        └── logistics_manager
            └── warehouse_manager
```



Higher roles automatically inherit permissions from lower roles defined in the hierarchy.

For example:

* CEO automatically has VP Operations permissions.
* VP Operations automatically has Procurement Manager permissions.

The `require_role`, `require_any_role`, and `require_all_roles` dependencies use the configured role hierarchy as applicable.

---

# Password Policy

Passwords must contain:

* Minimum 12 characters
* At least one number
* At least one special character

Password validation is currently called during user registration.

The password is validated **before** it is hashed.

Example:

```
Registration
    ↓
validate_password()
    ↓
hash_password()
    ↓
Store hashed password
```

The same password validator can be reused for future password reset functionality.

---
# Force reseting a password 
```
POST /api/v1/admin/users/{user_id}/force-reset-password

```
Changing password as requirement which meants the password policy.

# Login Rate Limiting

Login rate limiting is database-backed.

The system tracks failed login attempts using the `failed_login_attempts` table.

The current limit is:

```
5 failed attempts within 15 minutes
```

Two dimensions are checked:

### Per-email

Protects an individual account from credential-stuffing attacks.

### Per-IP

Protects against password spraying from a single IP address across multiple accounts.

Login is rejected with HTTP `429 Too Many Requests` when either limit is reached.

Unlike the earlier implementation, rate limiting is not dependent on an in-memory Python dictionary and therefore is not limited to a single Uvicorn worker.

---

# Logout

```
POST /api/v1/auth/logout
```

Body:

```json
{
    "refresh_token": "<refresh_token>"
}
```

The refresh token is marked as revoked in the database.

After logout, the revoked refresh token cannot be used to obtain a new access token.

---

# User Permissions

```
GET /api/v1/auth/me/permissions
```

Requires:

```
Authorization: Bearer <access_token>
```

Returns the effective permissions for the logged-in user based on the user's role and the configured role hierarchy.

---

# Admin User Management

Administrative user management is available under:
```
/api/v1/admin
```
The following operations are implemented.
# List Users
```
GET /api/v1/admin/users
```

Authorized roles:
* ceo
* vp_operations
Returns users stored in the database.
# Create User
```
POST /api/v1/admin/users
```

Example request:
```json
{
    "email": "r4testuser@company.com",
    "full_name": "R4 Test User",
    "password": "TestUser@12345",
    "role": "analyst"
}
```
The administrator:
* Checks whether the user already exists.
* Validates the password.
* Looks up the requested role.
* Hashes the password.
* Creates the user.
* Assigns the role.
* Records the initial role assignment in role-change history.

# Deactivate User
```
PATCH /api/v1/admin/users/{user_id}/deactivate
```

Authorized roles:
* ceo
8 vp_operations
A user can be deactivated by an authorized administrator.
An administrator cannot deactivate their own account.
# Change User Role
```
PATCH /api/v1/admin/users/{user_id}/role
```

Example request:
```json
{
    "role": "analyst"
}
```

* Role changes:
- Update the user's role.
- Record the previous role.
- Record the new role.
- Record the administrator who made the change.
- Create an authentication audit log.
# Role Change History
```
GET /api/v1/admin/users/{user_id}/role-history
```

Returns the role-change history for a user.
Each history record contains:
- History ID
- User ID
- Previous role
- New role
User who made the change
Timestamp
# Force Reset Password
```
POST /api/v1/admin/users/{user_id}/force-reset-password
```

Example request:
``` json
{
    "new_password": "NewPassword@12345"
}
```

The new password is validated against the password policy before hashing.
Only authorized administrators can perform this operation.
# Per-Session Management
Refresh tokens represent individual user sessions and are stored in the database.
* List Active Sessions
```
GET /api/v1/admin/users/{user_id}/sessions
```

Authorized roles:
* ceo
* vp_operations
The endpoint returns active sessions with:
- Session ID
- User ID
- Created timestamp
- Expiration timestamp
- Revocation status
- Refresh tokens themselves are not exposed through the session-management API.
Multiple Login Sessions
- Multiple successful logins for the same user create separate refresh-token sessions.
For example:
```
Login 1
    ↓
Session A

Login 2
    ↓
Session B
```

Session A and Session B have different refresh tokens and can be managed independently.
# Revoke Session
```
DELETE /api/v1/admin/users/{user_id}/sessions/{session_id}
```

- An administrator can revoke an individual session.
- The refresh token associated with that session is marked as revoked.
- A TOKEN_REVOKED authentication audit event is also recorded.
Example response:
``` json
{
    "message": "Session revoked successfully"
}
```

# Revoked Session Protection
After a session is revoked:
```
Refresh Token
      ↓
Database lookup
      ↓
is_revoked = True
      ↓
401 Unauthorized
```
The revoked refresh token cannot be used to create a new access token.

# Role Hierarchy Edge Cases
CEO receives all lower-level permissions defined by the hierarchy.
ceo
vp_operations
procurement_manager
logistics_manager
warehouse_manager
VP Operations
VP Operations receives its own and lower-level permissions, but does not receive CEO permissions.
vp_operations
procurement_manager
logistics_manager
warehouse_manager
CEO-only permissions are not inherited upward.
Supplier
Supplier only receives its explicitly configured supplier permission and cannot access administrator endpoints.
This verifies that role hierarchy does not accidentally grant unrelated roles administrative permissions.

# Password Reset Flow

The password reset flow is implemented as:
```
Request Reset
     ↓
Generate secure random token
     ↓
Store token in database
     ↓
Mock email/log output
     ↓
Reset Password
     ↓
Validate token
     ↓
Validate expiration
     ↓
Validate password
     ↓
Hash password
     ↓
Mark token as used
```

# Request Password Reset
```
POST /api/v1/auth/request-password-reset
```

The system generates a secure random password-reset token for an existing user.
The token is stored in the database with an expiration time.
A mock email service is used for development/testing.
The response does not reveal whether the supplied email exists.

# Reset Password
```
POST /api/v1/auth/reset-password
```

The reset operation validates:
Token exists.
Token has not already been used.
Token has not expired.
User exists.
New password satisfies the password policy.
After successful reset:
token.used = True
The same password-reset token cannot be used again.

# Authentication Audit Logging
Authentication-sensitive actions are recorded using the audit service.
Supported audit event types include:
LOGIN_SUCCESS
LOGIN_FAILED
ROLE_CHANGED
TOKEN_REVOKED
Audit records can be accessed by authorized administrators through:
```
GET /api/v1/admin/audit-logs
```

Optional filters:
user_id
event_type
The audit log records information such as:
- Event type
- User ID
- Email
- IP address
- Details
- Timestamp

# Seeded Users

Development and testing users are provided through:

```
app/seed.py
```

The seed process creates:

1. The configured roles.
2. The seeded users.
3. The relationship between users and roles.

Seeded users are stored in the database.

They are used for development and automated testing.

Example seeded users include:

```
ceo@company.com
vpoperations@company.com
procurementmanager@company.com
logisticsmanager@company.com
warehousemanager@company.com
compliance@company.com
analyst@company.com
supplier@company.com
```

Seeded users have roles assigned during the seeding process, allowing the authentication and RBAC flows to be tested immediately.

---

# Authentication Flow
Seed Database
    |
    v
Roles + Seeded Users
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
    +------------------+
    |                  |
    v                  v
Access Token       Refresh Token
    |                  |
    v                  v
Protected API      Database Storage
    |                  |
    v                  v
JWT Validation     Token Validation
    |                  |
    v                  v
RBAC / Hierarchy   Rotation / Revocation
    |
    v
User Access
Refresh Token Rotation
The refresh-token flow is:
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
Return Access Token + Token B
If an attacker attempts to replay Token A:
Token A
   ↓
Already revoked
   ↓
401 Unauthorized
This protects against refresh-token replay attacks.
Password Reset Flow
For a newly registered or existing user:
Request Password Reset
       |
       v
Generate secure token
       |
       v
Store token + expiration
       |
       v
Mock email
       |
       v
Submit reset token
       |
       v
Check token
       |
       +---- Invalid → 400
       |
       +---- Expired → 400
       |
       +---- Already used → 400
       |
       v
Validate new password
       |
       v
Hash password
       |
       v
Mark token used
       |
       v
Password changed
Newly Registered User Flow
Register
   |
   v
User created
   |
   v
role_id = NULL
   |
   v
Cannot login yet
   |
   v
Admin assigns role
   |
   v
User can login
---

# Setup

Create virtual environment:

```bash
python -m venv .venv
```

Activate:

```powershell
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create the environment file:

```bash
cp .env.example .env
```

Then set `SECRET_KEY` to a random value.

Generate one with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

# Database Initialization

Start the application:

```bash
python -m uvicorn app.main:app --reload
```

The application creates the database tables using:

```python
Base.metadata.create_all(bind=engine)
```

To insert the development roles and seeded users:

```bash
python -m app.seed
```

Run the seed command after the database tables have been created.

The seed operation is designed to avoid duplicating existing roles and users.

---

# Swagger

```
http://127.0.0.1:8000/docs
```

---

# Testing

Run:

```bash
pytest -q
```

- Authentication rate limiting

Failed-login attempts are tracked per email/IP within the configured rate-limit window. A successful login clears the recent failed-login counter for that email/IP.

- Self-registration

Self-registration creates the account with no role. Users without an assigned role cannot authenticate. An administrator must assign a role before the account becomes usable for login. This is intentional RBAC behavior.

Implemented tests cover:

* Root endpoint
* Successful login
* Invalid credentials
* Wrong role access
* RBAC access
* JWT validation
* Expired token
* Tampered token rejection
* Refresh token expiration
* Refresh token validation (success, wrong token type, malformed token)
* Logout and refresh-token revocation
* Rate limiting (per email + IP)
* CEO role hierarchy permissions
* User registration
* Password policy during registration
* Role Hierarchy
* Admin user management
* Per-session management
* Role hierarchy edge cases






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
  "user_id": 123,
  "email": "supplier@company.com",
  "full_name": "Supplier User",
  "role": "supplier",
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
  "detail": "Insufficient permissions"
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
       | X-Service-API-Key
       v
Platform Service
       |
       v
Validate service credential
```

Example:

```http
X-Service-API-Key: <service-api-key>
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
  "user_id": 123,
  "email": "...",
  "full_name": "...",
  "role": "supplier",
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

Run the complete test suite:

```bash
pytest -q
```

Run authentication tests:

```bash
pytest -q tests/test_auth.py
```

Run R5 real integration tests:

```bash
pytest -q tests/test_integration.py
```

Remember that `test_integration.py` requires the Platform Service to already be running on port `8005`.

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

R5 integration tests additionally cover:

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
5xx → Platform/service availability problem
```

--


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

