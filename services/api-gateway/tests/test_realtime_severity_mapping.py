"""
Tests for BFF Live Dashboard Severity Mapping (Round 15 Flow C, Issue #320).

Verifies:
- Inventory: quantity_on_hand == 0 -> critical; stock available -> warning.
- IoT Anomaly: critical/high -> critical; medium -> warning; low -> info.
- Supplier Risk: escalating tier -> warning; de-escalating tier -> info; same-tier/unexpected -> info.
- ETA: always info.
- Forecast: SUCCESS -> info; PARTIAL -> warning.
- Pipeline: always info.
- Unknown event types: resolver fallback -> info, while gateway schema validation & DLQ routing remain intact.
- Outgoing envelope preservation: top-level severity added, producer envelope & payload preserved unchanged.
- End-to-end fanout broadcast: valid events broadcast with BFF-decided severity; duplicates dropped; DLQ on invalid.
"""

import asyncio
import copy
import json
import uuid
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.realtime_events import validate_realtime_event
from app.services.realtime.connection_manager import ConnectionManager
from app.services.realtime.deduplicator import Deduplicator
from app.services.realtime.dlq import DLQService
from app.services.realtime.kafka_consumer import RealtimeKafkaConsumerService
from app.services.realtime.severity import (
    SEVERITY_CRITICAL,
    SEVERITY_INFO,
    SEVERITY_WARNING,
    build_outgoing_event,
    resolve_event_severity,
    resolve_severity,
)
from tests.test_realtime_events_validation import (
    DATA_PIPELINE_COMPLETED_SAMPLE,
    ETA_SHIPMENT_PREDICTED_SAMPLE,
    FORECAST_BATCH_COMPLETED_SAMPLE,
    INVENTORY_STOCK_LOW_SAMPLE,
    IOT_ANOMALY_DETECTED_SAMPLE,
    SALES_ANOMALY_DETECTED_SAMPLE,
    SUPPLIER_RISK_SCORE_CHANGED_SAMPLE,
)


# ---------------------------------------------------------------------------
# 1. Inventory Event Severity Tests
# ---------------------------------------------------------------------------

class TestInventorySeverity:
    @pytest.mark.parametrize("quantity", [0, "0", -1])
    def test_inventory_quantity_zero_or_stockout_is_critical(self, quantity: Any):
        """When quantity_on_hand is 0, severity must be critical."""
        payload = {
            "sku_id": "SKU-000123",
            "warehouse_id": "WH-BLR-01",
            "quantity_on_hand": quantity,
            "reorder_point": 35,
            "safety_stock": 15,
            "avg_daily_demand": 4.5,
        }
        severity = resolve_severity("inventory.stock.low", payload)
        assert severity == SEVERITY_CRITICAL

    @pytest.mark.parametrize("quantity", [1, 5, 8, 34, 100])
    def test_inventory_positive_quantity_is_warning(self, quantity: int):
        """When quantity_on_hand > 0, severity must be warning."""
        payload = {
            "sku_id": "SKU-000123",
            "warehouse_id": "WH-BLR-01",
            "quantity_on_hand": quantity,
            "reorder_point": 35,
            "safety_stock": 15,
            "avg_daily_demand": 4.5,
        }
        severity = resolve_severity("inventory.stock.low", payload)
        assert severity == SEVERITY_WARNING

    def test_inventory_payload_not_mutated(self):
        """Severity resolver must not mutate the payload."""
        payload = {"quantity_on_hand": 0}
        orig = dict(payload)
        resolve_severity("inventory.stock.low", payload)
        assert payload == orig


# ---------------------------------------------------------------------------
# 2. IoT Anomaly Event Severity Tests
# ---------------------------------------------------------------------------

