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

Registration behavior: Self-registration creates the account without a role. The account must be assigned a role by an authorized administrator before the user can log in. Until a role is assigned, login returns 401 User role is not assigned

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


