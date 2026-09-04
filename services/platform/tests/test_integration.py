import os
import uuid
import httpx
import pytest


BASE_URL = os.getenv(
    "PLATFORM_SERVICE_URL",
    "http://127.0.0.1:8005",
)

API_PREFIX = "/api/v1"

LOGIN_URL = f"{BASE_URL}{API_PREFIX}/auth/login"
VERIFY_URL = f"{BASE_URL}{API_PREFIX}/auth/verify"


TEST_USERS = {
    "supplier": {
        "email": "supplier@company.com",
        "password": "supplier@123",
        "role": "supplier",
    },
    "warehouse_manager": {
        "email": "warehousemanager@company.com",
        "password": "warehouse@123",
        "role": "warehouse_manager",
    },
    "vp_operations": {
        "email": "vpoperations@company.com",
        "password": "vpoperations@123",
        "role": "vp_operations",
    },
}


# ============================================================
# HELPERS
# ============================================================
def login(user):
    """
    Real HTTP login against the running Platform Service.
    Adjust json/data here to exactly match your published
    /auth/login contract.
    """
    response = httpx.post(
        LOGIN_URL,
        data={
            "username": user["email"],
            "password": user["password"],
        },
        timeout=10,
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert "access_token" in data

    return data["access_token"]


def verify_request(token, service="inventory-service"):
    request_id = str(uuid.uuid4())

    return httpx.post(
        VERIFY_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "X-Caller-Service": service,
            "X-Request-ID": request_id,
        },
        timeout=10,
    )


# ============================================================
# R5-1: REAL HTTP LOGIN / INTEGRATION CONTRACT
# ============================================================

def test_real_http_login():
    """
    R5:
    Proves documented login contract works through real HTTP.
    """

    user = TEST_USERS["supplier"]

    token = login(user)

    assert token
    assert isinstance(token, str)


# ============================================================
# R5-2: DEDICATED SERVICE-TO-SERVICE /VERIFY ENDPOINT
# ============================================================

def test_verify_valid_token():
    """
    R5:
    POST /api/v1/auth/verify accepts a valid JWT and
    returns authenticated user information and role.
    """

    user = TEST_USERS["supplier"]

    token = login(user)

    response = verify_request(token)

    assert response.status_code == 200

    data = response.json()

    assert data["email"] == user["email"]
    assert data["role"] == user["role"]
    assert data["is_active"] is True


def test_verify_warehouse_manager_role():
    """
    R5:
    Verify returns the correct role for another dependent user.
    """

    user = TEST_USERS["warehouse_manager"]

    token = login(user)

    response = verify_request(token)

    assert response.status_code == 200

    data = response.json()

    assert data["role"] == "warehouse_manager"


def test_verify_vp_operations_role():
    """
    R5:
    Verify returns the correct role for another dependent user.
    """

    user = TEST_USERS["vp_operations"]

    token = login(user)

    response = verify_request(token)

    assert response.status_code == 200

    data = response.json()

    assert data["role"] == "vp_operations"


# ============================================================
# R5-3: CONSISTENT 401 ERROR RESPONSES
# ============================================================

def test_verify_missing_token():
    response = httpx.post(
        VERIFY_URL,
        headers={
            "X-Caller-Service": "inventory-service",
            "X-Request-ID": str(uuid.uuid4()),
        },
        timeout=10,
    )

    assert response.status_code == 401

    data = response.json()

    assert list(data.keys()) == ["detail"]
    assert isinstance(data["detail"], str)
    assert data["detail"]


def test_verify_invalid_token():
    response = verify_request("invalid-token")

    assert response.status_code == 401

    data = response.json()

    assert list(data.keys()) == ["detail"]
    assert isinstance(data["detail"], str)


def test_verify_empty_authorization_header():
    response = httpx.post(
        VERIFY_URL,
        headers={
            "Authorization": "",
            "X-Caller-Service": "inventory-service",
            "X-Request-ID": str(uuid.uuid4()),
        },
        timeout=10,
    )

    assert response.status_code == 401

    data = response.json()

    assert list(data.keys()) == ["detail"]