class TestIotAnomalySeverity:
    @pytest.mark.parametrize("iot_sev", ["critical", "CRITICAL", "high", "HIGH", "High"])
    def test_iot_critical_and_high_map_to_critical(self, iot_sev: str):
        """payload.severity of 'critical' or 'high' maps to top-level 'critical'."""
        payload = {"severity": iot_sev, "message": "Anomaly"}
        assert resolve_severity("iot.anomaly.detected", payload) == SEVERITY_CRITICAL

    @pytest.mark.parametrize("iot_sev", ["medium", "MEDIUM", "Medium"])
    def test_iot_medium_maps_to_warning(self, iot_sev: str):
        """payload.severity of 'medium' maps to top-level 'warning'."""
        payload = {"severity": iot_sev, "message": "Anomaly"}
        assert resolve_severity("iot.anomaly.detected", payload) == SEVERITY_WARNING

    @pytest.mark.parametrize("iot_sev", ["low", "LOW", "Low"])
    def test_iot_low_maps_to_info(self, iot_sev: str):
        """payload.severity of 'low' maps to top-level 'info'."""
        payload = {"severity": iot_sev, "message": "Anomaly"}
        assert resolve_severity("iot.anomaly.detected", payload) == SEVERITY_INFO

    def test_iot_producer_severity_preserved(self):
        """Producer payload.severity must not be removed or overwritten."""
        payload = {"severity": "high", "episode_id": "EP-01"}
        orig_severity = payload["severity"]
        top_severity = resolve_severity("iot.anomaly.detected", payload)
        assert top_severity == SEVERITY_CRITICAL
        assert payload["severity"] == orig_severity


# ---------------------------------------------------------------------------
# 3. Supplier Risk Event Severity Tests
# ---------------------------------------------------------------------------

class TestSupplierRiskSeverity:
    @pytest.mark.parametrize(
        "prev_tier,new_tier",
        [
            ("low", "medium"),
            ("medium", "high"),
            ("low", "high"),
            ("LOW", "MEDIUM"),
            ("MEDIUM", "HIGH"),
        ],
    )
    def test_supplier_risk_tier_increase_is_warning(self, prev_tier: str, new_tier: str):
        """When risk tier escalates (low < medium < high), severity is warning."""
        payload = {"previous_tier": prev_tier, "new_tier": new_tier}
        assert resolve_severity("supplierrisk.score.changed", payload) == SEVERITY_WARNING

    @pytest.mark.parametrize(
        "prev_tier,new_tier",
        [
            ("high", "medium"),
            ("medium", "low"),
            ("high", "low"),
            ("HIGH", "MEDIUM"),
            ("MEDIUM", "LOW"),
        ],
    )
    def test_supplier_risk_tier_decrease_is_info(self, prev_tier: str, new_tier: str):
        """When risk tier improves (decreases), severity is info."""
        payload = {"previous_tier": prev_tier, "new_tier": new_tier}
        assert resolve_severity("supplierrisk.score.changed", payload) == SEVERITY_INFO

    @pytest.mark.parametrize("tier", ["low", "medium", "high", "LOW", "MEDIUM", "HIGH"])
    def test_supplier_risk_same_tier_is_info(self, tier: str):
        """When tier remains unchanged, severity safely falls back to info."""
        payload = {"previous_tier": tier, "new_tier": tier}
        assert resolve_severity("supplierrisk.score.changed", payload) == SEVERITY_INFO

    @pytest.mark.parametrize(
        "prev_tier,new_tier",
        [
            ("unknown", "high"),
            ("low", "catastrophic"),
            (None, "medium"),
            ("low", None),
        ],
    )
    def test_supplier_risk_unexpected_tier_safe_fallback_info(self, prev_tier: Any, new_tier: Any):
        """Unexpected or missing tier values fall back safely to info."""
        payload = {"previous_tier": prev_tier, "new_tier": new_tier}
        assert resolve_severity("supplierrisk.score.changed", payload) == SEVERITY_INFO

    def test_new_tier_alone_does_not_determine_severity(self):
        """Verify direction of change is evaluated, not just new_tier."""
        # Both have new_tier="high", but different previous_tier:
        increased = {"previous_tier": "low", "new_tier": "high"}
        same = {"previous_tier": "high", "new_tier": "high"}
        assert resolve_severity("supplierrisk.score.changed", increased) == SEVERITY_WARNING
        assert resolve_severity("supplierrisk.score.changed", same) == SEVERITY_INFO


# ---------------------------------------------------------------------------
# 4. ETA Event Severity Tests
# ---------------------------------------------------------------------------

