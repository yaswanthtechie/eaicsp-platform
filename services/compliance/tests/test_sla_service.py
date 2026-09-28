from app.services.sla_service import (
    SLAMetrics,
)


def test_sla_records_successful_request():
    metrics = SLAMetrics()

    metrics.record_request(
        duration_ms=100,
        success=True,
    )

    status = metrics.get_status()

    assert status["total_requests"] == 1
    assert status["successful_requests"] == 1
    assert status["failed_requests"] == 0
    assert status["slow_requests"] == 0
    assert status["average_latency_ms"] == 100


def test_sla_records_failed_request():
    metrics = SLAMetrics()

    metrics.record_request(
        duration_ms=100,
        success=False,
    )

    status = metrics.get_status()

    assert status["total_requests"] == 1
    assert status["successful_requests"] == 0
    assert status["failed_requests"] == 1


def test_sla_detects_slow_request():
    metrics = SLAMetrics()

    metrics.record_request(
        duration_ms=501,
        success=True,
    )

    status = metrics.get_status()

    assert status["total_requests"] == 1
    assert status["successful_requests"] == 1
    assert status["slow_requests"] == 1
    assert status["status"] == "degraded"


def test_sla_average_latency():
    metrics = SLAMetrics()

    metrics.record_request(
        duration_ms=100,
        success=True,
    )

    metrics.record_request(
        duration_ms=300,
        success=True,
    )

    status = metrics.get_status()

    assert status["total_requests"] == 2
    assert status["average_latency_ms"] == 200
    assert status["max_latency_ms"] == 300


def test_sla_request_at_threshold_is_not_slow():
    metrics = SLAMetrics()

    metrics.record_request(
        duration_ms=500,
        success=True,
    )

    status = metrics.get_status()

    assert status["total_requests"] == 1
    assert status["successful_requests"] == 1
    assert status["slow_requests"] == 0
    assert status["status"] == "healthy"


def test_sla_status_endpoint(client):
    response = client.get("/api/v1/compliance/sla")

    assert response.status_code == 200

    data = response.json()

    assert "total_requests" in data
    assert "successful_requests" in data
    assert "failed_requests" in data
    assert "slow_requests" in data
    assert "average_latency_ms" in data
    assert "max_latency_ms" in data
    assert "status" in data