# Platform Service

## Overview

Platform Service handles authentication and authorization for the Supply Chain Management System.

# Features

* User authentication
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
```
---

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

* refresh_tokens
* failed_login_attempts

---

## API Endpoints

### Login

```
POST /api/v1/auth/login
```
Returns JWT access token and refresh token.
---

### Refresh Token
```
POST /api/v1/auth/refresh
```
Takes a JSON body:
{"refresh_token": "<your refresh token>"}
Return a new access token

---

### Current User

```
GET /api/v1/users/me
```
Returns logged-in user details.
Requires:

```
Authorization: Bearer <token>
```

---
### RBAC Test
```
GET /api/v1/admin/test
```

Allowed roles:

```
ceo
vp_operations
```



# Role Hierarchy

```
ceo
└── vp_operations
    └── procurement_manager
        └── logistics_manager
            └── warehouse_manager
```

Higher roles automatically inherit permissions from lower roles.

Example:

* CEO automatically has VP Operations permissions.
* VP Operations automatically has Procurement Manager permissions.

---

# Password Policy

Passwords must contain:

* Minimum 12 characters
* At least one uppercase letter
* At least one lowercase letter
* At least one number
* At least one special character

Passwords are securely hashed using BCrypt before storage.
Here We will be calling password validator in register,reset password as they aren't having endpoints just used it.
## Logout

```
POST /api/v1/auth/logout
```

Body

```json
{
    "refresh_token": "<refresh_token>"
}
```

Revokes the refresh token from the database.

After logout, the refresh token cannot be used again.

---


## User Permissions

```
GET /api/v1/auth/me/permissions
```

Headers

```
Authorization: Bearer <access_token>
```

Returns all effective permissions for the logged-in user based on the role hierarchy.

---


---
## Authentication Flow
```
Login
  |
Validate User
  |
Generate JWT
  |
Access Token + Refresh Token
  |
Protected API
  |
JWT Validation
  |
User Access
```
---
## Setup
Create virtual environment:

```
python -m venv .venv
```
Activate:

```
.venv\Scripts\activate
```
Install:

```
pip install -r requirements.txt
```
Create your env file:

cp .env.example .env
Then set `SECRET_KEY` to a random value. Generate one with:
python -c "import secrets; print(secrets.token_urlsafe(32))"

Run:

```
uvicorn app.main:app --reload
```

Swagger:

```
http://127.0.0.1:8000/docs
```

---
## Testing

Implemented tests:

- Login success
- Invalid credentials
- JWT validation
- Expired token
- Wrong role access
- Refresh token validation (success, wrong token type, malformed token)
- Tampered token rejection
- Rate limiting (per account + IP)
- Logout revokes refresh token
- CEO inherits VP Operations permissions
---