class TestEtaSeverity:
    @pytest.mark.parametrize("eta_days", [0.5, 5.2, 30.0])
    def test_eta_always_info(self, eta_days: float):
        """eta.shipment.predicted without predicted_delay_days maps to info."""
        payload = {
            "shipment_id": "SHP-2026-000077",
            "po_number": "PO-2026-000123",
            "eta_days": eta_days,
        }
        assert resolve_severity("eta.shipment.predicted", payload) == SEVERITY_INFO

    @pytest.mark.parametrize("delay", [4, 4.0, 4.5, 5, 10.0, "4", "5.2"])
    def test_eta_delay_4_or_more_is_critical(self, delay: Any):
        """predicted_delay_days >= 4 maps to critical."""
        payload = {
            "shipment_id": "SHP-2026-000077",
            "po_number": "PO-2026-000123",
            "eta_days": 8.0,
            "predicted_delay_days": delay,
        }
        assert resolve_severity("eta.shipment.predicted", payload) == SEVERITY_CRITICAL

    @pytest.mark.parametrize("delay", [1, 1.0, 1.5, 2, 3, 3.0, 3.9, "1", "3.0"])
    def test_eta_delay_1_to_3_is_warning(self, delay: Any):
        """predicted_delay_days between 1 and 3 (1 <= delay < 4) maps to warning."""
        payload = {
            "shipment_id": "SHP-2026-000077",
            "po_number": "PO-2026-000123",
            "eta_days": 5.0,
            "predicted_delay_days": delay,
        }
        assert resolve_severity("eta.shipment.predicted", payload) == SEVERITY_WARNING

    @pytest.mark.parametrize("delay", [0, 0.0, -1, -2.5, -5, "0", "-1.0"])
    def test_eta_delay_0_or_negative_is_info(self, delay: Any):
        """predicted_delay_days <= 0 maps to info."""
        payload = {
            "shipment_id": "SHP-2026-000077",
            "po_number": "PO-2026-000123",
            "eta_days": 3.0,
            "predicted_delay_days": delay,
        }
        assert resolve_severity("eta.shipment.predicted", payload) == SEVERITY_INFO

    def test_eta_missing_delay_field_is_info(self):
        """Missing predicted_delay_days or None maps to info."""
        payload_missing = {
            "shipment_id": "SHP-2026-000077",
            "po_number": "PO-2026-000123",
            "eta_days": 5.0,
        }
        payload_none = {
            "shipment_id": "SHP-2026-000077",
            "po_number": "PO-2026-000123",
            "eta_days": 5.0,
            "predicted_delay_days": None,
        }
        assert resolve_severity("eta.shipment.predicted", payload_missing) == SEVERITY_INFO
        assert resolve_severity("eta.shipment.predicted", payload_none) == SEVERITY_INFO

    @pytest.mark.parametrize("invalid_delay", ["not-a-number", {}, [], float("nan"), float("inf")])
    def test_eta_invalid_delay_field_fallback_info(self, invalid_delay: Any):
        """Invalid non-numeric or NaN/inf predicted_delay_days falls back safely to info."""
        payload = {
            "shipment_id": "SHP-2026-000077",
            "po_number": "PO-2026-000123",
            "predicted_delay_days": invalid_delay,
        }
        assert resolve_severity("eta.shipment.predicted", payload) == SEVERITY_INFO

    def test_eta_payload_not_mutated(self):
        """Severity resolver must not mutate ETA payload."""
        payload = {"shipment_id": "SHP-2026-000077", "predicted_delay_days": 4.5}
        orig = dict(payload)
        resolve_severity("eta.shipment.predicted", payload)
        assert payload == orig


# ---------------------------------------------------------------------------
# 5. Sales Anomaly Event Severity Tests
# ---------------------------------------------------------------------------

