import json
import time
import uuid
import pytest
from kafka import KafkaConsumer
from app.core.event_publisher import publish_event

@pytest.mark.integration
def test_publish_platform_user_locked_event_to_kafka():
    """
    Integration test:

        Platform Service
              |
              v
        publish_event()
              |
              v
           Kafka
              |
              v
    platform.user.locked
              |
              v
          Consumer

    Requires Kafka running on localhost:9092.
    """

    topic = "platform.user.locked"

    consumer_group = f"platform-test-{uuid.uuid4()}"

    consumer = KafkaConsumer(
        bootstrap_servers="localhost:9092",
        group_id=consumer_group,
        auto_offset_reset="latest",
        enable_auto_commit=True,
        value_deserializer=lambda value: json.loads(
            value.decode("utf-8")
        ),
    )

    try:
        # ----------------------------------------------------
        # 1. Subscribe before publishing
        # ----------------------------------------------------

        consumer.subscribe([topic])

        # Force Kafka consumer group assignment.
        # This is important because otherwise the event could
        # be published before the consumer gets its partition.
        deadline = time.time() + 10

        while not consumer.assignment() and time.time() < deadline:
            consumer.poll(timeout_ms=500)

        assert consumer.assignment(), (
            "Kafka consumer did not receive a partition assignment"
        )

        # ----------------------------------------------------
        # 2. Publish event
        # ----------------------------------------------------

        test_user_id = 999999

        published_event = publish_event(
            "platform.user.locked",
            {
                "user_id": test_user_id,
            },
        )

        # ----------------------------------------------------
        # 3. Read event from Kafka
        # ----------------------------------------------------

        received_event = None

        deadline = time.time() + 10

        while time.time() < deadline:

            records = consumer.poll(
                timeout_ms=1000
            )

            for messages in records.values():

                for message in messages:

                    event = message.value

                    if (
                        event.get("event_type")
                        == "platform.user.locked"
                        and event.get("payload", {}).get("user_id")
                        == test_user_id
                    ):
                        received_event = event
                        break

                if received_event:
                    break

            if received_event:
                break

        assert received_event is not None, (
            "platform.user.locked event was not received from Kafka"
        )

        # ----------------------------------------------------
        # 4. Verify standard event envelope
        # ----------------------------------------------------

        assert set(received_event.keys()) == {
            "id",
            "event_type",
            "event_version",
            "occurred_at",
            "producer",
            "payload",
        }

        # ----------------------------------------------------
        # 5. Verify event ID
        # ----------------------------------------------------

        parsed_uuid = uuid.UUID(
            received_event["id"]
        )

        assert str(parsed_uuid) == received_event["id"]

        # ----------------------------------------------------
        # 6. Verify event metadata
        # ----------------------------------------------------

        assert received_event["event_type"] == (
            "platform.user.locked"
        )

        assert received_event["event_version"] == 1

        assert received_event["producer"] == (
            "platform-service"
        )

        assert received_event["occurred_at"].endswith("Z")

        # ----------------------------------------------------
        # 7. Verify payload
        # ----------------------------------------------------

        assert received_event["payload"] == {
            "user_id": test_user_id,
        }

        # ----------------------------------------------------
        # 8. Verify publisher returned the same event
        # ----------------------------------------------------

        assert received_event["id"] == (
            published_event["id"]
        )

    finally:
        consumer.close()