def test_verify_tampered_token():
    user = TEST_USERS["supplier"]

    token = login(user)

    tampered_token = token[:-1] + (
        "a" if token[-1] != "a" else "b"
    )

    response = verify_request(tampered_token)

    assert response.status_code == 401

    data = response.json()

    assert list(data.keys()) == ["detail"]


# ============================================================
# R5-4: 403 FOR VALID TOKEN + WRONG ROLE
# ============================================================

def test_valid_token_wrong_role_returns_403():
    """
    R5:
    Authentication succeeds, but authorization fails.
    Therefore response must be 403, not 401.
    """

    user = TEST_USERS["supplier"]

    token = login(user)

    response = httpx.get(
        f"{BASE_URL}{API_PREFIX}/admin/users",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Caller-Service": "inventory-service",
            "X-Request-ID": str(uuid.uuid4()),
        },
        timeout=10,
    )

    assert response.status_code == 403

    data = response.json()

    assert list(data.keys()) == ["detail"]
    assert isinstance(data["detail"], str)
    assert data["detail"]


# ============================================================
# R5-5: SERVICE CALLER IDENTIFICATION / REQUEST LOGGING
# ============================================================

def test_caller_service_header_accepted():
    """
    R5:
    Dependent services identify themselves through
    X-Caller-Service.
    """

    user = TEST_USERS["supplier"]

    token = login(user)

    response = verify_request(
        token,
        service="inventory-service",
    )

    assert response.status_code == 200


def test_request_id_header_accepted():
    """
    R5:
    Request ID is accepted for tracing/debugging.
    """

    user = TEST_USERS["supplier"]

    token = login(user)

    request_id = str(uuid.uuid4())

    response = httpx.post(
        VERIFY_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "X-Caller-Service": "inventory-service",
            "X-Request-ID": request_id,
        },
        timeout=10,
    )

    assert response.status_code == 200


# ============================================================
# R5-6: CONCURRENT SERVICE LOAD
# ============================================================

def test_five_services_can_call_verify_concurrently():
    """
    R5:
    Simulate 5 dependent services calling /verify at the
    same time.
    """

    user = TEST_USERS["supplier"]

    token = login(user)

    services = [
        "inventory-service",
        "logistics-service",
        "compliance-service",
        "supplier-portal",
        "api-gateway",
    ]

    def call_verify(service):
        return verify_request(
            token,
            service=service,
        )

    with httpx.Client(timeout=10) as client:

        requests = [
            client.build_request(
                "POST",
                VERIFY_URL,
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Caller-Service": service,
                    "X-Request-ID": str(uuid.uuid4()),
                },
            )
            for service in services
        ]

        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=5
        ) as executor:

            responses = list(
                executor.map(
                    client.send,
                    requests,
                )
            )

    assert len(responses) == 5

    for response in responses:
        assert response.status_code == 200


def test_twenty_concurrent_verify_requests():
    """
    R5:
    Higher concurrent load against /verify.
    """

    user = TEST_USERS["supplier"]

    token = login(user)

    def call_verify(_):
        return verify_request(
            token,
            service="inventory-service",
        )

    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=20
    ) as executor:

        responses = list(
            executor.map(
                call_verify,
                range(20),
            )
        )

    assert len(responses) == 20

    assert all(
        response.status_code == 200
        for response in responses
    )


# ============================================================
# R5-7: END-TO-END CONTRACT
# ============================================================

def test_complete_r5_authentication_flow():
    """
    R5 end-to-end:

    1. Service/user logs in
    2. Receives JWT
    3. Dependent service sends JWT to /verify
    4. Platform validates JWT
    5. Platform returns user + role
    """

    user = TEST_USERS["supplier"]

    # 1. Login
    token = login(user)

    assert token

    # 2. Service calls /verify
    response = verify_request(
        token,
        service="inventory-service",
    )

    # 3. Platform validates token
    assert response.status_code == 200

    data = response.json()

    # 4. Verify contract
    assert data["email"] == user["email"]
    assert data["role"] == user["role"]
    assert data["is_active"] is True