class TestSalesAnomalySeverity:
    @pytest.mark.parametrize("sev", ["high", "HIGH", "High", "  high  "])
    def test_sales_anomaly_high_is_critical(self, sev: str):
        """payload.severity == 'high' maps to critical."""
        payload = {
            "sku_id": "SKU-000123",
            "warehouse_id": "WH-BLR-01",
            "severity": sev,
            "quantity": 250,
        }
        assert resolve_severity("anomaly.sales.detected", payload) == SEVERITY_CRITICAL

    @pytest.mark.parametrize("sev", ["medium", "MEDIUM", "Medium", "  medium  "])
    def test_sales_anomaly_medium_is_warning(self, sev: str):
        """payload.severity == 'medium' maps to warning."""
        payload = {
            "sku_id": "SKU-000123",
            "warehouse_id": "WH-BLR-01",
            "severity": sev,
            "quantity": 100,
        }
        assert resolve_severity("anomaly.sales.detected", payload) == SEVERITY_WARNING

    @pytest.mark.parametrize("sev", ["low", "LOW", "Low", "  low  "])
    def test_sales_anomaly_low_is_info(self, sev: str):
        """payload.severity == 'low' maps to info."""
        payload = {
            "sku_id": "SKU-000123",
            "warehouse_id": "WH-BLR-01",
            "severity": sev,
            "quantity": 55,
        }
        assert resolve_severity("anomaly.sales.detected", payload) == SEVERITY_INFO

    @pytest.mark.parametrize("unexpected", [None, "extreme", "critical", "catastrophic", 123, {}])
    def test_sales_anomaly_missing_or_unexpected_fallback_info(self, unexpected: Any):
        """Missing or unrecognized severity falls back safely to info."""
        payload = {
            "sku_id": "SKU-000123",
            "warehouse_id": "WH-BLR-01",
            "severity": unexpected,
        }
        assert resolve_severity("anomaly.sales.detected", payload) == SEVERITY_INFO

    def test_sales_anomaly_payload_not_mutated(self):
        """Severity resolver must not mutate sales anomaly payload."""
        payload = {"sku_id": "SKU-000123", "severity": "high"}
        orig = dict(payload)
        resolve_severity("anomaly.sales.detected", payload)
        assert payload == orig


# ---------------------------------------------------------------------------
# 5. Forecast Event Severity Tests
# ---------------------------------------------------------------------------

class TestForecastSeverity:
    @pytest.mark.parametrize("status", ["SUCCESS", "success", "Success"])
    def test_forecast_success_is_info(self, status: str):
        """forecast.batch.completed with status SUCCESS maps to info."""
        payload = {"status": status, "run_id": "BATCH-01"}
        assert resolve_severity("forecast.batch.completed", payload) == SEVERITY_INFO

    @pytest.mark.parametrize("status", ["PARTIAL", "partial", "Partial"])
    def test_forecast_partial_is_warning(self, status: str):
        """forecast.batch.completed with status PARTIAL maps to warning."""
        payload = {"status": status, "run_id": "BATCH-01"}
        assert resolve_severity("forecast.batch.completed", payload) == SEVERITY_WARNING

    def test_forecast_missing_or_unexpected_status_fallback_info(self):
        """Unexpected status falls back safely to info."""
        payload = {"status": "OTHER"}
        assert resolve_severity("forecast.batch.completed", payload) == SEVERITY_INFO


# ---------------------------------------------------------------------------
# 6. Pipeline Event Severity Tests
# ---------------------------------------------------------------------------

class TestPipelineSeverity:
    def test_pipeline_completed_is_info(self):
        """data.pipeline.completed always maps to info."""
        payload = {"run_id": 1042, "status": "SUCCESS"}
        assert resolve_severity("data.pipeline.completed", payload) == SEVERITY_INFO


# ---------------------------------------------------------------------------
# 7. Unknown Event Type & Fallback Tests
# ---------------------------------------------------------------------------

class TestUnknownEventTypeSeverity:
    @pytest.mark.parametrize(
        "unknown_type",
        [
            "orders.order.cancelled",
            "payment.received",
            "custom.alert.triggered",
            "",
            "unknown",
        ],
    )
    def test_unknown_event_type_severity_returns_info(self, unknown_type: str):
        """Severity resolver returns 'info' fallback for unknown event types."""
        assert resolve_severity(unknown_type, {}) == SEVERITY_INFO

    def test_unknown_event_type_fails_schema_validation(self):
        """
        Verify that while the severity resolver returns 'info',
        the schema validator strictly rejects unknown event types.
        """
        raw_event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "unknown.event.type",
            "event_version": 1,
            "occurred_at": "2026-10-15T10:00:00Z",
            "producer": "unknown-service",
            "payload": {"foo": "bar"},
        }
        is_valid, dedup_key, error = validate_realtime_event(raw_event)
        assert is_valid is False
        assert "Unsupported event_type" in error

    def test_resolve_event_severity_with_invalid_inputs(self):
        """Resolver handles non-dict, missing event_type, and None inputs gracefully."""
        assert resolve_event_severity(None) == SEVERITY_INFO  # type: ignore[arg-type]
        assert resolve_event_severity("not a dict") == SEVERITY_INFO  # type: ignore[arg-type]
        assert resolve_event_severity({}) == SEVERITY_INFO
        assert resolve_event_severity({"event_type": None}) == SEVERITY_INFO  # type: ignore[dict-item]


