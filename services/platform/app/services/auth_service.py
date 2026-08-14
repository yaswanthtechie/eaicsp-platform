from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from app.schemas.user import Role
from app.core.security import hash_password, verify_password

from app.core.security import (
    create_access_token,
    create_refresh_token
)  

login_attempts = {}

MAX_ATTEMPTS = 5
WINDOW = timedelta(minutes=15)


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

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    if not user["is_active"]:
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

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


users = {
    "ceo@company.com": {
        "user_id": 1,
        "email": "ceo@company.com",
        "password": hash_password("ceo123"),
        "full_name": "Company CEO",
        "role": Role.ceo,
        "is_active": True,
    },
    "warehousemanager@company.com": {
        "user_id": 2,
        "email": "warehousemanager@company.com",
        "password": hash_password("warehouse123"),
        "full_name": "Warehouse Manager",
        "role": Role.warehouse_manager,
        "is_active": True,
    },
    "vpoperations@company.com":{
                "user_id": 3,
                "email": "vpoperations@company.com",
                "password": hash_password("vpop123"),
                "full_name": "vp_operations Manager",
                "role": Role.vp_operations,
                "is_active": True,
    },
    "procurementmanager@company.com":{
                "user_id":4,
                "email":"procurementmanager@company.com",
                "password":hash_password("prm123"),
                "full_name":"procurement_manager",
                "role":Role.procurement_manager,
                "is_active":True,

    },
     "logisticsmanager@company.com":{
                    "user_id":5,
                    "email":"logisticsmanager@company.com",
                    "password":hash_password("lom123"),
                    "full_name":"logistics_manager",
                    "role":Role.logistics_manager,
                    "is_active":True,
     },
    "compliance@company.com":{
                    "user_id":6,
                    "email":"compliance@company.com",
                    "password":hash_password("comp123"),
                    "full_name":"compliance_officer",
                    "role":Role.compliance_officer,
                    "is_active":True,
    },
    "analyst@company.com":{
                            "user_id":7,
                            "email":"analyst@company.com",
                            "password":hash_password("an123"),
                            "full_name":"analyst",
                            "role":Role.analyst,
                            "is_active":True,
    },
    "supplier@company.com":{
                            "user_id":8,
                            "email":"supplier@company.com",
                            "password":hash_password("sup123"),
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
