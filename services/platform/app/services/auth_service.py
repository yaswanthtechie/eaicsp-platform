from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from app.schemas.user import Role
from app.core.security import hash_password, verify_password

from app.core.security import (
    create_access_token,
    create_refresh_token
)  
from datetime import timedelta
from app.database import SessionLocal
from app.models.refresh_token import RefreshToken
from app.models.failed_login_attempts import FailedLoginAttempt

from app.core.config import REFRESH_TOKEN_EXPIRE_DAYS

login_attempts = {}

MAX_ATTEMPTS = 5
WINDOW = timedelta(minutes=15)

def save_refresh_token(user_id: int, token: str, expires_at):
    
    db = SessionLocal()
    try:
        refresh = RefreshToken(
            user_id=user_id,
            token=token,
            expires_at=datetime.now(
                timezone.utc
            ) + timedelta(
                days=REFRESH_TOKEN_EXPIRE_DAYS
            )

        )
        db.add(refresh)
        db.commit()
    finally:
        db.close()


'''def get_refresh_token(
    token: str
):
    db = SessionLocal()
    try:

        refresh = (
            db.query(RefreshToken)
            .filter(
                RefreshToken.token == token
            )
            .first()
        )

        if refresh is None:
            return None

        if refresh.is_revoked:
            return None

        return refresh

    finally:

        db.close()


def revoke_refresh_token(
    token: str
):

    db = SessionLocal()
    try:
        refresh = (
            db.query(RefreshToken)
            .filter(
                RefreshToken.token == token
            )
            .first()
        )
        if refresh is None:
            return False

        refresh.is_revoked = True
        db.commit()
        return True
    
    finally:
        db.close()'''
def get_refresh_token(token: str):

    db = SessionLocal()

    try:
        return (
            db.query(RefreshToken)
            .filter(
                RefreshToken.token == token,
                RefreshToken.is_revoked == False
            )
            .first()
        )

    finally:
        db.close()


def revoke_refresh_token(token: str):

    db = SessionLocal()

    try:

        refresh = (
            db.query(RefreshToken)
            .filter(RefreshToken.token == token)
            .first()
        )

        if refresh is None:
            return False

        refresh.is_revoked = True

        db.commit()

        return True

    finally:
        db.close()


def log_failed_login(email: str, ip_address: str):
    db = SessionLocal()
    try:
        db.add(
            FailedLoginAttempt(
                email=email,
                ip_address=ip_address
            )
        )
        db.commit()

    finally:
        db.close()

def login_user(
    username: str,
    password: str,
    client_ip: str
):

    now = datetime.now(timezone.utc)
    # Key on (email, ip) so a few bad attempts for one account cannot lock out
    # every other user sharing that IP (NAT / office network / load balancer).
    key = (username.lower(),client_ip)

    attempts = [
        t for t in login_attempts.get(key,[])
        if now - t < WINDOW
    ]

    if len(attempts) >= MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Try again after 15 minutes."
        )

    user = login(username, password)

    if not user:

        attempts.append(now)

        login_attempts[key] = attempts
        log_failed_login(
            email=username,
            ip_address=client_ip
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    if not user["is_active"]:
        log_failed_login(
            email=username,
            ip_address=client_ip
        )
        raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User account is inactive"
                )

    login_attempts.pop(key, None)

    access_token = create_access_token(
        {
            "sub": user["email"],
            "role": user["role"].value,
            "user_id": user["user_id"]
        }
    )

    refresh_token = create_refresh_token(
        {
            "sub": user["email"],
            "user_id": user["user_id"]
        }
    )
    save_refresh_token(
        user_id=user["user_id"],
        token=refresh_token,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7)
    )
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }

users = {
    "ceo@company.com": {
        "user_id": 1,
        "email": "ceo@company.com",
        "password": hash_password("ceocompany@123"),
        "full_name": "Company CEO",
        "role": Role.ceo,
        "is_active": True,
    },
    "warehousemanager@company.com": {
        "user_id": 2,
        "email": "warehousemanager@company.com",
        "password": hash_password("warehouse@123"),
        "full_name": "Warehouse Manager",
        "role": Role.warehouse_manager,
        "is_active": True,
    },
    "vpoperations@company.com":{
                "user_id": 3,
                "email": "vpoperations@company.com",
                "password": hash_password("vpoperations@123"),
                "full_name": "vp_operations Manager",
                "role": Role.vp_operations,
                "is_active": True,
    },
    "procurementmanager@company.com":{
                "user_id":4,
                "email":"procurementmanager@company.com",
                "password":hash_password("procurement@123"),
                "full_name":"procurement_manager",
                "role":Role.procurement_manager,
                "is_active":True,

    },
     "logisticsmanager@company.com":{
                    "user_id":5,
                    "email":"logisticsmanager@company.com",
                    "password":hash_password("logistics@123"),
                    "full_name":"logistics_manager",
                    "role":Role.logistics_manager,
                    "is_active":True,
     },
    "compliance@company.com":{
                    "user_id":6,
                    "email":"compliance@company.com",
                    "password":hash_password("compliance@123"),
                    "full_name":"compliance_officer",
                    "role":Role.compliance_officer,
                    "is_active":True,
    },
    "analyst@company.com":{
                            "user_id":7,
                            "email":"analyst@company.com",
                            "password":hash_password("analyst@123"),
                            "full_name":"analyst",
                            "role":Role.analyst,
                            "is_active":True,
    },
    "supplier@company.com":{
                            "user_id":8,
                            "email":"supplier@company.com",
                            "password":hash_password("supplier@123"),
                            "full_name":"supplier",
                            "role":Role.supplier,
                            "is_active":True,
    }
        
}
def login(username: str, password: str):

    user = users.get(username)

    if user is None:
        return None

    if not verify_password(password, user["password"]):
        return None

    return user