# ---------------------------------------------------------------------------
# 8. Outgoing Envelope Structure & Preservation Tests
# ---------------------------------------------------------------------------

class TestOutgoingEnvelopePreservation:
    def test_build_outgoing_event_preserves_envelope_and_payload(self):
        """
        BFF preserves all producer envelope fields and exact payload,
        adding only top-level 'severity'.
        """
        original_event = {
            "event_id": "test-uuid-1234",
            "event_type": "iot.anomaly.detected",
            "event_version": 1,
            "occurred_at": "2026-10-15T10:46:12Z",
            "producer": "anomaly-detection-service",
            "trace_id": "trace-987",
            "payload": {
                "episode_id": "WH-BLR-01-S1|2026-10-15T10:05:00Z",
                "sensor_id": "WH-BLR-01-S1",
                "warehouse_id": "WH-BLR-01",
                "severity": "high",
                "message": "Cold-chain reading abnormal",
            },
        }

        orig_copy = copy.deepcopy(original_event)
        outgoing = build_outgoing_event(original_event)

        # 1. Input dictionary is not mutated
        assert original_event == orig_copy

        # 2. Top-level severity added
        assert outgoing["severity"] == SEVERITY_CRITICAL

        # 3. All original envelope fields preserved
        assert outgoing["event_id"] == original_event["event_id"]
        assert outgoing["event_type"] == original_event["event_type"]
        assert outgoing["event_version"] == original_event["event_version"]
        assert outgoing["occurred_at"] == original_event["occurred_at"]
        assert outgoing["producer"] == original_event["producer"]
        assert outgoing["trace_id"] == original_event["trace_id"]

        # 4. Payload preserved exactly as received
        assert outgoing["payload"] == original_event["payload"]
        assert outgoing["payload"]["severity"] == "high"  # Producer payload severity untouched!

        # 5. Severity is not placed inside payload
        assert "severity" in outgoing
        assert outgoing["payload"]["severity"] == "high"  # Not overwritten by critical

    def test_build_outgoing_event_overwrites_preexisting_top_level_severity(self):
        """BFF decides top-level severity, overriding any preexisting field."""
        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "inventory.stock.low",
            "severity": "info",  # Preexisting invalid severity
            "payload": {"quantity_on_hand": 0},
        }
        outgoing = build_outgoing_event(event)
        assert outgoing["severity"] == SEVERITY_CRITICAL


# ---------------------------------------------------------------------------
# 9. End-to-End Consumer Pipeline Tests with Severity Fanout
# ---------------------------------------------------------------------------

@pytest.fixture
def consumer_setup():
    conn_mgr = MagicMock(spec=ConnectionManager)
    conn_mgr.broadcast = AsyncMock(return_value=1)
    dedup = Deduplicator(max_size=100)
    mock_producer = AsyncMock()
    mock_producer.send_and_wait = AsyncMock()
    dlq_svc = DLQService(producer=mock_producer)

    service = RealtimeKafkaConsumerService(
        conn_mgr=conn_mgr,
        dedup=dedup,
        dlq_svc=dlq_svc,
        enabled=False,
    )
    return service, conn_mgr, mock_producer


