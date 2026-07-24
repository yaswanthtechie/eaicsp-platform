from app.schemas.user import Role
from app.core.security import hash_password, verify_password
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