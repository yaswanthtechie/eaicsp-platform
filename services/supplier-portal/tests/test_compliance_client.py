import httpx
import pytest

from app.core.config import settings
from app.services.compliance_client import (
    ComplianceServiceError,
    ComplianceServiceUnavailableError,
    check_supplier_compliance,
)


# ============================================================
# TEST DATA
# ============================================================

SUPPLIER_ID = "SUP001"
SUPPLIER_NAME = "ABC Supplies Pvt Ltd"
COUNTRY = "India"


def make_response(
    *,
    json_data=None,
    json_error=False,
    status_code=200,
):
    """
    Create a lightweight fake httpx response.
    """

    class FakeResponse:
        def raise_for_status(self):
            if status_code >= 400:
                request = httpx.Request(
                    "POST",
                    "http://testserver/api/v1/compliance/internal-check",
                )

                response = httpx.Response(
                    status_code=status_code,
                    request=request,
                )

                raise httpx.HTTPStatusError(
                    f"HTTP {status_code}",
                    request=request,
                    response=response,
                )

        def json(self):
            if json_error:
                raise ValueError("Invalid JSON")

            return json_data

    return FakeResponse()


class FakeClient:
    """
    Fake httpx.Client used to inspect:
    - timeout
    - URL
    - payload
    - headers
    - returned response
    """

    last_instance = None

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.post_calls = []

        FakeClient.last_instance = self

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def post(self, url, json, headers):
        self.post_calls.append(
            {
                "url": url,
                "json": json,
                "headers": headers,
            }
        )

        return self.response


# ============================================================
# SUCCESS CASES
# ============================================================


