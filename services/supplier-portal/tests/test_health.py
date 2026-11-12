from types import SimpleNamespace

from fastapi.testclient import TestClient

import app.main as main


def test_health_returns_200_when_all_consumers_enabled(monkeypatch):
    flags = (
        "KAFKA_ENABLED",
        "PO_KAFKA_ENABLED",
        "PO_OUTBOX_ENABLED",
        "SHIPMENT_OUTBOX_ENABLED",
        "ETA_KAFKA_ENABLED",
        "GOODS_RECEIVED_KAFKA_ENABLED",
    )
    for flag in flags:
        monkeypatch.setattr(main.settings, flag, True)

    runners = (
        main.kafka_consumer_runner,
        main.inv_po_approved_consumer_runner,
        main.po_ack_outbox_publisher_runner,
        main.shipment_outbox_publisher_runner,
        main.shipment_eta_consumer_runner,
        main.inventory_goods_received_runner,
    )
    for runner in runners:
        monkeypatch.setattr(
            runner, "_thread", SimpleNamespace(is_alive=lambda: True)
        )

    response = TestClient(main.app).get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "kafka_consumer_alive": True,
        "po_kafka_consumer_alive": True,
        "po_outbox_publisher_alive": True,
        "shipment_outbox_publisher_alive": True,
        "shipment_eta_consumer_alive": True,
        "goods_received_consumer_alive": True,
    }
