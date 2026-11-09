
import httpx
import pytest

from app.core.config import settings
from app.services import supplier_risk_client


class FakeResponse:
    def __init__(self, data=None, status_error=None, json_error=None):
        self.data = data
        self.status_error = status_error
        self.json_error = json_error

    def raise_for_status(self):
        if self.status_error:
            raise self.status_error

    def json(self):
        if self.json_error:
            raise self.json_error
        return self.data


class FakeClient:
    response = None
    init_kwargs = None
    request_args = None
    transport_error = None

    def __init__(self, **kwargs):
        FakeClient.init_kwargs = kwargs

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def get(self, url, headers=None):
        FakeClient.request_args = {
            "url": url,
            "headers": headers,
        }

        if FakeClient.transport_error:
            raise FakeClient.transport_error

        return FakeClient.response


@pytest.fixture(autouse=True)
def setup_client(monkeypatch):
    FakeClient.response = None
    FakeClient.init_kwargs = None
    FakeClient.request_args = None
    FakeClient.transport_error = None

    monkeypatch.setattr(
        supplier_risk_client.httpx,
        "Client",
        FakeClient,
    )

    monkeypatch.setattr(
        settings,
        "SUPPLIER_RISK_SERVICE_URL",
        "http://localhost:8006/",
    )

    monkeypatch.setattr(
        settings,
        "SUPPLIER_PORTAL_SERVICE_API_KEY",
        "test-api-key",
    )


def valid_risk_response():
    return {
        "supplier_id": "SUP-00045",
        "score": 78.5,
        "tier": "High",
        "top_factors": [
            {
                "factor": "sanctions",
                "category": "Security",
                "weight": 45,
                "description": "Supplier matched a sanctions signal.",
            }
        ],
        "top_evidence_articles": [
            {
                "headline": "Supplier sanctions investigation",
                "date": "2026-10-15",
                "sentiment": "negative",
                "score": 78.5,
                "signals": [
                    {
                        "keyword": "sanction",
                        "weight": 45,
                    }
                ],
            }
        ],
        "computed_at": "2026-10-15T10:30:00Z",
    }


def test_get_supplier_risk_score_success():
    FakeClient.response = FakeResponse(valid_risk_response())

    result = supplier_risk_client.get_supplier_risk_score(
        "SUP-00045"
    )

    assert result["supplier_id"] == "SUP-00045"
    assert result["score"] == 78.5
    assert result["tier"] == "High"

    assert FakeClient.request_args["url"] == (
        "http://localhost:8006/api/v1/suppliers/"
        "SUP-00045/risk-score"
    )

    assert FakeClient.request_args["headers"] == {
        "X-API-Key": "test-api-key",
    }

    assert FakeClient.init_kwargs == {"timeout": 2.0}


def test_null_risk_score_is_valid():
    response = valid_risk_response()
    response["score"] = None
    response["tier"] = None
    response["top_factors"] = []
    response["top_evidence_articles"] = []

    FakeClient.response = FakeResponse(response)

    result = supplier_risk_client.get_supplier_risk_score(
        "SUP-00045"
    )

    assert result["score"] is None
    assert result["tier"] is None


def test_missing_api_key_raises_unavailable_error(monkeypatch):
    monkeypatch.setattr(
        settings,
        "SUPPLIER_PORTAL_SERVICE_API_KEY",
        "",
    )

    with pytest.raises(
        supplier_risk_client.SupplierRiskServiceUnavailableError
    ):
        supplier_risk_client.get_supplier_risk_score(
            "SUP-00045"
        )


def test_invalid_supplier_id_is_rejected():
    with pytest.raises(ValueError):
        supplier_risk_client.get_supplier_risk_score(
            "INVALID-ID"
        )


def test_transport_error_raises_unavailable_error():
    FakeClient.transport_error = httpx.ConnectError(
        "Connection failed"
    )

    with pytest.raises(
        supplier_risk_client.SupplierRiskServiceUnavailableError
    ):
        supplier_risk_client.get_supplier_risk_score(
            "SUP-00045"
        )


def test_server_error_raises_unavailable_error():
    request = httpx.Request(
        "GET",
        "http://localhost:8006/api/v1/suppliers/SUP-00045/risk-score",
    )
    response = httpx.Response(
        503,
        request=request,
    )

    FakeClient.response = FakeResponse(
        status_error=httpx.HTTPStatusError(
            "Service unavailable",
            request=request,
            response=response,
        )
    )

    with pytest.raises(
        supplier_risk_client.SupplierRiskServiceUnavailableError
    ):
        supplier_risk_client.get_supplier_risk_score(
            "SUP-00045"
        )


def test_client_error_raises_service_error():
    request = httpx.Request(
        "GET",
        "http://localhost:8006/api/v1/suppliers/SUP-00045/risk-score",
    )
    response = httpx.Response(
        404,
        request=request,
    )

    FakeClient.response = FakeResponse(
        status_error=httpx.HTTPStatusError(
            "Not found",
            request=request,
            response=response,
        )
    )

    with pytest.raises(
        supplier_risk_client.SupplierRiskServiceError
    ) as exc:
        supplier_risk_client.get_supplier_risk_score(
            "SUP-00045"
        )

    assert not isinstance(
        exc.value,
        supplier_risk_client.SupplierRiskServiceUnavailableError,
    )


def test_invalid_json_raises_invalid_response_error():
    FakeClient.response = FakeResponse(
        json_error=ValueError("Invalid JSON")
    )

    with pytest.raises(
        supplier_risk_client.SupplierRiskInvalidResponseError
    ):
        supplier_risk_client.get_supplier_risk_score(
            "SUP-00045"
        )


def test_wrong_supplier_id_in_response_is_rejected():
    response = valid_risk_response()
    response["supplier_id"] = "SUP-00023"

    FakeClient.response = FakeResponse(response)

    with pytest.raises(
        supplier_risk_client.SupplierRiskInvalidResponseError
    ):
        supplier_risk_client.get_supplier_risk_score(
            "SUP-00045"
        )


def test_invalid_tier_is_rejected():
    response = valid_risk_response()
    response["tier"] = "Unknown"

    FakeClient.response = FakeResponse(response)

    with pytest.raises(
        supplier_risk_client.SupplierRiskInvalidResponseError
    ):
        supplier_risk_client.get_supplier_risk_score(
            "SUP-00045"
        )


def test_inconsistent_null_score_and_tier_is_rejected():
    response = valid_risk_response()
    response["score"] = None

    FakeClient.response = FakeResponse(response)

    with pytest.raises(
        supplier_risk_client.SupplierRiskInvalidResponseError
    ):
        supplier_risk_client.get_supplier_risk_score(
            "SUP-00045"
        )
