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
├── services/
│   └── auth_service.py
├── core/
│   ├── config.py
│   ├── security.py
│   └── dependencies.py
│   └── password_validator.py
└── models/
│   ├── failed_login_attempts.py
│   ├── refresh_token.py
│   ├── roles.py
│   ├── users.py
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

Therefore, a newly registered user cannot successfully log in until an authorized administrator assigns a role.

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

```
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
     |
     v
JWT Validation
     |
     v
RBAC / Role Hierarchy
     |
     v
User Access
```

For a newly registered user:

```
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
```

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