def test_compliance_client_returns_clear_response(monkeypatch):
    fake_response = make_response(
        json_data={
            "cleared": True,
            "decision": "CLEAR",
            "reason": "No sanctions or watchlist match found.",
        }
    )

    def fake_init(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.post_calls = []
        self.response = fake_response
        FakeClient.last_instance = self

    monkeypatch.setattr(
        "app.services.compliance_client.httpx.Client",
        type(
            "TestClient",
            (FakeClient,),
            {
                "__init__": fake_init,
            },
        ),
    )

    result = check_supplier_compliance(
        supplier_id=SUPPLIER_ID,
        supplier_name=SUPPLIER_NAME,
        country=COUNTRY,
    )

    assert result["cleared"] is True
    assert result["decision"] == "CLEAR"
    assert result["reason"] == (
        "No sanctions or watchlist match found."
    )


@pytest.mark.parametrize(
    "decision,cleared",
    [
        ("CLEAR", True),
        ("BLOCK", False),
        ("REVIEW", False),
    ],
)
def test_compliance_client_accepts_all_valid_decisions(
    monkeypatch,
    decision,
    cleared,
):
    fake_response = make_response(
        json_data={
            "cleared": cleared,
            "decision": decision,
            "reason": f"Decision is {decision}.",
        }
    )

    class TestClient(FakeClient):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.response = fake_response

    monkeypatch.setattr(
        "app.services.compliance_client.httpx.Client",
        TestClient,
    )

    result = check_supplier_compliance(
        supplier_id=SUPPLIER_ID,
        supplier_name=SUPPLIER_NAME,
        country=COUNTRY,
    )

    assert result["decision"] == decision
    assert result["cleared"] is cleared


def test_compliance_client_returns_complete_response_unchanged(
    monkeypatch,
):
    expected = {
        "cleared": True,
        "decision": "CLEAR",
        "reason": "No sanctions or watchlist match found.",
        "extra_field": "extra-value",
    }

    fake_response = make_response(json_data=expected)

    class TestClient(FakeClient):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.response = fake_response

    monkeypatch.setattr(
        "app.services.compliance_client.httpx.Client",
        TestClient,
    )

    result = check_supplier_compliance(
        supplier_id=SUPPLIER_ID,
        supplier_name=SUPPLIER_NAME,
        country=COUNTRY,
    )

    assert result == expected


# ============================================================
# REQUEST CONSTRUCTION
# ============================================================


def test_compliance_client_uses_correct_url(
    monkeypatch,
):
    fake_response = make_response(
        json_data={
            "cleared": True,
            "decision": "CLEAR",
            "reason": "Clean",
        }
    )

    class TestClient(FakeClient):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.response = fake_response

    monkeypatch.setattr(
        "app.services.compliance_client.httpx.Client",
        TestClient,
    )

    monkeypatch.setattr(
        settings,
        "COMPLIANCE_SERVICE_URL",
        "http://127.0.0.1:8000/",
    )

    check_supplier_compliance(
        supplier_id=SUPPLIER_ID,
        supplier_name=SUPPLIER_NAME,
        country=COUNTRY,
    )

    client = FakeClient.last_instance

    assert client.post_calls[0]["url"] == (
        "http://127.0.0.1:8000"
        "/api/v1/compliance/internal-check"
    )


def test_compliance_client_removes_trailing_slash_from_base_url(
    monkeypatch,
):
    fake_response = make_response(
        json_data={
            "cleared": True,
            "decision": "CLEAR",
            "reason": "Clean",
        }
    )

    class TestClient(FakeClient):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.response = fake_response

    monkeypatch.setattr(
        "app.services.compliance_client.httpx.Client",
        TestClient,
    )

    monkeypatch.setattr(
        settings,
        "COMPLIANCE_SERVICE_URL",
        "http://compliance-service:8000////",
    )

    check_supplier_compliance(
        supplier_id=SUPPLIER_ID,
        supplier_name=SUPPLIER_NAME,
        country=COUNTRY,
    )

    client = FakeClient.last_instance

    assert client.post_calls[0]["url"] == (
        "http://compliance-service:8000"
        "/api/v1/compliance/internal-check"
    )


def test_compliance_client_sends_correct_payload(
    monkeypatch,
):
    fake_response = make_response(
        json_data={
            "cleared": True,
            "decision": "CLEAR",
            "reason": "Clean",
        }
    )

    class TestClient(FakeClient):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.response = fake_response

    monkeypatch.setattr(
        "app.services.compliance_client.httpx.Client",
        TestClient,
    )

    check_supplier_compliance(
        supplier_id=SUPPLIER_ID,
        supplier_name=SUPPLIER_NAME,
        country=COUNTRY,
    )

    client = FakeClient.last_instance

    assert client.post_calls[0]["json"] == {
        "supplier_id": SUPPLIER_ID,
        "supplier_name": SUPPLIER_NAME,
        "country": COUNTRY,
    }


def test_compliance_client_sends_correct_caller_header(
    monkeypatch,
):
    fake_response = make_response(
        json_data={
            "cleared": True,
            "decision": "CLEAR",
            "reason": "Clean",
        }
    )

    class TestClient(FakeClient):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.response = fake_response

    monkeypatch.setattr(
        "app.services.compliance_client.httpx.Client",
        TestClient,
    )

    check_supplier_compliance(
        supplier_id=SUPPLIER_ID,
        supplier_name=SUPPLIER_NAME,
        country=COUNTRY,
    )

    client = FakeClient.last_instance

    assert client.post_calls[0]["headers"] == {
        "X-Caller-Service": "supplier-portal",
    }


def test_compliance_client_uses_five_second_timeout(
    monkeypatch,
):
    fake_response = make_response(
        json_data={
            "cleared": True,
            "decision": "CLEAR",
            "reason": "Clean",
        }
    )

    class TestClient(FakeClient):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.response = fake_response

    monkeypatch.setattr(
        "app.services.compliance_client.httpx.Client",
        TestClient,
    )

    check_supplier_compliance(
        supplier_id=SUPPLIER_ID,
        supplier_name=SUPPLIER_NAME,
        country=COUNTRY,
    )

    client = FakeClient.last_instance

    assert client.kwargs["timeout"] == 5.0

# ============================================================
# SERVICE UNAVAILABLE CASES
# ============================================================

@pytest.mark.parametrize(
    "exception",
    [
        httpx.TimeoutException("timeout"),
        httpx.ConnectError("connection failed"),
        httpx.NetworkError("network failed"),
        httpx.RemoteProtocolError("server disconnected"),
    ],
)
def test_compliance_client_maps_network_failures_to_503_error(
    monkeypatch,
    exception,
):
    class TestClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def post(self, url, json, headers):
            raise exception

    monkeypatch.setattr(
        "app.services.compliance_client.httpx.Client",
        TestClient,
    )

    with pytest.raises(
        ComplianceServiceUnavailableError,
        match="Compliance Service is unavailable.",
    ):
        check_supplier_compliance(
            supplier_id=SUPPLIER_ID,
            supplier_name=SUPPLIER_NAME,
            country=COUNTRY,
        )
# ============================================================
# HTTP ERROR CASES
# ============================================================


@pytest.mark.parametrize(
    "status_code",
    [400, 401, 403, 404, 409, 422, 500, 502, 503],
)
def test_compliance_client_maps_http_errors_to_service_error(
    monkeypatch,
    status_code,
):
    fake_response = make_response(
        status_code=status_code,
    )

    class TestClient(FakeClient):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.response = fake_response

    monkeypatch.setattr(
        "app.services.compliance_client.httpx.Client",
        TestClient,
    )

    with pytest.raises(
        ComplianceServiceError,
        match="Compliance Service returned an error.",
    ):
        check_supplier_compliance(
            supplier_id=SUPPLIER_ID,
            supplier_name=SUPPLIER_NAME,
            country=COUNTRY,
        )


# ============================================================
# INVALID JSON
# ============================================================


def test_compliance_client_rejects_invalid_json(
    monkeypatch,
):
    fake_response = make_response(
        json_error=True,
    )

    class TestClient(FakeClient):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.response = fake_response

    monkeypatch.setattr(
        "app.services.compliance_client.httpx.Client",
        TestClient,
    )

    with pytest.raises(
        ComplianceServiceError,
        match="Compliance Service returned an invalid response.",
    ):
        check_supplier_compliance(
            supplier_id=SUPPLIER_ID,
            supplier_name=SUPPLIER_NAME,
            country=COUNTRY,
        )


# ============================================================
# INVALID DECISION
# ============================================================


@pytest.mark.parametrize(
    "decision",
    [
        "UNKNOWN",
        "CLEARANCE",
        "BLOCKED",
        "APPROVE",
        "",
        None,
    ],
)
def test_compliance_client_rejects_invalid_decision(
    monkeypatch,
    decision,
):
    fake_response = make_response(
        json_data={
            "cleared": True,
            "decision": decision,
            "reason": "Test reason",
        }
    )

    class TestClient(FakeClient):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.response = fake_response

    monkeypatch.setattr(
        "app.services.compliance_client.httpx.Client",
        TestClient,
    )

    with pytest.raises(
        ComplianceServiceError,
        match="Compliance Service returned an invalid decision.",
    ):
        check_supplier_compliance(
            supplier_id=SUPPLIER_ID,
            supplier_name=SUPPLIER_NAME,
            country=COUNTRY,
        )


def test_compliance_client_rejects_missing_decision(
    monkeypatch,
):
    fake_response = make_response(
        json_data={
            "cleared": True,
            "reason": "No decision provided.",
        }
    )

    class TestClient(FakeClient):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.response = fake_response

    monkeypatch.setattr(
        "app.services.compliance_client.httpx.Client",
        TestClient,
    )

    with pytest.raises(
        ComplianceServiceError,
        match="Compliance Service returned an invalid decision.",
    ):
        check_supplier_compliance(
            supplier_id=SUPPLIER_ID,
            supplier_name=SUPPLIER_NAME,
            country=COUNTRY,
        )


# ============================================================
# INVALID CLEARED VALUE
# ============================================================


@pytest.mark.parametrize(
    "cleared",
    [
        "true",
        "false",
        1,
        0,
        None,
        [],
        {},
    ],
)
def test_compliance_client_rejects_invalid_cleared_value(
    monkeypatch,
    cleared,
):
    fake_response = make_response(
        json_data={
            "cleared": cleared,
            "decision": "CLEAR",
            "reason": "Test reason",
        }
    )

    class TestClient(FakeClient):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.response = fake_response

    monkeypatch.setattr(
        "app.services.compliance_client.httpx.Client",
        TestClient,
    )

    with pytest.raises(
        ComplianceServiceError,
        match="Compliance Service returned an invalid clearance value.",
    ):
        check_supplier_compliance(
            supplier_id=SUPPLIER_ID,
            supplier_name=SUPPLIER_NAME,
            country=COUNTRY,
        )


def test_compliance_client_rejects_missing_cleared_value(
    monkeypatch,
):
    fake_response = make_response(
        json_data={
            "decision": "CLEAR",
            "reason": "No cleared value provided.",
        }
    )

    class TestClient(FakeClient):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.response = fake_response

    monkeypatch.setattr(
        "app.services.compliance_client.httpx.Client",
        TestClient,
    )

    with pytest.raises(
        ComplianceServiceError,
        match="Compliance Service returned an invalid clearance value.",
    ):
        check_supplier_compliance(
            supplier_id=SUPPLIER_ID,
            supplier_name=SUPPLIER_NAME,
            country=COUNTRY,
        )

@pytest.mark.parametrize(
    "decision,cleared",
    [
        ("CLEAR", False),
        ("BLOCK", True),
        ("REVIEW", True),
    ],
)
def test_compliance_client_rejects_contradictory_decision(
    monkeypatch,
    decision,
    cleared,
):
    fake_response = make_response(
        json_data={
            "cleared": cleared,
            "decision": decision,
            "reason": "Contradictory response.",
        }
    )

    class TestClient(FakeClient):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.response = fake_response

    monkeypatch.setattr(
        "app.services.compliance_client.httpx.Client",
        TestClient,
    )

    with pytest.raises(
        ComplianceServiceError,
        match="contradictory",
    ):
        check_supplier_compliance(
            supplier_id=SUPPLIER_ID,
            supplier_name=SUPPLIER_NAME,
            country=COUNTRY,
        )