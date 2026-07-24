# Platform Service

## Overview

Platform Service handles authentication and authorization for the Supply Chain Management System.

Features:
- User authentication
- JWT token generation
- Refresh token flow
- Protected APIs
- Role Based Access Control (RBAC)
---
## Tech Stack

- FastAPI
- Python
- Pydantic
- Uvicorn
- python-jose
- passlib
- bcrypt
---

## Project Structure

```
app/
├── main.py
├── routes/
│   ├── auth.py
│   ├── users.py
│   └── admin.py
├── schemas/
│   ├── auth.py
│   └── user.py
├── services/
│   └── auth_service.py
├── core/
│   ├── config.py
│   ├── security.py
│   └── dependencies.py
└── models/
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
Generates a new access token using refresh token.

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
- Refresh token validation