class TestRealtimeConsumerSeverityFanout:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "sample,expected_severity",
        [
            (INVENTORY_STOCK_LOW_SAMPLE, SEVERITY_WARNING),
            (IOT_ANOMALY_DETECTED_SAMPLE, SEVERITY_CRITICAL),
            (SUPPLIER_RISK_SCORE_CHANGED_SAMPLE, SEVERITY_WARNING),
            (ETA_SHIPMENT_PREDICTED_SAMPLE, SEVERITY_INFO),
            (FORECAST_BATCH_COMPLETED_SAMPLE, SEVERITY_INFO),
            (DATA_PIPELINE_COMPLETED_SAMPLE, SEVERITY_INFO),
            (SALES_ANOMALY_DETECTED_SAMPLE, SEVERITY_CRITICAL),
        ],
        ids=[
            "inventory_stock_low_warning",
            "iot_anomaly_detected_critical",
            "supplierrisk_score_changed_warning",
            "eta_shipment_predicted_info",
            "forecast_batch_completed_info",
            "data_pipeline_completed_info",
            "sales_anomaly_detected_critical",
        ],
    )
    async def test_canonical_samples_broadcast_with_correct_severity(
        self, consumer_setup, sample: Dict[str, Any], expected_severity: str
    ):
        """Each canonical event is broadcast with its BFF-decided severity."""
        service, conn_mgr, mock_producer = consumer_setup

        handled = await service.process_message(
            topic=sample["event_type"],
            value=json.dumps(sample).encode("utf-8"),
        )

        assert handled is True
        conn_mgr.broadcast.assert_called_once()
        broadcast_text = conn_mgr.broadcast.call_args[0][0]
        broadcast_data = json.loads(broadcast_text)

        # Top-level severity is present and matches expectation
        assert broadcast_data["severity"] == expected_severity

        # Original payload remains unchanged
        assert broadcast_data["payload"] == sample["payload"]

        # Original envelope fields remain present
        assert broadcast_data["event_id"] == sample["event_id"]
        assert broadcast_data["event_type"] == sample["event_type"]
        assert broadcast_data["event_version"] == sample["event_version"]
        assert broadcast_data["occurred_at"] == sample["occurred_at"]
        assert broadcast_data["producer"] == sample["producer"]

        # No DLQ routing occurred
        mock_producer.send_and_wait.assert_not_called()

    @pytest.mark.asyncio
    async def test_inventory_zero_quantity_broadcasts_critical(self, consumer_setup):
        """Inventory event with quantity_on_hand == 0 broadcasts severity 'critical'."""
        service, conn_mgr, _ = consumer_setup
        event = copy.deepcopy(INVENTORY_STOCK_LOW_SAMPLE)
        event["event_id"] = str(uuid.uuid4())
        event["payload"]["quantity_on_hand"] = 0

        await service.process_message(
            topic=event["event_type"],
            value=json.dumps(event).encode("utf-8"),
        )

        broadcast_text = conn_mgr.broadcast.call_args[0][0]
        broadcast_data = json.loads(broadcast_text)
        assert broadcast_data["severity"] == SEVERITY_CRITICAL
        assert broadcast_data["payload"]["quantity_on_hand"] == 0

    @pytest.mark.asyncio
    async def test_forecast_partial_broadcasts_warning(self, consumer_setup):
        """Forecast event with status PARTIAL broadcasts severity 'warning'."""
        service, conn_mgr, _ = consumer_setup
        event = copy.deepcopy(FORECAST_BATCH_COMPLETED_SAMPLE)
        event["event_id"] = str(uuid.uuid4())
        event["payload"]["status"] = "PARTIAL"

        await service.process_message(
            topic=event["event_type"],
            value=json.dumps(event).encode("utf-8"),
        )

        broadcast_text = conn_mgr.broadcast.call_args[0][0]
        broadcast_data = json.loads(broadcast_text)
        assert broadcast_data["severity"] == SEVERITY_WARNING
        assert broadcast_data["payload"]["status"] == "PARTIAL"

    @pytest.mark.asyncio
    async def test_supplier_risk_downgrade_broadcasts_info(self, consumer_setup):
        """Supplier risk tier decrease (high -> medium) broadcasts severity 'info'."""
        service, conn_mgr, _ = consumer_setup
        event = copy.deepcopy(SUPPLIER_RISK_SCORE_CHANGED_SAMPLE)
        event["event_id"] = str(uuid.uuid4())
        event["payload"]["previous_tier"] = "high"
        event["payload"]["new_tier"] = "medium"

        await service.process_message(
            topic=event["event_type"],
            value=json.dumps(event).encode("utf-8"),
        )

        broadcast_text = conn_mgr.broadcast.call_args[0][0]
        broadcast_data = json.loads(broadcast_text)
        assert broadcast_data["severity"] == SEVERITY_INFO

    @pytest.mark.asyncio
    async def test_duplicate_event_is_not_broadcast(self, consumer_setup):
        """Duplicate events must be dropped before fanout broadcast."""
        service, conn_mgr, _ = consumer_setup
        event = copy.deepcopy(INVENTORY_STOCK_LOW_SAMPLE)
        event["event_id"] = str(uuid.uuid4())

        # First delivery
        h1 = await service.process_message(
            topic=event["event_type"],
            value=json.dumps(event).encode("utf-8"),
        )
        assert h1 is True
        assert conn_mgr.broadcast.call_count == 1

        # Duplicate delivery
        h2 = await service.process_message(
            topic=event["event_type"],
            value=json.dumps(event).encode("utf-8"),
        )
        assert h2 is True
        # Broadcast count must not increment
        assert conn_mgr.broadcast.call_count == 1

    @pytest.mark.asyncio
    async def test_unknown_event_type_routed_to_dlq_not_broadcast(self, consumer_setup):
        """
        Unknown event type is rejected by schema validation and routed to DLQ.
        It is NOT broadcast to WebSocket clients.
        """
        service, conn_mgr, mock_producer = consumer_setup
        unknown_event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "billing.invoice.generated",
            "event_version": 1,
            "occurred_at": "2026-10-15T10:00:00Z",
            "producer": "billing-service",
            "payload": {"invoice_id": "INV-001"},
        }

        commit_called = False

        async def mock_commit():
            nonlocal commit_called
            commit_called = True

        handled = await service.process_message(
            topic="billing.invoice.generated",
            value=json.dumps(unknown_event).encode("utf-8"),
            offset=42,
            commit_callback=mock_commit,
        )

        assert handled is False
        assert commit_called is True
        conn_mgr.broadcast.assert_not_called()
        mock_producer.send_and_wait.assert_called_once()
        assert mock_producer.send_and_wait.call_args[0][0] == "billing.invoice.generated.dlq"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "delay,expected_sev",
        [
            (5.0, SEVERITY_CRITICAL),
            (2.0, SEVERITY_WARNING),
            (0.0, SEVERITY_INFO),
            (-1.5, SEVERITY_INFO),
            (None, SEVERITY_INFO),
        ],
    )
    async def test_eta_delay_fanout_broadcasts_correct_severity(
        self, consumer_setup, delay: Any, expected_sev: str
    ):
        """ETA events with predicted_delay_days broadcast with correct severity."""
        service, conn_mgr, _ = consumer_setup
        event = copy.deepcopy(ETA_SHIPMENT_PREDICTED_SAMPLE)
        event["event_id"] = str(uuid.uuid4())
        if delay is not None:
            event["payload"]["predicted_delay_days"] = delay
        else:
            event["payload"].pop("predicted_delay_days", None)

        handled = await service.process_message(
            topic=event["event_type"],
            value=json.dumps(event).encode("utf-8"),
        )
        assert handled is True
        broadcast_text = conn_mgr.broadcast.call_args[0][0]
        broadcast_data = json.loads(broadcast_text)
        assert broadcast_data["severity"] == expected_sev
        assert broadcast_data["payload"] == event["payload"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "producer_sev,expected_sev",
        [
            ("high", SEVERITY_CRITICAL),
            ("medium", SEVERITY_WARNING),
            ("low", SEVERITY_INFO),
        ],
    )
    async def test_sales_anomaly_fanout_broadcasts_correct_severity(
        self, consumer_setup, producer_sev: str, expected_sev: str
    ):
        """Sales anomaly events broadcast with correct mapped severity."""
        service, conn_mgr, _ = consumer_setup
        event = copy.deepcopy(SALES_ANOMALY_DETECTED_SAMPLE)
        event["event_id"] = str(uuid.uuid4())
        event["payload"]["severity"] = producer_sev

        handled = await service.process_message(
            topic=event["event_type"],
            value=json.dumps(event).encode("utf-8"),
        )
        assert handled is True
        broadcast_text = conn_mgr.broadcast.call_args[0][0]
        broadcast_data = json.loads(broadcast_text)
        assert broadcast_data["severity"] == expected_sev
        assert broadcast_data["payload"]["severity"] == producer_sev
        assert broadcast_data["payload"] == event["payload"]

